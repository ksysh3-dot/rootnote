"""Q0 measurements with explicit obligations, eligibility and calibrated filters.

This is an offline evaluator, never a listening/buzz classifier. Table parsing is
independent of the native lookup implementation. No renderer is used as oracle.
"""
from functools import lru_cache
from pathlib import Path
import re
import numpy as np
from scipy.signal import firwin, fftconvolve, periodogram, find_peaks
from scipy.optimize import minimize_scalar

TABLE = Path(__file__).resolve().parents[3] / 'app/src/main/cpp/libpvb/pvb_vb_tables.h'
VERSION = 'pvb.measurement.v4'

def temporal_metrics(values, time, expected_rate, expected_phase=0.):
    """Estimate modulation rate without inserting the known rate as a seed.

    Short observations below three cycles cannot certify rate preservation.
    Phase uses the declared source clock, never a best alignment per output.
    """
    step=max(1,int(round(1/(400*(time[1]-time[0])))))
    y=np.asarray(values)[::step];t=np.asarray(time)[::step]
    centered=y-np.mean(y)
    if np.mean(centered**2)<max(1e-20,np.mean(y*y)*1e-14):
        return dict(rate_hz=None,rate_status='no_modulation',phase_error_rad=None,temporal_passed=False)
    fs=1/(t[1]-t[0])
    freq,power=periodogram(centered,fs=fs,window='hann',nfft=max(16384,1<<int(np.ceil(np.log2(len(y))))))
    valid=(freq>=.25)&(freq<=30);freq=freq[valid];power=power[valid]
    peaks,_=find_peaks(power)
    candidates=peaks[np.argsort(power[peaks])[-5:]] if len(peaks) else [int(np.argmax(power))]
    def fit(rate):
        matrix=np.column_stack((np.ones(len(t)),np.cos(2*np.pi*rate*t),np.sin(2*np.pi*rate*t)))
        coef=np.linalg.lstsq(matrix,y,rcond=None)[0]
        return float(np.mean((matrix@coef-y)**2)),coef
    radius=max(.25,1/(t[-1]-t[0]))
    results=[minimize_scalar(lambda r:fit(r)[0],bounds=(max(.25,freq[i]-radius),min(30.,freq[i]+radius)),
                             method='bounded',options={'xatol':1e-7}) for i in candidates]
    best=min(results,key=lambda r:r.fun);rate=float(best.x)
    _,coef=fit(expected_rate)
    phase=float(np.arctan2(coef[1],coef[2]))
    phase_error=float(np.arctan2(np.sin(phase-expected_phase),np.cos(phase-expected_phase)))
    enough=(t[-1]-t[0])*rate>=3
    error=abs(rate-expected_rate)/expected_rate
    return dict(rate_hz=rate,rate_relative_error=error,rate_status='measurable' if enough else 'insufficient_cycles',
                phase_error_rad=phase_error,phase_limit_rad=float(np.pi/6),
                temporal_passed=bool(error<=.05 and abs(phase_error)<=np.pi/6) if enough else None)

@lru_cache(maxsize=1)
def tables():
    text = TABLE.read_text()
    def read(name):
        body = re.search(r'\b' + name + r'\[\d+\] = \{(.*?)\};', text, re.S)
        if body is None:
            raise ValueError('Missing table: ' + name)
        return np.fromstring(body[1].replace('\n', ''), sep=',')
    grid = read('kGridHz')
    return grid, read('kWeights').reshape(7, len(grid)), read('kGain'), read('kPsi')

def table_at(frequency):
    grid, weights, gain, phase = tables()
    return (np.array([np.interp(frequency, grid, w) for w in weights]),
            float(np.interp(frequency, grid, gain)), phase.copy())

def emission_weights(frequency,algorithm=2,upper_blend=None):
    weights,_,_=table_at(frequency)
    if algorithm in (3,4,5):
        if algorithm==5 and upper_blend is None:
            raise ValueError('Adaptive harmonic obligations require a recorded budget')
        blend=(1. if algorithm==4 else 0.) if upper_blend is None else upper_blend
        for j,k in enumerate(range(2,9)):
            if k*frequency>220:
                gentle=10**(-12*np.log2(k*frequency/220)/20)
                weights[j]*=gentle+blend*(gentle*gentle-gentle)
    return weights

def nmse_db(actual, reference):
    energy = float(np.mean(np.asarray(reference)**2))
    if energy < 1e-24:
        raise ValueError('Use absolute error for a silent reference')
    return float(10*np.log10(max(float(np.mean((actual-reference)**2))/energy, 1e-30)))

@lru_cache(maxsize=32)
def _lowpass(fs, rate):
    # A20Hz modulation must not sit on a20Hz cutoff. Longer signals and
    # nonoverlapping sidebands remain caller obligations.
    return firwin(2*round(fs/6)+1, max(20., 1.5*rate), fs=fs, window=('kaiser', 10))

def _demod(v, fs, center, rate, start, stop, latency, temporal=False):
    t = np.arange(len(v))/fs
    lo = max(0, int(start*fs)); hi = min(len(v), int(stop*fs))
    taps = _lowpass(fs, rate)
    if hi <= lo or lo < len(taps)//2 or hi+len(taps)//2 > len(v):
        raise ValueError('Evaluation interval needs filter settling margins')
    z = fftconvolve(2*v*np.exp(-2j*np.pi*center*t), taps, mode='same')
    phase_time = t[lo:hi] - latency
    design = np.column_stack((np.ones(hi-lo), np.cos(2*np.pi*rate*phase_time),
                              np.sin(2*np.pi*rate*phase_time)))
    coef = np.linalg.lstsq(design, np.abs(z[lo:hi]), rcond=None)[0]
    mean = float(coef[0])
    depth = float(np.hypot(coef[1], coef[2])/mean) if mean > 1e-15 else None
    result=dict(depth=depth, phase_rad=float(np.arctan2(coef[1], coef[2])) if depth is not None else None,
                rms_dbfs=float(20*np.log10(max(float(np.sqrt(np.mean(np.abs(z[lo:hi])**2)/2)), 1e-30))))
    if temporal:result.update(temporal_metrics(abs(z[lo:hi]),phase_time,rate))
    return result

def am_metric(signal, fs, carrier, order, rate, expected_depth, expected_weight,
              start=1.25, stop=3., latency=0., overlap=False,
              reference_peak=.15, minimum_rms_dbfs=-100.,temporal=False):
    result = dict(order=order, center_hz=carrier*order, expected_weight=float(expected_weight),
                  expected_depth=expected_depth, status='not_requested', passed=None)
    if expected_weight <= 1e-4:
        return result
    if overlap:
        result['status'] = 'overlap_ambiguous'
        return result
    if reference_peak < 1e-10:
        result['status'] = 'below_evaluation_floor'
        return result
    v = np.asarray(signal, dtype=float)
    if v.ndim == 2:
        v = np.mean(v, axis=1)
    if not np.isfinite(v).all():
        result.update(status='invalid_measurement', passed=False, reason='nonfinite_output')
        return result
    t = np.arange(len(v))/fs
    ideal = reference_peak*(1+expected_depth*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*carrier*order*t)
    calibration = _demod(ideal, fs, carrier*order, rate, start, stop, 0.)
    cal_error = abs(calibration['depth']-expected_depth)
    cal_ok = cal_error <= max(.0001, abs(expected_depth)*.01)
    result['calibration'] = dict(depth=calibration['depth'], absolute_error=cal_error, passed=bool(cal_ok))
    if not cal_ok:
        result.update(status='invalid_measurement', passed=False, reason='control_filter_error')
        return result
    measured = _demod(v, fs, carrier*order, rate, start, stop, latency,temporal)
    result.update(measured)
    result['minimum_rms_dbfs'] = minimum_rms_dbfs
    if measured['rms_dbfs'] < minimum_rms_dbfs or measured['depth'] is None:
        result.update(status='expected_but_missing', passed=False, depth=None, phase_rad=None)
        return result
    error = abs(measured['depth']-expected_depth)
    tolerance = abs(expected_depth)*.1 if expected_depth >= .1 else .01
    result.update(status='measurable', absolute_error=error,
                  relative_error=error/abs(expected_depth) if expected_depth else None,
                  passed=bool(error <= tolerance))
    if temporal:
        result['depth_passed']=result['passed']
        result['passed']=False if not result['depth_passed'] or measured['temporal_passed'] is False else measured['temporal_passed']
    return result

def am_harmonics(signal, fs, carrier, rate, expected_depth, algorithm=2,upper_blend=None, **kwargs):
    weights=emission_weights(carrier,algorithm,upper_blend)
    forced_overlap=kwargs.pop('overlap',False)
    requested=[k for k in range(2,9) if weights[k-2]>1e-4]
    return [am_metric(signal, fs, carrier, k, rate, expected_depth, weights[k-2],
                      overlap=forced_overlap or any(j!=k and abs(j-k)*carrier<=2*rate for j in requested), **kwargs)
            for k in range(2, 9)]

def aggregate_am(metrics):
    required = [m for m in metrics if m['status'] != 'not_requested']
    if not required:
        return 'not_evaluated'
    if any(m['status'] == 'invalid_measurement' for m in required):
        return 'invalid_measurement'
    if any(m['passed'] is False for m in required):
        return 'fail'
    if any(m['passed'] is None for m in required):
        return 'not_evaluated'
    return 'pass'

def fm_tone(fs, length, carrier, rate, cents, order=1, peak=.15):
    t=np.arange(length)/fs
    frequency=carrier*2**(cents*np.sin(2*np.pi*rate*t)/1200)
    # Trapezoidal integration of the declared instantaneous frequency. The
    # frequency truth remains the expression above, independent of demodulation.
    phase=np.r_[0.,np.cumsum((frequency[:-1]+frequency[1:])*.5)]*(2*np.pi/fs)
    return peak*np.cos(order*phase)

def _fm_demod(v, fs, carrier, order, rate, start, stop, latency,temporal=False):
    t=np.arange(len(v))/fs;lo=int(start*fs);hi=int(stop*fs);taps=_lowpass(fs,rate)
    if lo<len(taps)//2 or hi+len(taps)//2>len(v) or hi<=lo:
        raise ValueError('FM interval needs filter settling margins')
    z=fftconvolve(2*v*np.exp(-2j*np.pi*order*carrier*t),taps,mode='same')
    rms_dbfs=float(20*np.log10(max(float(np.sqrt(np.mean(abs(z[lo:hi])**2)/2)),1e-30)))
    frequency=carrier+np.gradient(np.unwrap(np.angle(z)))*fs/(2*np.pi*order)
    if np.any(frequency[lo:hi]<=0):
        return dict(depth_cents=None,rms_dbfs=rms_dbfs,reason='nonpositive_demodulated_frequency')
    cents=1200*np.log2(frequency[lo:hi]/carrier)
    time=t[lo:hi]-latency
    matrix=np.column_stack((np.ones(hi-lo),np.cos(2*np.pi*rate*time),np.sin(2*np.pi*rate*time)))
    c=np.linalg.lstsq(matrix,cents,rcond=None)[0]
    result=dict(depth_cents=float(np.hypot(c[1],c[2])),mean_pitch_error_cents=float(c[0]),
                phase_rad=float(np.arctan2(c[1],c[2])),
                rms_dbfs=rms_dbfs)
    if temporal:result.update(temporal_metrics(cents,time,rate))
    return result

def fm_metric(signal,fs,carrier,order,rate,expected_cents,expected_weight,
              start=1.25,stop=3.,latency=0.,overlap=False,minimum_rms_dbfs=-100.,temporal=False):
    result=dict(order=order,center_hz=carrier*order,expected_cents=expected_cents,
                status='not_requested',passed=None,rate_measurement='estimated independently' if temporal else 'depth only at declared rate')
    if expected_weight<=1e-4:return result
    if overlap:
        result['status']='overlap_ambiguous';return result
    v=np.asarray(signal,dtype=float)
    if v.ndim==2:v=np.mean(v,axis=1)
    if not np.isfinite(v).all():
        result.update(status='invalid_measurement',passed=False);return result
    control=_fm_demod(fm_tone(fs,len(v),carrier,rate,expected_cents,order),
                       fs,carrier,order,rate,start,stop,0.)
    error=abs(control['depth_cents']-expected_cents) if control['depth_cents'] is not None else float('inf')
    valid=error<=max(.01,abs(expected_cents)*.01)
    result['calibration']=dict(depth_cents=control['depth_cents'],absolute_error_cents=error,passed=bool(valid))
    if not valid:
        result.update(status='invalid_measurement',passed=False);return result
    m=_fm_demod(v,fs,carrier,order,rate,start,stop,latency,temporal);result.update(m)
    if m['rms_dbfs']<minimum_rms_dbfs:
        result.update(status='expected_but_missing',passed=False,depth_cents=None);return result
    if m['depth_cents'] is None:
        result.update(status='overlap_ambiguous',passed=None);return result
    error=abs(m['depth_cents']-expected_cents)
    tolerance=1. if expected_cents<=5 else abs(expected_cents)*.1
    result.update(status='measurable',absolute_error_cents=error,passed=bool(error<=tolerance))
    if temporal:
        result['depth_passed']=result['passed']
        result['passed']=False if not result['depth_passed'] or m['temporal_passed'] is False else m['temporal_passed']
    return result

def fm_harmonics(signal,fs,carrier,rate,expected_cents,algorithm=2,upper_blend=None,**kwargs):
    weights=emission_weights(carrier,algorithm,upper_blend)
    return [fm_metric(signal,fs,carrier,k,rate,expected_cents,weights[k-2],**kwargs) for k in range(2,9)]

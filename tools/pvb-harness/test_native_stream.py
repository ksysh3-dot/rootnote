#!/usr/bin/env python3
"""Shared production OLA/ring lifecycle, independent analytic trajectories."""
import argparse,ctypes as C,hashlib,json,math
from pathlib import Path
import numpy as np
from test_native_renderer import Probe,encode,DP
from vb_quality.measurement import table_at,nmse_db,am_metric,fm_metric,fm_tone

HERE=Path(__file__).resolve().parent
FS=3000;HOP=16

class Stream(Probe):
    def __init__(self,lib):
        super().__init__(lib)
        lib.pvb_renderer_probe_push.argtypes=[C.c_void_p,DP,C.c_int]
        lib.pvb_renderer_probe_read.argtypes=[C.c_void_p,DP,C.c_int]
        lib.pvb_renderer_probe_reset.argtypes=[C.c_void_p]
        lib.pvb_renderer_probe_finish.argtypes=[C.c_void_p]
        lib.pvb_renderer_probe_available.argtypes=[C.c_void_p]
    def reset(self):self.lib.pvb_renderer_probe_reset(self.handle)
    def push(self,fit):
        fit=None if fit is None else np.ascontiguousarray(fit,np.float64)
        return self.lib.pvb_renderer_probe_push(self.handle,None if fit is None else fit.ctypes.data_as(DP),3)
    def read(self,count):
        out=np.empty(count,np.float64)
        n=self.lib.pvb_renderer_probe_read(self.handle,out.ctypes.data_as(DP),count)
        if n!=count:raise ValueError(n)
        return out
    def available(self):return self.lib.pvb_renderer_probe_available(self.handle)
    def finish(self):return self.lib.pvb_renderer_probe_finish(self.handle)

def frame(kind,center):
    t=center/FS;phase=.3+2*np.pi*55*t;f=55.;slope=0.;a=.15;coef=np.zeros(5)
    coef[0]=a
    if kind=='am7':
        for j in range(5):coef[j]=a*(.7*(2*np.pi*7*.064)**j*np.sin(2*np.pi*7*t+j*np.pi/2)/math.factorial(j) if j else 1+.7*np.sin(2*np.pi*7*t))
    if kind=='ramp':coef[:3]=[.1+.02*t+.004*t*t,(.02+.008*t)*.064,.004*.064**2]
    if kind=='chirp':slope=5.;f+=slope*t;phase+=np.pi*slope*t*t
    if kind=='change' and t>=.75:f=65.;phase=.3+2*np.pi*(55*.75+65*(t-.75))
    if kind=='stop' and t>=.75:return None
    z=np.asarray(coef,complex)*np.exp(1j*phase)
    return encode(dict(amplitude=coef[0],frequency_hz=f,phase_rad=float(np.angle(z[0])),amplitude_slope=coef[1]/.064,
                       frequency_slope=slope,carrier_hz=f,carrier_slope=slope,coefficients=z))

def reference(kind,frames):
    result=np.zeros((frames+1)*16)
    for j in range(frames):
        center=(j+1)*16;fit=frame(kind,center)
        if fit is None:continue
        ix=np.arange(center-16,center+16);t=ix/FS;delta=(ix-center)/FS
        if kind=='am7':amp=.15*(1+.7*np.sin(2*np.pi*7*t))
        elif kind=='ramp':amp=.1+.02*t+.004*t*t
        else:amp=np.full(32,.15)
        # Phase is a declared local linear/chirp model. A sudden note change
        # blends the two known grains; no claim of an ideal instantaneous switch.
        phase=fit[2]+2*np.pi*fit[5]*delta+np.pi*fit[6]*delta**2
        weights,gain,offset=table_at(fit[1])
        wave=sum(amp*gain*w*np.cos(k*phase+offset[k-2]) for k,w in enumerate(weights,2) if w>1e-4)
        window=np.maximum(0.,1-abs(ix-center)/16)
        result[ix]+=wave*window
    return result

def render(stream,kind,frames=300,chunks=(16,),modify_at=None):
    stream.reset();out=[]
    for j in range(frames):
        fit=frame(kind,(j+1)*16)
        if modify_at is not None and j>=modify_at and fit is not None:fit=fit.copy();fit[10::2]*=.5;fit[11::2]*=.5;fit[0]*=.5
        assert stream.push(fit)==16
        for count in chunks:out.append(stream.read(count))
    n=stream.finish();out.append(stream.read(n))
    return np.concatenate(out)

def stream_correctness(lib):
    stream=Stream(lib);rows=[]
    try:
        for kind in ('steady','ramp','chirp','am7','change','stop'):
            actual=render(stream,kind);expected=reference(kind,300)
            score=nmse_db(actual,expected);limit=-80 if kind=='am7' else -120
            assert score<=limit,('native_ola_waveform',kind,score)
            other=render(stream,kind,chunks=(1,3,7,5))
            assert np.array_equal(actual,other),('native_ola_chunk',kind)
            if kind=='stop':assert np.max(abs(actual[2400:]))==0,('native_ola_tail',kind)
            rows.append(dict(name=kind,nmse_db=score,limit_db=limit,chunk_bit_exact=True))
        a=render(stream,'am7');b=render(stream,'am7',modify_at=180)
        assert np.array_equal(a[:180*16],b[:180*16]),'native_ola_prefix'
        stream.reset()
        try:stream.read(1)
        except ValueError as exc:assert exc.args==(-2,)
        else:raise AssertionError('unfinalized future exposed')
        fit=frame('steady',16);pushed=0
        while stream.push(fit)==16:pushed+=1
        assert pushed==31 and stream.available()==496,'native_ola_capacity'
        stream.read(496);assert stream.push(fit)==16
        stream.reset();assert stream.available()==0
    finally:stream.close()
    return dict(status='pass',cases=rows,core_rate=FS,control_hop=16,explicit_control_lookahead_samples=16,
                reset=True,capacity_guard=True,future_read_rejected=True,prefix=True,
                scope='production raw grain+shared OLA/ring; no analysis/HPSS/output filters')

def temporal_controls():
    fs=48000;rows=[]
    for rate,seconds in ((.5,12),(2,4),(7,4),(20,4)):
        t=np.arange(int(seconds*fs))/fs;start=1.;stop=seconds-1.
        x=.15*(1+.7*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*165*t)
        m=am_metric(x,fs,55,3,rate,.7,1,start=start,stop=stop,temporal=True)
        assert m['passed'],('am_temporal_control',rate,m)
        rows.append(dict(kind='am',rate_hz=rate,measured_hz=m['rate_hz'],phase_error=m['phase_error_rad']))
    n=int(4*fs);t=np.arange(n)/fs
    x=fm_tone(fs,n,55,7,35,3)
    m=fm_metric(x,fs,55,3,7,35,1,start=1,stop=3,temporal=True)
    assert m['passed'],('fm_temporal_control',m)
    rows.append(dict(kind='fm',rate_hz=7,measured_hz=m['rate_hz'],phase_error=m['phase_error_rad']))
    am_reverse=.15*(1-.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*165*t)
    a=am_metric(am_reverse,fs,55,3,7,.7,1,start=1,stop=3,temporal=True)
    f=fm_metric(fm_tone(fs,n,55,7,-35,3),fs,55,3,7,35,1,start=1,stop=3,temporal=True)
    wrong=.15*(1+.7*np.sin(2*np.pi*8*t))*np.cos(2*np.pi*165*t)
    w=am_metric(wrong,fs,55,3,7,.7,1,start=1,stop=3,temporal=True)
    assert a['depth_passed'] and not a['passed'] and abs(a['phase_error_rad'])>3
    assert f['depth_passed'] and not f['passed'] and abs(f['phase_error_rad'])>3
    assert not w['passed'] and abs(w['rate_hz']-8)<.05
    # A wrong family treats the source's AM sidebands as separate fundamentals:
    # its3rd-harmonic modulation occurs at21Hz instead of7Hz.
    bad=.15*(1+.7*np.sin(2*np.pi*21*t))*np.cos(2*np.pi*165*t)
    d=am_metric(bad,fs,55,3,7,.7,1,start=1,stop=3,temporal=True)
    assert not d['passed']
    return dict(status='pass',controls=rows,reversed_am_rejected=True,reversed_fm_rejected=True,
                wrong_rate_rejected=True,duplicated_sideband_rule_rejected=True,
                phase_limit_rad=float(np.pi/6),rate_relative_limit=.05)

def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',default=str(HERE/'build/libpvbcapi.so'));p.add_argument('--report',default='native-stream-q0.json')
    args=p.parse_args();lib=C.CDLL(args.lib)
    result=dict(schema='pvb.q0.native_stream.v1',stream=stream_correctness(lib),temporal=temporal_controls(),
                library_sha256=hashlib.sha256(Path(args.lib).read_bytes()).hexdigest())
    Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print('PASS: shared native OLA, temporal and lifecycle controls')

if __name__=='__main__':main()

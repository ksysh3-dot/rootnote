#!/usr/bin/env python3
"""Q0: inject explicit trajectories into the real renderTrack52 implementation.

Checks the raw32-sample3kHz grain, not full-engine OLA/filter/device quality.
The oracle evaluates declared complex polynomials independently in float64.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
from vb_quality.measurement import table_at, nmse_db, am_metric, aggregate_am, fm_metric, fm_tone

HERE = Path(__file__).resolve().parent
DP = C.POINTER(C.c_double)
TIME = (np.arange(32)-16)/3000.

def configure(lib):
    lib.pvb_renderer_probe_create.restype = C.c_void_p
    lib.pvb_renderer_probe_destroy.argtypes = [C.c_void_p]
    lib.pvb_renderer_probe_grain.argtypes = [C.c_void_p, DP, C.c_int, DP, C.c_int]
    return lib

class Probe:
    def __init__(self, lib):
        self.lib = configure(lib)
        self.handle = lib.pvb_renderer_probe_create()
        if not self.handle:
            raise RuntimeError('Native probe configure failed')
    def close(self):
        if self.handle:
            self.lib.pvb_renderer_probe_destroy(self.handle)
            self.handle = None
    def grain(self, fit, mode=3):
        fit = np.ascontiguousarray(fit, np.float64)
        if fit.shape != (20,):
            raise ValueError('Explicit20-double trajectory required')
        out = np.empty(32, np.float64)
        n = self.lib.pvb_renderer_probe_grain(self.handle, fit.ctypes.data_as(DP), mode,
                                            out.ctypes.data_as(DP), len(out))
        if n != 32:
            raise ValueError('Native trajectory rejected')
        return out

def encode(model):
    """Pack explicit model fields; no estimation or quality acceptance here."""
    a = np.zeros(20)
    a[:7] = [model[k] for k in ('amplitude', 'frequency_hz', 'phase_rad', 'amplitude_slope',
                               'frequency_slope', 'carrier_hz', 'carrier_slope')]
    a[9] = 1
    a[10::2] = np.real(model['coefficients']); a[11::2] = np.imag(model['coefficients'])
    return a

def oracle(fit):
    # Independent array powers, not M.evaluate or modulation::local.
    coeff = fit[10::2]+1j*fit[11::2]
    z = np.sum(coeff[:, None]*(TIME[None, :]/.064)**np.arange(5)[:, None], axis=0)
    amplitude = np.abs(z)
    phase = 2*np.pi*fit[5]*TIME + np.pi*fit[6]*TIME**2 + np.angle(z)
    weights, gain, offsets = table_at(fit[1])
    return np.sum([amplitude*gain*w*np.cos(k*phase+offsets[k-2])
                   for k, w in enumerate(weights, 2) if w > 1e-4], axis=0)

def golden_cases():
    for f in (40., 55., 80., 120.):
        for label, poly, slope in (
            ('steady', [1, 0, 0, 0, 0], 0),
            ('rise', [1, .4, 0, 0, 0], 0),
            ('curved_am', [1, -.8, .7, 0, 0], 0),
            ('glide', [1, 0, 0, 0, 0], 120),
            ('complex', [1, .2+.6j, .1-.3j, 0, 0], 0),
            ('joint', [1, -.3+.2j, .1+.1j, -.2j, .07], -80)):
            z = .15*np.exp(.3j)*np.array(poly, complex)
            ratio = z[1]/(.064*z[0])
            curve = 2*z[2]/(.064**2*z[0])-ratio**2
            m = dict(amplitude=abs(z[0]), phase_rad=.3, frequency_hz=f+ratio.imag/(2*np.pi),
                     amplitude_slope=abs(z[0])*ratio.real,
                     frequency_slope=slope+curve.imag/(2*np.pi),
                     carrier_hz=f, carrier_slope=slope, coefficients=z)
            yield f'{label}@{f:g}', encode(m)

def renderer_correctness(lib):
    probe = Probe(lib); rows = []
    try:
        for name, fit in golden_cases():
            expected = oracle(fit); actual = probe.grain(fit)
            score = nmse_db(actual, expected)
            passed = bool(np.isfinite(actual).all() and score <= -120)
            rows.append(dict(name=name, nmse_db=score, passed=passed))
            assert passed, ('native_renderer_waveform', name, score)
        bad = next(golden_cases())[1].copy(); bad[10] = np.nan
        try:
            probe.grain(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('nonfinite trajectory accepted')
    finally:
        probe.close()
    return dict(status='pass', cases=rows, scope='production raw grain, explicit open grid/fade/life; no engine OLA/filters')

def measurement_controls():
    fs=48000;t=np.arange(int(3.4*fs))/fs;rows=[]
    for rate in (.5, 1, 2, 4, 7, 10, 15, 20):
        x=.15*(1+.7*np.sin(2*np.pi*rate*t))*np.cos(2*np.pi*165*t)
        m=am_metric(x,fs,55,3,rate,.7,1)
        assert m['status']=='measurable' and m['passed'], (rate,m)
        assert abs(m['depth']-.7)/.7 < .01
        rows.append(dict(rate_hz=rate,depth=m['depth'],status='pass'))
    x=.15*(1+.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*165*t)
    missing=am_metric(np.zeros_like(x),fs,55,3,7,.7,1)
    assert missing['status']=='expected_but_missing' and aggregate_am([missing])=='fail'
    absent=am_metric(x,fs,55,2,7,.7,0)
    assert absent['status']=='not_requested' and absent['passed'] is None
    overlap=am_metric(x,fs,55,3,7,.7,1,overlap=True)
    assert overlap['status']=='overlap_ambiguous' and aggregate_am([overlap])=='not_evaluated'
    frozen=am_metric(.15*np.cos(2*np.pi*165*t),fs,55,3,7,.7,1)
    assert frozen['status']=='measurable' and frozen['passed'] is False
    below=am_metric(x,fs,55,3,7,.7,1,reference_peak=1e-12)
    assert below['status']=='below_evaluation_floor' and below['passed'] is None
    fm_rows=[]
    for rate,cents in ((2,35),(4,35),(7,35),(10,35),(7,5),(7,70)):
        m=fm_metric(fm_tone(fs,len(t),55,rate,cents,3),fs,55,3,rate,cents,1)
        assert m['status']=='measurable' and m['passed'],(rate,cents,m)
        assert m['calibration']['passed'],m
        fm_rows.append(dict(rate_hz=rate,cents=cents,measured_cents=m['depth_cents'],status='pass'))
    frozen_fm=fm_metric(.15*np.cos(2*np.pi*165*t),fs,55,3,7,35,1)
    assert frozen_fm['status']=='measurable' and frozen_fm['passed'] is False
    return dict(status='pass',ideal_am=rows,missing_output_rejected=True,
                nonrequested_excluded=True,ambiguous_not_passed=True,below_floor_not_passed=True,
                frozen_am_rejected=True,ideal_fm=fm_rows,frozen_fm_rejected=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lib',default=str(HERE/'build/libpvbcapi.so'))
    p.add_argument('--report',default='native-renderer-q0.json')
    a=p.parse_args();lib=configure(C.CDLL(a.lib))
    result=dict(schema='pvb.q0.native_renderer.v1',correctness=renderer_correctness(lib),
                measurement=measurement_controls(),quality='not_evaluated',device='not_evaluated',listening='not_evaluated',
                library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest())
    result['test_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(a.report).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:24 production-grain oracle cases; calibrated AM and eligibility controls')

if __name__=='__main__':
    main()

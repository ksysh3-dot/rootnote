#!/usr/bin/env python3
"""COMBO integration contracts. Signals stay in memory; requires a host C API build."""
import argparse
import ctypes
import numpy as np
from test_engine import Engine, FP, P, load_lib, true_peak_db

parser = argparse.ArgumentParser()
parser.add_argument('--lib', required=True)
parser.add_argument('--dry-unfiltered', action='store_true')
args = parser.parse_args()
lib = load_lib(args.lib)
P.update(P1PPP=57, XTC_MODE=47, DEV_ON=33)
lib.pvb_set_layer_cap.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.pvb_set_fixed_eq_open.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.pvb_p1ppp_state.argtypes = [ctypes.c_void_p]
lib.pvb_p1ppp_state.restype = ctypes.c_int
sr = 48000
t = np.arange(3 * sr) / sr
x = np.column_stack([.1 * (np.sin(2*np.pi*55*t) + .5*np.sin(2*np.pi*82*t)),
                     .08 * (np.sin(2*np.pi*63*t) + .4*np.sin(2*np.pi*1100*t))]).astype(np.float32)
base = dict(vb_on=1, vb_algo=6, vb_level_db=0, out_db=-5, ramp_ms=0)

def render(**overrides):
    settings = dict(base, **overrides)
    e = Engine(lib, sr, **settings)
    e.process(np.zeros((49152, 2), np.float32), block=1024)
    y = e.process(x, block=1024)
    assert e.latency() == 7140
    e.close()
    return y

reference = render()
assert np.array_equal(reference, render(p1ppp=1))
assert np.array_equal(reference, render(p1ppp=2))
assert np.array_equal(reference, render(xtc_mode=5, dyn_on=1, dev_on=1, hs_db=9))
print('PASS: retired preset packets and stored spatial/developer options cannot change COMBO')

e = Engine(lib, sr, **base)
assert lib.pvb_p1ppp_state(e.h) == 0
lib.pvb_set_layer_cap(e.h, -40)
e.process(np.zeros((49152, 2), np.float32), block=1024)
guarded = e.process(x, block=1024)
e.close()
assert np.max(np.abs(guarded-reference)) > 1e-5
print('PASS: retired preset stays inactive, speaker guard affects the active branch')

locked = render(low_db=-8)
assert np.array_equal(locked, reference)
e = Engine(lib, sr, **base)
lib.pvb_set_fixed_eq_open(e.h, 1)
e.set(low_db=-8)
e.process(np.zeros((49152, 2), np.float32), block=1024)
opened = e.process(x, block=1024)
e.close()
assert np.max(np.abs(opened-reference)) > 1e-5
print('PASS: EQ is frozen until the existing unlock control is enabled')

assert np.array_equal(render(vb_level_db=12, out_db=12, ceil_db=0),
                      render(vb_level_db=0, out_db=-3, ceil_db=-1))
e = Engine(lib, sr, **dict(base, out_db=12, ceil_db=0))
stress = e.process(x*12, block=1024)
e.close()
assert np.isfinite(stress).all() and true_peak_db(stress[sr:]) < -.8
assert np.max(np.abs(render(gate_db=-120))) == 0
print('PASS: output/layer/ceiling caps, finite stress output, true-peak ceiling and final mute')

dry = render(vb_level_db=-120)
expected = (x[:-7140].astype(np.float64) * 10**(-5/20)).astype(np.float32)
delta = float(np.max(np.abs(dry[7140:]-expected)))
if args.dry_unfiltered:
    assert np.array_equal(dry[7140:], expected), delta
else:
    assert delta > .001
print(f'PASS: dry topology V{int(args.dry_unfiltered)} max difference from delay+gain={delta:.9g}')

rate = 44100
t = np.arange(rate)/rate
signal = np.column_stack((.2*np.sin(2*np.pi*55*t), .1*np.cos(2*np.pi*82*t))).astype(np.float32)
outputs = []
for size in (64, 147, 256, 441, 480, 1024):
    e = Engine(lib, rate, **base)
    outputs.append(e.process(signal, block=size))
    assert e.latency() == 6646 and e.meters()[14] == 7
    e.close()
assert all(np.array_equal(outputs[0], y) for y in outputs)
e = Engine(lib, 46000, **base)
e.process(signal)
assert e.meters()[14] == 0 and e.latency() == 85
e.close()
print('PASS: 44.1 kHz block sizes, delay, and unsupported rate fallback')

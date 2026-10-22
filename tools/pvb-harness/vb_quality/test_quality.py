#!/usr/bin/env python3
"""Independent production-baseline and research alignment/causality checks.

Build the host library first. These tests verify the experiment, not sound quality.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

from quality import BASE_LATENCY, CANDIDATES, FS, HERE, P, V, layer, mix

sys.path.insert(0, str(HERE.parent))
import test_engine as T


def run():
    lib = T.load_lib(str(HERE.parent/'build/libpvbcapi.so'))
    t = np.arange(3*FS)/FS
    x = sum(.13/k*np.sin(2*np.pi*55*k*t+.4*k) for k in range(1, 9))*(t > .2)*(t < 2.6)
    x += .08*np.sin(2*np.pi*65.41*t+.7)*(t > 1)*(t < 1.8)
    before = (P.LAT_HPV, V.PLACEMENT)
    y, info = layer(x)
    cpp, _, latency, _ = T.vb_layer(lib, 2, FS, x, x)
    error = T.rel_db(y, cpp)
    T.check('research baseline equals build-14 C++', error < -120 and latency == BASE_LATENCY, rel_db=error)
    T.check('reference globals restored', before == (P.LAT_HPV, V.PLACEMENT))
    T.check('layer separated into two paths', np.max(abs(y-info['pv']-info['perc'])) < 1e-12)
    no_pm, no_pm_info = layer(x, 'no_phase_match')
    phase_control_difference = float(np.sqrt(np.mean((no_pm[FS:2*FS]-y[FS:2*FS])**2)))
    T.check('phase-off control actually disables matching while preserving grid mask',
            no_pm_info['stats']['pm_tried'] == 0 and phase_control_difference > 1e-4,
            difference_rms=phase_control_difference)

    stereo = T.stereo(x).astype(np.float64)
    h, _ = layer(stereo.mean(1))
    for level in (0, 9):
        e = T.Engine(lib, FS, vb_on=1, vb_algo=2, vb_level_db=level, ramp_ms=0, **T.V11)
        lib.pvb_reset(e.h)
        actual = e.process(stereo, blocks=[1, 17, 256, 1023])
        lat = e.latency()-BASE_LATENCY
        e.close()
        want = mix(stereo, h, 'baseline', level)['post_limiter']
        error = T.rel_db(actual[lat+FS:], want[FS:-lat])
        T.check(f'stage renderer equals full C++ engine at +{level}', error < -95, rel_db=error)

    # Same past, different future. No generator may change any already emitted sample.
    cut = int(1.55*FS)
    altered = x.copy()
    rng = np.random.default_rng(31)
    altered[cut:] = .15*rng.normal(size=len(x)-cut)
    for name in ('baseline', 'smooth128', 'smooth256', 'smooth512', 'existing512', 'multi512',
                 'continuous128', 'continuous_smooth128', 'follow128', 'gentle128'):
        a, parts = layer(x, name)
        b, _ = layer(altered, name)
        error = float(np.max(abs(a[:cut]-b[:cut])))
        T.check(f'causal emitted prefix: {name}', error < 2e-10, max_abs=error)
        T.check(f'finite and additive stages: {name}', np.isfinite(a).all() and
                float(np.max(abs(a-parts['pv']-parts['perc']))) < 1e-12)
    # A correctly aligned phase match on a stationary tone should survive N changes.
    tt = np.arange(4*FS)/FS
    harmonic_input = sum(.08/k*np.sin(2*np.pi*55*k*tt+.4*k) for k in range(1, 9))
    phases = {}
    for name in ('baseline', 'long256', 'long512', 'continuous128', 'continuous_smooth128', 'follow128'):
        c = CANDIDATES[name]
        generated, _ = layer(harmonic_input, c)
        a, b = FS+c.latency, 3*FS+c.latency
        segment = generated[a:b]
        phasor = np.exp(-2j*np.pi*165*np.arange(FS, 3*FS)/FS)
        phases[name] = float(np.angle(np.mean(segment*phasor)))
    delta = max(abs(float(np.angle(np.exp(1j*(v-phases['baseline']))))) for v in phases.values())
    T.check('window changes preserve nominal mix-point phase at 165 Hz', delta < .06,
            max_difference_rad=delta, phases=phases)
    ordinary, normal_parts = layer(harmonic_input, 'baseline')
    gentle, gentle_parts = layer(harmonic_input, 'gentle128')
    differences = {}
    lat = CANDIDATES['gentle128'].latency
    for f in (165, 220, 275, 330):
        phasor = np.exp(-2j*np.pi*f*np.arange(FS, 3*FS)/FS)
        sl = slice(FS+lat, 3*FS+lat)
        ratio = abs(np.mean(gentle[sl]*phasor))/abs(np.mean(ordinary[sl]*phasor))
        actual = 20*np.log10(ratio)
        expected = -12*max(np.log2(f/220), 0)
        differences[f] = float(actual-expected)
    T.check('upper-partial attenuation retains lower partial levels without redistribution',
            max(abs(v) for v in differences.values()) < .03, error_db=differences)
    T.check('upper-partial attenuation leaves percussion unchanged',
            np.array_equal(normal_parts['perc'], gentle_parts['perc']))
    for name in ('baseline', 'smooth512'):
        z, _ = layer(np.zeros(100), name)
        T.check(f'short silent input: {name}', len(z) == 100 and np.max(abs(z)) == 0)
    return T.RESULTS


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--report', required=True)
    args = p.parse_args()
    rows = run()
    Path(args.report).write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    raise SystemExit(any(not r['ok'] for r in rows))

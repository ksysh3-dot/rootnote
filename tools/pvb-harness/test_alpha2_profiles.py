#!/usr/bin/env python3
"""Exercise saved app IDs through Engine; compare actual output to the existing research path.

This is a routing/regression test, not a listening-quality verdict. The two
paths share the DSP algorithm, but independent app-ID dispatch must reach it.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
import test_engine as T
import test_modulation_research as P
from vb_quality.stage_capture import INDEX, StageCapture

PROFILES = ((6, 3, 0), (7, 3, 48), (8, 3, 240), (9, 0, 2048), (10, 0, 6144))


def source(fs, seconds=2.4):
    t = np.arange(round(fs * seconds)) / fs
    # AM expert, changing pitch, overlap and ending all reach the real audio path.
    carrier = 80 * t + 6 * np.maximum(t - 1.1, 0) ** 2
    x = .10 * (1 + .7 * np.sin(2 * np.pi * 20 * t)) * np.cos(2 * np.pi * carrier)
    x[t > seconds - .35] = 0
    return T.stereo(x.astype(np.float32))


def dispatch(lib):
    rows = []
    for fs in (44100, 48000):
        x = source(fs)
        for algorithm, mode, flags in PROFILES:
            app = P.render(lib, x, mode, fs=fs, algo=algorithm, level=9, stage_flags=0)
            oracle = P.render(lib, x, mode, True, fs=fs, algo=4, level=9, stage_flags=flags)
            for key in ('output', 'stem'):
                assert np.array_equal(app[key], oracle[key]), (fs, algorithm, key)
            stages = app['stages']
            assert len(stages) > 3000, (fs, algorithm, 'capture missing')
            assert np.all(stages[:, INDEX['flags']] == flags), (fs, algorithm, 'wrong profile')
            assert np.all(stages[:, INDEX['modulation_mode']] == mode)
            assert app['latency'] == (7140 if fs == 48000 else 6561)
            assert app['meters'][T.M['VB']] == algorithm + 1
            peak = float(np.max(np.abs(app['output'])))
            assert 1e-5 < peak < 1 and np.max(np.abs(app['stem'])) > 1e-5
            # Native ABI and chunking must still work with each app profile.
            chunk = P.render(lib, x, mode, fs=fs, algo=algorithm, level=9, block=1379, stage_flags=0)
            # Existing post-mix filter tails can differ below1e-24 with block
            # splits; legacy algo4 reproduces it too. Model stages and generated
            # stems must remain bit exact; do not change legacy DSP for a zero tail.
            chunk_error = float(np.max(abs(app['output'] - chunk['output'])))
            assert chunk_error < 1e-20, (fs, algorithm, 'chunk', chunk_error)
            assert np.array_equal(app['stem'], chunk['stem'])
            assert np.array_equal(app['stages'], chunk['stages'])
            changed = x.copy(); changed[int(.9 * fs):] *= -1
            future = P.render(lib, changed, mode, fs=fs, algo=algorithm, level=9)
            assert np.array_equal(app['output'][:int(.9 * fs)], future['output'][:int(.9 * fs)])
            rows.append(dict(fs=fs, algorithm=algorithm, mode=mode, flags=flags,
                app_research_output_bit_exact=True, stem_bit_exact=True, chunk_max_abs_error=chunk_error,
                chunk_stage_and_stem_bit_exact=True,
                prefix_invariant=True, latency=app['latency'], peak=peak,
                detail_fraction=float(stages[:, INDEX['detail_applied']].mean()),
                family_fraction=float(stages[:, INDEX['family_applied']].mean())))
    assert any(r['algorithm'] == 7 and r['detail_fraction'] > .05 for r in rows), rows
    assert any(r['algorithm'] == 8 and r['family_fraction'] > .05 for r in rows), rows
    return rows


def switch_and_reset(lib):
    results = []
    for fs in (44100, 48000):
        e = T.Engine(lib, fs, vb_on=1, vb_algo=9, vb_level_db=9, out_db=-18, ramp_ms=0)
        capture = StageCapture(lib, e.h, 0, 50000)
        try:
            for algorithm, mode, flags in (PROFILES[3], PROFILES[1], PROFILES[4], PROFILES[2], PROFILES[0]):
                e.set(vb_algo=algorithm)
                y = e.process(source(fs, 1.5))
                assert np.isfinite(y).all() and np.max(np.abs(y)) < 1
                assert e.meters()[T.M['VB']] == algorithm + 1
                captured = capture.copy()
                assert len(captured) and np.all(captured[-200:, INDEX['flags']] == flags)
                lib.pvb_reset(e.h)
                tail = e.process(np.zeros((int(fs * .6), 2), np.float32))
                assert np.max(np.abs(tail)) < 1e-7, (fs, algorithm, 'stale audio after reset')
            # Unsupported-rate fallback cannot report a model as audible.
            lib.pvb_set_sample_rate(e.h, 96000)
            e.process(np.zeros((12000, 2), np.float32))
            assert e.meters()[T.M['VB']] == 0
            results.append(dict(fs=fs, shared_module_switches=5, reset_tail=True, unsupported_rate=True))
        finally:
            capture.close(); e.close()
    return results


def legacy_regression(lib, baseline):
    old = T.load_lib(baseline); rows = []
    for fs in (44100, 48000):
        x = source(fs, 1.2)
        for algorithm in range(6):
            a = T.Engine(lib, fs, vb_on=1, vb_algo=algorithm, vb_level_db=9, out_db=-18, ramp_ms=0)
            b = T.Engine(old, fs, vb_on=1, vb_algo=algorithm, vb_level_db=9, out_db=-18, ramp_ms=0)
            try:
                assert np.array_equal(a.process(x), b.process(x)), (fs, algorithm, 'legacy regression')
                rows.append(dict(fs=fs, algorithm=algorithm, bit_exact=True))
            finally: a.close(); b.close()
    return rows


def main():
    p = argparse.ArgumentParser(); p.add_argument('--lib', required=True); p.add_argument('--baseline')
    p.add_argument('--report', required=True); a = p.parse_args(); lib = P.api(a.lib)
    report = dict(schema='pvb.alpha2.profiles.v1', library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest(),
        dispatch=dispatch(lib), switching=switch_and_reset(lib),
        legacy=legacy_regression(lib, a.baseline) if a.baseline else 'not_run_here',
        listening='not_evaluated', device='not_evaluated')
    Path(a.report).write_text(json.dumps(report, indent=2) + '\n')
    print('Alpha2: five app profiles x two rates, actual DSP equivalence, chunk/prefix, switches/reset passed')


if __name__ == '__main__': main()

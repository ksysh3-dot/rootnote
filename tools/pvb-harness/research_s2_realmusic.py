#!/usr/bin/env python3
"""Study 2 side check on real music: what candidate C1 changes, and listening pairs. Not a quality score.

Excerpts follow the P1+ real-music rule (docs/P1PLUS_OBJECTIVE_PROTOCOL.md): per WAV/FLAC three 8 s excerpts at
15 %, 50 % and 85 % of the available start interval, 4 s pre-roll, 0.22 s tail, resampled to 48 kHz stereo. Each model
is rendered unmodified and with C1. Reported per excerpt (evaluated 8 s only):
  layer_change_db       generated-layer total energy ratio change (C1 / unmodified)
  difference_db         energy of the generated-layer difference relative to the unmodified layer
  gain_below_one        fraction of core samples whose applied envelope gain is below 1 (unmodified, C1)
  max_abs_difference    largest output sample difference
The excerpts with the largest difference are written as WAV pairs (full output, unmodified vs C1) for listening.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as P
import research_s1_interaction as S
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS = 48000
MODELS = (('p1', 0, 0), ('p1plus', 6, 0), ('p1pp_v03', 6, 8))
C1 = 8192
GAIN = COLUMNS.index('applied_gain')


def excerpts(path):
    x, fs = sf.read(str(path), always_2d=True, dtype='float64')
    if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if fs != FS:
        g = np.gcd(int(fs), FS); x = resample_poly(x, FS // g, int(fs) // g, axis=0)
    dur = len(x) / FS
    if dur < 8.25 + 4: return
    for frac in (.15, .50, .85):
        start = 4 + frac * (dur - 8.25 - 4)
        a, b = int(round((start - 4) * FS)), int(round((start + 8.22) * FS))
        yield frac, start, np.ascontiguousarray(x[a:b], np.float32)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--wav-dir', type=Path, required=True)
    p.add_argument('--pairs', type=int, default=4)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []; keep = {}
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    for f in files:
        for frac, start, x in excerpts(f):
            ev = slice(4 * FS, 12 * FS)
            for model, flags, mode in MODELS:
                r0 = P.render(lib, x, FS, flags, impact_mode=mode)
                r1 = P.render(lib, x, FS, flags, impact_mode=mode, stage_flags=C1)
                d = r0['latency']
                y0 = r0['stem'][d:d + len(x)].astype(float)[ev]; y1 = r1['stem'][d:d + len(x)].astype(float)[ev]
                o0 = r0['output'][d:d + len(x)].astype(float); o1 = r1['output'][d:d + len(x)].astype(float)
                g0 = r0['stages'][:, GAIN]; g1 = r1['stages'][:, GAIN]; k = slice(len(g0) // 3, None)
                row = dict(file=f.name, fraction=frac, start_s=round(start, 3), model=model,
                           layer_change_db=S.db(S.energy(y1), S.energy(y0)),
                           difference_db=S.db(S.energy(y1 - y0), S.energy(y0)),
                           gain_below_one=[float(np.mean(g0[k] < 1 - 1e-9)), float(np.mean(g1[k] < 1 - 1e-9))],
                           max_abs_difference=float(np.max(np.abs(o1 - o0))))
                rows.append(row)
                print(f.name, frac, model, f"layer {row['layer_change_db']:+.2f} dB diff {row['difference_db']:+.1f} dB",
                      f"gain<1 {row['gain_below_one'][0]:.3f}->{row['gain_below_one'][1]:.3f}", flush=True)
                if model == 'p1plus':
                    keep[(f.name, frac)] = (row['difference_db'], o0, o1)
    a.wav_dir.mkdir(parents=True, exist_ok=True); written = []
    for (name, frac), (dd, o0, o1) in sorted(keep.items(), key=lambda kv: -kv[1][0])[:a.pairs]:
        stem = f"{Path(name).stem[:40]}_{int(frac * 100)}pct".replace(' ', '_')
        for tag, o in (('A_P1plus', o0), ('B_P1plus_C1', o1)):
            out = a.wav_dir / f'{stem}_{tag}.wav'; sf.write(str(out), o, FS, subtype='FLOAT'); written.append(out.name)
    summary = {}
    for model, _, _ in MODELS:
        sub = [r for r in rows if r['model'] == model]
        if sub:
            summary[model] = dict(excerpts=len(sub),
                                  layer_change_db_median=float(np.median([r['layer_change_db'] for r in sub])),
                                  layer_change_db_range=[float(min(r['layer_change_db'] for r in sub)),
                                                         float(max(r['layer_change_db'] for r in sub))],
                                  difference_db_median=float(np.median([r['difference_db'] for r in sub])),
                                  gain_below_one_median=[float(np.median([r['gain_below_one'][i] for r in sub])) for i in (0, 1)])
            print('SUMMARY', model, json.dumps(summary[model]), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study2.realmusic.v1', candidate='C1 (stage flag 8192)',
                                        note='side-effect description, not a quality or listening score',
                                        files=[f.name for f in files], summary=summary, wav_pairs=written, rows=rows),
                                   indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

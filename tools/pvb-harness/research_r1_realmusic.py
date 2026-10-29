#!/usr/bin/env python3
"""Resultant R1 (#4 follow-up) on real music: the same-peak gain of the crest-optimal unreferenced harmonic phases
(stage 1048576). Local files only; nothing here is committed or a listening score.

Excerpts follow the P1+ real-music rule (research_s2_realmusic.excerpts: per WAV/FLAC three 8 s excerpts at 15, 50
and 85 % of the available start interval, 4 s pre-roll). Per excerpt and model pair (P1 / P1 + R1, P1 + C1 /
P1 + C1 + R1), on the evaluated 8 s (shifted by the declared latency):
  layer_gain_db   generated layer (stem): RMS change minus true-peak change (both channels, 48 kHz), the layer's level
                  gain at the same layer peak
  output_gain_db  full output, true peak at 4x oversampling: RMS change minus true-peak change. The harness output is
                  -18 dB, so the limiter does not act and this is how much the whole output could rise before the
                  same limiter ceiling is reached
  layer_rms_change_db, output_peak_change_db, layer_share_db (layer RMS relative to the output RMS, P1)
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
import research_p1plus as P
import research_s2_realmusic as RM
from p1plus_paths import default_library

FS = 48000
R1 = 1048576
PAIRS = (('p1', (0, 0), (0, R1)), ('p1_c1', (0, 8192), (0, 8192 | R1)))


def db_ratio(a, b, power=False):
    return float((10 if power else 20) * np.log10(a / b)) if a > 0 and b > 0 else None


def window(r):
    lat = r['latency']; a, b = 4 * FS + lat, 12 * FS + lat
    return r['stem'][a:b].astype(float), r['output'][a:b].astype(float)


def true_peak(y):
    return float(np.max(np.abs(resample_poly(y, 4, 1, axis=0))))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    for j, path in enumerate(files):
        for frac, start, x in RM.excerpts(path):
            for model, base, cand in PAIRS:
                rb, rc = (P.render(lib, x, FS, fl, stage_flags=st) for fl, st in (base, cand))
                (sb, ob), (sc, oc) = window(rb), window(rc)
                lrms = db_ratio(np.mean(sc ** 2), np.mean(sb ** 2), True); lpk = db_ratio(np.max(np.abs(sc)), np.max(np.abs(sb)))
                orms = db_ratio(np.mean(oc ** 2), np.mean(ob ** 2), True); opk = db_ratio(true_peak(oc), true_peak(ob))
                row = dict(file_index=j, fraction=frac, model=model,
                           layer_gain_db=None if None in (lrms, lpk) else lrms - lpk, layer_rms_change_db=lrms,
                           layer_peak_change_db=lpk, output_gain_db=None if None in (orms, opk) else orms - opk,
                           output_peak_change_db=opk, output_rms_change_db=orms,
                           layer_share_db=db_ratio(np.mean(sb ** 2), np.mean(ob ** 2), True))
                rows.append(row)
                f = lambda v: 'n/a' if v is None else f'{v:+.2f}'
                print('ROW', f'file{j}', f'{frac:.2f}', model, 'layer', f(row['layer_gain_db']),
                      f"(rms {f(lrms)} peak {f(lpk)})", 'output', f(row['output_gain_db']), f"(peak {f(opk)})",
                      'share', f(row['layer_share_db']), flush=True)
    summary = {}
    for model, _, _ in PAIRS:
        for key in ('layer_gain_db', 'output_gain_db', 'layer_rms_change_db', 'output_peak_change_db', 'layer_share_db'):
            v = np.array([q[key] for q in rows if q['model'] == model and q[key] is not None])
            if len(v): summary[f'{model}/{key}'] = dict(median=float(np.median(v)), mean=float(v.mean()), min=float(v.min()),
                                                       max=float(v.max()), negative=int((v < 0).sum()), n=len(v))
    for k, v in summary.items(): print('SUMMARY', k, json.dumps(v), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r1_realmusic.v1', issue=4, files=len(files),
                                        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

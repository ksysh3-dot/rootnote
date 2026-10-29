#!/usr/bin/env python3
"""Study 3 (#4 follow-up) real-music side check: what the tiered candidate C3 + C5' (stage 32768 | 131072) changes on
real music. Local files only; nothing here is committed or a listening score.

Excerpts as research_s2_realmusic.excerpts (three 8 s per file, 4 s pre-roll). Per excerpt and model pair (P1 / P1 +
candidate, P1 + C1 / P1 + C1 + candidate), on the evaluated 8 s of the generated layer (shifted by the latency):
  layer_change_db   layer energy change;  difference_db  energy of the layer difference relative to the base layer
  validity          share of the layer's periodogram (0.5 s Hann frames, hop 0.25 s, 3 kHz) within 2.5 Hz of k p
                    (k = 2..8) for the input's low partials p (30-190 Hz, within 20 dB of the frame's strongest), for
                    base and candidate (research_r2_realmusic_validity's measure)
  onset_change_db   median over the input's low-band onsets (20 ms energy rises of 6 dB or more, 150 ms apart) of
                    the layer energy change in the 150 ms after each onset (the short-note target of study 3)
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly, sosfiltfilt
import research_p1plus as P
import research_r2_close_intervals as C
import research_s2_realmusic as RM
from p1plus_paths import default_library

FS, CORE = 48000, 3000
CAND = 32768 | 131072
PAIRS = (('p1', 0, CAND), ('p1_c1', 8192, 8192 | CAND))
W5 = np.hanning(C.N); FR = np.fft.rfftfreq(C.NFFT, 1 / CORE); SPAN = (FR >= 30) & (FR <= 1450)


def db(a, b):
    return float(10 * np.log10(a / b)) if a > 0 and b > 0 else None


def validity(zin, zst):
    num = den = 0.
    for s in range(0, min(len(zin), len(zst)) - C.N, C.HOP):
        mi = np.abs(np.fft.rfft(zin[s:s + C.N] * W5, C.NFFT)); ms = np.abs(np.fft.rfft(zst[s:s + C.N] * W5, C.NFFT)) ** 2
        parts = [FR[i] for i in C.peaks(mi, FR, rel_db=20)] if mi.max() > 0 else []
        if not parts: continue
        near = np.zeros(len(FR), bool)
        for q in parts:
            for k in range(2, 9):
                if k * q < 1450: near |= np.abs(FR - k * q) <= 2.5
        num += ms[near & SPAN].sum(); den += ms[SPAN].sum()
    return num / den if den > 0 else None


def onsets(zin):
    n = CORE // 50; e = np.array([np.sum(zin[j:j + n] ** 2) for j in range(0, len(zin) - n, n)]) + 1e-12
    out, last = [], -10 ** 9
    for j in range(1, len(e)):
        if 10 * np.log10(e[j] / e[j - 1]) >= 6 and e[j] >= e.max() * 1e-3 and j * n - last >= .15 * CORE:
            out.append(j * n); last = j * n
    return out


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
            zin = sosfiltfilt(C.SOS, resample_poly(np.asarray(x, float).mean(axis=1)[4 * FS:12 * FS], 1, 16))
            ons = onsets(zin)
            for model, base, cand in PAIRS:
                rb, rc = (P.render(lib, x, FS, 0, stage_flags=st) for st in (base, cand)); lat = rb['latency']
                yb, yc = (r['stem'][4 * FS + lat:12 * FS + lat].astype(float).mean(axis=1) for r in (rb, rc))
                zb, zc = resample_poly(yb, 1, 16), resample_poly(yc, 1, 16)
                ch = [db(np.sum(zc[o:o + 450] ** 2), np.sum(zb[o:o + 450] ** 2)) for o in ons]
                ch = [v for v in ch if v is not None]
                row = dict(file_index=j, fraction=frac, model=model, onsets=len(ons),
                           layer_change_db=db(np.sum(yc ** 2), np.sum(yb ** 2)), difference_db=db(np.sum((yc - yb) ** 2), np.sum(yb ** 2)),
                           validity=[validity(zin, zb), validity(zin, zc)], onset_change_db=float(np.median(ch)) if ch else None)
                rows.append(row)
                v = row['validity']
                print('ROW', f'file{j}', f'{frac:.2f}', model, f"layer {row['layer_change_db']:+.2f} diff {row['difference_db']:+.1f} dB",
                      f"valid {100 * v[0]:.0f}->{100 * v[1]:.0f}%" if None not in v else '',
                      f"onsets {len(ons)} change {row['onset_change_db']:+.2f} dB" if ch else '', flush=True)
    summary = {}
    for model, _, _ in PAIRS:
        sub = [q for q in rows if q['model'] == model]
        vd = [100 * (q['validity'][1] - q['validity'][0]) for q in sub if None not in q['validity']]
        oc = [q['onset_change_db'] for q in sub if q['onset_change_db'] is not None]
        summary[model] = dict(layer_change_median=float(np.median([q['layer_change_db'] for q in sub])),
                              difference_median=float(np.median([q['difference_db'] for q in sub])),
                              validity_change_pp=dict(median=float(np.median(vd)), min=float(min(vd)), max=float(max(vd))),
                              onset_change_db=dict(median=float(np.median(oc)), min=float(min(oc)), max=float(max(oc))) if oc else None)
        print('SUMMARY', model, json.dumps(summary[model]), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study3.realmusic.v1', issue=4, files=len(files), candidate=CAND,
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

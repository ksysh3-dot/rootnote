#!/usr/bin/env python3
"""Resultant R2 sizing (#4 follow-up): does P1's layer lose harmonic validity where real music has close low
partials? Local files only; nothing here is committed or a listening score.

Per excerpt (research_s2_realmusic.excerpts, evaluated 8 s), frames as in research_r2_close_intervals (0.5 s Hann,
hop 0.25 s, 0.18 Hz bins at 3 kHz). Input partials: local maxima of the mono low band (32-190 Hz) at 30-190 Hz within
20 dB of the frame's strongest. Layer (P1 stem, shifted by the declared latency, mono): valid share = periodogram
energy within 2.5 Hz of k p (k = 2..8, below 1450 Hz) for any input partial p, over the layer's energy; coverage =
the share of the 30-1450 Hz bins inside those windows (what a spectrum spread evenly would score). Frames with the
layer within 30 dB of its loudest frame are counted, split by whether the input frame has a resolved close pair
(research_r2_close_intervals.close_pairs, 3-15 Hz, without the persistence rule). Reported per group: the median valid
share, the median coverage and the median excess (valid share - coverage).
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve())
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    w = np.hanning(C.N); fr = np.fft.rfftfreq(C.NFFT, 1 / CORE); span = (fr >= 30) & (fr <= 1450)
    groups = {'close': [], 'other': []}; rows = []
    for j, path in enumerate(files):
        for frac, start, x in RM.excerpts(path):
            r = P.render(lib, x, FS, 0); lat = r['latency']
            zin = sosfiltfilt(C.SOS, resample_poly(np.asarray(x, float).mean(axis=1)[4 * FS:12 * FS], 1, 16))
            zst = resample_poly(r['stem'][4 * FS + lat:12 * FS + lat].astype(float).mean(axis=1), 1, 16)
            frames = range(0, min(len(zin), len(zst)) - C.N, C.HOP)
            e = np.array([np.sum(zst[s:s + C.N] ** 2) for s in frames]); live = e >= e.max() * 1e-3
            per = {'close': [], 'other': []}
            for s, ok in zip(frames, live):
                if not ok: continue
                mi = np.abs(np.fft.rfft(zin[s:s + C.N] * w, C.NFFT))
                ms = np.abs(np.fft.rfft(zst[s:s + C.N] * w, C.NFFT)) ** 2
                parts = [fr[i] for i in C.peaks(mi, fr, rel_db=20)]
                if not parts: continue
                near = np.zeros(len(fr), bool)
                for q in parts:
                    for k in range(2, 9):
                        if k * q < 1450: near |= np.abs(fr - k * q) <= 2.5
                tot = ms[span].sum()
                if tot <= 0: continue
                valid = ms[near & span].sum() / tot; cover = near[span].mean()
                key = 'close' if C.close_pairs(mi, fr) else 'other'
                per[key].append((valid, cover)); groups[key].append((valid, cover))
            row = dict(file_index=j, fraction=frac)
            for key, v in per.items():
                if v:
                    v = np.array(v); row[key] = dict(frames=len(v), valid=float(np.median(v[:, 0])),
                                                     coverage=float(np.median(v[:, 1])),
                                                     excess=float(np.median(v[:, 0] - v[:, 1])))
            rows.append(row)
            txt = ' '.join(f"{k}: n {row[k]['frames']} valid {100 * row[k]['valid']:.0f}% cover {100 * row[k]['coverage']:.0f}%"
                           for k in ('close', 'other') if k in row)
            print('ROW', f'file{j}', f'{frac:.2f}', txt, flush=True)
    summary = {}
    for key, v in groups.items():
        if v:
            v = np.array(v); summary[key] = dict(frames=len(v), valid=float(np.median(v[:, 0])), coverage=float(np.median(v[:, 1])),
                                                 excess=float(np.median(v[:, 0] - v[:, 1])),
                                                 valid_p25=float(np.percentile(v[:, 0], 25)))
    print('SUMMARY', json.dumps(summary), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r2_validity.v1', issue=4, files=len(files),
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

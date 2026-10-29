#!/usr/bin/env python3
"""Resultant R2 sizing (#4 follow-up): how often real music puts two strong low partials closer than P1's analysis
resolves (phase 0: 41.2 + 55 Hz, 13.8 Hz apart, left the layer 43 % valid with 52 % intermodulation). Input only, no
engine. Local files only; nothing here is committed.

Per excerpt (research_s2_realmusic.excerpts, the evaluated 8 s), on the mono low band (Butterworth 32-190 Hz, 3 kHz):
0.5 s Hann frames, hop 0.25 s, zero-padded to 0.18 Hz bins. A frame is active when its low-band energy is within 30 dB
of the excerpt's loudest frame. In it, peaks are local maxima at 30-190 Hz within 12 dB of the strongest. A close pair
is two peaks 3-15 Hz apart, both within 12 dB of the strongest and with a dip of at least 6 dB below the weaker
between them (resolved partials, not one broad bump), seen in two consecutive frames (0.5 s or longer).
Reported: the share of active frames with a close pair, and the spacing and frequency of the pairs.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt
import research_s2_realmusic as RM

FS, CORE = 48000, 3000
N, HOP, NFFT = 1500, 750, 16384
SOS = butter(4, [32, 190], btype='bandpass', fs=CORE, output='sos')


def peaks(mag, fr, rel_db=12):
    band = (fr >= 30) & (fr <= 190); idx = np.where(band)[0]
    m = mag[idx]; top = m.max()
    if top <= 0: return []
    loc = [idx[i] for i in range(1, len(idx) - 1) if m[i] >= m[i - 1] and m[i] > m[i + 1] and m[i] >= top * 10 ** (-rel_db / 20)]
    return loc


def close_pairs(mag, fr):
    loc = peaks(mag, fr); out = []
    for i in range(len(loc)):
        for k in range(i + 1, len(loc)):
            a, b = loc[i], loc[k]; d = fr[b] - fr[a]
            if not 3 <= d <= 15: continue
            dip = mag[a:b + 1].min(); weaker = min(mag[a], mag[b])
            if dip <= weaker * 10 ** (-6 / 20): out.append((float(fr[a]), float(fr[b])))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    rows, spacings, centres = [], [], []
    w = np.hanning(N); fr = np.fft.rfftfreq(NFFT, 1 / CORE)
    for j, path in enumerate(files):
        for frac, start, x in RM.excerpts(path):
            z = resample_poly(np.asarray(x, float).mean(axis=1)[4 * FS:12 * FS], 1, 16)
            z = sosfiltfilt(SOS, z)
            frames = [z[s:s + N] for s in range(0, len(z) - N, HOP)]
            energy = np.array([np.sum(f ** 2) for f in frames]); live = energy >= energy.max() * 1e-3
            found = [close_pairs(np.abs(np.fft.rfft(f * w, NFFT)), fr) if ok else [] for f, ok in zip(frames, live)]
            hit = np.zeros(len(frames), bool)
            for t in range(len(frames) - 1):
                for pa in found[t]:
                    if any(abs(pa[0] - pb[0]) < 1.5 and abs(pa[1] - pb[1]) < 1.5 for pb in found[t + 1]):
                        hit[t] = hit[t + 1] = True; spacings.append(pa[1] - pa[0]); centres.append(.5 * (pa[0] + pa[1]))
            share = float(hit[live].mean()) if live.any() else None
            rows.append(dict(file_index=j, fraction=frac, active_frames=int(live.sum()), close_pair_share=share))
            print('ROW', f'file{j}', f'{frac:.2f}', f'active {int(live.sum())}', f'close-pair share {100 * share:.0f}%', flush=True)
    s = np.array([q['close_pair_share'] for q in rows if q['close_pair_share'] is not None])
    summary = dict(excerpts=len(s), median_share=float(np.median(s)), mean_share=float(s.mean()), max_share=float(s.max()),
                   excerpts_over_10pct=int((s > .1).sum()),
                   spacing_hz=dict(median=float(np.median(spacings)), p10=float(np.percentile(spacings, 10)),
                                   p90=float(np.percentile(spacings, 90))) if spacings else None,
                   centre_hz=dict(median=float(np.median(centres)), p10=float(np.percentile(centres, 10)),
                                  p90=float(np.percentile(centres, 90))) if centres else None)
    print('SUMMARY', json.dumps(summary), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.resultant.r2_close_intervals.v1', issue=4, files=len(files),
                                        summary=summary, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

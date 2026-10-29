#!/usr/bin/env python3
"""Resultant R3-a (#4), offline check before any engine change: does the T / 2 energy that misleads R3 come from the
percussive part? The mix (3 kHz) is split by a median-filter HPSS (STFT 256 / hop 32, harmonic median over 17 frames
= 181 ms, percussive median over 17 bins, Wiener masks p = 2), an approximation of the engine's own HPSS, and the R3
frame classes of research_r3a_diagnose (good / bad / kept) get, besides its features:
  h_frac_half   Lh(T/2) - L(T/2): how much of the T / 2 level is harmonic (0 dB = all of it)
  h_half        Lh(T/2) - Lh(T): the R3 T / 2 test on the harmonic part only
  h_spread      spread of Lh(T/2) over t - 60, t, t + 60 ms
  comod         correlation of the log envelopes at T / 2 and at T over the past 300 ms (85 ms frames, 10 ms hop):
                a fundamental and its own octave rise and fall together, an unrelated low instrument need not
  f_err_half    cents from exactly T / 2 of the interpolated peak within +-2.5 % (the 341 ms spectrum)
  f_err_15      cents from exactly 1.5 T of the peak there (an equal-tempered fifth is -2 cents, a partial 0)
--dump writes every sampled frame's features (JSON) for a combined-cue check across the two datasets.
Development data only (MUSDB18 7 s, BabySlakh after the R3 confirmation); decides nothing."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import istft, sosfiltfilt, stft
import research_gt_bass as G
import research_p1plus as P
import research_r3a_diagnose as D
import test_harmonic_continuity as H

FEATS = ('half', 'h_half', 'h_frac_half', 'h_spread', 'x15', 'half_peak', 'comod', 'f_err_half', 'f_err_15')
NE, HE = 256, 30   # envelope frames: 85 ms, 10 ms hop at 3 kHz


def envelopes(z):
    """Short-time magnitude spectra on a 10 ms grid (rows = frames) for the co-modulation cue."""
    win = np.hanning(NE); n = (len(z) - NE) // HE
    fr = np.fft.rfftfreq(2048, 1 / G.CORE)
    E = np.abs(np.fft.rfft(np.stack([z[i * HE:i * HE + NE] * win for i in range(n)]), 2048, axis=1)) + 1e-12
    return fr, E


def band_env(fr, E, f, i0, i1):
    m = (fr >= .975 * f) & (fr <= 1.025 * f); return 20 * np.log10(E[i0:i1][:, m].max(axis=1))


def peak_cents(S, f):
    m = np.where((D.FR >= .975 * f) & (D.FR <= 1.025 * f))[0]
    if len(m) < 3: return np.nan
    i = m[np.argmax(S[m])]
    if i in (m[0], m[-1]): return np.nan
    a, b, c = np.log(S[i - 1]), np.log(S[i]), np.log(S[i + 1]); den = a - 2 * b + c
    off = .5 * (a - c) / den if abs(den) > 1e-12 else 0.
    return float(1200 * np.log2((D.FR[i] + off * (D.FR[1] - D.FR[0])) / f))


def hpss_harmonic(z):
    f, t, Z = stft(z, fs=G.CORE, nperseg=256, noverlap=256 - 32, window='hann')
    S = np.abs(Z); Hm = median_filter(S, size=(1, 17)); Pm = median_filter(S, size=(17, 1))
    mask = Hm ** 2 / (Hm ** 2 + Pm ** 2 + 1e-20)
    _, zh = istft(Z * mask, fs=G.CORE, nperseg=256, noverlap=256 - 32, window='hann')
    out = np.zeros_like(z); n = min(len(z), len(zh)); out[:n] = zh[:n]; return out


def features(zm, zh, env, t, T):
    S, Sh = D.spec(zm, t), D.spec(zh, t)
    if S is None or Sh is None: return None
    lT, lh = D.level(S, T), D.level(S, T / 2); hT, hh = D.level(Sh, T), D.level(Sh, T / 2)
    sp = [D.level(x, T / 2) for x in (D.spec(zh, t - .06), D.spec(zh, t + .06)) if x is not None] + [hh]
    ring = (np.abs(D.FR / (T / 2) - 1) >= .05) & (np.abs(D.FR / (T / 2) - 1) <= .15)
    fr, E = env; i1 = int((t * G.CORE - NE / 2) / HE) + 1; i0 = max(0, i1 - 30)
    comod = np.nan
    if i1 - i0 >= 10 and i1 <= len(E):
        a, b = band_env(fr, E, T / 2, i0, i1), band_env(fr, E, T, i0, i1)
        if np.std(a) > 1e-6 and np.std(b) > 1e-6: comod = float(np.corrcoef(a, b)[0, 1])
    return dict(half=lh - lT, h_half=hh - hT, h_frac_half=hh - lh, h_spread=float(np.ptp(sp)), x15=D.level(S, 1.5 * T) - lT,
                half_peak=lh - 20 * np.log10(np.median(S[ring])), comod=comod,
                f_err_half=abs(peak_cents(S, T / 2)), f_err_15=abs(peak_cents(S, 1.5 * T)), T=T)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('--library', type=Path, required=True)
    p.add_argument('--reference', choices=('yin', 'midi'), default='yin'); p.add_argument('--midi-transpose', type=int, default=0)
    p.add_argument('--crop', default=''); p.add_argument('--per-class', type=int, default=300)
    p.add_argument('--dump', type=Path)
    a = p.parse_args(); lib = P.api(a.library.resolve()); rng = np.random.default_rng(0)
    cls = {'good': [], 'bad': [], 'kept': []}
    for j, (name, mix, bass, fs, midis, _) in enumerate(G.items(a.root)):
        s0 = 0.
        if a.crop:
            s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs)); mix, bass = mix[sl], bass[sl]
            if len(bass) < 5 * fs: continue
        bz = sosfiltfilt(G.LP, G.to_rate(bass, fs, G.CORE)); zm = G.to_rate(mix.mean(axis=1), fs, G.CORE); zh = hpss_harmonic(zm)
        env = envelopes(zm)
        if a.reference == 'midi':
            if not midis: continue
            notes = [n for m in midis for n in G.midi_notes(m)]; tt = G.grid(len(bz)); f0 = G.midi_f0(tt, notes, s0, a.midi_transpose)
        else: tt, f0 = G.yin(bz)
        if np.sum(np.isfinite(f0)) < 20: continue
        mix48 = G.to_rate(mix, fs, G.FS).astype(np.float32); tk = {}
        for m in ('p1', 'p1_r3'):
            fl, st = G.MODELS[m]; r = P.render(lib, mix48 if mix48.shape[1] == 2 else np.repeat(mix48, 2, axis=1), G.FS, fl, stage_flags=st)
            tk[m] = (H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / G.CORE)
        hits = {'good': [], 'bad': [], 'kept': []}; t_end = len(bz) / G.CORE - .2
        for t, f in zip(tt, f0):
            if not (1.0 <= t <= t_end) or not np.isfinite(f): continue
            b, c = D.strong(*tk['p1'], t), D.strong(*tk['p1_r3'], t); pb, pc = D.near(b, f), D.near(c, f)
            if pb is None and pc is not None and D.near(b, 2 * f) is not None: hits['good'].append((t, D.near(b, 2 * f)))
            elif pb is not None and pc is None and D.near(c, f / 2) is not None: hits['bad'].append((t, pb))
            elif pb is not None and pc is not None and f >= 82: hits['kept'].append((t, pb))
        for k, v in hits.items():
            take = v if len(v) <= a.per_class else [v[i] for i in sorted(rng.choice(len(v), a.per_class, replace=False))]
            for t, T in take:
                ft = features(zm, zh, env, t, T)
                if ft: cls[k].append(dict(item=name, **ft))
        print('ITEM', j, name, {k: len(v) for k, v in hits.items()}, flush=True)
    if a.dump: a.dump.write_text(json.dumps(cls))
    print('\nfeature quantiles (25 / 50 / 75), dB')
    for k, v in cls.items():
        print(f'-- {k}: {len(v)} frames from {len({x["item"] for x in v})} items')
        for f in FEATS:
            q = np.nanpercentile([x[f] for x in v], [25, 50, 75]) if v else [np.nan] * 3
            print(f'   {f:14s} {q[0]:7.1f} {q[1]:7.1f} {q[2]:7.1f}')
    print('\nAUC good > bad / good > kept')
    for f in FEATS:
        print(f'   {f:14s} {D.auc([x[f] for x in cls["good"]], [x[f] for x in cls["bad"]])}  {D.auc([x[f] for x in cls["good"]], [x[f] for x in cls["kept"]])}')
    # two-cue rule sweep: keep R3's own condition (implied by the class) and add h_half >= -X and h_frac_half >= -Y
    print('\nadded rule: h_half >= -X dB  (share of good kept / share of bad removed)')
    for X in (6, 10, 14, 18):
        g = np.mean([x['h_half'] >= -X for x in cls['good']]); bd = np.mean([x['h_half'] < -X for x in cls['bad']])
        print(f'   X={X:2d}: good kept {g:.2f}  bad removed {bd:.2f}')


if __name__ == '__main__':
    main()

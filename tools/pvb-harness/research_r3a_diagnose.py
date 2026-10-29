#!/usr/bin/env python3
"""Resultant R3-a diagnosis (#4): when R3 moves a P1 track T down to T / 2, what in the mix separates a correct restoration
(P1 was an octave up, T = 2 f0) from a wrong halving (P1 had the true fundamental, T = f0)? Development data only
(MUSDB18 7 s, BabySlakh after the R3 confirmation); renders P1 and R3, reads no new data, decides nothing.

Frame classes against the reference f0 (research_gt_bass): good = P1 octave up and R3 tracked (T = 2 f0); bad = P1 tracked
and R3 an octave down (T = f0); kept = both tracked with f0 >= 82 Hz (T = f0, not moved). Features at T from a 1024-sample
(341 ms) Hann spectrum of the mix at 3 kHz, level = peak within +-2.5 %: L(T/2) - L(T), L(1.5T) - L(T), L(2.5T) - L(T),
the spread of L(T/2) over t - 60, t, t + 60 ms, the T/2 peak over its +-5..15 % neighbourhood, and from the bass stem
(diagnosis only, not available to the engine) the stem's own L(T/2) - L(T) and mix minus stem at T/2.
"""
import argparse
from pathlib import Path
import numpy as np
from scipy.signal import sosfiltfilt
import research_gt_bass as G
import research_p1plus as P
import test_harmonic_continuity as H

N, PAD = 1024, 8192
WIN = np.hanning(N); FR = np.fft.rfftfreq(PAD, 1 / G.CORE)
FEATS = ('half', 'x15', 'x25', 'half_spread', 'half_peak', 'stem_half', 'mix_minus_stem_half', 'T')


def spec(z, t):
    c = int(round(t * G.CORE)); s = c - N // 2
    if s < 0 or s + N > len(z): return None
    return np.abs(np.fft.rfft(z[s:s + N] * WIN, PAD)) + 1e-12


def level(S, f, tol=.025):
    m = (FR >= f * (1 - tol)) & (FR <= f * (1 + tol)); return 20 * np.log10(S[m].max()) if m.any() else np.nan


def strong(tr, tin, t):
    k = min(max(np.searchsorted(tin, t), 0), len(tin) - 1)
    fr, a, st = tr[k, :, 2], tr[k, :, 4], tr[k, :, 1]; live = (st > 0) & (st < 5) & (a > 0)
    if not live.any(): return np.array([])
    live &= a >= .1 * a[live].max(); return fr[live]


def near(fl, f):
    if not len(fl): return None
    c = 1200 * np.abs(np.log2(fl / f)); i = int(np.argmin(c)); return float(fl[i]) if c[i] <= 50 else None


def features(zm, zs, t, T):
    S = spec(zm, t); Ss = spec(zs, t)
    if S is None or Ss is None: return None
    lT, lh = level(S, T), level(S, T / 2)
    sp = [level(x, T / 2) for x in (spec(zm, t - .06), spec(zm, t + .06)) if x is not None] + [lh]
    ring = (np.abs(FR / (T / 2) - 1) >= .05) & (np.abs(FR / (T / 2) - 1) <= .15)
    return dict(half=lh - lT, x15=level(S, 1.5 * T) - lT, x25=level(S, 2.5 * T) - lT, half_spread=float(np.ptp(sp)),
                half_peak=lh - 20 * np.log10(np.median(S[ring])), stem_half=level(Ss, T / 2) - level(Ss, T),
                mix_minus_stem_half=lh - level(Ss, T / 2), T=T)


def auc(a, b):
    """P(feature of a > feature of b), ties half: how well one threshold separates the two classes."""
    a = np.asarray([x for x in a if np.isfinite(x)]); b = np.asarray([x for x in b if np.isfinite(x)])
    if not len(a) or not len(b): return None
    r = np.argsort(np.argsort(np.r_[a, b])) + 1.
    return float((r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('--library', type=Path, required=True)
    p.add_argument('--reference', choices=('yin', 'midi'), default='yin'); p.add_argument('--midi-transpose', type=int, default=0)
    p.add_argument('--crop', default=''); p.add_argument('--per-class', type=int, default=300)
    p.add_argument('--candidate', default='p1_r3', help='model compared with p1 (e.g. p1_r3a for the R3-b question)')
    a = p.parse_args(); lib = P.api(a.library.resolve()); rng = np.random.default_rng(0)
    cls = {'good': [], 'bad': [], 'kept': []}; per_item = []
    for j, (name, mix, bass, fs, midis, _) in enumerate(G.items(a.root)):
        s0 = 0.
        if a.crop:
            s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs)); mix, bass = mix[sl], bass[sl]
            if len(bass) < 5 * fs: continue
        bz = sosfiltfilt(G.LP, G.to_rate(bass, fs, G.CORE)); zs = G.to_rate(bass, fs, G.CORE); zm = G.to_rate(mix.mean(axis=1), fs, G.CORE)
        if a.reference == 'midi':
            if not midis: continue
            notes = [n for m in midis for n in G.midi_notes(m)]; tt = G.grid(len(bz)); f0 = G.midi_f0(tt, notes, s0, a.midi_transpose)
        else: tt, f0 = G.yin(bz)
        if np.sum(np.isfinite(f0)) < 20: continue
        mix48 = G.to_rate(mix, fs, G.FS).astype(np.float32)
        tk = {}
        for m in ('p1', a.candidate):
            fl, st = G.MODELS[m]; r = P.render(lib, mix48 if mix48.shape[1] == 2 else np.repeat(mix48, 2, axis=1), G.FS, fl, stage_flags=st)
            tk[m] = (H.tracks(r['rows']), (H.core_indices(r['rows']).astype(float) - 383) / G.CORE)
        hits = {'good': [], 'bad': [], 'kept': []}; t_end = len(bz) / G.CORE - .2
        hi = dict(voiced=0, lost_half=0, lost_up=0, lost_other=0, gained=0)   # >= 82 Hz frame budget, candidate vs p1
        for t, f in zip(tt, f0):
            if not (1.0 <= t <= t_end) or not np.isfinite(f): continue
            b, c = strong(*tk['p1'], t), strong(*tk[a.candidate], t)
            pb, pc = near(b, f), near(c, f)
            if f >= 82:
                hi['voiced'] += 1
                if pb is not None and pc is None:
                    hi['lost_half' if near(c, f / 2) is not None else 'lost_up' if near(c, 2 * f) is not None else 'lost_other'] += 1
                elif pb is None and pc is not None: hi['gained'] += 1
            if pb is None and pc is not None and near(b, 2 * f) is not None: hits['good'].append((t, near(b, 2 * f)))
            elif pb is not None and pc is None and near(c, f / 2) is not None: hits['bad'].append((t, pb))
            elif pb is not None and pc is not None and f >= 82: hits['kept'].append((t, pb))
        per_item.append((name, {**{k: len(v) for k, v in hits.items()}, **{'hi_' + k: v for k, v in hi.items()}}))
        for k, v in hits.items():
            take = v if len(v) <= a.per_class else [v[i] for i in sorted(rng.choice(len(v), a.per_class, replace=False))]
            for t, T in take:
                ft = features(zm, zs, t, T)
                if ft: cls[k].append(dict(item=name, **ft))
        print('ITEM', j, name, per_item[-1][1], flush=True)
    print('\nfeature quantiles (25 / 50 / 75), dB unless T (Hz)')
    for k, v in cls.items():
        print(f'-- {k}: {len(v)} frames from {len({x["item"] for x in v})} items')
        for f in FEATS:
            q = np.nanpercentile([x[f] for x in v], [25, 50, 75]) if v else [np.nan] * 3
            print(f'   {f:20s} {q[0]:7.1f} {q[1]:7.1f} {q[2]:7.1f}')
    print('\nAUC good > bad (1 = feature higher for correct restorations; 0 = lower; 0.5 = no separation)')
    for f in FEATS:
        print(f'   {f:20s} good>bad {auc([x[f] for x in cls["good"]], [x[f] for x in cls["bad"]])}  '
              f'good>kept {auc([x[f] for x in cls["good"]], [x[f] for x in cls["kept"]])}')
    tot = {k: sum(c[k] for _, c in per_item) for k in per_item[0][1]} if per_item else {}
    print('\nframes (all, before sampling):', tot)
    print('items with most bad frames:', sorted(((c['bad'], n) for n, c in per_item), reverse=True)[:6])


if __name__ == '__main__':
    main()

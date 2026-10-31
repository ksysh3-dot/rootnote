"""HAUX Q1 (existence AUC) and Q2 (pitch) on the Slakh features (CHOICES.md sections 3-4).  usage: runpy.sh haux_q12.py -> q12_report.txt"""
import sys, glob
import numpy as np
from scipy.stats import rankdata
from pathlib import Path
import dcommon as DC

HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')
SONGS = DC.SONGS
BASS = [k for k in SONGS if k not in ('Track00023', 'Track00024', 'Track00026')]
NOB = [k for k in SONGS if k not in BASS]
HOP_S = 16 / 3000.0
CAUSE = {3: 'no-bass song', 4: 'drum', 5: 'bass late/reverb', 6: 'other instrument', 7: 'other'}


def load(key):
    parts = sorted(glob.glob(str(HX / 'cache' / f'feat_{key}_p*.npz')))
    zs = [np.load(p) for p in parts]
    d = {k: np.concatenate([z[k] for z in zs]) for k in zs[0].files}
    # voice uid per part: vi is global within the song already
    o = np.lexsort((d['i'], d['vi']))
    return {k: v[o] for k, v in d.items()}


def nm(a, idx):
    with np.errstate(all='ignore'):
        return np.nanmean(a[:, idx], axis=1)


def feats(d, W, b):
    """feature dict for window W, basis b in ('t', 'h')"""
    E = d[f'E_{b}{W}'].astype(float); Ei = d[f'Ei_{b}{W}'].astype(float)
    with np.errstate(all='ignore'):
        fl12 = np.nanmean(Ei[:, :11], 1); fl6 = np.nanmean(Ei[:, :5], 1)
        h12 = 10 * np.log10((np.nanmean(E[:, :11], 1) + 1e-30) / (fl12 + 1e-30))
        h6 = 10 * np.log10((np.nanmean(E[:, :5], 1) + 1e-30) / (fl6 + 1e-30))
        hodd = 10 * np.log10((np.nanmean(E[:, [1, 3, 5, 7, 9]], 1) + 1e-30) / (fl12 + 1e-30))
        e8 = E[:, :7]
        nh = np.nansum(np.where(np.isfinite(e8), e8 >= 4 * fl12[:, None], False), 1).astype(float)
    return dict(h12=h12, h6=h6, hodd=hodd, nhit=nh, hmin=np.minimum(h6, hodd))


def auc(pos, neg):
    pos = pos[np.isfinite(pos)]; neg = neg[np.isfinite(neg)]
    if len(pos) < 20 or len(neg) < 20:
        return np.nan
    r = rankdata(np.concatenate([pos, neg]))
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fpr_at_tpr(real, ghost, tpr=0.8):
    real = real[np.isfinite(real)]; ghost = ghost[np.isfinite(ghost)]
    if len(real) < 20 or len(ghost) < 20:
        return np.nan
    thr = np.quantile(real, 1 - tpr)
    return float((ghost >= thr).mean())


def pct(x, ref):
    ref = np.sort(ref[np.isfinite(ref)])
    return np.searchsorted(ref, x) / max(len(ref), 1)


D = {k: load(k) for k in SONGS}
L = []
P = lambda s='': L.append(s)
P(f'# HAUX Q1/Q2 (Slakh train dev songs) rows: ' + ', '.join(f'{k[-2:]}:{len(D[k]["T"])}' for k in SONGS))

# ------------------------------------------------------------------ build feature tables
F = {}      # (key, W, b) -> dict
for k in SONGS:
    for W in (40, 85):
        for b in ('t', 'h'):
            F[(k, W, b)] = feats(D[k], W, b)
cls = {k: D[k]['cls'] for k in SONGS}; comp = {k: D[k]['comp'] for k in SONGS}
real = {k: (cls[k] == 0) & (comp[k] == 0) for k in SONGS}
ghost = {k: (cls[k] == 2) & (comp[k] >= 3) for k in SONGS}
mism = {k: (cls[k] == 1) & (comp[k] == 2) for k in SONGS}
K2 = {k: D[k]['K2'].astype(float) for k in SONGS}

# pooled reference for percentile combos (real+ghost of bass songs)
def pool(W, b, name):
    return np.concatenate([F[(k, W, b)][name][real[k] | ghost[k]] for k in BASS])


combo_names = ['K2 (3 kHz cue)', 'H_sal12', 'H_sal6', 'n_hit', 'H_odd', '(d) pct(H12)+pct(nhit)', '(e) pct(H6)+0.5 K2', '(f) H_sal6 at f_h', '(h) min(H6,H_odd)', 'H_sal12 at f_h', '(h) at f_h']


def score_table(k, W):
    """dict name -> hop score array for song k, window W"""
    f = F[(k, W, 't')]; fh = F[(k, W, 'h')]
    s = {'K2 (3 kHz cue)': K2[k], 'H_sal12': f['h12'], 'H_sal6': f['h6'], 'n_hit': f['nhit'], 'H_odd': f['hodd'],
         '(d) pct(H12)+pct(nhit)': pct(f['h12'], pool(W, 't', 'h12')) + pct(f['nhit'], pool(W, 't', 'nhit')),
         '(e) pct(H6)+0.5 K2': pct(f['h6'], pool(W, 't', 'h6')) + 0.5 * K2[k],
         '(f) H_sal6 at f_h': fh['h6'], '(h) min(H6,H_odd)': f['hmin'], 'H_sal12 at f_h': fh['h12'], '(h) at f_h': fh['hmin']}
    return s


# ------------------------------------------------------------------ Q1 per-song hop AUC
P('\n## Q1 hop-level AUC, real (matched, right) vs ghost (silence class, stem-aware wrong); 7 bass songs')
res = {}
for W in (40, 85):
    P(f'\n### window {W} ms  (rows: song | n_real n_ghost | AUC per score)')
    P('song | n_real | n_ghost | ' + ' | '.join(combo_names))
    tab = []
    for k in BASS:
        s = score_table(k, W)
        a = [auc(s[n][real[k]], s[n][ghost[k]]) for n in combo_names]
        tab.append(a)
        P(f'{k} | {real[k].sum()} | {ghost[k].sum()} | ' + ' | '.join(f'{x:.3f}' for x in a))
    tab = np.array(tab)
    P('median over songs | | | ' + ' | '.join(f'{x:.3f}' for x in np.nanmedian(tab, 0)))
    P('min over songs | | | ' + ' | '.join(f'{x:.3f}' for x in np.nanmin(tab, 0)))
    res[W] = tab
    # pooled (all bass songs)
    s_all = {n: np.concatenate([score_table(k, W)[n] for k in BASS]) for n in combo_names}
    r_all = np.concatenate([real[k] for k in BASS]); g_all = np.concatenate([ghost[k] for k in BASS])
    P('pooled bass songs | ' + f'{r_all.sum()} | {g_all.sum()} | ' + ' | '.join(f'{auc(s_all[n][r_all], s_all[n][g_all]):.3f}' for n in combo_names))
    # FPR at TPR 80 %
    P('FPR(ghost passing) at the threshold passing 80 % of real, median over songs: ' + ' | '.join(
        f'{n}: {np.nanmedian([fpr_at_tpr(score_table(k, W)[n][real[k]], score_table(k, W)[n][ghost[k]]) for k in BASS]):.3f}' for n in combo_names if n != 'K2 (3 kHz cue)'))
    tp = np.nanmedian([K2[k][real[k]].mean() for k in BASS]); fp = np.nanmedian([K2[k][ghost[k]].mean() for k in BASS])
    P(f'K2 cue: real hops with K2 true (median over songs) {tp:.3f}; ghost hops with K2 true {fp:.3f}')

# ghost-only songs (vs pooled real from bass songs)
P('\n### ghost-only songs (no bass MIDI): AUC of ghost hops vs the POOLED real hops of the 7 bass songs (cross-song, flagged)')
for W in (40, 85):
    P(f'window {W} ms: ' + 'song | n_ghost | ' + ' | '.join(combo_names))
    sr = {n: np.concatenate([score_table(k, W)[n][real[k]] for k in BASS]) for n in combo_names}
    for k in NOB:
        s = score_table(k, W)
        P(f'{k} | {ghost[k].sum()} | ' + ' | '.join(f'{auc(sr[n], s[n][ghost[k]]):.3f}' for n in combo_names))

# per cause (pooled bass songs; ghost of that cause vs pooled real)
P('\n### per cause, ghost of cause vs pooled real of the 7 bass songs (hop level)')
for W in (40, 85):
    sr = {n: np.concatenate([score_table(k, W)[n][real[k]] for k in BASS]) for n in combo_names}
    P(f'window {W} ms: cause | n | ' + ' | '.join(combo_names))
    for c in (4, 5, 6, 7):
        sg = {n: np.concatenate([score_table(k, W)[n][ghost[k] & (comp[k] == c)] for k in BASS]) for n in combo_names}
        n_ = int(sum((ghost[k] & (comp[k] == c)).sum() for k in BASS))
        P(f'{CAUSE[c]} | {n_} | ' + ' | '.join(f'{auc(sr[n], sg[n]):.3f}' for n in combo_names))
    sg = {n: np.concatenate([score_table(k, W)[n][ghost[k]] for k in NOB]) for n in combo_names}
    P(f'{CAUSE[3]} (3 songs) | {int(sum(ghost[k].sum() for k in NOB))} | ' + ' | '.join(f'{auc(sr[n], sg[n]):.3f}' for n in combo_names))
# mismatch
P('\n### mismatch-wrong voices (cls 1, comp 2) vs real, per song median (information)')
for W in (40, 85):
    t_ = np.array([[auc(score_table(k, W)[n][real[k]], score_table(k, W)[n][mism[k]]) for n in combo_names] for k in BASS])
    P(f'window {W} ms: ' + ' | '.join(f'{n}: {np.nanmedian(t_[:, i]):.3f}' for i, n in enumerate(combo_names)))

# voice-level AUC
P('\n### Q1 voice-level AUC (median over the voice hops of the score; voices with >= 5 real / ghost hops)')
for W in (40, 85):
    rows_ = []
    for k in BASS:
        s = score_table(k, W)
        vi = D[k]['vi']
        out = []
        for n in combo_names:
            vr = []; vg = []
            for m, store in ((real[k], vr), (ghost[k], vg)):
                idx = np.flatnonzero(m)
                for v_ in np.unique(vi[idx]):
                    ii = idx[vi[idx] == v_]
                    if len(ii) >= 5:
                        store.append(np.nanmedian(s[n][ii]) if np.isfinite(s[n][ii]).any() else np.nan)
            out.append(auc(np.array(vr), np.array(vg)) if min(len(vr), len(vg)) >= 10 else np.nan)
        rows_.append(out)
    rows_ = np.array(rows_)
    P(f'window {W} ms median over songs: ' + ' | '.join(f'{n}: {np.nanmedian(rows_[:, i]):.3f}' for i, n in enumerate(combo_names)))

# ------------------------------------------------------------------ Q1 summary line
best = {}
for W in (40, 85):
    med = np.nanmedian(res[W], 0)
    for i, n in enumerate(combo_names):
        best[(W, n)] = med[i]
bk = max(((v, k) for k, v in best.items() if k[1] != 'K2 (3 kHz cue)'), key=lambda t: (t[0] if np.isfinite(t[0]) else -1))
P(f'\nQ1 best median per-song AUC (non-K2): {bk[0]:.3f} = {bk[1]};  K2 cue: W40/W85 median {best[(40, "K2 (3 kHz cue)")]:.3f}')

# ------------------------------------------------------------------ Q2 pitch
def cents(a, b):
    return 1200 * np.log2(np.maximum(a, 1e-9) / np.maximum(b, 1e-9))


P('\n## Q2 pitch on matched hops (cls 0), gate: f_track within 100 cent of m x f_MIDI (m in 0.5/1/2/3 nearest)')
names = ['f_osc', 'f_track', 'f_h W40', 'f_h W85']
errs = {n: [] for n in names}; per = {}; nomidi = 0; gated = 0; tot0 = 0
near_note = []
allrows = []
for k in SONGS:
    d = D[k]
    m0 = d['cls'] == 0
    tot0 += m0.sum()
    ok = m0 & np.isfinite(d['ftrue'])
    nomidi += (m0 & ~np.isfinite(d['ftrue'])).sum()
    ft = d['ftrue'] * d['mult']
    ok2 = ok & (np.abs(cents(d['ftr'], ft)) <= 100)
    gated += (ok & ~ok2).sum()
    e = {'f_osc': np.abs(cents(d['fosc'], ft)), 'f_track': np.abs(cents(d['ftr'], ft)), 'f_h W40': np.abs(cents(d['fh40'], ft)), 'f_h W85': np.abs(cents(d['fh85'], ft))}
    for n in names:
        errs[n].append(e[n][ok2])
    per[k] = {n: e[n][ok2] for n in names}
    # distance to the nearest MIDI note start (glide / note-change proxy)
    nb = np.full(len(d['T']), np.inf)
    allrows.append((k, ok2, e, d))
P(f'matched hops total {tot0}; no sounding MIDI segment {nomidi}; outside the 100 cent gate {gated}; used {sum(len(x) for x in errs["f_osc"])}')
P('pooled error (cent): name | median | p75 | p90 | share>25 | share>50')
for n in names:
    x = np.concatenate(errs[n])
    P(f'{n} | {np.median(x):.1f} | {np.percentile(x, 75):.1f} | {np.percentile(x, 90):.1f} | {(x > 25).mean():.3f} | {(x > 50).mean():.3f}')
P('per song median error (cent): song | n | ' + ' | '.join(names))
for k in SONGS:
    if len(per[k]['f_osc']) > 20:
        P(f'{k} | {len(per[k]["f_osc"])} | ' + ' | '.join(f'{np.median(per[k][n]):.1f}' for n in names))
P('per song p90 error (cent): ' + ' ; '.join(f'{k[-2:]}: ' + '/'.join(f'{np.percentile(per[k][n], 90):.0f}' for n in names) for k in SONGS if len(per[k]['f_osc']) > 20))
# share of songs where f_h better than f_track (median)
for W in ('f_h W40', 'f_h W85'):
    n_better = sum(np.median(per[k][W]) < np.median(per[k]['f_track']) for k in SONGS if len(per[k]['f_osc']) > 20)
    n_all = sum(1 for k in SONGS if len(per[k]['f_osc']) > 20)
    P(f'{W}: median error lower than f_track in {n_better}/{n_all} songs; p90 lower in {sum(np.percentile(per[k][W], 90) < np.percentile(per[k]["f_track"], 90) for k in SONGS if len(per[k]["f_osc"]) > 20)}/{n_all}')

# near note change vs elsewhere (needs segs: use ftrue change between consecutive hops of a voice as proxy -> note change within +-100 ms: ftrue differs)
P('\nerror near a MIDI note change (|T - nearest change of f_MIDI| < 100 ms, change detected as a change of the sounding segment f along time of the same song) vs elsewhere')
import bisect
nearE = {n: [] for n in names}; farE = {n: [] for n in names}
for k, ok2, e, d in allrows:
    # note change times = times where the sounding f_MIDI of consecutive rows (sorted by T) changes
    o = np.argsort(d['T']); T_ = d['T'][o]; fm = d['ftrue'][o]
    chg = [T_[i] for i in range(1, len(T_)) if np.isfinite(fm[i]) and np.isfinite(fm[i - 1]) and abs(fm[i] - fm[i - 1]) > 1e-6]
    chg = np.unique(np.round(chg, 3))
    if len(chg) == 0:
        continue
    j = np.searchsorted(chg, d['T']); jl = np.clip(j - 1, 0, len(chg) - 1); jr = np.clip(j, 0, len(chg) - 1)
    dist = np.minimum(np.abs(d['T'] - chg[jl]), np.abs(d['T'] - chg[jr]))
    near = dist < 0.1
    for n in names:
        nearE[n].append(e[n][ok2 & near]); farE[n].append(e[n][ok2 & ~near])
for n in names:
    a = np.concatenate(nearE[n]); b = np.concatenate(farE[n])
    P(f'{n}: near change n={len(a)} median {np.median(a):.1f} p90 {np.percentile(a, 90):.1f} | elsewhere n={len(b)} median {np.median(b):.1f} p90 {np.percentile(b, 90):.1f}')

# jitter
P('\n## Q2 hop-to-hop jitter on consecutive hops of one voice (matched voices; all hops of cls 0)')
jit = {n: [] for n in names}; jit_hz = {n: [] for n in names}; npairs = 0
per_song_rate = {}
for k in SONGS:
    d = D[k]
    m0 = np.flatnonzero(d['cls'] == 0)
    if len(m0) < 3:
        continue
    vi = d['vi'][m0]; h = d['h'][m0]
    pair = (vi[1:] == vi[:-1]) & (h[1:] - h[:-1] == 1)
    a_, b_ = m0[:-1][pair], m0[1:][pair]
    npairs += len(a_)
    arr = {'f_osc': d['fosc'], 'f_track': d['ftr'], 'f_h W40': d['fh40'], 'f_h W85': d['fh85']}
    per_song_rate[k] = {}
    for n in names:
        dz = np.abs(arr[n][b_] - arr[n][a_]); dc = np.abs(cents(arr[n][b_], arr[n][a_]))
        jit[n].append(dc); jit_hz[n].append(dz)
        per_song_rate[k][n] = ((dz > 2).sum() / max(len(dz) * HOP_S, 1e-9), len(dz))
P(f'consecutive pairs: {npairs} ({npairs * HOP_S:.1f} voice-seconds)')
P('name | median |df| Hz | p95 |df| Hz | median cent | p95 cent | jumps > 2 Hz/hop per voice-second | share of pairs > 2 Hz')
for n in names:
    z = np.concatenate(jit_hz[n]); c = np.concatenate(jit[n])
    P(f'{n} | {np.median(z):.3f} | {np.percentile(z, 95):.2f} | {np.median(c):.1f} | {np.percentile(c, 95):.1f} | {(z > 2).sum() / (len(z) * HOP_S):.2f} | {(z > 2).mean():.4f}')
P('per song jumps>2Hz per voice-second: song | ' + ' | '.join(names))
for k in per_song_rate:
    P(f'{k} | ' + ' | '.join(f'{per_song_rate[k][n][0]:.2f}' for n in names) + f' | (pairs {per_song_rate[k]["f_osc"][1]})')
# where f_osc jumps > 2 Hz: does f_h move?
zo = np.concatenate(jit_hz['f_osc']);
for W in ('f_h W40', 'f_h W85'):
    zh = np.concatenate(jit_hz[W]); m = zo > 2
    P(f'at the {m.sum()} pairs where f_osc jumps > 2 Hz: {W} moved < 1 Hz in {(zh[m] < 1).mean():.3f}, < 2 Hz in {(zh[m] < 2).mean():.3f}; f_track moved < 2 Hz in {(np.concatenate(jit_hz["f_track"])[m] < 2).mean():.3f}')

# ------------------------------------------------------------------ verdict lines
P('\n## verdict inputs (mechanical, CHOICES 3-4)')
med_auc = {W: np.nanmedian(res[W], 0) for W in (40, 85)}
q1 = max(np.nanmax(med_auc[W][1:]) for W in (40, 85))
P(f'Q1: best non-K2 median per-song AUC = {q1:.3f} (threshold 0.7) -> {"useful" if q1 >= 0.7 else "useless"}')
x = {n: np.concatenate(errs[n]) for n in names}
imp = {W: (np.median(x[W]) < np.median(x['f_track']) and np.percentile(x[W], 90) < np.percentile(x['f_track'], 90)) for W in ('f_h W40', 'f_h W85')}
rate = {n: (np.concatenate(jit_hz[n]) > 2).mean() for n in names}
half = {W: rate[W] <= 0.5 * rate['f_osc'] and np.median(x[W]) <= np.median(x['f_track']) for W in ('f_h W40', 'f_h W85')}
P(f'Q2: error improvement (median and p90 both lower than f_track): {imp}; jump rate <= half of f_osc at no worse median error: {half}; rates {rate}')
open(HX / 'q12_report.txt', 'w').write('\n'.join(L))
print('\n'.join(L))

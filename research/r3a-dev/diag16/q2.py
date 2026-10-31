"""Q2: V5a low bins on Track00060 (config A). Suite definition (research_core_metrics.v5) reproduced inline; each low bin classified."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M
import research_core_signals as S

FS = X.FS
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


name = 'Track00060'
ref = M.bass_ref(name)
rf = C.ref(name)
x = S.load_excerpt(S.SLAKH_TRAIN / name / 'mix.flac', 36.0, 12.0)
res = dict(voicing=0, ampSource=0)
ctx = M.Ctx(X.CAND, 15, res)
r0 = ctx.render('t60', x, 0.0, harmonic=True, voice=True); rd = ctx.render('t60', x, -120.0)
lay = M.layer_of(r0, rd)
trace = r0['voice']
B = int(.020 * FS); i0 = int(3.0 * FS); nb = int(8.0 / .020)
cen_song = 39.0 + .020 * (np.arange(nb) + .5)
f0 = M.midi_f0_fast(cen_song, ref['notes'], ref['tp'])
lo = ref['lo']; nbins = len(lo) // B
levall = 10 * np.log10(np.mean(lo[:nbins * B].reshape(nbins, B) ** 2, axis=1) + 1e-20)
p95 = np.percentile(levall, 95)
k0 = int(39.0 / .020); lev = levall[k0:k0 + nb]
present = np.isfinite(f0) & (lev > p95 - 20)
bs = M.bandpass(ref['bz'][36 * FS:49 * FS], 150, 600)[:len(lay)]
L = M.bandpass(lay, 150, 600)
el = np.array([np.sum(L[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(nb)])
es = np.array([np.sum(bs[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(nb)])
ratio = M.db10(el, 1e-20) - M.db10(es, 1e-20); ldb = M.db10(el, 1e-20); sdb = M.db10(es, 1e-20)
idx = np.flatnonzero(present); cen = (np.arange(nb) + .5) * .020
low = []
for i in idx:
    m = idx[np.abs(cen[idx] - cen[i]) <= .250]
    if ratio[i] < np.median(ratio[m]) - 6:
        low.append(i)
low = np.array(low)
P(f'Track00060 V5a (suite definition, 20 ms bins from 39.00 s): present bins {len(idx)}, low bins {len(low)} = {100*len(low)/len(idx):.2f} %  (reference 5.7 %; allowed at 5 %: {int(np.floor(.05*len(idx)))})')

d, hop, tc = X.hops_of(trace)
tcs = tc + 36.0                      # song time of the analysis centre
raw = np.asarray(trace).reshape(-1, 8, 22)
w = np.where(d['state'] > 0, (d['A'] * d['c'] * d['sig']) ** 2, 0.0)

# ---- alignment check between layer 150-600 energy and the trace's own predicted harmonic energy sum(a2^2+a3^2) (per hop, c*sigma already inside a_k?)
pred = np.nansum(np.where(d['state'] > 0, d['a2'] ** 2 + d['a3'] ** 2, 0.0), axis=1)
# layer energy per 5.333 ms hop-sized box, aligned to song time (layer index i0 -> 39.0 - 3.0 + 3.0 = song 39 at excerpt sample 3 s => song time = 36 + n/FS)
ts_hop = tcs
Eh = np.array([np.sum(L[int((t - 36 - 0.00267) * FS):int((t - 36 + 0.00267) * FS)] ** 2) if 0 < t - 36 < 11.5 else np.nan for t in ts_hop])
ok = np.isfinite(Eh) & (ts_hop > 38) & (ts_hop < 47)
best = None; prof = []
for lag in range(-12, 13):
    a_ = M.db10(pred[ok], 1e-12); b_ = M.db10(np.roll(Eh, -lag)[ok], 1e-12)     # layer at hop h+lag
    c_ = np.corrcoef(a_, b_)[0, 1]
    prof.append((lag, round(float(c_), 3)))
    if best is None or c_ > best[1]:
        best = (lag, c_)
P('corr profile (lag hops, corr): ' + str(prof))
P(f'alignment: layer energy follows the trace-predicted harmonic energy best at a lag of {best[0]} hops ({best[0]*16/3:.1f} ms) corr {best[1]:.3f} (0 = layer at analysis-centre time; used 0 for assignment unless it differs)')
LAG = best[0]

drum = rf['drum_on']; bass_on = ref and np.array([n[0] for n in ref['notes']])
pitched = np.array(sorted(n[0] for n in ref['nodrum']))
STATE = {0: '-', 1: 'CAND', 2: 'ON', 3: 'REL'}

# birth times of voices (state enters ON)
birth = []
for v in np.unique(d['voice'][d['state'] > 0]):
    hs, js = np.nonzero((d['voice'] == v) & (d['state'] > 0))
    st = d['state'][hs, js]
    first_on = hs[np.argmax(st == 2)] if (st == 2).any() else None
    if first_on is not None:
        birth.append((tcs[first_on], int(v)))
birth_t = np.array(sorted(b[0] for b in birth))
# state transitions ON -> REL / REL -> ON / coast starts, per voice
trans = []
for v in np.unique(d['voice'][d['state'] > 0]):
    hs, js = np.nonzero((d['voice'] == v) & (d['state'] > 0)); o = np.argsort(hs); hs, js = hs[o], js[o]
    st = d['state'][hs, js]; co = d['coast'][hs, js] > .5
    for k in range(1, len(hs)):
        if hs[k] == hs[k - 1] + 1 and (st[k] != st[k - 1] or (co[k] and not co[k - 1])):
            trans.append(tcs[hs[k]])
trans = np.array(sorted(trans))

rows = []
P('\n| bin | time (s) | ratio vs local med (dB) | layer vs local max (dB) | stem vs local med (dB) | nearest drum (ms, +after) | bass onset lag (ms) | voice birth lag (ms) | dominant voice (id f_osc Hz state coast) | A | c | SNR dB | N_v | state transitions within +-40 ms | handover | class |')
P('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
cls_count = {}
for i in low:
    t = cen_song[i]; t0, t1 = t - .01, t + .01
    m_ = idx[np.abs(cen[idx] - cen[i]) <= .25]
    hs = np.flatnonzero((tcs >= t0 - LAG * 16 / 3000) & (tcs < t1 - LAG * 16 / 3000))
    if not len(hs):
        hs = np.array([np.argmin(np.abs(tcs - t))])
    ws = w[hs].sum(axis=0)
    if ws.max() <= 0:
        dom = -1
    else:
        dom = int(np.argmax(ws))
    hc = hs[len(hs) // 2]
    if dom >= 0:
        vid = int(d['voice'][hc][dom]); st = int(d['state'][hc][dom]); co = d['coast'][hc][dom]
        info = dict(vid=vid, f=float(d['fosc'][hc][dom]), st=STATE[st], coast=int(co), A=float(d['A'][hc][dom]), c=float(d['c'][hc][dom]), snr=float(d['snr'][hc][dom]),
                    np_=float(raw[hc, dom, X.F_NP]))
    else:
        info = dict(vid=-1, f=0, st='-', coast=0, A=0, c=0, snr=np.nan, np_=np.nan)
    dd = t - drum; k = np.argmin(np.abs(dd)); dnear = dd[k] * 1000
    bl = t - bass_on; bl = bl[bl >= -0.01]; bass_lag = bl.min() * 1000 if len(bl) else np.inf
    pl = t - pitched; pl = pl[pl >= -0.01]; pit_lag = pl.min() * 1000 if len(pl) else np.inf
    bb = t - birth_t; bb = bb[bb >= -0.01]; birth_lag = bb.min() * 1000 if len(bb) else np.inf
    tr_near = np.sum(np.abs(trans - t) <= .04)
    # handover: dominant voice id differs between t-50 and t+50 ms
    def domvoice(tt):
        h_ = np.argmin(np.abs(tcs - tt)); ww = w[h_]
        return (int(d['voice'][h_][np.argmax(ww)]) if ww.max() > 0 else -1)
    handover = domvoice(t - .05) != domvoice(t + .05) and domvoice(t - .05) >= 0 and domvoice(t + .05) >= 0
    # classification (priority attack lag > drum-coincident > handover > other)
    attack = (bass_lag <= 60)
    drum_c = (-20 <= dnear <= 80)
    if attack:
        cl = 'attack lag'
    elif drum_c:
        cl = 'drum-coincident dip'
    elif handover or info['st'] in ('REL', 'CAND'):
        cl = 'voice handover'
    else:
        cl = 'other'
    flags = [n_ for n_, f_ in (('attack', attack), ('voice_birth<=60ms', birth_lag <= 60), ('drum', drum_c), ('handover', handover or info['st'] in ('REL', 'CAND')), ('N_v>=200', info['np_'] >= 200), ('dominant SNR<13dB', info['snr'] < 13)) if f_]
    cls_count[cl] = cls_count.get(cl, 0) + 1
    rows.append(dict(bin=int(i), t=float(t), cl=cl, flags=flags, ratio_vs_med=float(ratio[i] - np.median(ratio[m_])), layer_vs_max=float(ldb[i] - ldb[m_].max()),
                     stem_vs_med=float(sdb[i] - np.median(sdb[m_])), dnear=float(dnear), bass_lag=float(bass_lag), pit_lag=float(pit_lag), birth_lag=float(birth_lag), **info,
                     trans40=int(tr_near), handover=bool(handover)))
    P(f'| {i} | {t:.3f} | {ratio[i]-np.median(ratio[m_]):+.1f} | {ldb[i]-ldb[m_].max():+.1f} | {sdb[i]-np.median(sdb[m_]):+.1f} | {dnear:+.0f} | {bass_lag:.0f} (any pitched {pit_lag:.0f}) | {birth_lag:.0f} | '
      f'{info["vid"]} {info["f"]:.1f} {info["st"]} {info["coast"]} | {info["A"]:.4f} | {info["c"]:.2f} | {info["snr"]:.1f} | {info["np_"]:.0f} | {tr_near} | {handover} | {cl} [{",".join(flags)}] |')
P('\nclassification (first match in priority attack lag > drum-coincident > handover > other): ' + ', '.join(f'{k}: {v}' for k, v in cls_count.items()) + f'  of {len(low)} bins')
fl = {}
for r in rows:
    for f_ in r['flags']:
        fl[f_] = fl.get(f_, 0) + 1
P('overlapping flags (a bin can have several): ' + ', '.join(f'{k}: {v}' for k, v in fl.items()))
rr = sorted(r['ratio_vs_med'] for r in rows)
P(f'margin: ratio drops (dB below local median) of the {len(rows)} low bins: ' + ', '.join(f'{-x:.1f}' for x in rr[::-1]) + f'; bins within 2 dB of the -6 dB line: {sum(x > -8 for x in rr)}; if those were not low the rate would be {100*(len(rows)-sum(x > -8 for x in rr))/len(idx):.2f} %')
P(f'layer fell vs stem rose: layer below local max by >6 dB in {sum(r["layer_vs_max"]<-6 for r in rows)}/{len(rows)} bins; stem above local median by >3 dB in {sum(r["stem_vs_med"]>3 for r in rows)}/{len(rows)} bins')

# neighbouring-hop context for the worst bins: print per-hop voices around the 6 lowest bins
P('\nper-hop context for the 6 bins with the lowest ratio (hop times relative to the bin centre, ms; all voices with state>0 and c>0.05):')
for r in sorted(rows, key=lambda r: r['ratio_vs_med'])[:6]:
    t = r['t']; P(f'-- bin {r["bin"]} t={t:.3f}s ratio {r["ratio_vs_med"]:+.1f} dB class {r["cl"]}')
    for h in np.flatnonzero((tcs >= t - .04) & (tcs <= t + .04))[::2]:
        vs = [f'v{int(d["voice"][h][j])} {STATE[int(d["state"][h][j])]}{"/co" if d["coast"][h][j]>.5 else ""} f{d["fosc"][h][j]:.1f} A{d["A"][h][j]:.4f} c{d["c"][h][j]:.2f} snr{d["snr"][h][j]:.0f} N{raw[h,j,X.F_NP]:.0f}' for j in range(8) if d['state'][h][j] > 0 and d['c'][h][j] > .05]
        P(f'   {1000*(tcs[h]-t):+5.0f} | ' + ' || '.join(vs))
json.dump(rows, open(C.D16 / 'q2.json', 'w'), indent=1, default=float)
open(C.D16 / 'q2_report.txt', 'w').write('\n'.join(out))

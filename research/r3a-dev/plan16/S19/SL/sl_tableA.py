"""S19-SL Part A table + 19.13.1 rule (mechanical). Reads res/dev_*.json. usage: sl_tableA.py > tableA.txt"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/SL')
import numpy as np
import sl_lib as Z
db = Z.db
DS = {s: json.load(open(Z.RES / f'dev_{s}.json')) for s in Z.DEVSONGS}
# window order = Z.DEV
order = []   # (song, index in song)
for s, t in Z.DEV:
    order.append((s, DS[s]['segs'].index(t)))
names = [f'{s}@{t:g}' for s, t in Z.DEV]
nU = 7


def per(key_fn):
    return [key_fn(DS[s], i) for s, i in order]


real = per(lambda D, i: D['real_v16c'][i])
rbase = per(lambda D, i: D['recon_base'][i])
print('== fidelity of the reconstruction (recon baseline minus real v1.6-c, per dev window; INTERPRETATION: a constant offset is a gain, not an error) ==')
print('window | m1 dB | m4 dB | M30 real | M30 recon | M_input | excess real | excess recon | lag used')
for k, (s, i) in enumerate(order):
    q, r = rbase[k], real[k]
    print(f'{names[k]} | {db(q["m1"]) - db(r["m1"]):+.1f} | {db(q["m4"]) - db(r["m4"]):+.1f} | {r["Ml"]:.2f} | {q["Ml"]:.2f} | {r["Mi"]:.2f} | {r["Ml"] - r["Mi"]:+.2f} | {q["Ml"] - r["Mi"]:+.2f} | {DS[s]["lag_used"]}')
print('lags per song (corr, lag):', {s: [(round(c, 2), l) for c, l in DS[s]['lags']] for s in DS})
print('sustain share of ON hops:', {s: round(DS[s]['sus_frac'], 3) for s in DS})

secs = len(order) * Z.WIN
E = lambda lst, k: np.array([x[k] for x in lst])
m1_meas = E(real, 'm1'); m4_meas = E(real, 'm4'); ex_meas = E(real, 'Ml') - E(real, 'Mi'); ex12_meas = E(real, 'Ml12') - E(real, 'Mi12')
jb = np.array([DS[s]['jumps_base'][i] for s, i in order])
sets = {'dev15': list(range(15)), 'user7': list(range(7)), 'bey+lc8': list(range(7, 15))}


def pooled(m1, idx):
    return db(m1[idx].sum())


print('\n== measured v1.6-c (real layer) ==')
for nm, idx in sets.items():
    print(f'{nm}: m1 pooled {pooled(m1_meas, idx):.2f} dB, mean per-window {np.mean(db(m1_meas[idx])):.2f}; m4 pooled {pooled(m4_meas, idx):.2f}; m2 excess mean {ex_meas[idx].mean():+.3f} (2-12 Hz: {ex12_meas[idx].mean():+.3f}); a_2 jumps {jb[idx, 0].sum()} in {len(idx) * Z.WIN:.0f} s = {jb[idx, 0].sum() / (len(idx) * Z.WIN):.1f}/s')
print('\n== projected variants: change vs v1.6-c (projected = measured - (recon_base - recon_variant)); negative = better ==')
hdr = 'variant | m1 pooled dev15 | m1 mean-win dev15 | m1 user7 pooled | m1 bey+lc | m1 user windows improved | m2 dev15 (M30 excess) | m2 user7 | m2 bey+lc | m2 alt 20log(Ml/Mi) dev15 | m4 body pooled dev15 | m3 jumps/s dev15 (base {:.1f}) | m3 change'.format(jb[:, 0].sum() / secs)
print(hdr)
res = {}
for v in DS['v09']['var']:
    rv = per(lambda D, i: D['var'][v]['recon'][i])
    d1 = db(E(rv, 'm1')) - db(E(rbase, 'm1'))           # per-window change (dB)
    d4 = db(E(rv, 'm4')) - db(E(rbase, 'm4'))
    dM = E(rv, 'Ml') - E(rbase, 'Ml')
    dMalt = 20 * np.log10(np.maximum(E(rv, 'Ml'), 1e-9) / np.maximum(E(rbase, 'Ml'), 1e-9))
    # projected pooled: scale each window's measured energy by the per-window recon ratio
    m1p = m1_meas * 10 ** (d1 / 10); m4p = m4_meas * 10 ** (d4 / 10)
    ch = {nm: db(m1p[idx].sum()) - db(m1_meas[idx].sum()) for nm, idx in sets.items()}
    ch4 = db(m4p[list(range(15))].sum()) - db(m4_meas[list(range(15))].sum())
    nimp = int((d1[:nU] < 0).sum())
    jv = np.array([DS[s]['var'][v]['jumps'][i] for s, i in order])
    jr = jv[:, 0].sum() / secs
    jsv = np.array([DS[s]['var'][v]['jumps_sus'][i] for s, i in order])[:, 0].sum() / secs
    r = dict(jsus=jsv,m1=ch['dev15'], m1mean=float(d1.mean()), m1u=ch['user7'], m1b=ch['bey+lc8'], nimp=nimp, m2=float(dM.mean()), m2u=float(dM[:nU].mean()), m2b=float(dM[nU:].mean()),
             m2alt=float(dMalt.mean()), m4=ch4, jr=jr)
    res[v] = r
    print(f'{v} | {r["m1"]:+.2f} | {r["m1mean"]:+.2f} | {r["m1u"]:+.2f} | {r["m1b"]:+.2f} | {nimp}/7 | {r["m2"]:+.3f} | {r["m2u"]:+.3f} | {r["m2b"]:+.3f} | {r["m2alt"]:+.2f} | {r["m4"]:+.2f} | {jr:.1f} | {jr - jb[:, 0].sum() / secs:+.1f}')
jbs = np.array([DS[s]['jumps_base_sus'][i] for s, i in order])[:, 0].sum() / secs
print(f'\nm3 detail: baseline jumps/s total {jb[:, 0].sum() / secs:.1f}, of which inside sustain hop pairs {jbs:.1f}; after smoothing (inside sustain /s): ' + ', '.join(f'{v} {r["jsus"]:.1f}' for v, r in res.items()))
print('\n== per-window m1 change (dB) of the strongest variants ==')
for v in sorted(res, key=lambda k: res[k]['m1'])[:3]:
    rv = per(lambda D, i: D['var'][v]['recon'][i])
    d1 = db(E(rv, 'm1')) - db(E(rbase, 'm1'))
    print(v, ' '.join(f'{n}:{x:+.1f}' for n, x in zip(names, d1)))
print('\n== RULE 19.13.1 (mechanical): fold A5 family iff for EVERY variant: m1 dev15 pooled change > -2 dB AND m2 dev15 change > -1 dB ==')
hit1 = [v for v, r in res.items() if r['m1'] <= -2.0]; hit2 = [v for v, r in res.items() if r['m2'] <= -1.0]
print('variants reaching m1 <= -2 dB:', hit1); print('variants reaching m2 <= -1 dB:', hit2)
b1 = min(res, key=lambda k: res[k]['m1']); b2 = min(res, key=lambda k: res[k]['m2'])
print(f'best m1: {b1} {res[b1]["m1"]:+.2f} dB; best m2: {b2} {res[b2]["m2"]:+.3f}')
print('DECISION:', 'FOLD A5 family (no variant reaches either threshold)' if not hit1 and not hit2 else 'DO NOT FOLD: pre-register per-harmonic a_2 smoothing (variants above)')

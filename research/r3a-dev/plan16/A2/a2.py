"""16.6 V5a drop decomposition (readings: CHOICES.md, written before this was run).
usage (from ~/r3a-dev/diag16): ./run.sh ../plan16/A2/a2.py"""
import sys, json, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import metrics as MT, rows as R, evaluate as E, ladder as Ld, synth16 as S, tables as T
from stems import stem_streams

OUTD = Ld.OUTD.parent / 'A2'
key = 't60_36_48'; sig = Sig(key); dur = 12.0
segs, rf = Ld.segments(key)
y3s = pickle.load(open(Ld.OUTD / 'cache' / 'ladder_y3.pkl', 'rb'))
S_ = MT.v5_setup(); B, K, i0 = S_['B'], S_['K'], S_['i0']
idx, tcen = S_['idx'], S_['tcen']
t_ex = 3.0 + tcen


def drops_of(y3):
    y = R.up48(y3); n = int(12.3 * FS); y = np.pad(y, (0, max(0, n - len(y))))[:n]
    lay = MT.X.band_fft(y[:min(len(y), 12 * FS + 1000)], 150, 600)
    lay = np.pad(lay, (0, max(0, i0 + K * B - len(lay))))
    el = np.array([np.sum(lay[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    ratio = 10 * np.log10(el + 1e-20) - S_['es_db']
    d = [i for i in idx if ratio[i] < np.median(ratio[idx[np.abs(tcen[idx] - tcen[i]) <= .25]]) - 6]
    return np.array(d, int)


def flat_gains(f, kmax=8):
    f = np.atleast_1d(np.asarray(f, float)); w, g = T.lookup(f)
    out = np.zeros((7, len(f)))
    for k in range(2, kmax + 1):
        out[k - 2] = np.where((k * f <= 700.0) & (f > 0), g, 0.0)
    return out


stem_bh, _ = stem_streams(key)
v_r3 = Ld.oracle_voices(sig, stem_bh, segs)
act = Ld.stem_activity(segs, stem_bh)
iv_stem = [(max(a['on'], 0.0), a['off']) if a['active'] else (sg['s'], sg['e']) for a, sg in zip(act, segs)]
v_r3s = Ld.oracle_voices(sig, stem_bh, segs, intervals=iv_stem)

layers = {}
layers['R3'] = y3s[(key, 'R3')]; layers['R2'] = y3s[(key, 'R2')]; layers['P1'] = y3s[(key, 'P1')]
vc = E.shift(R.voices_core(sig), E.load_lags()['core'])
layers['core'] = S.render_layer16(vc, dur + 0.3)
chk = S.render_layer16(v_r3, dur + 0.3)
orig = S.engine_gains
S.engine_gains = flat_gains
cf_flat = S.render_layer16(v_r3, dur + 0.3)
S.engine_gains = orig
cf_act = S.render_layer16(v_r3s, dur + 0.3)

D = {r: drops_of(y) for r, y in layers.items()}
D['cf_flat'] = drops_of(cf_flat); D['cf_act'] = drops_of(cf_act)
sanity = dict(R3_cached=len(D['R3']), R3_rerender=len(drops_of(chk)), n=len(idx), rerender_max_abs_diff=float(np.max(np.abs(chk - layers['R3'][:len(chk)]))))

# ---- B boundaries (excerpt time)
ss, es = rf['ss'] - 36.0, rf['es'] - 36.0
bnd_midi = np.concatenate([ss, es])
bnd_stem = np.array([x for a in act if a['active'] for x in (a['on'], a['off'])])
bnd_stem = bnd_stem[np.isfinite(bnd_stem)]
def dist(t, b):
    return float(np.min(np.abs(b - t))) if len(b) else 9e9

# ---- T: stem 150-600 / 40-150 ratio per bin
bz, _n = MT.X.bass_stems_and_notes('Track00060')
lo = MT.X.band_fft(bz, 40, 150); hi = MT.X.band_fft(bz, 150, 600)
k0 = int(round(39.0 / 0.02)); s0 = 39 * FS
Tr = np.zeros(K)
for k in range(K):
    a, b = s0 + k * B, s0 + (k + 1) * B
    Tr[k] = 10 * np.log10(np.sum(hi[a:b] ** 2) + 1e-20) - 10 * np.log10(np.sum(lo[a:b] ** 2) + 1e-20)
def T_excess(i):
    m = idx[np.abs(tcen[idx] - tcen[i]) <= .25]
    return float(Tr[i] - np.median(Tr[m]))

flat_set = set(D['cf_flat'].tolist())
def classify(i):
    t = t_ex[i]; dm, ds = dist(t, bnd_midi), dist(t, bnd_stem)
    te = T_excess(i)
    if dm <= 0.05 or ds <= 0.05: c = 'B'
    elif te > 6: c = 'T'
    elif i not in flat_set: c = 'W'
    else: c = 'O'
    return c, dict(bin=int(i), t_ex=round(float(t), 3), d_midi_ms=round(dm * 1000, 1), d_stem_ms=round(ds * 1000, 1), T_excess_db=round(te, 2), cat=c)

res = {}
for r in ('R3', 'R2', 'core', 'P1'):
    L = [classify(i)[1] for i in D[r]]
    cnt = {c: sum(1 for x in L if x['cat'] == c) for c in 'BTWO'}
    res[r] = dict(drops=len(L), n=len(idx), v5a_pct=100 * len(L) / len(idx), counts=cnt, bins=L)
res['cf_flat'] = dict(drops=len(D['cf_flat']), n=len(idx), v5a_pct=100 * len(D['cf_flat']) / len(idx))
res['cf_act'] = dict(drops=len(D['cf_act']), n=len(idx), v5a_pct=100 * len(D['cf_act']) / len(idx))
r3p = res['R3']['v5a_pct']
for r in ('R3', 'R2', 'core', 'P1'):
    res[r]['delta_vs_R3_pp'] = res[r]['v5a_pct'] - r3p; res[r]['rel_pass'] = bool(res[r]['v5a_pct'] - r3p <= 2.0)
c = res['R3']['counts']; nd = max(res['R3']['drops'], 1)
rule = dict(W_share=c['W'] / nd, BT_share=(c['B'] + c['T']) / nd)
rule['outcome'] = ('W>=50%: weight table is a real synthesis problem' if rule['W_share'] >= .5 else
                   'B+T>=50%: R3 floor comes from the measurement; use the relative criterion only' if rule['BT_share'] >= .5 else
                   'neither: record both facts')
json.dump(dict(sanity=sanity, res=res, rule=rule, n_boundaries=dict(midi=int(len(bnd_midi)), stem=int(len(bnd_stem)))), open(OUTD / 'a2.json', 'w'), indent=1, default=float)
print(json.dumps(dict(sanity=sanity, rule=rule), indent=1))
for r in ('R3', 'R2', 'core', 'P1'):
    print(r, '%.2f%%' % res[r]['v5a_pct'], res[r]['drops'], res[r]['counts'], 'delta %.2f' % res[r]['delta_vs_R3_pp'], res[r]['rel_pass'])
print('cf_flat', res['cf_flat']); print('cf_act', res['cf_act'])
for x in res['R3']['bins']: print(x)

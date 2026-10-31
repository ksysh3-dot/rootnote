import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import det as DT
from dcommon import *
key = sys.argv[1] if len(sys.argv) > 1 else 'Track00001'
t0 = time.time()
sig = Sig(key)
S = DT.SongData(sig)
print('features', round(time.time() - t0, 1), 'runs', len(S.runs))
th = dict(db=6.0, cent=50.0, nhop=3)
t0 = time.time()
ev, pc = DT.detect_song(S, th)
kinds = {}
for e in ev:
    for x in e:
        kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
print('detect', round(time.time() - t0, 1), kinds, 'modified runs', sum(p is not None for p in pc))
t0 = time.time()
v = DT.dfull_voices(S, pc)
print('voices', round(time.time() - t0, 1), len(v))
segs, rf = LD.segments(key)
act = act15(segs, rf['bz'], 30.0)
truth = SATruth(key, sig.tc1, segs, act)
annotate(v, segs)
t0 = time.time()
fn = comp_fn_factory(truth, sig.tc1, LAG, segs)
Y = render_multi(v, 30.3, fn)
en = energies(Y)
R3r = RAW_A['res'][key]['R3']['v6b']['E_right']
print('render', round(time.time() - t0, 1), 'wrong_sa/R3R', en['E_wrong_sa'] / R3r, 'right vs R3', 10 * np.log10(en['E_right_sa'] / R3r))
# core baseline
cv = E.shift(R.voices_core(sig), LAG); annotate(cv, segs)
Y0 = render_multi(cv, 30.3, comp_fn_factory(truth, sig.tc1, LAG, segs))
e0 = energies(Y0)
print('core wrong_sa/R3R', e0['E_wrong_sa'] / R3r, 'right vs R3', 10 * np.log10(e0['E_right_sa'] / R3r))
# oracle
real = DT.oracle_intervals(S, pc)
kept, ns, ni = SR.s2_select(real, segs, dedup=False)
t0 = time.time()
ov, nshort, tshort = DT.build_oracle_voices(sig, kept, segs)
Yo = render_multi(ov, 30.3, comp_fn_factory(truth, sig.tc1, 0.0, segs))
eo = energies(Yo)
print('oracle', round(time.time() - t0, 1), 'wrong_sa/R3R', eo['E_wrong_sa'] / R3r, 'right vs R3', 10 * np.log10(eo['E_right_sa'] / R3r), 'nshort', nshort, len(kept), len(real))

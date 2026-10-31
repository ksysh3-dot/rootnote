"""What is the engine's dry-path delay vs the reported latency, and how is the layer aligned? (algo 15 and P1, out_db -18)"""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
import test_engine as T
FS = X.FS
cand = X.open_lib(X.CAND); ref = X.open_lib(X.REF)
x = np.zeros(int(2.0 * FS)); x[FS] = 0.5; x[FS + 1] = -0.25      # click at exactly sample 48000
for name, lib, algo in (('cand15', cand, 15), ('cand6', cand, 6), ('ref6', ref, 6), ('cand0', cand, 0)):
    for lvl in (0.0, -120.0):
        r = X.render(lib, x, algo, lvl, out_db=-18.0, cfg=X.CFG['A'])
        y = np.asarray(r['y'], float)[:, 0]
        k = int(np.argmax(np.abs(y)))
        print(f'{name:7s} vb_level {lvl:7.1f}: reported latency {r["lat"]}  output click peak at +{k - FS} samples after the input click (peak {y[k]:+.4f})')
# params of engine defaults: DYN/FLAT etc
e = T.Engine(cand, FS, vb_on=1, vb_algo=15)
for nm in ('ENABLED', 'HP_HZ', 'LOW_DB', 'HI_DB', 'OUT_DB', 'CEIL_DB', 'DYN_ON', 'VB_ON', 'VB_ALGO', 'VB_LEVEL_DB', 'FLAT', 'GATE_DB'):
    print(nm, e.params[T.P[nm]])
e.close()

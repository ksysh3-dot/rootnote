"""INFORMATION ONLY (not part of the registered stage 0): longer holds and the 'all voices incl. revived REL / any age' hold, synth reading (a)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F2')
import numpy as np
import f2_oracle as O
import fcommon as FC
import research_core_api as CA
import e7_v7d as E7
lay, tr, st = O.render_all(str(FC.LIB15))
d = CA.trace_dict(tr); dur = len(lay) / O.FS
hd = 1319
base = O.build(d, None, 0, 80)
lb = O.layer_of_set(base, 'amp', lambda r: True, dur); n = min(len(lb), len(lay)); lb = lb[:n]
ba = E7.burst(lb, O.HIT, 'R1')[1]
out = {}
for W in (80, 120, 160, 240):
    for age in (10, 0):
        res = O.build(d, hd, 0.0, W, age_hops=age)
        lh = O.layer_of_set(res, 'held', lambda r: True, dur)[:n]
        h = E7.burst(lh, O.HIT, 'R1')[1]
        out[f'W{W}_age{age}'] = dict(base=ba, held=h, gain=ba - h, n_old=sum(1 for rr in res.values() for r in rr if r['old']))
        print(f'W={W} min_age_hops={age}: synth base {ba:.2f} held {h:.2f} gain {ba - h:.2f} dB', flush=True)
json.dump(out, open('/home/ksysh/r3a-dev/plan16/F2/f2_oracle_info.json', 'w'), indent=1)

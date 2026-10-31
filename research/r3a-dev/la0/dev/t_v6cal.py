import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import pipeline as P, labels, rows as R

res = json.load(open(HOME / 'r3a-dev/core_results/verify_A/results.json'))['metrics']['V6']
per = {t['name']: t for t in res['per_track']}
print('suite pooled wrong_share', res['wrong_share'])
for name in TRAIN:
    sig = Sig(name)
    tr = labels.Truth(name, sig.tc1)
    vc = R.voices_core(sig); vp = R.voices_p1(sig)
    a = P.v6b_row(vc, sig.tc1, tr); b = P.v6b_row(vp, sig.tc1, tr)
    k = per[name]
    print(name, 'core share %.4f (suite %.4f)  P1 share %.4f' % (a['share'], k['wrong'] / k['total'], b['share']))

import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A')
import numpy as np
from data import *
import ladder as LD
sig = Sig('Track00001')
segs, rf = LD.segments('Track00001')
d = sig.core_d; tc = sig.core_tc
print(len(segs))
# legato / fall-through starts
cnt = 0
for k in range(1, len(segs)):
    if abs(segs[k]['s'] - segs[k - 1]['e']) < 1e-3 and segs[k]['s'] > 3:
        t = segs[k]['s']; h = int(np.searchsorted(tc, t))
        print('change at', round(t, 3), 'f', round(segs[k - 1]['f'], 1), '->', round(segs[k]['f'], 1))
        for hh in range(h - 4, h + 14):
            st = d['state'][hh]; m = st > 0
            print(hh, round(tc[hh] - t, 3), [(int(d['voice'][hh][j]), int(st[j]), round(d['fosc'][hh][j], 1), round(d['A'][hh][j] * d['c'][hh][j] * d['sig'][hh][j], 4), int(d['coast'][hh][j])) for j in np.flatnonzero(m)])
        cnt += 1
        if cnt >= 3:
            break

import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import common16 as C
print(C.TRACKS, TRAIN + EVAL)
for n in C.TRACKS:
    rf = C.ref(n)
    ss, es, ps = rf['ss'], rf['es'], rf['ps']
    m = ss < 30
    # polyphony
    ev = sorted([(s, 1) for s in ss[m]] + [(min(e, 30), -1) for e in es[m]])
    cur = 0; mx = 0
    for t, d in ev:
        cur += d; mx = max(mx, cur)
    f = 440 * 2 ** ((ps[m] + rf['tp'] - 69) / 12)
    print(n, 'tp', rf['tp'], 'bass notes<30s', int(m.sum()), 'max poly', mx, 'f range %.1f-%.1f' % (f.min(), f.max()), 'dur med %.3f' % np.median((es - ss)[m]),
          'first', round(float(ss[m].min()), 2), 'n bass stems?')

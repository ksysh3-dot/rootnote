import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
from dcommon import *
key = 'Track00020'
sig = Sig(key); dur = LD.dur_of(key)
segs, rf = LD.segments(key)
act = act15(segs, rf['bz'], dur)
ivs = [((max(a['on'], 0.0), a['off']) if a['active'] else (s['s'], s['e'])) for a, s in zip(act, segs)]
print(len(sig.bh))
for k in range(len(segs)):
    try:
        LD.oracle_voices(sig, sig.bh, [segs[k]], intervals=[ivs[k]])
    except Exception as ex:
        print('single fail', k, ivs[k], segs[k], ex)
for k in range(len(segs) - 1):
    try:
        LD.oracle_voices(sig, sig.bh, segs[k:k + 2], intervals=ivs[k:k + 2])
    except Exception as ex:
        print('pair fail', k, ivs[k:k + 2], [(s['f'], s['s'], s['e']) for s in segs[k:k + 2]], ex)

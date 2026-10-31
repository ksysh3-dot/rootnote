import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
from data import *
for key in ['bass9', 'bass8c', 'pink10', 'logoff_37_49', 'bare100', 'step25', 'bkp_0', 'steady8', 't60_36_48']:
    t0 = time.time()
    s = Sig(key)
    print(key, 'ok', len(s.bh), s.nhop, round(time.time() - t0, 1), flush=True)

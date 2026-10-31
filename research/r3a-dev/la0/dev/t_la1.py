import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import la

for key in ('bare100',):
    sig = Sig(key)
    for stream in ('bh', 'det'):
        for L in (0, 64, 120, 217):
            t0 = time.time()
            r = la.run_la(sig, stream, L)
            print(f'== {key} {stream} L={L}: chunks {len(r["chunks"])} intervals {len(r["ivs"])}  ({time.time()-t0:.1f}s)')
            for iv in r['ivs']:
                A = iv['Af']
                if len(A) == 0 or A.max() < 0.02:
                    continue
                ch = iv['ch']
                print(f'   chunk {ch.cid} f~{np.median(ch.f):.1f} presence [{stream_time(ch.ja_p):.3f},{stream_time(ch.jb_p):.3f}] interval [{stream_time(iv["j_on"]):.3f},{stream_time(iv["j_off"]):.3f}] '
                      f'Amax {A.max():.4f} A@+5ms {A[min(2,len(A)-1)]:.4f} +10ms {A[min(4,len(A)-1)]:.4f} +20ms {A[min(8,len(A)-1)]:.4f}')

"""Information only: voices around the LOGOFF 4.12 s cue (hop 1319, 7.063 s): id, state, f, amp A c sigma, per 2 hops."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F2')
import numpy as np
import f2_oracle as O
import fcommon as FC
import research_core_api as CA
lay, tr, st = O.render_all(str(FC.LIB15))
d = CA.trace_dict(tr)
hd = 1319
for h in range(hd - 12, hd + 22, 2):
    s = f'h{h - hd:+3d} t={(d["hop"][h,0]-382)/3000+CA.CORE_T0:.3f} '
    for j in range(8):
        if d['state'][h, j] > 0:
            s += f"| id{int(d['voice'][h,j])} s{int(d['state'][h,j])} f{d['f_osc'][h,j]:.0f} amp{d['A'][h,j]*d['c'][h,j]*d['sigma'][h,j]*1e3:.1f}m "
    print(s)

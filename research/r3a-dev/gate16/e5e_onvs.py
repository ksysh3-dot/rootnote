import numpy as np
import common16 as C
import research_core_xcheck as X

DT = 16 / 3000.0
on_s = 0.0; secs = 0.0
for name in C.TRACKS:
    tr = C.get_core(name); d, hop, tc = X.hops_of(tr); st = d['state']
    m = tc > 0.5
    on_s += (st[m] == 2).sum() * DT; secs += m.sum() * DT
print(f'ON voice-seconds {on_s:.0f} over {secs:.0f} s of music (10 Slakh train tracks): mean ON voices {on_s/secs:.2f}')
print(f'CAND->ON + REL->ON = 1337 + 1561 = 2898 events -> {2898/on_s:.2f} per ON voice-second (V3l bar 0.3 on bass+pink)')

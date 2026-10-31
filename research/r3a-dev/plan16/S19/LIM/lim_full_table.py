"""S19-LIM supplement: whole rendered span (2 s .. window/excerpt end + 1 s) per song, so songs where the limiter does act can be examined."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/LIM')
sys.dont_write_bytecode = True
import numpy as np
from pathlib import Path
import lim_table as Tb
Tb.RES = Path('/home/ksysh/r3a-dev/plan16/S19/LIM/res_full')
fmt = Tb.fmt
names = Tb.Z.ROWNAME
L = []; P = L.append
songs = list(range(14))
for cond, sname in (('s6', '+6 dB'), ('s0', '0 dB')):
    P(f'\n=== FULL span, {sname}: per song  GR>1% / GR>3% / GRmax / pump | r0 / rbest(lag) | P(GR>1|burst) vs else | layer-caused% | layerpk/prepk% ===')
    for row in Tb.ROWS:
        P(f'-- {names[row]}')
        for i in songs:
            m = Tb.metrics(row, cond, [(i, 'FULL')])
            if m['g1'] == 0 and m['gmax'] < 0.05:
                P(f'  song {i:2d}: GR>1 0.00  GRmax {fmt(m["gmax"])}  (limiter idle)  d_peak {fmt(m["d_peak"])}')
                continue
            P(f'  song {i:2d}: GR>1 {fmt(m["g1"]):>5} GR>3 {fmt(m["g3"]):>5} max {fmt(m["gmax"]):>5} mean {fmt(m["gmean"],3):>6} pump {fmt(m["pump"],3):>6} | r0 {fmt(m["r0"]):>5} rb {fmt(m["rb"]):>5}({int(m["lagb"]):+d}) | rd0 {fmt(m["rd0"]):>5} | P(burst) {fmt(m["p_ab"]):>6} else {fmt(m["p_nab"]):>6} share_after_burst {fmt(m["share_ab"]):>6} (base {fmt(m["base_ab"])}) | caused {fmt(m["caused"],0):>4} | lpk% {fmt(m["lpk_pct"],1):>5} | n_hit {m["n_hit"]}/{m["n"]} | d_peak {fmt(m["d_peak"])} d_M {fmt(m["d_M"],3)}')
    P(f'\n--- {sname} pooled over all 14 songs (blocks concatenated) ---')
    allseg = [(i, 'FULL') for i in songs]
    m = Tb.metrics('p1', 'off', allseg)
    P(f'  off     GR>1 {fmt(m["g1"]):>5} GR>3 {fmt(m["g3"]):>5} max {fmt(m["gmax"])} pump {fmt(m["pump"],3)}')
    for row in Tb.ROWS:
        m = Tb.metrics(row, cond, allseg)
        P(f'  {names[row]:7s} GR>1 {fmt(m["g1"]):>5} GR>3 {fmt(m["g3"]):>5} max {fmt(m["gmax"]):>5} mean {fmt(m["gmean"],3)} pump {fmt(m["pump"],3):>6} | r0 {fmt(m["r0"])} rb {fmt(m["rb"])}({int(m["lagb"]):+d}) rd0 {fmt(m["rd0"])} rdb {fmt(m["rdb"])}({int(m["lagdb"]):+d}) | P(GR>1|burst) {fmt(m["p_ab"])} else {fmt(m["p_nab"])} share_after_burst {fmt(m["share_ab"])} (base {fmt(m["base_ab"])}) | lpk% {fmt(m["lpk_pct"],1)} caused {fmt(m["caused"],0)} | n_hit {m["n_hit"]}/{m["n"]}')
open('/home/ksysh/r3a-dev/plan16/S19/LIM/tables_full.txt', 'w').write('\n'.join(L))
print('\n'.join(L))

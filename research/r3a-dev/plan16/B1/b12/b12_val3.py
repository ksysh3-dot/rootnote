import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
np.set_printoptions(linewidth=200, precision=3, suppress=True)
for sk, t0, t1 in WINDOWS:
    for eng in ('v15', 'v16b'):
        sy = synth(sk, eng, t0, t1)
        xt = total(sy)
        bp = band_hop_power(xt)
        lo, hi = sy['sel_lo'], sy['sel_hi']
        print(f'--- {sk} {t0} {eng}: components {len(sy["comp"])}')
        for which in ('lo', 'mid'):
            pa = hop_power(band_signal(sk, eng, which), sy['ts'])
            pm = bp[which]
            sl = slice(lo, hi)
            best = max(((np.corrcoef(db(pm[sl]), db(np.roll(pa, -s)[sl]))[0, 1], s) for s in range(-4, 5)))
            print(f'  {which}: model {db(pm[sl].mean()):.1f} dB actual {db(pa[sl].mean()):.1f} dB diff {db(pm[sl].mean()) - db(pa[sl].mean()):+.1f}; corr {np.corrcoef(db(pm[sl]), db(pa[sl]))[0, 1]:.2f}; best shift {best[1]} corr {best[0]:.2f}')

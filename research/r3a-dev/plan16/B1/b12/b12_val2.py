import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_data import *
np.set_printoptions(linewidth=200, precision=3, suppress=True)
for sk, t0, t1 in WINDOWS:
    for eng in ('v15', 'v16b'):
        cp = comps(sk, eng, t0, t1)
        print(f'--- {sk} {t0}-{t1} {eng} hops {len(cp["hop"])} gain nan {np.isnan(cp["g"]).sum()} gain med {np.nanmedian(cp["g"]):.3f} min/max {np.nanmin(cp["g"]):.3f}/{np.nanmax(cp["g"]):.3f}')
        for which in ('lo', 'mid'):
            pm = model_band_power(cp, which).sum(1)
            pa = hop_power(band_signal(sk, eng, which), cp['ts'])
            best = None
            for sh in range(-6, 7):
                x = db(pm); y = db(np.roll(pa, -sh))
                cc = np.corrcoef(x, y)[0, 1]
                if best is None or cc > best[0]: best = (cc, sh)
            print(f'  {which}: mean power model {db(pm.mean()):.1f} dB vs actual {db(pa.mean()):.1f} dB (diff {db(pm.mean()) - db(pa.mean()):+.1f}); corr of dB series {np.corrcoef(db(pm), db(pa))[0, 1]:.2f}, best shift {best[1]} hops corr {best[0]:.2f}')

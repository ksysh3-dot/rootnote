import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
import common16 as C
import tables as T

for name in ['Track00060', 'Track00020']:
    tc1, ts = C.get_p1(name)
    v = ts[:, :, 1] > 0
    f = ts[:, :, 2]; a = ts[:, :, 4]; fade = ts[:, :, 7]; life = ts[:, :, 11]
    a2 = ts[:, :, 14]; a3 = ts[:, :, 20]
    g2, g3 = T.harm_gains(f, 3)
    for lab, tr_, g in (('k=2', a2, g2), ('k=3', a3, g3)):
        for cond, nm in ((v & (fade > 0.99) & (life > 0.99) & (a > 1e-4), 'fade=1 life=1'), (v & (fade > 0.2) & (a > 1e-4), 'fade>0.2')):
            pred = a * fade * life * g
            m = cond & (pred > 1e-7)
            r = tr_[m] / pred[m]
            print(name, lab, nm, 'n', m.sum(), 'ratio median %.4f p5 %.4f p95 %.4f' % (np.median(r), np.percentile(r, 5), np.percentile(r, 95)))
        # by frequency band
        pred = a * fade * life * g; m = v & (fade > 0.99) & (life > 0.99) & (pred > 1e-7)
        for lo, hi in ((25, 60), (60, 110), (110, 220), (220, 500)):
            mm = m & (f >= lo) & (f < hi)
            if mm.sum():
                r = tr_[mm] / pred[mm]
                print('   f %d-%d n %d ratio med %.4f p5 %.4f p95 %.4f' % (lo, hi, mm.sum(), np.median(r), np.percentile(r, 5), np.percentile(r, 95)))
print('life/fade ranges', np.percentile(life[v], [1, 50, 99]), np.percentile(fade[v], [1, 50, 99]))

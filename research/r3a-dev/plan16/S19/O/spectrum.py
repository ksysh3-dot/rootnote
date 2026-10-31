"""S19-O item 4: 20-600 Hz spectrum of baseline recon (k=2,3, before kOutSos) in frames of the 7 windows whose centre is noevent. rows f4, r1r."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from s19o_lib2 import *
from scipy.signal import get_window
from scipy.ndimage import median_filter
NP_, HOP_ = 512, 128
win_ = get_window('hann', NP_)
FREQ = np.fft.rfftfreq(NP_, 1 / CFS)
out = {}
lines = []
Pr = lambda *a: lines.append(' '.join(str(x) for x in a))
for row in ('f4', 'r1r'):
    src = 'b0p0' if row == 'r1r' else row
    acc = {0.9: [], 0.7: []}; accall = []
    nfr = {0.9: 0, 0.7: 0}
    for i, sk in ((9, 'app'), (6, 'rem')):
        d, boxes = load(src, i)
        cl = classify(d, boxes)
        runs = make_runs(d, cl, r1r=(row == 'r1r'))
        el, em, y = recon_bands(d, cl, runs, ('base',))
        ih = cl['ih']
        # time of core sample n -> input time: (n - 398)/3000 + T0   (output sample convention)
        for (s, t0, t1) in P.WINDOWS:
            if s != sk:
                continue
            n0 = int(round((t0 - A.T0) * CFS)) + 398; n1 = int(round((t1 - A.T0) * CFS)) + 398
            for a in range(n0, n1 - NP_, HOP_):
                tcen = ((a + NP_ // 2) - 398) / CFS + A.T0
                tb = np.arange(tcen - 0.0427, tcen + 0.0427, A.BOX / A.FS)
                nb = np.clip(((tb) / (A.BOX / A.FS)).astype(int), 0, len(boxes) - 1)
                frac = (cl['ex'][nb] == NT).mean()
                X = np.abs(np.fft.rfft(y[a:a + NP_] * win_)) ** 2
                accall.append(X)
                for th in acc:
                    if frac >= th:
                        acc[th].append(X); nfr[th] += 1
    out[row] = {}
    Pr(f'=== {row}: frames kept (>=90% noevent) {nfr[0.9]}, (>=70%) {nfr[0.7]}, all window frames {len(accall)}')
    for th in (0.9, 0.7):
        if not acc[th]:
            continue
        Pm = np.mean(acc[th], 0)
        band = (FREQ >= 20) & (FREQ <= 600)
        rm = median_filter(Pm, size=31, mode='nearest')
        prom = 10 * np.log10(Pm / np.maximum(rm, 1e-300))
        lo = (FREQ >= 20) & (FREQ <= 150)
        line_mask = prom > 6
        share_lo = Pm[lo & line_mask].sum() / Pm[lo].sum()
        share_all = Pm[band & line_mask].sum() / Pm[band].sum()
        # top peaks
        pk = [k for k in range(1, len(Pm) - 1) if Pm[k] > Pm[k - 1] and Pm[k] > Pm[k + 1] and band[k]]
        pk = sorted(pk, key=lambda k: -Pm[k])[:12]
        Pr(f' [{int(th*100)}%] power in 20-150 Hz bins >6 dB over running median: {100*share_lo:.1f}% ; in 20-600: {100*share_all:.1f}%;  power 20-150 / 150-600 = {10*np.log10(Pm[lo].sum()/Pm[band & (FREQ>150)].sum()):+.1f} dB')
        Pr('   top peaks (Hz, dB re max, prominence dB, offset to nearest 187.5 Hz multiple Hz):', '; '.join(f'{FREQ[k]:.0f} {10*np.log10(Pm[k]/Pm[pk[0]]):.0f} {prom[k]:.0f} {FREQ[k]-187.5*np.round(FREQ[k]/187.5):+.0f}' for k in pk))
        # coarse spectrum in 25 Hz bins (dB re max)
        edges = np.arange(20, 601, 20)
        cb = [Pm[(FREQ >= a) & (FREQ < b)].sum() for a, b in zip(edges[:-1], edges[1:])]
        cb = 10 * np.log10(np.array(cb) / max(cb))
        Pr('   20 Hz-bin spectrum (dB re max) 20..600:', ' '.join(f'{x:.0f}' for x in cb))
        out[row][str(th)] = dict(freq=FREQ[band].tolist(), p=Pm[band].tolist())
json.dump(out, open(O_DIR / 'spectrum.json', 'w'))
open(O_DIR / 'spectrum.txt', 'w').write('\n'.join(lines))
print('\n'.join(lines))

import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import pipeline as P, la
import proxy16 as PX

# 1. does the P1 tracker hold a track near 100 Hz at the V4b holes of bkp_0?
sig = Sig('bkp_0'); ts, tc = sig.ts, sig.tc1
print('--- bkp_0: P1 tracks (state>0) within 5 Hz of 100 Hz per hop centre inside the holes')
for (a, b) in ((1.608, 1.698), (2.626, 2.759), (4.12, 4.231)):
    hs = np.flatnonzero((tc >= a) & (tc <= b))
    have = [(((ts[h, :, 1] > 0) & (np.abs(ts[h, :, 2] - 100) <= 5)).any()) for h in hs]
    ids = sorted({int(ts[h, j, 0] + 65536 * ts[h, j, 13]) for h in hs for j in range(12) if ts[h, j, 1] > 0 and abs(ts[h, j, 2] - 100) <= 5})
    print(f'  [{a},{b}] hops {len(hs)}  hops with a 100 Hz track: {sum(have)}  track ids seen: {ids}')
# also: all-hops statistic over notes 2..15, 40..440 ms after the onset
miss = tot = 0
for n in range(2, 16):
    hs = np.flatnonzero((tc >= .5 * n + .04) & (tc < .5 * n + .44))
    for h in hs:
        tot += 1; miss += not ((ts[h, :, 1] > 0) & (np.abs(ts[h, :, 2] - 100) <= 5)).any()
print(f'  hops in notes 2..15 (40-440 ms) without any state>0 track within 5 Hz of 100 Hz: {miss}/{tot}')
core_d = sig.core_d
missc = 0
for n in range(2, 16):
    hs = np.flatnonzero((sig.core_tc >= .5 * n + .04) & (sig.core_tc < .5 * n + .44))
    for h in hs:
        missc += not ((core_d['state'][h] > 0) & (np.abs(core_d['fosc'][h] - 100) <= 5)).any()
print(f'  same for the core v1.5 voices (state>0, f_osc): {missc}/{tot}')

# 2. gated line: intervals around one onset, per L (band stream and bh)
sg = Sig('step25')
for stream in ('bh', 'det'):
    for note in (11,):
        t0 = note * PX.PER; f0 = PX.STEP_NOTES[note]
        print(f'--- step25 {stream}: note {note} f0 {f0} Hz onset {t0:.3f} s (previous note ends {t0-0.125:.3f})')
        for L in P.LS:
            d = P.load_la('step25', stream, L, 191); r = d['res']
            out = []
            for iv in r['ivs']:
                ch = iv['ch']
                if abs(np.median(ch.f) - f0) > 0.15 * f0 or not len(iv['Af']):
                    continue
                a, b = float(stream_time(iv['j_on'])), float(stream_time(iv['j_off']))
                if b < t0 - 0.15 or a > t0 + 0.12:
                    continue
                out.append(f'c{ch.cid}[{(a-t0)*1000:+.0f},{(b-t0)*1000:+.0f}]ms f{np.median(ch.f):.0f} A{iv["Af"].max():.3f}')
            print(f'  L={L:3d}: ' + '  '.join(out))

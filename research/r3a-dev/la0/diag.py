"""Mechanism listings (information only, synthetic signals): tracker dropouts on bass+kick+pink, interval structure around a gated-line onset,
and around a same-pitch re-attack of the bass line (the V3d-bass finding).  run: ./run.sh ../la0/diag.py > ../la0/diag_intervals.txt"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import pipeline as P, la
import proxy16 as PX

sig = Sig('bkp_0'); ts, tc = sig.ts, sig.tc1
print('--- bkp_0: P1 tracks (state>0) within 5 Hz of 100 Hz per hop centre inside the V4b holes')
for (a, b) in ((1.608, 1.698), (2.626, 2.759), (4.12, 4.231)):
    hs = np.flatnonzero((tc >= a) & (tc <= b))
    have = [(((ts[h, :, 1] > 0) & (np.abs(ts[h, :, 2] - 100) <= 5)).any()) for h in hs]
    ids = sorted({int(ts[h, j, 0] + 65536 * ts[h, j, 13]) for h in hs for j in range(12) if ts[h, j, 1] > 0 and abs(ts[h, j, 2] - 100) <= 5})
    print(f'  [{a},{b}] hops {len(hs)}  hops with a 100 Hz track: {sum(have)}  track ids seen: {ids}')
miss = tot = 0
for n in range(2, 16):
    for h in np.flatnonzero((tc >= .5 * n + .04) & (tc < .5 * n + .44)):
        tot += 1; miss += not ((ts[h, :, 1] > 0) & (np.abs(ts[h, :, 2] - 100) <= 5)).any()
print(f'  hops in notes 2..15 (40-440 ms) without any state>0 track within 5 Hz of 100 Hz: {miss}/{tot}')
missc = 0
for n in range(2, 16):
    for h in np.flatnonzero((sig.core_tc >= .5 * n + .04) & (sig.core_tc < .5 * n + .44)):
        missc += not ((sig.core_d['state'][h] > 0) & (np.abs(sig.core_d['fosc'][h] - 100) <= 5)).any()
print(f'  same for the core v1.5 voices (state>0, f_osc): {missc}/{tot}')


def listing(key, stream, t0, f0, tol, w0=-0.40, w1=0.15):
    for L in P.LS:
        d = P.load_la(key, stream, L, 191); r = d['res']; out = []
        for iv in r['ivs']:
            ch = iv['ch']
            if abs(np.median(ch.f) - f0) > tol * f0 or not len(iv['Af']):
                continue
            a, b = float(stream_time(iv['j_on'])), float(stream_time(iv['j_off']))
            if b < t0 + w0 or a > t0 + w1:
                continue
            out.append(f'c{ch.cid}[{(a-t0)*1000:+.0f},{(b-t0)*1000:+.0f}]ms f{np.median(ch.f):.0f} A{iv["Af"].max():.3f}')
        print(f'  L={L:3d}: ' + '  '.join(out))


for stream in ('bh', 'det'):
    note = 11; t0 = note * PX.PER
    print(f'--- step25 {stream}: gated-line note {note}, f0 {PX.STEP_NOTES[note]} Hz, onset {t0:.3f} s (previous note ends {t0-0.125:.3f}); intervals within 15 % of f0, times re the onset')
    listing('step25', stream, t0, PX.STEP_NOTES[note], 0.15)
for stream in ('bh', 'det'):
    t0 = 3.0
    print(f'--- bass9 {stream}: same-pitch re-attack at {t0:.1f} s (100 Hz, 350 ms decay, 12 dB lower at the next attack); intervals within 15 % of 100 Hz, times re the re-attack')
    listing('bass9', stream, t0, 100.0, 0.15, w0=-0.6, w1=0.6)

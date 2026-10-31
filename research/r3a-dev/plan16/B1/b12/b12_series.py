import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
from b12_p1join import *
sk, t0, t1, vid_, n = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
eng = 'v15'
sy = synth(sk, eng, t0, t1)
lo, hi = sy['sel_lo'], sy['sel_hi']
cpw = {k: band_hop_power(x, ('lo', 'mid')) for k, x in sy['comp'].items() if k[0] == vid_}
plo = sum(c['lo'] for c in cpw.values()); pmid = sum(c['mid'] for c in cpw.values())
ci, tk, hm, hd = p1_tracks(sk); ids = tid(tk); pos = {int(c): i for i, c in enumerate(ci)}
tr = load(sk, eng)['tr']; ix = sy['ix']
s = int(np.where((sy['vid'] == vid_).any(0))[0][0])
print('slot', s, 'hop columns: t-t0(s) | st coast | A dB | c | sigma | snr | f_osc | f_track | v15 a2 dB | P1 tr.a dB | P1 target2 dB | P1 mask | lo dB(abs, dBFS) | mid dB')
for h in range(lo, min(lo + n, hi)):
    if sy['vid'][h, s] != vid_: continue
    r = ix[h]; j = pos[int(sy['hops'][h])]
    row = np.where((ids[j] == int(tr['track'][r, s])) & (tk[j][:, 1] > 0))[0]
    if len(row):
        t = tk[j][row[0]]; hh = hm[j][row[0]][0]; p1 = f'{20 * np.log10(t[4] + 1e-12):6.1f} {20 * np.log10(hh[0] + 1e-12):6.1f} {hh[2]:.2f}'
    else: p1 = '   -      -     -  '
    print(f'{sy["ts"][h] - t0:5.3f} | {int(sy["st"][h, s])} {int(tr["coasting"][r, s]):3d} | {20 * np.log10(tr["A"][r, s] + 1e-12):6.1f} | {tr["c"][r, s]:.2f} | {tr["sigma"][r, s]:.2f} | {tr["snr_db"][r, s]:5.1f} | {sy["fo"][h, s]:6.1f} | {tr["f_track"][r, s]:6.1f} | {20 * np.log10(sy["a"][0][h, s] + 1e-12):6.1f} | {p1} | {db(plo[h]) - 5:6.1f} | {db(pmid[h]) - 5:6.1f}')

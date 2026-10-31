"""Extension: song-wide / long-range attribution of the 20-150 Hz layer. usage: b12_ext.py app 178 222 | rem 0 <end>"""
import sys, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
from b12_p1join import *
import soundfile as sf
from scipy.signal import find_peaks
sk, T0, T1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
eng = 'v15'
CH = 4.0
FB = [0, 50, 75, 100, 125, 150, 200, 1e9]; KB = [0, 100, 150, 200, 300, 450, 1e9]
x, fs = sf.read(MUSIC[SONG_IDX[sk]], always_2d=True, dtype='float64')
g = np.gcd(fs, FS); inp = resample_poly(x[:, :2].mean(1), FS // g, fs // g); del x
nlay = len(load(sk, eng)['layer']) / FS
T1 = min(T1, nlay - 3)
ci, tk, hm, hd = p1_tracks(sk); ids = tid(tk); pos = {int(c): i for i, c in enumerate(ci)}
tr = load(sk, eng)['tr']


def peaks_at(t):
    n = int(.5 * FS); i = int((t - .25) * FS)
    if i < 0 or i + n > len(inp): return np.array([])
    nf = 1 << 16; fq = np.fft.rfftfreq(nf, 1 / FS); sel = (fq >= 25) & (fq <= 1200)
    P = np.abs(np.fft.rfft(inp[i:i + n] * np.hanning(n), nf))[sel]; d = 20 * np.log10(P + 1e-12); d -= d.max()
    pk, _ = find_peaks(d, height=-30, distance=int(2.0 / fq[1]))
    return fq[sel][pk]


acc = dict(E=0.0, Emid=0.0, k=np.zeros(7), fb=np.zeros(7), kb=np.zeros(6), real=0., ghost=0., none=0., mask0=0., maskpart=0., maskon=0., notrk=0.,
           mid_mask0=0., mid_notrk=0., mid_maskon=0., st=np.zeros(4), chg=0, dur=0.0, nvoice=0.0, cls=np.zeros(3), nhop=0, hopcls=np.zeros(3),
           p1lo=0.0, v15lo=0.0, p1mid=0.0, v15mid=0.0, fk2_lt75=0.0, ghost_k=np.zeros(5))
rows = []
pk_cache = {}
t = T0
while t < T1:
    t1 = min(t + CH, T1)
    sy = synth(sk, eng, t, t1)
    lo, hi = sy['sel_lo'], sy['sel_hi']; sl = slice(lo, hi)
    if hi - lo < 10: t = t1; continue
    cpw = {k: band_hop_power(xx, ('lo', 'mid')) for k, xx in sy['comp'].items()}
    fo = sy['fo']; st = sy['st']
    plo_h = hop_power(band_signal(sk, 'P1', 'lo'), sy['ts']); pmid_h = hop_power(band_signal(sk, 'P1', 'mid'), sy['ts'])
    alo_h = hop_power(band_signal(sk, eng, 'lo'), sy['ts']); amid_h = hop_power(band_signal(sk, eng, 'mid'), sy['ts'])
    acc['p1lo'] += plo_h[sl].sum(); acc['v15lo'] += alo_h[sl].sum(); acc['p1mid'] += pmid_h[sl].sum(); acc['v15mid'] += amid_h[sl].sum(); acc['nhop'] += hi - lo
    coast = tr['coasting'][sy['ix']]; trk = tr['track'][sy['ix']]
    # activity: sounding voices per hop, ON<->REL changes
    snd = (st >= 2)
    acc['nvoice'] += snd[sl].sum()
    for s in range(8):
        a_, b_ = st[lo - 1:hi - 1, s], st[lo:hi, s]
        v_a, v_b = sy['vid'][lo - 1:hi - 1, s], sy['vid'][lo:hi, s]
        acc['chg'] += int(((a_ != b_) & (a_ >= 2) & (b_ >= 2) & (v_a == v_b)).sum())
    acc['dur'] += (hi - lo) * 16 / 3000
    for (v, kk), c in cpw.items():
        e = c['lo'][sl]; em = c['mid'][sl]
        acc['E'] += e.sum(); acc['Emid'] += em.sum(); acc['k'][kk - 2] += e.sum()
        for s in range(8):
            for h in np.where(sy['vid'][:, s] == v)[0]:
                if not (lo <= h < hi) or st[h, s] < 1: continue
                w = c['lo'][h]; wm = c['mid'][h]; f0 = fo[h, s]
                for j in range(7):
                    if FB[j] <= f0 < FB[j + 1]: acc['fb'][j] += w
                kf = kk * f0
                for j in range(6):
                    if KB[j] <= kf < KB[j + 1]: acc['kb'][j] += w
                acc['st'][int(st[h, s])] += w
                if kk == 2 and f0 < 75: acc['fk2_lt75'] += w
                if kk == 2:       # P1 side, once per voice-hop (k=2 carries ~all of the lo energy)
                    j = pos.get(int(sy['hops'][h]))
                    wl = sum(cpw[(v, k2)]['lo'][h] for k2 in range(2, 9) if (v, k2) in cpw); wm2 = sum(cpw[(v, k2)]['mid'][h] for k2 in range(2, 9) if (v, k2) in cpw)
                    row = np.where((ids[j] == int(trk[h, s])) & (tk[j][:, 1] > 0))[0] if (j is not None and trk[h, s] > 0) else []
                    if len(row) == 0: acc['notrk'] += wl; acc['mid_notrk'] += wm2
                    else:
                        mk = hm[j][row[0]][0][2]
                        if mk <= 1e-6: acc['mask0'] += wl; acc['mid_mask0'] += wm2
                        elif mk < .5: acc['maskpart'] += wl
                        else: acc['maskon'] += wl; acc['mid_maskon'] += wm2
                    # input relation
                    if wl > 0:
                        tt = sy['ts'][h]; key = round(tt * 8)
                        if key not in pk_cache: pk_cache[key] = peaks_at(key / 8)
                        pf = pk_cache[key]
                        tol = max(50.0, 1200 * np.log2(1 + 2.5 / f0))
                        nc = lambda f: np.min(np.abs(1200 * np.log2(f / pf))) if len(pf) else 1e9
                        if nc(f0) <= tol: acc['real'] += wl
                        else:
                            hit = [k3 for k3 in (2, 3, 4) if nc(k3 * f0) <= tol]
                            if hit: acc['ghost'] += wl; acc['ghost_k'][hit[0]] += wl
                            else: acc['none'] += wl
    t = t1
    print('chunk', t, flush=True)

# level rows: 2 s windows, hop 1 s over the whole range, actual renders
rows = []
for tt in np.arange(T0, T1 - 2, 1.0):
    sy_ts = np.arange(int(tt * FS), int((tt + 2) * FS) - 256, 256) / FS
    r = []
    for e in ('P1', eng):
        r += [db(hop_power(band_signal(sk, e, 'lo'), sy_ts).mean()), db(hop_power(band_signal(sk, e, 'mid'), sy_ts).mean())]
    rows.append((tt, *r))
rows = np.array(rows)
E = acc['E']
rep = []; P = rep.append
mm = lambda t: f'{int(t // 60)}:{t % 60:04.1f}'
P(f'=== {sk} {mm(T0)}-{mm(T1)} engine {eng}: range-wide attribution of the 20-150 Hz layer ({acc["dur"]:.0f} s of hops)')
P(f'MEASURED mean levels dBFS: 20-150: P1 {db(acc["p1lo"] / acc["nhop"]):.1f}, v15 {db(acc["v15lo"] / acc["nhop"]):.1f} | 150-600: P1 {db(acc["p1mid"] / acc["nhop"]):.1f}, v15 {db(acc["v15mid"] / acc["nhop"]):.1f}; lo-mid: P1 {db(acc["p1lo"]) - db(acc["p1mid"]):.1f} dB, v15 {db(acc["v15lo"]) - db(acc["v15mid"]):.1f} dB')
P('MEASURED by k: ' + ', '.join(f'k={k + 2}: {acc["k"][k] / E * 100:.1f}%' for k in range(7)))
P('MEASURED voice f_osc distribution of the energy: ' + ', '.join(f'{FB[j]:.0f}-{(FB[j + 1] if FB[j + 1] < 1e8 else 999):.0f}: {acc["fb"][j] / acc["fb"].sum() * 100:.1f}%' for j in range(7)))
P('MEASURED k*f_osc: ' + ', '.join(f'{KB[j]:.0f}-{(KB[j + 1] if KB[j + 1] < 1e8 else 999):.0f}: {acc["kb"][j] / acc["kb"].sum() * 100:.1f}%' for j in range(6)))
P(f'MEASURED k=2 of voices with f_osc < 75 Hz (the only way k=2 lands below 150 Hz): {acc["fk2_lt75"] / E * 100:.1f}% of the energy')
tot_in = acc['real'] + acc['ghost'] + acc['none']
P(f'MEASURED input relation (E-weighted): f_osc at a real input partial {acc["real"] / tot_in * 100:.0f}%; sub-harmonic ghost (k f_osc hits a partial, f_osc itself does not) {acc["ghost"] / tot_in * 100:.0f}% (first matching k=2/3/4: ' + '/'.join(f'{acc["ghost_k"][k] / max(acc["ghost"], 1e-30) * 100:.0f}%' for k in (2, 3, 4)) + f'); nothing {acc["none"] / tot_in * 100:.0f}%')
P(f'MEASURED voice state of the energy (1 cand/2 ON/3 REL): ' + ', '.join(f'{k}: {acc["st"][k] / acc["st"].sum() * 100:.0f}%' for k in (1, 2, 3)))
P(f'MEASURED ON<->REL changes: {acc["chg"] / acc["dur"]:.1f} per second over all slots; mean sounding voices {acc["nvoice"] / acc["nhop"]:.2f}')
tt_ = acc['mask0'] + acc['maskpart'] + acc['maskon'] + acc['notrk']
P(f'MEASURED P1 permission for the same voices (share of lo | share of mid energy): no P1 track {acc["notrk"] / tt_ * 100:.0f}% | {acc["mid_notrk"] / (acc["mid_notrk"] + acc["mid_mask0"] + acc["mid_maskon"]) * 100:.0f}%; P1 track but k=2 mask 0 {acc["mask0"] / tt_ * 100:.0f}% | {acc["mid_mask0"] / (acc["mid_notrk"] + acc["mid_mask0"] + acc["mid_maskon"]) * 100:.0f}%; mask on {acc["maskon"] / tt_ * 100:.0f}% | {acc["mid_maskon"] / (acc["mid_notrk"] + acc["mid_mask0"] + acc["mid_maskon"]) * 100:.0f}%')
d = rows[:, 3] - rows[:, 1]
P(f'MEASURED 2 s windows (hop 1 s), v15 minus P1 in 20-150 Hz: median {np.median(d):.1f} dB, p10 {np.percentile(d, 10):.1f}, p90 {np.percentile(d, 90):.1f}; v15 20-150 median {np.median(rows[:, 3]):.1f} dBFS, max {rows[:, 3].max():.1f}; lo-minus-mid (v15) median {np.median(rows[:, 3] - rows[:, 4]):.1f} dB')
o = np.argsort(-rows[:, 3])[:8]
P('top 2-s windows by v15 20-150 level (start | v15 lo | P1 lo | v15 mid | P1 mid): ' + '; '.join(f'{mm(rows[i, 0])} {rows[i, 3]:.0f}/{rows[i, 1]:.0f}/{rows[i, 4]:.0f}/{rows[i, 2]:.0f}' for i in o))
open(B12 / f'ext_{sk}_{int(T0)}_{int(T1)}.txt', 'w').write('\n'.join(rep)); print('\n'.join(rep))
np.save(B12 / f'ext_rows_{sk}_{int(T0)}_{int(T1)}.npy', rows)

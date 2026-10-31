"""Q2: what does P1 do at the same moments for the voices that carry v15's 20-150 Hz energy. usage: b12_q2.py [eng]"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_synth import *
from b12_p1join import *
eng = sys.argv[1] if len(sys.argv) > 1 else 'v15'
rep = []; P = rep.append
pool = {}
for sk, t0, t1 in WINDOWS:
    sy = synth(sk, eng, t0, t1)
    lo, hi = sy['sel_lo'], sy['sel_hi']; H = len(sy['hops']); sl = slice(lo, hi)
    cpw = {k: band_hop_power(x, ('lo', 'mid')) for k, x in sy['comp'].items()}
    tot = band_hop_power(total(sy))
    ci, tk, hm, hd = p1_tracks(sk); ids = tid(tk); pos = {int(c): i for i, c in enumerate(ci)}
    tr = load(sk, eng)['tr']
    hopsel = sy['hops']
    coast = tr['coasting'][sy['ix']]; trk = tr['track'][sy['ix']]
    P(f'=== {sk} {t0} {eng} vs P1 (hop = 5.33 ms; weights = the voice\'s own 20-150 Hz hop power from the re-synthesis)')
    cats = {}
    def add(c, w, key=None):
        cats[c] = cats.get(c, 0.0) + w
    nm_amp_v15 = nm_amp_p1 = nh_match = 0
    top = sorted({v for (v, k) in cpw}, key=lambda v: -sum(c['lo'][sl].sum() for (vv, kk), c in cpw.items() if vv == v))
    topset = set(top[:5])
    detail = {v: dict(n=0, nomatch=0, coast=0, zero=0, nz=0, st={}, life=[], fade=[], dB=[], reasons={}, a15=[], ap1=[]) for v in top[:5]}
    Etot = 0
    for v in top:
        plo = sum(c['lo'] for (vv, kk), c in cpw.items() if vv == v)
        for s in range(8):
            m = np.where(sy['vid'][:, s] == v)[0]
            for h in m:
                if not (lo <= h < hi): continue
                w = plo[h]; Etot += w
                j = pos.get(int(hopsel[h]))
                a2 = sy['a'][0][h, s]
                if sy['st'][h, s] < 1 or j is None: continue
                row = np.where((ids[j] == int(trk[h, s])) & (tk[j][:, 1] > 0))[0] if trk[h, s] > 0 else []
                if len(row) == 0:
                    add('no P1 track with this id' + (' (v15 voice coasting)' if coast[h, s] > 0 else ' (not coasting)'), w)
                    if v in detail: detail[v]['n'] += 1; detail[v]['nomatch'] += 1; detail[v]['coast'] += int(coast[h, s] > 0)
                    continue
                r = row[0]; t = tk[j][r]; hh = hm[j][r][0]      # k=2 harmonic: target, actual, mask weight, phase adj, reason, evidence
                reason = int(hh[4]); stn = int(t[1])
                if hh[1] > 0:
                    d = 20 * np.log10(a2 / hh[1]) if a2 > 0 else -99
                    add('P1 track present, k=2 sounding (v15 a2 - P1 actual = %s)' % ('>+6 dB' if d > 6 else ('within +-6 dB' if d > -6 else '<-6 dB')), w)
                    if v in detail: detail[v]['dB'].append(d)
                else:
                    names = '+'.join(n for b, n in HARM_REASONS.items() if reason & b) or 'none'
                    add(f'P1 track present, k=2 NOT sounding: reason {names}, track state {stn}', w)
                    if v in detail: detail[v]['reasons'][names] = detail[v]['reasons'].get(names, 0) + 1
                if v in detail:
                    detail[v]['n'] += 1; detail[v]['st'][stn] = detail[v]['st'].get(stn, 0) + 1
                    detail[v]['life'].append(t[11]); detail[v]['fade'].append(t[7]); detail[v]['a15'].append(a2); detail[v]['ap1'].append(hh[1])
                    detail[v]['zero'] += int(hh[1] <= 0)
    P('MEASURED: share of the offending voices\' 20-150 Hz energy (all voices of the window) by what P1 has at that hop:')
    for c, w in sorted(cats.items(), key=lambda x: -x[1]):
        if w / Etot > 0.005: P(f'  {w / Etot * 100:5.1f}%  {c}')
        pool[c.split(' (')[0] if 'present, k=2 NOT' not in c else 'P1 track present, k=2 NOT sounding'] = pool.get(c, 0) + w
    P('top-5 voices (by lo energy) with their P1 counterpart: id | hops | no P1 track (of which v15 coasting) | P1 k=2 zero | P1 track states {1 birth,2 tracked,3 held,4 release,5 end} | P1 life gain med | P1 fade med | median dB(v15 a2 / P1 actual) | steps >6 dB/hop v15 vs P1 (matched sounding hops)')
    for v in top[:5]:
        D = detail[v]
        a15 = np.array(D['a15']); ap1 = np.array(D['ap1'])
        ok = ap1 > 0
        # step counts on the matched, consecutive-free arrays (approximation: successive matched hops)
        def steps(x):
            x = np.asarray(x); x = x[x > 0]
            return int((np.abs(20 * np.log10(x[1:] / x[:-1])) > 6).sum()) if len(x) > 2 else 0
        P(f'  {v:5d} | {D["n"]} | {D["nomatch"]} ({D["coast"]}) | {D["zero"]} | {D["st"]} | {np.median(D["life"]) if D["life"] else float("nan"):.2f} | {np.median(D["fade"]) if D["fade"] else float("nan"):.3f} | {np.median(D["dB"]) if D["dB"] else float("nan"):+.1f} | {steps(a15)} vs {steps(ap1)} | zero reasons {D["reasons"]}')
    # P1 own level: sub-150 vs mid and the ratio compared with v15
    plo = hop_power(band_signal(sk, 'P1', 'lo'), sy['ts']); pmid = hop_power(band_signal(sk, 'P1', 'mid'), sy['ts'])
    alo = hop_power(band_signal(sk, eng, 'lo'), sy['ts']); amid = hop_power(band_signal(sk, eng, 'mid'), sy['ts'])
    P(f'MEASURED layer (actual renders): P1 20-150 {db(plo[sl].mean()):.1f} / 150-600 {db(pmid[sl].mean()):.1f} dBFS (lo-mid {db(plo[sl].mean()) - db(pmid[sl].mean()):.1f} dB); {eng} 20-150 {db(alo[sl].mean()):.1f} / 150-600 {db(amid[sl].mean()):.1f} (lo-mid {db(alo[sl].mean()) - db(amid[sl].mean()):.1f} dB)')
    # P1 header: how many P1 tracks are sounding k=2 at all in the window and their f
    n2 = 0; tf = []
    for h in hopsel[lo:hi]:
        j = pos.get(int(h))
        if j is None: continue
        for r in range(12):
            if tk[j][r][1] > 0 and hm[j][r][0][1] > 0: n2 += 1; tf.append(tk[j][r][2])
    P(f'  P1 tracks with sounding k=2 per hop: {n2 / (hi - lo):.2f}; their f median {np.median(tf) if tf else float("nan"):.0f} Hz; v15 voices with sounding k=2 per hop: {(sy["a"][0][lo:hi] > 0).sum() / (hi - lo):.2f}')
    P('')
open(B12 / f'q2_{eng}.txt', 'w').write('\n'.join(rep)); print('\n'.join(rep))

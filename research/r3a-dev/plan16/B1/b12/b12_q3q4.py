"""Q3: what is lost if the offending voices / hops are suppressed. Q4: times separating candidate 1 and candidate 2."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
import b12_synth as S
from b12_synth import *
from b12_p1join import *
sys.path.insert(0, str(B1))
from b1_mod import mod_series
rep = []; P = rep.append
eng = 'v15'


def synth_drop(sk, t0, t1, dropfn):
    """same as synth but with a (H+1, 8) boolean drop mask applied to the amplitudes (all k) -- implemented by zeroing trace A"""
    d = load(sk, eng); tr = d['tr']
    keep = {k: tr[k] for k in ('A',)}
    hop = tr['hop'][:, 0]; ts = CA.hop_time(hop)[1]
    sel = np.where((ts >= t0) & (ts < t1))[0]
    i0 = max(sel[0] - S.HOPS_PRE, 1); i1 = sel[-1] + 1
    ix = np.arange(i0 - 1, i1)
    m = dropfn(ix, tr)
    old = tr['A'][ix].copy()
    tr['A'][ix] = np.where(m, 0.0, old)
    try:
        sy = synth(sk, eng, t0, t1)
    finally:
        tr['A'][ix] = old
    return sy


def levels(sy):
    b = band_hop_power(total(sy)); sl = slice(sy['sel_lo'], sy['sel_hi'])
    return b['lo'][sl].sum(), b['mid'][sl].sum()


for sk, t0, t1 in WINDOWS + [('app', 208.0, 212.0), ('app', 204.0, 208.0)]:
    d = load(sk, eng); tr = d['tr']
    ci, tk, hm, hd = p1_tracks(sk); ids = tid(tk); pos = {int(c): i for i, c in enumerate(ci)}
    sy0 = synth(sk, eng, t0, t1); L0, M0 = levels(sy0)
    cpw = {k: band_hop_power(x, ('lo', 'mid')) for k, x in sy0['comp'].items()}
    sl = slice(sy0['sel_lo'], sy0['sel_hi'])
    ev = {}
    for (v, k), c in cpw.items(): ev[v] = ev.get(v, 0) + c['lo'][sl].sum()
    order = sorted(ev, key=lambda v: -ev[v]); cs = np.cumsum([ev[v] for v in order]) / sum(ev.values())
    P(f'=== {sk} {t0}-{t1}: layer 20-150 {db(L0) - 5:.1f} dBFS-equivalent hop-power, 150-600 {db(M0) - 5:.1f}  (K=-5 dB applied)')

    def rule_set(frac):
        n = int(np.searchsorted(cs, frac)) + 1; S_ = set(order[:n])
        return (lambda ix, tr_: np.isin(tr_['voice'][ix], list(S_)) & (tr_['state'][ix] >= 1)), n
    for name, fn in [('R0 oracle: voices covering 80% of the lo energy, removed entirely', rule_set(.8)[0]),
                     ('R0b oracle: voices covering 50%', rule_set(.5)[0])]:
        sy = synth_drop(sk, t0, t1, fn); L, M = levels(sy)
        P(f'  {name}: n={rule_set(.8)[1] if "80%" in name else rule_set(.5)[1]} voices; 20-150 {db(L) - db(L0):+.1f} dB, 150-600 {db(M) - db(M0):+.1f} dB')

    def p1rule(mode):
        def fn(ix, tr_):
            out = np.zeros((len(ix), 8), bool)
            for r, i in enumerate(ix):
                j = pos.get(int(tr_['hop'][i, 0]))
                for s in range(8):
                    if tr_['state'][i, s] < 1: continue
                    t_ = int(tr_['track'][i, s])
                    row = np.where((ids[j] == t_) & (tk[j][:, 1] > 0))[0] if (j is not None and t_ > 0) else []
                    if len(row) == 0: out[r, s] = (mode in ('notrack', 'both'))
                    else: out[r, s] = (mode in ('mask0', 'both')) and hm[j][row[0]][0][2] <= 1e-6
            return out
        return fn
    for mode, nm in (('notrack', 'R1a: hops whose voice has no P1 track (tracker lost it, v15 coasting)'), ('mask0', 'R1b: hops where P1 holds the track but k=2 mask is 0'), ('both', 'R1: R1a+R1b (mirror P1 permission)')):
        sy = synth_drop(sk, t0, t1, p1rule(mode)); L, M = levels(sy)
        P(f'  {nm}: 20-150 {db(L) - db(L0):+.1f} dB, 150-600 {db(M) - db(M0):+.1f} dB')
    P('')
# P1 reference for the same windows
for sk, t0, t1 in WINDOWS:
    sy = synth(sk, eng, t0, t1); sl = slice(sy['sel_lo'], sy['sel_hi'])
    plo = hop_power(band_signal(sk, 'P1', 'lo'), sy['ts'])[sl].mean(); pm = hop_power(band_signal(sk, 'P1', 'mid'), sy['ts'])[sl].mean()
    a_lo = hop_power(band_signal(sk, eng, 'lo'), sy['ts'])[sl].mean(); a_m = hop_power(band_signal(sk, eng, 'mid'), sy['ts'])[sl].mean()
    P(f'reference {sk} {t0}: P1 vs v15 actual: 20-150 {db(plo) - db(a_lo):+.1f} dB, 150-600 {db(pm) - db(a_m):+.1f} dB')

# ---------------- Q4
P('')
P('=== Q4: candidate 1 (registered 150-600 Hz pulse excess M, v15-P1) vs candidate 2 (20-150 Hz layer, v15 level / v15-P1), 2 s windows hop 0.5 s')
mmf = lambda t: f'{int(t // 60)}:{t % 60:04.1f}'
for sk, ci_ in (('app', 9), ('rem', 6)):
    C = B1 / 'cache'
    env = {e: np.load(C / f's{ci_:02d}_{e}.npz')['env'] for e in ('P1', 'v15')}
    Ms = {e: mod_series(env[e]) for e in env}
    n = min(len(Ms['P1'][1]), len(Ms['v15'][1]))
    t = Ms['v15'][0][:n]
    dM = Ms['v15'][1][:n] - Ms['P1'][1][:n]
    lo = {}
    for e in ('P1', 'v15'):
        sig = band_signal(sk, e, 'lo')
        lo[e] = np.array([db(np.mean(sig[int(tt * FS):int((tt + 2) * FS)] ** 2)) for tt in t])
    Dlo = lo['v15'] - lo['P1']
    ok = Ms['v15'][3][:n] > -70
    c2 = np.where(ok, lo['v15'], -999)
    P(f'-- {sk}: windows {n}; cand-2 measure = v15 20-150 level (dBFS) and v15-P1 (dB); cand-1 measure = M(v15)-M(P1) (dB-rms) and M(v15)')
    # cand 2 strongest, cand 1 absent: M(v15) - M(P1) <= 0 and M(v15) < 2
    m2 = ok & (dM <= 0) & (Ms['v15'][1][:n] < 2.0)
    idx2 = [i for i in np.argsort(-lo['v15']) if m2[i]]
    chosen = []
    for i in idx2:
        if all(abs(t[i] - t[j]) >= 4 for j in chosen): chosen.append(i)
        if len(chosen) == 4: break
    P('   cand 2 strong, cand 1 absent (start mm:ss | v15 lo dBFS | v15-P1 lo | M v15 | M P1): ' + '; '.join(f'{mmf(t[i])} | {lo["v15"][i]:.0f} | {Dlo[i]:+.0f} | {Ms["v15"][1][i]:.1f} | {Ms["P1"][1][i]:.1f}' for i in chosen))
    m1 = ok & (Dlo < 4)
    idx1 = [i for i in np.argsort(-dM) if m1[i]]
    chosen = []
    for i in idx1:
        if all(abs(t[i] - t[j]) >= 4 for j in chosen): chosen.append(i)
        if len(chosen) == 4: break
    P('   cand 1 strong, cand 2 absent (start | M v15 | M P1 | v15-P1 lo | v15 lo): ' + '; '.join(f'{mmf(t[i])} | {Ms["v15"][1][i]:.1f} | {Ms["P1"][1][i]:.1f} | {Dlo[i]:+.0f} | {lo["v15"][i]:.0f}' for i in chosen))
    j = np.argmin(np.abs(t - 209.5)) if sk == 'app' else None
    if j is not None: P(f'   reference 3:29.5: M v15 {Ms["v15"][1][j]:.1f} / P1 {Ms["P1"][1][j]:.1f}; v15 lo {lo["v15"][j]:.0f}, v15-P1 lo {Dlo[j]:+.0f}')
    P(f'   correlation across windows between cand-1 excess dM and cand-2 level: {np.corrcoef(dM[ok], lo["v15"][ok])[0, 1]:.2f}; between dM and v15-P1 lo: {np.corrcoef(dM[ok], Dlo[ok])[0, 1]:.2f}')
open(B12 / 'q3q4.txt', 'w').write('\n'.join(rep)); print('\n'.join(rep))

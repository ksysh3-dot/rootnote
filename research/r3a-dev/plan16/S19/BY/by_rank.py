"""S19-BY item 1: ranking of 2 s windows and comparison with the 14 vanila songs. numbers only. usage: by_rank.py SONG[,SONG] -> stdout (tee to ranks.txt)"""
import sys
import numpy as np
from pathlib import Path
R = Path('/home/ksysh/r3a-dev/plan16/S19/BY/res')
db = lambda p: 10 * np.log10(np.maximum(p, 1e-30))
ELIG_DB = -70.0   # input mean-square (dBFS) for a window to count as non-silent


def ld(row, s):
    return np.load(R / f'{row}_{s}.npz')


def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def derived(s):
    i, p, c = ld('inp', s), ld('p1', s), ld('hp8_150c1', s)
    nw = min(len(i['p140']), len(p['p140']), len(c['p140']))
    g = lambda z, k: z[k][:nw]
    D = dict(
        c_abs=db(g(c, 'p140')), p_abs=db(g(p, 'p140')), in_abs=db(g(i, 'p150')),
        exc=db(g(c, 'p140')) - db(g(p, 'p140')),
        c_r=db(g(c, 'p140')) - db(g(c, 'p600')), p_r=db(g(p, 'p140')) - db(g(p, 'p600')),
        c_260=db(g(c, 'p260')) - db(g(c, 'p600')), p_260=db(g(p, 'p260')) - db(g(p, 'p600')),
        c_b=g(c, 'burst2'), p_b=g(p, 'burst2'),
        c_Mx=g(c, 'M') - g(i, 'M'), p_Mx=g(p, 'M') - g(i, 'M'),
        inrms=db(g(i, 'rms')), t0=np.arange(nw) * 0.5)
    D['ok'] = (D['inrms'] > ELIG_DB) & np.isfinite(D['c_Mx'])
    return D


def pick(D, key, k=8):
    sc = np.where(D['ok'], D[key], -np.inf); out = []
    for j in np.argsort(-sc):
        if not np.isfinite(sc[j]):
            break
        if all(abs(D['t0'][j] - D['t0'][q]) >= 2.0 for q in out):
            out.append(j)
        if len(out) == k:
            break
    return out


def show(s, D):
    print(f'\n=== {s}: {D["ok"].sum()} eligible windows of {len(D["ok"])} (input ms > {ELIG_DB} dBFS) ===')
    for key, nm in (('c_abs', 'v1.6-c 20-140 Hz absolute'), ('exc', 'excess over P1 (c - P1, 20-140 abs)')):
        print(f'-- top 8 non-overlapping windows by {nm}')
        print('rank | t0 (m:ss) | c abs dBFS | P1 abs | exc dB | in 20-150 dBFS | c 20-140/150-600 | P1 same | c 150-260 re600 | P1 same | c burst>2x % | P1 | c pulse excess dB | P1')
        for r, j in enumerate(pick(D, key), 1):
            print(f'{r} | {mmss(D["t0"][j])} | {D["c_abs"][j]:.1f} | {D["p_abs"][j]:.1f} | {D["exc"][j]:+.1f} | {D["in_abs"][j]:.1f} | {D["c_r"][j]:.1f} | {D["p_r"][j]:.1f} | {D["c_260"][j]:.1f} | {D["p_260"][j]:.1f} | {100*D["c_b"][j]:.0f} | {100*D["p_b"][j]:.0f} | {D["c_Mx"][j]:+.2f} | {D["p_Mx"][j]:+.2f}')


if __name__ == '__main__':
    songs = sys.argv[1].split(',')
    V = {f'v{i:02d}': derived(f'v{i:02d}') for i in range(14)}
    keys = [('c_abs', 'v1.6-c 20-140 abs dBFS'), ('exc', 'c - P1 excess dB'), ('c_r', 'c 20-140/150-600 dB'), ('c_260', 'c 150-260 re 150-600'),
            ('c_b', 'c burst>2x share'), ('c_Mx', 'c pulse excess 20-150 dB')]
    pool = {k: np.concatenate([v[k][v['ok']] for v in V.values()]) for k, _ in keys}
    print('vanila pool: windows', len(pool['c_abs']), 'songs 14')
    print('metric | vanila p50 | p90 | p99 | max | per-song p90 range (min..max) | per-song max range')
    for k, nm in keys:
        a = pool[k]; ps90 = [np.percentile(v[k][v['ok']], 90) for v in V.values()]; psmx = [v[k][v['ok']].max() for v in V.values()]
        print(f'{nm} | {np.percentile(a,50):.2f} | {np.percentile(a,90):.2f} | {np.percentile(a,99):.2f} | {a.max():.2f} | {min(ps90):.2f}..{max(ps90):.2f} | {min(psmx):.2f}..{max(psmx):.2f}')
    for s in songs:
        D = derived(s); show(s, D)
        print(f'-- {s} distribution vs vanila pool (own p50 / p90 / p99 / max ; percent of vanila windows below own p90 / own max)')
        for k, nm in keys:
            a = D[k][D['ok']]; pa = pool[k]
            print(f'{nm} | {np.percentile(a,50):.2f} | {np.percentile(a,90):.2f} | {np.percentile(a,99):.2f} | {a.max():.2f} | {100*np.mean(pa<np.percentile(a,90)):.1f}% | {100*np.mean(pa<a.max()):.1f}%')

"""S19-LIM aggregation -> tables.txt, results.json. Definitions: CHOICES.md"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/LIM')
sys.dont_write_bytecode = True
import numpy as np
from pathlib import Path
import lim_lib as Z

RES = Path('/home/ksysh/r3a-dev/plan16/S19/LIM/res')
ROWS = ['p1', 'v15', 'v16b', 'v16c']
HELD = [i for i in range(14) if i not in (6, 9)]
_cache = {}


def load(row, i):
    k = (row, i)
    if k not in _cache:
        f = RES / f'{row}_s{i:02d}.npz'
        _cache[k] = dict(np.load(f)) if f.exists() else None
    return _cache[k]


def song_of(sn):
    return 9 if sn.startswith('A') else 6


def lagpairs(a, b, lag):
    """a: layer, b: GR; positive lag = GR later"""
    n = len(a)
    if lag >= 0:
        return a[:n - lag], b[lag:]
    return a[-lag:], b[:n + lag]


def corr(items, lag):
    xs = []; ys = []
    for a, b in items:
        if len(a) <= abs(lag) + 2:
            continue
        x, y = lagpairs(a, b, lag); xs.append(x); ys.append(y)
    if not xs:
        return np.nan
    x = np.concatenate(xs); y = np.concatenate(ys)
    if x.std() < 1e-9 or y.std() < 1e-9:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def best(items):
    rs = [(corr(items, l), l) for l in range(-10, 11)]
    rs = [(r, l) for r, l in rs if np.isfinite(r)]
    if not rs:
        return np.nan, 0
    r, l = max(rs, key=lambda t: abs(t[0]))
    return r, l


def dil(b, n=4):
    out = b.copy()
    for s in range(1, n + 1):
        out[s:] |= b[:-s]
    return out


def metrics(row, cond, segs):
    """segs: list of (song, sn). pooled metrics of condition cond (s6/s0/off) with the same row's off."""
    G = lambda i, sn, c, k: load(row, i)[f'{sn}|{c}|{k}']
    gr = np.concatenate([G(i, sn, cond, 'gr') for i, sn in segs]).astype(np.float64)
    grf = np.concatenate([G(i, sn, cond, 'grf') for i, sn in segs]).astype(np.float64)
    bp = np.concatenate([G(i, sn, cond, 'grbp') for i, sn in segs]); fbp = np.concatenate([G(i, sn, cond, 'grfbp') for i, sn in segs])
    sc = np.array([G(i, sn, cond, 'scal') for i, sn in segs]); so = np.array([G(i, sn, 'off', 'scal') for i, sn in segs])
    m = dict(g1=100 * (gr > 1).mean(), g3=100 * (gr > 3).mean(), gmean=gr.mean(), gmax=gr.max(), p99=np.percentile(gr, 99),
             f1=100 * (grf > 1).mean(), f3=100 * (grf > 3).mean(), pump=float(np.sqrt(np.mean(bp ** 2))), pumpf=float(np.sqrt(np.mean(fbp ** 2))),
             peak=sc[:, 0].max(), med200=sc[:, 1].mean(), M=sc[:, 2].mean(), d_peak=sc[:, 0].max() - so[:, 0].max(), d_med=sc[:, 1].mean() - so[:, 1].mean(), d_M=sc[:, 2].mean() - so[:, 2].mean())
    if cond == 'off':
        return m
    items = [(G(i, sn, cond, 'lo').astype(np.float64), G(i, sn, cond, 'gr').astype(np.float64)) for i, sn in segs]
    items_d = [(G(i, sn, cond, 'lo').astype(np.float64), G(i, sn, cond, 'gr').astype(np.float64) - G(i, sn, 'off', 'gr').astype(np.float64)) for i, sn in segs]
    m['r0'] = corr(items, 0); m['rb'], m['lagb'] = best(items)
    m['rd0'] = corr(items_d, 0); m['rdb'], m['lagdb'] = best(items_d)
    ab = np.concatenate([dil(G(i, sn, cond, 'burst').astype(bool)) for i, sn in segs])
    hit = gr > 1
    m['p_ab'] = 100 * hit[ab].mean() if ab.any() else np.nan
    m['p_nab'] = 100 * hit[~ab].mean() if (~ab).any() else np.nan
    m['share_ab'] = 100 * ab[hit].mean() if hit.any() else np.nan
    m['base_ab'] = 100 * ab.mean()
    lpk = np.concatenate([G(i, sn, cond, 'lpk') for i, sn in segs]).astype(np.float64); ppk = np.concatenate([G(i, sn, cond, 'ppk') for i, sn in segs]).astype(np.float64)
    gro = np.concatenate([G(i, sn, 'off', 'gr') for i, sn in segs]).astype(np.float64)
    m['lpk_pct'] = float(np.median(100 * lpk[hit] / np.maximum(ppk[hit], 1e-12))) if hit.any() else np.nan
    m['caused'] = 100 * ((gro[hit] < 0.25).mean()) if hit.any() else np.nan
    m['n_hit'] = int(hit.sum()); m['n'] = len(gr)
    return m


def groups():
    ws = list(zip(Z.WNAME, [9] * 5 + [6] * 2))
    W = [(i, sn) for sn, i in ws]
    g = {'U7': W, 'A-late': [w for w in W if w[1] in ('A3:21', 'A3:23')], 'others': [w for w in W if w[1] not in ('A3:21', 'A3:23')]}
    for sn, i in ws:
        g[sn] = [(i, sn)]
    return g


def held(row, cond):
    vals = []
    for i in HELD:
        if load(row, i) is None:
            continue
        vals.append(metrics(row, cond, [(i, 'EXC')]))
    out = {}
    for k in vals[0]:
        a = np.array([v[k] for v in vals], float)
        out[k] = float(np.nanmedian(a)) if np.isfinite(a).any() else np.nan
        out[k + '_n'] = int(np.isfinite(a).sum())
    out['g1_min'] = float(min(v['g1'] for v in vals)); out['g1_max'] = float(max(v['g1'] for v in vals))
    out['g1_per'] = [round(v['g1'], 2) for v in vals]
    return out


def fmt(x, d=2):
    return 'NA' if x is None or (isinstance(x, float) and not np.isfinite(x)) else f'{x:.{d}f}'


def main():
    G = groups(); R = {}
    for row in ROWS:
        for cond in ('off', 's6', 's0'):
            for gn, segs in G.items():
                R[f'{row}|{cond}|{gn}'] = metrics(row, cond, segs)
            R[f'{row}|{cond}|held'] = held(row, cond)
    json.dump(R, open('/home/ksysh/r3a-dev/plan16/S19/LIM/results.json', 'w'), indent=1, default=float)
    L = []
    P = L.append
    names = Z.ROWNAME
    for cond, sname in (('s6', '+6 dB'), ('s0', '0 dB')):
        for gn in ('U7', 'A-late', 'others', 'held'):
            P(f'\n=== {sname} | group {gn}  (held = median over 12 songs, 30 s) ===')
            P('row      | GR>1dB% GR>3dB% | fine>1 fine>3 | GRmean GRp99 GRmax | pump(meter) pump(fine) | out20-400 peak dBFS (d vs off) | med200 (d) | M 2-12Hz (d)')
            for row in ['off'] + ROWS:
                if row == 'off':
                    m = R[f'p1|off|{gn}']; nm = 'off(P1)'
                else:
                    m = R[f'{row}|{cond}|{gn}']; nm = names[row]
                P(f'{nm:8s} | {fmt(m["g1"]):>7} {fmt(m["g3"]):>7} | {fmt(m["f1"]):>6} {fmt(m["f3"]):>6} | {fmt(m["gmean"]):>6} {fmt(m["p99"]):>6} {fmt(m["gmax"]):>6} | {fmt(m["pump"],3):>8} {fmt(m["pumpf"],3):>8} | {fmt(m["peak"]):>6} ({fmt(m["d_peak"]):>5}) | {fmt(m["med200"]):>6} ({fmt(m["d_med"]):>5}) | {fmt(m["M"],3):>6} ({fmt(m["d_M"],3):>6})')
            P('-- correlation with the layer 20-150 Hz (GR_meter; lag in blocks of 5.33 ms, + = GR later)')
            P('row      | r0     rbest(lag)   | r0(dGR) rbest(lag) | P(GR>1|burst+0..4)% P(GR>1|else)% share of GR>1 after burst% (base burst%) | layerpk/prepk % @GR>1 | layer-caused% | nGR>1/n')
            for row in ROWS:
                m = R[f'{row}|{cond}|{gn}']
                P(f'{names[row]:8s} | {fmt(m["r0"]):>6} {fmt(m["rb"]):>6}({int(m["lagb"]):+d}) | {fmt(m["rd0"]):>6} {fmt(m["rdb"]):>6}({int(m["lagdb"]):+d}) | {fmt(m["p_ab"]):>7} {fmt(m["p_nab"]):>7} {fmt(m["share_ab"]):>7} ({fmt(m["base_ab"])}) | {fmt(m["lpk_pct"],1):>6} | {fmt(m["caused"],1):>6} | {m["n_hit"]}/{m["n"]}' if gn != 'held' else
                  f'{names[row]:8s} | r0 {fmt(m["r0"])} rb {fmt(m["rb"])} | rd0 {fmt(m["rd0"])} rdb {fmt(m["rdb"])} | {fmt(m["p_ab"])} {fmt(m["p_nab"])} {fmt(m["share_ab"])} ({fmt(m["base_ab"])}) | {fmt(m["lpk_pct"],1)} | {fmt(m["caused"],1)} | valid songs {m["r0_n"]}')
    P('\n=== per window, +6 dB (GR>1dB% | GRmean dB | pump rms dB | d_peak dB | d_M dB | r0 | layerpk/prepk% | caused%) ===')
    for gn in Z.WNAME:
        P(f'-- {gn}')
        for row in ROWS:
            m = R[f'{row}|s6|{gn}']; o = R[f'{row}|off|{gn}']
            P(f'  {names[row]:7s} GR>1 {fmt(m["g1"]):>6}  GR>3 {fmt(m["g3"]):>6}  mean {fmt(m["gmean"]):>5} max {fmt(m["gmax"]):>5}  pump {fmt(m["pump"],3):>6} (off {fmt(o["pump"],3)})  d_peak {fmt(m["d_peak"]):>6}  d_M {fmt(m["d_M"],3):>6}  r0 {fmt(m["r0"]):>6}  rb {fmt(m["rb"]):>6}({int(m["lagb"]):+d})  lpk% {fmt(m["lpk_pct"],1):>5}  caused {fmt(m["caused"],0):>4}')
    P('\n=== held-out per-song GR>1 dB% (+6 dB), sorted song index (12) ===')
    for row in ROWS:
        P(f'{names[row]:7s} {R[f"{row}|s6|held"]["g1_per"]}  (off: {R[f"{row}|off|held"]["g1_per"]})')
    open('/home/ksysh/r3a-dev/plan16/S19/LIM/tables.txt', 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()

"""LOGOFF 4.12 s / 4.73 s R1 burst (13.5 A1; gate16/e7_v7d.py mode R1) for P1 and the 18.3 rows (same recipe as plan16/F/f_burst.py).
Excerpt = LOGOFF 37..49 s, hits at render time 3.0 + hit, out_db -5, layer = out(0 dB) - out(-120 dB), 0.3 s zeros appended. usage: burst16.py [rho:creep ...]"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A'); sys.path.insert(0, '/home/ksysh/r3a-dev/gate16')
import numpy as np
import vcommon as VC
import research_core_metrics as M
import research_core_signals as S
import e7_v7d as E7

FS = 48000
lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
x2 = np.concatenate([np.stack([lg, lg], 1) if lg.ndim == 1 else lg, np.zeros((int(.3 * FS), 2))], 0).astype(np.float32)
lib = VC.load(str(VC.LIB16B))


def layer_core(par):
    rs = []
    for lv in (0.0, -120.0):
        y, _, lat = VC.render(lib, x2, VC.make_params(par[0], par[1], par[2]), trace=False, vb_level_db=lv, out_db=-5.0)
        rs.append(dict(y=y, lat=lat))
    return M.layer_of(rs[0], rs[1])


rows = {}
ctx = M.Ctx(str(M.REF_LIB), 6, None)
rows['P1'] = M.layer_of(ctx.render('lg', lg, 0.0), ctx.render('lg', lg, -120.0))
ROWS = {'v1.5': (0, 0, 0), 'v1.6-a base (A2 1.5)': (1.5, 0, 0), 'A1 8/1.5 (uncond)': (1.5, 8, 0), 'A1p (i) 8': (1.5, 8, 1), 'A1p (i) 16': (1.5, 16, 1),
        'A1p (ii) 8': (1.5, 8, 2), 'A1p (ii) 16': (1.5, 16, 2)}
for k, par in ROWS.items():
    rows[k] = layer_core(par)
out = {}
for k, lay in rows.items():
    for hit in (4.12, 4.73):
        old, new, ref = E7.burst(lay, 3.0 + hit, 'R1')
        out[f'{k}|{hit}'] = dict(burst_R1=new, energy100_db=old, ref_box_db=ref)
json.dump(out, open(VC.V_DIR / 'burst16b.json', 'w'), indent=1)
p1 = {h: out[f'P1|{h}']['burst_R1'] for h in (4.12, 4.73)}
print(f'{"row":16s} {"4.12 burst":>11s} {"4.73 burst":>11s}   (4.73 limit max(3, P1+1) = {max(3, p1[4.73] + 1):.2f})')
for k in rows:
    print(f'{k:16s} {out[k + "|4.12"]["burst_R1"]:11.2f} {out[k + "|4.73"]["burst_R1"]:11.2f}')

"""PRIMARY: LOGOFF 4.12 s / 4.73 s R1 burst (13.5 A1; same code as gate16/e7_v7d.py, mode R1) for P1, v1.5 and rho 1.5/2/3.
Excerpt = LOGOFF 37..49 s, hits at render time 3.0 + hit, out_db -5, layer = out(0 dB) - out(-120 dB), 0.3 s of zeros appended (as M.Ctx.render)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F'); sys.path.insert(0, '/home/ksysh/r3a-dev/gate16')
import numpy as np
import fcommon as FC
import research_core_metrics as M
import research_core_signals as S
import e7_v7d as E7

FS = 48000
lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
x2 = np.concatenate([np.stack([lg, lg], 1) if lg.ndim == 1 else lg, np.zeros((int(.3 * FS), 2))], 0).astype(np.float32)


def layer_core(lib, pvec):
    rs = []
    for lv in (0.0, -120.0):
        y, _, lat = FC.render(lib, x2, pvec, trace=False, vb_level_db=lv, out_db=-5.0)
        rs.append(dict(y=y, lat=lat))
    return M.layer_of(rs[0], rs[1])


def layer_p1():
    ctx = M.Ctx(str(M.REF_LIB), 6, None)
    r0 = ctx.render('lg', lg, 0.0); rd = ctx.render('lg', lg, -120.0)
    return M.layer_of(r0, rd)


rows = {}
rows['P1'] = layer_p1()
l15 = FC.load(str(FC.LIB15)); l151 = FC.load(str(FC.LIB151))
rows['v1.5'] = layer_core(l15, FC.make_params(None))
rows['v1.5 (new lib, cap 0)'] = layer_core(l151, FC.make_params(0.0))
for rho in (1.5, 2.0, 3.0):
    FC.cap_stats(l151)
    rows[f'rho {rho}'] = layer_core(l151, FC.make_params(rho))
out = {}
for k, lay in rows.items():
    for hit in (4.12, 4.73):
        old, new, ref = E7.burst(lay, 3.0 + hit, 'R1')
        out[f'{k}|{hit}'] = dict(burst_R1=new, energy100_db=old, ref_box_db=ref)
json.dump(out, open(FC.F_DIR / 'f_burst.json', 'w'), indent=1)
p1 = {h: out[f'P1|{h}']['burst_R1'] for h in (4.12, 4.73)}
print(f'{"row":26s} {"4.12 burst":>11s} {"4.73 burst":>11s}   (P1 limit 4.73: max(3, P1+1) = {max(3, p1[4.73] + 1):.2f})')
for k in rows:
    print(f'{k:26s} {out[k + "|4.12"]["burst_R1"]:11.2f} {out[k + "|4.73"]["burst_R1"]:11.2f}')

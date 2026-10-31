"""LOGOFF 4.12 s / 4.73 s R1 burst for P1 and the A5 rows (copy of plan16/V16A/burst16b.py with the 21-value vector). 18.9 guard: 4.73 s R1 <= max(3, P1 + 1)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5'); sys.path.insert(0, '/home/ksysh/r3a-dev/gate16')
import numpy as np
import a5common as VC
import a5rows as AR
import research_core_metrics as M
import research_core_signals as S
import e7_v7d as E7

FS = 48000
lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
x2 = np.concatenate([np.stack([lg, lg], 1) if lg.ndim == 1 else lg, np.zeros((int(.3 * FS), 2))], 0).astype(np.float32)
lib = VC.load(str(VC.LIB16C))


def vec(prm):
    return VC.make_params5(prm.get('capRho', 0), prm.get('windowCreep', 0), prm.get('creepMode', 0), prm.get('ampSlewDb', 0), prm.get('slewOnsetMode', 0))


def layer_core(prm):
    rs = []
    for lv in (0.0, -120.0):
        y, _, lat = VC.render(lib, x2, vec(prm), trace=False, vb_level_db=lv, out_db=-5.0)
        rs.append(dict(y=y, lat=lat))
    return M.layer_of(rs[0], rs[1])


rows = {}
ctx = M.Ctx(str(M.REF_LIB), 6, None)
rows['p1'] = M.layer_of(ctx.render('lg', lg, 0.0), ctx.render('lg', lg, -120.0))
for k in ['v15', 'base'] + AR.A5LABELS:
    rows[k] = layer_core(AR.ROWS[k][2])
out = {}
for k, lay in rows.items():
    for hit in (4.12, 4.73):
        old, new, ref = E7.burst(lay, 3.0 + hit, 'R1')
        out[f'{k}|{hit}'] = dict(burst_R1=new, energy100_db=old, ref_box_db=ref)
json.dump(out, open(VC.A5_DIR / 'burst_a5.json', 'w'), indent=1)
p1 = {h: out[f'p1|{h}']['burst_R1'] for h in (4.12, 4.73)}
print(f'{"row":8s} {"4.12 burst":>11s} {"4.73 burst":>11s}   (4.73 limit max(3, P1+1) = {max(3, p1[4.73] + 1):.2f})')
for k in rows:
    print(f'{k:8s} {out[k + "|4.12"]["burst_R1"]:11.2f} {out[k + "|4.73"]["burst_R1"]:11.2f}')

"""V0 for A1' (creepMode, param 19). Two halves:
 A. 16b with capRho = windowCreep = 0 (sent as 16 / 17 / 18 / 19 values, creepMode 0, and creepMode 1/2 with windowCreep = 0) is bit identical to v1.5 (output + 22-field trace).
 B. 16b with creepMode = 0 (or the value omitted) is bit identical to the 084ea45 build (16a) for (capRho, windowCreep) = (0, 8), (1.5, 8), (1.5, 16) = the 18.3 behaviour is kept
    (this is also the basis for reusing the already measured v1.5 / A2 / A1 8 rows of plan16/V16A).
 C. creepMode 1 / 2 with windowCreep > 0 change the output (the parameter does something); the library refuses creepMode outside {0, 1, 2}."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S
import test_engine as T

l15 = VC.load(str(VC.LIB15)); l16a = VC.load(str(VC.LIB16A)); l16b = VC.load(str(VC.LIB16B))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
sg = S.gated_line(25.0)
sigs['gated25_pink'] = S.stereo(sg['noisy'])[:int(8 * 48000)]
sigs['low_notes'] = S.stereo(S.low_notes())
rows = []
okA = okB = True
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(2.5 * 48000)] if blk == 1 else x
        y0, t0, _ = VC.render(l15, xx, VC.make_params(), block=blk)
        for tag, pv in (('16vals', VC.make_params()), ('17vals_cap0', VC.make_params(0.0)), ('18vals_0_0', VC.make_params(0.0, 0.0)),
                        ('19vals_0_0_0', VC.make_params(0.0, 0.0, 0.0)), ('19vals_0_0_m1', VC.make_params(0.0, 0.0, 1.0)), ('19vals_0_0_m2', VC.make_params(0.0, 0.0, 2.0))):
            y1, t1, _ = VC.render(l16b, xx, pv, block=blk)
            same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
            okA &= same
            rows.append(('A', nm, blk, tag, bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1)))))
            print(rows[-1], flush=True)
        if blk == 256:
            for tag, rho, cr in (('A1 8', 0.0, 8.0), ('A2 1.5', 1.5, 0.0), ('A1+A2 8/1.5', 1.5, 8.0), ('A1+A2 16/1.5', 1.5, 16.0)):
                ya, ta, _ = VC.render(l16a, xx, VC.make_params(rho, cr), block=blk)
                for tag2, pv in (('18vals', VC.make_params(rho, cr)), ('19vals_m0', VC.make_params(rho, cr, 0.0))):
                    yb, tb, _ = VC.render(l16b, xx, pv, block=blk)
                    same = np.array_equal(ya, yb) and np.array_equal(ta, tb)
                    okB &= same
                    rows.append(('B', nm, blk, f'{tag} {tag2}', bool(same), float(np.max(np.abs(ya - yb))), float(np.max(np.abs(ta - tb)))))
                    print(rows[-1], flush=True)
                for m in (1.0, 2.0):
                    yb, tb, _ = VC.render(l16b, xx, VC.make_params(rho, cr, m), block=blk)
                    print('C', nm, tag, 'mode', m, 'max|dy| vs mode 0', float(np.max(np.abs(ya - yb))), 'trace differs', not np.array_equal(ta, tb), flush=True)
eng = T.Engine(l16b, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
for bad in (-1.0, 0.5, 1.5, 3.0, float('nan')):
    v = VC.make_params(0.0, 8.0, bad)
    print('creepMode', bad, '->', l16b.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
for good in (0.0, 1.0, 2.0):
    v = VC.make_params(0.0, 8.0, good)
    print('creepMode', good, '->', l16b.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
eng.close()
print('V0 A (params at 0 = v1.5) ALL BIT-IDENTICAL:', okA)
print('V0 B (creepMode 0 = 084ea45) ALL BIT-IDENTICAL:', okB)
json.dump(rows, open(VC.V_DIR / 'v0_check16b.json', 'w'))

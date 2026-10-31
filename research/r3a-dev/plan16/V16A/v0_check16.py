"""V0 for v1.6-a: with capRho = 0 and windowCreep = 0 (sent as 16, 17 or 18 values) the output and the 22-field voice trace are bit identical to v1.5
(HEAD build). Also: A1 / A2 alone and together change the output (the parameters do something); the library refuses windowCreep outside 0 / [1,320]."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S
import test_engine as T

l15 = VC.load(str(VC.LIB15)); l16 = VC.load(str(VC.LIB16A))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
sg = S.gated_line(25.0)
sigs['gated25_pink'] = S.stereo(sg['noisy'])[:int(8 * 48000)]
rows = []
ok_all = True
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(2.5 * 48000)] if blk == 1 else x
        y0, t0, _ = VC.render(l15, xx, VC.make_params(), block=blk)
        for tag, pv in (('16vals', VC.make_params()), ('17vals_cap0', VC.make_params(0.0)), ('18vals_0_0', VC.make_params(0.0, 0.0))):
            y1, t1, _ = VC.render(l16, xx, pv, block=blk)
            same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
            ok_all &= same
            rows.append((nm, blk, tag, bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1)))))
            print(rows[-1], flush=True)
        if blk == 256:
            for tag, rho, cr in (('A1 16', 0.0, 16.0), ('A2 1.5', 1.5, 0.0), ('A1+A2 16/1.5', 1.5, 16.0)):
                VC.cap_stats(l16)
                y1, t1, _ = VC.render(l16, xx, VC.make_params(rho, cr), block=blk)
                print(nm, tag, 'max|dy|', float(np.max(np.abs(y0 - y1))), 'trace differs', not np.array_equal(t0, t1), 'cap stats', VC.cap_stats(l16), flush=True)
eng = T.Engine(l16, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
for bad in (-1.0, 0.5, 321.0, 1000.0, float('nan')):
    v = VC.make_params(0.0, bad)
    print('windowCreep', bad, '->', l16.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
for good in (0.0, 1.0, 8.0, 16.0, 32.0, 320.0):
    v = VC.make_params(0.0, good)
    print('windowCreep', good, '->', l16.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
for bad in (0.5, 10.5):
    v = VC.make_params(bad, 0.0)
    print('capRho', bad, '->', l16.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
v = VC.make_params(0.0, 0.0)
print('16 values accepted by new lib:', l16.pvb_set_resultant(eng.h, VC.make_params().ctypes.data_as(VC.CA.DP), 16))
eng.close()
print('V0 ALL BIT-IDENTICAL:', ok_all)
json.dump(rows, open(VC.V_DIR / 'v0_check16.json', 'w'))

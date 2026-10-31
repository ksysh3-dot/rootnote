"""V0 for v1.5.1: with capRho = 0 (sent as 17th value, or not sent) the output and the voice trace are bit identical to v1.5 (HEAD build).
Also: capRho = 1.5 / 2 / 3 differ from v1.5 (the parameter does something), and the library refuses capRho in (0,1) and > 10."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F')
import numpy as np
import fcommon as FC
import research_core_signals as S
import research_core_metrics as M

l15 = FC.load(str(FC.LIB15)); l151 = FC.load(str(FC.LIB151))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
rows = []
ok_all = True
for nm, x in sigs.items():
    for blk in (256, 1, 480) if nm == 'T20_0_8' else (256,):
        xx = x[:int(2.5 * 48000)] if blk == 1 else x
        y0, t0, _ = FC.render(l15, xx, FC.make_params(None), block=blk)
        for tag, pv in (('151_16vals', FC.make_params(None)), ('151_cap0', FC.make_params(0.0))):
            y1, t1, _ = FC.render(l151, xx, pv, block=blk)
            same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
            ok_all &= same
            rows.append((nm, blk, tag, bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1)))))
            print(rows[-1], flush=True)
        if blk == 256:
            for rho in (1.5, 2.0, 3.0):
                FC.cap_stats(l151)
                y1, t1, _ = FC.render(l151, xx, FC.make_params(rho), block=blk)
                st = FC.cap_stats(l151)
                d = float(np.max(np.abs(y0 - y1)))
                print(nm, 'rho', rho, 'max|dy|', d, 'cap stats (evaluated, acted)', st, flush=True)
# refusal of out-of-range values
e = None
import test_engine as T
eng = T.Engine(l151, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
for bad in (0.5, 0.99, 10.5, -1.0, float('nan')):
    v = FC.make_params(bad)
    r = l151.pvb_set_resultant(eng.h, v.ctypes.data_as(FC.CA.DP), len(v))
    print('capRho', bad, '->', r)
for good in (0.0, 1.0, 1.5, 10.0):
    v = FC.make_params(good)
    r = l151.pvb_set_resultant(eng.h, v.ctypes.data_as(FC.CA.DP), len(v))
    print('capRho', good, '->', r)
eng.close()
print('V0 ALL BIT-IDENTICAL:', ok_all)
json.dump(rows, open(FC.F_DIR / 'v0_check.json', 'w'))

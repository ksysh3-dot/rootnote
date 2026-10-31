"""V0 for A5 (params 20 ampSlewDb, 21 slewOnsetMode).
 A. 16c with ampSlewDb = 0 (any slewOnsetMode) is bit identical to the 16b build (5c1c62c) for (capRho, windowCreep, creepMode) = (0,0,0), (1.5,16,2), (1.5,8,0),
    and with (0,0,0) to v1.5 (output + 22-field trace); the 19-value call and the 21-value call agree.
 B. ampSlewDb > 0 changes the output; the library refuses ampSlewDb outside {0} U [0.1, 40] and slewOnsetMode outside {0,1,2}."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import numpy as np
import a5common as AC
import research_core_signals as S
import test_engine as T

VC = AC
l15 = VC.load(str(VC.LIB15)); l16b = VC.load(str(VC.LIB16B)); l16c = VC.load(str(VC.LIB16C))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
sg = S.gated_line(25.0)
sigs['gated25_pink'] = S.stereo(sg['noisy'])[:int(8 * 48000)]
sigs['low_notes'] = S.stereo(S.low_notes())
rows = []; okA = True
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(2.5 * 48000)] if blk == 1 else x
        y0, t0, _ = VC.render(l15, xx, VC.make_params(), block=blk)
        for tag, pv in (('21vals_0', VC.make_params5()), ('21vals_0_onset1', VC.make_params5(0, 0, 0, 0, 1)), ('21vals_0_onset2', VC.make_params5(0, 0, 0, 0, 2))):
            y1, t1, _ = VC.render(l16c, xx, pv, block=blk)
            same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
            okA &= same
            rows.append(('v15', nm, blk, tag, bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1))))); print(rows[-1], flush=True)
        for rho, cr, md in ((1.5, 16.0, 2.0), (1.5, 8.0, 0.0), (0.0, 0.0, 0.0)):
            yb, tb, _ = VC.render(l16b, xx, VC.make_params(rho, cr, md), block=blk)
            for tag, pv in (('19vals', VC.make_params(rho, cr, md)), ('21vals_0', VC.make_params5(rho, cr, md)), ('21vals_0_onset2', VC.make_params5(rho, cr, md, 0, 2))):
                yc, tc, _ = VC.render(l16c, xx, pv, block=blk)
                same = np.array_equal(yb, yc) and np.array_equal(tb, tc)
                okA &= same
                rows.append(('16b', nm, blk, f'{rho}/{cr}/{md} {tag}', bool(same), float(np.max(np.abs(yb - yc))), float(np.max(np.abs(tb - tc))))); print(rows[-1], flush=True)
        if blk == 256:
            yb, tb, _ = VC.render(l16b, xx, VC.make_params(1.5, 16.0, 2.0), block=blk)
            for sl, on in ((2.0, 0.0), (4.0, 1.0), (8.0, 2.0)):
                yc, tc, _ = VC.render(l16c, xx, VC.make_params5(1.5, 16.0, 2.0, sl, on), block=blk)
                print('B', nm, 'slew', sl, 'onset', on, 'max|dy| vs base', float(np.max(np.abs(yb - yc))), 'finite', bool(np.all(np.isfinite(yc))), flush=True)
eng = T.Engine(l16c, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
for tag, pv in (('slew -1', VC.make_params5(slew=-1)), ('slew 0.05', VC.make_params5(slew=0.05)), ('slew 41', VC.make_params5(slew=41)), ('slew nan', VC.make_params5(slew=float('nan'))),
                ('onset 3', VC.make_params5(slew=2, onset=3)), ('onset 0.5', VC.make_params5(slew=2, onset=.5)), ('onset -1', VC.make_params5(slew=2, onset=-1)),
                ('slew 0', VC.make_params5()), ('slew 0.1', VC.make_params5(slew=.1)), ('slew 40 onset 2', VC.make_params5(slew=40, onset=2))):
    print(tag, '->', l16c.pvb_set_resultant(eng.h, pv.ctypes.data_as(VC.CA.DP), len(pv)))
eng.close()
print('V0 A (new params at 0 = 5c1c62c / v1.5) ALL BIT-IDENTICAL:', okA)
json.dump(rows, open(VC.A5_DIR / 'v0_check_a5.json', 'w'))

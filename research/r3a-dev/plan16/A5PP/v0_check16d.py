"""V0 for A5'' (params 20-22). 16d with betaSusMin/Max/OnsetMs = 0 (sent as 19, 20, 21 or 22 values) is bit identical to the 5c1c62c build (16b), output + 22-field trace,
for the v1.5 and the v1.6-a settings, several signals and block sizes. Extra: sustain pair = (betaMin, betaMax) with any onset ms is identical to off; a different pair changes the output;
the library refuses sustain on with betaOnsetMs = 0 and values out of range."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S
import test_engine as T
from pathlib import Path
CA = VC.CA
l16b = VC.load(str(VC.LIB16B))
l16d = VC.load(str(VC.HOME / 'r3-work/tools/pvb-harness/build_core16d/libpvbcapi.so'))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
sg = S.gated_line(25.0)
sigs['gated25_pink'] = S.stereo(sg['noisy'])[:int(8 * 48000)]
sigs['low_notes'] = S.stereo(S.low_notes())
settings = {'v15': [], 'v16a': [1.5, 16.0, 2.0], 'v16a_b05': [1.5, 16.0, 2.0]}
rows = []; okA = True; okC = True
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(2.5 * 48000)] if blk == 1 else x
        for sn, extra in (('v15', None), ('v16a', [1.5, 16.0, 2.0])):
            v19 = VC.make_params(*extra) if extra else VC.make_params()
            y0, t0, _ = VC.render(l16b, xx, v19, block=blk)
            for tag, add in (('19vals', []), ('20vals', [0.0]), ('21vals', [0.0, 0.0]), ('22vals', [0.0, 0.0, 0.0]), ('22vals_onset60_susoff', [0.0, 0.0, 60.0])):
                if extra is None and add:
                    base = np.array(list(VC.make_params(0.0, 0.0, 0.0)) + add, np.float64)
                elif extra is None:
                    base = v19
                else:
                    base = np.array(list(v19) + add, np.float64)
                y1, t1, _ = VC.render(l16d, xx, base, block=blk)
                same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
                okA &= same
                rows.append(('A', nm, blk, sn, tag, bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1)))))
                print(rows[-1], flush=True)
            if blk == 256 and sn == 'v16a':
                # C: sustain pair = the default pair: identical to off whatever the onset time
                for ms in (30.0, 100.0):
                    vc = np.array(list(v19) + [0.2, 0.9, ms], np.float64)
                    y1, t1, _ = VC.render(l16d, xx, vc, block=blk)
                    same = np.array_equal(y0, y1) and np.array_equal(t0, t1)
                    okC &= same
                    rows.append(('C', nm, blk, sn, f'sus=(.2,.9) onset {ms:g}', bool(same), float(np.max(np.abs(y0 - y1))), float(np.max(np.abs(t0 - t1)))))
                    print(rows[-1], flush=True)
                # D: a real sustain pair changes the output
                vd = np.array(list(v19) + [0.05, 0.1, 60.0], np.float64)
                y1, t1, _ = VC.render(l16d, xx, vd, block=blk)
                print('D', nm, 'sus (.05,.1) onset 60: max|dy| vs off', float(np.max(np.abs(y0 - y1))), 'trace differs', not np.array_equal(t0, t1), flush=True)
eng = T.Engine(l16d, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
base = list(VC.make_params(1.5, 16.0, 2.0))
ref = []
for tag, add in (('sus .05/.1 onset 0', [.05, .1, 0.]), ('sus .05/0 onset 60', [.05, 0., 60.]), ('sus 1.5/.1', [1.5, .1, 60.]), ('sus -.1', [-.1, .1, 60.]), ('onset 1001', [.05, .1, 1001.]),
                 ('onset -1', [0., 0., -1.]), ('nan', [float('nan'), .1, 60.]), ('sus .05/.1 onset 60', [.05, .1, 60.]), ('sus .1/.2 onset 100', [.1, .2, 100.]), ('off, onset 60', [0., 0., 60.])):
    v = np.array(base + add, np.float64)
    r = l16d.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v))
    ref.append((tag, int(r)))
    print('param check', tag, '->', r)
v = np.array(base + [0.0] * 4, np.float64)
print('23 values ->', l16d.pvb_set_resultant(eng.h, v.ctypes.data_as(VC.CA.DP), len(v)))
eng.close()
print('V0 A (params 20-22 at 0 = 5c1c62c) ALL BIT-IDENTICAL:', okA)
print('V0 C (sustain pair = default pair) ALL BIT-IDENTICAL to off:', okC)
json.dump(dict(rows=rows, okA=bool(okA), okC=bool(okC), param=ref), open(Path.home() / 'r3a-dev/plan16/A5PP/v0_check16d.json', 'w'))

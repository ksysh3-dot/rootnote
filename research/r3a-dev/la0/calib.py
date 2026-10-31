"""Synthesis-path calibration for the two ENGINE rows (core v1.5, P1): (1) the constant time offset between the hop-centre time stamps of their traces
and their real (latency-compensated) layers, measured by cross-correlating the 1 ms layer-energy envelopes on Track00060 36-48 s (a TRAIN song, not one of
the test signals); (2) the same metric code applied to the real layer and to the synthesized-from-trace layer, with and without the offset."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import evaluate as E, pipeline as P, rows as R, metrics as MT
import proxy16 as PX

LIBS = {'core': (X.CAND, 15, X.CFG['A']), 'p1': (X.REF, 6, None)}


def real_layer(row, key):
    path, algo, cfg = LIBS[row]
    lib = X.open_lib(path)
    x = audio(key)
    r0 = X.render(lib, x, algo, 0.0, out_db=-5.0, cfg=cfg); rd = X.render(lib, x, algo, -120.0, out_db=-5.0, cfg=cfg)
    return X.layer(r0, rd)


def env1ms(y):
    n = len(y) // 48
    return np.sqrt((y[:n * 48].reshape(n, 48) ** 2).mean(1))


def main():
    out = {'lags_ms': {}, 'metrics': {}}
    lags = {}
    sig = Sig('t60_36_48'); dur = P.duration('t60_36_48')
    for row in ('core', 'p1'):
        real = real_layer(row, 't60_36_48')
        v = R.voices_core(sig) if row == 'core' else R.voices_p1(sig)
        y = E.y48_of(v, dur)
        er = env1ms(real)[1000:11000]
        best = None
        for lag_ms in range(-40, 41):
            ys = E.y48_of(E.shift(v, lag_ms / 1000.0), dur)
            es = env1ms(ys)[1000:11000]
            n = min(len(er), len(es))
            c = np.corrcoef(20 * np.log10(er[:n] + 1e-9), 20 * np.log10(es[:n] + 1e-9))[0, 1]
            if best is None or c > best[1]:
                best = (lag_ms, c)
        lags[row] = best[0] / 1000.0
        out['lags_ms'][row] = dict(lag=best[0], corr=float(best[1]))
        print(row, 'lag ms', best, flush=True)
    json.dump(lags, open(E.LAGS_FILE, 'w'))
    # real-layer metrics versus proxy metrics
    sigs = {k: Sig(k) for k in ('bare100', 'step25', 'bass9', 'bkp_0', 't60_36_48', 'logoff_37_49', 'pink10')}
    for row in ('core', 'p1'):
        rec = {}
        for tag, lag in (('real', None), ('proxy_lag', lags[row]), ('proxy_nolag', 0.0)):
            m = {}
            for key, s in sigs.items():
                d = P.duration(key)
                if tag == 'real':
                    y = real_layer(row, key); y = np.pad(y, (0, max(0, int((d + .3) * FS) - len(y))))
                else:
                    v = R.voices_core(s) if row == 'core' else R.voices_p1(s)
                    y = E.y48_of(E.shift(v, lag), d)
                if key == 'bare100':
                    m.update({'bare_' + k: x for k, x in MT.v3h_bare(y).items()})
                elif key == 'step25':
                    m.update({'line_' + k: x for k, x in MT.v3h_line(y).items()})
                    rr = MT.rerise(y); m['rerise_db'] = rr['median']; m['rerise_above6'] = rr['n_above6']
                    dd = MT.v3d(y, [i * PX.PER for i in range(2, 40)]); m['v3d_line_median'] = dd['median_plain']; m['v3d_line_suite'] = dd['median']
                elif key == 'bass9':
                    m['v3a_layer_ms'] = MT.M.legacy_peak_ms(y[:8 * FS])['peak_ms']
                    m['v3d_bass_median'] = MT.v3d(y, [.5 * n for n in range(2, 16)])['median']
                elif key == 'bkp_0':
                    m['v4b_low_frac'] = MT.v4b(y, audio('bass8c'))['low_frac']
                elif key == 't60_36_48':
                    m['v5a_frac'] = MT.v5a(y)['frac']
                elif key == 'pink10':
                    m['v9_energy_db'] = MT.energy_db(y, 0.5, 9.9)
                elif key == 'logoff_37_49':
                    b = MT.v7d_burst(y); m['v7d_4.12'], m['v7d_4.73'] = b['4.12'], b['4.73']
            rec[tag] = m
            print(row, tag, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()}, flush=True)
        out['metrics'][row] = rec
    json.dump(out, open(LA0 / 'calib.json', 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()

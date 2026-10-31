"""S19-LIM worker: usage lim_worker.py ROW SONGIDX  [--test]. Saves numbers (block series, scalars) to res/. No audio saved."""
import sys, time, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/LIM')
import numpy as np
from pathlib import Path
from scipy.signal import sosfiltfilt
import lim_lib as Z

import os
FULL = os.environ.get('LIM_FULL') == '1'
OUT = Path('/home/ksysh/r3a-dev/plan16/S19/LIM/res_full' if FULL else '/home/ksysh/r3a-dev/plan16/S19/LIM/res'); OUT.mkdir(exist_ok=True)


def segments(i):
    """list of (name, t0, t1)"""
    if i in Z.SONG_IDX.values():
        key = [k for k, v in Z.SONG_IDX.items() if v == i][0]
        return [(Z.WNAME[j], a, b) for j, (k, a, b) in enumerate(Z.WINDOWS) if k == key]
    return [('EXC', None, None)]


def main(row, i, test=False):
    t_start = time.time()
    x = Z.read_song(i)
    dur = len(x) / Z.FS
    segs = segments(i)
    if segs[0][0] == 'EXC':
        if dur < 31:
            print('skip short', i); return
        t0 = min(60.0, dur - 31.0)
        segs = [('EXC', t0, t0 + 30.0)]
    if test:
        segs = [('T', 8.0, 10.0)]
    end = max(s[2] for s in segs) + 2.0
    if FULL:   # supplement: the whole rendered span (start of song to the same end) as one segment
        segs = [('FULL', 2.0, end - 1.0)]
    x = x[:int(end * Z.FS)]
    res = {}; log = {}
    conds = [('off', -120.0), ('s6', 6.0), ('s0', 0.0)]
    for cname, lvl in conds:
        yL, grL, _, lat = Z.run(x, row, lvl, twin=False)
        yU, grU, layU, lat2 = Z.run(x, row, lvl, twin=True, capture=True)
        assert lat == lat2
        # sanity: where the meter shows no reduction, limited == pre-limiter
        nb = len(grL)
        quiet = np.repeat(grL < 1e-6, Z.BLOCK)[:len(yL)]
        pk = float(np.abs(yU).max())
        dev = float(np.abs(yL[quiet] - yU[quiet]).max()) if quiet.any() else 0.0
        log[cname] = dict(lat=lat, pre_peak=pk, dev_quiet=dev, dev_rel=dev / max(pk, 1e-12), twin_gr_max=float(grU.max()),
                          gr_max=float(grL.max()), share_quiet=float(quiet.mean()))
        grp = sosfiltfilt(Z.SOS_GR, grL.astype(np.float64))
        gf = Z.fine_gr(yL, yU)
        gfp = sosfiltfilt(Z.SOS_GR1K, gf)
        lev, lpk, ppk = Z.block_series(yL, yU, layU, grL, lat)
        burst = Z.bursts(lev)
        # output band (what the speaker gets), input timeline
        yb = sosfiltfilt(Z.SOS_400, yL.mean(1).astype(np.float64))[lat:]
        env = Z.env_db(yb)
        tb = (np.arange(nb) * Z.BLOCK + Z.BLOCK / 2 - lat) / Z.FS
        tf = (np.arange(len(gf)) * 48 + 24 - lat) / Z.FS
        for (sn, t0, t1) in segs:
            mb = (tb >= t0) & (tb < t1); mf = (tf >= t0) & (tf < t1)
            a, b = int(round(t0 * Z.FS)), int(round(t1 * Z.FS))
            seg = yb[a:b]
            pks = [np.abs(seg[j:j + 9600]).max() for j in range(0, len(seg) - 9600 + 1, 9600)]
            e0, e1 = int(round(t0 * 200)), int(round(t1 * 200))
            M = Z.mod_M(env[e0:e1])
            k = f'{sn}|{cname}|'
            res[k + 'gr'] = grL[mb]; res[k + 'grbp'] = grp[mb]; res[k + 'grf'] = gf[mf].astype(np.float32); res[k + 'grfbp'] = gfp[mf].astype(np.float32)
            res[k + 'lo'] = lev[mb].astype(np.float32); res[k + 'lpk'] = lpk[mb].astype(np.float32); res[k + 'ppk'] = ppk[mb].astype(np.float32); res[k + 'burst'] = burst[mb]
            res[k + 'scal'] = np.array([20 * np.log10(np.abs(seg).max() + 1e-12), 20 * np.log10(np.median(pks) + 1e-12), M.mean()])
        del yL, yU, layU
    np.savez_compressed(OUT / f'{"test_" if test else ""}{row}_s{i:02d}.npz', **res)
    json.dump(dict(row=row, song=i, segs=segs, log=log, sec=time.time() - t_start), open(OUT / f'{"test_" if test else ""}{row}_s{i:02d}.json', 'w'), indent=1)
    print(row, i, round(time.time() - t_start), 'dev_rel', {c: round(v['dev_rel'], 7) for c, v in log.items()}, flush=True)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), test='--test' in sys.argv)

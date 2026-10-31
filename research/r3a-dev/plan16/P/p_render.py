"""Render the 10 V6 songs (0-30 s, train) through core (algo 15) and P1 (algo 6) of build_core with the diagnostic layer capture.
Saves cache/layer_<key>_<algo>.npy (mono float32 layer, latency removed, input-time index) + render_info.json.
Run from tools/pvb-harness: PYTHONPATH=.:study ~/venv-rootnote/bin/python ~/r3a-dev/plan16/P/p_render.py"""
import sys, json, time, hashlib
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
import multiprocessing as mp
from pcommon import *

P_DIR = Path('/home/ksysh/r3a-dev/plan16/P')
CACHE = P_DIR / 'cache'; CACHE.mkdir(exist_ok=True)
SONGS = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']


def one(key):
    t0 = time.time()
    p = X.SLAKH / key / 'mix.flac'
    assert 'slakh2100/validation' not in str(p) and 'slakh2100/test' not in str(p)
    x = X.read_excerpt(p, 0.0, 31.0)
    info = {}
    for algo in (15, 6):
        r = render_capture(x, algo)
        assert abs(r['y'] - r['full']).max() == 0.0
        assert np.abs(r['layer'][:, 0] - r['layer'][:, 1]).max() == 0.0
        np.save(CACHE / f'layer_{key}_{algo}.npy', r['layer'][:, 0].astype(np.float32))
        info[algo] = dict(lat=r['lat'], rms_layer=float(np.sqrt((r['layer'] ** 2).mean())), rms_y=float(np.sqrt((r['y'] ** 2).mean())), peak_y=float(np.abs(r['y']).max()))
    print(key, round(time.time() - t0, 1), info, flush=True)
    return key, info


if __name__ == '__main__':
    with mp.get_context('fork').Pool(10) as pool:
        out = dict(pool.map(one, SONGS))
    lib_sha = hashlib.sha256(LIB.read_bytes()).hexdigest()
    json.dump(dict(songs=out, lib=str(LIB), lib_sha256=lib_sha), open(P_DIR / 'render_info.json', 'w'), indent=1)
    print('done', lib_sha)

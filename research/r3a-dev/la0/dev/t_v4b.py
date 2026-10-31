import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import pipeline as P, evaluate as E, rows as R, metrics as MT, classify
import research_core_metrics as M

stream, L = sys.argv[1], int(sys.argv[2])
key = 'bkp_0'
sig = Sig(key)
models = {}
m, info = P.train_models(stream, L, 191); models[(stream, L)] = (m, info)
res, d, p, on, ora = E.decisions(models, key, stream, L, 191)
ivs = res['ivs']
near = [iv for iv in ivs if abs(np.median(iv['ch'].f) - 100) < 6 and len(iv['Af'])]
print('intervals near 100 Hz:', len(near), ' total', len(ivs))
for iv in near[:40]:
    t0 = stream_time(iv['j_on']); t1 = stream_time(iv['j_off'])
    print(f'  cid {iv["cid"]} [{t0:.3f},{t1:.3f}] on={on[iv["ivid"]]} p={p[iv["ivid"]]:.2f} Amax {iv["Af"].max():.3f} Amed {np.median(iv["Af"]):.3f} label {d["label"][iv["ivid"]]}')
v = R.voices_la(res, on)
y = E.y48_of(v, 8.0)
clean = audio('bass8c')
for c in (3, 4, 5):
    t0 = .5 * c; cen = t0 + .040 + .020 * np.arange(20) + .010
    r = M.ratio_db(M.proj_power(y, cen, 300.0), M.proj_power(clean, cen, 300.0))
    print('note', c, 'ratio dB per 20ms bin:', np.round(r, 0).astype(int).tolist(), 'median', round(float(np.median(r)), 1))

"""S19-SL Part B held-out job: one song (vNN = vanila index, rNN = Rayark index), rows v16c and nf48, excerpt 30..90 s (whole song if shorter than 90 s).
usage: sl_held.py KEY -> res/held_KEY.json (numbers only). Run via V16A/runpy.sh. Definitions: CHOICES.md"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/SL')
import numpy as np
import sl_lib as Z

key = sys.argv[1]
t = time.time()
xin = Z.read_any(key); dur = len(xin) / Z.FS
t0, t1 = (0.0, dur) if dur < 90 else (30.0, 90.0)
t0 = float(int(t0 * 2) / 2.0)
xin = xin[:int(t1 * Z.FS)]
xm0 = xin.astype(np.float64).mean(1)
res = dict(key=key, dur=dur, t0=t0, t1=t1)
for r in ('v16c', 'nf48'):
    x, _ = Z.HM.render_song(xin, r)
    xm = xm0[:len(x)]
    i0, i1 = int(t0 * Z.FS), min(int(t1 * Z.FS), len(x))
    seg = x[i0:i1]
    d = Z.hann_bands(seg, Z.FS)
    el = Z.env_db_box(Z.sosfiltfilt(Z.BP260_48, x), 240); ei = Z.env_db_box(Z.sosfiltfilt(Z.BP260_48, xm), 240)
    # 2 s windows, hop 0.5 s, eligible: input mean square > -70 dBFS
    e0s = np.arange(int(round(t0 * 200)), int(round(i1 / Z.FS * 200)) - Z._WIN + 1, 100)
    Ml = []; Mi = []; Ml12 = []; Mi12 = []
    for e0 in e0s:
        a, b = e0 * 240, e0 * 240 + 400 * 240
        if b > len(xm):
            break
        if Z.db(np.mean(xm[a:b] ** 2)) <= -70.0:
            continue
        m = Z.modM(el[e0:e0 + Z._WIN]); n = Z.modM(ei[e0:e0 + Z._WIN])
        Ml.append(m[0]); Mi.append(n[0]); Ml12.append(m[1]); Mi12.append(n[1])
    d.update(nwin=len(Ml), excess=float(np.mean(np.array(Ml) - np.array(Mi))) if Ml else None,
             excess12=float(np.mean(np.array(Ml12) - np.array(Mi12))) if Ml else None)
    res[r] = d
    del x
res['sec'] = round(time.time() - t)
json.dump(res, open(Z.RES / f'held_{key}.json', 'w'))
print('DONE', key, res['sec'], flush=True)

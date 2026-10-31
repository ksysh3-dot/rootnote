"""S19-SL dev-window job for one song: Part B real metrics (v1.6-c, nf48, P1 body for user songs) and Part A oracle (trace reconstruction, 12 variants).
usage: sl_dev.py SONG   (v09, v06, beyond, lastcarn)   -> res/dev_SONG.json ; numbers only. Run via V16A/runpy.sh"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/SL')
import numpy as np
import sl_lib as Z

song = sys.argv[1]
segs = [t for s, t in Z.DEV if s == song]
out = dict(song=song, segs=segs)
t = time.time()
xin = Z.read_any(song); xm0 = xin.astype(np.float64).mean(1)
rows = ['v16c', 'nf48'] + (['p1'] if song in ('v09', 'v06') else [])
tr16 = None
for r in rows:
    x, tr = Z.HM.render_song(xin, r)
    xm = xm0[:len(x)]
    out['real_' + r] = Z.win_metrics_real(x, xm, segs)
    print(song, r, 'rendered', round(time.time() - t), flush=True)
    if r == 'v16c':
        tr16 = tr; x16 = x
    del x
d = Z.trace_of(tr16)
# alignment
lags = [Z.find_lag(x16, Z.rebuild(d, d['a_2'].astype(np.float64), d['a_3'].astype(np.float64)), s0) for s0 in segs]
out['lags'] = lags
good = [l for c, l in lags if c > 0.8]
Z.LAG[0] = int(np.median(good)) if good else 22
out['lag_used'] = Z.LAG[0]
a2 = d['a_2'].astype(np.float64); a3 = d['a_3'].astype(np.float64)
sus = Z.sustain_flags(d)
out['sus_frac'] = float(sus.sum() / max((d['state'] == 2).sum(), 1))
y0 = Z.rebuild(d, a2, a3)
out['recon_base'] = Z.win_metrics_recon(y0, segs)
out['jumps_base'] = Z.jump_stats(d, a2, segs)
out['jumps_base_sus'] = Z.jump_stats(d, a2, segs, only=sus)
out['recon_vs_real'] = [dict(m1=Z.db(q['m1']) - Z.db(r['m1']), m4=Z.db(q['m4']) - Z.db(r['m4'])) for q, r in zip(out['recon_base'], out['real_v16c'])]
print(song, 'baseline recon done, lag', Z.LAG[0], 'sus', out['sus_frac'], round(time.time() - t), flush=True)
out['var'] = {}
for kind in ('zp', 'c1', 'c2'):
    for T in (30, 50):
        s2 = Z.smooth_amp(d, sus, 'a_2', kind, T); s3 = Z.smooth_amp(d, sus, 'a_3', kind, T)
        assert np.array_equal(s2[~sus], a2[~sus]) and np.array_equal(s3[~sus], a3[~sus])   # onsets / REL / pre-sustain bitwise untouched
        for tag, (b2, b3) in (('a2', (s2, a3)), ('a23', (s2, s3))):
            y = Z.rebuild(d, b2, b3)
            out['var'][f'{kind}_{T}_{tag}'] = dict(recon=Z.win_metrics_recon(y, segs), jumps=Z.jump_stats(d, s2, segs), jumps_sus=Z.jump_stats(d, s2, segs, only=sus),
                                                  changed_hops=int((s2 != a2).sum()))
        print(song, kind, T, round(time.time() - t), flush=True)
json.dump(out, open(Z.RES / f'dev_{song}.json', 'w'))
print('DONE', song, round(time.time() - t), flush=True)

import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
import ladder as LD
S = json.load(open('/home/ksysh/r3a-dev/plan16/S/s_raw.json'))
tot = miss = 0; dm = []; dc = []
for k in LD.SONGS:
    segs, _ = LD.segments(k)
    for sg, i in zip(segs, S['s1info'][k]):
        (dm if i['missing'] else dc).append((sg['e'] - sg['s']) * 1e3)
q = lambda a: [round(float(np.percentile(a, p))) for p in (10, 50, 90)]
print('segment duration ms p10/50/90: missing', q(dm), len(dm), ' covered', q(dc), len(dc))
for ex in ('Track00040',):
    m = sum(i['missing'] for k in LD.SONGS if k != ex for i in S['s1info'][k]); n = sum(len(S['s1info'][k]) for k in LD.SONGS if k != ex)
    print('missing excluding', ex, m, n, round(100 * m / n, 1))
# time-weighted without T40
tm = sum(S['res'][k]['s1_time']['miss'] for k in LD.SONGS if k != 'Track00040'); tt = sum(S['res'][k]['s1_time']['tot'] for k in LD.SONGS if k != 'Track00040')
print('time-weighted excl T40', round(100 * tm / tt, 1))
# partial cover for covered segments
cov = [i['cov_time'] / ((sg['e'] - sg['s'])) for k in LD.SONGS for sg, i in zip(LD.segments(k)[0], S['s1info'][k]) if not i['missing']]
print('covered segments: fraction of segment time with S1 layer p10/50/90', [round(float(np.percentile(cov, p)), 2) for p in (10, 50, 90)])

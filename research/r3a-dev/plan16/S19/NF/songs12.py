"""12-song median of the per-song 20-150 / 150-600 Hz layer ratio (S19-NF CHOICES.md). Whole song rendered exactly as p_primary.render_song (read in place, never copied),
layer = zero-phase 4th-order Butterworth bands as p_primary, power over the whole song after the first 2 s (warm-up); ratio dB = 10log10(P_lo/P_mid), lower = better.
Songs: all vanila songs except Apparition (idx 9) and Reminiscence (idx 6). Only numbers are saved.
usage: songs12.py LABEL...  (writes songs12_<label>.json)"""
import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/NF')
import numpy as np
from scipy.signal import sosfiltfilt
import p_primary as P
from multiprocessing import Pool

SONGS = [i for i in range(len(P.MUSIC)) if i not in (6, 9)]
assert len(SONGS) == 12
FS = P.FS


def job(a):
    label, i = a
    t = time.time()
    lay, _ = P.render_song(P.read_song(i), label, with_trace=False)
    lay = lay[2 * FS:]
    lo = sosfiltfilt(P.SOS_LO, lay); mid = sosfiltfilt(P.SOS_MID, lay)
    pl, pm = float(np.mean(lo ** 2)), float(np.mean(mid ** 2))
    return label, i, dict(p_lo=pl, p_mid=pm, ratio_db=float(10 * np.log10(max(pl, 1e-30) / max(pm, 1e-30))), secs=time.time() - t)


if __name__ == '__main__':
    labels = sys.argv[1:]
    res = {l: {} for l in labels}
    with Pool(12) as p:
        for label, i, d in p.imap_unordered(job, [(l, i) for l in labels for i in SONGS]):
            res[label][str(i)] = d
            print(label, i, round(d['ratio_db'], 2), round(d['secs']), flush=True)
    for l, r in res.items():
        json.dump(r, open(f'/home/ksysh/r3a-dev/plan16/S19/NF/songs12_{l}.json', 'w'), indent=1)
        print(l, 'median', float(np.median([v['ratio_db'] for v in r.values()])))

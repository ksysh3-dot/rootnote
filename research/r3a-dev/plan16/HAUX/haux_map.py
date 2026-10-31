"""time-mapping validation (CHOICES.md section 1; not used to retune T): within matched real voices, cross-correlate hop differences of the trace amplitude (dB)
with hop differences of the fitted input partial energy (dB, mean E k=2..6, W40 at f_track).  lag > 0: the input changes later than the trace amplitude."""
import glob
import numpy as np
from pathlib import Path
HX = Path('/home/ksysh/r3a-dev/plan16/HAUX')
HOP_MS = 16 / 3000 * 1000
LAGS = np.arange(-10, 11)
tot = np.zeros(len(LAGS)); cnt = np.zeros(len(LAGS)); per = {}
for key in ('Track00060', 'Track00001', 'Track00012', 'Track00005', 'Track00020', 'Track00040'):
    zs = [np.load(p) for p in sorted(glob.glob(str(HX / 'cache' / f'feat_{key}_p*.npz')))]
    d = {k: np.concatenate([z[k] for z in zs]) for k in zs[0].files}
    o = np.lexsort((d['i'], d['vi'])); d = {k: v[o] for k, v in d.items()}
    m = (d['cls'] == 0) & (d['comp'] == 0)
    idx = np.flatnonzero(m)
    E = d['E_t40'].astype(float)
    with np.errstate(all='ignore'):
        edb = 10 * np.log10(np.nanmean(E[:, :5], 1) + 1e-30)
    adb = 20 * np.log10(d['amp'] + 1e-30)
    # contiguous runs of consecutive hops in one voice
    vi, h = d['vi'][idx], d['h'][idx]
    brk = np.flatnonzero((vi[1:] != vi[:-1]) | (h[1:] - h[:-1] != 1)) + 1
    runs = np.split(idx, brk)
    num = np.zeros(len(LAGS)); den = np.zeros(len(LAGS)); sa = 0.0; se = 0.0; n_ = 0
    for r in runs:
        if len(r) < 25:
            continue
        a = np.diff(adb[r]); e = np.diff(edb[r])
        a = a - a.mean(); e = e - e.mean()
        for li, l in enumerate(LAGS):
            if l >= 0:
                x, y = a[:len(a) - l], e[l:]
            else:
                x, y = a[-l:], e[:len(e) + l]
            num[li] += float((x * y).sum()); den[li] += len(x)
        sa += float((a ** 2).sum()); se += float((e ** 2).sum()); n_ += len(a)
    c = num / np.sqrt(sa * se) * (n_ / np.maximum(den, 1))
    per[key] = c
    tot += c; cnt += 1
    print(key, 'runs', sum(len(r) >= 25 for r in runs), 'argmax lag hops', LAGS[np.argmax(c)], '=', round(LAGS[np.argmax(c)] * HOP_MS, 1), 'ms; corr at 0', round(c[LAGS == 0][0], 3), 'max', round(c.max(), 3))
c = tot / cnt
print('mean over songs: argmax lag', LAGS[np.argmax(c)], 'hops =', round(LAGS[np.argmax(c)] * HOP_MS, 1), 'ms; corr(lag) ', ' '.join(f'{l}:{x:.3f}' for l, x in zip(LAGS, c)))

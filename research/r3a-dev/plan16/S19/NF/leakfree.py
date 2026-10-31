"""REPORT-ONLY leakage-free ratio (coordinator addition, added before its numbers were seen): on the 7 user windows, energy of FFT bins 20-140 Hz / energy of bins 150-600 Hz,
rectangular window over the whole 2 s window, mono mean of layer channels, same render and latency handling as p_primary.render_song. usage: leakfree.py LABEL..."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/NF')
import numpy as np
import p_primary as P
from multiprocessing import Pool
FS = P.FS


def job(a):
    label, sk = a
    lay, _ = P.render_song(P.read_song(P.SONG_IDX[sk]), label, with_trace=False)
    out = []
    for (s, t0, t1) in P.WINDOWS:
        if s != sk:
            continue
        x = lay[int(t0 * FS):int(t1 * FS)]
        X = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1 / FS)
        el = float(X[(f >= 20) & (f <= 140)].sum()); em = float(X[(f >= 150) & (f <= 600)].sum())
        out.append(dict(song=s, t0=t0, e_lo=el, e_mid=em))
    return label, out


if __name__ == '__main__':
    labels = sys.argv[1:]
    res = {l: [] for l in labels}
    with Pool(6) as p:
        for l, o in p.imap_unordered(job, [(l, s) for l in labels for s in P.SONG_IDX]):
            res[l].extend(o)
    db = lambda v: 10 * np.log10(max(v, 1e-30))
    summ = {}
    for l, r in res.items():
        r.sort(key=lambda d: (d['song'], d['t0']))
        pw = [db(d['e_lo']) - db(d['e_mid']) for d in r]
        summ[l] = dict(pooled=db(sum(d['e_lo'] for d in r)) - db(sum(d['e_mid'] for d in r)), per_window=pw)
        print(f'{l:8s} pooled {summ[l]["pooled"]:7.2f}  ' + ' '.join(f'{x:6.1f}' for x in pw), flush=True)
    json.dump(summ, open('/home/ksysh/r3a-dev/plan16/S19/NF/leakfree.json', 'w'), indent=1)

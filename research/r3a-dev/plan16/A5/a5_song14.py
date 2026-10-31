"""14-song table (report-only, 18.9): median / p95 of the 20-150 Hz layer pulse excess (B1 b1_rank_lo.py measure: 2 s windows, hop 0.5 s, 2-12 Hz modulation of the 5 ms dB envelope
minus the input's, eligibility = registered v1.5 150-600 level > -70 dBFS) for P1 / v1.5 (B1 cache, same library family, bit-identical params) and v1.6-a base / A5 rows rendered here
(16c library). Only 5 ms envelopes are kept (A5/cache14); no audio. usage: a5_song14.py render LABEL... | table LABEL..."""
import sys, os, json, time, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import numpy as np
from pathlib import Path
from scipy.signal import butter
import a5primary_mod as P
import a5rows as AR
from b1_mod import mod_series
from multiprocessing import Pool
B1 = Path('/home/ksysh/r3a-dev/plan16/B1'); CB = B1 / 'cache'; C14 = Path('/home/ksysh/r3a-dev/plan16/A5/cache14'); C14.mkdir(exist_ok=True)
FS = 48000; BOX = 240
SOS_LO = butter(4, [20, 150], 'bandpass', fs=FS, output='sos')
from scipy.signal import sosfiltfilt


def env_db(sig):
    n = len(sig) // BOX
    r = np.sqrt(np.mean(sig[:n * BOX].reshape(n, BOX) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), -90.0)


def job(a):
    i, label = a
    f = C14 / f's{i:02d}_{label}_lo.npy'
    if f.exists():
        return a
    lay, _ = P.render_song(P.read_song(i), label, with_trace=False)
    np.save(f, env_db(sosfiltfilt(SOS_LO, lay)).astype(np.float32))
    return a


def table(labels):
    mmss = lambda t: f'{int(t // 60)}:{t % 60:04.1f}'
    cols = ['P1', 'v15'] + labels
    print('song | n_elig | ' + ' | '.join(f'{AR.NAMES.get(c.lower(), c) if c in ("P1",) else AR.NAMES.get(c, c)} med/p95' for c in cols))
    allmed = {c: [] for c in cols}
    for i, p in enumerate(P.MUSIC):
        nm = os.path.basename(str(p))[:-5]
        env = {'P1': np.load(CB / f's{i:02d}_P1_lo.npz')['env'], 'v15': np.load(CB / f's{i:02d}_v15_lo.npz')['env']}
        for l in labels:
            env[l] = np.load(C14 / f's{i:02d}_{l}_lo.npy')
        inp = np.load(CB / f's{i:02d}_input_lo.npz')['env']; e15 = np.load(CB / f's{i:02d}_v15.npz')['env']
        n = min(len(inp), len(e15), *[len(v) for v in env.values()])
        S = {e: mod_series(env[e][:n]) for e in cols}
        t, _, _, lev = mod_series(e15[:n])
        Mi = mod_series(inp[:n])[1]
        elig = (lev > -70) & (t >= 2.0)
        st = {e: (float(np.median(S[e][1][elig] - Mi[elig])), float(np.percentile(S[e][1][elig] - Mi[elig], 95))) for e in cols}
        for e in cols:
            allmed[e].append(st[e][0])
        print(f'{i:02d} {nm[:30]:30s} | {elig.sum():3d} | ' + ' | '.join(f'{st[e][0]:.2f}/{st[e][1]:.2f}' for e in cols))
    print('median over songs of the per-song median: ' + ' | '.join(f'{c} {np.median(allmed[c]):.2f}' for c in cols))


if __name__ == '__main__':
    if sys.argv[1] == 'render':
        with Pool(12) as p:
            for a in p.imap_unordered(job, [(i, l) for i in range(len(P.MUSIC)) for l in sys.argv[2:]]):
                print(a, flush=True)
    else:
        table(sys.argv[2:])

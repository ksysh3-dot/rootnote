"""Report-only diagnostic: where in 20-600 Hz the layer energy of the 7 windows sits (pooled periodogram band energies, dBFS-equivalent), per row."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import numpy as np
import a5primary_mod as P
from multiprocessing import Pool
EDGES = [20, 40, 60, 80, 100, 125, 150, 200, 300, 600]


def job(a):
    label, sk = a
    lay, _ = P.render_song(P.read_song(P.SONG_IDX[sk]), label, with_trace=False)
    acc = np.zeros(len(EDGES) - 1)
    for (s, t0, t1) in P.WINDOWS:
        if s != sk:
            continue
        x = lay[int(t0 * P.FS):int(t1 * P.FS)] * np.hanning(int((t1 - t0) * P.FS))
        X = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1 / P.FS)
        for i in range(len(EDGES) - 1):
            acc[i] += X[(f >= EDGES[i]) & (f < EDGES[i + 1])].sum()
    return label, acc


if __name__ == '__main__':
    labels = sys.argv[1:]
    tot = {}
    with Pool(8) as p:
        for label, acc in p.imap_unordered(job, [(l, s) for l in labels for s in P.SONG_IDX]):
            tot[label] = tot.get(label, 0) + acc
    print('band Hz   ' + ' '.join(f'{EDGES[i]}-{EDGES[i + 1]:<5d}' for i in range(len(EDGES) - 1)))
    ref = tot[labels[0]]
    for l in labels:
        print(f'{l:6s} rel dB vs {labels[0]}: ' + ' '.join(f'{10 * np.log10(tot[l][i] / ref[i]):8.1f}' for i in range(len(EDGES) - 1)), ' | abs(first-row-rel) ' + ' '.join(f'{10 * np.log10(tot[l][i]):6.1f}' for i in range(len(EDGES) - 1)))

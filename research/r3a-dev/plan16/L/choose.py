"""Plan16 L step 2: window / null selection from L/sil_series.npz (no audio rendered). Writes L/choices.json.
Rules are in CHOICES.md (fixed before any pair is rendered)."""
import json, itertools
import numpy as np
FSC = 3000.0
W = 9.0
HOP = 0.25
START_MIN = 1.0           # engine settled / t > 0.5 s analysis rule
R3R = 59.3507
SLACK = 0.0               # null window: smallest achievable total overlap with the test windows (ties: best score)
z = np.load('/home/ksysh/r3a-dev/plan16/L/sil_series.npz')
SONGS = ('Track00025', 'Track00026')


def scores(key):
    y = z[key + '_ysil']
    e = y ** 2
    e[:1500] = 0.0                       # t > 0.5 s as in 16.9
    c = np.r_[0.0, np.cumsum(e)]
    starts = np.round(np.arange(START_MIN, 30.0 - W + 1e-9, HOP), 2)
    s = np.array([c[int(round((t + W) * FSC))] - c[int(round(t * FSC))] for t in starts])
    return starts, s


def overlap(a, b):
    return max(0.0, W - abs(a - b))


out = {}
for key in SONGS:
    starts, s = scores(key)
    n = len(starts)
    best, bi = -1, None
    for i, j, k in itertools.combinations(range(n), 3):
        if starts[j] - starts[i] >= W and starts[k] - starts[j] >= W:
            tot = s[i] + s[j] + s[k]
            if tot > best + 1e-12:
                best, bi = tot, (i, j, k)
    tests = sorted(bi, key=lambda i: -s[i])
    ov = np.array([sum(overlap(starts[i], starts[j]) for j in bi) for i in range(n)])
    allowed = np.flatnonzero((ov <= ov.min() + SLACK) & ~np.isin(np.arange(n), bi))
    nb = allowed[np.argmax(s[allowed])]
    out[key] = dict(tests=[dict(start=float(starts[i]), units=float(s[i] / R3R)) for i in tests],
                    null=dict(start=float(starts[nb]), units=float(s[nb] / R3R), overlap_with_tests=float(ov[nb])),
                    min_overlap=float(ov.min()), n_candidate_windows=int(n))
    print(key, json.dumps(out[key]))
    # info: greedy top-3 (what a naive greedy would give)
    gre = []
    for i in np.argsort(-s, kind='stable'):
        if all(overlap(starts[i], starts[j]) == 0 for j in gre):
            gre.append(i)
        if len(gre) == 3:
            break
    out[key]['greedy_info'] = [float(starts[i]) for i in gre]
    print('  greedy-by-score (info):', out[key]['greedy_info'])
json.dump(out, open('/home/ksysh/r3a-dev/plan16/L/choices.json', 'w'), indent=1)

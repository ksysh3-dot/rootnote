"""P1 harmonic-trace access and join with the v15 voices. Row layout (pvb_harmonic_trace.h): header 28, 12 tracks x 56:
[id, state(1 Birth,2 Tracked,3 Held,4 Release,5 End), f, df/dt, a, phase, residual, fade, age, missing, reason, life gain, raw residual, id_hi16]
+ 7 harmonics (k=2..8) x [target amp, actual amp, mask weight, phase adj, reason, evidence]."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_data import *

TF = {'id': 0, 'state': 1, 'f': 2, 'dfdt': 3, 'a': 4, 'phase': 5, 'res': 6, 'fade': 7, 'age': 8, 'missing': 9, 'reason': 10, 'life': 11, 'rawres': 12, 'idhi': 13}
HARM_REASONS = {1: 'Absolute', 2: 'Relative', 4: 'NoPeak', 8: 'Fit', 16: 'Grid', 32: 'Lost', 64: 'Capacity', 128: 'Weight', 256: 'Nonfinite', 512: 'Dependent'}


def p1_tracks(sk, eng='P1'):
    """dict core index -> (12, 14) track array, and (12, 7, 6) harmonic array"""
    d = load(sk, eng); h = d['h']
    T_ = h[:, 28:28 + 56 * 12].reshape(-1, 12, 56)
    return d['hci'], T_[:, :, :14], T_[:, :, 14:].reshape(-1, 12, 7, 6), h[:, :28]


def tid(tk):
    return tk[..., 0].astype(np.int64) + (tk[..., 13].astype(np.int64) << 16)


if __name__ == '__main__':
    np.set_printoptions(linewidth=200, precision=3, suppress=True)
    sk, t0, t1 = 'app', 52.0, 54.0
    ci, tk, hm, hd = p1_tracks(sk)
    ids = tid(tk)
    d = load(sk, 'v15'); tr = d['tr']
    hop = tr['hop'][:, 0]
    pos = {int(c): i for i, c in enumerate(ci)}
    cp = comps(sk, 'v15', t0, t1)
    # coverage of v15 voice track ids in the P1 track list
    tot = hit = 0
    for r, h_ in enumerate(cp['hop']):
        j = pos[int(h_)]
        for s in range(8):
            if cp['st'][r, s] >= 2 and cp['a'][0][r, s] > 0:
                tot += 1
                hit += int(cp['trk'][r, s]) in set(ids[j][tk[j][:, 1] > 0].tolist())
    print('v15 sounding slot-hops', tot, 'whose track id is in the P1 track list at the same hop:', hit)
    print('example v15 trk ids', np.unique(cp['trk'])[:10], 'P1 ids', np.unique(ids[tk[:, :, 1] > 0])[:10])

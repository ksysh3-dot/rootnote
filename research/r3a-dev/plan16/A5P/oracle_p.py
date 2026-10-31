"""Phase-side oracle (18.12 fallback, OFFLINE ESTIMATE; no engine change). For one grid row, renders Apparition and Reminiscence with the voice trace and rebuilds the
resultant layer from the trace exactly as ResultantCore::synthesize does (k = 2 and 3 only; theta ramps linearly over a hop from the previous hop-end theta_hat to this one,
a and psi interpolate linearly between hop ends; 3 kHz core rate). Variants:
  raw   : trace as it is (sanity: its 20-150/150-600 ratio is compared with the rendered layer's ratio from p_primary)
  th{W} : theta replaced by a centred moving average (W hops, edge-normalised) of the unwrapped theta_hat per voice run (nominal increment 2 pi f_osc hop + wrapped innovation);
          the frequency is then the derivative of that smooth phase ("f_osc and theta pinned to a smoothed reference")
  tp{W} : th{W} and the psi_2, psi_3 also replaced by their moving average (unwrapped)
Amplitudes a_2, a_3 stay as rendered. The rebuilt layer is upsampled x16 and passed through the engine output filter (vbt::kOutSos) before the 20-150 / 150-600 Hz zero-phase bands, as the rendered layer is. Band energies of the 7 user windows (input time via CA.hop_time), pooled ratio 10 log10(E20-150 / E150-600) of the rebuilt layer.
usage: oracle_p.py LABEL ...   -> oracle_<LABEL>.json"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
import p_primary as P
import a5prows as AR
from scipy.signal import butter, sosfiltfilt, sosfilt, resample_poly
from multiprocessing import Pool
CA = P.CA
FSC = 3000; HOPS = 16 / 3000
OUT_SOS = np.array([[0.6620158372026176, -1.3240316744052352, 0.6620158372026176, 1.0, -1.4796742169311934, 0.5558215432824889],
                    [1.0, -2.0, 1.0, 1.0, -1.7009643319435257, 0.7884997398152979],
                    [0.20657208382614792, 0.41314416765229584, 0.20657208382614792, 1.0, -0.3695273773512414, 0.19581571265583306]])   # vbt::kOutSos (output filter, 48 kHz)


def to_layer(y3k):
    """3 kHz core signal -> 48 kHz (x16 polyphase). The rendered resultant layer is NOT passed through kOutSos (diag_oracle.py: 150-600 Hz xcorr 0.94 without it, 0.6 with it).
    diag_oracle.py also finds the rebuilt 20-150 Hz energy ~6 dB above the rendered one (constant over windows): only differences between variants are meaningful."""
    return resample_poly(y3k, 16, 1)


def ma(x, W):
    """centred moving average, edge-normalised"""
    if W <= 1 or len(x) == 0:
        return x
    k = np.ones(W)
    return np.convolve(x, k, 'same') / np.convolve(np.ones(len(x)), k, 'same')


def runs(tr):
    """yield (slot, hop-row indices) of consecutive hops of one voice id with state >= 1 (CAND, ON, REL)"""
    st, vid = tr['state'], tr['voice']
    H, S = st.shape
    for s in range(S):
        act = st[:, s] >= 1
        i = 0
        while i < H:
            if not act[i]:
                i += 1; continue
            j = i + 1
            while j < H and act[j] and vid[j, s] == vid[i, s]:
                j += 1
            if j - i >= 2:
                yield s, np.arange(i, j)
            i = j


def rebuild(tr, variant, W):
    ih = tr['hop'][:, 0].astype(np.int64)
    out = np.zeros(int(ih.max()) + 64)
    j16 = np.arange(16) / 16.0
    for s, idx in runs(tr):
        th = tr['theta_hat'][idx, s].copy(); fo = tr['f_osc'][idx, s]
        ps = [tr['psi_2'][idx, s].copy(), tr['psi_3'][idx, s].copy()]
        am = [tr['a_2'][idx, s], tr['a_3'][idx, s]]
        if variant != 'raw':
            nom = 2 * np.pi * fo[:-1] * HOPS                                   # nominal increment of hop i (i>=1) uses f_osc of hop i-1
            inn = np.remainder(np.diff(th) - nom + np.pi, 2 * np.pi) - np.pi
            thu = np.concatenate([[th[0]], th[0] + np.cumsum(nom + inn)])
            th = ma(thu, W)
            if variant == 'tp':
                ps = [ma(np.unwrap(p), W) for p in ps]
        for i in range(1, len(idx)):
            t0 = np.remainder(th[i - 1] + np.pi, 2 * np.pi) - np.pi
            dth = (th[i] - th[i - 1]) / 16.0
            ph = t0 + dth * np.arange(16)
            base = ih[idx[i]]
            for kk, p, a in ((2, ps[0], am[0]), (3, ps[1], am[1])):
                if a[i] == 0 and a[i - 1] == 0:
                    continue
                aa = a[i - 1] + (a[i] - a[i - 1]) * j16
                out[base:base + 16] += aa * np.cos(kk * ph + p[i - 1] + (p[i] - p[i - 1]) * j16)
    return out


def job(a):
    label, sk = a
    lay, tr = P.render_song(P.read_song(P.SONG_IDX[sk]), label)
    lo = sosfiltfilt(P.SOS_LO, lay); mid = sosfiltfilt(P.SOS_MID, lay)
    ts = CA.hop_time(tr['hop'][:, 0])[1]; ih = tr['hop'][:, 0].astype(np.int64)
    res = {}
    wl = [(s, t0, t1) for (s, t0, t1) in P.WINDOWS if s == sk]
    res['rendered'] = [(float(np.mean(lo[int(t0 * P.FS):int(t1 * P.FS)] ** 2)), float(np.mean(mid[int(t0 * P.FS):int(t1 * P.FS)] ** 2))) for (_, t0, t1) in wl]
    for name, var, W in (('raw', 'raw', 1), ('th3', 'th', 3), ('th5', 'th', 5), ('th9', 'th', 9), ('th15', 'th', 15), ('tp9', 'tp', 9)):
        y = rebuild(tr, var, W)
        y48 = to_layer(y); yl = sosfiltfilt(P.SOS_LO, y48); ym = sosfiltfilt(P.SOS_MID, y48)
        e = []
        for (_, t0, t1) in wl:
            sel = np.where((ts >= t0) & (ts < t1))[0]
            n0, n1 = 16 * ih[sel.min()], 16 * (ih[sel.max()] + 16)
            e.append((float(np.mean(yl[n0:n1] ** 2)), float(np.mean(ym[n0:n1] ** 2))))
        res[name] = e
    return label, sk, res


if __name__ == '__main__':
    labels = sys.argv[1:]
    R = {}
    with Pool(min(8, 2 * len(labels))) as p:
        for label, sk, res in p.imap_unordered(job, [(l, s) for l in labels for s in P.SONG_IDX]):
            R.setdefault(label, {})[sk] = res
            print(label, sk, flush=True)
    db = lambda x: 10 * np.log10(max(x, 1e-30))
    for label, d in R.items():
        out = {}
        for var in d['app'].keys():
            rows = [x for sk in ('app', 'rem') for x in d[sk][var]]
            lo = sum(r[0] for r in rows); mid = sum(r[1] for r in rows)
            out[var] = dict(ratio=db(lo) - db(mid), lo_db=db(lo / len(rows)), mid_db=db(mid / len(rows)), per_window=[db(r[0]) - db(r[1]) for r in rows])
        json.dump(out, open(P.AC.A5_DIR / f'oracle_{label}.json', 'w'), indent=1)
        print(label, {k: round(v['ratio'], 2) for k, v in out.items()})

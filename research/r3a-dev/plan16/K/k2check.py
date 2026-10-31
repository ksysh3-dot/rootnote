"""K2 emulation check: (1) vectorised peak finder == q4.src_peaks loop, (2) agreement of evid_any with engine 'prominent' for det[j] vs det[j-191]"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/K')
from kcommon import *
import multiprocessing as mp


def src_peaks_loop(sm):                      # verbatim copy of diag16/q4.py src_peaks (accepted list only)
    res = [[], []]
    for band in range(2):
        lb = int(np.ceil((140 if band else 20) / BIN)); hb = int(np.floor((620 if band else 200) / BIN))
        maxmag = sm[lb:hb + 1].max()
        for b in range(lb + 1, hb):
            v = sm[b]
            if not (v >= sm[b - 1] and v > sm[b + 1]):
                continue
            med = np.median(sm[np.clip(np.arange(b - 27, b + 28), lb, hb)])
            rel = 20 * np.log10(v / maxmag + 1e-30)

            def offset(a, b_, c):
                den = a - 2 * b_ + c
                return float(np.clip(0.5 * (a - c) / den, -1, 1)) if abs(den) > 1e-12 else 0.0
            f = (b + offset(np.log(sm[b - 1] + 1e-30), np.log(v + 1e-30), np.log(sm[b + 1] + 1e-30))) * BIN
            floor_db = -60. if band else -50.
            ok = rel >= floor_db and v >= (med + 1e-20) * np.sqrt(10.)
            if ok:
                res[band].append((f, rel))
    return res


def one(key):
    sig = Sig(key)
    raw = sig.core_raw; d = sig.core_d
    rng = np.random.default_rng(3)
    hs, js = np.nonzero(d['state'] > 0)
    sel = rng.choice(len(hs), size=min(2500, len(hs)), replace=False)
    out = {0: [0, 0], 191: [0, 0]}
    mism = 0
    for off in (0, 191):
        for k in sel:
            h, j = hs[k], js[k]
            ih = int(sig.core_hop[h])
            sm = sm_at(sig.det, ih, off)
            pf, pr = src_peaks_vec(sm)
            if off == 0 and k < sel[0] + 0 or (off == 0 and k % 97 == 0):
                rl = src_peaks_loop(sm)
                a = sorted([x[0] for b in rl for x in b]); b2 = sorted(pf.tolist())
                if len(a) != len(b2) or (len(a) and np.max(np.abs(np.array(a) - np.array(b2))) > 1e-6):
                    mism += 1
            f = float(d['ftr'][h, j])
            emu = evid_any(pf, f)
            out[off][0] += int(emu == bool(raw[h, j, X.F_PROM])); out[off][1] += 1
    return key, out, mism


if __name__ == '__main__':
    keys = ['Track00025', 'Track00001', 'Track00005', 'Track00020', 'Track00012', 'Track00040', 'Track00060']
    with mp.get_context('fork').Pool(7) as pool:
        res = pool.starmap(one, [(k,) for k in keys])
    for k, o, m in res:
        print(k, {off: f'{a}/{b} = {a / b:.4f}' for off, (a, b) in o.items()}, 'loop-vs-vec mismatches', m)

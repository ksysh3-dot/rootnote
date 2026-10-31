"""S19-O lib2 (after the Opus 19.2 review, see CHOICES.md addendum): phase-residual F arm, FIR realizable rows, crossfade mid dips, r1render rows."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
from s19o_lib import *
import s19o_lib as L1

_FIR = {}


def fir_kernel(fc, D):
    k = (fc, D)
    if k not in _FIR:
        n = 2001
        dl = np.zeros(n); dl[n // 2] = 1.0
        h = sosfiltfilt(L1._sos(fc), dl, padtype=None)[n // 2 - D:n // 2 + D + 1]
        _FIR[k] = h / h.sum()
    return _FIR[k]


def future_needed(fc):
    n = 4001
    dl = np.zeros(n); dl[n // 2] = 1.0
    h = np.abs(sosfiltfilt(L1._sos(fc), dl, padtype=None)); pk = h.max()
    out = {}
    for thr in (0.05, 0.01):
        idx = np.flatnonzero(h[n // 2:] > thr * pk)
        out[thr] = (idx.max() + 1) * HOPS * 1000 if len(idx) else 0.0
    return out


def smooth(x, fc, causal=False, D=None):
    n = len(x)
    line = np.linspace(x[0], x[-1], n)
    r = x - line
    if D is not None:
        h = fir_kernel(fc, D)
        rp = np.concatenate([np.zeros(D), r, np.zeros(D)])
        y = np.convolve(rp, h, 'valid')           # symmetric, centred; output q uses x[q-D .. q+D]
    else:
        pad = int(min(700, 3 * FSH / fc)) + 4
        rp = np.concatenate([np.zeros(pad), r, np.zeros(pad)])
        sos = L1._sos(fc)
        y = (sosfilt(sos, rp) if causal else sosfiltfilt(sos, rp, padtype=None))[pad:pad + n]
    y = y - np.linspace(y[0], y[-1], n)
    return line + y


def apply_sustain(r, fc, do_f, do_a, causal, D=None, dev=None):
    th, a2, a3 = r['th'].copy(), r['a2'].copy(), r['a3'].copy()
    for (s0, s1) in r['segs']:
        if do_f:
            x = th[s0 - 1:s1 + 1].copy()
            xn = smooth(x, fc, causal, D)
            if dev is not None:
                F = np.diff(x) / (2 * np.pi * HOPS); Fn = np.diff(xn) / (2 * np.pi * HOPS)
                dev['cent'].append(1200 * np.log2(np.maximum(Fn, 1e-6) / np.maximum(F, 1e-6)))
            th[s0 - 1:s1 + 1] = xn
        if do_a:
            for arr, nm in ((a2, 'a2'), (a3, 'a3')):
                seg = arr[s0:s1 + 1].copy()
                new = np.maximum(smooth(seg, fc, causal, D), 0.0)
                if dev is not None and nm == 'a2':
                    ok = (seg > 1e-7) & (new > 1e-7)
                    dev['db'].append(20 * np.log10(np.where(ok, new, 1.0) / np.where(ok, seg, 1.0))[ok])
                arr[s0:s1 + 1] = new
    return th, a2, a3


def xf_dips(r, of0, of1, T_ms, out):
    if len(of0) < 40:
        return
    m0 = sosfiltfilt(SOS_MID, of0); m1 = sosfiltfilt(SOS_MID, of1)
    N = int(round(T_ms * CFS / 1000.0)); w = np.ones(6) / 6
    p0 = np.convolve(m0 ** 2, w, 'valid'); p1 = np.convolve(m1 ** 2, w, 'valid')
    for e in r['xf']:
        s = 16 * (e - 1)
        a, b = s, min(s + N, len(p0))
        if b - a < 1:
            continue
        q0 = p0[a:b]; q1 = p1[a:b]
        eps = 1e-3 * q0.mean() + 1e-30
        out.append(float(np.min(10 * np.log10((q1 + eps) / (q0 + eps)))))


def recon_bands(d, cl, runs, variant, slots=None, dev=None, dips=None):
    """variant: ('base',), ('sus', fc, do_f, do_a, causal, D), ('xf', T)"""
    ih = cl['ih']
    y = np.zeros(int(ih.max()) + 64)
    for r in runs:
        if slots is not None and r['s'] not in slots:
            continue
        if variant[0] == 'sus':
            th, a2, a3 = apply_sustain(r, variant[1], variant[2], variant[3], variant[4], variant[5] if len(variant) > 5 else None, dev)
        else:
            th, a2, a3 = r['th'], r['a2'], r['a3']
        of = synth_run(r, th, a2, a3)
        if variant[0] == 'xf':
            of0 = of.copy() if (dips is not None and r['xf']) else None
            apply_xf(r, th, a2, a3, of, variant[1])
            if of0 is not None:
                xf_dips(r, of0, of, variant[1], dips)
        y[r['pos']] += of
    yl = sosfiltfilt(SOS_LO, y); ym = sosfiltfilt(SOS_MID, y)
    ix = ih[:, None] + J16[None, :]
    return (yl[ix] ** 2).sum(1), (ym[ix] ** 2).sum(1), y

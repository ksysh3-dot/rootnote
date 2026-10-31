"""Per-(voice, k) re-synthesis at the 3 kHz core rate from the voice trace (theta, psi_2/psi_3, amplitudes a_vk, linear interpolation
inside the hop, exactly the rule of ResultantCore::synthesize), the core output filter, then the lo (20-150 Hz) and mid (150-600 Hz)
zero-phase Butterworth bands at 3 kHz. psi of k >= 4 is not in the trace (set 0: it only changes cross terms, not the per-component
band power). Fade voices (pushed out of a full table) are not in the trace -> reported as the residual against the measured layer."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1/b12')
from b12_data import *
from scipy.signal import sosfilt

CFS = 3000
S3_LO = butter(4, [20, 150], 'bandpass', fs=CFS, output='sos')
S3_MID = butter(4, [150, 600], 'bandpass', fs=CFS, output='sos')
S3_OUT = OUT_SOS
HOPS_PRE = 120   # 0.64 s of pre-roll for filter settling


def synth(sk, eng, t0, t1, kmask=None, vmask=None):
    d = load(sk, eng); tr = d['tr']
    hop = tr['hop'][:, 0]
    ts = CA.hop_time(hop)[1]
    sel = np.where((ts >= t0) & (ts < t1))[0]
    i0 = max(sel[0] - HOPS_PRE, 1); i1 = sel[-1] + 1
    ix = np.arange(i0 - 1, i1)            # include the previous hop for the start values
    st = tr['state'][ix]; vid = tr['voice'][ix]; fo = tr['f_osc'][ix]; th = tr['theta_hat'][ix]
    base = tr['A'][ix] * tr['c'][ix] * tr['sigma'][ix]
    a = amplitudes(fo, np.where(st >= 1, base, 0.0), True, 1.0)        # (7, H, 8)
    psi = np.zeros((7,) + st.shape); psi[0] = tr['psi_2'][ix]; psi[1] = tr['psi_3'][ix]
    H = len(ix) - 1
    ids = np.unique(vid[1:][st[1:] >= 1])
    comp = {}
    for v in ids:
        for kk in range(2, 9):
            if kmask is not None and kk not in kmask: continue
            x = np.zeros(16 * H); has = False
            for s in range(8):
                for h in np.where((vid[:, s] == v) & (st[:, s] >= 1))[0]:
                    if h < 1: continue
                    if a[kk - 2, h, s] == 0 and (vid[h - 1, s] != v or st[h - 1, s] < 1 or a[kk - 2, h - 1, s] == 0): continue
                    cont = vid[h - 1, s] == v and st[h - 1, s] >= 1
                    a0 = a[kk - 2, h - 1, s] if cont else 0.0
                    p0 = psi[kk - 2, h - 1, s] if cont else psi[kk - 2, h, s]
                    t0_ = th[h - 1, s] if cont else th[h, s] - 2 * np.pi * fo[h, s] * 16 / CFS
                    dth = (th[h, s] - t0_) / 16.0
                    j = np.arange(16); tt = j / 16.0
                    a_ = a0 + (a[kk - 2, h, s] - a0) * tt
                    ang = kk * (t0_ + dth * j) + p0 + (psi[kk - 2, h, s] - p0) * tt
                    x[16 * (h - 1):16 * h] += a_ * np.cos(ang); has = True
            if has: comp[(int(v), kk)] = x
    hops = hop[ix[1:]]
    return dict(comp=comp, hops=hops, ts=ts[ix[1:]], sel_lo=int(np.searchsorted(ts[ix[1:]], t0)), sel_hi=int(np.searchsorted(ts[ix[1:]], t1)),
                st=st[1:], vid=vid[1:], fo=fo[1:], a=a[:, 1:], ix=ix[1:])


def band_hop_power(x, bands=('lo', 'mid')):
    """x: 3 kHz series. out filter, then zero-phase band; returns {band: hop powers (H,)}"""
    y = sosfilt(S3_OUT, x)
    out = {}
    for b in bands:
        z = sosfiltfilt(S3_LO if b == 'lo' else S3_MID, y)
        out[b] = (z ** 2).reshape(-1, 16).mean(1)
    return out


def total(sy):
    n = 16 * len(sy['hops'])
    x = np.zeros(n)
    for v in sy['comp'].values(): x += v
    return x

import re
p='/home/ksysh/r3a-dev/plan16/S19/s19_attr.py'
s=open(p).read()
s=s.replace("import p_primary as P\n","import p_primary as P\nfrom scipy.signal import butter, sosfiltfilt\nSOS3 = butter(4, [20, 150], 'bandpass', fs=3000, output='sos')\n",1)
# per-voice rebuilt band energy
s=s.replace("def attribute(d, boxes, box_sel):", '''def slot_energy(d):
    """B1-2 style per-voice reconstruction: k=2,3 of each slot rebuilt from the trace as ResultantCore::synthesize (A5P oracle_p.rebuild), 20-150 Hz zero-phase at 3 kHz,
    energy per hop output block (16 core samples). returns (H, S) float"""
    ih = d['hop'][:, 0].astype(np.int64); st = d['state']; vid = d['voice']; H, S = st.shape
    j16 = np.arange(16) / 16.0
    E = np.zeros((H, S))
    for s in range(S):
        y = np.zeros(int(ih.max()) + 64)
        act = st[:, s] >= 1; i = 0
        while i < H:
            if not act[i]:
                i += 1; continue
            j = i + 1
            while j < H and act[j] and vid[j, s] == vid[i, s]:
                j += 1
            if j - i >= 2:
                idx = np.arange(i, j)
                th = d['theta_hat'][idx, s].astype(np.float64); ps = [d['psi_2'][idx, s].astype(np.float64), d['psi_3'][idx, s].astype(np.float64)]
                am = [d['a_2'][idx, s].astype(np.float64), d['a_3'][idx, s].astype(np.float64)]
                for q in range(1, len(idx)):
                    t0 = np.remainder(th[q - 1] + np.pi, 2 * np.pi) - np.pi
                    dth = (th[q] - th[q - 1]) / 16.0
                    ph = t0 + dth * np.arange(16)
                    base = ih[idx[q]]
                    for kk, pp, a in ((2, ps[0], am[0]), (3, ps[1], am[1])):
                        if a[q] == 0 and a[q - 1] == 0:
                            continue
                        aa = a[q - 1] + (a[q] - a[q - 1]) * j16
                        y[base:base + 16] += aa * np.cos(kk * ph + pp[q - 1] + (pp[q] - pp[q - 1]) * j16)
            i = j
        if not np.any(y):
            continue
        yb = sosfiltfilt(SOS3, y)
        E[:, s] = (yb[ih[:, None] + np.arange(16)[None, :]] ** 2).sum(1)
    return E


def attribute(d, boxes, box_sel):''',1)
s=s.replace('''    wt = np.where(fo <= BAND_F, a2 ** 2, 0.0)
    wt = 0.5 * (wt + np.vstack([wt[:1], wt[:-1]]))''','''    wt = d['_E']''')
s=s.replace("inband = (fo <= BAND_F) | (fo0 <= BAND_F)","inband = np.ones_like(fo, bool)")
s=s.replace("z = np.load(f); d = {k: z[k] for k in z.files if k != 'box'}; boxes = z['box']","z = np.load(f); d = {k: z[k] for k in z.files if k != 'box'}; boxes = z['box']; d['_E'] = slot_energy(d)")
open(p,'w').write(s)
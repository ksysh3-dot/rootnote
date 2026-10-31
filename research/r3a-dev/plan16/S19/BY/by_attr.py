"""S19-BY items 2-3: voice attribution of the v1.6-c layer's 20-150 Hz energy in the top windows. numbers only.
usage: by_attr.py SONG  (needs cache/tr_hp8_150c1_SONG.npz and res/*.npz). B1-2 style per-slot rebuild of k=2,k=3 from the trace, with the layer HP (butter 8, 150 Hz, causal, |H|) applied
to the rebuilt partials ('post') or not ('pre'); band = P.SOS_LO zero-phase at 3 kHz as s19_attr.slot_energy."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/BY'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfilt, sosfiltfilt
import s19_attr as A
import by_rank as BR
BY = Path('/home/ksysh/r3a-dev/plan16/S19/BY')
SOS3 = A.SOS3
HP3 = butter(8, 150, 'highpass', fs=3000, output='sos')
db = lambda p: 10 * np.log10(np.maximum(p, 1e-30))


def rebuild(d):
    """per slot-hop energies (H,S) of the 16-sample output block for: pre k2, pre k3, pre k2+3, post k2, post k3, post k2+3 (post = causal HP8 150 before the 20-150 zero-phase band)"""
    ih = d['hop'][:, 0].astype(np.int64); st = d['state']; vid = d['voice']; H, S = st.shape
    j16 = np.arange(16) / 16.0
    E = np.zeros((6, H, S))
    for s in range(S):
        ys = [np.zeros(int(ih.max()) + 64) for _ in range(3)]
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
                    ph = t0 + dth * np.arange(16); base = ih[idx[q]]
                    for ki, (kk, pp, a) in enumerate(((2, ps[0], am[0]), (3, ps[1], am[1]))):
                        if a[q] == 0 and a[q - 1] == 0:
                            continue
                        aa = a[q - 1] + (a[q] - a[q - 1]) * j16
                        v = aa * np.cos(kk * ph + pp[q - 1] + (pp[q] - pp[q - 1]) * j16)
                        ys[ki][base:base + 16] += v; ys[2][base:base + 16] += v
            i = j
        for ci, y in enumerate(ys):
            if not np.any(y):
                continue
            for pi, sig in enumerate((y, sosfilt(HP3, y))):
                if MODE == '140':
                    fr = np.fft.rfftfreq(len(sig), 1 / 3000.0)
                    up = np.clip((fr - 15) / 10, 0, 1); dn = np.clip((145 - fr) / 10, 0, 1)
                    yb = np.fft.irfft(np.fft.rfft(sig) * (0.5 * (1 - np.cos(np.pi * up)) * 0.5 * (1 - np.cos(np.pi * dn))), len(sig))
                else:
                    yb = sosfiltfilt(SOS3, sig)
                E[pi * 3 + ci, :, s] = (yb[ih[:, None] + np.arange(16)[None, :]] ** 2).sum(1)
    return E


MODE = sys.argv[2] if len(sys.argv) > 2 else '150'


def main(song):
    z = np.load(BY / 'cache' / f'tr_hp8_150c1_{song}.npz'); d = {k: z[k] for k in z.files if k != 'box'}; box = z['box']
    if MODE == '140':
        box = np.load(BY / 'cache' / f'box140_{song}.npy')
    ef = BY / 'cache' / (f'E_{song}.npy' if MODE == '150' else f'E140_{song}.npy')
    if ef.exists():
        E = np.load(ef)
    else:
        E = rebuild(d); np.save(ef, E)
    ih = d['hop'][:, 0].astype(np.int64); H, S = d['state'].shape
    tc = (ih - 398 + 8) / 3000.0 + A.T0
    Dd = BR.derived(song)
    d['_E'] = E[5]   # post k2+3 weights
    ev_cache = {}
    sel_list = []
    for key in ('c_abs', 'exc'):
        for j in BR.pick(Dd, key):
            if j not in [x[0] for x in sel_list]:
                sel_list.append((j, key))
    fo = d['f_osc']; ft = d['f_track']; st = d['state']; vid = d['voice']
    nbox = len(box); tcb = (np.arange(nbox) + 0.5) * A.BOX / A.FS
    print(f'\n##### {song} #####  (E rebuilt: S={S} slots; window sets: abs-top8 and excess-top8, union)')
    allacc = dict(post=0.0, f75=0.0, pre=0.0, pre75=0.0)
    for j, key in sel_list:
        t0 = Dd['t0'][j]; t1 = t0 + 2.0
        hm = (tc >= t0) & (tc < t1)
        nsmp = hm.sum() * 16
        e = E[:, hm, :]
        ms = e.sum((1, 2)) / nsmp          # mean square per channel set
        real_ms = box[(tcb >= t0) & (tcb < t1)].sum() / (((tcb >= t0) & (tcb < t1)).sum() * A.BOX)
        on = (st[hm] >= 2)
        nv = on.sum(1)
        f75 = fo[hm] < 75.0
        post = e[5]; pre = e[2]
        tot = post.sum()
        sh75 = post[f75].sum() / max(tot, 1e-30)
        sh75pre = pre[f75].sum() / max(pre.sum(), 1e-30)
        # k=3 on purpose below 150: f<50 ; k=2: f<75
        k2_75 = e[3][f75].sum() / max(tot, 1e-30); k3_50 = e[4][fo[hm] < 50.0].sum() / max(tot, 1e-30)
        # voices
        vv = vid[hm]; fw = ft[hm]; fv = fo[hm]
        ids = np.unique(vv[post > 0])
        rows = []
        for v in ids:
            m = (vv == v) & (post > 0)
            if m.sum() == 0:
                continue
            rows.append((post[m].sum() / max(tot, 1e-30), v, np.median(fw[m]), np.median(fv[m]), m.sum() * 16 / 3000.0, e[3][m].sum() / max(post[m].sum(), 1e-30)))
        rows.sort(reverse=True)
        # lowest notes among ON voices: median f_track per voice (id), with duration
        lowrows = []
        for v in np.unique(vv[on & (fw > 0)]):
            m = on & (vv == v) & (fw > 0)
            if m.sum() >= 5:
                lowrows.append((np.median(fw[m]), m.sum() / 187.5, v))
        lowrows.sort()
        below100 = float(((fw > 0) & on & (fw < 100)).sum() / max(on.sum(), 1))
        # event attribution (box-level, 20-150 band of the real layer)
        bsel = (tcb >= t0) & (tcb < t1)
        full = np.zeros(nbox, bool); full[:] = False
        r, *_ = A.attribute(d, box, bsel)
        tb = max(r['total'], 1e-30)
        excl = ' '.join(f'{k}{100*v/tb:.0f}' for k, v in r['excl'].items() if v / tb >= 0.02)
        print(f'\n[{BR.mmss(t0)}] ({key}) c abs20-140 {Dd["c_abs"][j]:.1f} dBFS, P1 {Dd["p_abs"][j]:.1f}, exc {Dd["exc"][j]:+.1f}, input 20-150 {Dd["in_abs"][j]:.1f}')
        print(f'  voices ON per hop: mean {nv.mean():.1f} max {nv.max()}; ON-voice-hops with f_track<100 Hz: {100*below100:.0f}%')
        print('  lowest voices (median f_track Hz / s present / id): ' + '; '.join(f'{a:.1f}/{b:.2f}s' for a, b, c in lowrows[:4]))
        print(f'  rebuild ms(20-150, 3k) dBFS: real layer {db(real_ms):.1f} | post k2+3 {db(ms[5]):.1f} (k2 {db(ms[3]):.1f}, k3 {db(ms[4]):.1f}) | pre k2+3 {db(ms[2]):.1f} (k2 {db(ms[0]):.1f}, k3 {db(ms[1]):.1f}); rebuild-post minus real {db(ms[5])-db(real_ms):+.1f} dB')
        print('  top voices by post-HP share: ' + '; '.join(f'{100*a:.0f}% f_track {b:.0f} f_osc {c_:.0f} {dd:.2f}s k2frac {100*k:.0f}%' for a, v, b, c_, dd, k in rows[:4]))
        print(f'  share of post-HP rebuilt energy from voices with 2*f_osc<150 (f_osc<75): {100*sh75:.0f}% (pre-HP {100*sh75pre:.0f}%); k2 of f_osc<75 {100*k2_75:.0f}%, k3 of f_osc<50 {100*k3_50:.0f}%')
        bins = [(0, 60), (60, 75), (75, 100), (100, 130), (130, 1e9)]
        print('  post-HP rebuilt energy share by voice f_osc bin (<60/60-75/75-100/100-130/>=130): ' + ' '.join(f'{100*post[(fv >= a) & (fv < b)].sum()/max(tot,1e-30):.0f}%' for a, b in bins))
        print(f'  event attribution of real 20-150 box energy (% excl): no-event {100*r["noevent"]/tb:.0f}%, no-voice {100*r["novoice"]/tb:.0f}%, none&f<=75 {100*r["none_direct"]/tb:.0f}%; event types >=2%: {excl}')
        allacc['post'] += tot; allacc['f75'] += post[f75].sum(); allacc['pre'] += pre.sum(); allacc['pre75'] += pre[f75].sum()
    print(f'\n{song} all listed windows pooled: post-HP share from f_osc<75 voices {100*allacc["f75"]/allacc["post"]:.0f}%, pre-HP {100*allacc["pre75"]/allacc["pre"]:.0f}%')


if __name__ == '__main__':
    main(sys.argv[1])

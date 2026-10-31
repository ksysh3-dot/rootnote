"""S19-O (e): lag cost of causal vs zero-phase sustain smoothing of F on synthetic glide / vibrato (A5P/fosc_p.py signals), row f4.
Estimate = F_q (oscillator increment of block q) of the dominant ON voice, truth at block-centre input time; octave-folded; sustain segmentation as CHOICES.md."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import numpy as np
from s19o_lib import *
import fosc_p as FP
S = FP.S
KEEP = A_KEEP = ['hop', 'voice', 'state', 'f_track', 'f_osc', 'A', 'c', 'sigma', 'Np', 'a_2', 'a_3', 'theta_hat', 'psi_2', 'psi_3']
FCS = [4, 8, 16, 32]


def Fmat(d, runs, fc=None, causal=False):
    H, Sn = d['state'].shape
    F = np.full((H, Sn), np.nan); inseg = np.zeros((H, Sn), bool)
    for r in runs:
        th = r['th']; Fr = np.full(len(th), np.nan); Fr[1:] = (th[1:] - th[:-1]) / (2 * np.pi * HOPS)
        ins = np.zeros(len(th), bool)
        for s0, s1 in r['segs']:
            ins[s0:s1 + 1] = True
            if fc:
                x = Fr[s0:s1 + 1].copy(); xs = smooth(x, fc, causal); dd = xs - x; dd -= dd.mean(); Fr[s0:s1 + 1] = x + dd
        F[r['idx'], r['s']] = Fr; inseg[r['idx'], r['s']] = ins
    return F, inseg


def run_sig(name, snr):
    fn, dur, win = FP.SIGS[name]
    x = FP.synth(fn, dur)
    if snr:
        x = x + S.pink_for_band_snr(x, snr)
    X = S.stereo(x).astype(np.float32)
    lay, tr = P.render_song(X, 'f4')
    d = {k: tr[k] for k in KEEP}
    d['hop'] = tr['hop']
    ih = d['hop'][:, 0].astype(np.int64)
    ev, _ = A.events(d)
    cl = dict(ev=ev, ih=ih)
    runs = make_runs(d, cl)
    tcb = (ih - 398 + 8) / 3000.0 + A.T0
    w = (d['A'].astype(float) * d['c'] * d['sigma']) ** 2 * (d['state'] == 2)
    top = np.argmax(w, 1); has = w[np.arange(len(ih)), top] > 0
    sel = has & (tcb >= win[0]) & (tcb < win[1])
    truth = fn(tcb)
    res = {}
    def ev_(F, inseg):
        Ft = F[np.arange(len(ih)), top]
        m = sel & np.isfinite(Ft) & (Ft > 0)
        e = 1200 * np.log2(Ft[m] / truth[m]); e = e - 1200 * np.round(e / 1200)
        ins = inseg[np.arange(len(ih)), top][m]
        return dict(med_abs=float(np.median(np.abs(e))), med_signed=float(np.median(e)), p90_abs=float(np.percentile(np.abs(e), 90)), n=int(m.sum()), frac_in_seg=float(ins.mean()),
                    med_abs_inseg=float(np.median(np.abs(e[ins]))) if ins.any() else None)
    F0, ins0 = Fmat(d, runs)
    res['raw'] = ev_(F0, ins0)
    for fc in FCS:
        for tag, cs in (('zp', False), ('ca', True)):
            F, ins = Fmat(d, runs, fc, cs)
            res[f'{tag}{fc}'] = ev_(F, ins)
    return res


if __name__ == '__main__':
    out = {}
    for nm in FP.SIGS:
        for snr in (None, 25.0):
            k = f'{nm}|{"clean" if snr is None else "snr25"}'
            out[k] = run_sig(nm, snr)
            print(k, {v: (round(r['med_abs'], 1), round(r['med_signed'], 1)) for v, r in out[k].items()}, flush=True)
    json.dump(out, open(O_DIR / 'synth_e.json', 'w'), indent=1)

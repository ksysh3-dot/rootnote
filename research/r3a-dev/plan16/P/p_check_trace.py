"""Extra validity evidence (added after p_main, flagged as such): does the captured-layer E_sil (time-silent, all pitches) agree with the
SAME time-silent energy measured on the 16.9 trace-based layer (voices shifted by LAGS, 3 kHz synthesis, kappa-free: raw band energy)?
This separates 'the output capture is wrong' from 'V6b silence wrong_sa counts only wrong-pitch energy of silence-class voices'.
usage: bash ~/r3a-dev/plan16/D/runpy.sh ~/r3a-dev/plan16/P/p_check_trace.py -> p_check_trace.txt"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
import multiprocessing as mp
from scipy.signal import butter, sosfiltfilt
from scipy.stats import spearmanr
import dcommon as DC
from dcommon import *
import p_main as PM

SOS3 = butter(4, (150.0, 700.0), 'bandpass', fs=3000, output='sos')
P_DIR = PM.P_DIR


def one(key):
    sig = Sig(key); mk = PM.song_masks(key)
    n3 = int(30 * FSC)
    t3 = np.arange(n3) / FSC
    act3 = mk['main'][::16][:n3]
    out = {}
    for algo, rowf, lagk, name in ((15, R.voices_core, 'core', 'core'), (6, R.voices_p1, 'p1', 'p1')):
        vo = E.shift(rowf(sig), LAGS[lagk])
        Y = render_multi(vo, 30.3, lambda v, tt, f, a: np.zeros(len(tt), int), 1)[0]
        e = sosfiltfilt(SOS3, Y)[:n3] ** 2
        ok = t3 >= 4.0
        out[name] = dict(E_sil=float(e[ok & ~act3].sum()), E_act=float(e[ok & act3].sum()))
    return key, out


if __name__ == '__main__':
    with mp.get_context('fork').Pool(10) as pool:
        tr = dict(pool.map(one, PM.SONGS))
    raw = json.load(open(P_DIR / 'p_raw.json'))['res']
    L = ['# trace-based (16.9 layer) vs captured layer: time-silent band energy, t >= 4 s (raw units; trace = 3 kHz synthesis scale, captured*kappa)']
    ks = PM.SONGS
    for name in ('core', 'p1'):
        a = np.array([PM.KAPPA * raw[k][name]['t4_main']['E_sil'] for k in ks]); b = np.array([tr[k][name]['E_sil'] for k in ks])
        L.append(f'{name}: Spearman(captured E_sil, trace-layer E_sil) = {spearmanr(a, b)[0]:.3f}; pooled ratio captured*kappa / trace = {a.sum() / b.sum():.3f}')
        L.append('  song: captured*kappa | trace  ' + '; '.join(f'{k[-2:]}: {x:.3f} | {y:.3f}' for k, x, y in zip(ks, a, b)))
        ea = np.array([PM.KAPPA * raw[k][name]['t4_main']['E_act'] for k in ks]); eb = np.array([tr[k][name]['E_act'] for k in ks])
        L.append(f'  E_act: pooled ratio {ea.sum() / eb.sum():.3f}; rho trace-layer pooled = {b.sum() / eb.sum():.4f} (captured {a.sum() / ea.sum():.4f})')
    c = np.array([tr[k]['core']['E_sil'] for k in ks]); p = np.array([tr[k]['p1']['E_sil'] for k in ks])
    ce = np.array([tr[k]['core']['E_act'] for k in ks]); pe = np.array([tr[k]['p1']['E_act'] for k in ks])
    L.append(f'trace-layer rho pooled: core {c.sum() / ce.sum():.4f}, P1 {p.sum() / pe.sum():.4f}, r = {(p.sum() / pe.sum()) / (c.sum() / ce.sum()):.3f}')
    V = json.load(open(HOME / 'r3a-dev/plan16/V/v_raw.json'))
    v69 = np.array([V[k]['E_sil'] for k in ks])
    L.append(f'Spearman(trace-layer time-silent E_sil (core), 16.9 silence wrong_sa) = {spearmanr(c, v69)[0]:.3f}  (same definitional gap, trace side)')
    open(P_DIR / 'p_check_trace.txt', 'w').write('\n'.join(L)); print('\n'.join(L))

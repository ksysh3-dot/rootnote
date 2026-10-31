"""Signals, stream loading and the trace-based layer PROXY used by Q8/Q9.
Proxy layer amplitude per hop = sqrt(sum over voices of (a_2^2 + a_3^2) * s_v^2) where a_2, a_3 are the trace's synthesised harmonic amplitudes (they contain
A c sigma) and s_v the candidate's amplitude scale (A_new/A).  The layer follows the trace at layer_time = hop_centre_time + LAG (LAG = -9 ms, Q5 correlation).
This is NOT a re-synthesis; the baseline proxy is always reported next to the real layer metric so the calibration is visible."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S

FS = X.FS
LAG = -0.009
STEP_NOTES, STEP_DUR = X.STEP_NOTES, X.STEP_DUR
PER = 2 * STEP_DUR
TPK = float(np.abs(np.sin(np.linspace(0, 2 * np.pi, 400001)) + .5 * np.sin(2 * np.linspace(0, 2 * np.pi, 400001)) + .18 * np.sin(3 * np.linspace(0, 2 * np.pi, 400001))).max())
SCALE = .25 / TPK


def bandp(s, mask=None):
    return float(np.mean((X.band_fft(s, 80, 200) ** 2)[mask] if mask is not None else X.band_fft(s, 80, 200) ** 2))


def pink_for(sig, snr_db, mask=None, seed=1):
    n = len(sig); n += n % 2
    rng = np.random.default_rng(seed); fr = np.fft.rfftfreq(n, 1 / FS)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(fr, 20)), n); w = (w / np.sqrt(np.mean(w ** 2)))[:len(sig)]
    g = np.sqrt(bandp(sig, mask) / (bandp(w) * 10 ** (snr_db / 10.0)))
    return g * w


def sig_step_line(snr=25.0):
    m = int(round(STEP_DUR * FS)); nn = len(STEP_NOTES)
    clean = np.zeros(int(round(nn * PER * FS))); on = np.zeros(len(clean), bool)
    for i, f in enumerate(STEP_NOTES):
        n0 = int(round(i * PER * FS)); clean[n0:n0 + m] = X._note(f, m, SCALE); on[n0:n0 + m] = True
    n = max(10 * FS, len(clean)); n += n % 2
    pk = pink_for(np.zeros(n), 0) if False else None
    rng = np.random.default_rng(1); fr = np.fft.rfftfreq(n, 1 / FS)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(fr, 20)), n); w = (w / np.sqrt(np.mean(w ** 2)))[:len(clean)]
    g = np.sqrt(bandp(clean, on) / (bandp(w) * 10 ** (snr / 10.0)))
    return clean + g * w, [i * PER for i in range(nn)]


def sig_bare():
    x = np.zeros(int(3.5 * FS)); x[int(.5 * FS):int(1.5 * FS)] = X._note(100.0, int(1.0 * FS), SCALE)
    return x, [0.5]


def sig_bass_kick_pink(kick_shift=0.0, secs=8.0):
    bass, scale, _ = X.bass_sig(secs); pk = X.pink_gf(secs); kick = X.kick_sig(secs)
    if kick_shift:
        kick = np.roll(kick, int(kick_shift * FS))
    return bass + .2 * kick + pk, [0.5 * n for n in range(int(secs / .5))], [0.5 * n + kick_shift for n in range(int(secs / .5))], bass


def sig_bass_pink_snr(snr=6.0, secs=8.0):
    bass, _, _ = X.bass_sig(secs)
    return bass + pink_for(bass, snr), [0.5 * n for n in range(int(secs / .5))]


def sig_steady(snr=8.0, secs=10.0):
    t = np.arange(int(secs * FS)) / FS
    x = (np.sin(2 * np.pi * 100 * t) + .5 * np.sin(2 * np.pi * 200 * t) + .18 * np.sin(2 * np.pi * 300 * t)) * (10 ** (-12 / 20) / TPK) * np.minimum(t / .008, 1)
    return x + pink_for(x, snr), []


def load(key, x):
    s = S.get(key, x)
    d, hop, tc = X.hops_of(s['trace'])
    raw = np.asarray(s['trace']).reshape(-1, 8, 22)
    return dict(bh=s['bh'], det=s['det'], d=d, raw=raw, tc=tc, hop=hop.astype(np.int64), st=d['state'])


def prev_freq_table(D):
    """f_b of every voice-hop: the previous hop's f_osc of the same voice id (what the LS basis used), current f_osc when new"""
    d, st = D['d'], D['st']; H = len(D['tc'])
    fb = d['fosc'].copy(); prev = {}
    for h in range(H):
        cur = {}
        for j in range(8):
            if st[h][j] > 0:
                v = int(d['voice'][h][j]); fb[h, j] = prev.get(v, d['fosc'][h][j]); cur[v] = d['fosc'][h][j]
        prev = cur
    return fb


def proxy_amp(D, scale=None):
    """per-hop proxy layer amplitude and the 300-Hz (third harmonic of ~100 Hz voices) amplitude"""
    d = D['d']; st = D['st']
    a2 = np.where(st > 0, d['a2'], 0.0); a3 = np.where(st > 0, d['a3'], 0.0)
    s = np.ones_like(a2) if scale is None else scale
    p = ((a2 ** 2 + a3 ** 2) * s ** 2)
    return np.sqrt(p.sum(axis=1)), p


def env_at(tc, v, dur, dt=0.001):
    tt = np.arange(0, dur, dt)
    return tt, np.interp(tt - LAG, tc, v)           # layer(t) = trace(t - LAG) [layer_time = tc + LAG]


def v3h_gated(tt, env, notes=range(2, 40)):
    rise, tail, last = [], [], []
    for i in notes:
        t0 = i * PER
        refv = float(np.mean(env[int((t0 + .06) / (tt[1] - tt[0])):int((t0 + .11) / (tt[1] - tt[0]))]))
        k0 = int(t0 / (tt[1] - tt[0])); k1 = int((t0 + .125) / (tt[1] - tt[0]))
        seg = env[k0:k1]; ok = seg >= .9 * refv
        rise.append(float(np.argmax(ok) * (tt[1] - tt[0]) * 1000) if ok.any() and refv > 1e-9 else np.inf)
        sg = env[k1:k1 + int(.12 / (tt[1] - tt[0]))]; ok = sg <= .1 * refv
        tail.append(float(np.argmax(ok) * (tt[1] - tt[0]) * 1000) if ok.any() and refv > 1e-9 else np.inf)
        ab = np.flatnonzero(sg > .1 * refv)
        last.append(float((ab[-1] + 1) * (tt[1] - tt[0]) * 1000) if len(ab) else 0.0)
    return np.array(rise), np.array(tail), np.array(last)


def stat(v):
    v = np.asarray(v, float); f = v[np.isfinite(v)]
    return f'median {np.median(f):.1f} [p10 {np.percentile(f,10):.1f}, p90 {np.percentile(f,90):.1f}]' if len(f) else 'n/a'

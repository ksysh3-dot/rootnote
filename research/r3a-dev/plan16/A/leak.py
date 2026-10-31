"""16.1 leak test.  x1 = a TRAIN excerpt (real music); x2_i = identical samples up to T, then four different suffixes (kick, other note, silence, noise).
The full chain is rerun for every signal: engine capture (bh, det streams), P1 tracker trace (reference build), LA (L = 64 and 217; streams bh and det),
the trained classifier decisions (models trained on the 5 TRAIN songs, identical for all signals), and the synthesized 3 kHz layer (k = 2..8, before resampling).
Pass: |layer(x1) - layer(x2_i)| <= 1e-9 for every output time t <= T - L.  First-divergence times (re T) of every stage are reported.
The oracle row is non-causal by construction (label = whole-interval majority) and is not tested.
usage (from diag16): ./run.sh ../plan16/A/leak.py [--song Track00060 --start 20 --dur 14 --T 7]"""
import sys, time, json, argparse, os
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import multiprocessing as mp
import numpy as np
from data import *
import la, classify, rows as R, pipeline as P
import synth16 as S
from data import stream_time

OUTD = HOME / 'r3a-dev/plan16/A'
CACHE_L = OUTD / 'cache_leak'; CACHE_L.mkdir(exist_ok=True)
TOL = 1e-9
LAG = 191


class FSig:
    def __init__(self, bh, det, tc1, ts):
        self.bh, self.det, self.tc1, self.ts = bh, det, tc1, ts
        self.nhop = len(tc1)

    def stream(self, name):
        return self.bh if name == 'bh' else self.det


def make_signals(song, start, dur, Tsec):
    x = X.read_excerpt(X.SLAKH / song / 'mix.flac', start, dur); guard(X.SLAKH / song)
    n = len(x); iT = int(round(Tsec * FS)); suffix_n = n - iT
    t = np.arange(suffix_n) / FS
    rng = np.random.default_rng(0)
    # big kicks every 0.5 s (60 Hz body, swept from ~120 Hz, 80 ms decay), first at T + 50 ms
    kick = np.zeros(suffix_n)
    for k in range(int(suffix_n / FS / 0.5) + 1):
        t0 = 0.05 + 0.5 * k
        if t0 * FS >= suffix_n:
            break
        i0 = int(t0 * FS); tt = np.arange(suffix_n - i0) / FS
        f = 50 + 70 * np.exp(-tt / 0.03); ph = 2 * np.pi * np.cumsum(f) / FS
        kick[i0:] += 0.9 * np.sin(ph) * np.exp(-tt / 0.08)
    # a different note: E1 (41.2 Hz) with harmonics, onset 20 ms after T, 5 ms ramp
    f0 = 41.2; env = np.clip((t - 0.02) / 0.005, 0, 1)
    note = 0.25 * env * (np.sin(2 * np.pi * f0 * t) + .5 * np.sin(2 * np.pi * 2 * f0 * t) + .3 * np.sin(2 * np.pi * 3 * f0 * t))
    noise = 0.1 * rng.standard_normal(suffix_n)
    sufs = dict(kick=kick, note=note, silence=np.zeros(suffix_n), noise=noise)
    sigs = dict(orig=x.copy(), orig_repeat=x.copy())
    for k, s in sufs.items():
        y = x.copy(); y[iT:, 0] = s; y[iT:, 1] = s
        sigs[k] = np.clip(y, -1, 1).astype(np.float32)
    assert all(np.array_equal(v[:iT], x[:iT]) for v in sigs.values())
    return sigs, iT


def front_end(name, x2):
    """engine capture (bh, det) + P1 reference tracker trace, cached"""
    p = CACHE_L / f'fe_{name}.npz'
    if p.exists():
        z = np.load(p); return z['bh'], z['det'], z['tc1'], z['ts']
    import research_core_metrics as M
    from vb_quality.stage_capture import INDEX as SI
    ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
    r = ctx.render(name, x2, 0.0, voice=False, stage=True)
    st = r['stage']
    core = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
    bh = np.zeros(core.max() + 1); det = np.zeros_like(bh)
    bh[core] = st[:, SI['selected_h']]; det[core] = st[:, SI['band_delayed191']]
    tc1, ts = X.p1_harmonic(X.open_lib(X.REF), x2)
    np.savez_compressed(p, bh=bh, det=det, tc1=tc1, ts=ts)
    return bh, det, tc1, ts


_MODELS = {}


def layers_for(name, x2, dur):
    bh, det, tc1, ts = front_end(name, x2)
    sig = FSig(bh, det, tc1, ts)
    out = {}
    for stream in ('bh', 'det'):
        for L in (64, 217):
            res = la.run_la(sig, stream, L, LAG)
            F = classify.interval_features(sig, res)
            p = classify.predict(_MODELS[(stream, L)][0], F) if len(F) else np.zeros(0)
            on = p >= 0.5
            out[f'{stream}-{L}-clf'] = S.render_layer16(R.voices_la(res, on), dur)
            out[f'{stream}-{L}-all'] = S.render_layer16(R.voices_la(res, None), dur)
    return dict(bh=bh, det=det, tc1=tc1, ts=ts, layers=out)


def job(args):
    name, x2, dur = args
    p = CACHE_L / f'res_{name}.npz'
    if p.exists():
        z = np.load(p, allow_pickle=True); return name, z['d'].item()
    d = layers_for(name, x2, dur)
    np.savez_compressed(p, d=np.array(d, dtype=object))
    return name, d


def first_div(a, b, tol):
    n = min(len(a), len(b)); df = np.abs(a[:n] - b[:n]); idx = np.flatnonzero(df > tol)
    return (int(idx[0]) if len(idx) else None), float(df.max()) if n else 0.0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--song', default='Track00060'); ap.add_argument('--start', type=float, default=20.0)
    ap.add_argument('--dur', type=float, default=14.0); ap.add_argument('--T', type=float, default=7.0); ap.add_argument('--tag', default=''); ap.add_argument('--trklag', type=int, default=191)
    a = ap.parse_args()
    global LAG
    LAG = a.trklag
    if LAG != 191:
        a.tag += f'_lag{LAG}'
    t0 = time.time()
    sigs, iT = make_signals(a.song, a.start, a.dur, a.T)
    Tsec = iT / FS; dur = len(sigs['orig']) / FS
    for s in ('bh', 'det'):
        for L in (64, 217):
            _MODELS[(s, L)] = P.train_models(s, L, 191)
    names = list(sigs)
    tag = f'{a.song}_{int(a.start)}_{int(a.T)}{a.tag}'
    jobs = [(f'{tag}_{n}', sigs[n], dur) for n in names]
    res = {}
    with mp.get_context('fork').Pool(len(jobs)) as pool:
        for n, d in pool.imap_unordered(job, jobs):
            res[n.replace(tag + '_', '')] = d
    print('computed', round(time.time() - t0, 1), flush=True)
    rep = dict(song=a.song, start=a.start, T=Tsec, dur=dur, tol=TOL, checks={})
    # determinism baseline
    a0, a1 = res['orig'], res['orig_repeat']
    det_ok = bool(np.array_equal(a0['bh'], a1['bh']) and np.array_equal(a0['det'], a1['det']) and np.array_equal(a0['ts'], a1['ts']) and
                  all(np.array_equal(a0['layers'][k], a1['layers'][k]) for k in a0['layers']))
    rep['determinism_bitwise_identical'] = det_ok
    print('determinism (x1 vs x1 re-rendered) bitwise identical:', det_ok)
    for sname in ('kick', 'note', 'silence', 'noise'):
        b = res[sname]; c = {}
        # streams: first divergent stream sample -> input time re T
        for st in ('bh', 'det'):
            i, mx = first_div(a0[st], b[st], 0.0)
            c[f'stream_{st}_first_div_ms_re_T'] = None if i is None else float((stream_time(i) - Tsec) * 1000)
        # tracker hops: first hop whose track array differs; hop centre minus T
        n = min(len(a0['tc1']), len(b['tc1']))
        dif = np.flatnonzero([not np.array_equal(a0['ts'][h], b['ts'][h]) for h in range(n)])
        c['tracker_first_div_hop_centre_ms_re_T'] = None if not len(dif) else float((a0['tc1'][dif[0]] - Tsec) * 1000)
        for key in a0['layers']:
            stream, L, kind = key.split('-'); L = int(L)
            y1, y2 = a0['layers'][key], b['layers'][key]
            lim = int(np.floor((Tsec - L / 1000.0) * FSC)) + 1                   # samples with t <= T - L
            mx_allowed = float(np.max(np.abs(y1[:lim] - y2[:lim])))
            i, mx = first_div(y1, y2, TOL)
            c[f'layer_{key}'] = dict(pass_=bool(mx_allowed <= TOL), max_abs_diff_t_le_T_minus_L=mx_allowed, first_div_ms_re_T=None if i is None else float((i / FSC - Tsec) * 1000),
                                     first_div_ms_re_T_minus_L=None if i is None else float((i / FSC - (Tsec - L / 1000.0)) * 1000), layer_peak=float(np.max(np.abs(y1))))
        rep['checks'][sname] = c
    json.dump(rep, open(OUTD / f'leak_{tag}.json', 'w'), indent=1)
    print(json.dumps(rep, indent=1)[:6000])


if __name__ == '__main__':
    main()

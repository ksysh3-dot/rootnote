"""16.3 oracle ladder R0-R3 (+ P1 reference, + information row R2s).  Readings: CHOICES.md (written before this was run).
usage (from diag16):  ./run.sh ../plan16/A/ladder.py            -> plan16/A/ladder_raw.json  (all numbers; ladder_report.py makes the tables/decision)"""
import sys, time, json, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import *
import la, classify, labels, rows as R, metrics as MT, pipeline as P, evaluate as E
import synth16 as S
from stems import stem_streams

OUTD = HOME / 'r3a-dev/plan16/A'
SONGS = list(C.TRACKS); assert SONGS == TRAIN + EVAL
KEYS = SONGS + ['t60_36_48']
L_RS = 191 / 3.0            # N_f = 191, D = 0
T_MIN = 0.5
I_MIN = int(T_MIN * FSC)
ROWS = ['P1', 'R0', 'R1', 'R2', 'R3', 'R2s']
LAGS = E.load_lags()


def song_name(key):
    return 'Track00060' if key == 't60_36_48' else key


def song_off(key):
    return 36.0 if key == 't60_36_48' else 0.0


def dur_of(key):
    return 12.0 if key == 't60_36_48' else 30.0


# ------------------------------------------------------------------------------------------ truth segments
def segments(key):
    """lowest-bass-note segments in EXCERPT time: list of dict(s, e, f, attack, note)"""
    rf = C.ref(song_name(key)); off = song_off(key); dur = dur_of(key)
    ss, es, ps = rf['ss'] - off, rf['es'] - off, rf['ps']
    idx = np.flatnonzero((es > 0) & (ss < dur))
    if not len(idx):
        return [], rf
    b = np.unique(np.clip(np.r_[ss[idx], es[idx], 0.0, dur], 0.0, dur))
    segs = []
    for a, c in zip(b[:-1], b[1:]):
        if c - a < 1e-6:
            continue
        mid = 0.5 * (a + c)
        snd = idx[(ss[idx] <= mid) & (mid < es[idx])]
        if not len(snd):
            continue
        low = snd[np.argmin(ps[snd])]
        segs.append([a, c, int(low)])
    merged = []
    for s in segs:
        if merged and merged[-1][2] == s[2] and abs(merged[-1][1] - s[0]) < 1e-6:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    out = []
    for a, c, n in merged:
        f = 440 * 2 ** ((ps[n] + rf['tp'] - 69) / 12)
        out.append(dict(s=float(a), e=float(c), f=float(f), attack=bool(abs(ss[n] - a) < 1e-6), note=n))
    return out, rf


class StrictTruth(labels.Truth):
    """right iff within 50 cent of 0.5/1/2/3 x the lowest sounding bass note"""
    def __init__(self, tc, segs):
        self.tc = np.asarray(tc); self.cache = {}; self.ok = True
        S_ = np.array([s['s'] for s in segs]); E_ = np.array([s['e'] for s in segs]); F_ = np.array([s['f'] for s in segs])

        def fn(t):
            m = (S_ <= t) & (t < E_)
            return F_[m][:1] if m.any() else np.zeros(0)
        self.fn_at = fn


# ------------------------------------------------------------------------------------------ oracle LS rows
def oracle_voices(sig, x, segs, intervals=None):
    """R2/R3: one constant-f chunk per truth segment, LS with N_p 320, N_f 191 on stream x, clipped to the interval (MIDI segment, or `intervals` if given)"""
    if not len(segs):
        return []
    chunks, ivs = [], []
    nx = len(x)
    for i, sg in enumerate(segs):
        s, e = (sg['s'], sg['e']) if intervals is None else intervals[i]
        if e <= s:
            continue
        ch = la.Chunk(); ch.cid = len(chunks); ch.id = i
        ch.tc = np.array([s - 0.2, e + 0.2]); ch.f = np.array([sg['f'], sg['f']])
        la.prepare_chunk(ch, nx, L_RS, 191)
        j_on = int(round(float(stream_index(s)))); j_off = int(round(float(stream_index(e))))
        if j_off - j_on < la.GRID_A // 2:
            continue
        chunks.append(ch)
        ivs.append(dict(ch=ch, cid=ch.cid, j_on=j_on, j_off=j_off, ivid=len(ivs), seg=i))
    la.solve_amplitudes(sig, x, chunks, ivs, L_RS, 191)
    for iv in ivs:
        la.smooth(iv, L_RS)
    return R.voices_la(dict(ivs=ivs, L_ms=L_RS), None)


def stem_activity(segs, stem_bh):
    """per segment: stem on / off times (excerpt time) from the stem envelope, and the peak; returns arrays"""
    env = np.sqrt(np.convolve(stem_bh ** 2, np.ones(30) / 30, 'same'))
    tj = stream_time(np.arange(len(env)))
    p95 = float(np.percentile(env[I_MIN:], 95)) if len(env) > I_MIN else 1.0
    out = []
    for k, sg in enumerate(segs):
        prev_e = segs[k - 1]['e'] if k else -1e9
        next_s = segs[k + 1]['s'] if k + 1 < len(segs) else 1e9
        lo = max(sg['s'] - 0.150, prev_e); hi = min(sg['e'] + 0.500, next_s)
        w_in = (tj >= sg['s']) & (tj <= sg['e'])
        if not w_in.any():
            out.append(dict(on=sg['s'], off=sg['e'], peak=0.0, active=False)); continue
        i_pk = np.flatnonzero(w_in)[np.argmax(env[w_in])]
        P_ = env[i_pk]
        w = np.flatnonzero((tj >= lo) & (tj <= hi))
        ok = env[w] >= P_ * 0.1
        pos = int(np.flatnonzero(w == i_pk)[0])
        a = pos
        while a > 0 and ok[a - 1]:
            a -= 1
        b = pos
        while b < len(w) - 1 and ok[b + 1]:
            b += 1
        out.append(dict(on=float(tj[w[a]]), off=float(tj[w[b]]), peak=float(P_), active=bool(P_ >= p95 * 1e-2)))
    return out


# ------------------------------------------------------------------------------------------ measuring a voice list
def make_split(truth, tc, lag):
    def split(v, tt, f, a):
        t0 = tt - lag
        h = np.clip(np.rint((t0 - tc[0]) / HOP_S).astype(int), 0, len(tc) - 1)
        uh, inv = np.unique(h, return_inverse=True)
        fh = np.interp(tc[uh], v['t'], v['f'])
        wr = truth.wrong(uh, fh)
        return ~wr[inv]
    return split


def attack_list(segs, rf, off, dur):
    """gap attacks (no bass note sounding in [t0-150 ms, t0)) and the other attacks / fall-throughs"""
    ss, es = rf['ss'] - off, rf['es'] - off
    gap, leg, fall = [], [], []
    for sg in segs:
        t0 = sg['s']
        if not (0.6 <= t0 <= dur - 0.3):
            continue
        if not sg['attack']:
            fall.append(t0); continue
        before = (ss < t0 - 1e-6) & (es > t0 - 0.150)
        (leg if before.any() else gap).append(t0)
    return np.array(gap), np.array(leg), np.array(fall)


def pre_rise(y3, t0s):
    p = y3 ** 2
    pf = max(float(np.percentile(p, 90)) * 1e-6, 1e-30)
    c = np.concatenate([[0.0], np.cumsum(p)])
    def mean_p(a, b):
        i0, i1 = int(round(a * FSC)), int(round(b * FSC))
        return max((c[i1] - c[i0]) / max(i1 - i0, 1), pf)
    return np.array([10 * np.log10(mean_p(t - .030, t) / mean_p(t - .150, t - .050)) for t in t0s])


def v5a_of(y3, dur):
    y = R.up48(y3)
    n = int((dur + 0.3) * FS)
    y = np.pad(y, (0, max(0, n - len(y))))[:n]
    r5 = MT.v5a(y)
    return r5


def measure(voices_unshifted, lag, sig, truths, dur, attacks):
    """layer energies (right / wrong per truth), V6b per truth, pre-echo, V5a (caller), layer"""
    vt = E.shift(voices_unshifted, lag)
    out = {}
    yfull = None
    for tn, truth in truths.items():
        yr, yw = S.render_layer16(vt, dur + 0.3, split=make_split(truth, sig.tc1, lag))
        if yfull is None:
            yfull = yr + yw
        out[tn] = dict(E_right=float(np.sum(yr[I_MIN:] ** 2)), E_wrong=float(np.sum(yw[I_MIN:] ** 2)))
        vb = P.v6b_row(voices_unshifted, sig.tc1, truth)
        out[tn].update(v6b_wrong=vb['wrong'], v6b_right=vb['right'])
    out['y3'] = yfull
    out['E_full'] = float(np.sum(yfull[I_MIN:] ** 2))
    gap, leg, fall = attacks
    out['pre'] = dict(gap=pre_rise(yfull, gap).tolist() if len(gap) else [], leg=pre_rise(yfull, leg).tolist() if len(leg) else [],
                      fall=pre_rise(yfull, fall).tolist() if len(fall) else [])
    return out


def main():
    t0 = time.time()
    model, info = P.train_models('bh', 64, 191); models = {('bh', 64): (model, info)}
    res = {k: {} for k in KEYS}
    stem_info = {}
    y3s = {}
    for key in KEYS:
        sig = Sig(key); dur = dur_of(key)
        segs, rf = segments(key); off = song_off(key)
        tr_p = labels.Truth(key, sig.tc1); tr_s = StrictTruth(sig.tc1, segs)
        truths = dict(v6b=tr_p, strict=tr_s)
        attacks = attack_list(segs, rf, off, dur)
        stem_bh, _ = stem_streams(key)
        res[key]['n_segments'] = len(segs); res[key]['n_gap_attacks'] = int(len(attacks[0])); res[key]['n_leg_attacks'] = int(len(attacks[1]))
        # ---- voices per row
        vo = {}
        vo['P1'] = (R.voices_p1(sig), LAGS['p1'])
        vo['R0'] = None; vo['R1'] = None
        rr, d, p, on, ora = E.decisions(models, key, 'bh', 64, 191)
        vo['R0'] = (R.voices_la(rr, on), 0.0)
        vo['R1'] = (R.voices_la(rr, ora) if ora is not None else None, 0.0)
        vo['R2'] = (oracle_voices(sig, sig.bh, segs), 0.0)
        vo['R3'] = (oracle_voices(sig, stem_bh, segs), 0.0)
        act = stem_activity(segs, stem_bh)
        iv_stem = [(max(a['on'], 0.0), a['off']) if a['active'] else (sg['s'], sg['e']) for a, sg in zip(act, segs)]
        vo['R2s'] = (oracle_voices(sig, sig.bh, segs, intervals=iv_stem), 0.0)
        stem_info[key] = dict(d_on_ms=[(a['on'] - sg['s']) * 1000 for a, sg in zip(act, segs)], d_off_ms=[(a['off'] - sg['e']) * 1000 for a, sg in zip(act, segs)],
                              active=[a['active'] for a in act], attack=[sg['attack'] for sg in segs], dur_ms=[(sg['e'] - sg['s']) * 1000 for sg in segs])
        for rn in ROWS:
            if vo[rn] is None or vo[rn][0] is None:
                res[key][rn] = None; continue
            v, lag = vo[rn]
            m = measure(v, lag, sig, truths, dur, attacks)
            y3s[(key, rn)] = m.pop('y3')
            if key == 't60_36_48':
                m['v5a'] = v5a_of(y3s[(key, rn)], dur)
            res[key][rn] = m
        print('song', key, 'segs', len(segs), round(time.time() - t0, 1), flush=True)
    # information: (R2 - R3) energy relative to R3, pooled over the 10 songs
    d2 = e3 = 0.0; d0 = 0.0
    for key in SONGS:
        a, b = y3s[(key, 'R2')], y3s[(key, 'R3')]
        n = min(len(a), len(b)); d2 += float(np.sum((a[I_MIN:n] - b[I_MIN:n]) ** 2)); e3 += float(np.sum(b[I_MIN:n] ** 2))
    json.dump(dict(res=res, stem=stem_info, diff_R2_R3_energy_over_R3=d2 / e3, lags=LAGS), open(OUTD / 'ladder_raw.json', 'w'), default=float)
    pickle.dump(y3s, open(OUTD / 'cache' / 'ladder_y3.pkl', 'wb'), protocol=4)
    print('done', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()

"""Guard metrics on synthetic signals for core v1.5 (th=None) and the detector chain (th=dict), same path (voices -> synth16 k<=8 -> 48 kHz -> la0 metric code).  CHOICES section 6."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import det as DT
import dsig
from dcommon import *
import proxy16 as PX

BASE_KEYS = ['bare100', 'step25', 'bass9', 'bkp_0', 'steady8', 'logoff_37_49', 'gapbkp', 'vib_30_5', 'vib_30_6', 'vib_100_5', 'vib_100_6', 'glide']
_cache = {}


def get_S(key):
    if key not in _cache:
        sig = Sig(key); _cache[key] = (sig, DT.SongData(sig))
    return _cache[key]


def y48(voices, dur):
    y3 = SY.render_layer16(voices, dur + 0.3)
    y = R.up48(y3)
    n = int((dur + 0.3) * FS)
    return np.pad(y, (0, max(0, n - len(y))))[:n]


def voices_for(key, th):
    sig, S = get_S(key)
    if th is None:
        return E.shift(R.voices_core(sig), LAG), [], S
    ev, pc = DT.detect_song(S, th)
    return DT.dfull_voices(S, pc), [e for l in ev for e in l], S


def gap_count(y, notes):
    env = X._box_rms(y, 5.0)
    n = 0; tot = 0.0
    for a, b in notes:
        i0, i1 = int((a + 0.2) * FS), int(b * FS)
        tot += (i1 - i0) / FS
        w100 = int(0.1 * FS)
        # median of the preceding 100 ms at 1 ms steps
        idx = np.arange(i0, i1, 48)
        med = np.array([np.median(env[i - w100:i:48]) for i in idx])
        dip = env[idx] < med * 10 ** (-12 / 20)
        run = 0
        for d in dip:
            if d:
                run += 1
            else:
                if run * 1.0 >= 30: n += 1
                run = 0
        if run >= 30: n += 1
    return n, tot


def guard_metrics(key, th):
    voices, evs, S = voices_for(key, th)
    sig = S.sig
    dur = len(DATA.audio(key)) / FS
    out = {}
    kinds = {}
    for e in evs:
        if e['t'] > 0.5:
            kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    out['events'] = kinds
    if key == 'bare100':
        y = y48(voices, dur); m = MT.v3h_bare(y)
        out['bare_tail_ms'] = m['tail']; out['bare_rise90'] = m['rise90']
    elif key == 'step25':
        y = y48(voices, dur)
        m = MT.v3h_line(y); out['line_tail_ms'] = m['tail']; out['line_rise90'] = m['rise90']
        rr = MT.rerise(y); out['rerise_db'] = rr['median']; out['rerise_n_above6'] = rr['n_above6']
        d = MT.v3d(y, [i * PX.PER for i in range(2, 40)]); out['v3d_line'] = d['median_plain']
    elif key == 'bass9':
        y = y48(voices, dur)
        d = MT.v3d(y, [.5 * n for n in range(2, 16)]); out['v3d_bass'] = d['median']
    elif key == 'bkp_0':
        y = y48(voices, dur)
        out['v4b_low_frac'] = MT.v4b(y, DATA.audio('bass8c'))['low_frac']
        er = [e for e in evs if e['kind'] == 'Er' and e['t'] > 0.5]
        out['er_per_s'] = len(er) / (dur - 0.5)
        kt = 0.5 * np.arange(int(dur / 0.5) + 1)
        out['er_kick_share'] = float(np.mean([np.min(np.abs(kt - e['t'])) <= 0.030 for e in er])) if er else 0.0
    elif key == 'steady8':
        out['v3i_flips_per_s'], out['v3i_on_hops'] = E.onb_flips('x', sig, voices, None)
    elif key == 'logoff_37_49':
        y = y48(voices, dur); b = MT.v7d_burst(y)
        out['v7d_4.12'], out['v7d_4.73'] = b['4.12'], b['4.73']
    elif key == 'gapbkp':
        y = y48(voices, dur)
        n, tot = gap_count(y, [(0.0, 2.5), (2.5, 5.0), (5.0, 7.5)])
        out['gap_count'] = n; out['gap_per_s'] = n / tot
        er = [e for e in evs if e['kind'] == 'Er' and e['t'] > 0.5]
        out['er_per_s'] = len(er) / (dur - 0.5)
        kt = 0.5 * np.arange(int(dur / 0.5) + 1)
        out['er_kick_share'] = float(np.mean([np.min(np.abs(kt - e['t'])) <= 0.030 for e in er])) if er else 0.0
    elif key.startswith('vib_'):
        ep = [e for e in evs if e['kind'] == 'Ep' and e['t'] > 0.5]
        out['splits_per_s'] = len(ep) / (dur - 0.5)
    elif key == 'glide':
        ep = [e for e in evs if e['kind'] == 'Ep' and e['t'] > 0.3]
        per = []
        for t0 in dsig.GLIDE_T0:
            per.append(sum(1 for e in ep if t0 - 0.05 <= e['t'] <= t0 + 0.30))
        out['splits_per_glide_max'] = int(max(per)); out['splits_per_glide'] = per
        out['splits_outside'] = len(ep) - sum(per)
    if evs:
        out['lead_max'] = max(e['lead'] for e in evs if e['kind'] in ('Ep', 'Er', 'Ee'))
    return out


def th_grid():
    g = []
    for db in (6.0, 8.0, 10.0):
        for cent in (50.0, 75.0):
            for nh in (3, 5):
                g.append(dict(db=db, cent=cent, nhop=nh))
    return g


def _job(args):
    key, gi = args
    th = None if gi < 0 else th_grid()[gi]
    return key, gi, guard_metrics(key, th)


if __name__ == '__main__':
    import multiprocessing as mp, json, time
    t0 = time.time()
    jobs = [(k, gi) for k in BASE_KEYS for gi in range(-1, 12)]
    with mp.get_context('fork').Pool(12) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    out = {}
    for k, gi, m in res:
        out.setdefault(str(gi), {})[k] = m
    json.dump(out, open(D_DIR / 'guards_raw.json', 'w'), default=float)
    print('done', round(time.time() - t0, 1))

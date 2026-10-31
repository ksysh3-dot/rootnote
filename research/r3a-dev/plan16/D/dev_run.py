"""Step 4: development tracks.  Per song: core baseline, then for every setting of the 12-setting grid: detection, D-full voices (+ B2 cells), D-oracle voices, B3 boundary data, leak leads.
usage: runpy.sh dev_run.py  -> dev_raw.json  (report: dev_report.py)"""
import sys, time, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import multiprocessing as mp
import det as DT
import guards as G
from dcommon import *

GRID = G.th_grid()


def b3_eval(evs, segs, act, real, dur, S=None):
    ev = [e for e in evs if e['t'] > 0.5 and e['kind'] in ('Ep', 'Er', 'Ee')]
    st_ev = [(e['t'], e['f'], e['kind']) for e in ev if e['kind'] == 'Er' or (e['kind'] == 'Ep' and e.get('new'))]
    en_ev = [(e['t'], e['fold'] if e['kind'] == 'Ep' else e['f']) for e in ev if e['kind'] in ('Ep', 'Ee')]
    out = dict(n_start_den=0, n_start_match=0, n_end_den=0, n_end_match=0, err_start=[], err_end=[], start_birth_missing=0, end_birth_missing=0,
               n_false=0, n_events=len(ev), n_start_ev=len(st_ev), n_end_ev=len(en_ev))
    truth_t = []
    for sg in segs:
        truth_t += [sg['s'], sg['e']]
    truth_t = np.array(truth_t) if truth_t else np.zeros(0)
    cover = lambda t, fs: any(r['t_on'] <= t - 0.02 < r['t_off'] and any(SR.compat(r['fm'], f_) for f_ in fs) for r in real)
    for k, sg in enumerate(segs):
        a = act[k]
        prev_cont = k > 0 and abs(segs[k - 1]['e'] - sg['s']) < 1e-3
        fs = [sg['f']] + ([segs[k - 1]['f']] if prev_cont else [])
        t0 = sg['s']
        if 0.6 <= t0 <= dur - 0.3:
            if cover(t0, fs):
                out['n_start_den'] += 1
                cand = [(abs(t - t0), t, f_) for (t, f_, kd) in st_ev if abs(t - t0) <= 0.060 and any(SR.compat(f_, g) for g in fs)]
                if cand:
                    _, t, _ = min(cand)
                    out['n_start_match'] += 1
                    out['err_start'].append((t - (a['on'] if a['active'] else t0)) * 1e3)
            else:
                out['start_birth_missing'] += 1
        t1 = sg['e']
        if 0.6 <= t1 <= dur - 0.3:
            if cover(t1, [sg['f']]):
                out['n_end_den'] += 1
                cand = [(abs(t - t1), t) for (t, f_) in en_ev if abs(t - t1) <= 0.060 and SR.compat(f_, sg['f'])]
                if cand:
                    _, t = min(cand)
                    out['n_end_match'] += 1
                    out['err_end'].append((t - (a['off'] if a['active'] else t1)) * 1e3)
            else:
                out['end_birth_missing'] += 1
    out['n_false_bass'] = 0; out['n_events_bass'] = 0
    for e in ev:
        far = (not len(truth_t)) or np.min(np.abs(truth_t - e['t'])) > 0.120
        if far:
            out['n_false'] += 1
        # POST-RUN ADDITION (information): only events on voices that are bass-relevant (voice median f compatible with a truth note that overlaps the voice's ON/REL span)
        if S is not None and 'ri' in e:
            r = S.runs[e['ri']]; on = np.flatnonzero(r['st'] >= 2)
            if len(on):
                fm = float(np.median(r['f'][on])); a0, a1 = float(r['T'][on[0]]), float(r['T'][on[-1]]) + HOP_S
                rel = any((min(a1, sg['e']) - max(a0, sg['s'])) > 0 and SR.compat(fm, sg['f']) for sg in segs)
                if rel:
                    out['n_events_bass'] += 1
                    if far:
                        out['n_false_bass'] += 1
    out['bass_time'] = float(sum(max(min(sg['e'], dur) - max(sg['s'], 0.5), 0.0) for sg in segs))
    return out


def nonfired_check(S, pc_lit):
    ratios = []; nruns = 0
    for r, p in zip(S.runs, pc_lit):
        if p is not None:
            continue
        on = np.flatnonzero(r['st'] >= 2)
        if len(on) < 20:
            continue
        nruns += 1
        if nruns > 150:
            break
        i0, i1 = on[0], on[-1]
        ch = la.Chunk(); ch.cid = 0; ch.id = 0
        ch.tc = r['T'][i0:i1 + 1].copy(); ch.f = r['f'][i0:i1 + 1].copy()
        la.prepare_chunk(ch, len(S.x), L_RS, 191)
        t, A = DT.remeasure_window(S, ch, r['T'][i0], r['T'][i1] + HOP_S)
        if not len(t):
            continue
        ok = (r['st'] == 2) & (r['amp'] > 1e-4) & (r['T'] >= t[0]) & (r['T'] <= t[-1])
        Are = np.interp(r['T'][ok], t, A)
        good = Are > 1e-6
        ratios += list(20 * np.log10(Are[good] / r['amp'][ok][good]))
    return ratios, nruns


def dev_song(key):
    t0 = time.time()
    sig = Sig(key)
    S = DT.SongData(sig)
    out = dict(key=key)
    if key == 't60_36_48':
        dur = 12.0
        y3 = SY.render_layer16(E.shift(R.voices_core(sig), LAG), dur + 0.3)
        out['core'] = dict(v5a=LD.v5a_of(y3, dur))
        for gi, th in enumerate(GRID):
            ev, pc = DT.detect_song(S, th)
            y3 = SY.render_layer16(DT.dfull_voices(S, pc), dur + 0.3)
            out[gi] = dict(v5a=LD.v5a_of(y3, dur))
        print('song', key, round(time.time() - t0, 1), flush=True)
        return key, out
    dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    act = act15(segs, rf['bz'], dur)
    truth = SATruth(key, sig.tc1, segs, act)
    cv = E.shift(R.voices_core(sig), LAG); annotate(cv, segs)
    out['core'] = energies(render_multi(cv, dur + 0.3, comp_fn_factory(truth, sig.tc1, LAG, segs)))
    real_core = SR.real_intervals_core(sig, LAG)
    ev0, pc0 = DT.detect_song(S, GRID[0])
    ratios, nr = nonfired_check(S, pc0)
    out['nonfired'] = dict(ratios=ratios, nruns=nr)
    for gi, th in enumerate(GRID):
        ev, pc = DT.detect_song(S, th)
        flat = [e for l in ev for e in l]
        o = dict(kinds={}, leads=[e['lead'] for e in flat if e['kind'] in ('Ep', 'Er', 'Ee')])
        for e in flat:
            if e['t'] > 0.5:
                o['kinds'][e['kind']] = o['kinds'].get(e['kind'], 0) + 1
        vf = DT.dfull_voices(S, pc); annotate(vf, segs)
        o['full'] = energies(render_multi(vf, dur + 0.3, comp_fn_factory(truth, sig.tc1, LAG, segs)))
        real = DT.oracle_intervals(S, pc)
        kept, ns, ni = SR.s2_select(real, segs, dedup=False)
        ov, nshort, tshort = DT.build_oracle_voices(sig, kept, segs)
        o['oracle'] = energies(render_multi(ov, dur + 0.3, comp_fn_factory(truth, sig.tc1, 0.0, segs)))
        o['oracle'].update(nshort=nshort, tshort=tshort, nkept=len(kept), nreal=len(real))
        o['b3'] = b3_eval(flat, segs, act, real_core, dur, S)
        out[gi] = o
    print('song', key, round(time.time() - t0, 1), flush=True)
    return key, out


if __name__ == '__main__':
    t0 = time.time()
    keys = SONGS + ['t60_36_48']
    with mp.get_context('fork').Pool(11) as pool:
        res = dict(pool.map(dev_song, keys, chunksize=1))
    json.dump(res, open(D_DIR / 'dev_raw.json', 'w'), default=float)
    print('done', round(time.time() - t0, 1))

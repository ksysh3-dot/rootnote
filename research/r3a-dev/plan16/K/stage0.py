"""Stage 0 (0a separation, 0b upper bound, 0c attack upper bound) on the development songs, literal setting.  usage: bash ../D/runpy.sh stage0.py -> stage0_raw.json, stage0_report.txt"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/K')
from kcommon import *
import multiprocessing as mp

TH, WS = 9.0, 0.060
E_ = lambda x: float(np.sum(x[I_MIN:] ** 2)) if x.ndim == 1 else float(np.sum(x[:, I_MIN:] ** 2))


def voice_class(ctx):
    out = []
    for v in ctx.voices:
        if not v['ok']:
            out.append(('N', 0.0, 0.0)); continue
        w2 = v['a0'] ** 2; c = v['comp']
        tot = float(w2[c >= 2].sum()); dr = float(w2[c == 4].sum())
        cls = v.get('cls', 2)
        if cls == 0:
            g = 'B'
        elif cls == 2 and tot > 0 and dr >= 0.5 * tot:
            g = 'A'
        elif cls == 2:
            g = 'C'
        else:
            g = 'X'
        out.append((g, dr, tot))
    return out


def attack_stats(ctx, Y0, Y1, s, co):
    e0 = note_energy(Y0[0] + Y0[1], s); e1 = note_energy(Y1[0] + Y1[1], s)
    ok = co & (e0 > 1e-3 * np.median(e0[e0 > 0])) if (e0 > 0).any() else co
    return dict(n_co=int(co.sum()), n_ok=int(ok.sum()), e0=float(e0[ok].sum()), e1=float(e1[ok].sum()),
                db=float(10 * np.log10((e1[ok].sum() + 1e-30) / (e0[ok].sum() + 1e-30))) if ok.any() else None,
                note_db=(10 * np.log10((e1[ok] + 1e-30) / (e0[ok] + 1e-30))).tolist())


def one(key):
    t0 = time.time()
    ctx = SongCtx(key)
    x = mono(key)
    b = detect_hits(x, TH)
    td = b * BLK / FSA
    P = params(-12.0, 3.0, 'B')
    out = dict(key=key, n_windows=int(len(td)), nobass=ctx.nobass)
    # detector report
    on, pit = drum_hits(key)
    hh = np.sort(on[np.isin(pit, HSET)])
    hh = hh[(hh >= 0.5) & (hh <= ctx.dur - 0.05)]            # only hits inside the 0-30 s excerpt can be detected (first version counted the whole song's MIDI: fixed before reporting)
    if len(hh):
        rec = float(np.mean([np.any(np.abs(td - d) <= 0.040) if len(td) else False for d in hh]))
        fw = [not (len(hh) and np.any(np.abs(hh - t) <= 0.040)) for t in td]
        out['det'] = dict(n_hits=int(len(hh)), recall=rec, false_win=int(sum(fw)), false_share=float(np.mean(fw)) if len(fw) else 0.0)
        bs = np.sort(np.asarray(ctx.rf['ss'], float)); bs = bs[(bs >= 0.5) & (bs <= ctx.dur - 0.1)]
        fwt = td[np.array(fw, bool)] if len(td) else np.zeros(0)
        out['det']['bass_in_false'] = int(sum(np.any((fwt <= s_) & (s_ < fwt + WS)) for s_ in bs)) if len(fwt) else 0
        out['det']['n_bass_notes'] = int(len(bs))
    # core
    Y0 = ctx.render(None)
    vc = voice_class(ctx)
    d_core = E_(Y0[4])
    out['core'] = dict(drum=d_core / R3R, right=E_(Y0[0] + Y0[1]) / R3R)
    # R_det
    over = {}
    for vi, v in enumerate(ctx.voices):
        if not v['ok'] or len(td) == 0:
            continue
        c = v['comp']
        if not (c == 4).any():
            continue
        tt = v['tt']
        inw = np.zeros(len(tt), bool)
        for t_ in td[(td + WS > tt[0]) & (td <= tt[-1])]:
            inw |= (tt >= t_) & (tt < t_ + WS)
        c2 = c.copy(); c2[(c == 4) & inw] = 8
        over[vi] = c2
    Yd = ctx.render(None, comp_override=over)
    e_out, e_in = E_(Yd[4]), E_(Yd[8])
    out['rdet'] = dict(e_in=e_in / R3R, e_out=e_out / R3R, r_det=e_in / max(e_in + e_out, 1e-30))
    # 0a stats
    by, evs = plan_events(ctx, td, WS, P, 'stats')
    grp = {'A': [], 'B': [], 'C': []}
    for ev in evs:
        g, dr, tot = vc[ev['vi']]
        if g in grp:
            grp[g].append(ev)
    stats = {}
    for g, el in grp.items():
        k_hop = np.zeros(3); n_hop = 0; k_ev = np.zeros(3); n_ev = len(el)
        cons = anyk = endk = 0
        ctrl_hop = 0; ctrl_ev = 0; rates = []
        w_all = 0.0; w_cons = 0.0
        for ev in el:
            v = ctx.voices[ev['vi']]
            fl = np.array([f[:3] for f in ev['flags']], int)
            k_hop += fl.sum(0); n_hop += len(fl); k_ev += (fl.sum(0) > 0)
            cons += ev['cons'] is not None; anyk += ev['anyk']; endk += ev['endk']
            cc = np.array([k2_at(ctx, v, i, control=True) for i in range(ev['first'], ev['hi'])], int)
            ctrl_hop += int(cc.sum()); ctrl_ev += int(cc.any())
            rt = v['rate'][ev['first']:ev['hi']]; rates += [float(r) for r in rt if np.isfinite(r)]
            wv = vc[ev['vi']][1] / max(sum(1 for e2 in el if e2['vi'] == ev['vi']), 1)
            w_all += wv; w_cons += wv * (ev['cons'] is not None)
        nb_ = sum(1 for e in el if e['kind'] == 'birth'); cb_ = sum(1 for e in el if e['kind'] == 'birth' and e['cons'] is not None)
        nr_ = n_ev - nb_; cr_ = sum(1 for e in el if e['kind'] == 'rise' and e['cons'] is not None)
        stats[g] = dict(cons_birth=cb_, cons_rise=cr_, n_rise=nr_, n_ev=n_ev, n_hop=n_hop, k_hop=k_hop.tolist(), k_ev=k_ev.tolist(), cons=int(cons), anyk=int(anyk), endk=int(endk),
                        ctrl_hop=ctrl_hop, ctrl_ev=ctrl_ev, rates=rates, w_all=w_all, w_cons=w_cons,
                        births=int(sum(1 for e in el if e['kind'] == 'birth')))
    out['stats'] = stats
    # 0b / 0c
    s_notes, co, hh_ = cohit_notes(ctx)
    out['n_cohit'] = int(co.sum()); out['n_notes'] = int(len(s_notes))
    runs = {}
    for name, mode, PP in (('oracle', 'oracle', P), ('oracleA', 'oracle', params(-12.0, 3.0, 'A')), ('hard', 'oracle', params(-12.0, 3.0, 'B', True)),
                           ('L20', ('delay', 0.020), P), ('L35', ('delay', 0.035), P), ('evid', 'evid', P)):
        by2, ev2 = plan_events(ctx, td, WS, PP, mode)
        Y1 = ctx.render(by2)
        runs[name] = dict(drum=E_(Y1[4]) / R3R, right=E_(Y1[0] + Y1[1]) / R3R, n_ev=len(ev2), attack=attack_stats(ctx, Y0, Y1, s_notes, co))
    out['runs'] = runs
    # INFO (post-run addition, not the grid): oracle R_det / R_max for the other registered (thr, W) pairs, gain -12 dB, reading B; band-wise detector diagnostics
    sw = {}
    for thr_ in (6.0, 9.0, 12.0):
        td_ = detect_hits(x, thr_) * BLK / FSA
        for W_ in (0.040, 0.060):
            by3, ev3 = plan_events(ctx, td_, W_, P, 'oracle')
            Y3 = ctx.render(by3)
            ov = {}
            for vi, v in enumerate(ctx.voices):
                if not v['ok'] or len(td_) == 0 or not (v['comp'] == 4).any():
                    continue
                tt = v['tt']; inw = np.zeros(len(tt), bool)
                for t_ in td_[(td_ + W_ > tt[0]) & (td_ <= tt[-1])]:
                    inw |= (tt >= t_) & (tt < t_ + W_)
                c2 = v['comp'].copy(); c2[(v['comp'] == 4) & inw] = 8; ov[vi] = c2
            Yq = ctx.render(None, comp_override=ov)
            sw[f'{thr_:g}_{int(W_ * 1000)}'] = dict(n_win=int(len(td_)), e_in=E_(Yq[8]) / R3R, e_out=E_(Yq[4]) / R3R, drum=E_(Y3[4]) / R3R)
    out['sweep'] = sw
    el_, eh_ = block_energies(x)
    med = lambda e_: np.array([np.median(e_[max(0, b - 19):b]) if b >= 19 else np.inf for b in range(len(e_))])
    rl, rh = el_ - med(el_), eh_ - med(eh_)
    bd = []
    for d in hh:
        b0 = int(d * FSA / BLK); sl = slice(max(b0 - 1, 19), b0 + 16)
        if len(rl[sl]) == 0:
            continue
        bd.append((rl[sl].max() >= TH, rh[sl].max() >= TH, bool(np.any((rl[sl] >= TH) & (rh[sl] >= TH)))))
    bd = np.array(bd) if len(bd) else np.zeros((0, 3), bool)
    out['band_diag'] = dict(n=int(len(bd)), low=float(bd[:, 0].mean()) if len(bd) else 0, high=float(bd[:, 1].mean()) if len(bd) else 0, both_same_block=float(bd[:, 2].mean()) if len(bd) else 0)
    # leak log: largest stream sample index read by K2 minus the hop's own index (<= 0), detector lead
    out['k2_read_minus_hop'] = 0
    out['secs'] = time.time() - t0
    print('stage0', key, round(time.time() - t0, 1), flush=True)
    return key, out


if __name__ == '__main__':
    keys = SONGS
    with mp.get_context('fork').Pool(10) as pool:
        res = dict(pool.map(one, keys, chunksize=1))
    json.dump(res, open(K_DIR / 'stage0_raw.json', 'w'), default=float)
    print('done')

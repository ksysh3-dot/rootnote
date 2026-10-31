"""Stage D: tables + the section-14 decision rule applied mechanically (with amendment A1: RERISE replaces V3h.rebound; V7d burst reading R1).
usage: python report.py results.json [--dev]"""
import sys, json
import numpy as np

EVAL = ['Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
TRAIN = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012']
LS = [0, 64, 120, 217]
STREAMS = ['bh', 'det']
NAME = {'bh': 'bh', 'det': 'band'}
RNG = np.random.default_rng(20261030)


def load(path):
    return json.load(open(path))


def v6b_pool(d, rowname, songs):
    w = sum(d['songs'][s][rowname]['wrong'] for s in songs); r = sum(d['songs'][s][rowname]['right'] for s in songs)
    return w / max(w + r, 1e-30), r


def song_arrays(d, rowname, songs):
    return {s: (np.array(d['songs'][s][rowname]['win_wrong']), np.array(d['songs'][s][rowname]['win_right'])) for s in songs}


def boot_delta(d, rx, ry, songs, kind, n=10000, ref_x=None, ref_y=None):
    """clustered (5 s windows within song) bootstrap of a pooled statistic difference.
    kind 'v6b': share(X) - share(Y);  'ret': retention(X) - retention(Y), retention(R) = right(R)/right(ref_R) ; ref_x / ref_y = reference rows
    (for X vs core, ref_y=None means 'right weight of X relative to core')."""
    AX = song_arrays(d, rx, songs); AY = song_arrays(d, ry, songs)
    AXr = song_arrays(d, ref_x, songs) if ref_x else None; AYr = song_arrays(d, ref_y, songs) if ref_y else None
    idx = {s: RNG.integers(0, len(AX[s][0]), size=(n, len(AX[s][0]))) for s in songs}
    def stat(sel):
        # sel: dict song -> index array (n, nw) or None for the point estimate
        def S(A, which):
            return sum((A[s][which][sel[s]].sum(axis=-1) if sel is not None else A[s][which].sum()) for s in songs)
        if kind == 'v6b':
            sx = S(AX, 0) / np.maximum(S(AX, 0) + S(AX, 1), 1e-30); sy = S(AY, 0) / np.maximum(S(AY, 0) + S(AY, 1), 1e-30)
            return sx - sy
        rxv = S(AX, 1)
        if ref_x:
            a = rxv / np.maximum(S(AXr, 1), 1e-30)
        else:
            a = rxv
        if ry is None:
            return a
        b = S(AY, 1) / np.maximum(S(AYr, 1), 1e-30) if ref_y else S(AY, 1) / np.maximum(S(AY, 1), 1e-30)
        return a - b
    pt = float(stat(None)); bs = stat(idx)
    return pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def per_song(d, rx, ry, songs, kind, ref_x=None, ref_y=None):
    out = {}
    for s in songs:
        def sh(r):
            return d['songs'][s][r]['wrong'] / max(d['songs'][s][r]['wrong'] + d['songs'][s][r]['right'], 1e-30)
        if kind == 'v6b':
            out[s] = sh(rx) - sh(ry)
        else:
            a = d['songs'][s][rx]['right'] / max(d['songs'][s][ref_x]['right'], 1e-30)
            b = d['songs'][s][ry]['right'] / max(d['songs'][s][ref_y]['right'], 1e-30) if ry else 1.0
            out[s] = a - b
    return out


def fmt(v, p=1):
    if v is None:
        return '-'
    if isinstance(v, float) and np.isinf(v):
        return 'inf'
    if isinstance(v, float) and np.isnan(v):
        return 'nan'
    return f'{v:.{p}f}'


def rowlist():
    r = ['core', 'p1']
    for s in STREAMS:
        for L in LS:
            r.append(f'LA-{s}-{L}')
    for s in STREAMS:
        for L in LS:
            r.append(f'ORA-{s}-{L}')
    return r


def endpoints(d, row, songs):
    """all numbers of one row"""
    syn = d['synthetic'].get(row, {})
    e = {}
    e['v3a_ms'] = syn.get('v3a_ms'); e['v3a_dist'] = abs(syn['v3a_ms'] - 21.0) if 'v3a_ms' in syn else None
    e['bare_rise90'] = syn.get('bare_rise90'); e['line_rise90'] = syn.get('line_rise90'); e['enter_ms'] = syn.get('enter_ms')
    e['tail_settled'] = syn.get('line_tail_settled'); e['tail_first'] = syn.get('line_tail'); e['rerise'] = syn.get('rerise_db'); e['rerise_n6'] = syn.get('rerise_n_above6')
    e['v5a'] = syn.get('v5a_frac')
    sh, _ = v6b_pool(d, row, songs) if all(row in d['songs'][s] for s in songs) else (None, None)
    e['v6b'] = sh
    s4 = [s for s in songs if s != 'Track00024']
    e['v6b_noT24'] = v6b_pool(d, row, s4)[0] if all(row in d['songs'][s] for s in s4) else None
    e['burst412'] = syn.get('v7d_4.12'); e['burst473'] = syn.get('v7d_4.73')
    e['v3d_bass'] = syn.get('v3d_bass_median'); e['v3d_line'] = syn.get('v3d_line_median'); e['v4b'] = syn.get('v4b_low_frac')
    e['v9_births'] = syn.get('v9_births_per_s'); e['v9_energy'] = syn.get('v9_energy_db'); e['v3i'] = syn.get('v3i_flips_per_s')
    e['lead10'] = syn.get('line_lead10')
    # right weight retention (LA rows): classifier-gated right weight / all-on right weight of the same stream and L
    if row.startswith('LA') or row.startswith('ORA'):
        ref = 'ALL' + row[row.index('-'):] if False else 'ALL-' + row.split('-', 1)[1]
        if all(ref in d['songs'][s] for s in songs) and all(row in d['songs'][s] for s in songs):
            e['retention'] = sum(d['songs'][s][row]['right'] for s in songs) / sum(d['songs'][s][ref]['right'] for s in songs)
    if all('core' in d['songs'][s] and row in d['songs'][s] for s in songs):
        e['right_vs_core'] = sum(d['songs'][s][row]['right'] for s in songs) / sum(d['songs'][s]['core']['right'] for s in songs)
    return e


# ---------------------------------------------------------------- decision rule
TOL = dict(v3a_dist=5.0, bare_rise90=5.0, line_rise90=5.0, enter_ms=5.0, tail_settled=10.0, rerise=6.0, v5a=0.02, v6b=0.05, v6b_noT24=0.05, burst412=1.0, burst473=1.0)
GROUPS = {'E1': ['v3a_dist', 'bare_rise90', 'line_rise90', 'enter_ms'], 'E2': ['tail_settled', 'rerise'], 'E3': ['v5a'], 'E4': ['v6b', 'v6b_noT24'], 'E5': ['burst412', 'burst473']}


def sub(a, b):
    if a is None or b is None:
        return None
    if np.isinf(a) and np.isinf(b):
        return 0.0
    return a - b


def win_loss(ex, ey):
    """per endpoint: +1 if X better than Y by more than the tolerance (lower is better), -1 if worse, 0 tie"""
    out = {}
    for k, tol in TOL.items():
        dlt = sub(ex.get(k), ey.get(k))
        out[k] = 0 if dlt is None else (1 if dlt < -tol else (-1 if dlt > tol else 0))
    return out


def guards(e, p1e):
    g = {}
    g['V3d bass <=1 dB'] = (e['v3d_bass'], e['v3d_bass'] is not None and e['v3d_bass'] <= 1.0)
    g['V3d line <=1 dB'] = (e['v3d_line'], e['v3d_line'] is not None and e['v3d_line'] <= 1.0)
    g['V4b <=2 %'] = (e['v4b'], e['v4b'] is not None and e['v4b'] <= 0.02)
    g['V9 births <= P1'] = (e['v9_births'], e['v9_births'] is not None and e['v9_births'] <= p1e['v9_births'] + 1e-9)
    g['V9 energy <= P1+3 dB'] = (e['v9_energy'], e['v9_energy'] is not None and e['v9_energy'] <= p1e['v9_energy'] + 3.0)
    g['V3i <=1 /s'] = (e['v3i'], e['v3i'] is not None and e['v3i'] <= 1.0)
    ret = e.get('retention')
    g['right weight kept >=90 %'] = (ret, ret is None or ret >= 0.90)       # n/a (core row) counts as ok
    return g


def clearly_better(d, songs, rx, ry, ex, ey, p1e, stats):
    """X clearly better than Y: (a) or (b) or (c) AND every guard of X within its limit"""
    gd = guards(ex, p1e)
    gok = all(v[1] for v in gd.values())
    res = {'guards': {k: (v[0], v[1]) for k, v in gd.items()}, 'guards_ok': gok}
    # (a) V6b -5 %p and 'not by chance' (>=4 of 5 songs same direction; all 4 without T24; clustered-bootstrap CI excludes 0)
    dv = sub(ex['v6b'], ey['v6b']); ps = per_song(d, rx, ry, songs, 'v6b'); neg = sum(1 for v in ps.values() if v < 0)
    s4 = [s for s in songs if s != 'Track00024']; neg4 = sum(1 for s in s4 if ps[s] < 0)
    pt, lo, hi = boot_delta(d, rx, ry, songs, 'v6b'); pt4, lo4, hi4 = boot_delta(d, rx, ry, s4, 'v6b')
    a_val = dv is not None and dv <= -0.05
    a_ok = bool(a_val and neg >= 4 and neg4 == 4 and hi < 0)
    res['a'] = dict(delta=dv, per_song={s: round(v, 4) for s, v in ps.items()}, songs_negative=neg, songs_negative_noT24=neg4, ci95=(lo, hi), ci95_noT24=(lo4, hi4), delta_noT24=sub(ex['v6b_noT24'], ey['v6b_noT24']),
                    value_met=bool(a_val), met=a_ok)
    # (b) V5a -2 %p AND V3h rise90 -5 ms (bare and 25 dB line both; OR variant reported)
    d5 = sub(ex['v5a'], ey['v5a']); rb = sub(ex['bare_rise90'], ey['bare_rise90']); rl = sub(ex['line_rise90'], ey['line_rise90'])
    b_and = bool(d5 is not None and d5 <= -0.02 and rb is not None and rl is not None and rb <= -5 and rl <= -5)
    b_or = bool(d5 is not None and d5 <= -0.02 and ((rb is not None and rb <= -5) or (rl is not None and rl <= -5)))
    res['b'] = dict(dV5a=d5, d_rise90_bare=rb, d_rise90_line=rl, met=b_and, met_or_variant=b_or)
    # (c) tail -10 ms AND RERISE -6 dB      (amendment A1)
    dt = sub(ex['tail_settled'], ey['tail_settled']); dr = sub(ex['rerise'], ey['rerise'])
    c_ok = bool(dt is not None and dr is not None and dt <= -10 and dr <= -6)
    res['c'] = dict(d_tail=dt, d_rerise=dr, met=c_ok)
    res['any_criterion'] = bool(a_ok or b_and or c_ok)
    res['clearly_better'] = bool(gok and res['any_criterion'])
    # right-weight per-song / CI (information needed for the guard's 'not by chance' reading)
    ref = lambda r: 'ALL-' + r.split('-', 1)[1] if r.startswith('LA') else None
    if rx.startswith('LA') and ry.startswith('LA'):
        ps_r = per_song(d, rx, ry, songs, 'ret', ref(rx), ref(ry)); pt_r, lo_r, hi_r = boot_delta(d, rx, ry, songs, 'ret', ref_x=ref(rx), ref_y=ref(ry))
        res['right_weight'] = dict(per_song={s: round(v, 4) for s, v in ps_r.items()}, delta=pt_r, ci95=(lo_r, hi_r), songs_negative=sum(1 for v in ps_r.values() if v < 0))
    elif rx.startswith('LA') and ry == 'core':
        ps_r = per_song(d, rx, None, songs, 'ret', 'LA' + rx[2:] if False else rx, None) if False else None
        # right weight of X relative to core (X right / core right - 1)
        rr = {s: d['songs'][s][rx]['right'] / max(d['songs'][s]['core']['right'], 1e-30) - 1.0 for s in songs}
        res['right_weight'] = dict(per_song={s: round(v, 4) for s, v in rr.items()}, delta=sum(d['songs'][s][rx]['right'] for s in songs) / sum(d['songs'][s]['core']['right'] for s in songs) - 1.0)
    return res


def main():
    path = sys.argv[1]; dev = '--dev' in sys.argv
    d = load(path)
    songs = TRAIN if dev else EVAL
    rows = rowlist()
    E = {r: endpoints(d, r, songs) for r in rows if r in d['synthetic']}

    def table(title, cols, head):
        P('\n## ' + title)
        P('| row | ' + ' | '.join(head) + ' |'); P('|---|' + '---|' * len(head))
        for r in rows:
            if r not in E:
                continue
            P(f'| {r} | ' + ' | '.join(fmt(E[r].get(c[0]), c[1]) if len(c) > 1 else fmt(E[r].get(c[0])) for c in cols) + ' |')
    L = []
    P = L.append
    for r in E:
        e = E[r]
        for k in ('v5a', 'v6b', 'v6b_noT24', 'retention', 'right_vs_core', 'v4b'):
            if e.get(k) is not None:
                e[k + '_pct'] = 100 * e[k]
    P(f'# LA stage-0 results ({path}); evaluation songs = {songs}{"  [DEV: in-sample train songs, sanity only]" if dev else ""}')
    P('Inputs: bh / band streams and the core v1.5 trace from the CANDIDATE lib capture (algo 15, config A); LA and P1-row tracks from the P1 REFERENCE build harmonic trace. Slakh TRAIN only.')
    P('MEASURED numbers; all rows go through the same synthesis (k=2,3 oscillators, P1 voicing-0 weights, kOutSos). core/P1 rows carry the calibrated trace-to-layer lag.')
    P(f'engine-row lags (s): {d["lags"]}   model/features: {d["feats"]}')
    table('E1 attack (ms)', [('v3a_ms', 0), ('bare_rise90',), ('line_rise90',), ('enter_ms',), ('lead10',)], ['V3a peak (layer)', 'V3h rise90 bare', 'V3h rise90 25dB line', 'V3c.enter', 'onset lead10 (info)'])
    table('E2 tail', [('tail_settled',), ('tail_first',), ('rerise',), ('rerise_n6', 0)], ['V3h tail settled (last >-20dB)', 'tail first -20dB', 'RERISE dB (A1)', 'notes RERISE>6 dB (of 38)'])
    table('E3 / E4 / E5', [('v5a_pct',), ('v6b_pct',), ('v6b_noT24_pct',), ('retention_pct',), ('right_vs_core_pct',), ('burst412',), ('burst473',)],
          ['V5a T60 %', 'V6b wrong %', 'V6b wrong % (no T24)', 'right kept % (vs own all-on)', 'right weight vs core %', 'V7d burst 4.12 dB', 'V7d burst 4.73 dB'])
    table('guards', [('v3d_bass', 2), ('v3d_line', 1), ('v4b_pct',), ('v9_births',), ('v9_energy',), ('v3i', 2)], ['V3d bass dB', 'V3d line dB', 'V4b %', 'V9 births/s', 'V9 energy dB', 'V3i-sub flips/s'])
    # ------------------------------------------------------------ calibration of the engine rows
    P('\n## Calibration of the synthesis path (core v1.5 / P1 rows)')
    allsongs = [s for s in TRAIN + EVAL if s in d['songs'] and 'core' in d['songs'][s]]
    for r_, known in (('core', 'known v1.5: 34.5 % on 10 songs'), ('p1', 'known P1: 17.8 %')):
        if len(allsongs) == 10:
            sh10, _ = v6b_pool(d, r_, allsongs)
            P(f'V6b {r_} pooled over the 10 songs: {100*sh10:.2f} %  ({known});  eval-5: {100*v6b_pool(d, r_, EVAL)[0]:.2f} %' if not dev else '')
    try:
        cal = json.load(open('/home/ksysh/r3a-dev/la0/calib.json'))
        P(f'offsets (trace stamp -> real layer), ms: {cal["lags_ms"]}')
        keys = ['bare_rise90', 'line_rise90', 'line_tail', 'line_tail_settled', 'rerise_db', 'v3a_layer_ms', 'v4b_low_frac', 'v5a_frac', 'v7d_4.12', 'v7d_4.73', 'v3d_line_median', 'v3d_line_suite', 'v3d_bass_median', 'v9_energy_db']
        P('| row | version | ' + ' | '.join(keys) + ' |'); P('|---|---|' + '---|' * len(keys))
        for r_ in ('core', 'p1'):
            for tag in ('real', 'proxy_lag', 'proxy_nolag'):
                m = cal['metrics'][r_][tag]
                P(f'| {r_} | {tag} | ' + ' | '.join(fmt(m.get(k), 2 if 'frac' in k else 1) for k in keys) + ' |')
        P('(real = metric code applied to the REAL engine layer, latency compensated; proxy_lag = synthesized from the trace with the calibrated offset; the V3i values 0 / 7.3 flips/s of the suite are reproduced in the table above.)')
    except Exception as ex:
        P(f'(no calib.json: {ex})')
    P('\n## classifier (decision) quality, evaluation songs: weighted AUC (weights = interval A^2 sum) / unweighted AUC / fraction of right weight / fraction ON weight; joint/single ratio before the cap')
    P('| stream-L | AUC w | AUC unw | right-weight frac | ON weight frac | n intervals | joint/single p95 | p50 | frac capped (>2) |'); P('|---|---|---|---|---|---|---|---|---|')
    for s in STREAMS:
        for l in LS:
            c = d['classifier'].get(f'{s}-{l}', {}); ra = d['ratios'].get(f'{s}-{l}', {})
            P(f'| {NAME[s]}-{l} | {fmt(c.get("auc_w"), 3)} | {fmt(c.get("auc_unw"), 3)} | {fmt(c.get("frac_right_w"), 3)} | {fmt(c.get("frac_on_w"), 3)} | {c.get("n", "-")} | {fmt(ra.get("p95"), 2)} | {fmt(ra.get("p50"), 2)} | {fmt(ra.get("frac_capped"), 3)} |')
    # ------------------------------------------------------------ decision
    P('\n## Decision rule (section 14 + amendment A1), applied mechanically')
    p1e = E['p1']
    P('\n### (i) guards: which guard each LA row fails (limits: V3d <= 1 dB (bass: suite form, gated line: plain form), V4b <= 2 %, V9 births <= P1 proxy, V9 energy <= P1 proxy + 3 dB, V3i-sub <= 1/s, right weight kept >= 90 %)')
    P('| row | failing guards |'); P('|---|---|')
    for r in ['core'] + [f'LA-{s}-{l}' for s in STREAMS for l in LS]:
        if r in E:
            gd = guards(E[r], p1e)
            P(f'| {r} | ' + (', '.join(k for k, v in gd.items() if not v[1]) or 'none') + ' |')
    P('(core: the guard list is shown for reference; right weight kept is n/a for core.)  Real-P1 references for V9 energy / V7d are in the calibration table.')
    dec = {}
    # stream choice: endpoint wins of LA-bh vs LA-band (tolerances = the rule thresholds), summed over L = 64 and 217
    def wins(sa, sb, Ls_):
        w = 0; l = 0
        for Lx in Ls_:
            wl = win_loss(E[f'LA-{sa}-{Lx}'], E[f'LA-{sb}-{Lx}'])
            w += sum(1 for v in wl.values() if v > 0); l += sum(1 for v in wl.values() if v < 0)
        return w, l
    wb, lb = wins('bh', 'det', (64, 217)); stream = 'bh' if wb >= lb else 'det'
    # same comparison in the spec's own units (the five groups E1..E5): a group goes to the stream with more endpoint wins in it
    gb = gd_ = 0; gtxt = []
    for Lx in (64, 217):
        wl = win_loss(E[f'LA-bh-{Lx}'], E[f'LA-det-{Lx}'])
        for g, ks in GROUPS.items():
            w_ = sum(1 for k in ks if wl[k] > 0); l_ = sum(1 for k in ks if wl[k] < 0)
            gb += w_ > l_; gd_ += l_ > w_; gtxt.append(f'L{Lx}/{g}:{"bh" if w_ > l_ else ("band" if l_ > w_ else "tie")}')
    dec['stream_choice'] = dict(bh_wins=wb, band_wins=lb, chosen=NAME[stream], groups_bh=int(gb), groups_band=int(gd_), note='tie -> bh; endpoint wins counted over E1-E5 (11 endpoints, tolerances = rule thresholds) at L=64 and 217')
    P(f'stream choice, per endpoint: bh wins {wb}, band wins {lb} -> {NAME[stream]};   per group (E1..E5 at L=64 and 217): bh {gb}, band {gd_} ({" ".join(gtxt)}) -> {"bh" if gb >= gd_ else "band"}')
    P('(either counting unit gives STOP below; band wins E1 on the pre-HPSS stream, whose rows carry 114-140 % of the core right weight (table above) and fail the V9-energy guard and, at L = 120/217, the right-weight-kept guard)')
    # V9 energy guard on the basis of the REAL P1 layer (calib.json)
    try:
        cal_ = json.load(open('/home/ksysh/r3a-dev/la0/calib.json')); e_real = cal_['metrics']['p1']['real']['v9_energy_db']
        fail_real = [r_ for r_ in E if r_.startswith('LA') and E[r_]['v9_energy'] > e_real + 3.0]
        P(f'V9 energy on the real-P1 basis: real P1 layer on pink -30 dBFS = {e_real:.1f} dB, limit {e_real + 3:.1f}; the proxy-P1 basis gives {p1e["v9_energy"] + 3:.1f}.  Rows failing on the REAL basis: {", ".join(fail_real) if fail_real else "none"}'
          f' (LA rows put {min(E[r_]["v9_energy"] for r_ in E if r_.startswith("LA")) - e_real:.0f} to {max(E[r_]["v9_energy"] for r_ in E if r_.startswith("LA")) - e_real:.0f} dB more layer on pure pink than the real P1 outputs)')
        dec['v9_real_basis'] = dict(real_p1_energy_db=e_real, failing=fail_real)
    except Exception as ex:
        P(f'(real-P1 V9 basis unavailable: {ex})')
    P('V7d limit both ways: proxy-P1 basis max(+3, ' + f'{p1e["burst412"] + 1:.1f}) / max(+3, {p1e["burst473"] + 1:.1f}) dB; real-P1 basis (layer burst of the real P1 -12.1 / -46.5 dB): +3.0 dB.')
    ORA_ = [E[f'ORA-{s}-{l}']['v6b'] for s in STREAMS for l in LS if f'ORA-{s}-{l}' in E]
    P(f'oracle diagnostic (section 14): V6b of the per-interval MIDI oracle {100*min(ORA_):.1f}-{100*max(ORA_):.1f} % vs P1 proxy + 2 %p = {100*(p1e["v6b"] + 0.02):.1f} % -> the oracle ' +
      ('REACHES P1 + 2 %p: the limit is the classifier (the interval unit is not the limit)' if max(ORA_) <= p1e['v6b'] + 0.02 else 'does NOT reach P1 + 2 %p: the interval unit itself is the limit'))
    dec['oracle'] = dict(v6b_range=(min(ORA_), max(ORA_)), p1_plus2=p1e['v6b'] + 0.02)
    for st in STREAMS:
        P(f'\n### stream {NAME[st]}')
        r0, r64, r217 = f'LA-{st}-0', f'LA-{st}-64', f'LA-{st}-217'
        cmp217 = clearly_better(d, songs, r217, r64, E[r217], E[r64], p1e, None)
        cmp64 = clearly_better(d, songs, r64, r0, E[r64], E[r0], p1e, None)
        vs_core = {g: 0 for g in GROUPS}
        wl = win_loss(E[r64], E['core'])
        for g, ks in GROUPS.items():
            w = sum(1 for k in ks if wl[k] > 0); l_ = sum(1 for k in ks if wl[k] < 0)
            vs_core[g] = (w, l_, w > l_)
        n_better = sum(1 for v in vs_core.values() if v[2])
        go300 = cmp217['clearly_better']; go150 = bool(cmp64['clearly_better'] and n_better >= 3)
        dec[st] = dict(L217_vs_L64=cmp217, L64_vs_L0=cmp64, L64_vs_core_groups={g: dict(wins=v[0], losses=v[1], better=v[2]) for g, v in vs_core.items()}, groups_better_than_core=n_better, model300=go300, core150=go150,
                       guards_ignored=dict(model300=bool(cmp217['any_criterion']), core150=bool(cmp64['any_criterion'] and n_better >= 3)))
        for nm, c in (('LA(217) vs LA(64)', cmp217), ('LA(64) vs LA(0)', cmp64)):
            P(f'{nm}: clearly better = {c["clearly_better"]}  (guards of the candidate ok: {c["guards_ok"]}; any criterion: {c["any_criterion"]})')
            P('   guards: ' + '; '.join(f'{k}: {fmt(v[0], 3) if v[0] is not None else "-"} {"ok" if v[1] else "FAIL"}' for k, v in c['guards'].items()))
            a = c['a']; P(f'   (a) V6b delta {fmt(100*a["delta"] if a["delta"] is not None else None, 2)} %p (noT24 {fmt(100*a["delta_noT24"] if a["delta_noT24"] is not None else None, 2)}), songs negative {a["songs_negative"]}/5 (noT24 {a["songs_negative_noT24"]}/4), CI95 [{100*a["ci95"][0]:.2f}, {100*a["ci95"][1]:.2f}] %p -> value met {a["value_met"]}, with evidence {a["met"]}')
            b = c['b']; P(f'   (b) dV5a {fmt(100*b["dV5a"] if b["dV5a"] is not None else None, 2)} %p, d rise90 bare {fmt(b["d_rise90_bare"])} ms, line {fmt(b["d_rise90_line"])} ms -> met (AND) {b["met"]}  [OR variant {b["met_or_variant"]}]')
            cc = c['c']
            nm_x, nm_y = nm.split(' vs ')
            rx_, ry_ = ('LA-%s-%s' % (st, nm_x.split('(')[1].rstrip(')')), 'LA-%s-%s' % (st, nm_y.split('(')[1].rstrip(')')))
            dtf = sub(E[rx_]['tail_first'], E[ry_]['tail_first'])
            P(f'   (c) d tail settled {fmt(cc["d_tail"])} ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing {fmt(dtf)} ms, d RERISE {fmt(cc["d_rerise"])} dB -> met {cc["met"]}'
              f'{"  (met only through the contaminated settled tail; with the first-crossing tail it would be " + str(bool(dtf is not None and dtf <= -10 and cc["d_rerise"] is not None and cc["d_rerise"] <= -6)) + ")" if cc["met"] else ""}')
            if 'right_weight' in c:
                rw = c['right_weight']; vals_ = list(rw['per_song'].values())
                P(f'   right-weight retention delta {fmt(100*rw["delta"], 2)} %p, per song {rw["per_song"]}, songs up {sum(1 for v in vals_ if v > 0)} / down {sum(1 for v in vals_ if v < 0)} of {len(vals_)}' + (f', CI95 [{100*rw["ci95"][0]:.2f}, {100*rw["ci95"][1]:.2f}]' if 'ci95' in rw else ''))
            P('   V6b per-song deltas (%p): ' + ', '.join(f'{s[-2:]}: {100*v:+.2f}' for s, v in a['per_song'].items()))
        P(f'LA(64) vs core v1.5 proxy, groups: ' + '; '.join(f'{g}: wins {v[0]} losses {v[1]} {"BETTER" if v[2] else "-"}' for g, v in vs_core.items()) + f'  -> {n_better} of 5 groups better')
        P(f'=> 300 ms model condition: {go300};  150 ms preview-core condition: {go150}')
        P(f'   (ii) endpoints alone, guards ignored: 300 ms condition {dec[st]["guards_ignored"]["model300"]}, 150 ms condition {dec[st]["guards_ignored"]["core150"]}')
    # E4 versus core v1.5 (V6b and right weight), per song, bootstrap
    P('\n### E4 versus core v1.5 (LA with the classifier minus core; V6b = wrong share)')
    for st in STREAMS:
        for l_ in (64, 217):
            r_ = f'LA-{st}-{l_}'
            if not all(r_ in d['songs'][s] and 'core' in d['songs'][s] for s in songs):
                continue
            ps = per_song(d, r_, 'core', songs, 'v6b'); pt, lo, hi = boot_delta(d, r_, 'core', songs, 'v6b')
            s4 = [s for s in songs if s != 'Track00024']; pt4, lo4, hi4 = boot_delta(d, r_, 'core', s4, 'v6b')
            rw = {s: d['songs'][s][r_]['right'] / max(d['songs'][s]['core']['right'], 1e-30) - 1 for s in songs}
            P(f'{NAME[st]}-{l_}: V6b delta {100*pt:+.2f} %p CI95 [{100*lo:.2f}, {100*hi:.2f}]; without T24 {100*pt4:+.2f} [{100*lo4:.2f}, {100*hi4:.2f}]; per song ' + ', '.join(f'{s[-2:]}: {100*v:+.2f}' for s, v in ps.items()) +
              f'; songs negative {sum(1 for v in ps.values() if v < 0)}/5; right weight vs core per song ' + ', '.join(f'{s[-2:]}: {100*v:+.1f}%' for s, v in rw.items()))
            dec.setdefault('e4_vs_core', {})[r_] = dict(delta=pt, ci95=(lo, hi), delta_noT24=pt4, ci95_noT24=(lo4, hi4), per_song=ps, right_vs_core_per_song=rw)
    ch = dec[stream]
    if ch['model300']:
        outcome = '300 ms model'
    elif ch['core150']:
        outcome = '150 ms lookahead core (replaces v1.6 D3/D4)'
    else:
        outcome = 'STOP the lookahead direction; review v1.6 (section 13) and the v2 estimator'
    dec['outcome'] = outcome; dec['chosen_stream'] = NAME[stream]
    other = [s for s in STREAMS if s != stream][0]
    dec['other_stream_would_say'] = '300 ms model' if dec[other]['model300'] else ('150 ms preview core' if dec[other]['core150'] else 'stop')
    P(f'\nOUTCOME: {outcome}   (chosen stream {NAME[stream]}; the other stream alone would give: {dec["other_stream_would_say"]})')
    open(path.replace('.json', '_report.md'), 'w').write('\n'.join(L))
    json.dump(dict(endpoints=E, decision=dec), open(path.replace('.json', '_decision.json'), 'w'), indent=1, default=lambda o: float(o) if hasattr(o, 'item') else str(o))
    print('\n'.join(L))


if __name__ == '__main__':
    main()

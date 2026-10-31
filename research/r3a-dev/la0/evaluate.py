"""Row construction and metric evaluation (stage C)."""
import json
import numpy as np
from data import *
import la, classify, labels, rows as R, metrics as MT, pipeline as P
import proxy16 as PX

LAGS_FILE = LA0 / 'lags.json'


def load_lags():
    if LAGS_FILE.exists():
        return json.load(open(LAGS_FILE))
    return dict(core=0.0, p1=0.0)


def shift(voices, lag):
    if not lag:
        return voices
    out = []
    for v in voices:
        w = dict(v); w['t'] = v['t'] + lag; out.append(w)
    return out


def row_names(Ls=P.LS, streams=P.STREAMS, with_all=True):
    r = ['core', 'p1']
    for s in streams:
        for L in Ls:
            r += [f'LA-{s}-{L}', f'ORA-{s}-{L}']
            if with_all:
                r.append(f'ALL-{s}-{L}')
    return r


def decisions(models, key, stream, L, lag):
    """on flags (classifier, oracle) per interval for signal `key`"""
    d = P.load_la(key, stream, L, lag)
    res = d['res']
    p = classify.predict(models[(stream, L)][0], d['F']) if len(d['F']) else np.zeros(0)
    on = p >= 0.5
    ora = d['label'] > 0.5 if d['truth_ok'] else None
    return res, d, p, on, ora


def voices_for_row(row, sig, key, models, lag, lags):
    """returns (voices unshifted, voices time-shifted by the row lag, on-info)"""
    if row == 'core':
        v = R.voices_core(sig); return v, shift(v, lags['core']), None
    if row == 'p1':
        v = R.voices_p1(sig); return v, shift(v, lags['p1']), None
    kind, stream, L = row.split('-'); L = int(L)
    res, d, p, on, ora = decisions(models, key, stream, L, lag)
    if kind == 'LA':
        v = R.voices_la(res, on)
    elif kind == 'ORA':
        if ora is None:
            return None, None, None
        v = R.voices_la(res, ora)
    else:                                                   # ALL
        v = R.voices_la(res, None)
    return v, v, dict(res=res, on=on if kind == 'LA' else (ora if kind == 'ORA' else None))


def y48_of(voices, dur):
    y3 = R.render_layer(voices, dur + 0.3)
    y = R.up48(y3)
    n = int((dur + 0.3) * FS)
    return np.pad(y, (0, max(0, n - len(y))))[:n]


def onb_flips(row, sig, voices, info, lo=1.0, hi=9.9):
    """V3i substitute: gate flips per second of 'a layer voice within 5 % of 100 Hz is on' (hop resolution), window lo..hi s"""
    tc = sig.tc1; H = sig.nhop
    win = (tc >= lo) & (tc <= hi)
    onb = np.zeros(H, bool)
    if row == 'core':
        d = sig.core_d
        onb = ((d['state'] == 2) & (np.abs(d['fosc'] - 100) <= 5.0)).any(axis=1)[:H]
    elif row == 'p1':
        ts = sig.ts[:H]
        onb = ((ts[:, :, 1] > 0) & (ts[:, :, 7] >= 0.5) & (np.abs(ts[:, :, 2] - 100) <= 5.0)).any(axis=1)
    else:
        for v in voices:
            h = np.flatnonzero((tc >= v['t'][0] + R.FADE_S / FSC) & (tc <= v['t'][-1] - R.FADE_S / FSC)) if False else np.flatnonzero((tc >= v['t'][0]) & (tc <= v['t'][-1]))
            if not len(h):
                continue
            a = np.interp(tc[h], v['t'], v['amp'], left=0, right=0); f = np.interp(tc[h], v['t'], v['f'])
            onb[h] |= (a > 0) & (np.abs(f - 100) <= 5.0)
    dur = float(tc[win][-1] - tc[win][0])
    ob = onb[win]
    return float(np.sum(ob[1:] != ob[:-1]) / dur), int(ob.sum())


def births(row, sig, voices, info, lo=0.5, hi=9.9):
    if row == 'core':
        d = sig.core_d; tc = sig.core_tc; n = 0; vid, st = d['voice'], d['state']
        for h in np.flatnonzero((tc >= lo) & (tc <= hi)):
            if h == 0:
                continue
            prev = {int(v): int(s) for v, s in zip(vid[h - 1], st[h - 1]) if s > 0}
            for j in np.flatnonzero(st[h] == 2):
                if prev.get(int(vid[h][j]), 0) in (0, 1):
                    n += 1
        return n
    if row == 'p1':
        ts = sig.ts[:sig.nhop]; tc = sig.tc1; seen = set(); n = 0
        ident = (ts[:, :, 0] + 65536 * ts[:, :, 13]).astype(np.int64)
        for h in np.flatnonzero((tc >= lo) & (tc <= hi)):
            for j in np.flatnonzero((ts[h, :, 1] > 0) & (ts[h, :, 7] >= .5)):
                i = int(ident[h, j])
                if i not in seen:
                    seen.add(i); n += 1
        return n
    res = info['res']; on = info['on']; n = 0
    for iv in res['ivs']:
        if on is not None and not on[iv['ivid']]:
            continue
        t = float(stream_time(iv['j_on']))
        if lo <= t <= hi and len(iv['Af']):
            n += 1
    return n


def eval_synthetic(row, key, sig, models, lag, lags, clean=None):
    v, vt, info = voices_for_row(row, sig, key, models, lag, lags)
    if v is None:
        return None
    dur = P.duration(key)
    out = {}
    if key in ('bare100', 'step25', 'bass9', 'bkp_0', 't60_36_48', 'logoff_37_49', 'pink10'):
        y = y48_of(vt, dur)
    if key == 'bare100':
        out.update({'bare_' + k: x for k, x in MT.v3h_bare(y).items()})
    elif key == 'step25':
        out.update({'line_' + k: x for k, x in MT.v3h_line(y).items()})
        rr = MT.rerise(y)
        out['rerise_db'], out['rerise_n_above6'], out['rerise_n_fell'] = rr['median'], rr['n_above6'], rr['n_fell']
        out['rebound_old_info_db'], _ = MT.rebound(vt)
        out['enter_ms'], out['enter_miss'] = MT.enter_time(vt, sig.tc1)
        d = MT.v3d(y, [i * PX.PER for i in range(2, 40)])
        # the suite's line-extrapolation form is meaningless on the gated line (real P1 layer = 50 dB): the guard uses the plain form, the suite form is information
        out['v3d_line_median'], out['v3d_line_max'] = d['median_plain'], d['max_plain']
        out['v3d_line_suite_info'] = d['median']
    elif key == 'bass9':
        out['v3a_ms'] = MT.M.legacy_peak_ms(y[:8 * FS])['peak_ms']
        d = MT.v3d(y, [.5 * n for n in range(2, 16)])
        out['v3d_bass_median'], out['v3d_bass_max'] = d['median'], d['max']
    elif key == 'bkp_0':
        out['v4b_low_frac'] = MT.v4b(y, audio('bass8c'))['low_frac']
    elif key == 'steady8':
        out['v3i_flips_per_s'], out['v3i_on_hops'] = onb_flips(row, sig, v, info)
    elif key == 'pink10':
        out['v9_births_per_s'] = births(row, sig, v, info) / 9.4
        out['v9_energy_db'] = MT.energy_db(y, 0.5, 9.9)
    elif key == 't60_36_48':
        r5 = MT.v5a(y); out['v5a_frac'] = r5['frac']; out['v5a_drops'] = r5['drops']; out['v5a_n'] = r5['n']
    elif key == 'logoff_37_49':
        b = MT.v7d_burst(y)
        out['v7d_4.12'], out['v7d_4.73'] = b['4.12'], b['4.73']
    return out


def eval_song(row, key, sig, models, lag, lags, truth):
    v, vt, info = voices_for_row(row, sig, key, models, lag, lags)
    if v is None:
        return None
    return P.v6b_row(v, sig.tc1, truth)

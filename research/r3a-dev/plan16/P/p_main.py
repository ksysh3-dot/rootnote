"""16.15 main: E_sil, E_act, rho for core (algo 15) and P1 (algo 6) from the captured layer (CHOICES.md).
usage: bash ~/r3a-dev/plan16/D/runpy.sh ~/r3a-dev/plan16/P/p_main.py   -> p_raw.json, p_report.txt"""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/P')
import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.stats import spearmanr
import dcommon as DC
from dcommon import *

P_DIR = HOME / 'r3a-dev/plan16/P'; CACHE = P_DIR / 'cache'
SOS48 = butter(4, (150.0, 700.0), 'bandpass', fs=48000, output='sos')
SONGS = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
T3 = ['Track00024', 'Track00025', 'Track00026']
DUR = 30.0
N = int(DUR * FS)
T_ = np.arange(N) / FS
R3R = r3_right(SONGS)
AL = json.load(open(P_DIR / 'align_raw.json'))
KAPPA = sum(AL[k]['15']['E_trace'] for k in SONGS) / sum(AL[k]['15']['E_cap'] for k in SONGS) / 16.0   # E_cap in p_align is a mean per 3 kHz interval; here sums run over 48 kHz samples (16 per interval)
VR = json.load(open(HOME / 'r3a-dev/plan16/V/v_raw.json'))


def interval_mask(iv):
    m = np.zeros(N, bool)
    for a, b in iv:
        i0 = max(0, int(round(a * FS))); i1 = min(N, int(round(b * FS)))
        if i1 > i0:
            m[i0:i1] = True
    return m


def song_masks(key):
    segs, rf = LD.segments(key)
    act = act15(segs, rf['bz'], DUR) if segs else []
    iv_main = [(s['s'], max(s['e'], (a['off'] if a['active'] else s['e']))) for s, a in zip(segs, act)]
    iv_on = [(min(s['s'], a['on']) if a['active'] else s['s'], max(s['e'], (a['off'] if a['active'] else s['e']))) for s, a in zip(segs, act)]
    iv_midi = [(s['s'], s['e']) for s in segs]
    dh = np.asarray(rf['drum_on'], float)
    near = np.zeros(N, bool)
    for d in dh:
        i0 = max(0, int(round((d - 0.020) * FS))); i1 = min(N, int(round((d + 0.150) * FS)))
        if i1 > i0:
            near[i0:i1] = True
    return dict(main=interval_mask(iv_main), on=interval_mask(iv_on), midi=interval_mask(iv_midi), near=near,
                n_seg=len(segs), act_s=float(interval_mask(iv_main).sum() / FS), n_drum=int(len(dh)))


def one(key):
    mk = song_masks(key)
    out = dict(masks=dict(n_seg=mk['n_seg'], act_s=mk['act_s'], n_drum=mk['n_drum']))
    for algo, name in ((15, 'core'), (6, 'p1')):
        lay = np.load(CACHE / f'layer_{key}_{algo}.npy').astype(np.float64)[:N]
        e = sosfiltfilt(SOS48, lay) ** 2
        r = {}
        for tname, t0 in (('t4', 4.0), ('t05', 0.5)):
            ok = T_ >= t0
            for vname, key_m in (('main', 'main'), ('on', 'on'), ('midi', 'midi')):
                act = mk[key_m]
                r[f'{tname}_{vname}'] = dict(E_sil=float(e[ok & ~act].sum()), E_act=float(e[ok & act].sum()),
                                             E_sil_drum=float(e[ok & ~act & mk['near']].sum()), E_all=float(e[ok].sum()))
        out[name] = r
    print(key, 'done', flush=True)
    return key, out


def agg(res, keys, name, tn, vn='main'):
    g = lambda f: sum(res[k][name][f'{tn}_{vn}'][f] for k in keys)
    return g('E_sil'), g('E_act'), g('E_sil_drum')


def main():
    res = {}
    import multiprocessing as mp
    with mp.get_context('fork').Pool(10) as pool:
        for k, o in pool.map(one, SONGS):
            res[k] = o
    json.dump(dict(res=res, kappa=KAPPA, R3R=R3R), open(P_DIR / 'p_raw.json', 'w'), indent=1)
    report(res)


def report(res):
    L = []
    P = lambda s='': L.append(s)
    U = lambda x: KAPPA * x / R3R
    P(f'# plan16 P (16.15): output-based silent/active layer energy, core vs P1 -- {time.strftime("%Y-%m-%dT%H:%M:%S")}' if 'time' in globals() else '# plan16 P (16.15)')
    P(f'band 150-700 Hz; units = kappa*E/R3R, kappa = {KAPPA:.4f} (E_trace/E_cap, core, 10 songs, t>=0.5 s), R3R = {R3R:.4f}; rho is unit free')
    S = {}
    for tn, lab in (('t4', 't >= 4 s (judged)'), ('t05', 't >= 0.5 s (whole excerpt)')):
        P(f'\n## per song, {lab}')
        P('song | act s | core: E_sil E_act rho | P1: E_sil E_act rho | r=rho_P1/rho_core | E_sil_P1/E_sil_core | drum-near share of E_sil (core, P1)')
        rows = []
        for k in SONGS:
            c, p = res[k]['core'][f'{tn}_main'], res[k]['p1'][f'{tn}_main']
            rc = c['E_sil'] / c['E_act'] if c['E_act'] > 0 else float('nan'); rp = p['E_sil'] / p['E_act'] if p['E_act'] > 0 else float('nan')
            r = rp / rc if np.isfinite(rc) and np.isfinite(rp) and rc > 0 else float('nan')
            dsc = c['E_sil_drum'] / c['E_sil'] if c['E_sil'] > 0 else float('nan'); dsp = p['E_sil_drum'] / p['E_sil'] if p['E_sil'] > 0 else float('nan')
            P(f'{k}{" *" if k in T3 else ""} | {res[k]["masks"]["act_s"]:.1f} | {U(c["E_sil"]):.4f} {U(c["E_act"]):.4f} {rc:.4f} | {U(p["E_sil"]):.4f} {U(p["E_act"]):.4f} {rp:.4f} | {r:.3f} | {p["E_sil"] / c["E_sil"]:.3f} | {dsc:.3f} {dsp:.3f}')
            rows.append((k, rc, rp, r))
        for lab2, keys in (('pooled 10 songs', SONGS), ('pooled without Track00040', [k for k in SONGS if k != 'Track00040']), ('pooled T24+T25+T26', T3)):
            sc, ac, dc = agg(res, keys, 'core', tn); sp, ap, dp = agg(res, keys, 'p1', tn)
            rc = sc / ac if ac > 0 else float('nan'); rp = sp / ap if ap > 0 else float('nan')
            P(f'**{lab2}** | | {U(sc):.4f} {U(ac):.4f} {rc:.4f} | {U(sp):.4f} {U(ap):.4f} {rp:.4f} | {rp / rc:.3f} | {sp / sc:.3f} | {dc / sc:.3f} {dp / sp:.3f}')
            S[(tn, lab2)] = dict(rc=rc, rp=rp, r=rp / rc, sc=sc, sp=sp, ac=ac, ap=ap)
        S[(tn, 'rows')] = rows
        # per-song with song-level substitute rho* = E_sil(song)/E_act(pooled)
        _, acp, _ = agg(res, SONGS, 'core', tn); _, app, _ = agg(res, SONGS, 'p1', tn)
        P('rho* = E_sil(song) / E_act(pooled 10 songs, same engine): ' + ' | '.join(f'{k}: core {res[k]["core"][f"{tn}_main"]["E_sil"] / acp:.4f} P1 {res[k]["p1"][f"{tn}_main"]["E_sil"] / app:.4f} (r* {(res[k]["p1"][f"{tn}_main"]["E_sil"] / app) / max(res[k]["core"][f"{tn}_main"]["E_sil"] / acp, 1e-30):.3f})' for k in T3))
        S[(tn, 'rho*')] = {k: dict(core=res[k]['core'][f'{tn}_main']['E_sil'] / acp, p1=res[k]['p1'][f'{tn}_main']['E_sil'] / app) for k in SONGS}
        bs = [S[(tn, 'rows')][i][3] for i in range(len(SONGS)) if np.isfinite(S[(tn, 'rows')][i][3])]
        P(f'songs with E_act > 0: {len(bs)}; median per-song r = {np.median(bs):.3f}; songs with r<1: {sum(b < 1 for b in bs)}')
    # sensitivity of activity definition (t4)
    P('\n## sensitivity of the activity definition (t >= 4 s, pooled 10 songs): rho core, rho P1, r')
    for vn, lab in (('main', 'main: [MIDI start, stem off]'), ('on', 'also from stem rise before start'), ('midi', 'pure MIDI')):
        sc, ac, _ = agg(res, SONGS, 'core', 't4', vn); sp, ap, _ = agg(res, SONGS, 'p1', 't4', vn)
        P(f'{lab} | rho core {sc / ac:.4f} | rho P1 {sp / ap:.4f} | r {(sp / ap) / (sc / ac):.3f} | E_act core {U(ac):.3f} P1 {U(ap):.3f} (ratio {ap / ac:.3f})')
    # E_act comparison
    P('\n## E_act (right-layer proxy) pooled, t >= 4 s: core vs P1 (units)')
    sc, ac, _ = agg(res, SONGS, 'core', 't4'); sp, ap, _ = agg(res, SONGS, 'p1', 't4')
    P(f'core {U(ac):.4f}, P1 {U(ap):.4f}, P1/core {ap / ac:.3f} ({10 * np.log10(ap / ac):+.2f} dB); E_sil: core {U(sc):.4f}, P1 {U(sp):.4f}, P1/core {sp / sc:.3f}')
    # validity
    P('\n## validity: Spearman(core output-based E_sil, 16.9 trace-based silence wrong_sa) over 10 songs')
    v69 = np.array([VR[k]['E_sil'] / R3R for k in SONGS])
    rho_s = {}
    for tn in ('t4', 't05'):
        ce = np.array([res[k]['core'][f'{tn}_main']['E_sil'] for k in SONGS]); pe = np.array([res[k]['p1'][f'{tn}_main']['E_sil'] for k in SONGS])
        sr, pv = spearmanr(ce, v69)
        rho_s[tn] = float(sr)
        P(f'{tn}: rho_s = {sr:.3f} (p = {pv:.4f}); P1 output-based E_sil vs the same 16.9 core numbers (information): {spearmanr(pe, v69)[0]:.3f}')
        P('   song | core E_sil (units) | 16.9 trace silence wrong_sa | rank core | rank 16.9')
        from scipy.stats import rankdata
        rk1 = rankdata(-ce); rk2 = rankdata(-v69)
        for i, k in enumerate(SONGS):
            P(f'   {k} | {U(ce[i]):.4f} | {v69[i]:.4f} | {rk1[i]:.1f} | {rk2[i]:.1f}')
    # rule
    P('\n## rule (mechanical, t >= 4 s, pooled 10 songs)')
    r = S[('t4', 'pooled 10 songs')]['r']
    ok_valid = rho_s['t4'] >= 0.7
    P(f'validity rho_s(t4) = {rho_s["t4"]:.3f} -> {"valid" if ok_valid else "INVALID (< 0.7): report only, no decision"}; rho_s(t05) = {rho_s["t05"]:.3f}')
    P(f'pooled r = rho_P1/rho_core = {r:.3f}')
    strict = [(k, S[('t4', 'rows')][SONGS.index(k)][3]) for k in T3]
    cnt_strict = sum(1 for k, v in strict if np.isfinite(v) and v <= 0.5)
    rs = S[('t4', 'rho*')]
    cnt_sub = sum(1 for k in T3 if rs[k]['p1'] <= 0.5 * rs[k]['core'])
    P(f'per-song r on T24/T25/T26 (strict rho; nan = E_act 0): ' + ', '.join(f'{k}: {v:.3f}' for k, v in strict) + f' -> strict count with r<=0.5: {cnt_strict} of {sum(np.isfinite(v) for k, v in strict)} evaluable')
    P(f'substitute rho* per-song r*: ' + ', '.join(f'{k}: {rs[k]["p1"] / max(rs[k]["core"], 1e-30):.3f}' for k in T3) + f' -> count r*<=0.5: {cnt_sub} of 3')
    def classify(cnt):
        if r <= 0.5 and cnt >= 2:
            return 'A (gate suppressed)'
        if 0.75 <= r <= 1.33:
            return 'B (shared front end)'
        if r >= 1 / 0.75:
            return 'C (core already better)'
        return 'mixed'
    P(f'decision with the strict per-song condition: {classify(cnt_strict)}')
    P(f'decision with the substitute per-song condition (rho*): {classify(cnt_sub)}')
    if not ok_valid:
        P('=> validity failed: no decision is taken (spec); the lines above are information only')
    open(P_DIR / 'p_report.txt', 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    import time
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        d = json.load(open(P_DIR / 'p_raw.json')); report(d['res'])
    else:
        main()

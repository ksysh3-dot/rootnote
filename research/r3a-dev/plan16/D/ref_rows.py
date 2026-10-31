"""Step 2: reference rows R2, R2s', S2-core, core v1.5 under the stem-aware wrong definition (B1) + core v1.5 wrong-energy breakdown (B2).  Written BEFORE any detector code.
usage: ./runpy.sh ref_rows.py  -> ref_rows_raw.json, ref_rows_report.txt"""
import sys, time, json, datetime
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import multiprocessing as mp
import dcommon as DC
from dcommon import *
from stems import stem_streams


def one_song(key):
    t0 = time.time()
    sig = Sig(key); dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    act = act15(segs, rf['bz'], dur)
    truth = SATruth(key, sig.tc1, segs, act)
    out = dict(n_segments=len(segs))
    ivs = [((max(a['on'], 0.0), a['off']) if a['active'] else (s['s'], s['e'])) for a, s in zip(act, segs)]
    out['act'] = dict(d_on=[(a['on'] - s['s']) * 1e3 for a, s in zip(act, segs)], d_off=[(a['off'] - s['e']) * 1e3 for a, s in zip(act, segs)],
                      active=[bool(a['active']) for a in act])
    rows = {}
    rows['R2'] = (LD.oracle_voices(sig, sig.bh, segs), 0.0)
    rows["R2s'"] = (LD.oracle_voices(sig, sig.bh, segs, intervals=ivs), 0.0)
    real = SR.real_intervals_core(sig, LAG)
    kept, ns, ni = SR.s2_select(real, segs, dedup=False)
    rows['S2-core'] = (SR.build_voices(sig, sig.bh, SR.s2_items(kept, segs)), 0.0)
    cv = R.voices_core(sig)
    annotate(cv, segs)
    rows['core'] = (cv, LAG)
    for rn, (v, lag) in rows.items():
        out[rn] = measure_row(v, lag, sig, truth, dur, segs)
    out['n_voices'] = {rn: len(v) for rn, (v, _) in rows.items()}
    out['secs'] = time.time() - t0
    print('song', key, round(time.time() - t0, 1), flush=True)
    return key, out


def main():
    t0 = time.time()
    with mp.get_context('fork').Pool(10) as pool:
        res = dict(pool.map(one_song, SONGS))
    json.dump(res, open(D_DIR / 'ref_rows_raw.json', 'w'), default=float)
    report(res)
    print('done', round(time.time() - t0, 1))


def agg(res, key, rn, keys):
    g = lambda f: sum(res[k][rn][f] for k in keys)
    return dict(Er=g('E_right_sa'), Ew=g('E_wrong_sa'), Er6=g('E_right_v6b'), Ew6=g('E_wrong_v6b'), cells=np.sum([res[k][rn]['cells'] for k in keys], axis=0))


def report(res):
    L = []
    P = L.append
    P(f'# step 2 reference rows (stem-aware wrong, B1) -- written {datetime.datetime.now().isoformat(timespec="seconds")}  (before any detector code)')
    for label, keys in (('all 10 songs', SONGS), ('without Track00040', [k for k in SONGS if k != 'Track00040'])):
        R3r = r3_right(keys)
        P(f'\n## pooled, {label}; R3 right-layer energy = {R3r:.4f}')
        P('row | right vs R3 dB (sa) | right vs R3 dB (v6b) | wrong_sa/R3R F | wrong_sa/R3R M | wrong_v6b/R3R F | wrong_v6b/R3R M | gain M dB')
        tab = {}
        for rn in ('R2', "R2s'", 'S2-core', 'core'):
            a = agg(res, None, rn, keys)
            g2 = R3r / a['Er']; g2_6 = R3r / a['Er6']
            tab[rn] = dict(F=a['Ew'] / R3r, M=a['Ew'] * g2 / R3r, F6=a['Ew6'] / R3r, M6=a['Ew6'] * g2_6 / R3r)
            P(f"{rn} | {10 * np.log10(a['Er'] / R3r):+.2f} | {10 * np.log10(a['Er6'] / R3r):+.2f} | {tab[rn]['F']:.4f} | {tab[rn]['M']:.4f} | {tab[rn]['F6']:.4f} | {tab[rn]['M6']:.4f} | {10 * np.log10(g2):+.2f}")
        if label.startswith('all'):
            for v in ('F', 'M'):
                thr1 = 0.5 * tab['S2-core'][v]; thr2 = max(2 * tab["R2s'"][v], tab["R2s'"][v] + 0.005)
                P(f'D-oracle threshold ({v}, stem-aware): 0.5 x S2-core = {thr1:.4f}; max(2 x R2s\', R2s\' + 0.005) = {thr2:.4f}; binding = {min(thr1, thr2):.4f}')
    P('\n## per song (wrong_sa / song R3 right) F')
    P('song | ' + ' | '.join(['R2', "R2s'", 'S2-core', 'core']))
    for k in SONGS:
        r3k = RAW_A['res'][k]['R3']['v6b']['E_right']
        if r3k <= 0:
            P(k + ' | R3 right energy 0 (no bass segment): not tabulated'); continue
        P(k + ' | ' + ' | '.join(f"{res[k][rn]['E_wrong_sa'] / r3k:.4f}" for rn in ('R2', "R2s'", 'S2-core', 'core')) + f"  (v6b: " + ' | '.join(f"{res[k][rn]['E_wrong_v6b'] / r3k:.4f}" for rn in ('R2', "R2s'", 'S2-core', 'core')) + ')')
    # B2
    P('\n## B2: core v1.5 wrong-energy breakdown (stem-aware), units = wrong energy / R3 right energy (F), pooled 10 songs and without T40')
    names_c = ['matched', 'mismatch', 'silence']; names_k = ['(a) spans', '(b) tail', '(c) front', '(d) other']
    for label, keys in (('all 10 songs', SONGS), ('without Track00040', [k for k in SONGS if k != 'Track00040'])):
        R3r = r3_right(keys)
        a = agg(res, None, 'core', keys)
        cells = a['cells'] / R3r
        P(f'\n### {label}: total wrong_sa/R3R = {a["Ew"] / R3r:.4f}; sum of cells = {cells.sum():.4f}')
        P('class | ' + ' | '.join(names_k))
        for i, cn in enumerate(names_c):
            P(cn + ' | ' + ' | '.join(f'{cells[i * 4 + j]:.4f}' for j in range(4)))
        inscope = cells[0] + cells[1]
        P(f'in-scope (matched x (a+b)) = {inscope:.4f}; out-of-scope (rest of cells) = {cells.sum() - inscope:.4f}; total (rendered) = {a["Ew"] / R3r:.4f}')
    # stem vs MIDI boundaries info
    don = np.concatenate([res[k]['act']['d_on'] for k in SONGS]); doff = np.concatenate([res[k]['act']['d_off'] for k in SONGS])
    act_ = np.concatenate([res[k]['act']['active'] for k in SONGS]).astype(bool)
    P(f'\n## info: -15 dB stem activity vs MIDI (active segments {int(act_.sum())}/{len(act_)}): on-start median {np.median(don[act_]):+.1f} ms (p10..p90 {np.percentile(don[act_], 10):+.0f}..{np.percentile(don[act_], 90):+.0f}); off-end median {np.median(doff[act_]):+.1f} ms (p10..p90 {np.percentile(doff[act_], 10):+.0f}..{np.percentile(doff[act_], 90):+.0f})')
    open(D_DIR / 'ref_rows_report.txt', 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        report(json.load(open(D_DIR / 'ref_rows_raw.json')))
    else:
        main()

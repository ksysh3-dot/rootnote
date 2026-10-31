"""Step 4 report: D-oracle / D-full rows per setting, guards, leak, mechanical selection (M9).  usage: runpy.sh dev_report.py"""
import sys, json, datetime
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
from dcommon import *
import guards as G

GRID = G.th_grid()
dev = json.load(open(D_DIR / 'dev_raw.json'))
ref = json.load(open(D_DIR / 'ref_rows_raw.json'))
gd = json.load(open(D_DIR / 'guards_raw.json'))
R3R = r3_right(SONGS)
V5A_R3 = RAW_A['res']['t60_36_48']['R3']['v5a']['frac']
EPS = 1e-9


def pool(rows, key, f):
    return sum(dev[k][key][f] for k in SONGS)


def refpool(rn, f, keys=SONGS):
    return sum(ref[k][rn][f] for k in keys)


# ---- reference thresholds (step 2)
tab = {}
for rn in ("R2s'", 'S2-core', 'core'):
    Er, Ew = refpool(rn, 'E_right_sa'), refpool(rn, 'E_wrong_sa')
    tab[rn] = dict(F=Ew / R3R, M=Ew * (R3R / Er) / R3R)
THR = {v: min(0.5 * tab['S2-core'][v], max(2 * tab["R2s'"][v], tab["R2s'"][v] + 0.005)) for v in ('F', 'M')}
L = []
P = L.append
P(f'# step 4 development report -- {datetime.datetime.now().isoformat(timespec="seconds")}')
P(f"D-oracle wrong_sa/R3R thresholds (step 2, B1): F <= {THR['F']:.4f}, M <= {THR['M']:.4f}  (S2-core F {tab['S2-core']['F']:.4f} M {tab['S2-core']['M']:.4f}; R2s' F {tab[chr(82)+'2s' + chr(39)]['F']:.4f})")

# ---- non-fired hop check (M8)
rat = np.concatenate([dev[k]['nonfired']['ratios'] for k in SONGS if len(dev[k]['nonfired']['ratios'])])
P(f"\n## M8 non-fired hop check: re-measured LS (R2's LS, own f, window clipped to the run) / trace A.c.sigma at ON hops of runs the literal-setting detector did not touch: median {np.median(rat):+.2f} dB (p10..p90 {np.percentile(rat, 10):+.2f}..{np.percentile(rat, 90):+.2f}), {len(rat)} hops, runs {sum(dev[k]['nonfired']['nruns'] for k in SONGS)}; per song medians "
  + ', '.join(f"{k[-5:]}:{np.median(dev[k]['nonfired']['ratios']):+.1f}" for k in SONGS if len(dev[k]['nonfired']['ratios'])))
P(f"   -> within +-1 dB: {'YES' if abs(np.median(rat)) <= 1.0 else 'NO'}")

# ---- core baseline (shifted annotation)
cE = dict(Er=pool(None, 'core', 'E_right_sa'), Ew=pool(None, 'core', 'E_wrong_sa'), cells=np.sum([dev[k]['core']['cells'] for k in SONGS], axis=0))
c_in = (cE['cells'][0] + cE['cells'][1]) / R3R
c_out = cE['Ew'] / R3R - c_in
P(f"\n## core v1.5 chain (same simulation path, input-time annotation): wrong_sa/R3R = {cE['Ew'] / R3R:.4f}; in-scope (matched x (spans+tail)) = {c_in:.4f}; out-of-scope = {c_out:.4f}; right vs R3 = {10 * np.log10(cE['Er'] / R3R):+.2f} dB")
P(f"V5a core = {dev['t60_36_48']['core']['v5a']['frac'] * 100:.2f} % ; R3 = {V5A_R3 * 100:.2f} %")

rows = []
for gi, th in enumerate(GRID):
    r = dict(gi=gi, th=th)
    Er_o, Ew_o = pool(None, gi, 'oracle') if False else (sum(dev[k][str(gi)]['oracle']['E_right_sa'] for k in SONGS), sum(dev[k][str(gi)]['oracle']['E_wrong_sa'] for k in SONGS))
    r['or_wF'] = Ew_o / R3R; r['or_wM'] = Ew_o * (R3R / Er_o) / R3R; r['or_rdB'] = 10 * np.log10(Er_o / R3R)
    r['or_nshort'] = sum(dev[k][str(gi)]['oracle']['nshort'] for k in SONGS); r['or_tshort'] = sum(dev[k][str(gi)]['oracle']['tshort'] for k in SONGS)
    # B3
    b = [dev[k][str(gi)]['b3'] for k in SONGS]
    es = np.concatenate([x['err_start'] for x in b]); ee = np.concatenate([x['err_end'] for x in b])
    r['st_med'] = float(np.median(np.abs(es))) if len(es) else float('nan'); r['en_med'] = float(np.median(np.abs(ee))) if len(ee) else float('nan')
    ds = sum(x['n_start_den'] for x in b); ms = sum(x['n_start_match'] for x in b); de = sum(x['n_end_den'] for x in b); me = sum(x['n_end_match'] for x in b)
    r['n_st'] = (ms, ds); r['n_en'] = (me, de)
    r['missed'] = 1 - (ms + me) / max(ds + de, 1)
    r['missed_st'] = 1 - ms / max(ds, 1); r['missed_en'] = 1 - me / max(de, 1)
    btime = sum(x['bass_time'] for x in b)
    r['false_n'] = sum(x['n_false'] for x in b); r['false_rate'] = r['false_n'] / max(btime, 1e-9); r['false_rate_song'] = r['false_n'] / (30.0 * len(SONGS))
    r['n_events'] = sum(x['n_events'] for x in b)
    r['n_events_bass'] = sum(x['n_events_bass'] for x in b); r['false_bass_rate'] = sum(x['n_false_bass'] for x in b) / max(btime, 1e-9)
    r['birth_missing'] = (sum(x['start_birth_missing'] for x in b), sum(x['end_birth_missing'] for x in b))
    r['or_pass'] = dict(wrong=(r['or_wF'] <= THR['F'] + EPS and r['or_wM'] <= THR['M'] + EPS), right=(r['or_rdB'] >= -1.0), start=r['st_med'] <= 10.0, end=r['en_med'] <= 20.0,
                        missed=r['missed'] <= 0.10, false=r['false_rate'] <= 0.15)
    # D-full
    Er_f = sum(dev[k][str(gi)]['full']['E_right_sa'] for k in SONGS); Ew_f = sum(dev[k][str(gi)]['full']['E_wrong_sa'] for k in SONGS)
    cells = np.sum([dev[k][str(gi)]['full']['cells'] for k in SONGS], axis=0)
    r['f_w'] = Ew_f / R3R; r['f_in'] = (cells[0] + cells[1]) / R3R; r['f_out'] = Ew_f / R3R - r['f_in']; r['f_rdB'] = 10 * np.log10(Er_f / R3R); r['f_r_vs_core'] = 10 * np.log10(Er_f / cE['Er'])
    r['f_v5a'] = dev['t60_36_48'][str(gi)]['v5a']['frac']
    r['f_pass'] = dict(in_scope=r['f_in'] <= 0.5 * c_in, out_scope=r['f_out'] <= 1.10 * c_out, total=r['f_w'] <= cE['Ew'] / R3R + EPS, right=r['f_r_vs_core'] >= -1.0, v5a=(r['f_v5a'] - V5A_R3) <= 0.02)
    r['f_half_core'] = r['f_w'] <= 0.5 * cE['Ew'] / R3R
    # guards
    g = gd[str(gi)]; c = gd['-1']
    leads = [e for k in SONGS for e in dev[k][str(gi)]['leads']] + [g[k].get('lead_max', 0) for k in g]
    r['lead_max'] = int(max(leads)) if leads else 0
    gp = {}
    gp['V3i'] = g['steady8']['v3i_flips_per_s'] <= 0.5
    gp['V4b'] = g['bkp_0']['v4b_low_frac'] <= c['bkp_0']['v4b_low_frac'] + 0.02
    gp['RERISE'] = g['step25']['rerise_db'] <= c['step25']['rerise_db'] + EPS
    gp['V3d'] = g['step25']['v3d_line'] <= 1.0 and g['bass9']['v3d_bass'] <= 1.0
    gp['V3h_tail'] = g['bare100']['bare_tail_ms'] <= c['bare100']['bare_tail_ms'] + EPS and g['step25']['line_tail_ms'] <= c['step25']['line_tail_ms'] + EPS
    gp['V7d'] = g['logoff_37_49']['v7d_4.12'] <= c['logoff_37_49']['v7d_4.12'] + EPS and g['logoff_37_49']['v7d_4.73'] <= c['logoff_37_49']['v7d_4.73'] + EPS
    gp['gap'] = g['gapbkp']['gap_per_s'] <= c['gapbkp']['gap_per_s'] + 0.1
    gp['vib'] = all(g[k]['splits_per_s'] <= 0.1 for k in g if k.startswith('vib_'))
    gp['glide'] = g['glide']['splits_per_glide_max'] <= 1
    gp['E-r'] = g['gapbkp']['er_per_s'] <= 2.0 and g['bkp_0']['er_per_s'] <= 2.0
    gp['leak'] = r['lead_max'] <= 120
    r['guards'] = gp; r['guards_all'] = all(gp.values())
    r['gv'] = dict(v3i=g['steady8']['v3i_flips_per_s'], v4b=(g['bkp_0']['v4b_low_frac'], c['bkp_0']['v4b_low_frac']), rerise=(g['step25']['rerise_db'], c['step25']['rerise_db']),
                   v3d=(g['step25']['v3d_line'], g['bass9']['v3d_bass']), tail=(g['bare100']['bare_tail_ms'], g['step25']['line_tail_ms']),
                   v7d=(g['logoff_37_49']['v7d_4.12'], g['logoff_37_49']['v7d_4.73']), gap=g['gapbkp']['gap_per_s'], vib=[g[k]['splits_per_s'] for k in g if k.startswith('vib_')],
                   glide=g['glide']['splits_per_glide_max'], er=(g['gapbkp']['er_per_s'], g['bkp_0']['er_per_s'], g['gapbkp']['er_kick_share'], g['bkp_0']['er_kick_share']))
    rows.append(r)

P('\n## settings (th_db, th_cent, n_hop) -- D-oracle (stem-aware wrong/R3R F | M | right vs R3 dB | start med|err| ms | end med|err| ms | missed % | false /s bass-time | pass flags)')
for r in rows:
    th = r['th']
    P(f"#{r['gi']:2d} ({th['db']:.0f},{th['cent']:.0f},{th['nhop']}) | {r['or_wF']:.4f} | {r['or_wM']:.4f} | {r['or_rdB']:+.2f} | {r['st_med']:.1f} ({r['n_st'][0]}/{r['n_st'][1]}) | {r['en_med']:.1f} ({r['n_en'][0]}/{r['n_en'][1]}) | {100 * r['missed']:.1f} (st {100 * r['missed_st']:.0f}, en {100 * r['missed_en']:.0f}) | {r['false_rate']:.3f} (n {r['false_n']}, per song-s {r['false_rate_song']:.3f}) | "
      + ' '.join(f"{k}:{'ok' if v else 'FAIL'}" for k, v in r['or_pass'].items()) + f" | events {r['n_events']} (bass-relevant voices {r['n_events_bass']}; INFO restricted false rate {r['false_bass_rate']:.3f} /s), fragments dropped {r['or_nshort']}")
P('\n## settings -- D-full (wrong_sa/R3R | in-scope | out-of-scope | right vs core dB | V5a % | B2/right/V5a flags | <=0.5 x core (info))')
for r in rows:
    P(f"#{r['gi']:2d} | {r['f_w']:.4f} | {r['f_in']:.4f} | {r['f_out']:.4f} | {r['f_r_vs_core']:+.2f} | {100 * r['f_v5a']:.2f} | " + ' '.join(f"{k}:{'ok' if v else 'FAIL'}" for k, v in r['f_pass'].items()) + f" | {r['f_half_core']}")
P('\n## guards (D-full chain): ok/FAIL; values')
for r in rows:
    P(f"#{r['gi']:2d} | " + ' '.join(f"{k}:{'ok' if v else 'FAIL'}" for k, v in r['guards'].items()) + f" | lead_max {r['lead_max']} samples")
    gv = r['gv']
    P(f"      V3i {gv['v3i']:.3f}/s; V4b {gv['v4b'][0]:.3f} (core {gv['v4b'][1]:.3f}); RERISE {gv['rerise'][0]:.2f} (core {gv['rerise'][1]:.2f}); V3d line {gv['v3d'][0]:.2f} bass9 {gv['v3d'][1]:.2f}; tail bare {gv['tail'][0]:.1f} line {gv['tail'][1]:.1f}; "
      f"V7d {gv['v7d'][0]:.2f}/{gv['v7d'][1]:.2f}; gap {gv['gap']:.2f}/s; vib {[round(x, 2) for x in gv['vib']]}; glide max {gv['glide']}; E-r gapbkp {gv['er'][0]:.2f}/s bkp_0 {gv['er'][1]:.2f}/s (kick +-30ms share {gv['er'][2]:.2f}, {gv['er'][3]:.2f})")
c = gd['-1']
P(f"      core: V3i {c['steady8']['v3i_flips_per_s']:.3f}; V4b {c['bkp_0']['v4b_low_frac']:.3f}; RERISE {c['step25']['rerise_db']:.2f}; V3d line {c['step25']['v3d_line']:.2f} bass9 {c['bass9']['v3d_bass']:.2f}; tail bare {c['bare100']['bare_tail_ms']:.1f} line {c['step25']['line_tail_ms']:.1f} (abs limit 40 ms, m3); V7d {c['logoff_37_49']['v7d_4.12']:.2f}/{c['logoff_37_49']['v7d_4.73']:.2f}; gap {c['gapbkp']['gap_per_s']:.2f}/s")

# ---- selection (M9)
ok = [r for r in rows if r['guards_all']]
P('\n## M9 selection: settings whose D-full guards ALL hold: ' + (', '.join(f"#{r['gi']}" for r in ok) if ok else 'none'))
sel = None
if ok:
    sel = min(ok, key=lambda r: (r['or_wF'], r['or_wM']))
    P(f"selected: #{sel['gi']} {sel['th']} (lowest D-oracle wrong_sa F = {sel['or_wF']:.4f})")
    P('D-oracle pass flags: ' + str(sel['or_pass']) + ' -> ' + ('PASS' if all(sel['or_pass'].values()) else 'FAIL'))
    P('D-full pass flags: ' + str(sel['f_pass']) + ' -> ' + ('PASS' if all(sel['f_pass'].values()) else 'FAIL'))
    json.dump(dict(setting=sel['th'], gi=sel['gi'], frozen_at=datetime.datetime.now().isoformat(timespec='seconds')), open(D_DIR / 'frozen_setting.json', 'w'))
else:
    P('=> "설정 없음": the confirmation tracks are NOT processed (16.8.1 M9).')
    # information only: closest settings
    best = min(rows, key=lambda r: sum(not v for v in r['guards'].values()))
    P(f"information: fewest failing guards = #{best['gi']} {best['th']} with {sum(not v for v in best['guards'].values())} failing ({[k for k, v in best['guards'].items() if not v]})")
open(D_DIR / 'dev_report.txt', 'w').write('\n'.join(L))
print('\n'.join(L))

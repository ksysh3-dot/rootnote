import json, time
import numpy as np
K = '/home/ksysh/r3a-dev/plan16/K/'
res = json.load(open(K + 'stage0_raw.json'))
SONGS = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
BASS = [k for k in SONGS if not res[k]['nobass']]
L = []
P = lambda s='': L.append(s)
P(f'# plan16 K stage 0 -- {time.strftime("%Y-%m-%dT%H:%M:%S")}  (literal setting: thr 9 dB, W 60 ms, gain -12 dB, cap +3 dB, K3 120 dB/s)')
P('\n## detector (info)')
P('song | windows | MIDI H hits | recall(+-40ms) | false windows (share) | bass starts in false windows / bass notes')
for k in SONGS:
    r = res[k]; d = r.get('det')
    P(f'{k} | {r["n_windows"]} | ' + (f'{d["n_hits"]} | {d["recall"]:.3f} | {d["false_win"]} ({d["false_share"]:.2f}) | {d["bass_in_false"]}/{d["n_bass_notes"]}' if d else 'no hits'))
# 0a
P('\n## 0a separation (bass songs pooled: ' + ', '.join(BASS) + ')')
agg = {}
for g in 'ABC':
    a = dict(n_ev=0, n_hop=0, k_hop=np.zeros(3), k_ev=np.zeros(3), cons=0, anyk=0, endk=0, ctrl_hop=0, ctrl_ev=0, rates=[], w_all=0.0, w_cons=0.0, births=0)
    for k in BASS:
        s = res[k]['stats'][g]
        for kk in ('n_ev', 'n_hop', 'cons', 'anyk', 'endk', 'ctrl_hop', 'ctrl_ev', 'w_all', 'w_cons', 'births'):
            a[kk] += s[kk]
        a['k_hop'] += np.array(s['k_hop']); a['k_ev'] += np.array(s['k_ev']); a['rates'] += s['rates']
    agg[g] = a
names = {'A': 'A drum-cause silence voices', 'B': 'B matched (bass-compatible) voices', 'C': 'C other silence voices (info)'}
P('group | events (births) | K1 hop % | K2 hop % | K3 hop % | K1 ev % | K2 ev % | K3 ev % | confirm consecutive % | any-hop 2of3 % | last-hop 2of3 % | K2 control hop % | K2 control ev %')
for g in 'ABC':
    a = agg[g]; n = max(a['n_ev'], 1); nh = max(a['n_hop'], 1)
    P(f'{names[g]} | {a["n_ev"]} ({a["births"]}) | ' + ' | '.join(f'{100 * x / nh:.1f}' for x in a['k_hop']) + ' | ' + ' | '.join(f'{100 * x / n:.1f}' for x in a['k_ev']) +
      f' | {100 * a["cons"] / n:.1f} | {100 * a["anyk"] / n:.1f} | {100 * a["endk"] / n:.1f} | {100 * a["ctrl_hop"] / nh:.1f} | {100 * a["ctrl_ev"] / n:.1f}')
a = agg['A']
P(f'A energy-weighted consecutive confirmation: {100 * a["w_cons"] / max(a["w_all"], 1e-30):.1f} %')
P('\nper song: group A (events, cons %) | group B (events, cons %) | K2 control hop % A / B')
for k in BASS:
    s = res[k]['stats']
    f = lambda g: f'{s[g]["n_ev"]}, {100 * s[g]["cons"] / max(s[g]["n_ev"], 1):.0f}%'
    c = lambda g: f'{100 * s[g]["ctrl_hop"] / max(s[g]["n_hop"], 1):.1f}'
    P(f'{k} | A {f("A")} | B {f("B")} | {c("A")} / {c("B")}')
P('\nK3 decay-rate distribution (dB/s) at event hops with a defined statistic (peak >= 15 ms back): deciles')
for g in 'AB':
    r = np.array(agg[g]['rates']); r = r[np.isfinite(r)]
    P(f'{g}: n {len(r)}  ' + ' '.join(f'p{q}={np.percentile(r, q):.0f}' for q in (10, 25, 50, 75, 90)) + f'  share <=120: {100 * np.mean(r <= 120):.1f} %' if len(r) else f'{g}: none')
pa = 100 * agg['A']['cons'] / max(agg['A']['n_ev'], 1); pb = 100 * agg['B']['cons'] / max(agg['B']['n_ev'], 1)
ca = 100 * agg['A']['ctrl_hop'] / max(agg['A']['n_hop'], 1); cb = 100 * agg['B']['ctrl_hop'] / max(agg['B']['n_hop'], 1)
ok_a, ok_b, ok_c = pa <= 40, pb >= 80, (ca <= 25 and cb <= 25)
P(f'\n0a conditions: A cons {pa:.1f} % <= 40 : {"PASS" if ok_a else "FAIL"};  B cons {pb:.1f} % >= 80 : {"PASS" if ok_b else "FAIL"};  K2 control hop A {ca:.1f} % / B {cb:.1f} % <= 25 : {"PASS" if ok_c else "FAIL"}')
# 0b
P('\n## 0b upper bound (units = energy / R3R)')
tot = {n: 0.0 for n in ('core', 'oracle', 'oracleA', 'hard', 'L20', 'L35', 'evid')}
P('song | core drum | R_det | oracle | oracle reading A | hard oracle | evidence (literal)')
for k in BASS:
    r = res[k]; c = r['core']['drum']
    P(f'{k} | {c:.4f} | {100 * r["rdet"]["r_det"]:.1f} % | ' + ' | '.join(f'{r["runs"][n]["drum"]:.4f}' for n in ('oracle', 'oracleA', 'hard', 'evid')))
    tot['core'] += c
    for n in ('oracle', 'oracleA', 'hard', 'L20', 'L35', 'evid'):
        tot[n] += r['runs'][n]['drum']
ein = sum(res[k]['rdet']['e_in'] for k in BASS); eout = sum(res[k]['rdet']['e_out'] for k in BASS)
t25 = res['Track00025']
P(f'pooled core {tot["core"]:.4f} | R_det pooled {100 * ein / (ein + eout):.1f} % | oracle {tot["oracle"]:.4f} | A {tot["oracleA"]:.4f} | hard {tot["hard"]:.4f} | evid {tot["evid"]:.4f}')
red = lambda n: 100 * (1 - tot[n] / tot['core'])
nt = lambda n: 100 * (1 - (tot[n] - t25['runs'][n]['drum']) / (tot['core'] - t25['core']['drum']))
P(f'reduction pooled: oracle R_max {red("oracle"):.1f} %, reading A {red("oracleA"):.1f} %, hard {red("hard"):.1f} %, evidence {red("evid"):.1f} %, L20 {red("L20"):.1f} %, L35 {red("L35"):.1f} %')
P(f'reduction without T25: oracle {nt("oracle"):.1f} %, A {nt("oracleA"):.1f} %, hard {nt("hard"):.1f} %, evidence {nt("evid"):.1f} %')
P(f'per-song oracle reduction: ' + ', '.join(f'{k[-2:]} {100 * (1 - res[k]["runs"]["oracle"]["drum"] / res[k]["core"]["drum"]):.0f}%' for k in BASS if res[k]['core']['drum'] > 1e-6))
ok_b0 = red('oracle') >= 55
P(f'0b condition: R_max {red("oracle"):.1f} % >= 55 : {"PASS" if ok_b0 else "FAIL (stop; Opus resets the threshold)"}')
# 0c
P('\n## 0c attack upper bound: co-hit attack energy change vs core (dB), notes with H hit within +-30 ms')
P('song | co-hit notes (used) | oracle (L=inf) | L=20 ms | L=35 ms | evidence (literal) | worst-note 10th percentile (L20)')
tt = {n: [0.0, 0.0] for n in ('oracle', 'L20', 'L35', 'evid')}
for k in BASS:
    r = res[k]
    a = r['runs']['L20']['attack']
    if a['n_ok'] < 8:
        P(f'{k} | {r["n_cohit"]} ({a["n_ok"]}) <8 excluded'); continue
    cells = []
    for n in ('oracle', 'L20', 'L35', 'evid'):
        at = r['runs'][n]['attack']; cells.append(f'{at["db"]:+.2f}'); tt[n][0] += at['e0']; tt[n][1] += at['e1']
    nd = np.array(a['note_db'])
    P(f'{k} | {r["n_cohit"]} ({a["n_ok"]}) | ' + ' | '.join(cells) + f' | {np.percentile(nd, 10):+.1f}')
pool = {n: 10 * np.log10((tt[n][1] + 1e-30) / (tt[n][0] + 1e-30)) for n in tt}
P('pooled (songs with >= 8 co-hit notes): ' + ', '.join(f'{n} {v:+.2f} dB' for n, v in pool.items()))
ok_c0 = pool['L20'] >= -2 and pool['L35'] >= -2
P(f'0c condition: L20 {pool["L20"]:+.2f}, L35 {pool["L35"]:+.2f} >= -2 dB : {"PASS" if ok_c0 else "FAIL (stop; Opus resets the attack threshold)"}')
P('\n## INFORMATION (post-run additions; not decisions)')
P('confirmation by kind (consecutive): ' + ', '.join(f'{g}: births {sum(res[k]["stats"][g]["cons_birth"] for k in BASS)}/{sum(res[k]["stats"][g]["births"] for k in BASS)}, rises {sum(res[k]["stats"][g]["cons_rise"] for k in BASS)}/{sum(res[k]["stats"][g]["n_rise"] for k in BASS)}' for g in 'ABC'))
P('detector band diagnostics on MIDI H hits (anywhere in [-1, +15] blocks): song | hits | low band >= 9 dB % | high band >= 9 dB % | both in the same block %')
for k in SONGS:
    b = res[k]['band_diag']
    P(f'{k} | {b["n"]} | {100 * b["low"]:.0f} | {100 * b["high"]:.0f} | {100 * b["both_same_block"]:.0f}')
P('oracle (reading B, gain -12 dB) R_det and R_max for the registered detector settings (bass songs, pooled), cause-2 units:')
P('thr_W | windows (all songs) | R_det % | oracle reduction % | oracle reduction w/o T25 %')
for key in ('6_40', '6_60', '9_40', '9_60', '12_40', '12_60'):
    ein_ = sum(res[k]['sweep'][key]['e_in'] for k in BASS); eout_ = sum(res[k]['sweep'][key]['e_out'] for k in BASS)
    dr = sum(res[k]['sweep'][key]['drum'] for k in BASS); c0 = sum(res[k]['core']['drum'] for k in BASS)
    d25 = res['Track00025']['sweep'][key]['drum']; c25 = res['Track00025']['core']['drum']
    P(f'{key} | {sum(res[k]["sweep"][key]["n_win"] for k in SONGS)} | {100 * ein_ / max(ein_ + eout_, 1e-30):.1f} | {100 * (1 - dr / c0):.1f} | {100 * (1 - (dr - d25) / (c0 - c25)):.1f}')
P(f'\nSTOP FLAGS: 0a {"stop" if not (ok_a and ok_b and ok_c) else "ok"}, 0b {"stop" if not ok_b0 else "ok"}, 0c {"stop" if not ok_c0 else "ok"}')
open(K + 'stage0_report.txt', 'w').write('\n'.join(L))
print('\n'.join(L))

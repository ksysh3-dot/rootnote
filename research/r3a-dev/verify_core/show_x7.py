import json
V = '/home/ksysh/r3a-dev/verify_core/'
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
x = json.load(open(V + 'xcheck_v7a.json'))['v7a']
print('V7a  energy >1.5 kHz re 150-600 Hz (dB), literal FFT definition, out_db -18:  xcheck | suite')
for sn, d in x.items():
    print('  ', sn, ' '.join(f'{k}: {v:6.1f}|{suite[smap[k]]["V7"]["a_d18"][sn]["hi_over_lo_db"]:6.1f}' for k, v in d.items()))
x = json.load(open(V + 'xcheck_v9.json'))['v9']
print('V9 core side (own birth count from the voice trace):', json.dumps(x))
print('   suite: ', {k: (v['births'], round(v['births_per_s'], 3)) for k, v in suite['verify_A']['V9'].items() if isinstance(v, dict)}, ' P1', {k: (v['births'], round(v['births_per_s'], 1)) for k, v in suite['p1_baseline']['V9'].items()})
x = json.load(open(V + 'xcheck_v6.json'))['v6']['A']
s = suite['verify_A']['V6']; p = suite['p1_baseline']['V6']
print(f'V6 core (config A): coverage xcheck {x["coverage"]:.4f} | suite {s["coverage"]:.4f} | P1 {p["coverage"]:.4f}      wrong share xcheck {x["wrong_share"]:.4f} | suite {s["wrong_share"]:.4f} | P1 {p["wrong_share"]:.4f}')
for t, ts in zip(x['per_track'], s['per_track']):
    if 'error' in t:
        print('  ', t); continue
    print(f'   {t["name"]}: loud {t["loud"]} (suite {ts["loud_hops"]}) cov {t["covered"]} (suite {ts["covered"]}) wrong share {t["share"]:.4f} (suite {ts["wrong"]/ts["total"]:.4f})')
print('  wrong-note share by voice state (2 ON, 1 CAND, 3 REL):', x['wrong_share_by_state'], ' weight share by state', x['weight_share_by_state'])
print('  wrong weight by nearest harmonic of a sounding note:', {k: round(v, 3) for k, v in x['wrong_weight_by_nearest_harmonic'].items()})

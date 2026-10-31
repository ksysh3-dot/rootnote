import json, sys
def load(label):
    return json.load(open(f'/home/ksysh/r3a-dev/core_results/{label}/results.json'))['metrics']
A = load('verify_A'); P = load('p1_baseline')
print('V7 a_d  core:', json.dumps(A['V7']['a_d']))
print('V7 a_d  P1  :', json.dumps(P['V7']['a_d']))
print('V7 a_d18 core:', json.dumps(A['V7']['a_d18']))
print('V7 a_d18 P1  :', json.dumps(P['V7']['a_d18']))
print('V7 rough core:')
for k, v in A['V7']['rough'].items():
    p = P['V7']['rough'][k]
    print(f'  {k:30s} total {v["total"]:.4g} vs P1 {p["total"]:.4g} ({100*(v["total"]/p["total"]-1):+.1f} %)  gr_low_max {v["gr_low_max"]:.2f} vs {p["gr_low_max"]:.2f} ({v["gr_low_max"]-p["gr_low_max"]:+.2f})')
print('V6 core per track:')
for t, p in zip(A['V6']['per_track'], P['V6']['per_track']):
    print(t['name'], 'loud', t['loud_hops'], 'cov', t['covered'], f'({t["covered"]/max(t["loud_hops"],1):.3f}) P1 cov {p["covered"]/max(p["loud_hops"],1):.3f}',
          f'wrong share {t["wrong"]/max(t["total"],1e-30):.3f} vs P1 {p["wrong"]/max(p["total"],1e-30):.3f}', 'tp', t['tp'], 'midi files', t['n_midi_files'])
for k in ('coverage', 'wrong_share', 'wrong_share_tol60', 'wrong_share_nodrum', 'wrong_share_w23'):
    print(k, 'core', A['V6'][k], 'P1', P['V6'][k])

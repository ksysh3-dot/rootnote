import json
x = json.load(open('/home/ksysh/r3a-dev/verify_core/xcheck_v2.json'))['v2']
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
print('V2 dphi (rad) k=2, k=3 | layer re P1 (dB) xcheck   vs suite dphi k2, k3 | V1 layer level re P1 (dB)')
for k, v in x.items():
    s = suite[smap[k]]
    sv1 = s['V1']['layer_level_db'] - suite['p1_baseline']['V1']['layer_level_db']
    print(f'  {k:3s} {v["dphi_k2_mean_rad"]:+.5f} {v["dphi_k3_mean_rad"]:+.5f} | {v["layer_re_P1_db"]:+7.3f}      suite {s["V2"]["k2"]["dphi_mean_rad"]:+.5f} {s["V2"]["k3"]["dphi_mean_rad"]:+.5f} | {sv1:+7.3f}')

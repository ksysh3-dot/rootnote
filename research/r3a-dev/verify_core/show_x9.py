import json
V = '/home/ksysh/r3a-dev/verify_core/'
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
x = json.load(open(V + 'xcheck_v3a_v7e.json'))
print('V3a  peak of cycle-averaged 150-600 Hz power (ms): xcheck output | xcheck layer-only | suite')
for k, v in x['v3a'].items():
    print(f'  {k:3s} {v["output"]["peak_ms"]:3d} | {v["layer"]["peak_ms"]:3d} | {suite[smap[k]]["V3bare"]["v3a"]["peak_ms"]:3d}')
print('V7d  LOGOFF hit energy (dB), +-50 ms, out_db -5:')
for k, v in x['v7e'].items():
    print(f'  {k:3s} ' + '  '.join(f'{kk}: {vv:7.1f}' for kk, vv in v.items()))
p1 = x['v7e']['P1']
for k, v in x['v7e'].items():
    if k != 'P1':
        print(f'  {k:3s} re P1: ' + '  '.join(f'{kk}: {vv - p1[kk]:+6.1f}' for kk, vv in v.items()))

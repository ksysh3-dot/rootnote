import json
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/V16A')
d = json.load(open(V / 'suite_values16b.json')); SV, P1 = d['SV'], d['P1']
labs = ['v15', 'a2', 'c8a2', 'i8a2', 'i16a2', 'ii8a2', 'ii16a2']
ids = list(SV['v15'].keys())
print('| id | ' + ' | '.join(labs) + ' | P1 |')
for i in ids:
    def f(v):
        try: return f'{float(v):.4g}'
        except Exception: return str(v)
    print(f'| {i} | ' + ' | '.join(f(SV[l][i]) for l in labs) + f' | {f(P1[i])} |')
BU = json.load(open(V / 'burst16b.json'))
print('\nBURST', {k: round(v['burst_R1'], 2) for k, v in BU.items()})
R = json.load(open(V / 'rho16b.json'))
print('\nRHO', {k: round(v['rho'], 4) for k, v in R.items()})
L = json.load(open(V / 'logoff45b.json'))
print('\nLOGOFF45'); [print(' ', k, v) for k, v in L.items()]
for l in labs:
    s = json.load(open(V / f'right_{l}.json'))['summary']
    print(l, 'right dB', round(s['all10']['right_vs_R3_dB_sa'], 3), 'wrong_sa_F', round(s['all10']['wrong_sa_F'], 4))

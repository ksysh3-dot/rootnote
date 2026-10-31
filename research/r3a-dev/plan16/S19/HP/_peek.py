import json
A = '/home/ksysh/r3a-dev/plan16/A5P/suite/'
H = '/home/ksysh/r3a-dev/plan16/S19/HP/suite/'
rows = {'b3p2': A + 'b3p2', 'hp8_150c1': H + 'hp8_150c1', 'hp8_135c1': H + 'hp8_135c1', 'hp8_150c0': H + 'hp8_150c0'}
V = {l: {c['id']: c['value'] for c in json.load(open(p + '/results.json'))['checks']} for l, p in rows.items()}
for k in V['b3p2']:
    print(k, *[V[l].get(k) if not isinstance(V[l].get(k), float) else round(V[l][k], 4) for l in rows])

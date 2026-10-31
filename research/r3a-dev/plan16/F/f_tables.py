"""Collect suite results (checks list) for v15 / rho1.5 / rho2 / rho3 / P1 and the guard tests of 16.17."""
import json
from pathlib import Path
F = Path('/home/ksysh/r3a-dev/plan16/F')
labs = ['v15', 'rho1.5', 'rho2', 'rho3']
J = {l: json.loads((F / 'suite' / l / 'results.json').read_text()) for l in labs}
ck = {l: {c['id']: c for c in J[l]['checks']} for l in labs}
ids = list(ck['v15'].keys())
print('| id | what | v1.5 | rho1.5 | rho2 | rho3 | P1 | limit |')
print('|---|---|---|---|---|---|---|---|')
def fm(v):
    if v is None: return 'n/a'
    try: return f'{float(v):.4g}'
    except Exception: return str(v)
for i in ids:
    c = ck['v15'][i]
    print(f"| {i} | {c['desc'][:70]} | " + ' | '.join(fm(ck[l][i]['value']) + ('' if ck[l][i]['ok'] else ' ✗') for l in labs) + f" | {fm(c.get('p1'))} | {c['op']} {c['limit']} |")
json.dump({l: {i: ck[l][i]['value'] for i in ids} for l in labs}, open(F / 'suite_values.json', 'w'), indent=1)

"""Collects the suite results (checks) of the 18.3 rows into one table + suite_values16.json. usage: tables16.py [label ...]"""
import json, sys
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/V16A')
labs = sys.argv[1:] or ['v15', 'c8', 'c16', 'c32', 'a2', 'c16a2']
J = {l: json.loads((V / 'suite' / l / 'results.json').read_text()) for l in labs}
ck = {l: {c['id']: c for c in J[l]['checks']} for l in labs}
ids = list(ck[labs[0]].keys())


def fm(v):
    if v is None: return 'n/a'
    try: return f'{float(v):.4g}'
    except Exception: return str(v)


print('| id | what | ' + ' | '.join(labs) + ' | P1 | limit |')
print('|---|---|' + '---|' * (len(labs) + 2))
for i in ids:
    c = ck[labs[0]][i]
    print(f"| {i} | {c['desc'][:60]} | " + ' | '.join(fm(ck[l][i]['value']) for l in labs) + f" | {fm(c.get('p1'))} | {c['op']} {c['limit']} |")
json.dump({l: {i: ck[l][i]['value'] for i in ids} for l in labs}, open(V / 'suite_values16.json', 'w'), indent=1)
json.dump({i: ck[labs[0]][i].get('p1') for i in ids}, open(V / 'suite_p1_values16.json', 'w'), indent=1)

import json
V = '/home/ksysh/r3a-dev/verify_core/'
x = json.load(open(V + 'xcheck_v0.json'))['v0']
for k, v in x.items():
    if k in ('extra_blocks', 'switch'):
        continue
    print('V0 subset', k, 'max|diff| per algo 0-14:', {a: d for a, d in v.items()})
print('extra:', x['extra_blocks'])
for k, v in x['switch'].items():
    print('switch:', k, v)

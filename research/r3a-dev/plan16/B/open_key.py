import json, hashlib, re, pathlib
B = pathlib.Path('/home/ksysh/r3a-dev/plan16/B')
raw = (B / 'key.json').read_bytes()
k = json.loads(raw)
print('file sha256', hashlib.sha256(raw).hexdigest())
print('blob sha256', hashlib.sha256(json.dumps(dict(key=k.get('key', k), seed=k.get('seed')), sort_keys=True).encode()).hexdigest())
for n, v in sorted(k.get('key', k).items()):
    print(n, v)
for i, l in enumerate((B / 'inj.py').read_text().splitlines(), 1):
    if re.search(r"TYPES|V\['E\d'\]|# E\d|E\d:", l):
        print(i, l)

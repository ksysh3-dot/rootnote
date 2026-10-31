import json, subprocess, glob
j = json.load(open('/home/ksysh/r3a-dev/plan16/S19/NF/suite/b3p2/results.json'))
print(j.keys())
for c in j['checks']:
    if c['id'] in ('V3d', 'V3a', 'V3b', 'V3i.trans'):
        print(c)

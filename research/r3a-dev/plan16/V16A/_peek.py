import json
j = json.load(open('/home/ksysh/r3a-dev/plan16/V16A/suite/v15/results.json'))
for c in j['checks']:
    print(c['id'], '|', c['desc'][:80], '|', c['value'])

import json, sys
label = sys.argv[1]
keys = sys.argv[2:]
j = json.load(open(f'/home/ksysh/r3a-dev/core_results/{label}/results.json'))
M = j['metrics']
print('meta:', {k: j['meta'][k] for k in ('lib_sha', 'source_commit', 'seconds', 'voice_trace_mismatch', 'wrapper')})
def strip(o, depth=0):
    if isinstance(o, dict):
        return {k: strip(v, depth + 1) for k, v in o.items() if k != 'arrays' and k != 'trace'}
    if isinstance(o, list) and len(o) > 40:
        return f'<list {len(o)}>'
    return o
for k in keys or M.keys():
    print('=====', k)
    print(json.dumps(strip(M.get(k)), indent=1)[:6000])

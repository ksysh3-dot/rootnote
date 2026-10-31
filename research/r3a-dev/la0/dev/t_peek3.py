import json, numpy as np
d = json.load(open('/home/ksysh/r3a-dev/la0/dev2.json'))
rows = list(d['synthetic'].keys())
songs = list(d['songs'].keys())
print('songs', songs)
def pooled(r, songs):
    w = sum(d['songs'][s][r]['wrong'] for s in songs if r in d['songs'][s]); rt = sum(d['songs'][s][r]['right'] for s in songs if r in d['songs'][s])
    return w / (w + rt), rt
base = None
for r in ['core', 'p1'] + [x for x in d['songs'][songs[0]].keys() if x not in ('core', 'p1')]:
    sh, rt = pooled(r, songs)
    print(f'{r:12s} V6b {100*sh:5.1f}%  right {rt:.3g}')
print(json.dumps(d['classifier'], indent=0)[:1500])
print(json.dumps(d['ratios']))
for r in ['core', 'p1', 'LA-bh-64', 'LA-det-64', 'LA-bh-217']:
    s = d['synthetic'][r]
    print(r, {k: round(v, 2) for k, v in s.items() if k in ('rerise_db', 'rerise_n_above6', 'v3d_line_median', 'v3d_bass_median', 'v7d_4.12', 'v7d_4.73', 'line_tail_settled', 'line_tail')})

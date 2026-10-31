import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import numpy as np
import a5rows as AR
from pathlib import Path
A = Path('/home/ksysh/r3a-dev/plan16/A5')
db = lambda p: 10 * np.log10(max(p, 1e-30))
R = {}
LABS = [l for l in AR.ROWS if (A / f'primary_{l}.json').exists()]
for l in LABS:
    R[l] = sorted(json.load(open(A / f'primary_{l}.json')), key=lambda r: (r['song'], r['t0']))
summ = {}
print(f'{"row":18s} {"pooled lo/mid dB":>16s} {"lo dBFS":>8s} {"mid dBFS":>9s} {"jumps>6dB":>9s}  per-window ratio dB ' + ' | '.join(f'{w["song"]}{w["t0"]:g}' for w in R['base']))
for l in LABS:
    rows = R[l]
    lo = sum(r['p_lo'] for r in rows); mid = sum(r['p_mid'] for r in rows)
    j = sum(r['jumps'] for r in rows) if rows[0]['jumps'] is not None else None
    pw = [db(r['p_lo']) - db(r['p_mid']) for r in rows]
    summ[l] = dict(ratio=db(lo) - db(mid), lo=db(lo / len(rows)), mid=db(mid / len(rows)), jumps=j, per_window=pw, per_mid=[db(r['p_mid']) for r in rows], per_lo=[db(r['p_lo']) for r in rows],
                   per_jumps=[r['jumps'] for r in rows], checked=sum(r['checked'] or 0 for r in rows))
    print(f'{AR.NAMES[l]:18s} {summ[l]["ratio"]:16.2f} {summ[l]["lo"]:8.1f} {summ[l]["mid"]:9.1f} {str(j):>9s}  ' + ' '.join(f'{x:6.1f}' for x in pw))
json.dump(summ, open(A / 'primary_summary.json', 'w'), indent=1)

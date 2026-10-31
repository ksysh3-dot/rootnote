"""LOGOFF 37-49 s 45 Hz ON fraction and gaps (report-only), A5 rows (copy of plan16/V16A/logoff45b.py)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5PP')
import numpy as np
import a5ppcommon as VC
import a5pprows as AR
import research_core_signals as S
lib = VC.load(str(VC.LIB16B))
x = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
out = {}
for name in ['v15'] + AR.GRID:
    p = AR.ROWS[name][2]
    y, tr, _ = VC.render(lib, x, VC.make_vec(p))
    t = VC.CA.trace_dict(tr)
    tc, _ = VC.CA.hop_time(t['hop'][:, 0])
    on = ((t['state'] == 2) & (np.abs(t['f_osc'] - 45) <= 6)).any(axis=1)
    on = on[tc > 0.5]
    first = int(np.argmax(on)) if on.any() else 0
    seg = on[first:]
    gaps = []; run = 0
    for v in seg:
        if not v: run += 1
        elif run: gaps.append(run); run = 0
    if run: gaps.append(run)
    out[name] = dict(hops=int(len(seg)), on_frac=float(seg.mean()), n_gaps=len(gaps), gap_hops_total=int(sum(gaps)), longest_gap=int(max(gaps)) if gaps else 0)
    print(name, out[name], flush=True)
json.dump(out, open(VC.A5_DIR / 'logoff45_pp.json', 'w'), indent=1)

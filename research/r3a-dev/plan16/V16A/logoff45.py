"""Does the synthetic V3g note-loss (35/45 Hz noREL) show up on the user's LOGOFF (45 Hz sine sub-bass)? LOGOFF 37-49 s: per row, hops (after 0.5 s)
with an ON voice within 40-50 Hz, ON->not-ON gaps (runs of hops without), and the longest gap (hops, 5.33 ms each)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S
lib = VC.load(str(VC.LIB16A))
x = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
out = {}
for name, par in (('v1.5', (0, 0)), ('A1 8', (0, 8)), ('A2 1.5', (1.5, 0)), ('A1+A2 8/1.5', (1.5, 8))):
    y, tr, _ = VC.render(lib, x, VC.make_params(*par))
    t = VC.CA.trace_dict(tr)
    tc, _ = VC.CA.hop_time(t['hop'][:, 0])
    on = ((t['state'] == 2) & (np.abs(t['f_osc'] - 45) <= 6)).any(axis=1)
    ok = tc > 0.5
    on = on[ok]
    first = int(np.argmax(on)) if on.any() else 0
    seg = on[first:]
    gaps = []; run = 0
    for v in seg:
        if not v: run += 1
        elif run: gaps.append(run); run = 0
    if run: gaps.append(run)
    out[name] = dict(hops=int(len(seg)), on_frac=float(seg.mean()), n_gaps=len(gaps), gap_hops_total=int(sum(gaps)), longest_gap=int(max(gaps)) if gaps else 0)
    print(name, out[name], flush=True)
json.dump(out, open(VC.V_DIR / 'logoff45.json', 'w'), indent=1)

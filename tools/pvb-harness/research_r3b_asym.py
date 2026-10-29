"""R3-b step 1: asymmetric operating point. For each cue and direction (block halving when cue <= th, or >= th),
set the threshold so that MUSDB loses only q of its correct halvings (q = 0.5, 1, 2 %), then report what share of
BabySlakh's wrong halvings that threshold removes, and both sets' frame balance (bad removed - good lost, scaled to
totals). Usage: asym_gate.py feat_musdb.json feat_slakh.json"""
import json, sys
import numpy as np
M, S = (json.load(open(p)) for p in sys.argv[1:3])
cues = [k for k, v in M['frames']['good'][0].items() if isinstance(v, (int, float))]
print('totals musdb', M['totals'], 'slakh', S['totals'])
arr = lambda d, kind, c: np.array([x.get(c, np.nan) for x in d['frames'][kind]], float)
for c in cues:
    for sign in (1, -1):                      # sign 1: block when cue <= th; -1: block when cue >= th
        mg, mb, sg, sb = (sign * arr(d, k, c) for d in (M, S) for k in ('good', 'bad'))
        if np.isfinite(mg).mean() < .5: continue
        out = []
        for q in (.005, .01, .02):
            th = np.nanquantile(mg, q)
            f = lambda v: float(np.mean(np.isfinite(v) & (v <= th)))
            balM = f(mb) * M['totals']['bad'] - f(mg) * M['totals']['good']
            balS = f(sb) * S['totals']['bad'] - f(sg) * S['totals']['good']
            out.append(f"q{q*100:.1f}%: slakh bad -{100*f(sb):4.1f}% good -{100*f(sg):4.1f}% bal {balS:+7.0f} | musdb bad -{100*f(mb):4.1f}% bal {balM:+6.0f}")
        print(f"{c:10s} {'<=' if sign == 1 else '>='}  " + '  ||  '.join(out))

"""RERISE and V3h tail (report-only, 18.9) on the real output layer of the 25 dB gated line, for P1 and the A5 rows (copy of plan16/V16A/rerise16b.py)."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import numpy as np
import a5common as VC
import a5rows as AR
import research_core_metrics as M
import research_core_signals as S

M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0), ('ampSlewDb', 0), ('slewOnsetMode', 0)]
FS = 48000
ROWS = ['p1', 'v15', 'base'] + AR.A5LABELS


def rerise(env, t0s):
    vals = []; fell = 0
    for t0 in t0s:
        t_e = t0 + 0.125
        ref = float(np.mean(env[int((t_e - .045) * FS):int((t_e - .008) * FS)]))
        if ref <= 1e-12:
            continue
        line = 0.1 * ref
        post = env[int(t_e * FS):int((t_e + .120) * FS)]
        below = np.flatnonzero(post < line)
        if not len(below):
            vals.append(0.0); continue
        fell += 1
        k = below[0]
        vals.append(max(0.0, float(20 * np.log10(max(post[k:].max(), 1e-30) / line))))
    vals = np.array(vals)
    return dict(median=float(np.median(vals)), n_above6=int((vals > 6).sum()), n=len(vals), n_fell=fell, p90=float(np.percentile(vals, 90)), vals=vals.tolist())


def tail(env, t0s):
    out = []
    for t0 in t0s:
        ref = float(np.mean(env[int((t0 + .06) * FS):int((t0 + .11) * FS)]))
        i1 = int((t0 + .125) * FS); seg = env[i1:i1 + int(.12 * FS)]; ok = seg <= .1 * ref
        out.append(float(np.argmax(ok) / FS * 1000) if ok.any() and ref > 1e-9 else np.inf)
    return float(np.median(out))


sg = S.gated_line(25.0); X = S.stereo(sg['noisy'])
t0s = [sg['t0'][i] for i in range(2, 40)]
res = {}
for name in ROWS:
    d, algo, par = AR.ROWS[name]
    ctx = M.Ctx(str(M.REF_LIB), 6, None) if algo == 6 else M.Ctx(str(VC.LIB16C), 15, par)
    r0 = ctx.render('g25', X, 0.0); rd = ctx.render('g25', X, -120.0)
    lay = M.layer_of(r0, rd)
    env = M.amp_env(M.bandpass(lay, 150, 600), 5.0)
    rr = rerise(env, t0s)
    res[name] = dict(rerise_median=rr['median'], rerise_n_above6=rr['n_above6'], rerise_p90=rr['p90'], n=rr['n'], n_fell=rr['n_fell'],
                     tail_bp_ms=tail(env, t0s), tail_raw_ms=tail(M.amp_env(lay, 5.0), t0s))
    print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[name].items()}, flush=True)
json.dump(res, open(VC.A5_DIR / 'rerise_a5.json', 'w'), indent=1)

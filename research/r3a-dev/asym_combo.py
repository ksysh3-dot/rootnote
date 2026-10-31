"""R3-b step 1b: in-sample UPPER BOUND for a small combined gate. Logistic regression (good vs bad halvings) on
BabySlakh with the non-oracle cues (stem_half / mix_minus_stem_half use the isolated stem and are excluded), NaN ->
column median. Threshold set so MUSDB loses q of its correct halvings; report BabySlakh bad removed / good lost and
both balances, plus the tracking change that balance implies on BabySlakh (frames / voiced frames).
Usage: asym_combo.py musdb.json slakh.json"""
import json, sys, itertools
import numpy as np
class LogisticRegression:
    """class-balanced logistic regression by Newton steps (numpy only)"""
    def __init__(self, **kw): pass
    def fit(self, Xz, y):
        A = np.c_[np.ones(len(Xz)), Xz]; w = np.zeros(A.shape[1])
        sw = np.where(y == 1, .5 / y.mean(), .5 / (1 - y.mean()))
        for _ in range(30):
            pr = 1 / (1 + np.exp(-A @ w)); g = A.T @ (sw * (pr - y)) + 1e-3 * w
            H = (A * (sw * pr * (1 - pr))[:, None]).T @ A + 1e-3 * np.eye(len(w)); w -= np.linalg.solve(H, g)
        self.w = w; return self
    def predict_proba(self, Xz):
        p = 1 / (1 + np.exp(-np.c_[np.ones(len(Xz)), Xz] @ self.w)); return np.c_[1 - p, p]
M, S = (json.load(open(p)) for p in sys.argv[1:3])
ALL = ['half', 'x15', 'x25', 'half_spread', 'half_peak', 'T', 'ladder', 'half_avg', 'half_pre', 'reg', 'tim', 'tim_all']
def X(d, kind, cols): return np.array([[x.get(c, np.nan) if x.get(c) is not None else np.nan for c in cols] for x in d['frames'][kind]], float)
def run(cols):
    sg, sb, mg, mb = X(S, 'good', cols), X(S, 'bad', cols), X(M, 'good', cols), X(M, 'bad', cols)
    med = np.nanmedian(np.r_[sg, sb], axis=0)
    fill = lambda a: np.where(np.isfinite(a), a, med)
    sg, sb, mg, mb = map(fill, (sg, sb, mg, mb))
    mu, sd = np.r_[sg, sb].mean(0), np.r_[sg, sb].std(0) + 1e-9
    z = lambda a: (a - mu) / sd
    clf = LogisticRegression(class_weight='balanced', max_iter=2000).fit(z(np.r_[sg, sb]), np.r_[np.ones(len(sg)), np.zeros(len(sb))])
    p = lambda a: clf.predict_proba(z(a))[:, 1]          # P(good)
    out = []
    for q in (.005, .01, .02):
        th = np.quantile(p(mg), q)
        f = lambda a: float(np.mean(p(a) <= th))
        balS = f(sb) * S['totals']['bad'] - f(sg) * S['totals']['good']; balM = f(mb) * M['totals']['bad'] - f(mg) * M['totals']['good']
        out.append(f"q{q*100:.1f}%: slakh bad -{100*f(sb):4.1f}% good -{100*f(sg):4.1f}% bal {balS:+6.0f} ({100*balS/S['totals']['hi_voiced']:+.2f}%p of hi-voiced) | musdb bal {balM:+5.0f}")
    return out
print('all non-oracle:'); [print('  ', o) for o in run(ALL)]
best = []
for k in (2, 3):
    for cols in itertools.combinations(['half', 'half_spread', 'half_peak', 'half_avg', 'half_pre', 'tim_all', 'reg', 'x25'], k):
        o = run(list(cols)); best.append((o[1], cols))
best.sort(key=lambda t: -float(t[0].split('bal')[1].split()[0]))
for o, c in best[:5]: print(c, o)

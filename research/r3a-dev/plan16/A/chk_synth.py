"""Task 1 check: Python engine_gains vs the ENGINE.
 (A) through the lib: steady tones at 35/45/60/100/150 Hz rendered by algo 15 (config A) with the voice trace; trace fields a2/a3 (= u.a[0], u.a[1]) divided by A c sigma
     must equal engine_gains k = 2, 3 at the voice's own fOsc (k >= 4 has no trace field).
 (B) the engine's own lookup() source text (pvb_vb.cpp:390-424, extracted by sed) + amplitudes() rolloff compiled with g++ against the real pvb_vb_tables.h:
     all k = 2..8 at the same frequencies.
Run from the pvb-harness environment:  ~/r3a-dev/diag16/run.sh ../plan16/A/chk_synth.py   (run.sh cds to harness and adds PYTHONPATH; script path is under diag16)"""
import sys, subprocess, json, os
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A')
import numpy as np
import research_core_xcheck as X
import synth16 as S

FREQS = [35.0, 45.0, 60.0, 100.0, 150.0]
FS = 48000
out = {}

# ---------------------------------------------------------------- (A) engine trace
lib = X.open_lib(X.CAND)
rowsA = []
for f0 in FREQS:
    t = np.arange(int(5.0 * FS)) / FS
    x = sum(0.08 / k * np.sin(2 * np.pi * k * f0 * t) for k in (1, 2, 3)).astype(np.float32)
    r = X.render(lib, x, 15, cfg=X.CFG['A'], trace=True)
    d, hop, tc = X.hops_of(r['trace'])
    m = (tc > 3.0) & (tc < 4.5)
    st = d['state'][m]; fo = d['fosc'][m]; base = (d['A'] * d['c'] * d['sig'])[m]; a2 = d['a2'][m]; a3 = d['a3'][m]
    sel = (st == 2) & (np.abs(fo - f0) < 0.03 * f0) & (base > 0)
    if sel.sum() == 0:
        rowsA.append(dict(f=f0, n=0)); continue
    G = S.engine_gains(fo[sel])
    e2 = a2[sel] / (base[sel] * G[0]); e3 = a3[sel] / (base[sel] * G[1]) if True else None
    # a3 may legitimately be zero when 3 f > 700 (not the case here); guard
    ok3 = G[1] > 0
    rowsA.append(dict(f=f0, n=int(sel.sum()), fosc_med=float(np.median(fo[sel])), ratio_k2_med=float(np.median(e2)), ratio_k2_maxdev=float(np.max(np.abs(e2 - 1))),
                      ratio_k3_med=float(np.median(e3[ok3])) if ok3.any() else None, ratio_k3_maxdev=float(np.max(np.abs(e3[ok3] - 1))) if ok3.any() else None,
                      g_k2=float(np.median(G[0])), g_k3=float(np.median(G[1]))))
out['trace_check'] = rowsA

# also: every cached coreA trace of the 10 songs (all voice-hops with state > 0)
import glob
worst2 = worst3 = 0.0; nh = 0
for p in sorted(glob.glob('/home/ksysh/r3a-dev/diag16/cache/Track*_coreA.npz')):
    d, hop, tc = X.hops_of(np.load(p)['trace'])
    st = d['state']; fo = d['fosc']; base = d['A'] * d['c'] * d['sig']
    sel = (st > 0) & (base > 1e-9) & (fo > 20) & (fo < 350)
    G = S.engine_gains(fo[sel])
    e2 = d['a2'][sel] / (base[sel] * G[0]); worst2 = max(worst2, float(np.max(np.abs(e2 - 1))))
    s3 = G[1] > 0
    e3 = d['a3'][sel][s3] / (base[sel][s3] * G[1][s3]); worst3 = max(worst3, float(np.max(np.abs(e3 - 1)))); nh += int(sel.sum())
    z3 = ~s3
    if z3.any():
        assert np.all(d['a3'][sel][z3] == 0), 'a3 nonzero where 3f > 700'
out['songs_trace_check'] = dict(n_voice_hops=nh, worst_rel_dev_k2=worst2, worst_rel_dev_k3=worst3)

# ---------------------------------------------------------------- (B) compile the engine's lookup() text
src = open('/home/ksysh/r3-work/app/src/main/cpp/libpvb/pvb_vb.cpp').read().split('\n')
i0 = next(i for i, l in enumerate(src) if l.startswith('void VbHpv::lookup('))
i1 = next(i for i in range(i0, len(src)) if src[i] == '}')
body = '\n'.join(src[i0:i1 + 1]).replace('void VbHpv::lookup(', 'void Lk::lookup(')
cpp = r'''
#include <cmath>
#include <cstdio>
#include <algorithm>
#include "pvb_vb_tables.h"
namespace pvb {
template <class T> inline T clampv(T v, T lo, T hi) { return v < lo ? lo : (v > hi ? hi : v); }
struct Lk { static constexpr int kKMax = 8; struct { double tableScale = 1.0; } dev_; void lookup(double f, double* wk, double& gk) const; };
''' + body + r'''
}
int main() {
    pvb::Lk lk; const double fs[5] = {35., 45., 60., 100., 150.};
    for (double f : fs) {
        double w[7], g; lk.lookup(f, w, g);
        std::printf("%.1f", f);
        for (int kk = 2; kk <= 8; ++kk) {
            const double fk = kk * f; double a = 0;
            if (fk <= 700.0) {
                double r = 1.0;
                if (fk > 220) { const double g12 = std::pow(10., -12 * std::log2(fk / 220.) / 20); r = g12 + 1.0 * (g12 * g12 - g12); }
                a = g * w[kk - 2] * r;
            }
            std::printf(" %.17g", a);
        }
        std::printf("\n");
    }
}
'''
os.makedirs('/home/ksysh/r3a-dev/plan16/A/cpp', exist_ok=True)
open('/home/ksysh/r3a-dev/plan16/A/cpp/lk.cpp', 'w').write(cpp)
subprocess.check_call(['g++', '-O1', '-std=c++17', '-I/home/ksysh/r3-work/app/src/main/cpp/libpvb', '-o', '/home/ksysh/r3a-dev/plan16/A/cpp/lk',
                       '/home/ksysh/r3a-dev/plan16/A/cpp/lk.cpp'])
txt = subprocess.check_output(['/home/ksysh/r3a-dev/plan16/A/cpp/lk']).decode().strip().split('\n')
cmp = []
for line in txt:
    v = line.split(); f = float(v[0]); eng = np.array([float(a) for a in v[1:]])
    py = S.engine_gains(f)[:, 0]
    cmp.append(dict(f=f, engine=[float(x) for x in eng], python=[float(x) for x in py], max_abs_diff=float(np.max(np.abs(eng - py))),
                    k_present=[k for k in range(2, 9) if k * f <= 700]))
out['cpp_check'] = cmp
json.dump(out, open('/home/ksysh/r3a-dev/plan16/A/chk_synth.json', 'w'), indent=1)
print(json.dumps(out['trace_check'], indent=1))
print(json.dumps(out['songs_trace_check']))
for c in cmp:
    print(f"f={c['f']:6.1f}  k present {c['k_present']}  max|engine-python| = {c['max_abs_diff']:.2e}")
    print('   engine a_k/(A c sigma):', ' '.join(f'{x:.5f}' for x in c['engine']))

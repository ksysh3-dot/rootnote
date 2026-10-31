import re, sys
base = '/home/ksysh/r3-work/app/src/main/cpp/libpvb/'
def sub(path, old, new, count=1):
    s = open(base + path, newline='').read()
    assert s.count(old) == count, (path, old, s.count(old))
    open(base + path, 'w', newline='').write(s.replace(old, new))

sub('pvb_resultant.h', "    double maxDfdtBirth = 200;\n};",
    "    double maxDfdtBirth = 200;\n"
    "    double capRho = 0;          // v1.5.1 (16.17; 13.2 D2 as revised by 13.5 F4): stage 1 coefficient cap rho, 0 = off (v1.5)\n};")
sub('pvb_resultant.h', "kParams = 16;", "kParams = 17;")
sub('pvb_resultant.inc', "static_cast<double>(d.crest), d.maxDfdtBirth};", "static_cast<double>(d.crest), d.maxDfdtBirth, d.capRho};")
sub('pvb_resultant.inc', "!flag(14) || !in(15, 20, 2000)) return false;",
    "!flag(14) || !in(15, 20, 2000) ||\n        !(q[16] == 0.0 || in(16, 1, 10))) return false;")
sub('pvb_resultant.inc', "p_.maxDfdtBirth = q[15];\n    return true;", "p_.maxDfdtBirth = q[15];\n    p_.capRho = q[16];\n    return true;")

# the cap itself: after the stage 1 solve, before the residual (ytot) is built
old = """    double al[kVoices], be[kVoices];
    for (int j = 0; j < nv; ++j) {
        Voice& u = vo_[cx.ls[j]];
        al[j] = sol[2 * j]; be[j] = sol[2 * j + 1];
        u.A = u.A1 = std::hypot(al[j], be[j]);
"""
new = """    double al[kVoices], be[kVoices];
    for (int j = 0; j < nv; ++j) {
        Voice& u = vo_[cx.ls[j]];
        al[j] = sol[2 * j]; be[j] = sol[2 * j + 1];
        // v1.5.1 stage 1 coefficient cap (13.2 D2 as revised by 13.5 F4): A <- min(A, rho A_single) with A_single the amplitude of
        // this voice alone from the diagonal 2x2 block of G (same weights, same ridge as rSolve, no extra pass). It acts before
        // the residual below is built, so stage 2 and the other voices see the capped coefficients; A1 is capped with it.
        // Only pairs matter (a single voice is its own block); the phase of the coefficient is kept.
        if (p_.capRho > 0 && nv >= 2) {
            const double g00 = G[2 * j][2 * j], g01 = G[2 * j][2 * j + 1], g11 = G[2 * j + 1][2 * j + 1];
            const double lam = 1e-4 * .5 * (g00 + g11);
            const double d00 = g00 + lam, d11 = g11 + lam, det = d00 * d11 - g01 * g01;
            double aSingle = 0;
            if (det > 1e-300) {
                const double sa = (d11 * rhs[2 * j] - g01 * rhs[2 * j + 1]) / det;
                const double sb = (d00 * rhs[2 * j + 1] - g01 * rhs[2 * j]) / det;
                aSingle = std::hypot(sa, sb);
            }
            const double a1 = std::hypot(al[j], be[j]), lim = p_.capRho * aSingle;
#ifdef PVB_RESEARCH_CAPSTATS
            ++gCapStats[0];
#endif
            if (det > 1e-300 && a1 > lim) {
                const double k = lim / a1;
                al[j] *= k; be[j] *= k;
#ifdef PVB_RESEARCH_CAPSTATS
                ++gCapStats[1];
#endif
            }
        }
        u.A = u.A1 = std::hypot(al[j], be[j]);
"""
sub('pvb_resultant.inc', old, new)

# optional research counters (only with -DPVB_RESEARCH_CAPSTATS, absent from app builds)
old = "bool ResultantCore::setParams("
new = """#ifdef PVB_RESEARCH_CAPSTATS
// host research only: [0] voice-hops of LS sets with >= 2 voices (cap evaluated), [1] voice-hops where the cap acted; read and zeroed
static unsigned long long gCapStats[2] = {0, 0};
extern "C" __attribute__((visibility("default"))) void pvb_resultant_cap_stats(double* out) {
    out[0] = static_cast<double>(gCapStats[0]); out[1] = static_cast<double>(gCapStats[1]);
    gCapStats[0] = gCapStats[1] = 0;
}
#endif

bool ResultantCore::setParams("""
sub('pvb_resultant.inc', old, new)
print('ok')

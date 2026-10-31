import re
from pathlib import Path
d = Path.home() / 'r3-work/app/src/main/cpp/libpvb'
h = (d / 'pvb_resultant.h').read_text()
i = (d / 'pvb_resultant.inc').read_text()
def rep(t, a, b, cnt=1):
    assert t.count(a) == cnt, (a, t.count(a))
    return t.replace(a, b)
h = rep(h, "                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0\n};",
"                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0\n"
"    double betaSusMin = 0, betaSusMax = 0;   // A5'' (18.15): beta range of the sustain, used instead of betaMin / betaMax (theta pull and f_off gain) outside the\n"
"                                // onset period; 0 / 0 = off (betaMin / betaMax always, as 5c1c62c)\n"
"    double betaOnsetMs = 0;     // A5'': length of the onset period after a voice birth, a REL -> ON or a pitch move of > 50 cent in 2 hops; > 0 when the sustain pair is on\n};")
h = rep(h, "kParams = 19;", "kParams = 22;")
h = rep(h, "        int64_t onHop = -1;        // hop at which the voice was born ON (same-hop births are subordinate by ratio alone)\n",
"        int64_t onHop = -1;        // hop at which the voice was born ON (same-hop births are subordinate by ratio alone)\n"
"        int64_t onsetAt = -1;      // A5'': hop of the last onset (birth, REL -> ON, pitch move); beta is the onset pair for betaOnsetMs from it\n")
h = rep(h, "        double f = 0, fPrev = 0, fdot = 0;", "        double f = 0, fPrev = 0, fPrev2 = 0, fdot = 0;")
(d / 'pvb_resultant.h').write_text(h)

i = rep(i, "static_cast<double>(d.windowCreep), static_cast<double>(d.creepMode)};",
        "static_cast<double>(d.windowCreep), static_cast<double>(d.creepMode),\n        d.betaSusMin, d.betaSusMax, d.betaOnsetMs};")
i = rep(i, "!(q[17] == 0.0 || in(17, 1, 320)) || !(q[18] == 0.0 || q[18] == 1.0 || q[18] == 2.0)) return false;",
        "!(q[17] == 0.0 || in(17, 1, 320)) || !(q[18] == 0.0 || q[18] == 1.0 || q[18] == 2.0) ||\n"
        "        !in(19, 0, 1) || !in(20, 0, 1) || !in(21, 0, 1000) || ((q[19] > 0 || q[20] > 0) && !(q[21] > 0))) return false;")
i = rep(i, "p_.creepMode = static_cast<int>(q[18]);\n    return true;",
        "p_.creepMode = static_cast<int>(q[18]);\n    p_.betaSusMin = q[19]; p_.betaSusMax = q[20]; p_.betaOnsetMs = q[21];\n    return true;")
# spawn
i = rep(i, "        u.f = u.fPrev = tk.f;", "        u.f = u.fPrev = u.fPrev2 = tk.f;")
# births
i = rep(i, "        u.onHop = hopCount_; u.onMeas = 0;", "        u.onHop = u.onsetAt = hopCount_; u.onMeas = 0;")
# REL->ON
i = rep(i, "                if (u.revCnt >= 3) { u.state = On; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0; }",
           "                if (u.revCnt >= 3) { u.state = On; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0; u.onsetAt = hopCount_; }")
# phase
i = rep(i, "        if (cx.lsOk && u.inLs) {\n            const double e = std::remainder(u.thetaMeas - pred, kRTwoPi), ae = std::fabs(e);\n            const double lo = std::min(p_.betaMin, p_.betaMax), hi = std::max(p_.betaMin, p_.betaMax);\n",
"""        // A5'': after an onset (birth, REL -> ON, or f_track more than 50 cent from where it was 1 or 2 hops ago) the voice pulls with betaMin / betaMax
        // for betaOnsetMs, afterwards with the sustain pair; both the theta pull and the f_off gain use the beta chosen here
        const bool sus = p_.betaSusMin > 0 || p_.betaSusMax > 0;
        bool sustain = false;
        if (sus) {
            auto moved = [&](double f0) { return f0 > 0 && std::fabs(1200.0 * std::log2(u.f / f0)) > 50.0; };
            if (moved(u.fPrev) || moved(u.fPrev2)) u.onsetAt = hopCount_;
            sustain = static_cast<double>(hopCount_ - u.onsetAt) * kRHopS * 1000.0 >= p_.betaOnsetMs;
        }
        if (cx.lsOk && u.inLs) {
            const double e = std::remainder(u.thetaMeas - pred, kRTwoPi), ae = std::fabs(e);
            const double b0 = sustain ? p_.betaSusMin : p_.betaMin, b1 = sustain ? p_.betaSusMax : p_.betaMax;
            const double lo = std::min(b0, b1), hi = std::max(b0, b1);
""")
i = rep(i, "        u.fPrev = u.f;\n        if (u.dead) u = Voice{};", "        u.fPrev2 = u.fPrev; u.fPrev = u.f;\n        if (u.dead) u = Voice{};")
(d / 'pvb_resultant.inc').write_text(i)
a = Path.home() / 'r3-work/tools/pvb-harness/research_core_api.py'
t = a.read_text()
t = rep(t, "the 19 parameters, the voice", "the 22 parameters, the voice")
t = rep(t, "# the 19 parameters of pvb_set_resultant, in the order of spec 5.8 (capRho, windowCreep: v1.6-a; creepMode: A1', 0 = off = v1.5), with their defaults",
 "# the 22 parameters of pvb_set_resultant, in the order of spec 5.8 (capRho, windowCreep: v1.6-a; creepMode: A1', 0 = off = v1.5;\n# betaSusMin, betaSusMax, betaOnsetMs: A5'', 0 = off), with their defaults")
t = rep(t, "'windowCreep', 'creepMode')\nDEFAULTS", "'windowCreep', 'creepMode',\n          'betaSusMin', 'betaSusMax', 'betaOnsetMs')\nDEFAULTS")
t = rep(t, "windowCreep=0, creepMode=0)", "windowCreep=0, creepMode=0,\n                betaSusMin=0, betaSusMax=0, betaOnsetMs=0)")
a.write_text(t)

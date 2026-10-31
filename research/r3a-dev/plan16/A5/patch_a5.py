from pathlib import Path
d = Path.home() / 'r3-work/app/src/main/cpp/libpvb'
h = (d/'pvb_resultant.h').read_text()
i = (d/'pvb_resultant.inc').read_text()
def rep(t, old, new):
    assert t.count(old) == 1, old
    return t.replace(old, new)

# header: params
h = rep(h, "                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0\n",
"                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0\n"
"    double ampSlewDb = 0;       // A5 (18.9): largest change of a voice's rendered amplitude A c sigma per hop, dB, up and down; 0 = off (v1.6-a)\n"
"    int slewOnsetMode = 0;      // A5: rise-limit exemption for 3 hops. 0 none, 1 strong births (SNR >= snrFastDb), 2 = 1 and REL -> ON after more than 50 ms in REL; no effect when ampSlewDb = 0\n")
h = rep(h, "kParams = 19;", "kParams = 21;")
h = rep(h, "        int npUsed = 0;            // past window actually used for this voice in this hop (trace)\n",
"        int npUsed = 0;            // past window actually used for this voice in this hop (trace)\n"
"        double ampR = 0;           // A5: the amplitude A c sigma rendered at the end of the last hop (after the slew limit)\n"
"        int slewFree = 0;          // A5: hops left in which the rise limit is waived (slewOnsetMode)\n"
"        int relHops = 0;           // A5 (mode 2): hops spent in REL since the last transition to REL\n")
h = rep(h, "    void amplitudes(const VbHpv& v, Voice& u) const;\n",
"    void amplitudes(const VbHpv& v, Voice& u) const;\n    double slewLimit(Voice& u, double target) const;\n")
(d/'pvb_resultant.h').write_text(h)

# inc
i = rep(i, "constexpr double kRFallDb = 3.0;\n",
"constexpr double kRFallDb = 3.0;\n// A5 (18.9): amplitudes under this (-100 dBFS) count as this much when the previous amplitude is the base of the dB limit, so that a voice rises from silence at the slew rate, not never\n"
"constexpr double kRSlewFloor = 1e-5;\nconstexpr int kRSlewFreeHops = 3;\n")
i = rep(i, "static_cast<double>(d.windowCreep), static_cast<double>(d.creepMode)};",
"static_cast<double>(d.windowCreep), static_cast<double>(d.creepMode), d.ampSlewDb, static_cast<double>(d.slewOnsetMode)};")
i = rep(i, "|| !(q[18] == 0.0 || q[18] == 1.0 || q[18] == 2.0)) return false;",
"|| !(q[18] == 0.0 || q[18] == 1.0 || q[18] == 2.0) ||\n        !(q[19] == 0.0 || in(19, .1, 40)) || !(q[20] == 0.0 || q[20] == 1.0 || q[20] == 2.0)) return false;")
i = rep(i, "p_.creepMode = static_cast<int>(q[18]);", "p_.creepMode = static_cast<int>(q[18]);\n    p_.ampSlewDb = q[19]; p_.slewOnsetMode = static_cast<int>(q[20]);")
# REL entry / exit
i = rep(i, "if (toRel) { u.state = Rel; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0; }",
"if (toRel) { u.state = Rel; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0; u.relHops = 0; }")
i = rep(i, "        } else if (u.state == Rel) {\n            if (cx.measured) {\n",
"        } else if (u.state == Rel) {\n            ++u.relHops;\n            if (cx.measured) {\n")
i = rep(i, "if (u.revCnt >= 3) { u.state = On; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0; }",
"if (u.revCnt >= 3) {\n                    u.state = On; u.lowSnrM = u.domCnt = u.revCnt = u.onMeas = 0;\n"
"                    // A5 mode 2: a return from more than 50 ms in REL is a real re-attack, not a flicker\n"
"                    if (p_.ampSlewDb > 0 && p_.slewOnsetMode >= 2 && u.relHops * kRHopS > .050) u.slewFree = kRSlewFreeHops;\n"
"                }")
i = rep(i, "        u.onHop = hopCount_; u.onMeas = 0;\n",
"        u.onHop = hopCount_; u.onMeas = 0;\n        u.ampR = 0; u.relHops = 0;\n"
"        u.slewFree = p_.ampSlewDb > 0 && p_.slewOnsetMode >= 1 && u.snr >= p_.snrFastDb ? kRSlewFreeHops : 0;   // A5: a strong birth is not slowed\n")
# amplitudes
i = rep(i, "// Harmonic amplitudes at the end of the hop: a_vk = G_L g w_k R_k A c sigma (spec 5.6)\n",
"""// A5 (18.9): the amplitude A c sigma that the synthesis interpolates to (per hop) moves at most ampSlewDb from the one rendered at the end of
// the previous hop, up and down. A previous amplitude under kRSlewFloor counts as kRSlewFloor (a voice rises from silence at the slew rate; a
// target under the floor is taken as it is once the limit reaches it). A rise is waived while slewFree > 0 (slewOnsetMode). The hop in which a
// REL voice is freed (c = 0) is not limited: it ends at zero as it did without the limit.
double ResultantCore::slewLimit(Voice& u, double target) const {
    if (!(p_.ampSlewDb > 0) || u.dead) { u.ampR = target > 0 ? target : 0; return u.ampR; }
    const double g = std::pow(10.0, p_.ampSlewDb / 20);
    const double prev = std::max(u.ampR, kRSlewFloor);
    double r = target > 0 ? target : 0;
    if (r > prev * g) { if (u.slewFree <= 0) r = prev * g; }
    else if (r < prev / g) { r = prev / g; if (r < kRSlewFloor) r = target > 0 ? target : 0; }
    if (u.slewFree > 0) --u.slewFree;
    u.ampR = r;
    return r;
}

// Harmonic amplitudes at the end of the hop: a_vk = G_L g w_k R_k A c sigma (spec 5.6)
""")
i = rep(i, "    const double base = u.A * u.c * u.sigma, f = u.fOsc;\n    if (!(base > 0) || !(f > 0)) return;\n",
"    const double f = u.fOsc;\n    const double base = slewLimit(u, u.A * u.c * u.sigma);\n    if (!(base > 0) || !(f > 0)) return;\n")
(d/'pvb_resultant.inc').write_text(i)

a = Path.home()/'r3-work/tools/pvb-harness/research_core_api.py'
t = a.read_text()
t = rep(t, "the 19 parameters of pvb_set_resultant, in the order of spec 5.8 (capRho, windowCreep: v1.6-a; creepMode: A1', 0 = off = v1.5)",
 "the 21 parameters of pvb_set_resultant, in the order of spec 5.8 (capRho, windowCreep: v1.6-a; creepMode: A1'; ampSlewDb, slewOnsetMode: A5; 0 = off = v1.5)")
t = rep(t, "'capRho', 'windowCreep', 'creepMode')", "'capRho', 'windowCreep', 'creepMode', 'ampSlewDb', 'slewOnsetMode')")
t = rep(t, "windowCreep=0, creepMode=0)", "windowCreep=0, creepMode=0, ampSlewDb=0, slewOnsetMode=0)")
t = rep(t, "library loading, the 19 parameters", "library loading, the 21 parameters")
a.write_text(t)

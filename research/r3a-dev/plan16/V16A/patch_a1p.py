"""Applies the A1' (creepMode) edit to ~/r3-work core sources on top of 084ea45 / 232e46a."""
from pathlib import Path
S = Path.home() / 'r3-work/app/src/main/cpp/libpvb'


def sub(path, old, new, count=1):
    t = path.read_text()
    assert t.count(old) == count, (path.name, old[:60], t.count(old))
    path.write_text(t.replace(old, new))


h = S / 'pvb_resultant.h'
inc = S / 'pvb_resultant.inc'
sub(h, "    int windowCreep = 0;        // v1.6-a A1 (18.3; 13.2 D4 narrowed by 13.5 F5): window growth limit, samples per hop (1..320), 0 = off (v1.5)\n",
    "    int windowCreep = 0;        // v1.6-a A1 (18.3; 13.2 D4 narrowed by 13.5 F5): window growth limit, samples per hop (1..320), 0 = off (v1.5)\n"
    "    int creepMode = 0;          // A1' (18.5): which windows the growth limit acts on and when. 0 = N_J and N_v always (18.3 A1), 1 = N_v only while its voice's SNR\n"
    "                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0\n")
sub(h, "kParams = 18;", "kParams = 19;")
sub(h, "    static constexpr int kTracks = 12;       // VbHpv::tr52_ capacity\n",
    "    static constexpr int kTracks = 12;       // VbHpv::tr52_ capacity\n"
    "    static constexpr int kFallHops = 6;      // A1': SNR history length, 6 hops = 32 ms (the 30 ms of 18.5)\n")
sub(h, "        int npvA = 0;              // window creep: the stage 2 window actually applied (follows npv up by at most windowCreep per hop)\n",
    "        int npvA = 0;              // window creep: the stage 2 window actually applied (follows npv up by at most windowCreep per hop)\n"
    "        double snrH[kFallHops] = {};   // A1': SNR of the last hops (ring), snrHp = next slot, snrHn = valid entries\n"
    "        int snrHp = 0, snrHn = 0;\n")
sub(h, "    int npJA_ = 0;             // window creep: N_J actually applied (npJ_ stays the hysteresis-held value); 0 = start at N_lo\n",
    "    int npJA_ = 0;             // window creep: N_J actually applied (npJ_ stays the hysteresis-held value); 0 = start at N_lo\n"
    "    double sMaxH_[kFallHops] = {};   // A1' (creepMode 2): maximum SNR over the LS set at the last hops (ring); emptied when the set is empty\n"
    "    int sMaxHp_ = 0, sMaxHn_ = 0;\n")

# helpers
sub(inc, "// N_snr(s) of spec 5.3:",
    "// A1' (18.5): the SNR is falling when it is more than 3 dB under its maximum over the last ResultantCore::kFallHops hops, the current one included\n"
    "constexpr double kRFallDb = 3.0;\n"
    "inline void rPushSnr(double* h, int& pos, int& n, double s) {\n"
    "    h[pos] = s;\n"
    "    pos = (pos + 1) % ResultantCore::kFallHops;\n"
    "    n = std::min(n + 1, ResultantCore::kFallHops);\n"
    "}\n"
    "inline bool rSnrFalling(const double* h, int n, double s) {\n"
    "    double mx = s;\n"
    "    for (int i = 0; i < n; ++i) mx = std::max(mx, h[i]);   // unused slots are never read (n counts the valid ones, they fill from slot 0)\n"
    "    return s < mx - kRFallDb;\n"
    "}\n\n"
    "// N_snr(s) of spec 5.3:")
sub(inc, "    npJ_ = npJPend_ = npJA_ = 0;\n", "    npJ_ = npJPend_ = npJA_ = 0;\n    sMaxHp_ = sMaxHn_ = 0;\n")
# params
sub(inc, "d.capRho, static_cast<double>(d.windowCreep)};", "d.capRho, static_cast<double>(d.windowCreep), static_cast<double>(d.creepMode)};")
sub(inc, "!(q[16] == 0.0 || in(16, 1, 10)) || !(q[17] == 0.0 || in(17, 1, 320))) return false;",
    "!(q[16] == 0.0 || in(16, 1, 10)) || !(q[17] == 0.0 || in(17, 1, 320)) || !(q[18] == 0.0 || q[18] == 1.0 || q[18] == 2.0)) return false;")
sub(inc, "p_.windowCreep = static_cast<int>(std::lround(q[17]));", "p_.windowCreep = static_cast<int>(std::lround(q[17])); p_.creepMode = static_cast<int>(q[18]);")
# per-voice history
sub(inc, "        u.snr = snrOf(cx, u);\n", "        u.snr = snrOf(cx, u);\n        rPushSnr(u.snrH, u.snrHp, u.snrHn, u.snr);\n")
# solveLs: set max and N_J
sub(inc, "    if (nv == 0) { npJA_ = 0; return; }\n", "    if (nv == 0) { npJA_ = 0; sMaxHp_ = sMaxHn_ = 0; return; }\n")
sub(inc, "    double fLow = 1e9, dfMin = 1e9, sOn = 1e9, sAll = 1e9;\n", "    double fLow = 1e9, dfMin = 1e9, sOn = 1e9, sAll = 1e9, sMax = -1e9;\n")
sub(inc, "        sAll = std::min(sAll, u.snr);\n", "        sAll = std::min(sAll, u.snr);\n        sMax = std::max(sMax, u.snr);\n")
sub(inc, """    if (p_.windowCreep > 0) {   // v1.6-a A1 (13.5 F5): N_J grows by at most windowCreep per hop whatever raised it (SNR, separation, N_lo, birth, set change); shrinking is immediate
        if (npJA_ <= 0) npJA_ = nLo;
        else if (npJh > npJA_) npJA_ = std::min(npJh, npJA_ + p_.windowCreep);
        else npJA_ = npJh;
        npJ = npJA_;
    }
""", """    rPushSnr(sMaxH_, sMaxHp_, sMaxHn_, sMax);
    if (p_.windowCreep > 0 && p_.creepMode != 1) {   // v1.6-a A1 (13.5 F5): N_J grows by at most windowCreep per hop whatever raised it (SNR, separation, N_lo, birth, set change); shrinking is immediate
        // A1' (18.5) creepMode 2: only while the maximum SNR of the LS set is falling, otherwise N_J follows the hysteresis-held window at once as in v1.5
        if (p_.creepMode == 2 && !rSnrFalling(sMaxH_, sMaxHn_, sMax)) npJA_ = npJh;
        else if (npJA_ <= 0) npJA_ = nLo;
        else if (npJh > npJA_) npJA_ = std::min(npJh, npJA_ + p_.windowCreep);
        else npJA_ = npJh;
        npJ = npJA_;
    }
""")
sub(inc, """            if (p_.windowCreep > 0) {   // v1.6-a A1: the same growth limit on the stage 2 window
                if (u.npvA <= 0) u.npvA = std::min(nvv, nLov);
""", """            if (p_.windowCreep > 0) {   // v1.6-a A1: the same growth limit on the stage 2 window; A1' (creepMode >= 1): only while this voice's SNR is falling
                if (p_.creepMode >= 1 && !rSnrFalling(u.snrH, u.snrHn, u.snr)) u.npvA = nvv;
                else if (u.npvA <= 0) u.npvA = std::min(nvv, nLov);
""")

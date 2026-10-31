"""Applies the A1 (windowCreep) edit to ~/r3-work core sources, after d2.diff (capRho) has been applied."""
from pathlib import Path
S = Path.home() / 'r3-work/app/src/main/cpp/libpvb'


def sub(path, old, new, count=1):
    t = path.read_text()
    assert t.count(old) == count, (path.name, old[:60], t.count(old))
    path.write_text(t.replace(old, new))


h = S / 'pvb_resultant.h'
inc = S / 'pvb_resultant.inc'
sub(h, "    double capRho = 0;          // v1.5.1 (16.17; 13.2 D2 as revised by 13.5 F4): stage 1 coefficient cap rho, 0 = off (v1.5)\n",
    "    double capRho = 0;          // v1.5.1 (16.17; 13.2 D2 as revised by 13.5 F4): stage 1 coefficient cap rho, 0 = off (v1.5)\n"
    "    int windowCreep = 0;        // v1.6-a A1 (18.3; 13.2 D4 narrowed by 13.5 F5): window growth limit, samples per hop (1..320), 0 = off (v1.5)\n")
sub(h, "kParams = 17;", "kParams = 18;")
sub(h, "        int npv = 0, npvPend = 0;  // per-voice past window (stage 2) and its hysteresis counter\n",
    "        int npv = 0, npvPend = 0;  // per-voice past window (stage 2) and its hysteresis counter\n"
    "        int npvA = 0;              // window creep: the stage 2 window actually applied (follows npv up by at most windowCreep per hop)\n")
sub(h, "    int npJ_ = 0, npJPend_ = 0;\n",
    "    int npJ_ = 0, npJPend_ = 0;\n"
    "    int npJA_ = 0;             // window creep: N_J actually applied (npJ_ stays the hysteresis-held value); 0 = start at N_lo\n")

sub(inc, "    npJ_ = npJPend_ = 0;\n    std::fill", "    npJ_ = npJPend_ = npJA_ = 0;\n    std::fill")
# params
sub(inc, "static_cast<double>(d.crest), d.maxDfdtBirth, d.capRho};",
    "static_cast<double>(d.crest), d.maxDfdtBirth, d.capRho, static_cast<double>(d.windowCreep)};")
sub(inc, "        !(q[16] == 0.0 || in(16, 1, 10))) return false;",
    "        !(q[16] == 0.0 || in(16, 1, 10)) || !(q[17] == 0.0 || in(17, 1, 320))) return false;")
sub(inc, "    p_.capRho = q[16];\n", "    p_.capRho = q[16]; p_.windowCreep = static_cast<int>(std::lround(q[17]));\n")
# no LS set: forget the applied window
sub(inc, "    const int nv = cx.nLs;\n    if (nv == 0) return;\n",
    "    const int nv = cx.nLs;\n    if (nv == 0) { npJA_ = 0; return; }\n")
# stage 1
sub(inc, """    npJ_ = std::min(kRMaxPast, std::max(nLo, npJ_));
    const int npJ = npJ_, nf = std::min(npJ, p_.nFuture), len = npJ + nf + 1;
""", """    npJ_ = std::min(kRMaxPast, std::max(nLo, npJ_));
    const int npJh = npJ_;   // the window the hysteresis holds
    int npJ = npJh;
    if (p_.windowCreep > 0) {   // v1.6-a A1 (13.5 F5): N_J grows by at most windowCreep per hop whatever raised it (SNR, separation, N_lo, birth, set change); shrinking is immediate
        if (npJA_ <= 0) npJA_ = nLo;
        else if (npJh > npJA_) npJA_ = std::min(npJh, npJA_ + p_.windowCreep);
        else npJA_ = npJh;
        npJ = npJA_;
    }
    const int nf = std::min(npJ, p_.nFuture), len = npJ + nf + 1;
""")
# birth reset
sub(inc, "        u.npv = u.npvPend = 0; u.psiSet = 0;\n", "        u.npv = u.npvPend = u.npvA = 0; u.psiSet = 0;\n")
# stage 2
sub(inc, """        if (u.trans) {   // the pitch is moving: the shortest window
            nvv = std::min(nLov, npJ);
            u.npv = nvv; u.npvPend = 0;
        } else {
            const int tgt = std::min(npJ, std::max(nLov, rWindowTarget(u.snr, nLov)));""",
    """        if (u.trans) {   // the pitch is moving: the shortest window
            nvv = std::min(nLov, npJ);
            u.npv = nvv; u.npvPend = 0; u.npvA = nvv;
        } else {
            const int tgt = std::min(npJh, std::max(nLov, rWindowTarget(u.snr, nLov)));""")
sub(inc, """            u.npv = std::min(npJ, std::max(nLov, u.npv));
            nvv = u.npv;
""", """            u.npv = std::min(npJh, std::max(nLov, u.npv));
            nvv = u.npv;
            if (p_.windowCreep > 0) {   // v1.6-a A1: the same growth limit on the stage 2 window
                if (u.npvA <= 0) u.npvA = std::min(nvv, nLov);
                else if (nvv > u.npvA) u.npvA = std::min(nvv, u.npvA + p_.windowCreep);
                else u.npvA = nvv;
                nvv = std::min(u.npvA, npJ);
            }
""")
print('patched')

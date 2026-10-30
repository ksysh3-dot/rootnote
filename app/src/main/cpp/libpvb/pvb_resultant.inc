// PVB speaker engine - Resultant core, definitions (docs/RESULTANT_CORE.md v1.3). See pvb_resultant.h.
//
// Included at the end of pvb_vb52.cpp: same translation unit as the anonymous-namespace helpers (psi52, interp52,
// offset52) and, as a friend of VbHpv, with access to the tracker, the rings and the spectra of the module.
//
// Time axes (spec 3): a hop is the call of pvFrame52 at core index i_h = VbHpv::i_. The analysis centre is ring slot
// n_h = i_h - 191 (input time i_h - 382). A hop writes the output samples [i_h, i_h + 16) of the ring that core52 reads.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include "pvb_fastmath.h"

namespace pvb {
namespace {

constexpr double kRTwoPi = 2 * kPi;
constexpr double kRFs = 3000.0;
constexpr double kRHopS = 16.0 / 3000.0;   // one hop in seconds
// phase of the fixed delays between the input and the layer (same expression as renderTrack52)
constexpr double kRTc = 2. * 80 / 48000 + (192. + 15 + 191) / 3000 - 7052. / 48000;
constexpr int kRMaxPast = 320;             // N_p limit (ring of 512, 191 samples of analysis delay)
constexpr int kRMaxLen = kRMaxPast + 96 + 1;
constexpr int kRCoastMax = 48;             // hops a voice may coast (256 ms)
constexpr double kRStage2Snr = 18.0;       // dB: voices at least this clean get a window of their own (stage 2)

// Rotation recursion for cos / sin of the quadratic phase Phi(m) = om m + be m^2 / 2: (c, s) is the basis at m, (dc, ds)
// the per-sample rotation delta(m) = Phi(m + 1) - Phi(m) = om + be (m + 1/2), (rc, rs) the rotation of delta by be.
struct ROsc { double c, s, dc, ds, rc, rs; };
inline void rOscInit(ROsc& o, double om, double be, int m0) {
    const double ph = om * m0 + .5 * be * static_cast<double>(m0) * m0;
    const double dl = om + be * (m0 + .5);
    fastmath::sincos(ph, o.s, o.c);
    fastmath::sincos(dl, o.ds, o.dc);
    fastmath::sincos(be, o.rs, o.rc);
}
inline void rOscStep(ROsc& o) {
    const double c = o.c * o.dc - o.s * o.ds, s = o.s * o.dc + o.c * o.ds;
    o.c = c; o.s = s;
    const double dc = o.dc * o.rc - o.ds * o.rs, ds = o.ds * o.rc + o.dc * o.rs;
    o.dc = dc; o.ds = ds;
}

// c[j] = cos(pi j / (n + 1)), j = 0 .. n, by the Chebyshev recurrence (the window is evaluated without a call per sample)
inline void rCosRamp(double* c, int n) {
    c[0] = 1.0;
    if (n < 1) return;
    const double d = kPi / (n + 1), k2 = 2 * std::cos(d);
    c[1] = std::cos(d);
    for (int j = 2; j <= n; ++j) c[j] = k2 * c[j - 1] - c[j - 2];
}
// Skewed Hann window w[i], m = i - np, i = 0 .. np + nf (spec 5.3). Returns its centroid (weighted mean of m), in samples.
inline double rMakeWindow(double* w, int np, int nf) {
    double c[kRMaxPast + 2];
    rCosRamp(c, np);
    for (int j = 0; j <= np; ++j) w[np - j] = .5 * (1 + c[j]);
    rCosRamp(c, nf);
    for (int j = 1; j <= nf; ++j) w[np + j] = .5 * (1 + c[j]);
    double s = 0, sm = 0;
    for (int i = 0; i <= np + nf; ++i) { s += w[i]; sm += (i - np) * w[i]; }
    return sm / s;
}

// Solves (G + lambda I) x = r, lambda = 1e-4 tr(G) / n, by Cholesky. G is symmetric with its upper triangle filled
// (row stride 16). False when the matrix is not positive definite.
inline bool rSolve(const double (*G)[16], const double* r, int n, double* x) {
    double tr = 0;
    for (int i = 0; i < n; ++i) tr += G[i][i];
    const double lam = 1e-4 * tr / n;
    double L[16][16];
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j <= i; ++j) {
            double sum = G[j][i] + (i == j ? lam : 0.0);
            for (int k = 0; k < j; ++k) sum -= L[i][k] * L[j][k];
            if (i == j) {
                if (!(sum > 1e-300)) return false;
                L[i][i] = std::sqrt(sum);
            } else L[i][j] = sum / L[j][j];
        }
    }
    double y[16];
    for (int i = 0; i < n; ++i) {
        double s = r[i];
        for (int k = 0; k < i; ++k) s -= L[i][k] * y[k];
        y[i] = s / L[i][i];
    }
    for (int i = n - 1; i >= 0; --i) {
        double s = y[i];
        for (int k = i + 1; k < n; ++k) s -= L[k][i] * x[k];
        x[i] = s / L[i][i];
    }
    return true;
}

// N_snr(s) of spec 5.3: nLo from 30 dB up, kRMaxPast from 12 dB down, log-linear between
inline int rWindowTarget(double snrDb, int nLo) {
    if (snrDb >= 30.0) return nLo;
    if (snrDb <= 12.0) return kRMaxPast;
    const double t = (30.0 - snrDb) / 18.0;
    return static_cast<int>(std::lround(std::exp(std::log(static_cast<double>(nLo)) +
        t * (std::log(static_cast<double>(kRMaxPast)) - std::log(static_cast<double>(nLo))))));
}
inline int rPeriodWindow(double f, int nMin) {
    return static_cast<int>(clampv(std::ceil(kRFs / f), static_cast<double>(nMin), static_cast<double>(kRMaxPast)));
}

}  // namespace

// ------------------------------------------------------------------------------------------------ housekeeping
void ResultantCore::reset() {
    for (auto& u : vo_) u = Voice{};
    std::fill(std::begin(out_), std::end(out_), 0.0);
    nextVoiceId_ = 0; hopCount_ = 0;
    npJ_ = npJPend_ = 0;
    std::fill(std::begin(lsSig_), std::end(lsSig_), 0);
    std::fill(std::begin(rejId_), std::end(rejId_), 0u);
    std::fill(std::begin(rejHop_), std::end(rejHop_), static_cast<int64_t>(0));
    rejPos_ = 0;
    traceN_ = 0; traceOver_ = false;
}

bool ResultantCore::setParams(const double* v, int n) {
    if (n < 0 || n > kParams || (n > 0 && !v)) return false;
    const ResultantParams d;
    double q[kParams] = {static_cast<double>(d.voicing), d.levelDb, static_cast<double>(d.ampSource), d.snrOnDb,
        d.snrFastDb, d.snrOffDb, d.tauOnMs, d.tauOffMs, d.betaMin, d.betaMax, d.kappa, static_cast<double>(d.nMin),
        static_cast<double>(d.nFuture), d.psiSlew, static_cast<double>(d.crest), d.maxDfdtBirth};
    for (int i = 0; i < n; ++i) q[i] = v[i];
    auto in = [&](int i, double lo, double hi) { return std::isfinite(q[i]) && q[i] >= lo && q[i] <= hi; };
    auto flag = [&](int i) { return q[i] == 0.0 || q[i] == 1.0; };
    if (!flag(0) || !in(1, 0, 12) || !flag(2) || !in(3, 6, 30) || !in(4, 10, 40) || !in(5, 0, 20) || !in(6, 1, 100) ||
        !in(7, 5, 300) || !in(8, 0, 1) || !in(9, 0, 1) || !in(10, .5, 3) || !in(11, 16, 191) || !in(12, 0, 96) ||
        !in(13, .01, 3.2) || !flag(14) || !in(15, 20, 2000)) return false;
    p_.voicing = static_cast<int>(q[0]); p_.levelDb = q[1]; p_.ampSource = static_cast<int>(q[2]);
    p_.snrOnDb = q[3]; p_.snrFastDb = q[4]; p_.snrOffDb = q[5]; p_.tauOnMs = q[6]; p_.tauOffMs = q[7];
    p_.betaMin = q[8]; p_.betaMax = q[9]; p_.kappa = q[10];
    p_.nMin = static_cast<int>(std::lround(q[11])); p_.nFuture = static_cast<int>(std::lround(q[12]));
    p_.psiSlew = q[13]; p_.crest = static_cast<int>(q[14]); p_.maxDfdtBirth = q[15];
    return true;
}

bool ResultantCore::traceEnable(int hops) {
    if (hops <= 0) {
        std::vector<double>().swap(trace_);
        traceCap_ = traceN_ = 0; traceOver_ = false;
        return true;
    }
    if (hops > 200000) return false;
    trace_.assign(static_cast<size_t>(hops) * kVoices * kTraceFields, 0.0);
    traceCap_ = hops; traceN_ = 0; traceOver_ = false;
    return true;
}

int ResultantCore::traceCopy(double* out, int capacity) const {
    if (traceCap_ <= 0) return -1;
    if (traceOver_) return -3;
    const long long rows = static_cast<long long>(traceN_) * kVoices, need = rows * kTraceFields;
    if (capacity < need || (need > 0 && !out)) return -2;
    std::copy(trace_.begin(), trace_.begin() + static_cast<std::ptrdiff_t>(need), out);
    return static_cast<int>(rows);
}

void ResultantCore::rejectTrack(uint32_t id) {
    if (!id) return;
    rejId_[rejPos_] = id; rejHop_[rejPos_] = hopCount_;
    rejPos_ = (rejPos_ + 1) & 7;
}
bool ResultantCore::rejected(uint32_t id) const {
    for (int i = 0; i < 8; ++i) if (rejId_[i] == id && hopCount_ - rejHop_[i] < 24) return true;
    return false;
}

// A voice v is subordinate when an ON voice u sits at 1/2, 1/3 or 1/4 of its frequency (spec 5.2)
bool ResultantCore::isSubordinate(double f, int self) const {
    for (int q = 0; q < kVoices; ++q) {
        if (q == self) continue;
        const Voice& w = vo_[q];
        if (w.state != On || !(w.f < .9 * f)) continue;
        for (int m = 2; m <= 4; ++m) if (std::fabs(f - m * w.f) <= .015 * f) return true;
    }
    return false;
}

void ResultantCore::markLs(Ctx& cx) {
    cx.nLs = 0;
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        u.inLs = eligible(u) && !u.excluded;
        if (u.inLs) cx.ls[cx.nLs++] = s;
    }
}

// A free slot for a new voice. When the table is full and audible, the weakest voice (A c) is moved to a fade-only slot so
// the slot is free in the same hop (spec 5.2); -1 when the new track is not louder than it.
int ResultantCore::allocateSlot(const Ctx& cx, double trackAmp) {
    (void)cx;
    for (int s = 0; s < kVoices; ++s) if (vo_[s].state == Empty) return s;
    int best = -1;
    for (int s = 0; s < kVoices; ++s) {
        const Voice& u = vo_[s];
        if (u.state == Rel && u.c < .01 && (best < 0 || u.A * u.c < vo_[best].A * vo_[best].c)) best = s;
    }
    if (best >= 0) { vo_[best] = Voice{}; return best; }
    int weak = 0;
    double wv = 1e300, wscore = 1e300;
    for (int s = 0; s < kVoices; ++s) {
        const double a = vo_[s].A * vo_[s].c, score = a + 1e-6 * vo_[s].A;   // candidates (c = 0) go by their own amplitude
        if (score < wscore) { wscore = score; wv = a; weak = s; }
    }
    if (!(trackAmp > wv)) return -1;
    Voice victim = vo_[weak];
    bool audible = false;
    for (int k = 0; k < kPartials; ++k) if (victim.a[k] != 0 || victim.aStart[k] != 0) audible = true;
    if (audible) {
        int fs = -1;
        for (int q = kVoices; q < kVoices + kFade; ++q) if (vo_[q].state == Empty) { fs = q; break; }
        if (fs < 0) {   // both fade slots busy: the one with less left is overwritten
            double m0 = 0, m1 = 0;
            for (int k = 0; k < kPartials; ++k) {
                m0 = std::max(m0, vo_[kVoices].a[k]); m1 = std::max(m1, vo_[kVoices + 1].a[k]);
            }
            fs = m0 <= m1 ? kVoices : kVoices + 1;
        }
        victim.state = Fade; victim.trackId = 0; victim.inLs = victim.born = victim.dead = false;
        vo_[fs] = victim;
    }
    rejectTrack(victim.trackId);
    vo_[weak] = Voice{};
    return weak;
}

// ------------------------------------------------------------------------------------------------ voices <-> tracks
void ResultantCore::syncVoices(Ctx& cx) {
    // start values of this hop's interval = end values of the previous one
    for (int s = 0; s < kVoices + kFade; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty) continue;
        u.thetaStart = u.theta; u.cStart = u.c; u.sigmaStart = u.sigma;
        for (int k = 0; k < kPartials; ++k) { u.aStart[k] = u.a[k]; u.psiStart[k] = u.psi[k]; }
    }
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty) continue;
        u.born = false; u.dead = false; u.excluded = false; u.inLs = false; u.tracked = false;
        int ti = -1;
        if (u.trackId) for (int t = 0; t < cx.nt; ++t) if (cx.tr[t].id == u.trackId) { ti = t; break; }
        if (ti >= 0) cx.bound[ti] = true;
        if (ti >= 0 && cx.tr[ti].missing == 0) {
            const TrackInfo& t = cx.tr[ti];
            const bool jump = u.fPrev > 0 && std::fabs(t.f - u.fPrev) > .03 * u.fPrev;
            u.f = t.f;
            u.dfHist[u.dfPos] = t.dfdt; u.dfPos = (u.dfPos + 1) & 3; if (u.dfN < 4) ++u.dfN;
            double sum = 0;
            for (int j = 0; j < u.dfN; ++j) sum += u.dfHist[j];
            u.fdot = clampv(sum / u.dfN, -400.0, 400.0);
            u.rawDb = t.raw; u.resDb = t.res;
            // a track that jumps (>3 %) keeps the oscillator where it is: the offset takes up the difference
            if (jump && (u.state == On || u.state == Rel)) u.fOff = clampv(u.fOsc - t.f, -.125 * t.f, .125 * t.f);
            u.tracked = true; u.coast = 0;
        } else {
            ++u.coast;   // coasting: last frequency + slope, the slope fading by 0.9 per hop
            u.f = clampv(u.f + u.fdot * kRHopS, 20.0, 250.0);
            u.fdot *= .9;
            if (ti >= 0) { u.rawDb = cx.tr[ti].raw; u.resDb = cx.tr[ti].res; }
        }
    }
    // re-link: a coasting voice takes a new track within 3 % of its predicted frequency (id, theta, psi, c are kept)
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if ((u.state != On && u.state != Rel) || u.tracked || u.coast > kRCoastMax) continue;
        int best = -1;
        double bd = 1e300;
        for (int t = 0; t < cx.nt; ++t) {
            if (cx.bound[t] || cx.tr[t].missing != 0) continue;
            const double d = std::fabs(cx.tr[t].f - u.f);
            if (d <= .03 * u.f && d < bd) { bd = d; best = t; }
        }
        if (best < 0) continue;
        const TrackInfo& t = cx.tr[best];
        cx.bound[best] = true;
        u.trackId = t.id; u.tracked = true; u.coast = 0;
        u.f = t.f;
        u.fOff = clampv(u.fOsc - t.f, -.125 * t.f, .125 * t.f);   // the oscillator frequency continues
        u.rawDb = t.raw; u.resDb = t.res;
    }
}

// Two voices closer than 3 Hz are one sound: the younger goes to REL and out of the fit; the older takes over its track.
void ResultantCore::mergeVoices(Ctx& cx) {
    (void)cx;
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state != Empty) u.fb = u.f + clampv(u.fOff, -.125 * u.f, .125 * u.f);
    }
    for (int i = 0; i < kVoices; ++i) {
        for (int j = i + 1; j < kVoices; ++j) {
            Voice& a = vo_[i];
            Voice& b = vo_[j];
            if (!eligible(a) || a.excluded || !eligible(b) || b.excluded) continue;
            if (std::fabs(a.fb - b.fb) >= 3.0) continue;
            const bool aOlder = a.birthHop < b.birthHop || (a.birthHop == b.birthHop && a.id < b.id);
            Voice& older = aOlder ? a : b;
            Voice& younger = aOlder ? b : a;
            if (!older.tracked && younger.tracked) {
                older.trackId = younger.trackId; older.tracked = true; older.coast = 0;
                older.f = younger.f;
                older.fOff = clampv(older.fOsc - older.f, -.125 * older.f, .125 * older.f);
                older.fb = older.f + older.fOff;
                younger.trackId = 0; younger.tracked = false;
            }
            if (younger.state == Cand) {
                younger = Voice{};
            } else {
                younger.state = Rel; younger.excluded = true;
                younger.lowSnrM = younger.domCnt = younger.revCnt = 0;
            }
        }
    }
}

// New tracks become candidates (lowest frequency first); never on top of an existing voice (that would be merged at once)
void ResultantCore::spawnVoices(Ctx& cx) {
    if (!cx.measured) return;
    int order[kTracks], n = 0;
    for (int t = 0; t < cx.nt; ++t) {
        const TrackInfo& tk = cx.tr[t];
        if (cx.bound[t] || tk.missing != 0 || !(tk.f >= 22.0 && tk.f <= 205.0) || rejected(tk.id)) continue;
        order[n++] = t;
    }
    for (int i = 1; i < n; ++i) {
        const int t = order[i];
        int j = i - 1;
        while (j >= 0 && cx.tr[order[j]].f > cx.tr[t].f) { order[j + 1] = order[j]; --j; }
        order[j + 1] = t;
    }
    for (int i = 0; i < n; ++i) {
        const TrackInfo& tk = cx.tr[order[i]];
        bool clash = false;
        for (int s = 0; s < kVoices; ++s)
            if (eligible(vo_[s]) && !vo_[s].excluded && std::fabs(vo_[s].fb - tk.f) < 3.0) clash = true;
        if (clash) continue;
        const int s = allocateSlot(cx, tk.a);
        if (s < 0) continue;
        Voice& u = vo_[s];
        u = Voice{};
        u.state = Cand; u.id = ++nextVoiceId_; u.trackId = tk.id; u.tracked = true; u.birthHop = hopCount_;
        u.f = u.fPrev = tk.f;
        u.fdot = clampv(tk.dfdt, -400.0, 400.0);
        u.dfHist[0] = tk.dfdt; u.dfN = 1; u.dfPos = 1;
        u.fb = u.fOsc = tk.f;
        u.rawDb = tk.raw; u.resDb = tk.res;
        cx.bound[order[i]] = true;
    }
}

// ------------------------------------------------------------------------------------------------ confidence inputs
// Evidence (b): a peak of the full-band spectrum within max(4 Hz, 3 %) of k f, k = 1 .. 4 (measured hops only)
bool ResultantCore::evidence(const Ctx& cx, double f) const {
    if (!cx.measured || !cx.src || !cx.ns) return false;
    for (int k = 1; k <= 4; ++k) {
        const double fk = k * f, tol = std::max(4.0, .03 * fk);
        for (int band = 0; band < 2; ++band)
            for (int j = 0; j < cx.ns[band]; ++j) if (std::fabs(cx.src[band][j] - fk) <= tol) return true;
    }
    return false;
}

// SNR of a voice (spec 5.4): the peak within +-2 bins of f_b over the median of the bins 22-45 Hz away that are not close to
// a voice, a track or their 2x and 3x; 22-70 Hz when fewer than 4; the whole band with the same exclusions when still fewer
double ResultantCore::snrOf(const Ctx& cx, const Voice& u) const {
    const double fb = u.fb;
    const int bc = static_cast<int>(std::lround(fb / cx.binHz));
    double peak = 0;
    for (int b = bc - 2; b <= bc + 2; ++b) {
        const int i = b - cx.loBin;
        if (i >= 0 && i < cx.nb) peak = std::max(peak, cx.mag[i]);
    }
    double vals[256];
    int n = 0;
    for (int pass = 0; pass < 2 && n < 4; ++pass) {
        const double lim = pass == 0 ? 45.0 : 70.0;
        n = 0;
        for (int i = 0; i < cx.nb; ++i) {
            if (cx.excl[i]) continue;
            const double d = std::fabs((cx.loBin + i) * cx.binHz - fb);
            if (d >= 22.0 && d <= lim) vals[n++] = cx.mag[i];
        }
    }
    if (n < 4) {
        n = 0;
        for (int i = 0; i < cx.nb; ++i) if (!cx.excl[i]) vals[n++] = cx.mag[i];
        if (n == 0) for (int i = 0; i < cx.nb; ++i) vals[n++] = cx.mag[i];
    }
    if (n == 0) return 0.0;
    std::nth_element(vals, vals + n / 2, vals + n);
    const double floorMag = std::max(vals[n / 2], 1e-10);
    return clampv(20 * std::log10(std::max(peak, 1e-30) / floorMag), -60.0, 120.0);
}

void ResultantCore::computeSnr(Ctx& cx) {
    markLs(cx);
    double ex[3 * (kTracks + kVoices)];
    int ne = 0;
    for (int t = 0; t < cx.nt; ++t) for (int m = 1; m <= 3; ++m) ex[ne++] = m * cx.tr[t].f;
    for (int j = 0; j < cx.nLs; ++j) for (int m = 1; m <= 3; ++m) ex[ne++] = m * vo_[cx.ls[j]].fb;
    for (int i = 0; i < cx.nb; ++i) {
        const double fbin = (cx.loBin + i) * cx.binHz;
        bool x = false;
        for (int e = 0; e < ne; ++e) if (std::fabs(fbin - ex[e]) <= 22.0) { x = true; break; }
        cx.excl[i] = x;
    }
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty || u.excluded) continue;
        u.snr = snrOf(cx, u);
        if (cx.measured) u.prominent = evidence(cx, u.f);
    }
}

// ------------------------------------------------------------------------------------------------ state machine
void ResultantCore::transitions(Ctx& cx) {
    const double snrOff = p_.snrOffDb;
    markLs(cx);   // the previous hop's stage 1 amplitudes (A1) are the neighbour table of the LS evidence rule
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state == On) {
            bool toRel = false;
            if (cx.measured) {
                u.lowSnrM = u.snr < snrOff ? u.lowSnrM + 1 : 0;
                if (u.lowSnrM >= 24) toRel = true;
                // far below a stronger neighbour within 15 Hz: its main lobe is what holds the spectral SNR up
                double strongest = 0;
                for (int j = 0; j < cx.nLs; ++j) {
                    const int q = cx.ls[j];
                    if (q == s) continue;
                    const Voice& w = vo_[q];
                    if (std::fabs(w.fb - u.fb) <= 15.0 && w.A1 > u.A1 && w.A1 > strongest) strongest = w.A1;
                }
                const double thr = u.coast > 0 ? 12.0 : 20.0;
                if (strongest > 0 && u.A1 < strongest * std::pow(10.0, -thr / 20)) ++u.domCnt; else u.domCnt = 0;
                if (u.domCnt >= 3) toRel = true;
            }
            if (u.coast > kRCoastMax) toRel = true;
            if (toRel) { u.state = Rel; u.lowSnrM = u.domCnt = u.revCnt = 0; }
        } else if (u.state == Rel) {
            if (cx.measured) {
                const bool good = u.snr >= snrOff + 4.0 && u.prominent && !u.excluded && (u.tracked || u.coast <= kRCoastMax);
                u.revCnt = good ? u.revCnt + 1 : 0;
                if (u.revCnt >= 3) { u.state = On; u.lowSnrM = u.domCnt = u.revCnt = 0; }
            }
        }
    }
    if (!cx.measured) return;   // no births (and no candidate bookkeeping) without a measurement
    int born[kVoices], nBorn = 0;
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state != Cand) continue;
        if (!u.tracked) {
            if (++u.absent >= 2) u = Voice{};
            continue;
        }
        u.absent = 0;
        ++u.candMeas;
        const bool okNow = u.snr >= p_.snrOnDb && u.prominent;
        bool birth = false;
        if (u.candOk && okNow) {   // (a) and (b) at both measured hops, (c) between them
            const double dt = static_cast<double>(hopCount_ - u.candHop) * kRHopS;
            const double df = std::fabs(u.f - u.candF);
            birth = df <= .03 * u.f && df <= p_.maxDfdtBirth * dt;
        }
        u.candOk = okNow; u.candF = u.f; u.candHop = hopCount_;
        if (birth) born[nBorn++] = s;
        else if (u.candMeas >= 12) { rejectTrack(u.trackId); u = Voice{}; }
    }
    for (int i = 1; i < nBorn; ++i) {   // lowest frequency first: a newborn can be subordinate to one born before it
        const int q = born[i];
        int j = i - 1;
        while (j >= 0 && vo_[born[j]].f > vo_[q].f) { born[j + 1] = born[j]; --j; }
        born[j + 1] = q;
    }
    for (int i = 0; i < nBorn; ++i) {
        Voice& u = vo_[born[i]];
        u.state = On; u.born = true; u.fOff = 0;
        u.lowSnrM = u.domCnt = u.revCnt = u.bigE = 0; u.trans = false;
        u.npv = u.npvPend = 0; u.psiSet = 0;
        for (int k = 0; k < kPartials; ++k) { u.present[k] = false; u.offC[k] = u.offF[k] = 0; }
        u.c = u.cStart = 0;
        if (isSubordinate(u.f, born[i])) u.sigma = u.sigmaStart = 0;   // starts silent, not after a 20 ms decay
    }
}

// ------------------------------------------------------------------------------------------------ least squares
void ResultantCore::solveLs(Ctx& cx) {
    markLs(cx);
    cx.lsOk = false;
    for (int s = 0; s < kVoices; ++s) vo_[s].npUsed = 0;
    const int nv = cx.nLs;
    if (nv == 0) return;
    const double fs = kRFs;
    double fbv[kVoices], fdv[kVoices];
    double fLow = 1e9, dfMin = 1e9, sOn = 1e9, sAll = 1e9;
    for (int j = 0; j < nv; ++j) {
        const Voice& u = vo_[cx.ls[j]];
        fbv[j] = u.fb;
        fdv[j] = clampv(u.fdot, -400.0, 400.0);
        fLow = std::min(fLow, fbv[j]);
        sAll = std::min(sAll, u.snr);
        if (u.state == On) sOn = std::min(sOn, u.snr);
    }
    for (int i = 0; i < nv; ++i) for (int j = i + 1; j < nv; ++j) dfMin = std::min(dfMin, std::fabs(fbv[i] - fbv[j]));
    // stage 1 window: N_J = clamp(max(N_lo, N_sep, N_snr(s_ON)), N_lo, 320), s_ON over the ON voices only
    const int nLo = rPeriodWindow(fLow, p_.nMin);
    int nSep = 0;
    if (nv >= 2) nSep = static_cast<int>(std::ceil(2 * p_.kappa * fs / std::max(dfMin, 1e-3))) - p_.nFuture;
    const int nSnr = rWindowTarget(sOn < 1e8 ? sOn : sAll, nLo);
    const int target = std::min(kRMaxPast, std::max(nLo, std::max(nSep, nSnr)));
    int sig[kVoices] = {};
    for (int j = 0; j < nv; ++j) sig[cx.ls[j]] = vo_[cx.ls[j]].id;
    bool changed = false;
    for (int s = 0; s < kVoices; ++s) if (sig[s] != lsSig_[s]) changed = true;
    std::copy(sig, sig + kVoices, lsSig_);
    if (changed || npJ_ <= 0) { npJ_ = target; npJPend_ = 0; }
    else if (std::abs(target - npJ_) > .25 * npJ_) { if (++npJPend_ >= 3) { npJ_ = target; npJPend_ = 0; } }
    else npJPend_ = 0;
    npJ_ = std::min(kRMaxPast, std::max(nLo, npJ_));
    const int npJ = npJ_, nf = std::min(npJ, p_.nFuture), len = npJ + nf + 1;
    cx.npJ = npJ; cx.nf = nf;

    double xs[kRMaxLen + 8], w1[kRMaxLen + 8];
    for (int i = 0; i < len; ++i) xs[i] = cx.x[(cx.nh - npJ + i) & (VbHpv::kRing - 1)];
    const double mc1 = rMakeWindow(w1, npJ, nf);

    // ---- stage 1: all voices of the LS set together
    const int nu = 2 * nv;
    double G[16][16], rhs[16], sol[16];
    for (int a = 0; a < 16; ++a) { rhs[a] = 0; for (int b = 0; b < 16; ++b) G[a][b] = 0; }
    ROsc osc[kVoices];
    for (int j = 0; j < nv; ++j) rOscInit(osc[j], kRTwoPi * fbv[j] / fs, kRTwoPi * fdv[j] / (fs * fs), -npJ);
    for (int i = 0; i < len; ++i) {
        double bs[16];
        for (int j = 0; j < nv; ++j) { bs[2 * j] = osc[j].c; bs[2 * j + 1] = osc[j].s; }
        const double wi = w1[i], xv = xs[i];
        for (int a = 0; a < nu; ++a) {
            const double wb = wi * bs[a];
            rhs[a] += wb * xv;
            for (int b = a; b < nu; ++b) G[a][b] += wb * bs[b];
        }
        for (int j = 0; j < nv; ++j) rOscStep(osc[j]);
    }
    if (!rSolve(G, rhs, nu, sol)) return;
    double al[kVoices], be[kVoices];
    for (int j = 0; j < nv; ++j) {
        Voice& u = vo_[cx.ls[j]];
        al[j] = sol[2 * j]; be[j] = sol[2 * j + 1];
        u.A = u.A1 = std::hypot(al[j], be[j]);
        u.thetaMeas = std::atan2(-be[j], al[j]);
        u.npUsed = npJ;
        u.cb = std::fabs(mc1) / 16.0;
    }

    // ---- stage 2: a window of its own for every clean voice, on the signal without the other voices' stage 1 components
    bool haveY = false;
    double ytot[kRMaxLen + 8], w2[kRMaxLen + 8];
    for (int j = 0; j < nv; ++j) {
        Voice& u = vo_[cx.ls[j]];
        if (!(u.snr >= kRStage2Snr)) continue;
        const int nLov = rPeriodWindow(fbv[j], p_.nMin);
        int nvv;
        if (u.trans) {   // the pitch is moving: the shortest window
            nvv = std::min(nLov, npJ);
            u.npv = nvv; u.npvPend = 0;
        } else {
            const int tgt = std::min(npJ, std::max(nLov, rWindowTarget(u.snr, nLov)));
            if (u.npv <= 0) { u.npv = tgt; u.npvPend = 0; }
            else if (std::abs(tgt - u.npv) > .25 * u.npv) { if (++u.npvPend >= 3) { u.npv = tgt; u.npvPend = 0; } }
            else u.npvPend = 0;
            u.npv = std::min(npJ, std::max(nLov, u.npv));
            nvv = u.npv;
        }
        const bool nuis2 = 2 * fbv[j] < 200.0, nuis3 = 3 * fbv[j] < 200.0;
        if (nv == 1 && nvv == npJ && !nuis2) continue;   // would reproduce stage 1
        if (!haveY) {
            ROsc oy[kVoices];
            for (int q = 0; q < nv; ++q) rOscInit(oy[q], kRTwoPi * fbv[q] / fs, kRTwoPi * fdv[q] / (fs * fs), -npJ);
            for (int i = 0; i < len; ++i) {
                double y = 0;
                for (int q = 0; q < nv; ++q) { y += al[q] * oy[q].c + be[q] * oy[q].s; rOscStep(oy[q]); }
                ytot[i] = y;
            }
            haveY = true;
        }
        const int len2 = nvv + nf + 1, off = npJ - nvv;
        const double mc2 = rMakeWindow(w2, nvv, nf);
        const int nu2 = 2 + (nuis2 ? 2 : 0) + (nuis3 ? 2 : 0);
        const double om = kRTwoPi * fbv[j] / fs, bt = kRTwoPi * fdv[j] / (fs * fs);
        ROsc o[3];
        for (int h = 0; h < 3; ++h) rOscInit(o[h], (h + 1) * om, (h + 1) * bt, -nvv);
        double G2[16][16], r2[16], s2[16];
        for (int a = 0; a < 16; ++a) { r2[a] = 0; for (int b = 0; b < 16; ++b) G2[a][b] = 0; }
        for (int i = 0; i < len2; ++i) {
            const double rv = xs[i + off] - ytot[i + off] + al[j] * o[0].c + be[j] * o[0].s;
            double bs[6];
            bs[0] = o[0].c; bs[1] = o[0].s;
            if (nuis2) { bs[2] = o[1].c; bs[3] = o[1].s; }
            if (nuis3) { bs[4] = o[2].c; bs[5] = o[2].s; }
            const double wi = w2[i];
            for (int a = 0; a < nu2; ++a) {
                const double wb = wi * bs[a];
                r2[a] += wb * rv;
                for (int b = a; b < nu2; ++b) G2[a][b] += wb * bs[b];
            }
            for (int h = 0; h < 3; ++h) rOscStep(o[h]);
        }
        if (!rSolve(G2, r2, nu2, s2)) continue;
        u.A = std::hypot(s2[0], s2[1]);
        u.thetaMeas = std::atan2(-s2[1], s2[0]);
        u.npUsed = nvv;
        u.cb = std::fabs(mc2) / 16.0;
    }
    cx.lsOk = true;
}

// ------------------------------------------------------------------------------------------------ phase, weights
// theta_hat and f_off (spec 5.6). Born voices take the measured phase; the others follow it with a PLL whose gain depends
// on the SNR; the frequency offset integrates the phase error with a gain limited by the centroid of the window used.
void ResultantCore::updatePhase(Ctx& cx) {
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty) continue;
        if (u.born) {
            if (!cx.lsOk) { u.state = Cand; u.born = false; u.c = u.cStart = 0; u.fOsc = u.f; continue; }   // not reached after a fit
            u.theta = u.thetaMeas; u.fOff = 0; u.fOsc = u.f; u.bigE = 0;
            continue;
        }
        const double pred = u.theta + kRTwoPi * u.fOsc * kRHopS;
        if (u.state == Cand) {
            u.theta = (cx.lsOk && u.inLs) ? u.thetaMeas : pred;
            u.fOff = 0; u.fOsc = u.f;
            continue;
        }
        if (cx.lsOk && u.inLs) {
            const double e = std::remainder(u.thetaMeas - pred, kRTwoPi), ae = std::fabs(e);
            const double lo = std::min(p_.betaMin, p_.betaMax), hi = std::max(p_.betaMin, p_.betaMax);
            const double beta = clampv((u.snr - 10.0) / 20.0, lo, hi);
            const double gamma = std::min(0.2, 0.5 / std::max(u.cb, 1e-9)) * beta;
            u.theta = pred + beta * e;
            u.fOff = clampv(u.fOff + gamma * e / (kRTwoPi * kRHopS), -.125 * u.f, .125 * u.f);
            if (ae < 0.2) u.fOff *= 0.98;
            if (u.state == On) {   // transition state: a pitch on the move keeps the short window
                if (cx.measured) u.bigE = ae > 0.5 ? u.bigE + 1 : 0;
                if (u.bigE >= 2) u.trans = true;
                if (ae < 0.3) { u.trans = false; u.bigE = 0; }
            }
        } else {
            u.theta = pred;
        }
        u.fOsc = u.f + u.fOff;
    }
}

// c (confidence), sigma (subordinate weight) and the end of a REL voice
void ResultantCore::updateWeights(Ctx& cx) {
    (void)cx;
    const double aOn = 1 - std::exp(-kRHopS * 1000.0 / p_.tauOnMs), aOff = 1 - std::exp(-kRHopS * 1000.0 / p_.tauOffMs);
    const double aSig = 1 - std::exp(-kRHopS * 1000.0 / 20.0);
    for (int s = 0; s < kVoices; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty) continue;
        const double cStar = u.state == On ? 1.0 : 0.0;
        u.c += (cStar - u.c) * (cStar > u.c ? aOn : aOff);
        u.subordinate = isSubordinate(u.f, s);
        u.sigma += ((u.subordinate ? 0.0 : 1.0) - u.sigma) * aSig;
        if (u.state == Rel && !u.tracked && u.c < 0.01) { u.c = 0; u.dead = true; }
    }
}

// ------------------------------------------------------------------------------------------------ input partials
// Projection of the unfiltered input on k f_osc (chirp k fdot) with a Hann window of half length N_k, presence with
// hysteresis, and the target phase psi* of every harmonic (spec 5.5); psi follows it at most psiSlew per hop.
void ResultantCore::updatePartials(VbHpv& v, Ctx& cx, Voice& u) {
    const double fo = u.fOsc;
    const int kmax = std::min(8, static_cast<int>(700.0 / fo));
    if (kmax < 2 || !(u.A > 0)) return;
    const double om = kRTwoPi * fo / kRFs;
    const double be = kRTwoPi * clampv(u.fdot, -400.0, 400.0) / (kRFs * kRFs);
    auto phiComp = [&](double f) {
        return interp52(vb52t::kPhase, 3920, (f - 20) * 4) + v.phaseDelta52(f) + kRTwoPi * f * kRTc;
    };
    for (int kk = 2; kk <= kmax; ++kk) {
        const int k = kk - 2;
        const int nk = std::min(191, std::max(48, static_cast<int>(std::lround(191 * 2.0 / kk))));
        // C_k = 2 sum w x e^{-j k Phi} / sum w, same phase convention as the LS (theta = atan2(-beta, alpha))
        const double d = kPi / (nk + 1), cd2 = 2 * std::cos(d);
        double c0 = -1.0, c1 = std::cos(d * nk);
        ROsc o;
        rOscInit(o, kk * om, kk * be, -nk);
        double sr = 0, si = 0, ws = 0;
        for (int m = -nk; m <= nk; ++m) {
            const double w = .5 * (1.0 + c1);
            const double xv = cx.md2[(cx.nh + m) & (VbHpv::kRing - 1)] * w;
            sr += xv * o.c; si += xv * o.s; ws += w;
            rOscStep(o);
            const double c2 = cd2 * c1 - c0;
            c0 = c1; c1 = c2;
        }
        const double cr = 2 * sr / ws, ci = -2 * si / ws, cabs = std::hypot(cr, ci);
        // the P1 'found' test on the full-band spectrum of this hop
        const double fk = kk * fo, tol = std::max(3.0, .02 * fk);
        const int b0 = std::max(1, static_cast<int>(std::floor((fk - tol) / cx.binHz)));
        const int b1 = std::min(cx.halfFft, static_cast<int>(std::ceil((fk + tol) / cx.binHz)) + 1);
        bool found = false;
        if (b1 - b0 >= 3) {
            int ii = b0;
            for (int b = b0 + 1; b < b1; ++b) if (cx.sm[b] > cx.sm[ii]) ii = b;
            if (cx.sm[ii] >= cx.sm[ii - 1] && cx.sm[ii] > cx.sm[ii + 1]) {
                const double la = std::log(cx.sm[ii - 1] + 1e-30), lb = std::log(cx.sm[ii] + 1e-30), lc = std::log(cx.sm[ii + 1] + 1e-30);
                const double off = offset52(la, lb, lc), fe = ii * cx.binHz + off * cx.binHz;
                const double ae = std::exp(lb - .25 * (la - lc) * off) * 2 / cx.wsum;
                found = std::fabs(fe - fk) <= tol && ae >= u.A * .01 && ae >= cx.pvAbs;
            }
        }
        const bool onCond = cabs >= .01 * u.A && cabs >= cx.pvAbs && found;
        if (!u.present[k]) {
            if (onCond) { u.present[k] = true; u.offC[k] = u.offF[k] = 0; }
        } else {
            u.offC[k] = cabs < .005 * u.A ? u.offC[k] + 1 : 0;
            u.offF[k] = !found ? u.offF[k] + 1 : 0;
            if (u.offC[k] >= 2 || u.offF[k] >= 2) u.present[k] = false;
        }
        const double target = u.present[k] ? std::atan2(ci, cr) - kk * u.theta + phiComp(fk)
                                           : psi52(kk, u.f, p_.crest != 0);
        if (!(u.psiSet & (1u << k))) {
            u.psi[k] = target; u.psiStart[k] = target; u.psiSet |= 1u << k;
        } else {
            u.psi[k] += clampv(std::remainder(target - u.psi[k], kRTwoPi), -p_.psiSlew, p_.psiSlew);
        }
    }
}

// ------------------------------------------------------------------------------------------------ amplitudes, synthesis
// Harmonic amplitudes at the end of the hop: a_vk = G_L g w_k R_k A c sigma (spec 5.6)
void ResultantCore::amplitudes(const VbHpv& v, Voice& u) const {
    for (int k = 0; k < kPartials; ++k) u.a[k] = 0;
    const double base = u.A * u.c * u.sigma, f = u.fOsc;
    if (!(base > 0) || !(f > 0)) return;
    double w[7], g;
    v.lookup(f, w, g);
    if (v.devHarm_) v.devWeights(w);
    double gl = 1.0;   // voicing 1: the register level (R4-L), 0 dB at 73.3 Hz, full from 92.4 to 150 Hz, 0 dB at 220 Hz
    if (p_.voicing == 1 && p_.levelDb > 0 && 3 * f > 220 && f < 220) {
        const double s = f < 92.4 ? 3 * std::log2(f * 3 / 220) : f <= 150 ? 1. : std::log2(220 / f) / std::log2(220 / 150.);
        gl = std::pow(10., p_.levelDb * clampv(s, 0., 1.) / 20);
    }
    const double corner = std::max(220., 3 * f);
    auto rolloff = [&](double fk, double cornerHz) {
        if (v.devRolloff_) {
            const double slope = clampv((v.upperMode_ == 0 ? 12. : 24.) + v.dev_.rolloffOffset, 0., 48.);
            return std::pow(10., -slope * std::log2(fk / cornerHz) / 20);
        }
        const double g12 = std::pow(10., -12 * std::log2(fk / cornerHz) / 20);
        return g12 + v.research_.upperBlend * (g12 * g12 - g12);
    };
    for (int kk = 2; kk <= 8; ++kk) {
        const double fk = kk * f;
        if (fk > 700.0) break;
        double r = 1.0;
        if (v.gentle_ && fk > 220) {
            if (p_.voicing == 0) r = rolloff(fk, 220.);
            else r = fk > corner ? rolloff(fk, corner) : 1.;
        }
        u.a[kk - 2] = gl * g * w[kk - 2] * r * base;
    }
}

// Voices pushed out of a full table fade with tau 5 ms (synthesis only)
void ResultantCore::fadeVoices() {
    const double decay = std::exp(-kRHopS / .005);
    for (int s = kVoices; s < kVoices + kFade; ++s) {
        Voice& u = vo_[s];
        if (u.state != Fade) continue;
        u.theta = u.thetaStart + kRTwoPi * u.fOsc * kRHopS;
        double mx = 0;
        for (int k = 0; k < kPartials; ++k) { u.a[k] = u.aStart[k] * decay; mx = std::max(mx, u.a[k]); }
        if (mx < 1e-7) { for (int k = 0; k < kPartials; ++k) u.a[k] = 0; u.dead = true; }
    }
}

// s_res(n) = sum_v sum_k a_vk(n) cos(k theta_v(n) + psi_vk(n)) for n in [C_{h-1}, C_h): theta rises by a constant step, the
// amplitudes and psi are interpolated linearly between the hop ends
void ResultantCore::synthesize(const Ctx& cx) {
    double acc[16] = {};
    for (int s = 0; s < kVoices + kFade; ++s) {
        const Voice& u = vo_[s];
        if (u.state == Empty) continue;
        const double th0 = std::remainder(u.thetaStart, kRTwoPi), dth = (u.theta - u.thetaStart) / 16.0;
        for (int k = 0; k < kPartials; ++k) {
            if (u.a[k] == 0 && u.aStart[k] == 0) continue;
            const double kk = k + 2, da = u.a[k] - u.aStart[k], dp = u.psi[k] - u.psiStart[k];
            for (int j = 0; j < 16; ++j) {
                const double t = j / 16.0;
                double sn, cs;
                fastmath::sincos(kk * (th0 + dth * j) + u.psiStart[k] + dp * t, sn, cs);
                acc[j] += (u.aStart[k] + da * t) * cs;
            }
        }
    }
    for (int j = 0; j < 16; ++j) out_[(cx.ih + j) & (kOut - 1)] += acc[j];
}

void ResultantCore::writeTrace(const Ctx& cx) {
    if (traceCap_ <= 0) return;
    if (traceN_ >= traceCap_) { traceOver_ = true; return; }
    double* row = trace_.data() + static_cast<size_t>(traceN_) * kVoices * kTraceFields;
    for (int s = 0; s < kVoices; ++s, row += kTraceFields) {
        const Voice& u = vo_[s];
        row[0] = static_cast<double>(cx.ih);
        if (u.state == Empty) { std::fill(row + 1, row + kTraceFields, 0.0); continue; }
        row[1] = u.id; row[2] = u.trackId; row[3] = u.state; row[4] = u.coast;
        row[5] = u.f; row[6] = u.fOsc; row[7] = u.fdot; row[8] = u.A; row[9] = u.c; row[10] = u.sigma;
        row[11] = u.npUsed; row[12] = u.snr; row[13] = u.prominent ? 1 : 0; row[14] = u.rawDb; row[15] = u.resDb;
        row[16] = u.subordinate ? 1 : 0; row[17] = u.theta; row[18] = u.psi[0]; row[19] = u.psi[1];
        row[20] = u.a[0]; row[21] = u.a[1];
    }
    ++traceN_;
}

// ------------------------------------------------------------------------------------------------ the hop
void ResultantCore::hop(VbHpv& v, bool measured, const double (*src)[256], const int* ns) {
    Ctx cx;
    cx.ih = static_cast<int64_t>(v.i_);
    cx.nh = cx.ih - 191;
    cx.measured = measured && src && ns;
    cx.src = src; cx.ns = ns;
    cx.nt = std::min(v.nt52_, kTracks);
    for (int t = 0; t < cx.nt; ++t) {
        const auto& s = v.tr52_[t];
        TrackInfo& d = cx.tr[t];
        d.id = s.id; d.f = s.f; d.dfdt = s.dfdt; d.a = s.a; d.res = s.residual; d.raw = s.rawResidual; d.missing = s.missing;
    }
    cx.loBin = v.loBin_; cx.nb = std::min(v.hiBin_ - v.loBin_, 256);
    cx.binHz = v.binHz_; cx.wsum = v.pvWsum_; cx.pvAbs = v.pvAbs_;
    for (int b = 0; b < cx.nb; ++b) cx.mag[b] = std::hypot(v.xr52_[cx.loBin + b], v.xi52_[cx.loBin + b]);
    cx.x = p_.ampSource ? v.detailRing52_ : v.bhRing_;
    cx.md2 = v.md2_52_; cx.sm = v.sm52_; cx.halfFft = VbHpv::kHalfFft;
    ++hopCount_;

    syncVoices(cx);
    mergeVoices(cx);
    spawnVoices(cx);
    computeSnr(cx);
    transitions(cx);
    solveLs(cx);
    updatePhase(cx);
    updateWeights(cx);
    if (cx.measured && cx.lsOk)
        for (int s = 0; s < kVoices; ++s) {
            Voice& u = vo_[s];
            if (u.state == On && u.tracked && u.inLs) updatePartials(v, cx, u);
        }
    for (int s = 0; s < kVoices; ++s) if (vo_[s].state != Empty) amplitudes(v, vo_[s]);
    fadeVoices();
    synthesize(cx);
    writeTrace(cx);
    for (int s = 0; s < kVoices + kFade; ++s) {
        Voice& u = vo_[s];
        if (u.state == Empty) continue;
        u.fPrev = u.f;
        if (u.dead) u = Voice{};
    }
}

}  // namespace pvb

// PVB speaker engine - Resultant core (docs/RESULTANT_CORE.md v1.3): the sustained layer of algorithm 15 (VB_RESULTANT).
//
// P1's front end (band path, HPSS, PV tracker, tables, phase calibration) stays; only the amplitude path of the sustained
// layer is new. Per hop (16 core samples at 3 kHz) a voice manager binds voices to tracker ids, a two-stage past-weighted
// least squares fit reads amplitude and phase of every voice from the harmonic stream, a PLL-smoothed oscillator phase
// drives per-sample synthesis of k f (k = 2..8) into a small output ring that core52 reads instead of P1's grain ring.
//
// This header only declares; the definitions are in pvb_resultant.inc, which pvb_vb52.cpp includes at its end (same
// translation unit as the helpers psi52/interp52/offset52 and the private members of VbHpv). Fixed-size state only: no
// allocation after construction except traceEnable() (host research trace), none in the audio path.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <cstdint>
#include <vector>

namespace pvb {

class VbHpv;

// Parameters in the order of pvb_set_resultant (spec 5.8). snrFastDb is kept for the slot (v1.3 removed the one-hop birth).
struct ResultantParams {
    int voicing = 0;            // 0 P1 timbre, 1 register corner + level
    double levelDb = 0;         // voicing 1: register level
    int ampSource = 0;          // 0 bhRing_, 1 detailRing52_
    double snrOnDb = 15, snrFastDb = 22, snrOffDb = 6;
    double tauOnMs = 8, tauOffMs = 30;
    double betaMin = .2, betaMax = .9;
    double kappa = 1.0;
    int nMin = 30;
    int nFuture = 24;
    double psiSlew = .12;
    int crest = 0;
    double maxDfdtBirth = 200;
    double capRho = 0;          // v1.5.1 (16.17; 13.2 D2 as revised by 13.5 F4): stage 1 coefficient cap rho, 0 = off (v1.5)
    int windowCreep = 0;        // v1.6-a A1 (18.3; 13.2 D4 narrowed by 13.5 F5): window growth limit, samples per hop (1..320), 0 = off (v1.5)
    int creepMode = 0;          // A1' (18.5): which windows the growth limit acts on and when. 0 = N_J and N_v always (18.3 A1), 1 = N_v only while its voice's SNR
                                // is falling, 2 = N_v (own SNR) and N_J (max SNR over the LS set) only while falling; no effect when windowCreep = 0
};

class ResultantCore {
public:
    static constexpr int kVoices = 8;        // voice slots (V_max)
    static constexpr int kFade = 2;          // extra fade-only slots for voices pushed out of a full slot table
    static constexpr int kPartials = 7;      // harmonics k = 2..8
    static constexpr int kParams = 19;
    static constexpr int kTraceFields = 22;
    static constexpr int kOut = 64;          // output ring, power of two (a hop writes 16 samples ahead of the read index)
    static constexpr int kTracks = 12;       // VbHpv::tr52_ capacity
    static constexpr int kFallHops = 6;      // A1': SNR history length, 6 hops = 32 ms (the 30 ms of 18.5)

    enum State : int { Empty = 0, Cand = 1, On = 2, Rel = 3, Fade = 4 };

    ResultantCore() { reset(); }
    // Forgets voices, rings and the recorded trace; keeps the parameters and the trace allocation.
    void reset();
    // v[0..n) in the order of spec 5.8, the rest at the defaults. false (nothing applied) when a value is out of range.
    bool setParams(const double* v, int n);
    const ResultantParams& params() const { return p_; }
    // Host research trace: kVoices rows of kTraceFields doubles per hop. Allocation here only. hops <= 0 frees it.
    bool traceEnable(int hops);
    // Rows copied (kVoices per recorded hop), -1 no trace, -2 capacity (doubles) too small, -3 hop capacity exceeded.
    int traceCopy(double* out, int capacity) const;
    // One hop (called at the end of pvFrame52 with measured = true and src/ns of that hop, and at the end of
    // missingFrame52 with measured = false). Writes the 16 samples [i, i + 16) of the output ring.
    void hop(VbHpv& v, bool measured, const double (*src)[256], const int* ns);
    // Reads and clears one output sample (index = core sample index).
    double take(int64_t index) {
        double& s = out_[index & (kOut - 1)];
        const double r = s;
        s = 0;
        return r;
    }

private:
    struct TrackInfo {
        uint32_t id = 0;
        double f = 0, dfdt = 0, a = 0, res = -200, raw = -200;
        int missing = 0;
    };
    struct Voice {
        int state = Empty;
        int id = 0;
        uint32_t trackId = 0;
        bool tracked = false;      // the bound track was measured in this hop
        bool excluded = false;     // merged into an older voice in this hop (not in the LS)
        bool inLs = false;
        bool born = false;         // became ON in this hop
        bool trans = false;        // transition state: short window until the phase error settles
        bool dead = false;         // REL, faded out, no track: the slot is freed at the end of the hop
        bool prominent = false;    // evidence (b) in the last measured hop
        bool subordinate = false;
        bool candOk = false;       // CAND: (a) and (b) held at the last measured hop
        unsigned psiSet = 0;       // bit k: psi of harmonic k + 2 has been given its first value
        int coast = 0;             // hops since the track was last measured
        int lowSnrM = 0;           // consecutive measured hops with SNR < snrOff
        int domCnt = 0;            // consecutive measured hops far below a stronger neighbour (LS evidence rule)
        int revCnt = 0;            // REL: consecutive measured hops with SNR >= snrOff + 4 dB and evidence
        int absent = 0;            // CAND: consecutive measured hops without a measured track
        int candMeas = 0;          // CAND: measured hops since the voice appeared
        int bigE = 0;              // consecutive measured hops with |e| > 0.5 rad
        int onMeas = 0;            // measured hops this voice has been ON without a break (subordinate rule, v1.5)
        int histN = 0;             // consecutive measured hops with a LS phase in thHist (at most 8)
        int64_t onHop = -1;        // hop at which the voice was born ON (same-hop births are subordinate by ratio alone)
        double thHist[8] = {};     // LS phase theta_v at n_h of the last measured hops, slot = measCount_ & 7
        int dfN = 0, dfPos = 0;
        int npv = 0, npvPend = 0;  // per-voice past window (stage 2) and its hysteresis counter
        int npvA = 0;              // window creep: the stage 2 window actually applied (follows npv up by at most windowCreep per hop)
        double snrH[kFallHops] = {};   // A1': SNR of the last hops (ring), snrHp = next slot, snrHn = valid entries
        int snrHp = 0, snrHn = 0;
        int npUsed = 0;            // past window actually used for this voice in this hop (trace)
        int64_t birthHop = 0;
        int64_t candHop = -1;      // measured hop at which candOk / candF were taken
        double candF = 0;
        double f = 0, fPrev = 0, fdot = 0;   // track (or coasting) frequency, Hz; smoothed slope, Hz/s
        double dfHist[4] = {};
        double fOff = 0, fb = 0, fOsc = 0;   // oscillator offset, LS basis frequency, oscillator frequency
        double theta = 0, thetaStart = 0, thetaMeas = 0;
        double A = 0, A1 = 0, snr = 0, cb = 0;   // amplitude (final / stage 1), SNR dB, window centroid in hops
        double c = 0, cStart = 0, sigma = 1, sigmaStart = 1;
        double rawDb = -200, resDb = -200;
        double psi[kPartials] = {}, psiStart[kPartials] = {};
        double a[kPartials] = {}, aStart[kPartials] = {};
        bool present[kPartials] = {};
        int offC[kPartials] = {}, offF[kPartials] = {};
    };
    struct Ctx {
        int64_t ih = 0;            // core sample index of the hop (VbHpv::i_)
        int64_t nh = 0;            // ring slot of the analysis centre (ih - 191)
        bool measured = false;
        int nt = 0;
        TrackInfo tr[kTracks];
        bool bound[kTracks] = {};
        int loBin = 0, nb = 0;     // bh spectrum magnitudes for the bins loBin .. loBin + nb - 1
        double binHz = 0, wsum = 0, pvAbs = 0;
        double mag[256] = {};
        bool excl[256] = {};       // bins within 22 Hz of a LS voice / track frequency and their 2x, 3x
        const double (*src)[256] = nullptr;
        const int* ns = nullptr;
        const double* x = nullptr;     // LS signal ring (bhRing_ or detailRing52_)
        const double* md2 = nullptr;
        const double* sm = nullptr;
        int halfFft = 1024;
        int nLs = 0;
        int ls[kVoices] = {};
        int npJ = 0, nf = 0;
        bool lsOk = false;
    };

    // hop steps (pvb_resultant.inc)
    void syncVoices(Ctx& cx);
    void mergeVoices(Ctx& cx);
    void spawnVoices(Ctx& cx);
    void markLs(Ctx& cx);
    void computeSnr(Ctx& cx);
    double snrOf(const Ctx& cx, const Voice& u) const;
    bool evidence(const Ctx& cx, double f) const;
    void transitions(Ctx& cx);
    void solveLs(Ctx& cx);
    void updatePhase(Ctx& cx);
    void updateWeights(Ctx& cx);
    void updatePartials(VbHpv& v, Ctx& cx, Voice& u);
    void amplitudes(const VbHpv& v, Voice& u) const;
    void fadeVoices();
    void synthesize(const Ctx& cx);
    void writeTrace(const Ctx& cx);
    int allocateSlot(const Ctx& cx, double trackAmp);
    void rejectTrack(uint32_t id);
    bool rejected(uint32_t id) const;
    bool isSubordinate(int self) const;
    bool phaseLocked(int v, int u, int m) const;
    void updatePhaseHistory(const Ctx& cx);
    bool eligible(const Voice& u) const { return u.state == Cand || u.state == On || (u.state == Rel && u.c > 0.1); }

    ResultantParams p_;
    Voice vo_[kVoices + kFade];
    double out_[kOut];
    int nextVoiceId_ = 0;
    int64_t hopCount_ = 0;
    int64_t measCount_ = 0;    // measured hops so far (ring slot of the voices' phase histories)
    // stage 1 window (N_J) hysteresis and the LS set it was computed for
    int npJ_ = 0, npJPend_ = 0;
    int npJA_ = 0;             // window creep: N_J actually applied (npJ_ stays the hysteresis-held value); 0 = start at N_lo
    double sMaxH_[kFallHops] = {};   // A1' (creepMode 2): maximum SNR over the LS set at the last hops (ring); emptied when the set is empty
    int sMaxHp_ = 0, sMaxHn_ = 0;
    int lsSig_[kVoices] = {};
    // tracks that were pushed out or timed out as candidates: not given a voice again for a while
    uint32_t rejId_[8] = {};
    int64_t rejHop_[8] = {};
    int rejPos_ = 0;
    // host research trace
    std::vector<double> trace_;
    int traceCap_ = 0, traceN_ = 0;
    bool traceOver_ = false;
};

}  // namespace pvb

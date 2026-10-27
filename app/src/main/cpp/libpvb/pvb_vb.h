// PVB speaker engine - virtual bass (experimental, alpha).
//
// A virtual bass module turns the low end the phone speaker cannot play into a layer of harmonics. The engine adds
// the layer to both channels after the EQ filters, before the output gain and the limiter. Its input is either the
// engine's pre-EQ input (inputAfterEq() false: hpv, a purely synthesised harmonic layer that needs the bass below the
// 100 Hz high-pass) or the EQ output itself (true: Bankstown, out = x + layer(x) on the same signal - its layer keeps a
// copy of 150-300 Hz, which only adds in phase to the very signal it came from). While a module with latency is
// active, the engine delays its own (dry) path by latencyFrames() so the layer lines up with the music.
//
// Interface rules (so a later algorithm, e.g. "hpv 5.1", can be added next to these two):
//   - all memory is part of the object (no allocation after construction, none in tick());
//   - configure(sampleRate) only recomputes coefficients; it returns false for a rate the module does not support;
//   - the latency is fixed for a given rate;
//   - tick() is called once per frame, from the audio thread only.
//
// Algorithms:
//   VbHpv        'hpv' from tools/pvb-harness/vb5 (frozen reference: tools/pvb-harness/vb_port/hpv_ref.py):
//                mono input -> 3 kHz (polyphase, exact for 44.1 and 48 kHz) -> band 32-190 Hz -> causal median HPSS
//                -> percussive part: 1-band analytic generator (u^k, k = 2..8); harmonic part: sinusoidal / phase
//                vocoder path (128 ms frames, <= 4 peaks, harmonic k at phase k*Phi) with envelope imposition
//                -> output band 150-600 Hz -> back to the host rate. Latency 146.9 ms (see hpv_ref.py).
//   VbBankstown  chadmed/bankstown (MIT), per channel, no latency, on the EQ output:
//                p = LP2(ceil)(HP2(floor)(x)), sat = K [blend tanh(s3 p) + (1 - blend) tanh(s2 p) (p <= 0)],
//                K = pi / (0.5 + e), layer = LP2(3 ceil)(HP2(final_hp)(amt sat)); RBJ Butterworth biquads.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include "pvb_dsp.h"
#include "pvb_vb_policy.h"
#include "pvb_harmonic_trace.h"
#include "pvb_vb_continuity.h"
#include "pvb_vb_modulation.h"
#include "pvb_vb_am_family.h"
#include "pvb_vb_stage.h"
#include "pvb_track_prediction.h"
#include "pvb_track_protection.h"
#include "pvb_harmonic_renderer.h"

namespace pvb {

enum VbAlgo : int { VB_HPV = 0, VB_BANKSTOWN = 1, VB_HPV52M = 2, VB_GENTLE = 3,
                   VB_GENTLE_STRONG = 4, VB_GENTLE_ADAPTIVE = 5,
                   VB_ALPHA2_P1 = 6, VB_ALPHA2_D2 = 7, VB_ALPHA2_J2 = 8,
                   VB_ALPHA2_OSC = 9, VB_ALPHA2_OSC_CORRECT = 10,
                   // P1 with the P1+ research flags 6 (phase hold + centred HPSS, +26.7 ms) and P1++ v0.2
                   // (flags 6, impact mode 4): app models, "실험" (research/p1pp, docs/P1PP_RESEARCH.md)
                   VB_ALPHA2_P1_PLUS = 11, VB_ALPHA2_P1PP = 12,
                   // P1++ v0.3: flags 6, impact mode 8 (research/p1pp/2026-10-26-v03)
                   VB_ALPHA2_P1PP_V03 = 13, VB_ALGO_COUNT };

// Scene observations are unvalidated. Only the opt-in adaptive profile uses
// them to select a harmonic attenuation budget; they are not buzz labels.
enum VbScene : int { VB_SCENE_UNKNOWN = 0, VB_SCENE_STEADY, VB_SCENE_TRANSIENT, VB_SCENE_COMPLEX };
// Research hook (gen-s1s2, 2026-10-22); all fields off reproduce the production profiles bit for bit. The app
// reaches only `envelope` with the defaults below, on P1, through the experimental option P_X_S1M
// (Engine::vbApply -> setGenEnvelope); every other field and `bursts` (S2) stay host research.
// envelope (S1): one envelope per track harmonic replaces permission x life x fade
//   (linear attack attackMs, one-pole release releaseMs; onsetReleaseMs only for
//   tracks ended by a newly born note at a true onset, see onsetMode), and the envelope-imposition gain falls no
//   faster than gainReleaseMs (0 = unchanged).
// bursts (S2): the percussive u^k stream is replaced by fixed-envelope harmonic
//   bursts started only at low-band onsets (attack burstAttackMs, -40 dB after
//   burstDecayMs), harmonic weights and placement from the P1 track renderer.
struct GenResearch52 {
    bool envelope = false, bursts = false;
    double attackMs = 10, releaseMs = 70, onsetReleaseMs = 20, gainReleaseMs = 70;
    double burstAttackMs = 5, burstDecayMs = 90, onsetDb = 6, refractoryMs = 60;
    // Which born events end lost tracks with onsetReleaseMs: 0 every born note (P1 rule),
    // 1 only when the low band also rises 3 dB above its level 43-300 ms earlier, 2 never.
    int onsetMode = 1;
};
// Developer mode voicing (general build, "개발자 모드"). Every field at its default reproduces the model bit for bit;
// a field only takes a new code path while it differs from the default. Applied by the engine on the audio thread
// (VbHpv::setDev) to the masked (hpv52m family) modules only. See pvb_engine.h P_D_*.
struct DevVoicing {
    static constexpr double kBoundaryHz = 190.0;   // generator input band: LR4 low-pass edge (table kBandSos)
    static constexpr double kOutLoHz = 150.0;      // output band: 4th-order Butterworth high-pass (table kOutSos)
    static constexpr double kOutHiHz = 600.0;      // output band: 2nd-order Butterworth low-pass (table kOutSos)
    static constexpr int kAttackHops = 2, kReleaseHops = 6;   // ContinuityParams defaults (16/3000 s hops)
    double boundaryHz = kBoundaryHz, outLoHz = kOutLoHz, outHiHz = kOutHiHz;
    double harmDb[4] = {0, 0, 0, 0};  // k = 2, 3, 4, and 5..8: dB re the model's own weight table
    double rolloffOffset = 0;         // dB/oct added to the module's sustained upper roll-off above 220 Hz
    double sustDb = 0, percDb = 0;    // sustained (vocoder) / percussive (analytic) path gains
    int attackHops = kAttackHops, releaseHops = kReleaseHops;   // P1-family track life (continuity) attack/release
    double tableScale = 1.0;          // speaker-floor scale: weight/gain table looked up at f / tableScale
    bool operator==(const DevVoicing& o) const {
        for (int i = 0; i < 4; ++i) if (harmDb[i] != o.harmDb[i]) return false;
        return boundaryHz == o.boundaryHz && outLoHz == o.outLoHz && outHiHz == o.outHiHz &&
               rolloffOffset == o.rolloffOffset && sustDb == o.sustDb && percDb == o.percDb &&
               attackHops == o.attackHops && releaseHops == o.releaseHops && tableScale == o.tableScale;
    }
    bool operator!=(const DevVoicing& o) const { return !(*this == o); }
};
// Developer-mode display snapshot of one module: the loudest rendered track of the last vocoder frame (sustained
// path, before the output band filter), its k = 2..8 harmonic amplitudes and the envelope-imposition gain.
struct DevHarmonics {
    static constexpr int kTracks = 3;
    int n = 0;                     // tracks held (loudest rendered tracks since the last read), 0 = none
    double f[kTracks] = {};        // Hz
    double amp[kTracks][7] = {};   // linear, at layer level 0 dB, before the output filter and the imposition gain
    double sum[kTracks] = {};      // sum of amp (ranking)
    double gain = 0;               // envelope-imposition gain applied to the sustained path (last core sample)
    // Keeps the [kTracks] loudest: a track within 10 % of a held one merges into it (largest amplitude per harmonic).
    void add(double hz, const double* a, double s) {
        if (!(hz > 0) || !(s > 0)) return;
        for (int i = 0; i < n; ++i) {
            if (std::fabs(hz - f[i]) <= 0.10 * f[i]) {
                for (int k = 0; k < 7; ++k) amp[i][k] = std::max(amp[i][k], a[k]);
                if (s > sum[i]) { sum[i] = s; f[i] = hz; }
                return;
            }
        }
        int slot = n < kTracks ? n++ : -1;
        if (slot < 0) {
            int lo = 0;
            for (int i = 1; i < n; ++i) if (sum[i] < sum[lo]) lo = i;
            if (s <= sum[lo]) return;
            slot = lo;
        }
        f[slot] = hz; sum[slot] = s;
        for (int k = 0; k < 7; ++k) amp[slot][k] = a[k];
    }
    void clearTracks() { n = 0; }
};
struct VbResearchStats {
    int scene = VB_SCENE_UNKNOWN;
    uint64_t frames[4] = {};
    double upperBlend = 0; // 0: gentle12, 1: gentle24, shared oscillator phases
    int upperTarget = 0;
    uint64_t transitions = 0;
};

class VbModule {
public:
    virtual ~VbModule() = default;
    // Recomputes the coefficients for this rate and resets; false = not available at this rate (then unused).
    virtual bool configure(int sampleRate) = 0;
    virtual void reset() = 0;
    // Frames the dry path must be delayed by so the layer lines up with it.
    virtual int latencyFrames() const = 0;
    // false: tick() gets the pre-EQ input; true: it gets the EQ output (before the output gain).
    virtual bool inputAfterEq() const = 0;
    // One frame of pre-EQ input in, one frame of layer out (layer at the 'faithful' level, level 0 dB).
    virtual void tick(double inL, double inR, double& outL, double& outR) = 0;
    virtual VbResearchStats researchStats() const { return {}; } // audio thread only
    virtual void setHarmonicCapture(bool) {}
    virtual const HarmonicTrace* takeHarmonicTrace() { return nullptr; }
    // Developer mode (audio thread only). Modules without support ignore the voicing and report no harmonics.
    virtual void setDev(const DevVoicing&) {}
    virtual void setDevMeter(bool) {}
    // Takes the tracks held since the last call (developer meter; audio thread, once per block).
    virtual bool devHarmonics(DevHarmonics&) { return false; }
    // |output filter| at f Hz (the module's own output band), 1 when it has none.
    virtual double devOutResponse(double) const { return 1.0; }
};

// ------------------------------------------------------------------------------------------------ hpv
struct HpvParams {
    double epsDb = -80.0;          // soft floor of the analytic magnitude (no gate)
    double ifFloorDb = -52.0;      // below this band magnitude the instantaneous frequency is not trusted
    double ifDefaultHz = 60.0;
    double ifSmoothS = 0.005;      // one-pole on the instantaneous frequency
    double gainSmoothS = 0.020;    // slower frequency estimate for the level table
    double fLoHz = 32.0, fHiHz = 190.0;   // clamp of the frequency used for the tables
    int pvMaxPeaks = 4;
    double pvRelDb = -30.0;        // peaks within this of the strongest
    double pvAbsDb = -75.0;        // frames below this are skipped (tracks reset)
    double pvPeakMinSepHz = 12.0;
    double pvTrackTol = 0.10;      // a peak continues a track within 10 % of its frequency
    double envCap = 1.0;           // envelope imposition: cut only
    double envSmoothS = 0.020;
    double harmonicMinWeight = 1e-4;
};

class VbHpv final : public VbModule {
public:
    // Core rate and frame sizes (fixed: the tables and buffers are sized for them).
    static constexpr int kFsd = 3000;
    static constexpr int kHpN = 192, kHpHop = 16, kHpMedT = 11, kHpMedF = 7, kHpBins = kHpN / 2 + 1;
    static constexpr int kPvN = 384, kPvH = 16, kPvNfft = 2048, kMaxPeaks = 8;
    static constexpr int kRtShift = kPvH - 1;
    static constexpr int kDeferHops = 3;  // P1++ v0.4 bit 32: hops a guarded track's grains wait (read one hop later)  // the reference grain placement looks 15 core samples ahead
    static constexpr int kKMax = 8;

    explicit VbHpv(bool masked = false, bool gentle = false, int upperMode = 0);
    bool configure(int sampleRate) override;
    void reset() override;
    int latencyFrames() const override {
        return latency_ + (supported_ ? static_cast<int>(std::lround(
            static_cast<double>(hpssLookahead()+outputDefer())*M_/L_)) : 0);
    }
    bool inputAfterEq() const override { return false; }
    void tick(double inL, double inR, double& outL, double& outR) override;
    VbResearchStats researchStats() const override { return research_; }
    void setHarmonicCapture(bool on) override { harmonicCapture_ = on; if (!on) harmonicReady_ = false; }
    const HarmonicTrace* takeHarmonicTrace() override {
        if (!harmonicReady_) return nullptr;
        harmonicReady_ = false; return &harmonicTrace_;
    }
    // Host research only: configure before processing; not a saved app algorithm.
    void setContinuityResearch(const ContinuityParams& p) { continuity_ = p; reset(); }
    // Host-only controls, no JNI/UI; bit0=synthesis, bit1=analysis.
    void setModulationResearch(int mode, bool tonalOnly=false) { modulationMode_=mode&3; tonalOnly_=tonalOnly; reset(); }
    // Host-only P1+ experiments, off by default. Bit0: exclude a valid
    // modulation frame's stationary residual from the stationary history;
    // bit1: keep the current synthesis phase offset when no source reference
    // is available; new tracks still start at the table phase.
    // bit2: centered eleven-frame HPSS, five future hops (26.667 ms).
    // bit3 (requires bit2): mix causal/centered masks by spectral prominence.
    // No bit changes the app's stored algorithm or the public trace ABI.
    // Host values apply to profile 6 only; profiles 11/12 use their fixed flags.
    void setP1PlusResearch(unsigned flags) { p1PlusHostFlags_=flags&15; if(!p1PlusFixed_) p1PlusFlags_=p1PlusHostFlags_; reset(); }
    // Host-only: 0=baseline, 1=current fit, 2=unconfirmed fit, 3=first-fit
    // recovery, 4=clean current-fit recovery after initial rejection,
    // 5=mode 4 only inside an impact context (percussive > 1/4 of harmonic, held 24 hops) with tones playing
    // before the impact resuming at once, 6=the same with a percussive-spike context, 7=no guard for tones with
    // stationary history (5-7 were evaluated and set aside), 8=mode 4 with steady tones released (P1++ v0.3,
    // app model 13; research/p1pp/2026-10-26-v03).
    // Host-only knobs of the research modes 5-8 (impact-context hold in hops, mode 7 history limit in dB,
    // mode 8 steady hops, amplitude ratio and minimum strength against the strongest peak of the hop).
    // Defaults are the values the modes were evaluated with.
    void setP1PPResearchParams(int hold, double historyDb, int steadyHops, double steadyA, double releaseStrength) {
        impactHold52_=hold; histDbResearch_=historyDb; steadyHops52_=steadyHops; steadyA52_=steadyA;
        releaseStrength52_=releaseStrength; }
    void setP1PPImpactResearch(int mode) { p1ppHostImpact_=mode; if(!p1PlusFixed_) p1ppImpactMode_=mode; reset(); }
    // Host-only P1++ v0.4 research on top of impact mode 8 (research/p1pp/2026-10-27-v04): 1 = a confirmed track
    // whose peak is not among the six strongest keeps its own local peak (up to 8 peaks), 2 = steadiness from the
    // phase-vocoder phase prediction instead of the amplitude ratio, 4 = no strength condition, 8 = a birth within
    // 3 % of a confirmed track that ended in the last 250 ms is that track again, 16 = a guarded track still emits
    // the harmonics the input already has at k f, 32 = the layer is read four hops later and a guarded track's
    // grains are kept; when the track is released within three hops they are added back where they belonged.
    void setP1PPV04Research(unsigned flags) { p1ppV04Host_=flags&127; if(!p1PlusFixed_) p1ppV04_=p1ppV04Host_; reset(); }
    void setStageResearch(unsigned flags,StageCapture52::Sink sink=nullptr,void* user=nullptr) {
        stageHostFlags_=flags&8191;stageFlags_=stageHostFlags_;stageSink_=sink;stageUser_=user;reset();
    }
    // App listening profiles, applied only by the audio owner while switching.
    // All use the same gentle24 placement. Legacy research setters remain separate.
    bool setAlpha2Profile(int algorithm);
    void setStageCapture(StageCapture52::Sink sink,void* user) {stageSink_=sink;stageUser_=user;}
    // Host research only; survives setAlpha2Profile (see GenResearch52).
    void setGenResearch(const GenResearch52& g) { gen_=g; reset(); }
    // App option "배음별 단일 포락선" (S1m, P1 only): the S1 envelope with the research defaults. No reset here: the
    // engine calls it while switching (faded out) and then setAlpha2Profile, which resets the module. Realtime safe.
    void setGenEnvelope(bool on) { gen_=GenResearch52{}; gen_.envelope=on; }
    bool genEnvelope() const { return gen_.envelope; }

    // Developer mode (masked modules only; ignored by the legacy hpv). No allocation; filter memory is kept.
    void setDev(const DevVoicing& d) override;
    void setDevMeter(bool on) override { devMeter_ = on; if (!on) devSnap_ = DevHarmonics{}; }
    bool devHarmonics(DevHarmonics& out) override {
        if (!masked_) { devSnap_.clearTracks(); return false; }
        out = devSnap_; devSnap_.clearTracks(); return true;
    }
    double devOutResponse(double f) const override;

    // Audio-thread-owned EQ, including coefficient glides and dynamic bass. A standalone module uses the
    // reference EQ v1.1 at 48 kHz. The engine binds these objects for phase matching to the actual dry path.
    void bindEq(const RampedSvf* hp, const RampedSvf* lo, const RampedSvf* hi, const RampedSvf* hs, int fs) {
        eq52_[0]=hp; eq52_[1]=lo; eq52_[2]=hi; eq52_[3]=hs; eqFs52_=fs;
    }

    HpvParams params;  // read at configure() / reset(); change only while the module is not ticking

private:
    // Defined only by the host harness; invokes the production grain renderer.
    friend struct HarmonicRendererTestAccess;
    struct Biquad {  // direct form II transposed, like scipy.signal.sosfilt
        double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z0 = 0, z1 = 0;
        inline double tick(double x) {
            const double y = b0 * x + z0;
            z0 = b1 * x - a1 * y + z1;
            z1 = b2 * x - a2 * y;
            return y;
        }
        void clear() { z0 = z1 = 0; }
    };
    struct Allpass {  // y[n] = c (x[n] + y[n-2]) - x[n-2] as scipy.signal.lfilter([c, 0, -1], [1, 0, -c])
        double c = 0, z0 = 0, z1 = 0;
        inline double tick(double x) {
            const double y = c * x + z0;
            z0 = 0.0 * x - 0.0 * y + z1;
            z1 = -1.0 * x - (-c) * y;
            return y;
        }
        void clear() { z0 = z1 = 0; }
    };
    struct Hilbert {
        Allpass i[4], q[4];
        double qPrev = 0;
        void clear();
        void tick(double x, double& re, double& im);
    };
    struct OnePole {  // lfilter([1 - a], [1, -a]) with an initial state
        double b0 = 0, a = 0, z = 0;
        inline double tick(double x) {
            const double y = b0 * x + z;
            z = a * y;  // b1 * x - a1 * y with b1 = 0, a1 = -a
            return y;
        }
    };
    struct Track { double f, phi; };

    double core(double d);       // one 3 kHz sample in, one out (the reference's output kRtShift samples earlier)
    double core52(double d);
    void pvFrame52();
    void spectrum52(const double* ring, int64_t start, double* re, double* im);
    bool masked_ = false;
    bool gentle_ = false;
    int upperMode_ = 0; // 0 fixed12, 1 fixed24, 2 experimental adaptive12/24
    UpperHarmonicPolicy upperPolicy_;
    VbResearchStats research_;
    void observeScene(int scene) {
        if (!gentle_) return;
        research_.scene = scene;
        ++research_.frames[scene];
        if(upperMode_==2) {
            upperPolicy_.step(scene==VB_SCENE_STEADY);
            research_.upperBlend=upperPolicy_.blend();
            research_.upperTarget=upperPolicy_.target();
            research_.transitions=upperPolicy_.switches();
        }
    }
    const RampedSvf* eq52_[4] = {};
    int eqFs52_ = 48000;
    double phaseDelta52(double f) const;
    void hpssFrame();            // a 192-sample HPSS frame is complete
    void pvFrame();              // a 384-sample vocoder frame is complete
    void lookup(double f, double* wk, double& gk) const;
    void fft64(double* re, double* im) const;                   // in place, natural order in and out
    void dft192(const double* xr, const double* xi, double* yr, double* yi, int nOut);  // forward, first nOut bins
    double bandLayer(double re, double im);

    // rate conversion (host rate <-> exactly 3 kHz): decimated sample m = input at time m / 3000 s
    int L_ = 1, M_ = 16, taps_ = 0;
    const double* fir_ = nullptr;          // FIR at fs * L (unity DC gain)
    double firDec_[1471] = {};             // fir * L
    double firInt_[1471] = {};             // fir * M
    static constexpr int kInRing = 256, kHcRing = 32;
    double inRing_[kInRing] = {};
    double hcRing_[kHcRing] = {};
    uint64_t n_ = 0, m_ = 0, mDue_ = 0;    // next input index, next decimated index and its input index
    bool supported_ = false;
    int latency_ = 0;

    // 3 kHz core
    uint64_t i_ = 0;                       // core sample index
    Biquad band_[4], out_[3];
    // HPSS
    static constexpr int kRing = 512;      // power of two, > every look-back below
    double bRing_[kRing] = {};
    double winHp_[kHpN] = {};
    double wsumHp_[kHpHop] = {};
    double cosHp_[kHpN] = {}, sinHp_[kHpN] = {};   // exp(-2 pi i n / 192); 192 = 3 x 64 (mixed radix)
    int bitrev64_[64] = {};
    double tw64r_[63] = {}, tw64i_[63] = {};   // per-stage twiddles of fft64 (same values as its table lookups)
    double fr3_[3][64] = {}, fi3_[3][64] = {};
    // HQ prominence mode retains both target-frame windows: past 10..future 5.
    double sHist_[kHpMedT+5][kHpBins] = {};
    int sPos_ = 0;
    double olaH_[kRing] = {}, olaP_[kRing] = {};
    Hilbert hilH_, hilP_;
    // percussive generator state
    double prevUr_ = 0, prevUi_ = 0;
    bool first_ = true;
    OnePole fInst_, fGain_;
    double hpRing_[kRing] = {};            // percussive layer, delayed by kPvN / 2 at use
    // vocoder
    double bhRing_[kRing] = {};            // harmonic stream
    double aRing_[kRing] = {};             // |analytic harmonic stream|
    double winPv_[kPvN] = {};
    double pvWsum_ = 0;
    double cosPv_[kPvNfft] = {}, sinPv_[kPvNfft] = {};   // exp(-2 pi i n / 2048)
    static constexpr int kHalfFft = kPvNfft / 2;          // real 2048-point FFT through a complex 1024-point one
    int bitrev_[kHalfFft] = {};
    double zr_[kHalfFft] = {}, zi_[kHalfFft] = {};
    // Twiddles of the 1024-point stages in the order the butterflies use them: stage with half length h at
    // [h - 1, 2h - 1): cosPv_[k * 2048 / (2h)] and -sinPv_[...] (the same values the loops used to look up).
    double twr_[kHalfFft] = {}, twi_[kHalfFft] = {};
    void fftHalf();  // in place on zr_ / zi_ (input in bit-reversed order), radix 2
    double gw_[2 * kPvH] = {};
    int loBin_ = 0, hiBin_ = 0;
    double binHz_ = 0;
    double pvOut_[kRing] = {}, pvApv_[kRing] = {};
    Track tracks_[kMaxPeaks] = {};
    int nTracks_ = 0;
    OnePole envA_, envP_;
    double eps_ = 0, ifFloor_ = 0, pvAbs_ = 0, pvRel_ = 0, cPsi_[kKMax - 1] = {}, sPsi_[kKMax - 1] = {};

    // hpv52m: all state is fixed-size and owned by the module; no audio-thread allocations.
    struct Track52 {
        double f=0, phi=0, off[7]={}, fade=0, a=0;
        bool impactRecoveryPending=false;
        int steadyHops=0;               // P1++ mode 8: hops of steady frequency and amplitude while unconfirmed
        bool guarded=false;             // P1++ v0.4 bit 16: held back by the fit guard in this hop
        double confF=0; int64_t confHop=-1000;  // P1++ v0.4 bit 8: frequency and hop when last confirmed (fade >= .5)
        int confHops=0; bool inherited=false;   // hops confirmed so far; this track continues a long confirmed one
        // P1++ v0.4 bit 32: grains this track would have emitted while the guard held it (oldest first)
        double pend[kDeferHops][32]={}, pendNominal[kDeferHops]={}; int64_t pendCentre[kDeferHops]={}; int pendN=0;
        bool strong=false, fastEnding=false;
        uint32_t id=0, age=0;
        double dfdt=0, life=1, residual=-200, rawResidual=-200;
        int missing=0;
        double dadt=0;
        ModulationFit modulation;
        AmFamily52 family;
        HarmonicPermission permission[7];
        prediction52::History prediction;
        trackprotection::State protection;  // host-only v0.4 bit 64: frozen stable frequency over kick onset
        oscillator52::State oscillator;
        double envPeak=0; // S1 research: largest harmonic envelope after the last render
    };
    Track52 tr52_[12];
    ContinuityParams continuity_;
    int modulationMode_=0;
    bool tonalOnly_=false;
    unsigned stageFlags_=0;
    unsigned p1PlusFlags_=0;
    int p1ppImpactMode_=0;
    bool p1PlusProfile_=false;
    bool p1PlusFixed_=false;          // profile 11/12: flags fixed by the model, host values kept for profile 6
    unsigned p1PlusHostFlags_=0;
    int p1ppHostImpact_=0;
    unsigned p1ppV04Host_=0, p1ppV04_=0;
    // v0.4 bit 8: confirmed tracks that ended recently (frequency, hop of the end)
    double grave52_[8]={}; int64_t graveHop52_[8]={}; int graveN52_=0; int64_t hop52_=0;
    // research impact modes 5/6: impact context and the tones playing when it began
    int impactCtx52_=0, preImpactN52_=0;
    double histDbResearch_=-6, percSlow52_=0;
    int impactHold52_=24, steadyHops52_=3;
    double steadyA52_=.97, releaseStrength52_=.4;
    double preImpactF52_[12]={};
    int hpssLookahead() const { return p1PlusProfile_ && (p1PlusFlags_&4) ? 5*kHpHop : 0; }
    int outputDefer() const {
        return p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_==8 && (p1ppV04_&32) ? kPvH*(kDeferHops+1) : 0; }
    unsigned stageHostFlags_=0;  // explicit host stage choices survive first P1 profile activation
    StageCapture52::Sink stageSink_=nullptr;
    void* stageUser_=nullptr;
    double detailRing52_[kRing]={};
    bool detailApplied52_=false, familyApplied52_=false;
    AmFamily52 family52_;
    int64_t familyCentre52_=0;
    int familyCountdown52_=0;
    double conditionalGain52_=0;
    double oscillatorNominal52_[kPvH]={};
    uint32_t nextTrackId_=0, harmonicEpoch_=0;
    bool harmonicCapture_=false, harmonicReady_=false;
    HarmonicTrace harmonicTrace_;
    void beginHarmonic52();
    void traceTrack52(int slot, const Track52& t, int state, int reason);
    void renderTrack52(Track52& t, const double src[2][256], const int ns[2], bool observed,
                       bool fast, int traceSlot, double* grain, double& agrain);
    void addGrain52(int64_t centre, const double* grain, double nominalAmplitude);
    void takeGrain52(int64_t index, double& sample, double& nominalAmplitude);
    void missingFrame52(int reason, bool fast);
    void grave52(const Track52& tr);   // P1++ v0.4 bit 8: remember a confirmed track that ended
    int nt52_=0, apkCount_=0, histCount_=0, holdCount_=0, holdPos_=0, onsetLeft_=0;
    double apk52_[56]={}, hist52_[11][8]={};
    int histN52_[11]={};
    double hold52_[28][190]={};
    double md52_[kRing]={}, md2_52_[kRing]={}, max52_[kRing]={}, polyT52_[kRing]={};
    double poly52_=1, percEnv52_=0, harmEnv52_=0;
    // gen-s1s2 research state (unused unless gen_ is set)
    GenResearch52 gen_;
    double genGain_=0, genFastE_=0, genSlowE_=0, lastFc_=60, lastGk_=0;
    int64_t genLastOnset_=-1000000;
    static constexpr int kBurstDelay=45; // 15 ms look-ahead for the burst amplitude, inside the hp read delay
    double genAmpRing_[kRing]={}, genPhaseRing_[kRing]={};
    bool genOnsetRing_[kRing]={};
    struct Burst { double amp=0, phi=0, f=60, w[7]={}; int64_t start=0; bool on=false; };
    Burst bursts_[2];
    double burstSample52(int64_t j);
    double xr52_[kHalfFft+1]={}, xi52_[kHalfFft+1]={};
    double sr52_[kHalfFft+1]={}, si52_[kHalfFft+1]={}, sm52_[kHalfFft+1]={};

    // Developer mode. Each flag is set only while its value differs from the model, so the default path is untouched.
    DevVoicing dev_;
    bool devHarm_=false, devRolloff_=false, devMix_=false;
    double devHarmLin_[4]={1,1,1,1}, devSustLin_=1, devPercLin_=1;
    void applyDevContinuity();
    void devWeights(double* w) const { for(int k=0;k<kKMax-1;++k) w[k]*=devHarmLin_[k<3?k:3]; }
    double devGain_=0;   // developer release: envelope-imposition gain follower
    double devAttM_=0, devAttS_=0;   // developer attack: layer level and its attack-limited follower
    bool devMeter_=false;
    DevHarmonics devFrame_, devSnap_;   // this frame's loudest tracks; tracks gathered since the engine's last read
    void devBeginFrame() { devFrame_.clearTracks(); }
    void devEndFrame() { for(int i=0;i<devFrame_.n;++i) devSnap_.add(devFrame_.f[i],devFrame_.amp[i],devFrame_.sum[i]); }
};

// ------------------------------------------------------------------------------------------------ Bankstown
struct BankstownParams {  // defaults: Asahi Linux tuning for the MacBook Pro 14 (to be replaced by phone values)
    double amt = 1.45;
    double s2 = 1.35;
    double s3 = 2.25;
    double blend = 0.67;
    double floorHz = 20.0;
    double ceilHz = 200.0;
    double finalHpHz = 200.0;
};

class VbBankstown final : public VbModule {
public:
    bool configure(int sampleRate) override;
    void reset() override;
    int latencyFrames() const override { return 0; }
    bool inputAfterEq() const override { return true; }
    void tick(double inL, double inR, double& outL, double& outR) override;

    BankstownParams params;  // read at configure()

private:
    struct Biquad {
        double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z0 = 0, z1 = 0;
        inline double tick(double x) {
            const double y = b0 * x + z0;
            z0 = b1 * x - a1 * y + z1;
            z1 = b2 * x - a2 * y;
            return y;
        }
    };
    static Biquad rbj(double fs, double f, bool lowpass);
    double chan(int c, double x);
    Biquad hp_[2], lp_[2], hpOut_[2], lpOut_[2];
    double k_ = 0;
    int sr_ = 0;
};

}  // namespace pvb



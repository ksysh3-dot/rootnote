#include "way3combo1_level.h"
#include "way3alt1_synth.h"
#include "way3alt2_synth.h"
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
// The app uses the COMBO harmonic generator.
// Older algorithms are recoverable at archive/models-pre-prune-20261102.
// The optional fixed Resultant c source lives under tools/pvb_combo1-harness/reference.
// VbHpv: mono -> 3 kHz -> causal HPSS -> tracked/percussive harmonics -> output band.
// Existing P1 arithmetic and rate-conversion tables are retained for V0.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once
#include "team2_family.h"
#include "hrr3.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include "pvb_dsp.h"
#include "pvb_harmonic_trace.h"
#include "pvb_vb_continuity.h"
#include "pvb_vb_modulation.h"
#include "pvb_vb_am_family.h"
#include "pvb_vb_stage.h"
#include "pvb_track_prediction.h"
#include "pvb_track_protection.h"
#include "pvb_harmonic_renderer.h"

namespace pvb_combo1 {

// Stable JNI IDs: deleted slots 0-5, 7-15 and 17 stay reserved, never reused.
enum VbAlgo : int { VB_ALPHA2_P1 = 6, VB_RESULTANT_V16 = 16, VB_ALGO_COUNT = 18 };
inline bool supportedVbAlgo(int id) {
    return id == VB_ALPHA2_P1
        ;
}

// Scene observations are unvalidated. Only the opt-in adaptive profile uses
// them to select a harmonic attenuation budget; they are not buzz labels.
enum VbScene : int { VB_SCENE_UNKNOWN = 0, VB_SCENE_STEADY, VB_SCENE_TRANSIENT, VB_SCENE_COMPLEX };
// Optional envelopes for sustained harmonics and percussive bursts.
// envelope: one envelope per track harmonic replaces permission x life x fade
//   (linear attack attackMs, one-pole release releaseMs; onsetReleaseMs only for
//   tracks ended by a newly born note at a true onset, see onsetMode), and the envelope-imposition gain falls no
//   faster than gainReleaseMs (0 = unchanged).
// bursts: the percussive u^k stream is replaced by fixed-envelope harmonic
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
    // Only the integrated STABLE mode selects the frozen analysis window.
    // Storage stays at legacy maxima; OFF/STRONG keep their original windows.
    void setStable183Window(bool enabled);
    static void warmShortKernel();
    int baseDelay48() const { return base48_; }
    static constexpr int kFsd = 3000;
    static constexpr int kHpN = 192, kHpHop = 16, kHpMedT = 11, kHpMedF = 7, kHpBins = kHpN / 2 + 1;
    static constexpr int kPvN = 384, kPvH = 16, kPvNfft = 2048, kMaxPeaks = 8;
    static constexpr int kRtShift = kPvH - 1;
    static constexpr int kDeferHops = 3;  // hops a guarded track's grains wait (read one hop later)  // the reference grain placement looks 15 core samples ahead
    static constexpr int kKMax = 8;

    explicit VbHpv(bool masked = false, bool gentle = false, int upperMode = 0);
    void freezeCombo1() {
        setAlpha2Profile(VB_ALPHA2_P1);
        family2_=true;comboLevel_=comboMedian_=comboNumeric_=true;
        age2sW2_=x35W2_=true;altFlags_=59;alt2Mode_=3;
        mode128_=0;prediction131_=nullptr;capture131_=nullptr;
        reset();
    }

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
    // host diagnostics only: configure before processing; not a saved app algorithm.
    void setContinuityResearch(const ContinuityParams& p) { continuity_ = p; reset(); }
    // set before processing; caller owns optional trace storage.
    // mode0 OFF; 1 onset50,2 slow250,3 confidence,4 table;5..9 diagnostic ablations;10..12 event realignment.
    bool setPhase41(int mode,double* trace,int capacity) {
        if(mode<0 || mode>12 || capacity<0 || (capacity && !trace)) return false;
        s41HostMode_=mode; s41Mode_=s32Profile_?mode:0;
        s41Log_=trace; s41LogCapacity_=capacity; s41LogCount_=0; return true;
    }
    int phase41Count() const { return s41LogCount_; }
    // Audio owner, muted batch only. One following joint reset replaces repeated
    // diagnostic setter resets; no host flags can leak into the frozen preset.
    void prepareP1pppResearch(bool on) {
        setObs130(0,0);
        setObs128(0,nullptr);
        setOpen112(0); // Re-prepare clears this host-only intervention and observers.
        s41HostMode_=on?12:0;s41Mode_=s32Profile_?s41HostMode_:0;
        s41Log_=nullptr;s41LogCapacity_=s41LogCount_=0;
        s32HostFlags_=s32Flags_=0;s38HostFlags_=s38Flags_=0;
        s38HostMode_=s38Mode_=s38TapeN_=0;s38Value_=0.;s38Tape_=nullptr;
        p1PlusHostFlags_=p1PlusFlags_=0;p1ppHostImpact_=p1ppImpactMode_=0;
        p1ppV04Host_=p1ppV04_=0;stageHostFlags_=stageFlags_=0;
        stageSink_=nullptr;stageUser_=nullptr;genReq_=gen_=GenResearch52{};
    }
    // host-only stage diagnosis, all zero by default. Tape is baseline-derived
    // ID-indexed (frequency, circular phase intercept), owned by the host.
    bool setN2Research(unsigned flags,int mode,double value,const double* tape,int count) {
        if(flags>63 || mode<0 || mode>10 || !std::isfinite(value) || value<0 || count<0 || (count && !tape)) return false;
        s38HostFlags_=flags; s38HostMode_=mode; s38Value_=value; s38Tape_=tape; s38TapeN_=count;
        s38Flags_=s32Profile_?flags:0; s38Mode_=s32Profile_?mode:0; if(flags || mode || count) reset(); return true;
    }
    // host-only, before processing. 1=current fit, 2=salience, 4=dry novelty focus.
    // No truth/MIDI/stem inputs. Only profile 6 applies these controls.
    bool setP1WrongNoteResearch(unsigned flags) {
        if(flags>7) return false;
        s32HostFlags_=flags; if(s32Profile_) s32Flags_=flags; reset(); return true;
    }
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
    // Tune impact hold time, stationary history and the strength needed to release a steady tone.
    void setP1PPResearchParams(int hold, double historyDb, int steadyHops, double steadyA, double releaseStrength) {
        impactHold52_=hold; histDbResearch_=historyDb; steadyHops52_=steadyHops; steadyA52_=steadyA;
        releaseStrength52_=releaseStrength; }
    // onset protection (StageOnsetProtect): protected for the first holdHops of the 24-hop onset window,
    // the register corner share falls to floorBlend there, and comes back with tauUpMs. Defaults: 24, 0, 60.
    void setR4Research(int holdHops,double floorBlend,double tauUpMs) {
        r4Hold52_=holdHops; r4Floor52_=floorBlend; r4TauUp52_=tauUpMs; }
    // register level (StageRegisterLevel), dB at full share. Default 6.
    void setR4Level(double gainDb) { r4LevelDb52_=gainDb; }
    // (StageReentrySlow): time constant of a track's share coming back after a failed fit. Default 250.
    void setR4Reentry(double tauMs) { r4ReentryTau52_=tauMs; }
    void setP1PPImpactResearch(int mode) { p1ppHostImpact_=mode; if(!p1PlusFixed_) p1ppImpactMode_=mode; reset(); }
    // Impact tracking flags: 1 = a confirmed track
    // whose peak is not among the six strongest keeps its own local peak (up to 8 peaks), 2 = steadiness from the
    // phase-vocoder phase prediction instead of the amplitude ratio, 4 = no strength condition, 8 = a birth within
    // 3 % of a confirmed track that ended in the last 250 ms is that track again, 16 = a guarded track still emits
    // the harmonics the input already has at k f, 32 = the layer is read four hops later and a guarded track's
    // grains are kept; when the track is released within three hops they are added back where they belonged.
    void setP1PPV04Research(unsigned flags) { p1ppV04Host_=flags&511; if(!p1PlusFixed_) p1ppV04_=p1ppV04Host_; reset(); }
    // Only the diagnostic generator applies the saved stage flags.
    void setRho101(double r){rho101_=r;}
    void setMode102(int m){mode102_=m;}
    void setMode103(int m){mode103_=m;}
    // host observation swaps; borrowed peer, never a PCM source.
    struct ObsPeak128 {double f=0,a=0,ph=0,beta=0;};
    VbHpv* peer128_=nullptr;
    int mode128_=0,np128_=0;int64_t stamp128_=-1;
    ObsPeak128 peaks128_[8];
    uint64_t counts128_[9]={}; // aligned,bad,A attempts,A changed,F attempts,F changed,C hops,C changed,zero A
    void setObs128(int mode,VbHpv* peer){mode128_=mode;peer128_=peer;std::fill_n(counts128_,9,0);}
    // Mask bits: 1 fit residual; 2 mask; 4 noise3; 8 noise6; 16 trailing median5.
    float* capture131_=nullptr;int capacity131_=0,count131_=0;bool noSwap131_=false;
    const float* prediction131_=nullptr;int predictions131_=0;uint64_t missing131_=0,used131_=0;
    void setCapture131(float* p,int n,bool noSwap){capture131_=p;capacity131_=n;count131_=0;noSwap131_=noSwap;}
    void setPrediction131(const float* p,int n){prediction131_=p;predictions131_=n;missing131_=used131_=0;if(p)mode128_=1;}
    int mode130_=0;uint64_t seed130_=0,counts130_[14]={};
    double fitModelF130_[8]={},fitModelA130_[8]={},fitModelP130_[8]={};int fitModelN130_=0;
    double rawFit130_[8]={};bool falling130_=false;
    double src130_[2][256]={};int ns130_[2]={};
    void setObs130(int mode,uint64_t seed){mode130_=mode;seed130_=seed;std::fill_n(counts130_,14,0);}
    double rawResidual130(double f) const;
    double fitResidual130(double f,double& raw) const;
    double evidence130(double f,int k,bool observed) const;
    void setOpen112(int mode) {
        open112_=mode;openHops112_=fadeHops112_=maskHops112_=0;openSeen112_=0;
    }
    int open112_=0; // Host overrides, off by default.
    uint64_t openHops112_=0,fadeHops112_=0,maskHops112_=0;
    int openSeen112_=0; // Reset for every synthesis hop, including missing-frame hops.
    void noteOpen112(int bit) {
        if(openSeen112_&bit)return;
        if(!openSeen112_)++openHops112_;
        if(bit==1)++fadeHops112_;else ++maskHops112_;
        openSeen112_|=bit;
    }
    void setFadeGate106(int m){fadegate106_=m;}
    int fadegate106_=0; // 0 off, 1 slow decay, 2 hold for up to 12 failed hops
    void setSlew105(double r){slew105_=r;slewFall105_=std::pow(10.,-r/20.);}
    double slew105_=0, slewFall105_=1; // dB/hop, default disabled
    int mode103_=0; // 1 born-cut tracks release normally, 2 also crossfade with the newcomer; off by default
    int mode102_=0; // 1 energy-matched floor, 2 level-only, off by default
    double rho101_=0; // 3rd-harmonic floor for f>=90 Hz, off by default
    double gentleCorner94_=220.;
    void setGentleCorner94(double hz){gentleCorner94_=hz;}

    void setStageResearch(unsigned flags,StageCapture52::Sink sink=nullptr,void* user=nullptr) {
        stageHostFlags_=flags&268435455;stageFlags_=resultantOn_?0u:stageHostFlags_;stageSink_=sink;stageUser_=user;reset();
    }
    // App listening profiles, applied only by the audio owner while switching.
    // All use the same gentle24 placement. Legacy diagnostic setters remain separate.
    bool setAlpha2Profile(int algorithm);
    // Restore defaults when leaving the reference path without selecting another profile.
    void leaveResultantSet() {
    }
    void setStageCapture(StageCapture52::Sink sink,void* user) {stageSink_=sink;stageUser_=user;}
    // Host-only controls: replace the selected HPSS outputs (InjectHpss, inside [hStart,hEnd)
    // of the core clock) and/or the envelope targets (InjectEnvelope, inside [eStart,eEnd)) by host buffers indexed
    // by core sample. The buffers belong to the host and must outlive processing. mask 0 (default, the app) leaves
    // the path as is.
    struct StageInject52 {
        enum : unsigned { InjectHpss=1, InjectEnvelope=2 };
        unsigned mask=0; const double* bh=nullptr; const double* bp=nullptr; const double* as=nullptr;
        const double* ps=nullptr; int64_t n=0, hStart=0, hEnd=0, eStart=0, eEnd=0;
        bool active(unsigned bit,int64_t i) const {
            if(!(mask&bit) || i>=n) return false;
            return bit==InjectHpss ? i>=hStart && i<hEnd : i>=eStart && i<eEnd;
        }
    };
    void setStageInject(const StageInject52& v) { inject_=v; reset(); }
    // Host-only track replacement: a tape of the track list after every hop. Recording saves the tracks (bed-only render);
    // Playback substitutes tracks inside hops [startHop,endHop): a track within tol (relative) of a taped track takes the taped
    // state, a taped track with no counterpart is added while there is room, every other (impact) track is kept.
    // Allocation happens here, outside the audio call. No tape (the app) leaves the path as is.
    struct TrackTape52;
    static TrackTape52* createTrackTape(int hops);
    static void destroyTrackTape(TrackTape52* t);
    // recorded hops, replaced, added, kept, duplicate ids, overflow, replay hops in the window
    static int trackTapeStats(const TrackTape52* t,long long* out,int n);
    void setTrackTape(TrackTape52* t,int mode,int64_t startHop,int64_t endHop,double tol) {
        tape_=t; tapeMode_=t?mode:0; tapeStart_=startHop; tapeEnd_=endHop; tapeTol_=tol; reset();
    }
    // Host diagnostics survive profile changes.
    // genReq_ remembers the request, gen_ (the one the code reads) is the default while resultantOn_.
    void setGenResearch(const GenResearch52& g) { genReq_=g; gen_=resultantOn_?GenResearch52{}:g; reset(); }
    // App option "배음별 단일 포락선" (S1m, P1 only): the S1 envelope with the diagnostic defaults. No reset here: the
    // engine calls it while switching (faded out) and then setAlpha2Profile, which resets the module. Realtime safe.
    void setGenEnvelope(bool on) { genReq_=GenResearch52{}; genReq_.envelope=on; if(!resultantOn_) gen_=genReq_; }
    bool genEnvelope() const { return gen_.envelope; }

    // Host voice parameters in declaration order (false:
    // out of range, nothing applied; kept for any algorithm), and the per-hop voice trace (allocation in enable only).

    // Developer mode (masked modules only; ignored by the legacy hpv). No allocation; filter memory is kept.
    void setDev(const DevVoicing& d) override;
    void setDevMeter(bool on) override { devMeter_ = on; if (!on) devSnap_ = DevHarmonics{}; }
    // Developer detail (developer meter on, COMBO level only): the harmonic level terms of family slot s at its latest
    // hop, dB unless noted: tracker cap T, low-band supply G*sqrt(2J), power mix, 5-hop median level, start
    // attenuation (<= 0), X35 expander loss (>= 0), final amplitude, winning min term (0 T, 1 J, 2 mix), added decay loss (>= 0 dB), predicted amplitude (dB).
    bool comboDev(int s, float* out) const {
        if (s < 0 || s >= 6) return false;
        for (int j = 0; j < 10; ++j) out[j] = comboDev_[s][j];
        return true;
    }
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
    // The host renderer reads the tracker, rings and spectra of this module and writes its output ring.
    friend class ResultantCore;
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
    int polyCausal52(int64_t s0);
    void spectrum52(const double* ring, int64_t start, double* re, double* im);
    const bool masked_ = true;
    const bool gentle_ = true;
    static constexpr int upperMode_ = 1; // P1 fixed 24 dB/oct
    VbResearchStats research_;
    void observeScene(int scene) {
        if (!gentle_) return;
        research_.scene = scene;
        ++research_.frames[scene];

    }
    const RampedSvf* eq52_[4] = {};
    int eqFs52_ = 48000;
    double phaseDelta52(double f) const;
    void hpssFrame();            // a 192-sample HPSS frame is complete
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
    bool shortWindow_ = false;
    int hpN_=192, hpBins_=97, pvN_=384, base48_=7052, envelopeDelay_=207, closingRadius_=90;
    void initializeWindows();
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
    double olaHA_[kRing] = {};  // harmonic part for the analysis only (prominence mask); output paths keep olaH_/olaP_
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
    struct Track143 {
        unsigned id=0; bool used=false; int64_t last=0;
        double ola[kRing]={},hc[kHcRing]={}; Biquad band[3];
    };
    Track143 tracks143_[64];
    double* power143_=nullptr; int cap143_=0,rows143_=0; bool check143_=false,init143_=false;
    double request143_[kRing]={},requestHc143_[kHcRing]={},layerHc143_[kHcRing]={};
    Biquad layerBand143_[3];
    double sums143_[3]={},clockOffset143_=0.; int hop143_=0; uint64_t single143_=0,walsh143_=0;
    double singleDiff143_=0,singleT143_=0,walshError143_=0,reconstructionError143_=0,reconstructionPower143_=0;
    int maxTracks143_=0,overflow143_=0,unsupported143_=0;
    void host143(uint64_t mMax,uint64_t j0);

    Track tracks_[kMaxPeaks] = {};
    int nTracks_ = 0;
    OnePole envA_, envP_;
    double eps_ = 0, ifFloor_ = 0, pvAbs_ = 0, pvRel_ = 0, cPsi_[kKMax - 1] = {}, sPsi_[kKMax - 1] = {};

    // hpv52m: all state is fixed-size and owned by the module; no audio-thread allocations.
    struct Track52 {
        hrr3::State hrr3state;
        double f=0, phi=0, off[7]={}, fade=0, a=0;
        double aSyn105=0; // synthesis amplitude only; frozen while missing
        struct Phase41 {
            double c[7]={},s[7]={}; int n[7]={},bin[7]={},stable[7]={};
            bool found[7]={}; uint64_t last[7]={};
            bool pending43[7]={}; uint64_t until43[7]={}; int event43=0;
        } s41;
        double s32Gain=1; // independent render attenuation; nominal normalization stays original
        bool impactRecoveryPending=false;
        int steadyHops=0;               // hops of steady frequency and amplitude while unconfirmed
        bool guarded=false;             // held back by the fit guard in this hop
        double confF=0; int64_t confHop=-1000;  // frequency and hop when last confirmed (fade >= .5)
        int fitFailHops106=0; // consecutive observed fit failures; saturates at 13
        int confHops=0; bool inherited=false;   // hops confirmed so far; this track continues a long confirmed one
        // grains this track would have emitted while the guard held it (oldest first)
        double pend[kDeferHops][32]={}, pendNominal[kDeferHops]={}; int64_t pendCentre[kDeferHops]={}; int pendN=0;
        bool strong=false, fastEnding=false, handover103=false;
        uint32_t id=0, age=0;
        double dfdt=0, life=1, residual=-200, rawResidual=-200;
        int missing=0;
        double dadt=0;
        ModulationFit modulation;
        AmFamily52 family;
        HarmonicPermission permission[7];
        HarmonicPermission permission130[7];
        double amp130[5]={};int ampN130=0,ampPos130=0;int64_t ampStamp130=-1;

        prediction52::History prediction;
        trackprotection::State protection;  // frozen stable frequency over kick onset
        oscillator52::State oscillator;
        double envPeak=0; // largest harmonic envelope after the last render
        double r4Share=1; // share of the register corner and level (StageReentrySlow; 1 otherwise)
    };
    Track52 tr52_[12];
    int alt2Mode_=0;alt1::EqState alt2FlatEq_;
    int altFlags_=0;alt1::EqState altEq_;
    uint64_t altTracks_=0,altPartials_=0;
    bool age2sW2_=false,x35W2_=false;double* traceW2_=nullptr;
    int capacityW2_=0,countW2_=0;
    float features5_[80]={};
    bool comboLevel_=false,comboMedian_=true,comboNumeric_=true;
    combo1::State comboState_[6];double* comboTrace_=nullptr;int comboCap_=0,comboCount_=0;
    float comboDev_[6][10]={};  // developer detail only (see comboDev); never read by the audio path

    bool family2_=false;
    bool hrr3_=false;
    hrr3::Snapshot hrr3snapshot_[12];
    int hrr3count_=0;
    int gapStart2_=-1,gapEnd2_=-1; // Synthetic observation seam; disabled in dev.
    combo_family::Tracker families2_;
    Track52 voices2_[6];
    void familyFrame2();

    void captureTrack131(const Track52& tr,int state);
    double amplitude130(Track52& tr,double a);

    void obsTrack128(Track52& tr,bool count);
    bool candidates128() const {return mode128_==4 && peer128_ && peer128_->stamp128_==static_cast<int64_t>(i_);}

    unsigned s32HostFlags_=0, s32Flags_=0;
    int s41HostMode_=0,s41Mode_=0,s41LogCapacity_=0,s41LogCount_=0;
    double* s41Log_=nullptr;
    bool s43OnsetPrev_=false;
    unsigned s38HostFlags_=0,s38Flags_=0;
    int s38HostMode_=0,s38Mode_=0,s38TapeN_=0;
    const double* s38Tape_=nullptr;
    double s38Value_=0,s38LogGain_=0,s38Fast_=0,s38Slow_=0,s38PrevApv_=0;
    int s38OnsetLeft_=0; bool s38GainValid_=false;

    bool s32Profile_=false;
    double s32MaxA_=0, s32FocusHz_=0;
    int s32FocusLeft_=0;
    double s32RawSlow_[kHalfFft+1]={};
    void s32Focus52(const double* frequencies,const double* amplitudes,int count);
    double s32Gate52(Track52& track,bool observed);
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
    // confirmed tracks that ended recently (frequency, hop of the end)
    double grave52_[8]={}; int64_t graveHop52_[8]={}; int graveN52_=0; int64_t hop52_=0;
    // impact context and the tones playing when it began
    int impactCtx52_=0, preImpactN52_=0;
    int lowGridHold52_=0;  // hops left in the impact context that suspends the wider low grid
    double onsetBlend52_=1;  // share of the register-corner roll-off (StageOnsetProtect; 1 otherwise)
    int r4Hold52_=24; double r4Floor52_=0, r4TauUp52_=60;  // onset protection (setR4Research)
    double r4LevelDb52_=6;  // register level (setR4Level)
    double r4ReentryTau52_=250;  // return time constant, ms (setR4Reentry)
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
    StageInject52 inject_;
    TrackTape52* tape_=nullptr; int tapeMode_=0; int64_t tapeStart_=0, tapeEnd_=0; double tapeTol_=.03;
    void trackTape52();
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
    double* life147_=nullptr;int lifeCap147_=0,lifeN147_=0;
    void record147(const Track52& t,int state,int reason);
    void renderTrack52(Track52& t, const double src[2][256], const int ns[2], bool observed,
                       bool fast, int traceSlot, double* grain,double& agrain,alt2::NumericGrain* numeric=nullptr);
    void addGrain52(int64_t centre, const double* grain, double nominalAmplitude);
    void takeGrain52(int64_t index, double& sample, double& nominalAmplitude);
    void missingFrame52(int reason, bool fast);
    void grave52(const Track52& tr);   // remember a confirmed track that ended
    int nt52_=0, apkCount_=0, histCount_=0, holdCount_=0, holdPos_=0, onsetLeft_=0;
    double apk52_[56]={}, hist52_[11][8]={};
    int histN52_[11]={};
    double hold52_[28][190]={};
    double md52_[kRing]={}, md2_52_[kRing]={}, max52_[kRing]={}, polyT52_[kRing]={};
    double poly52_=1, percEnv52_=0, harmEnv52_=0;
    // Envelope and burst state (unused unless gen_ is set)
    GenResearch52 gen_;
    GenResearch52 genReq_;   // what setGenResearch / setGenEnvelope asked for; gen_ equals it except while resultantOn_
    // The reference path reads the voices directly and skips grain rendering.
    bool resultantOn_=false;
    bool resultantSet_=false;   // The reference renderer holds its preset until a profile switch.
    double genGain_=0, genFastE_=0, genSlowE_=0, lastFc_=60, lastGk_=0;
    int64_t genLastOnset_=-1000000;
    static constexpr int kBurstDelay=45; // 15 ms look-ahead for the burst amplitude, inside the hp read delay
    double genAmpRing_[kRing]={}, genPhaseRing_[kRing]={};
    bool genOnsetRing_[kRing]={};
    struct Burst { double amp=0, phi=0, f=60, w[7]={}; int64_t start=0; bool on=false; };
    Burst bursts_[2];
    double burstSample52(int64_t j);
    double xr52_[kHalfFft+1]={}, xi52_[kHalfFft+1]={};
    double polyXr52_[kHalfFft+1]={}, polyXi52_[kHalfFft+1]={}, bhCausal52_[kRing]={};  // polyphony analysis
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

}  // namespace pvb_combo1

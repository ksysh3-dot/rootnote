// PVB speaker engine - public interface.
//
// Signal chain (per channel, stereo interleaved float I/O):
//   input -> 4th-order high-pass (two Butterworth SVFs = LR4)
//         -> low-mid bell (220 Hz, +3 dB, Q 1 by default)
//         -> treble bell (4.5 kHz, -3 dB, Q 0.6 by default)
//         -> + virtual bass layer (experimental, off by default; pvb_vb.h): generated from the pre-EQ input; while an
//              algorithm with latency is on, the whole chain runs on the input delayed by that latency
//         -> output gain (-5 dB by default)
//         -> look-ahead true-peak limiter (-1 dBTP by default)
//   output = (mix * wet + (1 - mix) * bypass) * gate, where gate is the final output gate (blind-comparison mute and
//   headroom). The gate sits after the dry/wet mix, so a bypass (route change, "speaker only") can never let
//   unattenuated audio through while a comparison mutes. The bypass path is either
//     - dry: the input delayed by the same latency (P_FLAT = 0), or
//     - flat ("끌 때 음량 맞춤", P_FLAT = 1): the delayed input times the live loudness-match gain, through a second
//       true-peak limiter with the same ceiling and latency. The processed chain keeps running unheard meanwhile, so
//       the match (LoudnessMatcher in pvb_dsp.h: processed output vs input, ~10 s average) stays current.
//
// Threading: setParams()/setSampleRate()/readMeters() may be called from any thread.
// process()/processInt16() must be called from one audio thread only. The audio thread never
// blocks: new parameters are picked up with try_lock at the start of a block.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once
#include "pvb_layer_cap.h"

#include <atomic>
#include <cstdint>
#include <mutex>
#include <vector>

#include "pvb_analysis.h"
#include "pvb_stable.h"
#include "pvb_stable_peak.h"
#include "pvb_dsp.h"
#include "pvb_vb.h"
#include "pvb_xtc.h"
#include "pvb_layer_peak42.h"
#include "pvb_dry_peak44.h"
#include "pvb_bounded_peak50.h"

namespace pvb {

struct AnalysisState;  // pvb_analysis.cpp

// Order of the parameter array passed to setParams(). Keep in sync with PvbEngine.kt.
enum Param : int {
    P_ENABLED = 0,  // 1 = processed, 0 = bypass (crossfade, 50 ms)
    P_HP_HZ,        // high-pass corner (LR4)
    P_LOW_HZ,       // low-mid bell
    P_LOW_DB,
    P_LOW_Q,
    P_HI_HZ,        // treble bell
    P_HI_DB,
    P_HI_Q,
    P_OUT_DB,       // output gain before the limiter
    P_CEIL_DB,      // limiter ceiling, dBTP
    P_REL_MS,       // limiter release
    P_RAMP_MS,      // glide time for this update (filters and gains)
    P_DYN_ON,         // dynamic low-mid (slow): more boost while the phone limiter has headroom (and,
                      // only if DOWN_MAX > 0, less on loud passages)
    P_DYN_REF_DB,     // reference level, as the phone limiter sees it (>200 Hz, sine-equivalent dBFS)
    P_DYN_DOWN_RATIO, // above the reference: dB of boost taken back per dB (phone limiter relief)
    P_DYN_DOWN_MAX_DB,
    P_DYN_UP_RATIO,   // below the reference: dB added per dB (equal-loudness, as the volume link)
    P_DYN_UP_MAX_DB,
    P_HS_HZ,          // treble tilt: high shelf corner
    P_HS_DB,          // treble tilt: gain above the corner (0 = off)
    P_GATE_DB,        // final output gate after the dry/wet mix, dB (0 = open; <= -90 = silent). Glides over RAMP_MS.
    P_TAG,            // opaque condition tag (integer); openMs() counts audible time per tag (blind comparison)
    P_VB_ON,          // virtual bass (experimental): 1 = the algorithm below is in the path (with its latency)
    P_VB_ALGO,        // stable native ID 6 (P1); 0-5/7-17 reserved in app
    P_VB_LEVEL_DB,    // layer level re the 'faithful' level, dB (-120..+12; the app offers -6..+9); <= -90 = layer
                      // silent (algorithm and latency stay)
    P_FLAT,           // 1 = the bypass path is 'flat' (input x loudness-match gain, limiter) instead of the plain input
    P_MATCH_HOLD,     // 1 = the loudness match keeps its value (blind comparison: other settings play meanwhile)
    P_MATCH_SEED_DB,  // loudness-match gain until the first measurement (the value saved last time), -30..+3 dB
    P_DIAGNOSTIC_SOLO, // generated layer monitor; ordinary full mix continues driving analysis/match/limiter
    // Retired X_* ABI slots. Stored/direct packets always sanitize these to zero.
    P_X_SMOOTH,       // reserved legacy slot; always 0
    P_X_RISE,         // reserved legacy slot; always 0
    P_X_S1M,          // reserved legacy slot; always 0
    P_X_DENSE,        // reserved legacy slot; always 0
    // Developer mode ("개발자 모드", general build). P_DEV_ON = 0: every P_D_* value is ignored and the output is
    // bit-identical to the engine without them. P_DEV_ON = 1 with every P_D_* at its default is bit-identical too: a
    // value only changes the processing while it differs from the model (DevVoicing in pvb_vb.h). The voicing acts on
    // P1 generator; P1+++ locks developer voicing OFF.
    // P_DEV_ON also caps the limiter ceiling at -1 dBTP; the limiter itself can never be bypassed.
    P_DEV_ON,
    P_DEV_METER,        // 1 = compute the developer-mode meters (copyDevMeters); display only, never changes the output
    P_D_BOUNDARY_HZ,    // generator input band, upper edge (LR4 low-pass; model 190 Hz)
    P_D_OUT_LO_HZ,      // output band, lower edge (4th-order Butterworth high-pass; model 150 Hz)
    P_D_OUT_HI_HZ,      // output band, upper edge (2nd-order Butterworth low-pass; model 600 Hz; >= 1.5 x lower edge)
    P_D_H2_DB,          // harmonic weight offsets re the model's table, dB: k = 2, 3, 4 and 5..8
    P_D_H3_DB,
    P_D_H4_DB,
    P_D_H5_DB,
    P_D_ROLLOFF_DB_OCT, // added to the sustained upper roll-off above 220 Hz (model 24 dB/oct), dB/oct
    P_D_SUST_DB,        // sustained (vocoder) path gain, dB
    P_D_PERC_DB,        // percussive (analytic) path gain, dB
    P_D_ATTACK_MS,      // P1-family track life attack (rounded to 16/3 ms hops; model 2 hops)
    P_D_RELEASE_MS,     // P1-family track life release (rounded to hops; model 6 hops = 32 ms)
    // Crosstalk cancellation ("공간감", pvb_xtc.h). P_XTC_MODE = 0: off and bit-identical to the engine without it.
    // It acts on the processed path only (the plain and the matched bypass stay unprocessed), first in the chain.
    P_XTC_MODE,         // 0 off, 1 centre safe (side only), 2 full; held upright: 3 mono, 4/5 mono split, low to L / R;
                        // 6/7 matched M/S widener for 1/2 (blind comparison only)
    P_XTC_STRENGTH_DB,  // loop gain g, dB (-6 gentle, -4.5 medium, -3 strong)
    P_XTC_DIST_CM,      // listening distance
    P_XTC_HAT_CM,       // head size as hat size (circumference), 57 = standard head
    P_XTC_SPACING_CM,   // speaker spacing in landscape (device value)
    P_XTC_LO_HZ,        // feedback band, first-order high-pass
    P_XTC_HI_HZ,        // feedback band, first-order low-pass
    P_XTC_BAL_LO_DB,    // speaker balance after the canceller: left louder by this, 400-1500 Hz (pvb_xtc.h)
    P_XTC_BAL_HI_DB,    // the same, 1.5-8 kHz
    // Developer mode, appended after the spatial block to keep the indices above stable. Speaker-floor scale of the
    // virtual-bass weight/gain table: notes are looked up at f / scale, so a phone whose speaker stops k times higher
    // than the S26 Ultra gives notes up to k x higher the layer the model gives the S26 Ultra's. 1 (and 0, so a
    // zero-filled array stays the model) = the model, bit-identical; 0.75..1.75. Needs P_DEV_ON like every P_D_*.
    P_D_TABLE_SCALE,
    P_P1PPP,          // S50 atomic frozen P1+++; default0, supported at48kHz only
    P_COUNT
};

// Order of the meter array filled by readMeters(). Keep in sync with PvbEngine.kt.
enum Meter : int {
    M_IN_PEAK_DB = 0,  // highest input sample since last read, dBFS
    M_OUT_PEAK_DB,     // highest output sample since last read, dBFS
    M_LIM_GR_DB,       // largest limiter gain reduction since last read, dB (>= 0)
    M_LOW_DB_NOW,      // low-mid bell gain currently applied (follows the glide), dB
    M_MIX,             // 0 = bypass, 1 = processed
    M_LOAD_PCT,        // processing time / audio time, %, smoothed
    M_SAMPLE_RATE,
    M_LATENCY,         // frames
    M_BLOCKS,          // processed blocks (wraps)
    M_NAN_EVENTS,      // blocks that contained non-finite samples
    M_EST_LEVEL_DB,    // loudest octave band of our output as the phone sees it (sine-equivalent), dBFS
    M_EST_GR_DB,       // estimated reduction the phone applies to the 250 Hz band (PhoneModel), dB
    M_DYN_DB,          // low-mid change from the dynamic stage right now, dB (+ adds, - takes back)
    M_DYN_LEVEL_DB,    // level the dynamic stage compares with its reference (>200 Hz, slow), dBFS; -120 = none yet
    M_VB,              // virtual bass in the signal path: 0 = none, 1 + VbAlgo
    M_MATCH_DB,        // loudness-match gain now (flat bypass = this much quieter or louder than the input), dB
    M_VB_SCENE,        // unvalidated research observation, 0 unknown, 1 steady, 2 transient, 3 complex
    M_VB_UNKNOWN_FRAMES,
    M_VB_STEADY_FRAMES,
    M_VB_TRANSIENT_FRAMES,
    M_VB_COMPLEX_FRAMES,
    M_VB_UPPER_BLEND,
    M_VB_UPPER_TARGET,
    M_VB_UPPER_TRANSITIONS,
    M_DIAGNOSTIC_SOLO_BLEND,
    M_DIAGNOSTIC_SOLO_EXTRA_GR_DB,
    M_LIM_ACTIVE_PCT,  // share of the last few seconds (3 s time constant) the limiter took off > 0.5 dB, %; not reset by reads
    M_P1PPP_STATE,    // 0 OFF,1 effective,2 unsupported rate,4 transition
    M_COUNT
};

void defaultParams(float* out);  // fills P_COUNT values

// Developer display: legacy fields + (generator-low, actual-layer) pairs, then 9 stage fields per bin, oldest first.
enum DevMeter : int {
    DM_F0 = 0,          // fundamental of the loudest held track, Hz (0 = none); held 0.15 s, then falls 30 dB/s
    DM_H2_DB,           // k = 2..8 at the output (output band, imposition gain, level and output gain applied), dBFS
    DM_H8_DB = DM_H2_DB + 6,
    DM_DRY_BAND_DB,     // processed music without the layer, 150-400 Hz band, sine-equivalent dBFS (50 ms)
    DM_LAYER_BAND_DB,   // layer alone, same band, dBFS
    DM_RING_COUNT,      // ring entries written so far (wraps at 1e6)
    DM_RING_BIN_MS,     // time per ring entry
    DM_GAIN,            // envelope-imposition gain of the sustained path
    DM_BOUNDARY_HZ,     // generator input edge in use
    DM_OUT_LO_HZ,
    DM_OUT_HI_HZ,
    DM_T2_F0,           // second and third held tracks (quieter), same layout as DM_F0 and DM_H2_DB..DM_H8_DB
    DM_T2_H2_DB,
    DM_T3_F0 = DM_T2_H2_DB + 7,
    DM_T3_H2_DB,
    DM_FIELDS = DM_T3_H2_DB + 7
};

class Engine {
public:
    explicit Engine(int sampleRate);
    ~Engine();

    void setSampleRate(int sampleRate);
    void setParams(const float* values, int count);
    // Atomic validation/enqueue; rejection leaves all pending and audio state unchanged.
    bool trySetParams(const float* values,int count);
    bool setP1pppPreset(bool enabled);
    int p1pppState()const{return p1pppPublished_.load(std::memory_order_relaxed);}
    void process(float* interleavedStereo, int frames);
    // Called once by service creation before handing this instance to audio/UI threads.
    bool loadStableWeights(const unsigned char* p,size_t n){return stable_.load(p,n);}
    uint64_t separatorTicks88_=0;
    void setControl88(bool en,unsigned modules,const float* frames,int n,int stride){vbAlpha2_.setControl88(en,modules,frames,n,stride);}
    void setFloor89(float e){vbAlpha2_.setFloor89(e);}
    void setEvents88(const double* events,int n){vbAlpha2_.setEvents88(events,n);}
    int stats88(double* out,int n)const {
        if(n<10)return 0;
        const auto& c=vbAlpha2_.stats88();
        const double v[10]={double(c.hops),double(c.injections),double(c.eventPreview),double(c.eventRelease),
            double(c.reviewKeep),double(c.reviewDrop),stable_.loaded()?1.:0.,double(separatorTicks88_),c.time,c.g};
        std::copy(v,v+10,out);return 10;
    }
    void setDiag88b(float* p,int n){vbAlpha2_.setDiag88b(p,n);}
    int stats88b(double* out,int n)const {
        if(n<10)return 0;
        const auto& c=vbAlpha2_.stats88();
        const double v[10]={double(c.injectionEvents),double(c.holdEvents),double(c.capacityOmissions),double(c.heldHops),double(c.holdHops),c.maxHoldMs,c.tokens,double(c.diagnosticCount),c.injectStart,c.nextRefill};
        std::copy(v,v+10,out);return 10;
    }
    ControlStream control91_;std::unique_ptr<ControlWorker> worker91_;
    bool stream91Enabled_=false,worker91Enabled_=false;int64_t stream91Samples_=0,stream91Origin_=0;
    bool loadControl91(const unsigned char* p,size_t n){return control91_.load(p,n);}
    bool setStream91(bool enabled,bool worker,int64_t origin){
        if(enabled && (!control91_.loaded() || stable_.loaded()))return false;
        if(worker91_)worker91_->stop();
        stream91Enabled_=enabled;worker91Enabled_=enabled && worker;stream91Origin_=origin;stream91Samples_=0;control91_.reset();
        if(enabled && worker){if(!worker91_)return false;worker91_->reset();worker91_->start();}
        vbAlpha2_.setStream91(enabled && !worker?&control91_:nullptr,enabled && worker?worker91_.get():nullptr,origin);return true;
    }
    bool loadWorker91(const unsigned char* p,size_t n){worker91_=std::make_unique<ControlWorker>();return worker91_->stream.load(p,n);}
    uint64_t stale91()const{return vbAlpha2_.stats88().staleHops;}
    // Service lifecycle only: no audio generation may be alive during prepare.
    bool prepareStageC(int mode,const unsigned char* data,size_t bytes,bool worker,bool telemetry,int sampleRate,bool familyP2=true);
    // Speaker guard of the fixed modes, dBFS; 0 = off. Any thread: the audio loop reads one atomic.
    void setLayerCapDb(float db){layerCapDb_.store(db,std::memory_order_relaxed);}
    // Fixed modes: accept EQ values other than the defaults (low-mid gain still no higher than the default).
    // Call before the parameters that carry them; checked when parameters are queued.
    void setFixedEqOpen(bool open){std::lock_guard<std::mutex> lock(mtx_);fixedEqOpen_=open;}
    // Host check only: turn the s104 handover on in another mode after prepareStageC. Audio must be stopped.
    void setHandoverHost(bool on);
    // Host check only: turn the s107 FT3M fade inertia and layer trim on in another mode after prepareStageC.
    void setFadeTrimHost(bool on);
    // Host check only: turn the s110 CF375M fit relaxation and its layer trim on or off after prepareStageC.
    void setFitRelaxHost(bool on);
    uint64_t fitRelaxHops() const { return vbAlpha2_.fitRelaxHops(); }
    static constexpr int kStageCSize=2012;
    void copyStageC(int64_t* out)const;
    std::atomic<int> stageCMode_{0},stageCFlags_{0};
    bool stageCTelemetry_=false;uint64_t stageCLateBase_=0;
    std::atomic<uint64_t> stageCLate_{0},stageCSeparatorTicks_{0};


    void setSeparatorPeak70Research(bool on){separatorPeak70_=on;}
    void processSeparator70(float* z,const float* x,int n){separatorMix70_=x;process(z,n);separatorMix70_=nullptr;}

    void processInt16(const int16_t* in, int16_t* out, int frames);
    void readMeters(float* out, int count);
    // Detailed diagnostics: call only from the audio owner, immediately around process().
    static constexpr int kDiagnosticSamples = 32768;
    static constexpr int kDiagnosticFields = 32 + P_COUNT;
    void setDiagnosticCapture(bool enabled) { diagnosticCapture_ = enabled; }
    bool copyDiagnostic(float* generated, float* fullMix, int samples, float* trace, int fields) const;
    // Returns rows for the last captured callback; -1 unavailable, -2 capacity
    // exhausted (never silently truncated). Offset0 is relative to that callback.
    int copyHarmonicTrace(float* out, int capacity) const;
    // Developer-mode meters (P_DEV_METER on). Any thread; never blocks the audio thread. Fills
    // kDevFields values (DevMeter) then 2 x kDevRing ring values (dry low band, layer: 5 ms RMS as sine-equivalent
    // dBFS, oldest first). Returns the number of floats written, or 0 when out is too small.
    static constexpr int kDevFields = DM_FIELDS;
    static constexpr int kDevRing = 512;
    static constexpr int kDevStageFields = 9; // common, generator, requested, f0, reasons, fit dB, state, final GR, layer GR
    static constexpr int kDevMeterSize = kDevFields + (2 + kDevStageFields) * kDevRing;
    int copyDevMeters(float* out, int capacity) const;
    void setModulationResearch(int mode, bool tonalOnly=false) {
        for(VbHpv* m : {&vbAlpha2_}) m->setModulationResearch(mode,tonalOnly);
    }
    // Before processing, host only. Only profile 6 may apply these controls.
    bool setPhase41(int mode,double* trace,int capacity) { return vbAlpha2_.setPhase41(mode,trace,capacity); }
    int phase41Count() const { return vbAlpha2_.phase41Count(); }
    bool setN2Research(unsigned flags,int mode,double value,const double* tape,int count) { return vbAlpha2_.setN2Research(flags,mode,value,tape,count); }
    bool setP1WrongNoteResearch(unsigned flags) { return vbAlpha2_.setP1WrongNoteResearch(flags); }
    void setP1PlusResearch(unsigned flags) {
        vbAlpha2_.setP1PlusResearch(flags);
        if(vbCur_==VB_ALPHA2_P1) {
            vbDelay_=clampv(vbAlpha2_.latencyFrames(),0,kVbDelayLen-1);
            updateLatency();
        }
    }
    void setP1PPImpactResearch(int mode) { vbAlpha2_.setP1PPImpactResearch(mode); }
    void setP1PPV04Research(unsigned flags) {
        vbAlpha2_.setP1PPV04Research(flags);
        if(vbCur_==VB_ALPHA2_P1) {
            vbDelay_=clampv(vbAlpha2_.latencyFrames(),0,kVbDelayLen-1);
            updateLatency();
        }
    }
    void setP1PPResearchParams(int hold, double historyDb, int steadyHops, double steadyA, double releaseStrength) {
        vbAlpha2_.setP1PPResearchParams(hold, historyDb, steadyHops, steadyA, releaseStrength); }
    void setR4Research(int holdHops, double floorBlend, double tauUpMs) { vbAlpha2_.setR4Research(holdHops, floorBlend, tauUpMs); }
    void setR4Level(double gainDb) { vbAlpha2_.setR4Level(gainDb); }
    void setR4Reentry(double tauMs) { vbAlpha2_.setR4Reentry(tauMs); }
    // S30 host research; set before processing, no JNI/UI connection. Default off.
    // Two Butterworth sections form the fourth-order Linkwitz-Riley transfer.
    // Shelf Hz denotes its upper (pole) corner; DC gain is dryLowCutDb.
    bool setDryLowCutResearch(int dryLowCutMode, double dryLowCutHz, double dryLowCutDb);
    // S31 host-only, configure before processing. Default order4/gain1/cap0 preserves all old bits.
    bool setDryLowCutOrderResearch(int order);
    bool setLayerGainResearch(double requestedGain, double gainCap);
    // S34 host-only, set before processing. Disabled is exact legacy arithmetic.
    // blend is an offline certified interpolation toward P1, not a realtime TP guarantee.
    int copyPeak42Inputs(double* out,int capacity) const {
        const int n=std::min(capacity,peak42InputSamples_);
        std::copy_n(peak42Inputs_,n,out);return n;
    }
    bool setDryPeak44Research(int mode) {
        if(mode<0 || mode>2 || (mode && sr_!=48000))return false;
        dryPeak44Mode_=mode;dryPeak44_.reset();
        for(auto& a:sDryPeak44Eq_)for(auto& v:a)v.reset();
        for(auto& a:sDryPeak44Shelf_)for(auto& v:a)v.reset();
        if(mode){peak44P1_.configure(sr_);peak44P1_.setAlpha2Profile(VB_ALPHA2_P1);peak44P1_.bindEq(&hp_,&lo_,&hi_,&hs_,sr_);}
        return true;
    }
    int copyPeak50State(double* out,int cap)const {
        if(!out || cap<5)return 0;
        out[0]=dryPeak44_.peak();out[1]=dryPeak44_.alpha();out[2]=layerPeak42_.referencePeak();
        out[3]=layerPeak42_.gain();out[4]=boundedPeak50_.gain();return 5;
    }
    int copyPeak44Inputs(double* out,int cap)const {int n=std::min(cap,peak44InputSamples_);std::copy_n(peak44Inputs_,n,out);return n;}
    bool setLayerPeak42Research(int mode,double releaseMs) { return layerPeak42_.configure(mode,sr_,releaseMs); }
    bool setPeakBudgetResearch(int enabled, double cap, double ceilingDb,
                               double referenceOutDb, double releaseMs, double blend);

    // Host research (Resultant core, algorithm 15; docs/RESULTANT_CORE.md 4.2, 5.8). Not reachable from JNI.
    // v: up to ResultantCore::kParams values in the order of the spec (n may be shorter: the rest are the defaults); false = out of range, nothing
    // applied. Kept whichever algorithm runs. The trace holds 8 voice rows of 22 values per hop (allocated in enable).
    bool setResultantParams(const double* v, int n) { return vbAlpha2_.setResultantParams(v, n); }
    bool resultantTraceEnable(int hops) { return vbAlpha2_.resultantTraceEnable(hops); }
    int resultantTraceCopy(double* out, int capacity) const { return vbAlpha2_.resultantTraceCopy(out, capacity); }
    void setContinuityResearch(const ContinuityParams& p) {
        for(VbHpv* m : {&vbAlpha2_}) m->setContinuityResearch(p);
    }
    // Host-only study 1 (#4): counterfactual injection on the P1 research profile (ID 6) only.
    void setStageInject(const VbHpv::StageInject52& v) { vbAlpha2_.setStageInject(v); }
    void setTrackTape(VbHpv::TrackTape52* t,int mode,int64_t startHop,int64_t endHop,double tol) {
        vbAlpha2_.setTrackTape(t,mode,startHop,endHop,tol); }
    void setStageResearch(unsigned flags,StageCapture52::Sink sink=nullptr,void* user=nullptr) {
        for(VbHpv* m : {&vbAlpha2_}) m->setStageResearch(flags,sink,user);
        // P1 (ID 6) is the host research profile: allow an explicit stage probe
        // to compare greedy and global track assignment in the *same* engine.
        // Fixed app profiles (IDs 11-13) remain capture-only and unaffected.
        // The test harness attaches before the first audio block, while vbCur_
        // can still be -1. Consult the pending profile as well.
        const bool hostP1=vbCur_==VB_ALPHA2_P1 ||
            (hasPending_ && static_cast<int>(pending_[P_VB_ALGO])==VB_ALPHA2_P1);
        if(hostP1) vbAlpha2_.setStageResearch(flags,sink,user);
        else vbAlpha2_.setStageCapture(sink,user);
    }
    // Host research only (gen-s1s2): S1/S2 generator variants on the app profiles. Not reachable from JNI.
    // While set (any field on), the app option P_X_S1M no longer changes the generator (its -2 dB trim still applies).
    void setGenResearch(const GenResearch52& g) {
        for(VbHpv* m : {&vbAlpha2_}) m->setGenResearch(g);
        genHost_ = g.envelope || g.bursts;
    }

    // Clears filter memory and delay lines at the next block and fades in over 50 ms (any thread).
    void requestReset() { resetRequested_.store(true, std::memory_order_release); }
    // Milliseconds of audio processed with the parameter set tagged `tag` while it was audible: the output gate
    // open (and settled), fully processed (not bypassed or crossfading) and the input not silent. Restarts at 0
    // whenever another tag becomes active; -1 if `tag` is not the active one. Any thread.
    int openMs(int tag) const;
    int latencyFrames() const { return latency_.load(std::memory_order_relaxed); }
    // Loudness-match gain in dB (see P_FLAT), and whether it comes from a measurement (else: the seed). Any thread.
    float matchDb() const { return mMatchDb_.load(std::memory_order_relaxed); }
    bool matchMeasured() const { return mMatchMeasured_.load(std::memory_order_relaxed); }
    int sampleRate() const { return srMeter_.load(std::memory_order_relaxed); }

    // Live spectrum analysis (pvb_analysis.cpp). Any thread except the audio thread; never blocks it.
    // Fills nPts points log-spaced from 20 Hz to 20 kHz (NaN where there is nothing to show) and
    // info (A_COUNT values, see AnaInfo). dtSeconds is the time since the previous call for the
    // display smoothing; < 0 measures it with the clock, a large value gives the raw values.
    // Returns nPts, or 0 for bad arguments.
    int analyze(float* inDb, float* outDb, float* diffDb, float* eqDb, int nPts, float* info, int nInfo,
                double dtSeconds);

private:
    friend struct Sum50TestAccess; // host boundary fixture, no production injection path
    bool validP1ppp(const float* p) const;
    void setP1pppControls(bool on);
    void queueP1ppp(const float* p);
    void commitP1ppp();
    void publishP1ppp();
    void configure(int sampleRate);
    void applyParams(const float* v, bool snap);
    void resetState();
    void publishFilters();
    int vbWanted() const;
    bool genWanted(int algo) const;   // S1m for this algorithm (P1 only)
    bool vbSwitchPending() const;     // algorithm or S1m differs from what runs
    void vbApply(int algo, bool force);
    void updateLatency();
    void applyDev(const float* v);
    static void storeMax(std::atomic<float>& a, float v);

    // Pending updates, guarded by mtx_.
    std::mutex mtx_;
    bool fixedEqOpen_ = false;  // guarded by mtx_
    float pending_[P_COUNT] = {};
    bool hasPending_ = false;
    int pendingSr_ = 0;
    // P2 uses a bounded atomic snapshot. Writers retain mtx_; the audio owner never takes it.
    static_assert(std::atomic<float>::is_always_lock_free && std::atomic<uint32_t>::is_always_lock_free,
                  "P2 parameter snapshots require lock-free 32-bit atomics");
    bool p2SettingsRoute_=false;
    std::atomic<uint32_t> p2Seq_{0},p2ParamTicket_{0},p2RateTicket_{0};
    std::atomic<float> p2Params_[P_COUNT]{};
    std::atomic<int> p2Rate_{0};
    uint32_t p2SeenSeq_=0,p2SeenParams_=0,p2SeenRate_=0;
    void publishP2Settings(bool params,bool rate); // mtx_ held; sequentially consistent payload and sequence.
    bool readP2Settings(float* p,bool& has,int& rate); // one attempt, never spins.


    // Fixed diagnostic buffers; no allocation or locks in the audio callback.
    bool diagnosticCapture_ = false;
    int diagnosticSamples_ = 0;
    float diagnosticLayer_[kDiagnosticSamples] = {}, diagnosticFull_[kDiagnosticSamples] = {};
    float diagnosticTrace_[kDiagnosticFields] = {};
    float harmonicRows_[HarmonicTrace::kBlockRows * HarmonicTrace::kFields] = {};
    int harmonicCount_ = 0;
    bool harmonicOverflow_ = false;
    double layerDelayL_[TruePeakLimiter::kDelayLen] = {}, layerDelayR_[TruePeakLimiter::kDelayLen] = {};
    int layerPos_ = 0;

    // P1+++ mutations below belong exclusively to the audio owner.
    bool p1pppEffective_=false,processed_=false,p1pppQueued_=false;
    enum PppPhase { PPP_STEADY,PPP_FADE_OUT,PPP_HOLD,PPP_FADE_IN };
    PppPhase p1pppPhase_=PPP_STEADY;
    float p1pppNext_[P_COUNT]={};RampedValue p1pppFade_;int p1pppHold_=0;
    std::atomic<int> p1pppPublished_{0};BoundedPeak50 boundedPeak50_;
    std::atomic<float> layerCapDb_{0.f};float layerCapActiveDb_=0.f;LayerCap layerCap_;

    StableSeparator stable_;
    bool stableEffective_=false,stableNeedsPrime_=false,stablePriming_=false;
    bool separatorPeak70_=false;const float* separatorMix70_=nullptr;
    SvfState separatorEq70_[2][5];double separatorDelay70_[2][16384]{};int separatorPos70_=0;
    int stablePrimeRemaining_=0;
    void primeStable(int physicalFrames);
    // Audio-thread state.
    int sr_ = 48000;
    float active_[P_COUNT] = {};
    RampedSvf hp_, lo_, hi_, hs_;
    SvfState sHp1_[2], sHp2_[2], sLo_[2], sHi_[2], sHs_[2];
    RampedValue outGain_, mix_, fade_, lowDbNow_;
    int dryLowCutMode_ = 0;
    double dryLowCutHz_ = 80.0, dryLowCutDb_ = -6.0;
    int dryLowCutOrder_ = 4;
    double researchLayerGain_ = 1.0, researchLayerGainCap_ = 0.0;
    static constexpr double kFt3mTrim = 0.9816349216172104; // 10^(-0.161/20), s107
    static constexpr double kCf375mTrim = 0.9305291874902555; // 10^(-0.161/20) * 10^(-0.4644/20), s110
    double layerTrim_ = 1.0;
    bool peakBudgetOn_ = false;
    double peakBudgetCap_ = 2.0, peakBudgetCeilingDb_ = -3.0;
    double peakBudgetReferenceOutDb_ = -5.0, peakBudgetReleaseMs_ = 80.0, peakBudgetBlend_ = 1.0;
    double peakBudgetDryEnv_ = 0.0, peakBudgetLayerEnv_ = 0.0;
    RampedSvf dryLowCut_[4];
    SvfState sDryLowCut_[2][4];
    void configureDryLowCut();
#if defined(PVB_HOST_RESEARCH)
    static constexpr int kResearchCaptureFrames=4096;
#else
    static constexpr int kResearchCaptureFrames=0;
#endif
    double peak42Inputs_[6*kResearchCaptureFrames+1]={};int peak42InputSamples_=0;
    ModeLayerPeak42 layerPeak42_;
    int dryPeak44Mode_=0;ModeDryPeak44 dryPeak44_;
    ModulationFitCache fitCache_;
    VbHpv peak44P1_{true,true,1};
    SvfState sDryPeak44Eq_[2][5],sDryPeak44Shelf_[2][4];
    double peak44Inputs_[5*kResearchCaptureFrames+1]={};int peak44InputSamples_=0;
    TruePeakLimiter lim_;
    TruePeakLimiter limSolo_; // parallel, same latency; protects an isolated layer that may exceed the sum
    RampedValue soloX_;
    bool soloRun_ = false;
    std::atomic<float> mSoloBlend_{0.f}, mSoloExtraMin_{1.f};
    static constexpr int kDryLen = TruePeakLimiter::kDelayLen;
    double dryL_[kDryLen] = {}, dryR_[kDryLen] = {};
    int dryPos_ = 0;
    PhoneModel phone_;
    // The phone model only feeds the estimate meters (M_EST_*, analysis): it runs while someone reads them. Readers
    // (readMeters, analyze) extend phoneUntil_ to a few seconds past the audio processed so far.
    std::atomic<uint64_t> phoneUntil_{0};
    bool phoneRun_ = false;
    void wantPhoneModel();
    bool matchRun_ = false;  // match_ runs while the matched ("flat") bypass is set

    // Virtual bass. Switching an algorithm on or off (or between algorithms) changes the latency: while the output is
    // audible the engine fades out (30 ms), switches, and - when the latency grows - stays silent for the extra
    // latency so the music continues where it stopped (no repeat), then fades in. Switching to less latency skips
    // that much music. While the output is silent (muted blind comparison, reset) the switch is immediate.
    enum VbPhase { VB_STEADY, VB_FADE_OUT, VB_HOLD, VB_FADE_IN };
    VbHpv vbAlpha2_{true, true, 1};
    // Sparse stable IDs. Only slot 6 is populated in Android/JNI builds.
    VbModule* vbMods_[VB_ALGO_COUNT] = {nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,&vbAlpha2_,
        nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,
#if defined(PVB_HOST_RESULTANT_REFERENCE)
        &vbAlpha2_,
#else
        nullptr,
#endif
        nullptr};
    bool vbOk_[VB_ALGO_COUNT] = {};   // available at the current rate
    int vbCur_ = -1;                  // algorithm in the signal path, -1 = none
    bool genCur_ = false;             // S1m running in vbAlpha2_ (P1 only); switched like an algorithm (faded)
    bool genHost_ = false;            // host research hook set (setGenResearch): leave vbAlpha2_'s GenResearch52 alone
    Xtc xtc_;                         // crosstalk cancellation (P_XTC_*), first in the processed path
    int vbDelay_ = 0;                 // frames the chain's input is delayed by while vbCur_ >= 0
    VbPhase vbPhase_ = VB_STEADY;
    int vbHold_ = 0;
    RampedValue vbX_;                 // switching fade of the whole output
    RampedValue vbGain_;              // layer level
    // HQ centered HPSS needs 8332 module frames at 48 kHz. Keep the
    // dry/layer alignment exact instead of silently clipping it to 8191.
    static constexpr int kVbDelayLen = 16384;
    float vbDL_[kVbDelayLen] = {}, vbDR_[kVbDelayLen] = {};
    int vbPos_ = 0;
    std::atomic<int> mVb_{0};

    // Flat bypass and its loudness match (see the signal chain above).
    LoudnessMatcher match_;
    TruePeakLimiter limFlat_;
    RampedValue flatX_;      // 0 = the bypass path is the plain input, 1 = flat
    bool flatRun_ = false;   // limFlat_ is running (it is reset whenever it starts)
    std::atomic<float> mMatchDb_{-6.f};
    std::atomic<bool> mMatchMeasured_{false};

    RampedValue gate_;     // final output gate (after the dry/wet mix)
    double gateTarget_ = 1.0;
    int tag_ = 0;
    uint64_t openFrames_ = 0;
    std::atomic<int> tagPub_{0};
    std::atomic<uint64_t> openFramesPub_{0};
    // Dynamic low-mid: feed-forward level detector on the input (>200 Hz, rise 0.5 s, fall 1 s).
    static constexpr int kDynStep = 64;  // frames between gain updates; each update glides over the step
    RampedSvf dynHp_;
    SvfState sDyn_[2];
    double dynEnv_ = 0.0, dynEnvCoef_ = 0.0, dynRise_ = 0.0, dynFall_ = 0.0, dynOff_ = 0.0;
    double dynDb_ = 0.0;  // slow level in dB
    bool dynHave_ = false;
    int dynCount_ = 0;
    std::atomic<float> mDyn_{0.f};
    std::atomic<float> mDynLevel_{-120.f};
    double loadEma_ = 0.0;
    std::vector<float> scratch_;

    // Developer mode: voicing last pushed to the modules, and the display meters (audio thread writes, any reads).
    DevVoicing devApplied_;
    bool devMeterOn_ = false;
    void resetDevTelemetry();
    SvfState devCommonState_[4],devSourceState_[4];
    float devInputDelay_[2][16384]{};
    struct DevDecision {float f=0,reason=0,fit=0,state=0;};
    DevDecision devDecisionQueue_[16384]{};
    DevDecision devDecision_;
    uint64_t devSample_=0;
    double devStagePower_[3]{};
    float devBinFinalGr_=0,devBinLayerGr_=0;
    std::atomic<float> devStages_[kDevRing][kDevStageFields]{};

    // devLp_: 8th-order Butterworth low-pass at the generator edge (4 sections): the display's source-bass line, steep
    // enough that piano or vocals at 250-400 Hz do not read as bass the generator could use.
    static constexpr int kDevLpSections = 4;
    RampedSvf devLp_[kDevLpSections], devBp_;
    SvfState sDevLp_[kDevLpSections], sDevBpDry_, sDevBpLay_;
    double devBinDry_ = 0, devBinLay_ = 0, devPowDry_ = 0, devPowLay_ = 0, devPowCoef_ = 0;
    int devBinLen_ = 240, devBinN_ = 0;
    uint32_t devRingCount_ = 0;
    std::atomic<float> devFields_[kDevFields];
    // Developer display only: the held tracks behind DM_F0 / DM_T2_* / DM_T3_* (hold, then fall; audio time).
    struct DevSlot { double f = 0; double db[7] = {}; double hold = 0; };
    DevSlot devSlots_[DevHarmonics::kTracks];
    void devUpdateSlots(const DevHarmonics& h, bool have, double level, double blockS);
    std::atomic<float> devRingDry_[kDevRing], devRingLay_[kDevRing];
    std::atomic<uint32_t> devRingPub_{0};

    // Meters (written by the audio thread, read anywhere).
    std::atomic<float> mInPeak_{0.f}, mOutPeak_{0.f}, mLimMin_{1.f};
    std::atomic<float> mLowDb_{0.f}, mMix_{0.f}, mLoad_{0.f}, mEstLevel_{-120.f}, mEstGr_{0.f};
    std::atomic<int> mVbScene_{VB_SCENE_UNKNOWN};
    std::atomic<float> mVbSceneFrames_[4] = {};
    std::atomic<float> mVbUpperBlend_{0.f}, mVbUpperTarget_{0.f}, mVbUpperTransitions_{0.f};
    std::atomic<int> latency_{0};
    std::atomic<int> srMeter_{48000};
    std::atomic<bool> resetRequested_{false};
    std::atomic<uint32_t> mBlocks_{0}, mNan_{0};
    double limActive_ = 0.0;                    // audio thread: M_LIM_ACTIVE_PCT state, 0..1
    std::atomic<float> mLimActive_{0.f};        // its published value, %

    // Analysis tap: a single-producer ring the reader never blocks. Before writing a block the audio thread
    // announces its end in tapWriteEnd_ (then a release fence); it writes frame t at index t % kAnaRing with
    // relaxed atomic stores and publishes the block in tapFrames_ (release). The reader copies frames older than
    // tapFrames_, then (acquire fence) re-reads tapWriteEnd_: if the writer may have reached any frame it copied,
    // the copy is dropped (late analysis loses a frame; it never reads a half-overwritten window). The elements
    // are atomics, so a concurrent read and write is not a data race; relaxed atomic floats compile to plain
    // loads and stores.
    std::atomic<float> tapIn_[kAnaRing * 2];
    std::atomic<float> tapOut_[kAnaRing * 2];
    std::atomic<uint64_t> tapFrames_{0};
    std::atomic<uint64_t> tapWriteEnd_{0};
    std::atomic<float> anaLimMin_{1.f};
    // Filter coefficients in use (hp, low, high: g k m0 m1 m2 each), output gain (linear), mix,
    // low-mid gain (dB); written by the audio thread under a sequence counter.
    // hp lo hi (5 each), out gain, mix, low dB, high shelf (5), bypass gain dB, dry low shelf sections in use,
    // then up to four dry low shelf sections (5 each; fixed modes only)
    static constexpr int kPubCount = 45;
    std::atomic<double> pub_[kPubCount];
    std::atomic<uint32_t> pubSeq_{0};
    std::mutex anaMtx_;
    AnalysisState* ana_ = nullptr;  // created by the first analyze() call, deleted in ~Engine()
};

// Measured static gain reduction of the phone's processor for a sine at levelDb (stepped 1 kHz sines).
double estimatePhoneLimiterGr(double levelDb);

}  // namespace pvb

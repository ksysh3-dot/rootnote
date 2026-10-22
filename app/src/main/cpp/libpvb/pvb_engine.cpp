// PVB speaker engine - implementation. See pvb_engine.h for the signal chain and threading rules.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include "pvb_engine.h"

#include <chrono>
#include <climits>

#if defined(__SSE2__) || defined(_M_X64)
#include <xmmintrin.h>
#endif

namespace pvb {

namespace {

constexpr double kButterworthQ = 0.70710678118654752;
constexpr double kLookaheadMs = 1.5;
constexpr double kBypassFadeS = 0.05;   // enable / bypass crossfade
constexpr double kRecoverFadeS = 0.05;  // fade-in after a reset caused by bad samples
constexpr double kDynHoldBelowDb = -60.0;  // dynamic low-mid holds its value below this level
constexpr double kSilentGainLin = 1e-4;    // output gain at or below -80 dB: filter changes are applied at once
constexpr double kGateOffDb = -90.0;       // gate at or below this: exact silence
constexpr double kOpenMinLin = 1e-3;       // gate above -60 dB counts as audible (openMs)
constexpr double kOpenInputPeak = 1e-4;    // a block whose input peak is below -80 dBFS does not count as heard
constexpr double kVbFadeS = 0.03;          // virtual bass switching fade (out and in)
// S1m: fixed layer trim. Offline S1m matched each song's layer 220-400 Hz p99 to P1 (-1.58, -3.04, -1.36 dB on the
// three gate songs, GEN_S1S2_20261022.md); the app cannot measure per song, so it uses their mean, -2 dB.
constexpr double kS1mTrimDb = -2.0;

// Flush denormals to zero for the duration of a block (restored afterwards).
struct DenormalScope {
#if defined(__aarch64__)
    uint64_t old = 0;
    DenormalScope() {
        __asm__ __volatile__("mrs %0, fpcr" : "=r"(old));
        __asm__ __volatile__("msr fpcr, %0" : : "r"(old | (1ull << 24)));
    }
    ~DenormalScope() { __asm__ __volatile__("msr fpcr, %0" : : "r"(old)); }
#elif defined(__SSE2__) || defined(_M_X64)
    unsigned int old = 0;
    DenormalScope() {
        old = _mm_getcsr();
        _mm_setcsr(old | 0x8040u);  // FTZ | DAZ
    }
    ~DenormalScope() { _mm_setcsr(old); }
#else
    DenormalScope() {}
#endif
};

void sanitizeParams(float* v) {
    float d[P_COUNT];
    defaultParams(d);
    for (int i = 0; i < P_COUNT; ++i)
        if (!isFiniteBits(v[i])) v[i] = d[i];
    v[P_ENABLED] = v[P_ENABLED] >= 0.5f ? 1.f : 0.f;
    v[P_HP_HZ] = clampv(v[P_HP_HZ], 10.f, 400.f);
    v[P_LOW_HZ] = clampv(v[P_LOW_HZ], 40.f, 2000.f);
    v[P_LOW_DB] = clampv(v[P_LOW_DB], -15.f, 15.f);
    v[P_LOW_Q] = clampv(v[P_LOW_Q], 0.1f, 10.f);
    v[P_HI_HZ] = clampv(v[P_HI_HZ], 500.f, 20000.f);
    v[P_HI_DB] = clampv(v[P_HI_DB], -15.f, 15.f);
    v[P_HI_Q] = clampv(v[P_HI_Q], 0.1f, 10.f);
    v[P_OUT_DB] = clampv(v[P_OUT_DB], -90.f, 12.f);   // down to -90: the blind comparison mutes with it
    v[P_CEIL_DB] = clampv(v[P_CEIL_DB], -20.f, 0.f);
    v[P_REL_MS] = clampv(v[P_REL_MS], 1.f, 5000.f);
    v[P_RAMP_MS] = clampv(v[P_RAMP_MS], 0.f, 5000.f);
    v[P_DYN_ON] = v[P_DYN_ON] >= 0.5f ? 1.f : 0.f;
    v[P_DYN_REF_DB] = clampv(v[P_DYN_REF_DB], -50.f, 0.f);
    v[P_DYN_DOWN_RATIO] = clampv(v[P_DYN_DOWN_RATIO], 0.f, 2.f);
    v[P_DYN_DOWN_MAX_DB] = clampv(v[P_DYN_DOWN_MAX_DB], 0.f, 12.f);
    v[P_DYN_UP_RATIO] = clampv(v[P_DYN_UP_RATIO], 0.f, 1.f);
    v[P_DYN_UP_MAX_DB] = clampv(v[P_DYN_UP_MAX_DB], 0.f, 6.f);
    v[P_HS_HZ] = clampv(v[P_HS_HZ], 500.f, 12000.f);
    v[P_HS_DB] = clampv(v[P_HS_DB], -15.f, 15.f);
    v[P_GATE_DB] = clampv(v[P_GATE_DB], -120.f, 0.f);
    v[P_TAG] = std::nearbyint(clampv(v[P_TAG], 0.f, 1.0e7f));
    v[P_VB_ON] = v[P_VB_ON] >= 0.5f ? 1.f : 0.f;
    v[P_VB_ALGO] = clampv(std::nearbyint(v[P_VB_ALGO]), 0.f, static_cast<float>(VB_ALGO_COUNT - 1));
    v[P_VB_LEVEL_DB] = clampv(v[P_VB_LEVEL_DB], -120.f, 12.f);
    v[P_DIAGNOSTIC_SOLO] = v[P_DIAGNOSTIC_SOLO] >= 0.5f ? 1.f : 0.f;
    v[P_FLAT] = v[P_FLAT] >= 0.5f ? 1.f : 0.f;
    v[P_MATCH_HOLD] = v[P_MATCH_HOLD] >= 0.5f ? 1.f : 0.f;
    v[P_MATCH_SEED_DB] = clampv(v[P_MATCH_SEED_DB], static_cast<float>(LoudnessMatcher::kMinDb),
                                static_cast<float>(LoudnessMatcher::kMaxDb));
    for (int i : {P_X_SMOOTH, P_X_RISE, P_X_S1M, P_X_DENSE}) v[i] = v[i] >= 0.5f ? 1.f : 0.f;
    // Developer mode: hard engine limits (the app's sliders stay inside them).
    v[P_DEV_ON] = v[P_DEV_ON] >= 0.5f ? 1.f : 0.f;
    v[P_DEV_METER] = v[P_DEV_METER] >= 0.5f ? 1.f : 0.f;
    v[P_D_BOUNDARY_HZ] = clampv(v[P_D_BOUNDARY_HZ], 80.f, 220.f);
    v[P_D_OUT_LO_HZ] = clampv(v[P_D_OUT_LO_HZ], 60.f, 300.f);
    v[P_D_OUT_HI_HZ] = std::max(clampv(v[P_D_OUT_HI_HZ], 250.f, 1200.f), 1.5f * v[P_D_OUT_LO_HZ]);
    for (int i : {P_D_H2_DB, P_D_H3_DB, P_D_H4_DB, P_D_H5_DB}) v[i] = clampv(v[i], -24.f, 12.f);
    v[P_D_ROLLOFF_DB_OCT] = clampv(v[P_D_ROLLOFF_DB_OCT], -24.f, 24.f);
    v[P_D_SUST_DB] = clampv(v[P_D_SUST_DB], -24.f, 12.f);
    v[P_D_PERC_DB] = clampv(v[P_D_PERC_DB], -24.f, 12.f);
    v[P_D_ATTACK_MS] = clampv(v[P_D_ATTACK_MS], 1.f, 200.f);
    v[P_D_RELEASE_MS] = clampv(v[P_D_RELEASE_MS], 1.f, 1000.f);
    // The output ceiling stays at or below -1 dBTP while developer values are in use.
    if (v[P_DEV_ON] >= 0.5f) v[P_CEIL_DB] = std::min(v[P_CEIL_DB], -1.f);
}

// Developer mode: milliseconds to 16/3000 s continuity hops (at least one).
int msToHops(float ms) { return std::max(1, static_cast<int>(std::lround(ms * 3.0 / 16.0))); }

void storeMin(std::atomic<float>& a, float v) {
    float cur = a.load(std::memory_order_relaxed);
    while (v < cur && !a.compare_exchange_weak(cur, v, std::memory_order_relaxed)) {
    }
}

float dbOrFloor(double lin) {
    return static_cast<float>(std::max(-120.0, linToDb(lin)));
}

}  // namespace

void defaultParams(float* v) {
    v[P_ENABLED] = 1.f;
    v[P_HP_HZ] = 100.f;
    v[P_LOW_HZ] = 220.f;
    v[P_LOW_DB] = 3.f;
    v[P_LOW_Q] = 1.f;
    v[P_HI_HZ] = 4500.f;
    v[P_HI_DB] = -3.f;
    v[P_HI_Q] = 0.6f;
    v[P_OUT_DB] = -5.f;
    v[P_CEIL_DB] = -1.f;
    v[P_REL_MS] = 60.f;
    v[P_RAMP_MS] = 20.f;
    v[P_DYN_ON] = 0.f;
    v[P_DYN_REF_DB] = -30.f;      // 3 dB below where the phone limiter starts (-27 dBFS)
    v[P_DYN_DOWN_RATIO] = 0.5f;
    v[P_DYN_DOWN_MAX_DB] = 0.f;   // taking boost back on loud passages: off (album study: loses more bass than it saves)
    v[P_DYN_UP_RATIO] = 0.19f;
    v[P_DYN_UP_MAX_DB] = 2.f;
    v[P_HS_HZ] = 2500.f;
    v[P_HS_DB] = 0.f;            // treble tilt off (EQ v1.1)
    v[P_GATE_DB] = 0.f;          // output gate open
    v[P_TAG] = 0.f;
    v[P_VB_ON] = 0.f;            // virtual bass: off (experimental)
    v[P_VB_ALGO] = 0.f;          // hpv
    v[P_VB_LEVEL_DB] = 0.f;      // 'faithful' level
    v[P_FLAT] = 0.f;             // bypass = the plain input
    v[P_MATCH_HOLD] = 0.f;
    v[P_DIAGNOSTIC_SOLO] = 0.f;
    v[P_MATCH_SEED_DB] = -6.f;   // album average for EQ v1.1 (-6.2 dB, 23 tracks)
    v[P_X_SMOOTH] = 0.f;         // experimental layer options: off
    v[P_X_RISE] = 0.f;
    v[P_X_S1M] = 0.f;
    v[P_X_DENSE] = 0.f;
    v[P_DEV_ON] = 0.f;           // developer mode: off, and every value at the model's own
    v[P_DEV_METER] = 0.f;
    v[P_D_BOUNDARY_HZ] = static_cast<float>(DevVoicing::kBoundaryHz);
    v[P_D_OUT_LO_HZ] = static_cast<float>(DevVoicing::kOutLoHz);
    v[P_D_OUT_HI_HZ] = static_cast<float>(DevVoicing::kOutHiHz);
    v[P_D_H2_DB] = v[P_D_H3_DB] = v[P_D_H4_DB] = v[P_D_H5_DB] = 0.f;
    v[P_D_ROLLOFF_DB_OCT] = 0.f;
    v[P_D_SUST_DB] = v[P_D_PERC_DB] = 0.f;
    v[P_D_ATTACK_MS] = 32.f / 3.f;   // 2 hops
    v[P_D_RELEASE_MS] = 32.f;        // 6 hops
}

double estimatePhoneLimiterGr(double levelDb) { return PhoneModel::staticGr(levelDb); }

void Engine::storeMax(std::atomic<float>& a, float v) {
    float cur = a.load(std::memory_order_relaxed);
    while (v > cur && !a.compare_exchange_weak(cur, v, std::memory_order_relaxed)) {
    }
}

Engine::Engine(int sampleRate) {
    for (auto& v : pub_) v.store(0.0, std::memory_order_relaxed);
    for (auto& v : tapIn_) v.store(0.f, std::memory_order_relaxed);
    for (auto& v : tapOut_) v.store(0.f, std::memory_order_relaxed);
    for (auto& v : devFields_) v.store(0.f, std::memory_order_relaxed);
    for (auto& v : devRingDry_) v.store(-120.f, std::memory_order_relaxed);
    for (auto& v : devRingLay_) v.store(-120.f, std::memory_order_relaxed);
    gate_.snap(1.0);
    vbX_.snap(1.0);
    vbGain_.snap(1.0);
    flatX_.snap(0.0);
    soloX_.snap(0.0);
    defaultParams(active_);
    defaultParams(pending_);
    scratch_.reserve(16384);
    configure(sampleRate);
}

void Engine::setSampleRate(int sampleRate) {
    std::lock_guard<std::mutex> lock(mtx_);
    pendingSr_ = sampleRate;
}

void Engine::setParams(const float* values, int count) {
    if (values == nullptr || count <= 0) return;
    std::lock_guard<std::mutex> lock(mtx_);
    const int n = count < P_COUNT ? count : static_cast<int>(P_COUNT);
    for (int i = 0; i < n; ++i) pending_[i] = values[i];
    sanitizeParams(pending_);
    hasPending_ = true;
}

int Engine::vbWanted() const {
    if (active_[P_VB_ON] < 0.5f) return -1;
    const int a = static_cast<int>(active_[P_VB_ALGO]);
    return (a >= 0 && a < VB_ALGO_COUNT && vbOk_[a]) ? a : -1;
}

bool Engine::genWanted(int algo) const {
    return algo == VB_ALPHA2_P1 && active_[P_X_S1M] >= 0.5f;
}

// Experimental layer options: only while a virtual bass algorithm is in the path (they blend out otherwise).
void Engine::updateCondWanted() {
    const bool vb = vbCur_ >= 0;
    cond_.setWanted(vb && active_[P_X_SMOOTH] >= 0.5f, vb && active_[P_X_RISE] >= 0.5f, vb && active_[P_X_DENSE] >= 0.5f);
}

bool Engine::vbSwitchPending() const {
    const int w = vbWanted();
    return w != vbCur_ || (w >= 0 && genWanted(w) != genCur_);
}

void Engine::updateLatency() {
    latency_.store(lim_.latency() + (vbCur_ >= 0 ? vbDelay_ : 0), std::memory_order_relaxed);
}

void Engine::vbApply(int algo, bool force) {
    const bool gen = algo >= 0 && genWanted(algo);
    if (algo == vbCur_ && gen == genCur_ && !force) return;
    vbCur_ = algo;
    // vbAlpha2_ serves all five Alpha2 profiles: the S1m envelope is set (or cleared) before the profile resets it.
    genCur_ = gen;
    // Host research (setGenResearch) keeps its own GenResearch52; the app option never overrides it.
    if (!genHost_) vbAlpha2_.setGenEnvelope(gen);
    cond_.clearDetectors();
    updateCondWanted();
    if (algo >= VB_ALPHA2_P1) vbAlpha2_.setAlpha2Profile(algo);
    else if (algo >= 0) vbMods_[algo]->reset();
    vbDelay_ = algo >= 0 ? clampv(vbMods_[algo]->latencyFrames(), 0, kVbDelayLen - 1) : 0;
    mVb_.store(algo + 1, std::memory_order_relaxed);
    updateLatency();
}

// Developer mode: voicing to the hpv52m-family modules (only when it changed) and the display meters. Audio thread.
void Engine::applyDev(const float* v) {
    DevVoicing d;
    if (v[P_DEV_ON] >= 0.5f) {
        d.boundaryHz = v[P_D_BOUNDARY_HZ];
        d.outLoHz = v[P_D_OUT_LO_HZ];
        d.outHiHz = v[P_D_OUT_HI_HZ];
        d.harmDb[0] = v[P_D_H2_DB]; d.harmDb[1] = v[P_D_H3_DB]; d.harmDb[2] = v[P_D_H4_DB]; d.harmDb[3] = v[P_D_H5_DB];
        d.rolloffOffset = v[P_D_ROLLOFF_DB_OCT];
        d.sustDb = v[P_D_SUST_DB];
        d.percDb = v[P_D_PERC_DB];
        d.attackHops = msToHops(v[P_D_ATTACK_MS]);
        d.releaseHops = msToHops(v[P_D_RELEASE_MS]);
    }
    if (d != devApplied_) {
        devApplied_ = d;
        for (VbHpv* m : {&vb52_, &vbGentle_, &vbGentleStrong_, &vbGentleAdaptive_, &vbAlpha2_}) m->setDev(d);
    }
    const bool meter = v[P_DEV_METER] >= 0.5f;
    if (meter != devMeterOn_) {
        devMeterOn_ = meter;
        for (VbModule* m : vbMods_) m->setDevMeter(meter);
        sDevLp_.reset(); sDevBpDry_.reset(); sDevBpLay_.reset();
        devBinDry_ = devBinLay_ = devPowDry_ = devPowLay_ = 0.0;
        devBinN_ = 0;
    }
    if (meter) {
        SvfCoef lp;
        lp.g = prewarp(sr_, d.boundaryHz);
        lp.k = std::sqrt(2.0);
        lp.m0 = 0.0; lp.m1 = 0.0; lp.m2 = 1.0;
        devLp_.snap(lp);
    }
}

void Engine::configure(int sampleRate) {
    sr_ = clampv(sampleRate, 8000, 192000);
    devBinLen_ = std::max(1, static_cast<int>(std::lround(0.005 * sr_)));
    devPowCoef_ = 1.0 - std::exp(-1.0 / (0.05 * sr_));
    devBp_.snap(svfBandpass(sr_, 245.0, 0.65));
    lim_.configure(sr_, kLookaheadMs);
    limSolo_.configure(sr_, kLookaheadMs);
    limFlat_.configure(sr_, kLookaheadMs);  // same latency as lim_: the flat path stays aligned with wet and dry
    match_.configure(sr_);
    cond_.configure(sr_);
    for (int a = 0; a < VB_ALGO_COUNT; ++a)
        vbOk_[a] = a > VB_ALPHA2_P1 ? vbOk_[VB_ALPHA2_P1] : vbMods_[a]->configure(sr_);
    vb52_.bindEq(&hp_, &lo_, &hi_, &hs_, sr_);
    vbGentle_.bindEq(&hp_, &lo_, &hi_, &hs_, sr_);
    vbGentleStrong_.bindEq(&hp_, &lo_, &hi_, &hs_, sr_);
    vbGentleAdaptive_.bindEq(&hp_, &lo_, &hi_, &hs_, sr_);
    vbAlpha2_.bindEq(&hp_, &lo_, &hi_, &hs_, sr_);
    srMeter_.store(sr_, std::memory_order_relaxed);
    phone_.configure(sr_);
    dynHp_.snap(svfHighpass(sr_, 200.0, kButterworthQ));
    // 50 ms mean square (like the phone limiter's view), then a slow follower in dB: rise 0.5 s, fall 1 s.
    dynEnvCoef_ = 1.0 - std::exp(-1.0 / (0.05 * sr_));
    dynRise_ = 1.0 - std::exp(-static_cast<double>(kDynStep) / (0.5 * sr_));
    dynFall_ = 1.0 - std::exp(-static_cast<double>(kDynStep) / (1.0 * sr_));
    applyParams(active_, true);
    resetState();
    vbApply(vbWanted(), true);  // the latency of an algorithm depends on the rate
    publishFilters();
}

void Engine::publishFilters() {
    // Sequence counter (odd while writing); readers retry until they see the same even value twice.
    const uint32_t s = pubSeq_.load(std::memory_order_relaxed);
    pubSeq_.store(s + 1, std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_release);
    const SvfCoef* f[4] = {&hp_.current(), &lo_.current(), &hi_.current(), &hs_.current()};
    int i = 0;
    for (int fi = 0; fi < 3; ++fi) {
        const SvfCoef* c = f[fi];
        pub_[i++].store(c->g, std::memory_order_relaxed);
        pub_[i++].store(c->k, std::memory_order_relaxed);
        pub_[i++].store(c->m0, std::memory_order_relaxed);
        pub_[i++].store(c->m1, std::memory_order_relaxed);
        pub_[i++].store(c->m2, std::memory_order_relaxed);
    }
    pub_[i++].store(outGain_.value(), std::memory_order_relaxed);
    pub_[i++].store(mix_.value(), std::memory_order_relaxed);
    pub_[i++].store(lowDbNow_.value() + dynOff_, std::memory_order_relaxed);
    pub_[i++].store(f[3]->g, std::memory_order_relaxed);
    pub_[i++].store(f[3]->k, std::memory_order_relaxed);
    pub_[i++].store(f[3]->m0, std::memory_order_relaxed);
    pub_[i++].store(f[3]->m1, std::memory_order_relaxed);
    pub_[i++].store(f[3]->m2, std::memory_order_relaxed);
    pub_[i++].store(flatX_.value() * match_.gainDb(), std::memory_order_relaxed);
    pubSeq_.store(s + 2, std::memory_order_release);
}

void Engine::resetState() {
    for (int c = 0; c < 2; ++c) {
        sHp1_[c].reset();
        sHp2_[c].reset();
        sLo_[c].reset();
        sHi_[c].reset();
        sHs_[c].reset();
        sDyn_[c].reset();
    }
    dynEnv_ = 0.0;
    dynOff_ = 0.0;
    dynDb_ = 0.0;
    dynHave_ = false;
    dynCount_ = 0;
    std::fill(std::begin(dryL_), std::end(dryL_), 0.0);
    std::fill(std::begin(dryR_), std::end(dryR_), 0.0);
    dryPos_ = 0;
    lim_.reset();
    limSolo_.reset();
    std::fill(std::begin(layerDelayL_), std::end(layerDelayL_), 0.0);
    std::fill(std::begin(layerDelayR_), std::end(layerDelayR_), 0.0);
    layerPos_ = 0;
    soloRun_ = false;
    soloX_.snap(soloX_.target());
    limFlat_.reset();
    flatRun_ = false;
    flatX_.snap(flatX_.target());
    match_.resetFilters();
    phone_.reset();
    fade_.snap(1.0);
    // virtual bass: forget old audio, finish a switch in progress at once
    std::fill(std::begin(vbDL_), std::end(vbDL_), 0.f);
    std::fill(std::begin(vbDR_), std::end(vbDR_), 0.f);
    vbPos_ = 0;
    vbPhase_ = VB_STEADY;
    vbX_.snap(1.0);
    if (vbCur_ >= 0) vbMods_[vbCur_]->reset();
    cond_.clearDetectors();
}

void Engine::applyParams(const float* v, bool snap) {
    bool monitorOnly = !snap && v[P_DIAGNOSTIC_SOLO] != active_[P_DIAGNOSTIC_SOLO];
    for (int i = 0; monitorOnly && i < P_COUNT; ++i)
        if (i != P_DIAGNOSTIC_SOLO && i != P_RAMP_MS && v[i] != active_[i]) monitorOnly = false;
    if (monitorOnly) {
        soloX_.setTarget(v[P_DIAGNOSTIC_SOLO] >= 0.5f ? 1.0 : 0.0, static_cast<int>(std::lround(0.1 * sr_)));
        active_[P_DIAGNOSTIC_SOLO] = v[P_DIAGNOSTIC_SOLO];
        return; // preserve in-flight EQ/output-gain ramps when only the listening monitor changes
    }
    const int ramp = snap ? 0 : static_cast<int>(std::lround(v[P_RAMP_MS] * 1e-3 * sr_));
    // While the output is practically silent (the blind comparison between two sounds), filter changes cannot be
    // heard: apply them at once, so the following fade-in never carries a glide from the previous setting.
    const bool silent = outGain_.value() <= kSilentGainLin || gate_.value() <= kSilentGainLin;
    const int filterRamp = silent ? 0 : ramp;
    hp_.setTarget(svfHighpass(sr_, v[P_HP_HZ], kButterworthQ), filterRamp);
    lo_.setTarget(svfBell(sr_, v[P_LOW_HZ], v[P_LOW_DB], v[P_LOW_Q]), filterRamp);
    hi_.setTarget(svfBell(sr_, v[P_HI_HZ], v[P_HI_DB], v[P_HI_Q]), filterRamp);
    hs_.setTarget(svfHighShelf(sr_, v[P_HS_HZ], v[P_HS_DB], kButterworthQ), filterRamp);
    outGain_.setTarget(dbToLin(v[P_OUT_DB]), ramp);
    lowDbNow_.setTarget(v[P_LOW_DB], filterRamp);
    gateTarget_ = v[P_GATE_DB] <= kGateOffDb ? 0.0 : dbToLin(v[P_GATE_DB]);
    if (snap) gate_.snap(gateTarget_);
    else if (gateTarget_ != gate_.target()) gate_.setTarget(gateTarget_, ramp);
    const double vbTarget = v[P_VB_LEVEL_DB] <= kGateOffDb ? 0.0 : dbToLin(v[P_VB_LEVEL_DB]);
    if (snap) vbGain_.snap(vbTarget);
    else if (vbTarget != vbGain_.target()) vbGain_.setTarget(vbTarget, filterRamp);
    const int tag = static_cast<int>(v[P_TAG]);
    if (tag != tag_) {
        // a new condition: its audible time starts from zero (published before the tag, see openMs)
        tag_ = tag;
        openFrames_ = 0;
        openFramesPub_.store(0, std::memory_order_release);
        tagPub_.store(tag, std::memory_order_release);
    }

    // Flat or plain bypass: switch at once while the bypass path is not heard (fully processed, e.g. a route change
    // that also bypasses), else crossfade like enable/bypass.
    const double flatTarget = v[P_FLAT] >= 0.5f ? 1.0 : 0.0;
    if (snap || (mix_.value() >= 1.0 && mix_.target() >= 1.0)) flatX_.snap(flatTarget);
    else if (flatTarget != flatX_.target()) flatX_.setTarget(flatTarget, static_cast<int>(std::lround(kBypassFadeS * sr_)));
    match_.setHold(v[P_MATCH_HOLD] >= 0.5f);
    match_.seed(v[P_MATCH_SEED_DB]);

    const double mixTarget = v[P_ENABLED] >= 0.5f ? 1.0 : 0.0;
    if (snap) mix_.snap(mixTarget);
    else if (mixTarget != mix_.target()) mix_.setTarget(mixTarget, static_cast<int>(std::lround(kBypassFadeS * sr_)));

    // Monitor switching must never reset generators or retune the full-mix sidechains.
    const double soloTarget = v[P_DIAGNOSTIC_SOLO] >= 0.5f ? 1.0 : 0.0;
    if (snap) soloX_.snap(soloTarget);
    else if (soloTarget != soloX_.target()) soloX_.setTarget(soloTarget, static_cast<int>(std::lround(0.1 * sr_)));
    limSolo_.setCeilingDb(v[P_CEIL_DB]);
    limSolo_.setReleaseMs(v[P_REL_MS]);
    lim_.setCeilingDb(v[P_CEIL_DB]);
    lim_.setReleaseMs(v[P_REL_MS]);
    limFlat_.setCeilingDb(v[P_CEIL_DB]);
    limFlat_.setReleaseMs(v[P_REL_MS]);
    for (int i = 0; i < P_COUNT; ++i) active_[i] = v[i];
    applyDev(v);
    if (snap) vbApply(vbWanted(), false);
}

void Engine::process(float* io, int frames) {
    if (io == nullptr || frames <= 0) return;
    const auto t0 = std::chrono::steady_clock::now();
    DenormalScope denormals;

    // Pick up new settings without ever blocking the audio thread.
    if (mtx_.try_lock()) {
        const int newSr = pendingSr_;
        pendingSr_ = 0;
        float p[P_COUNT];
        bool has = hasPending_;
        if (has) {
            std::memcpy(p, pending_, sizeof p);
            hasPending_ = false;
        }
        mtx_.unlock();

        if (newSr > 0 && newSr != sr_) {
            if (has) std::memcpy(active_, p, sizeof p);
            configure(newSr);  // snaps all values and clears the filter memory
            has = false;
        }
        if (has) applyParams(p, false);
    }

    // The engine was out of the signal path: forget old audio and fade in instead of jumping.
    if (resetRequested_.exchange(false, std::memory_order_acq_rel)) {
        resetState();
        fade_.snap(0.0);
        fade_.setTarget(1.0, static_cast<int>(std::lround(kRecoverFadeS * sr_)));
    }

    // Virtual bass on/off or another algorithm: switch now if nothing is audible, else fade out first.
    if (vbPhase_ == VB_STEADY && vbSwitchPending()) {
        const bool silent = gate_.value() <= kSilentGainLin || outGain_.value() <= kSilentGainLin || fade_.value() <= 0.0;
        if (silent) {
            vbApply(vbWanted(), false);
        } else {
            vbX_.setTarget(0.0, static_cast<int>(std::lround(kVbFadeS * sr_)));
            vbPhase_ = VB_FADE_OUT;
        }
    }

    double inPeak = 0.0, outPeak = 0.0;
    bool badInput = false, badOutput = false;
    const int lat = lim_.latency();
    const uint64_t tapBase = tapFrames_.load(std::memory_order_relaxed);  // only this thread writes it
    const bool capture = diagnosticCapture_ && frames <= kDiagnosticSamples / 2;
    diagnosticSamples_ = capture ? frames * 2 : 0;
    harmonicCount_=0; harmonicOverflow_=false;
    for(auto* module:vbMods_) module->setHarmonicCapture(capture);
    double powers[5] = {}, peaks[5] = {}, mainMin = 1.0, extraMin = 1.0;
    if (capture) {
        std::fill(std::begin(diagnosticTrace_), std::end(diagnosticTrace_), 0.f);
        diagnosticTrace_[0] = 1.f; diagnosticTrace_[1] = static_cast<float>(frames);
        diagnosticTrace_[3] = static_cast<float>(sr_);
        diagnosticTrace_[5] = static_cast<float>(vbCur_);
        diagnosticTrace_[8] = static_cast<float>(vbCur_ >= 0 ? vbMods_[vbCur_]->researchStats().upperBlend : 0.0);
        diagnosticTrace_[24] = static_cast<float>(soloX_.value());
        diagnosticTrace_[26] = static_cast<float>(outGain_.value());
        for (int j = 0; j < P_COUNT; ++j) diagnosticTrace_[32+j] = active_[j];
    }

    // Announce the frames this block will overwrite before touching the ring (see pvb_engine.h).
    tapWriteEnd_.store(tapBase + static_cast<uint64_t>(frames), std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_release);
    uint64_t openBlock = 0;
    const bool dynOn = active_[P_DYN_ON] >= 0.5f;
    if (!dynOn) dynOff_ = 0.0;
    updateCondWanted();  // new parameters (vbApply updates it when the algorithm changes mid-block)
    const double s1mTrim = dbToLin(kS1mTrimDb);

    for (int n = 0; n < frames; ++n) {
        float fl = io[2 * n], fr = io[2 * n + 1];
        if (!isFiniteBits(fl)) { fl = 0.f; badInput = true; }
        if (!isFiniteBits(fr)) { fr = 0.f; badInput = true; }
        const double xl = fl, xr = fr;
        inPeak = std::max(inPeak, std::max(std::fabs(xl), std::fabs(xr)));

        // Virtual bass switching state (see pvb_engine.h).
        double vbx = 1.0;
        if (vbPhase_ != VB_STEADY) {
            vbx = vbX_.next();
            if (vbPhase_ == VB_FADE_OUT && vbx == 0.0) {
                const int before = vbDelay_;
                vbApply(vbWanted(), false);
                if (vbDelay_ > before) {
                    vbHold_ = vbDelay_ - before;  // silent until the delayed music reaches the point it stopped at
                    vbPhase_ = VB_HOLD;
                } else {
                    vbX_.setTarget(1.0, static_cast<int>(std::lround(kVbFadeS * sr_)));
                    vbPhase_ = VB_FADE_IN;
                }
            } else if (vbPhase_ == VB_HOLD) {
                if (--vbHold_ <= 0) {
                    vbX_.setTarget(1.0, static_cast<int>(std::lround(kVbFadeS * sr_)));
                    vbPhase_ = VB_FADE_IN;
                }
            } else if (vbPhase_ == VB_FADE_IN && vbx == 1.0) {
                vbPhase_ = VB_STEADY;
            }
        }
        // The input delay line always records, so a switch while silent finds recent music in it.
        vbDL_[vbPos_] = fl;
        vbDR_[vbPos_] = fr;
        double xdl = xl, xdr = xr;
        if (vbCur_ >= 0 && vbDelay_ > 0) {
            const int rd = (vbPos_ - vbDelay_ + kVbDelayLen) & (kVbDelayLen - 1);
            xdl = vbDL_[rd];
            xdr = vbDR_[rd];
        }
        if (++vbPos_ >= kVbDelayLen) vbPos_ = 0;
        const double vg = vbGain_.next();

        if (dynOn) {
            // Slow level follower: above the reference take boost back (the phone limiter would squash it),
            // below it add a little (the ear hears less low end at low level). Near silence: hold.
            if (dynCount_ <= 0) {
                const double now = 10.0 * std::log10(std::max(dynEnv_, 1e-12)) + 3.0103 + linToDb(outGain_.value());
                if (now > kDynHoldBelowDb) {
                    if (!dynHave_) {
                        dynDb_ = now;
                        dynHave_ = true;
                    } else {
                        dynDb_ += (now - dynDb_) * (now > dynDb_ ? dynRise_ : dynFall_);
                    }
                    const double d = dynDb_ - active_[P_DYN_REF_DB];
                    dynOff_ = d >= 0.0
                        ? -std::min(d * active_[P_DYN_DOWN_RATIO], static_cast<double>(active_[P_DYN_DOWN_MAX_DB]))
                        : std::min(-d * active_[P_DYN_UP_RATIO], static_cast<double>(active_[P_DYN_UP_MAX_DB]));
                    if (dynOff_ == 0.0) dynOff_ = 0.0;  // no negative zero in the meters
                }
                lo_.setTarget(svfBell(sr_, active_[P_LOW_HZ], lowDbNow_.value() + dynOff_, active_[P_LOW_Q]), kDynStep);
                dynCount_ = kDynStep;
            }
            --dynCount_;
            const double dl = dynHp_.tick(sDyn_[0], xdl), dr = dynHp_.tick(sDyn_[1], xdr);
            const double p = 0.5 * (dl * dl + dr * dr);
            dynEnv_ += (p - dynEnv_) * dynEnvCoef_;
        }

        hp_.advance();
        lo_.advance();
        hi_.advance();
        hs_.advance();
        const double og = outGain_.next();
        const double mix = mix_.next();
        const double fade = fade_.next();
        const double gate = gate_.next();
        lowDbNow_.next();
        if (gate == gateTarget_ && gateTarget_ >= kOpenMinLin && mix == 1.0 && fade == 1.0 && vbx == 1.0) ++openBlock;

        double wl = hp_.tick(sHp2_[0], hp_.tick(sHp1_[0], xdl));
        double wr = hp_.tick(sHp2_[1], hp_.tick(sHp1_[1], xdr));
        wl = hs_.tick(sHs_[0], hi_.tick(sHi_[0], lo_.tick(sLo_[0], wl)));
        wr = hs_.tick(sHs_[1], hi_.tick(sHi_[1], lo_.tick(sLo_[1], wr)));
        // virtual bass layer after the EQ filters, before the output gain and the limiter; generated from the
        // undelayed pre-EQ input (hpv) or from the EQ output itself (Bankstown)
        double layL = 0.0, layR = 0.0;
        if (vbCur_ >= 0) {
            VbModule* m = vbMods_[vbCur_];
            if (m->inputAfterEq()) m->tick(wl, wr, layL, layR);
            else m->tick(xl, xr, layL, layR);
            // Experimental options (all off: neither branch runs, the layer is untouched).
            if (genCur_) { layL *= s1mTrim; layR *= s1mTrim; }
            if (!cond_.idle()) {
                const double cg = cond_.tick(layL, layR, 0.5 * (xdl + xdr));
                layL *= cg;
                layR *= cg;
            }
            if(capture) if(const auto* hop=m->takeHarmonicTrace()) {
                if(harmonicCount_>=HarmonicTrace::kBlockRows) harmonicOverflow_=true;
                else {
                    float* row=harmonicRows_+harmonicCount_++*HarmonicTrace::kFields;
                    std::copy_n(hop->data,HarmonicTrace::kFields,row);
                    row[0]=static_cast<float>(n); row[1]=static_cast<float>(vbCur_);
                    row[10]+=static_cast<float>(lim_.latency());
                }
            }
        }
        if (devMeterOn_) {
            // Developer-mode display only (nothing here reaches the output): dry low band (aligned with the layer),
            // layer, and both in the 150-400 Hz band where the phone's protection acts.
            const double low = devLp_.tick(sDevLp_, 0.5 * (xdl + xdr));
            const double lay = vg * 0.5 * (layL + layR) * og;
            devBinDry_ += low * low;
            devBinLay_ += lay * lay;
            const double bd = devBp_.tick(sDevBpDry_, 0.5 * (wl + wr) * og);
            const double bl = devBp_.tick(sDevBpLay_, lay);
            devPowDry_ += (bd * bd - devPowDry_) * devPowCoef_;
            devPowLay_ += (bl * bl - devPowLay_) * devPowCoef_;
            if (++devBinN_ >= devBinLen_) {
                const int slot = static_cast<int>(devRingCount_ % kDevRing);
                devRingDry_[slot].store(dbOrFloor(std::sqrt(2.0 * devBinDry_ / devBinLen_)), std::memory_order_relaxed);
                devRingLay_[slot].store(dbOrFloor(std::sqrt(2.0 * devBinLay_ / devBinLen_)), std::memory_order_relaxed);
                ++devRingCount_;
                devRingPub_.store(devRingCount_, std::memory_order_release);
                devBinDry_ = devBinLay_ = 0.0;
                devBinN_ = 0;
            }
        }
        // Keep this small delay warm even when diagnostics are off: exact component alignment on arming.
        const double preL = vg * layL * og, preR = vg * layR * og;
        layerDelayL_[layerPos_] = preL; layerDelayR_[layerPos_] = preR;
        const int layerRead = (layerPos_ - lat + kDryLen) % kDryLen;
        const double delayedLayerL = layerDelayL_[layerRead], delayedLayerR = layerDelayR_[layerRead];
        if (++layerPos_ >= kDryLen) layerPos_ = 0;
        wl = (wl + vg * layL) * og;
        wr = (wr + vg * layR) * og;

        double ll = 0.0, lr = 0.0;
        lim_.process(wl, wr, ll, lr);

        // Isolate the actual generator contribution, not the difference between two reruns.
        // The full sum above still drives its original limiter and the loudness matcher below.
        const double sx = soloX_.next();
        double sl = 0.0, sr = 0.0;
        const bool runSolo = sx > 0.0 || soloX_.target() > 0.0;
        if (runSolo) {
            if (!soloRun_) limSolo_.reset();
            limSolo_.process(vg * layL * og, vg * layR * og, sl, sr);
            const double fullGain = lim_.currentGain();
            const double soloGain = limSolo_.currentGain();
            // Shared full-mix gain, with extra attenuation only if the isolated layer needs protection.
            const double shared = std::min(1.0, fullGain / std::max(soloGain, 1e-30));
            sl *= shared; sr *= shared;
            storeMin(mSoloExtraMin_, static_cast<float>(std::min(1.0, soloGain / std::max(fullGain, 1e-30))));
        }
        soloRun_ = runSolo;

        // Dry path, delayed by the limiter latency so the crossfade stays phase aligned.
        dryL_[dryPos_] = xdl;
        dryR_[dryPos_] = xdr;
        const int rd = (dryPos_ - lat + kDryLen) % kDryLen;
        const double dl = dryL_[rd], dr = dryR_[rd];
        if (++dryPos_ >= kDryLen) dryPos_ = 0;

        // Loudness match: processed output vs the input it came from (both time aligned, before any gate or fade).
        match_.push(dl, dr, ll, lr);
        // Flat bypass: the input at the matched loudness, through its own limiter (same ceiling, same latency). The
        // limiter stays warm whenever matched bypass is enabled, including while the wet path is selected.
        const double fx = flatX_.next();
        const double mg = match_.nextGain();
        double bl = dl, br = dr;
        // Keep this delay/limiter warm even while wet is selected, so bypass starts with valid recent samples.
        const bool runFlat = fx > 0.0;
        if (runFlat) {
            if (!flatRun_) limFlat_.reset();
            double fl2 = 0.0, fr2 = 0.0;
            limFlat_.process(xdl * mg, xdr * mg, fl2, fr2);
            bl = fx * fl2 + (1.0 - fx) * dl;
            br = fx * fr2 + (1.0 - fx) * dr;
        }
        flatRun_ = runFlat;

        // The gate comes after the dry/wet mix: a bypass never escapes a mute.
        const double normalL = mix * ll + (1.0 - mix) * bl;
        const double normalR = mix * lr + (1.0 - mix) * br;
        // No bypass leaks into a settled solo monitor; VB-off/zero-layer means silence.
        const double yl = (sx == 0.0 ? normalL : (1.0 - sx) * normalL + sx * mix * sl) * fade * gate * vbx;
        const double yr = (sx == 0.0 ? normalR : (1.0 - sx) * normalR + sx * mix * sr) * fade * gate * vbx;
        if (!isFiniteBits(yl) || !isFiniteBits(yr)) badOutput = true;

        if (capture) {
            const double sharedGate = mix * fade * gate * vbx * lim_.currentGain();
            const double gl = delayedLayerL * sharedGate, gr = delayedLayerR * sharedGate;
            const double fullL = normalL * fade * gate * vbx, fullR = normalR * fade * gate * vbx;
            diagnosticLayer_[2*n] = static_cast<float>(gl); diagnosticLayer_[2*n+1] = static_cast<float>(gr);
            diagnosticFull_[2*n] = static_cast<float>(fullL); diagnosticFull_[2*n+1] = static_cast<float>(fullR);
            const double pairs[10] = {xl,xr,preL,preR,gl,gr,fullL,fullR,yl,yr};
            for (int j = 0; j < 5; ++j) {
                const double a = pairs[2*j], b = pairs[2*j+1];
                powers[j] += a*a + b*b;
                peaks[j] = std::max(peaks[j], std::max(std::fabs(a),std::fabs(b)));
            }
            mainMin = std::min(mainMin, lim_.currentGain());
            if (runSolo) extraMin = std::min(extraMin, std::min(1.0, limSolo_.currentGain()/std::max(lim_.currentGain(),1e-30)));
        }

        // What the phone's own processor will do with this (display only); left and right powers, not the mid.
        phone_.push(yl, yr);

        io[2 * n] = static_cast<float>(yl);
        io[2 * n + 1] = static_cast<float>(yr);
        outPeak = std::max(outPeak, std::max(std::fabs(yl), std::fabs(yr)));

        // Analysis tap: copy only.
        const size_t t = static_cast<size_t>((tapBase + static_cast<uint64_t>(n)) & (kAnaRing - 1));
        tapIn_[2 * t].store(fl, std::memory_order_relaxed);
        tapIn_[2 * t + 1].store(fr, std::memory_order_relaxed);
        tapOut_[2 * t].store(static_cast<float>(yl), std::memory_order_relaxed);
        tapOut_[2 * t + 1].store(static_cast<float>(yr), std::memory_order_relaxed);
    }

    if (badOutput) {
        // Something blew up (should not happen with sane parameters): silence, reset, fade back in.
        std::fill(io, io + 2 * frames, 0.f);
        resetState();
        fade_.snap(0.0);
        fade_.setTarget(1.0, static_cast<int>(std::lround(kRecoverFadeS * sr_)));
        outPeak = 0.0;
        phone_.reset();
        for (int n = 0; n < frames; ++n) {
            const size_t t = static_cast<size_t>((tapBase + static_cast<uint64_t>(n)) & (kAnaRing - 1));
            tapOut_[2 * t].store(0.f, std::memory_order_relaxed);
            tapOut_[2 * t + 1].store(0.f, std::memory_order_relaxed);
        }
    }
    if (badInput || badOutput) mNan_.fetch_add(1, std::memory_order_relaxed);
    if (inPeak > kOpenInputPeak && !badOutput) {
        openFrames_ += openBlock;
        openFramesPub_.store(openFrames_, std::memory_order_release);
    }

    for (int c = 0; c < 2; ++c) {
        sHp1_[c].flushTiny();
        sHp2_[c].flushTiny();
        sLo_[c].flushTiny();
        sHi_[c].flushTiny();
        sHs_[c].flushTiny();
        sDyn_[c].flushTiny();
    }
    if (dynEnv_ < 1e-24) dynEnv_ = 0.0;
    match_.flushTiny();
    cond_.flushTiny();
    if (devMeterOn_) {
        sDevLp_.flushTiny(); sDevBpDry_.flushTiny(); sDevBpLay_.flushTiny();
        if (devPowDry_ < 1e-24) devPowDry_ = 0.0;
        if (devPowLay_ < 1e-24) devPowLay_ = 0.0;
        DevHarmonics h;
        const bool have = vbCur_ >= 0 && vbMods_[vbCur_]->devHarmonics(h) && h.f0 > 0.0;
        devFields_[DM_F0].store(have ? static_cast<float>(h.f0) : 0.f, std::memory_order_relaxed);
        const double level = vbGain_.value() * outGain_.value() * (genCur_ ? s1mTrim : 1.0);
        for (int k = 2; k <= 8; ++k) {
            const double a = have ? h.amp[k - 2] * h.gain * vbMods_[vbCur_]->devOutResponse(k * h.f0) * level : 0.0;
            devFields_[DM_H2_DB + k - 2].store(dbOrFloor(a), std::memory_order_relaxed);
        }
        devFields_[DM_DRY_BAND_DB].store(dbOrFloor(std::sqrt(2.0 * devPowDry_)), std::memory_order_relaxed);
        devFields_[DM_LAYER_BAND_DB].store(dbOrFloor(std::sqrt(2.0 * devPowLay_)), std::memory_order_relaxed);
        devFields_[DM_RING_BIN_MS].store(static_cast<float>(1000.0 * devBinLen_ / sr_), std::memory_order_relaxed);
        devFields_[DM_GAIN].store(static_cast<float>(have ? h.gain : 0.0), std::memory_order_relaxed);
        devFields_[DM_BOUNDARY_HZ].store(static_cast<float>(devApplied_.boundaryHz), std::memory_order_relaxed);
        devFields_[DM_OUT_LO_HZ].store(static_cast<float>(devApplied_.outLoHz), std::memory_order_relaxed);
        devFields_[DM_OUT_HI_HZ].store(static_cast<float>(devApplied_.outHiHz), std::memory_order_relaxed);
    }

    // Meters.
    storeMax(mInPeak_, static_cast<float>(inPeak));
    storeMax(mOutPeak_, static_cast<float>(outPeak));
    const double wetMin = lim_.takeMinGain(), flatMin = limFlat_.takeMinGain();
    const float blockMinGain = static_cast<float>(mix_.value() <= 0 && flatX_.value() >= 1 ? flatMin :
        mix_.value() >= 1 || flatX_.value() <= 0 ? wetMin : std::min(wetMin,flatMin));
    storeMin(mLimMin_, blockMinGain);
    storeMin(anaLimMin_, blockMinGain);
    mLowDb_.store(static_cast<float>(lowDbNow_.value() + dynOff_), std::memory_order_relaxed);
    mDyn_.store(static_cast<float>(dynOff_), std::memory_order_relaxed);
    mDynLevel_.store(static_cast<float>(dynHave_ ? std::max(-120.0, dynDb_) : -120.0), std::memory_order_relaxed);
    mSoloBlend_.store(static_cast<float>(soloX_.value()), std::memory_order_relaxed);
    mMix_.store(static_cast<float>(mix_.value()), std::memory_order_relaxed);
    mMatchDb_.store(static_cast<float>(match_.gainDb()), std::memory_order_relaxed);
    mMatchMeasured_.store(match_.measured(), std::memory_order_relaxed);
    mEstLevel_.store(static_cast<float>(std::max(-120.0, phone_.maxLevelDb())), std::memory_order_relaxed);
    mEstGr_.store(static_cast<float>(phone_.grDb(1)), std::memory_order_relaxed);
    mBlocks_.fetch_add(1, std::memory_order_relaxed);
    const auto research = vbCur_ >= 0 ? vbMods_[vbCur_]->researchStats() : VbResearchStats{};
    mVbScene_.store(research.scene, std::memory_order_relaxed);
    mVbUpperBlend_.store(static_cast<float>(research.upperBlend), std::memory_order_relaxed);
    mVbUpperTarget_.store(static_cast<float>(research.upperTarget), std::memory_order_relaxed);
    mVbUpperTransitions_.store(static_cast<float>(research.transitions), std::memory_order_relaxed);
    for (int j = 0; j < 4; ++j)
        mVbSceneFrames_[j].store(static_cast<float>(research.frames[j]), std::memory_order_relaxed);
    publishFilters();
    tapFrames_.store(tapBase + static_cast<uint64_t>(frames), std::memory_order_release);

    const auto t1 = std::chrono::steady_clock::now();
    const double busy = std::chrono::duration<double>(t1 - t0).count();
    if (capture) {
        diagnosticTrace_[2] = static_cast<float>(busy * 1e6);
        diagnosticTrace_[4] = static_cast<float>(latencyFrames());
        diagnosticTrace_[6] = static_cast<float>(vbCur_);
        diagnosticTrace_[7] = static_cast<float>(research.scene);
        diagnosticTrace_[9] = static_cast<float>(research.upperBlend);
        diagnosticTrace_[10] = static_cast<float>(research.upperTarget);
        diagnosticTrace_[11] = static_cast<float>(research.transitions);
        for (int j = 0; j < 5; ++j) {
            diagnosticTrace_[12+2*j] = dbOrFloor(peaks[j]);
            diagnosticTrace_[13+2*j] = dbOrFloor(std::sqrt(powers[j]/(2*frames)));
        }
        diagnosticTrace_[22] = static_cast<float>(std::max(0.0,-linToDb(mainMin)));
        diagnosticTrace_[23] = static_cast<float>(std::max(0.0,-linToDb(extraMin)));
        diagnosticTrace_[25] = static_cast<float>(soloX_.value());
        diagnosticTrace_[27] = static_cast<float>(outGain_.value());
        diagnosticTrace_[28] = static_cast<float>(dynOff_);
        diagnosticTrace_[29] = static_cast<float>(match_.gainDb());
        diagnosticTrace_[30] = static_cast<float>(mNan_.load(std::memory_order_relaxed));
        diagnosticTrace_[31] = static_cast<float>(vbPhase_);
    }
    const double audio = static_cast<double>(frames) / sr_;
    const double pct = 100.0 * busy / audio;
    loadEma_ = (loadEma_ <= 0.0) ? pct : loadEma_ + 0.1 * (pct - loadEma_);
    mLoad_.store(static_cast<float>(loadEma_), std::memory_order_relaxed);
}

bool Engine::copyDiagnostic(float* generated, float* fullMix, int samples, float* trace, int fields) const {
    if (!diagnosticCapture_ || samples <= 0 || samples != diagnosticSamples_ || fields != kDiagnosticFields ||
        !generated || !fullMix || !trace) return false;
    std::copy_n(diagnosticLayer_, samples, generated);
    std::copy_n(diagnosticFull_, samples, fullMix);
    std::copy_n(diagnosticTrace_, fields, trace);
    return true;
}

int Engine::copyDevMeters(float* out, int capacity) const {
    if (out == nullptr || capacity < kDevMeterSize) return 0;
    const uint32_t count = devRingPub_.load(std::memory_order_acquire);
    for (int i = 0; i < kDevFields; ++i) out[i] = devFields_[i].load(std::memory_order_relaxed);
    out[DM_RING_COUNT] = static_cast<float>(count % 1000000u);
    // Oldest first. An entry the audio thread overwrites meanwhile shows a newer value; display only.
    for (int i = 0; i < kDevRing; ++i) {
        const int slot = static_cast<int>((count + static_cast<uint32_t>(i)) % kDevRing);
        out[kDevFields + 2 * i] = devRingDry_[slot].load(std::memory_order_relaxed);
        out[kDevFields + 2 * i + 1] = devRingLay_[slot].load(std::memory_order_relaxed);
    }
    return kDevMeterSize;
}

int Engine::copyHarmonicTrace(float* out,int capacity) const {
    if(!diagnosticCapture_ || diagnosticSamples_<=0 || !out) return -1;
    if(harmonicOverflow_ || capacity<harmonicCount_*HarmonicTrace::kFields) return -2;
    std::copy_n(harmonicRows_,harmonicCount_*HarmonicTrace::kFields,out);
    return harmonicCount_;
}

void Engine::processInt16(const int16_t* in, int16_t* out, int frames) {
    if (in == nullptr || out == nullptr || frames <= 0) return;
    const size_t n = static_cast<size_t>(frames) * 2;
    if (scratch_.size() < n) scratch_.resize(n);  // grows only when a longer block shows up
    for (size_t i = 0; i < n; ++i) scratch_[i] = in[i] * (1.0f / 32768.0f);
    process(scratch_.data(), frames);
    for (size_t i = 0; i < n; ++i) {
        const float v = std::nearbyint(scratch_[i] * 32768.0f);
        out[i] = static_cast<int16_t>(clampv(v, -32768.0f, 32767.0f));
    }
}

int Engine::openMs(int tag) const {
    if (tagPub_.load(std::memory_order_acquire) != tag) return -1;
    const uint64_t f = openFramesPub_.load(std::memory_order_acquire);
    if (tagPub_.load(std::memory_order_acquire) != tag) return -1;
    const uint64_t sr = static_cast<uint64_t>(std::max(1, srMeter_.load(std::memory_order_relaxed)));
    return static_cast<int>(std::min<uint64_t>(f * 1000u / sr, static_cast<uint64_t>(INT_MAX)));
}

void Engine::readMeters(float* out, int count) {
    if (out == nullptr || count <= 0) return;
    float m[M_COUNT];
    m[M_DIAGNOSTIC_SOLO_BLEND] = mSoloBlend_.load(std::memory_order_relaxed);
    m[M_DIAGNOSTIC_SOLO_EXTRA_GR_DB] = static_cast<float>(std::max(0.0, -linToDb(mSoloExtraMin_.exchange(1.f, std::memory_order_relaxed))));
    m[M_IN_PEAK_DB] = dbOrFloor(mInPeak_.exchange(0.f, std::memory_order_relaxed));
    m[M_OUT_PEAK_DB] = dbOrFloor(mOutPeak_.exchange(0.f, std::memory_order_relaxed));
    m[M_LIM_GR_DB] = static_cast<float>(std::max(0.0, -linToDb(mLimMin_.exchange(1.f, std::memory_order_relaxed))));
    m[M_LOW_DB_NOW] = mLowDb_.load(std::memory_order_relaxed);
    m[M_MIX] = mMix_.load(std::memory_order_relaxed);
    m[M_LOAD_PCT] = mLoad_.load(std::memory_order_relaxed);
    m[M_SAMPLE_RATE] = static_cast<float>(srMeter_.load(std::memory_order_relaxed));
    m[M_LATENCY] = static_cast<float>(latency_.load(std::memory_order_relaxed));
    m[M_BLOCKS] = static_cast<float>(mBlocks_.load(std::memory_order_relaxed) % 1000000u);
    m[M_NAN_EVENTS] = static_cast<float>(mNan_.load(std::memory_order_relaxed));
    m[M_EST_LEVEL_DB] = mEstLevel_.load(std::memory_order_relaxed);
    m[M_EST_GR_DB] = mEstGr_.load(std::memory_order_relaxed);
    m[M_DYN_DB] = mDyn_.load(std::memory_order_relaxed);
    m[M_DYN_LEVEL_DB] = mDynLevel_.load(std::memory_order_relaxed);
    m[M_VB] = static_cast<float>(mVb_.load(std::memory_order_relaxed));
    m[M_MATCH_DB] = mMatchDb_.load(std::memory_order_relaxed);
    m[M_VB_SCENE] = static_cast<float>(mVbScene_.load(std::memory_order_relaxed));
    m[M_VB_UPPER_BLEND] = mVbUpperBlend_.load(std::memory_order_relaxed);
    m[M_VB_UPPER_TARGET] = mVbUpperTarget_.load(std::memory_order_relaxed);
    m[M_VB_UPPER_TRANSITIONS] = mVbUpperTransitions_.load(std::memory_order_relaxed);
    for (int j = 0; j < 4; ++j)
        m[M_VB_UNKNOWN_FRAMES + j] = mVbSceneFrames_[j].load(std::memory_order_relaxed);
    const int n = count < M_COUNT ? count : static_cast<int>(M_COUNT);
    for (int i = 0; i < n; ++i) out[i] = m[i];
}

}  // namespace pvb


// Experimental layer conditioning (opt-in, all off by default). Copyright (C) 2026 PVB project. GPL v3.
//
// Applied to the virtual bass layer after the VB module and before the layer is summed with the dry signal. One gain
// for both channels. Every stage only cuts (gain <= 1); none ever raises the layer. With every stage off the engine
// skips this code entirely, so the output is bit-identical to the engine without it (test_experimental.py).
//
//  smooth ("층 출렁임 완화"): listening round 6 (offline) found that smoothing the layer envelope over 500 ms removed a
//      "hoong-hoong" pumping. That offline version was zero-phase (gain = 500 ms envelope / 5 ms envelope of the
//      layer, clipped 0.3..3, then RMS matched), so it also raised dips and tails. The layer already decays slower
//      than the source (tails 3-5 dB louder, 40-60 ms longer) and lengthened kick tails are disliked, so this causal
//      version only cuts: where the fast envelope (5 ms, two one-pole stages on the power) exceeds the slow one (one
//      pole, 500 ms) by more than 1 dB, the layer is reduced to 1 dB above the slow envelope, at most -10.5 dB (the
//      offline floor 0.3). It never boosts and is not RMS matched, so the layer gets a little smaller on average and
//      the first ~0.5 s after a note starts from silence is reduced (the slow envelope still has to rise).
//  rise ("급상승 완화"): rounds 7-8 (prepare_kick_protect.py / prepare_rise_control.py). Same followers as offline:
//      envelope e (20 ms), slow = follower(e, attack 150 ms, release 20 ms), quick = follower(e, 5 ms, 20 ms),
//      gain = clip(slow / quick, 0.2, 1), then 5 ms smoothing. Offline e was the Hilbert envelope smoothed zero-phase
//      over 20 ms and the final 5 ms smoothing was zero-phase; here both are causal one-pole smoothers (e = RMS of
//      the power through two 10 ms one-poles). Cut-only by construction, as offline. Runs after "smooth".
//  dense ("복합음 감응 세기"): round 19 (deep/make19.py). The dry 500-4000 Hz band (4th-order Butterworth high- and
//      low-pass) level in dB (mean square, one pole 25 ms ~ the offline 50 ms centred window); when it is above its
//      usual level the layer is reduced by the excess in dB, at most 6 dB, attack 50 ms / release 300 ms (as
//      offline). Offline "usual" was the song's median (over frames within 40 dB of the song's maximum); here it is
//      a running average in dB (a plain mean of what was heard while that is shorter than 10 s, then a 10 s one-pole),
//      updated only while the band is within 40 dB of it and above -80 dBFS; no cut during the first ~1.1 s of band
//      activity after the option starts. Uses the dry input aligned with the layer.
//
// Switching: each stage blends in and out over 100 ms (gain = 1 - blend * (1 - stage gain)); a stage that has blended
// out stops and forgets its state, so with everything off nothing runs. Realtime rules: no allocation, fixed state,
// deterministic.
#pragma once

#include <algorithm>
#include <cmath>

#include "pvb_dsp.h"

namespace pvb {

class LayerConditioner {
public:
    static constexpr double kSmoothFastMs = 5.0, kSmoothSlowMs = 500.0, kSmoothMarginDb = 1.0, kSmoothFloor = 0.3;
    static constexpr double kRiseEnvMs = 10.0, kRiseSlowAttMs = 150.0, kRiseQuickAttMs = 5.0, kRiseRelMs = 20.0;
    static constexpr double kRiseFloor = 0.2, kRiseGainMs = 5.0;
    static constexpr double kDenseEnvMs = 25.0, kDenseUsualS = 10.0, kDenseMaxDb = 6.0;
    static constexpr double kDenseAttMs = 50.0, kDenseRelMs = 300.0, kDenseFloorDb = -80.0, kDenseWindowDb = 40.0;
    static constexpr double kDenseReadyS = 1.0;  // no cut until the usual level has 1 s of audio behind it
    static constexpr double kBlendMs = 100.0;
    static constexpr double kQuietPower = 1e-12;  // layer below -120 dBFS: no detection, gain 1

    void configure(int sr) {
        const double fs = sr;
        auto pole = [fs](double ms) { return std::exp(-1.0 / (ms * 1e-3 * fs)); };
        smFast_ = pole(kSmoothFastMs);
        smSlow_ = pole(kSmoothSlowMs);
        riEnv_ = pole(kRiseEnvMs);
        riSlowAtt_ = pole(kRiseSlowAttMs);
        riQuickAtt_ = pole(kRiseQuickAttMs);
        riRel_ = pole(kRiseRelMs);
        riGain_ = pole(kRiseGainMs);
        deEnv_ = pole(kDenseEnvMs);
        deUsual_ = std::exp(-1.0 / (kDenseUsualS * fs));
        deAtt_ = pole(kDenseAttMs);
        deRel_ = pole(kDenseRelMs);
        deSkip_ = static_cast<long>(0.1 * fs);
        deReady_ = static_cast<long>(kDenseReadyS * fs);
        deCap_ = deSkip_ + std::max(deReady_, static_cast<long>(kDenseUsualS * fs)) + 1;
        blendStep_ = 1.0 / std::max(1.0, kBlendMs * 1e-3 * fs);
        // 4th-order Butterworth = two 2nd-order sections, Q 0.5412 and 1.3066.
        static constexpr double kQ[2] = {0.54119610014619698, 1.3065629648763766};
        for (int j = 0; j < 2; ++j) {
            hp_[j] = coef(svfHighpass(fs, 500.0, kQ[j]));
            SvfCoef lp;
            lp.g = prewarp(fs, 4000.0);
            lp.k = 1.0 / kQ[j];
            lp.m0 = 0.0; lp.m1 = 0.0; lp.m2 = 1.0;
            lp_[j] = coef(lp);
        }
        reset();
    }

    // Every stage off and idle (no state).
    void reset() {
        for (Stage* s : {&smooth_, &rise_, &dense_}) *s = Stage{};
        clearSmooth();
        clearRise();
        clearDense();
    }

    // Detector memory only (another algorithm or a reset of the chain): the blends stay where they are.
    void clearDetectors() {
        clearSmooth();
        clearRise();
        clearDense();
    }

    void setWanted(bool smooth, bool rise, bool dense) {
        smooth_.want = smooth;
        rise_.want = rise;
        dense_.want = dense;
    }

    // True: tick() would return exactly 1 and change no state, so the caller may skip it.
    bool idle() const { return !smooth_.active() && !rise_.active() && !dense_.active(); }

    // Gain for this frame (0 < gain <= 1). dry: the input aligned with the layer (mono).
    double tick(double layL, double layR, double dry) {
        double g = 1.0;
        if (smooth_.active()) {
            if (smooth_.begin()) clearSmooth();
            const double p = 0.5 * (layL * layL + layR * layR);
            smP1_ = smFast_ * smP1_ + (1.0 - smFast_) * p;
            smP2_ = smFast_ * smP2_ + (1.0 - smFast_) * smP1_;
            const double fast = std::sqrt(smP2_);
            smA_ = smSlow_ * smA_ + (1.0 - smSlow_) * fast;
            double s = 1.0;
            if (smP2_ > kQuietPower) s = clampv(smMargin_ * smA_ / fast, kSmoothFloor, 1.0);
            g *= smooth_.apply(s, blendStep_);
        }
        if (rise_.active()) {
            if (rise_.begin()) clearRise();
            const double p = 0.5 * (layL * layL + layR * layR) * g * g;  // after "smooth"
            riP1_ = riEnv_ * riP1_ + (1.0 - riEnv_) * p;
            riP2_ = riEnv_ * riP2_ + (1.0 - riEnv_) * riP1_;
            const double e = std::sqrt(riP2_);
            double a = e > riSlow_ ? riSlowAtt_ : riRel_;
            riSlow_ = a * riSlow_ + (1.0 - a) * e;
            a = e > riQuick_ ? riQuickAtt_ : riRel_;
            riQuick_ = a * riQuick_ + (1.0 - a) * e;
            const double r = riP2_ > kQuietPower && riQuick_ > 0.0 ? clampv(riSlow_ / riQuick_, kRiseFloor, 1.0) : 1.0;
            riG_ = riGain_ * riG_ + (1.0 - riGain_) * r;
            g *= rise_.apply(std::min(riG_, 1.0), blendStep_);
        }
        if (dense_.active()) {
            if (dense_.begin()) clearDense();
            double b = dry;
            for (int j = 0; j < 2; ++j) b = tick(hp_[j], hpS_[j], b);
            for (int j = 0; j < 2; ++j) b = tick(lp_[j], lpS_[j], b);
            deP_ = deEnv_ * deP_ + (1.0 - deEnv_) * b * b;
            const double e = 10.0 * std::log10(deP_ + 1e-14);
            if (e > kDenseFloorDb && (deCount_ <= deSkip_ || e > deUsualDb_ - kDenseWindowDb)) {
                // Running mean of the active level: a plain average while fewer than 10 s were seen, then the
                // 10 s one-pole. The first 100 ms (envelope still rising) are left out.
                if (deCount_ < deCap_) ++deCount_;  // capped: past 10 s the one-pole rate applies anyway
                if (deCount_ > deSkip_) {
                    const double n = static_cast<double>(deCount_ - deSkip_);
                    deUsualDb_ += (e - deUsualDb_) * std::max(1.0 / n, 1.0 - deUsual_);
                }
            }
            const bool ready = deCount_ >= deSkip_ + deReady_;
            deHave_ = ready;
            const double want = ready ? clampv(e - deUsualDb_, 0.0, kDenseMaxDb) : 0.0;
            const double a = want > deCutDb_ ? deAtt_ : deRel_;
            deCutDb_ = a * deCutDb_ + (1.0 - a) * want;
            g *= dense_.apply(deCutDb_ > 0.0 ? std::pow(10.0, -deCutDb_ / 20.0) : 1.0, blendStep_);
        }
        return g;
    }

    void flushTiny() {
        for (auto* s : {&hpS_[0], &hpS_[1], &lpS_[0], &lpS_[1]}) s->flushTiny();
        for (double* v : {&smP1_, &smP2_, &smA_, &riP1_, &riP2_, &riSlow_, &riQuick_, &deP_})
            if (*v < 1e-30) *v = 0.0;
    }

    // Gains applied in the last frame (1 = no cut), for tests.
    double smoothGain() const { return smooth_.applied; }
    double riseGain() const { return rise_.applied; }
    double denseGain() const { return dense_.applied; }
    double denseUsualDb() const { return deHave_ ? deUsualDb_ : -120.0; }

private:
    struct Stage {
        bool want = false;
        bool running = false;
        double blend = 0.0;
        double applied = 1.0;
        bool active() const { return want || running; }
        // First frame after starting: the caller clears the detector.
        bool begin() {
            if (running) return false;
            running = true;
            blend = 0.0;
            return true;
        }
        double apply(double gain, double step) {
            blend = want ? std::min(1.0, blend + step) : std::max(0.0, blend - step);
            applied = 1.0 - blend * (1.0 - gain);
            if (!want && blend <= 0.0) {  // blended out: stop (state is cleared on the next start)
                running = false;
                applied = 1.0;
            }
            return applied;
        }
    };
    struct Coef { double a1 = 1, a2 = 0, a3 = 0, m0 = 1, m1 = 0, m2 = 0; };
    static Coef coef(const SvfCoef& c) {
        Coef r;
        r.a1 = 1.0 / (1.0 + c.g * (c.g + c.k));
        r.a2 = c.g * r.a1;
        r.a3 = c.g * r.a2;
        r.m0 = c.m0; r.m1 = c.m1; r.m2 = c.m2;
        return r;
    }
    static double tick(const Coef& c, SvfState& s, double v0) {
        const double v3 = v0 - s.ic2;
        const double v1 = c.a1 * s.ic1 + c.a2 * v3;
        const double v2 = s.ic2 + c.a2 * s.ic1 + c.a3 * v3;
        s.ic1 = 2.0 * v1 - s.ic1;
        s.ic2 = 2.0 * v2 - s.ic2;
        return c.m0 * v0 + c.m1 * v1 + c.m2 * v2;
    }
    void clearSmooth() { smP1_ = smP2_ = smA_ = 0.0; }
    void clearRise() { riP1_ = riP2_ = riSlow_ = riQuick_ = 0.0; riG_ = 1.0; }
    void clearDense() {
        for (auto* s : {&hpS_[0], &hpS_[1], &lpS_[0], &lpS_[1]}) s->reset();
        deP_ = 0.0; deUsualDb_ = 0.0; deCutDb_ = 0.0; deHave_ = false; deCount_ = 0;
    }

    Stage smooth_, rise_, dense_;
    double blendStep_ = 1.0 / 4800.0;
    // smooth
    double smFast_ = 0, smSlow_ = 0, smMargin_ = std::pow(10.0, kSmoothMarginDb / 20.0);
    double smP1_ = 0, smP2_ = 0, smA_ = 0;
    // rise
    double riEnv_ = 0, riSlowAtt_ = 0, riQuickAtt_ = 0, riRel_ = 0, riGain_ = 0;
    double riP1_ = 0, riP2_ = 0, riSlow_ = 0, riQuick_ = 0, riG_ = 1;
    // dense
    Coef hp_[2], lp_[2];
    SvfState hpS_[2], lpS_[2];
    double deEnv_ = 0, deUsual_ = 0, deAtt_ = 0, deRel_ = 0;
    double deP_ = 0, deUsualDb_ = 0, deCutDb_ = 0;
    bool deHave_ = false;
    long deCount_ = 0, deSkip_ = 4800, deReady_ = 48000, deCap_ = 484801;
};

}  // namespace pvb

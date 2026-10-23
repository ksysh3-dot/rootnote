// Crosstalk cancellation for the two built-in phone speakers ("공간감", RACE-style; docs/XTC_PLAN.md).
//
// Each output subtracts the other output delayed by the head's crosstalk delay tau and scaled by g (recursive, as in
// Glasgal's RACE). The feedback path is shaped by first-order filters: a high-pass at loHz, a low-pass at hiHz and a
// head-shadow shelf (far ear / near ear, Brown-Duda form), so the bass and the top end are left almost untouched.
//   full:        yL = xL - g B[yR(t - tau)],  yR = xR - g B[yL(t - tau)]
//   centre safe: mid unchanged, side S = s + g B[S(t - tau)]   (centre sounds keep their tone; less separation)
// tau comes from a standard spherical head (Woodworth), scaled by hat size, and the listening distance: nothing is
// measured. The delay line interpolates linearly, like JamesDSP's EEL fractionalDelayLine, so the sound matches the
// LiveProg prototype (tools/xtc/race_xtc.eel) that was judged by ear; tools/xtc/check_eel_port.py is the reference.
//
// Speaker balance (P_XTC_BAL_LO_DB / P_XTC_BAL_HI_DB): the two phone speakers differ (a bottom speaker and the
// earpiece), and cancellation assumes equal speakers. For speakers a_L, a_R the exact inverse is the symmetric
// canceller followed by diag(1/a_L, 1/a_R), so after the canceller each channel gets a gentle two-band correction
// (RBJ peaking bells at ~775 Hz, Q 0.7 for 400-1500 Hz and ~3.5 kHz, Q 0.55 for 1.5-8 kHz): balance b dB ("the left
// speaker is b dB louder") lowers the left by b/2 and raises the right by b/2. Only on the processed path.
//
// Off (mode 0, no fade in progress): idle() is true and the engine does not call tick(), so the output is
// bit-identical to the engine without this stage. Switching and setting changes crossfade with the plain input.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <algorithm>
#include <cmath>

namespace pvb {

class Xtc {
public:
    // PORTRAIT_*: the phone held upright, its speakers above each other (no left/right to cancel). Both channels are
    // summed to mono and crossed over at kSplitHz (4th-order Linkwitz-Riley: the two parts add up flat, in phase):
    // MONO plays the mono sum from both speakers; SPLIT_LOW_L / SPLIT_LOW_R send the low part to that channel's
    // speaker (the bottom one, which has the bass) and the high part to the other (the earpiece), as a two-way speaker,
    // so the two speakers no longer play the same highs from two heights (comb filtering) and the earpiece is spared
    // the bass. Each part is played at +3 dB (sqrt 2): one speaker instead of two.
    enum Mode { OFF = 0, CENTRE = 1, FULL = 2, PORTRAIT_MONO = 3, SPLIT_LOW_L = 4, SPLIT_LOW_R = 5 };
    static constexpr double kSplitHz = 1000.0;

    struct Config {
        int mode = OFF;
        double strengthDb = -6.0;   // g: -6 gentle, -4.5 medium, -3 strong
        double distanceCm = 40.0;   // listening distance
        double hatCm = 57.0;        // head size as hat size (circumference); 57 = the standard 8.75 cm head
        double spacingCm = 15.5;    // speaker spacing in landscape
        double loHz = 400.0;
        double hiHz = 8000.0;
        double balLoDb = 0.0;       // left speaker louder than the right by this much, 400-1500 Hz (negative: right)
        double balHiDb = 0.0;       // the same, 1.5-8 kHz
        bool operator==(const Config& o) const {
            return mode == o.mode && strengthDb == o.strengthDb && distanceCm == o.distanceCm && hatCm == o.hatCm &&
                   spacingCm == o.spacingCm && loHz == o.loHz && hiHz == o.hiHz && balLoDb == o.balLoDb &&
                   balHiDb == o.balHiDb;
        }
        bool operator!=(const Config& o) const { return !(*this == o); }
    };

    static constexpr double kFadeS = 0.03;   // crossfade with the plain input on switching or a change
    static constexpr int kDelayLen = 64;     // longest delay: 60 cm away, large head, 192 kHz < 30 samples

    void setSampleRate(int sr) {
        sr_ = sr;
        fadeLen_ = std::max(1, static_cast<int>(std::lround(kFadeS * sr_)));
        apply(want_);
        reset();
        x_ = cur_.mode != OFF ? 1.0 : 0.0;
        phase_ = STEADY;
    }

    // New wanted settings. Applied at once while off and silent-to-us (no fade); else fade to the plain input,
    // apply, and fade back in.
    void setWanted(const Config& c) {
        want_ = c;
        if (want_ == cur_) return;
        // Only the balance moved (calibrating by ear): new bell gains at once, no fade, filter memory kept.
        Config sameBal = want_;
        sameBal.balLoDb = cur_.balLoDb;
        sameBal.balHiDb = cur_.balHiDb;
        if (sameBal == cur_ && cur_.mode != OFF && phase_ == STEADY) {
            setBalance(want_.balLoDb, want_.balHiDb);
            return;
        }
        if (cur_.mode == OFF && x_ == 0.0) {
            apply(want_);
            reset();
            if (cur_.mode != OFF) phase_ = FADE_IN;
            return;
        }
        phase_ = FADE_OUT;
    }

    bool idle() const { return cur_.mode == OFF && x_ == 0.0 && phase_ == STEADY; }

    void reset() {
        std::fill(std::begin(dA_), std::end(dA_), 0.0);
        std::fill(std::begin(dB_), std::end(dB_), 0.0);
        w_ = 0;
        yA_ = yB_ = 0.0;
        for (auto* s : {&lA_, &lB_}) for (auto& f : s->f) f.z = 0.0;
        for (auto& st : sBal_) st = BiquadState{};
        for (auto& st : sSplit_) st = BiquadState{};
    }

    // After the engine dropped its audio (route change): forget the old signal and finish any switch at once.
    void hardReset() {
        if (cur_ != want_) apply(want_);
        reset();
        x_ = cur_.mode != OFF ? 1.0 : 0.0;
        phase_ = STEADY;
    }

    inline void tick(double inL, double inR, double& outL, double& outR) {
        // fade state
        const double step = 1.0 / fadeLen_;
        if (phase_ == FADE_OUT) {
            x_ = std::max(0.0, x_ - step);
            if (x_ == 0.0) {
                apply(want_);
                reset();
                phase_ = cur_.mode != OFF ? FADE_IN : STEADY;
            }
        } else if (phase_ == FADE_IN) {
            x_ = std::min(1.0, x_ + step);
            if (x_ == 1.0) phase_ = STEADY;
        }
        if (cur_.mode == OFF || x_ == 0.0) {
            outL = inL;
            outR = inR;
            return;
        }
        double pl, pr;
        if (cur_.mode >= PORTRAIT_MONO) {
            const double mono = 0.5 * (inL + inR);
            if (cur_.mode == PORTRAIT_MONO) {
                pl = pr = mono;
            } else {
                const double low = split_[0].tick(sSplit_[1], split_[0].tick(sSplit_[0], mono));
                const double high = split_[1].tick(sSplit_[3], split_[1].tick(sSplit_[2], mono));
                const double lo2 = low * 1.4142135623730951, hi2 = high * 1.4142135623730951;
                pl = cur_.mode == SPLIT_LOW_L ? lo2 : hi2;
                pr = cur_.mode == SPLIT_LOW_L ? hi2 : lo2;
            }
            outL = inL + x_ * (pl - inL);
            outR = inR + x_ * (pr - inR);
            return;
        }
        if (cur_.mode == FULL) {
            const double fbR = loop(lB_, delayRead(dB_));
            const double fbL = loop(lA_, delayRead(dA_));
            yA_ = inL - g_ * fbR;
            yB_ = inR - g_ * fbL;
            pl = yA_;
            pr = yB_;
        } else {
            const double mid = 0.5 * (inL + inR), side = 0.5 * (inL - inR);
            yA_ = side + g_ * loop(lA_, delayRead(dA_));
            pl = mid + yA_;
            pr = mid - yA_;
        }
        // the delay lines hold the outputs fed back (as the EEL version: written, then read lag samples back)
        delayWrite();
        if (balOn_) {
            pl = bal_[1].tick(sBal_[1], bal_[0].tick(sBal_[0], pl));
            pr = bal_[3].tick(sBal_[3], bal_[2].tick(sBal_[2], pr));
        }
        outL = inL + x_ * (pl - inL);
        outR = inR + x_ * (pr - inR);
    }

    // The virtual-bass layer while the phone is upright (code review 2026-10-23, F3): the layer is generated beside
    // this stage and added after it, so without this it would reach both speakers whatever the portrait mode. MONO:
    // both get the mono layer; SPLIT_*: all of it goes to the low channel at +3 dB like the music's low part (the
    // layer is harmonics of the bass, at most a few hundred hertz), nothing to the earpiece. Landscape modes leave
    // the layer as it is. Follows the same crossfade as tick(); call after tick() for the same sample.
    inline void routeLayer(double& l, double& r) const {
        if (cur_.mode < PORTRAIT_MONO || x_ == 0.0) return;
        const double mono = 0.5 * (l + r);
        double pl, pr;
        if (cur_.mode == PORTRAIT_MONO) {
            pl = pr = mono;
        } else {
            const double low = mono * 1.4142135623730951;
            pl = cur_.mode == SPLIT_LOW_L ? low : 0.0;
            pr = cur_.mode == SPLIT_LOW_L ? 0.0 : low;
        }
        l += x_ * (pl - l);
        r += x_ * (pr - r);
    }

    // Design numbers (also for the tests): crosstalk delay in samples and loop gain.
    double tauSamples() const { return tau_; }
    double loopGain() const { return g_; }

private:
    enum Phase { STEADY, FADE_OUT, FADE_IN };
    struct FirstOrder {
        double b0 = 1, b1 = 0, a1 = 0, z = 0;
        void set(double nb0, double nb1, double na0, double na1) {
            b0 = nb0 / na0; b1 = nb1 / na0; a1 = na1 / na0;
        }
        inline double tick(double x) {
            const double y = b0 * x + z;
            z = b1 * x - a1 * y;
            return y;
        }
    };
    struct Loop { FirstOrder f[3]; };   // high-pass, low-pass, head shadow
    struct BiquadState { double z1 = 0, z2 = 0; };
    struct Biquad {
        double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
        void peaking(double sr, double f0, double q, double db) {
            const double pi = 3.14159265358979323846;
            const double A = std::pow(10.0, db / 40.0), w = 2 * pi * f0 / sr, al = std::sin(w) / (2 * q), cw = std::cos(w);
            const double a0 = 1 + al / A;
            b0 = (1 + al * A) / a0; b1 = -2 * cw / a0; b2 = (1 - al * A) / a0; a1 = -2 * cw / a0; a2 = (1 - al / A) / a0;
        }
        inline double tick(BiquadState& s, double x) const {
            const double y = b0 * x + s.z1;
            s.z1 = b1 * x - a1 * y + s.z2;
            s.z2 = b2 * x - a2 * y;
            return y;
        }
    };

    static double loop(Loop& l, double x) { return l.f[2].tick(l.f[1].tick(l.f[0].tick(x))); }

    // EEL fractionalDelayLine semantics: the value fed back is the output of the previous sample (one sample of
    // delay already), read (tau - 1) samples behind the write position with linear interpolation.
    inline double delayRead(const double* d) const {
        double rp = static_cast<double>(w_) - lag_;
        while (rp < 0.0) rp += kDelayLen;
        const int i = static_cast<int>(rp);
        const double fr = rp - i;
        return d[i] * (1.0 - fr) + d[(i + 1) % kDelayLen] * fr;
    }
    inline void delayWrite() {
        w_ = (w_ + 1) % kDelayLen;
        dA_[w_] = yA_;
        dB_[w_] = yB_;
    }

    void apply(const Config& c) {
        cur_ = c;
        if (sr_ <= 0) return;
        g_ = std::pow(10.0, c.strengthDb / 20.0);
        const double radius = 0.0875 * c.hatCm / 57.0;
        const double theta = std::atan((c.spacingCm * 0.005) / (c.distanceCm * 0.01));
        const double tau = radius / 343.0 * (theta + std::sin(theta));
        tau_ = tau * sr_;
        lag_ = std::max(0.0, tau_ - 1.0);
        const double pi = 3.14159265358979323846;
        double k = std::tan(pi * c.loHz / sr_);
        const double alphaNear = 1.05 + 0.95 * std::cos((pi / 2 - theta) / (150.0 / 180.0 * pi) * pi);
        const double alphaFar = 1.05 + 0.95 * std::cos((pi / 2 + theta) / (150.0 / 180.0 * pi) * pi);
        const double w0 = 343.0 / radius, kk = 2.0 * sr_;
        const double bS = alphaFar / (2 * w0) * kk, aS = alphaNear / (2 * w0) * kk;
        for (auto* l : {&lA_, &lB_}) {
            k = std::tan(pi * c.loHz / sr_);
            l->f[0].set(1, -1, 1 + k, k - 1);
            // kept below Nyquist (a host or a future caller at a low rate: past pi/2 tan() turns negative and the
            // pole leaves the unit circle)
            k = std::tan(pi * std::min(c.hiHz, 0.45 * sr_) / sr_);
            l->f[1].set(k, k, 1 + k, k - 1);
            l->f[2].set(1 + bS, 1 - bS, 1 + aS, 1 - aS);
        }
        {
            const double w = 2 * pi * kSplitHz / sr_, al = std::sin(w) / (2 * 0.7071067811865476), cw = std::cos(w);
            const double a0 = 1 + al;
            split_[0].b0 = (1 - cw) / 2 / a0; split_[0].b1 = (1 - cw) / a0; split_[0].b2 = (1 - cw) / 2 / a0;
            split_[1].b0 = (1 + cw) / 2 / a0; split_[1].b1 = -(1 + cw) / a0; split_[1].b2 = (1 + cw) / 2 / a0;
            for (auto& b : split_) { b.a1 = -2 * cw / a0; b.a2 = (1 - al) / a0; }
        }
        setBalance(c.balLoDb, c.balHiDb);
    }

    // speaker balance: left -b/2, right +b/2 in each band
    void setBalance(double loDb, double hiDb) {
        cur_.balLoDb = loDb;
        cur_.balHiDb = hiDb;
        if (sr_ <= 0) return;
        bal_[0].peaking(sr_, kBalLoHz, kBalLoQ, -0.5 * loDb);
        bal_[1].peaking(sr_, kBalHiHz, kBalHiQ, -0.5 * hiDb);
        bal_[2].peaking(sr_, kBalLoHz, kBalLoQ, 0.5 * loDb);
        bal_[3].peaking(sr_, kBalHiHz, kBalHiQ, 0.5 * hiDb);
        const bool on = loDb != 0.0 || hiDb != 0.0;
        if (on && !balOn_) for (auto& st : sBal_) st = BiquadState{};
        balOn_ = on;
    }

    int sr_ = 0;
    int fadeLen_ = 1;
    Config want_, cur_;
    Phase phase_ = STEADY;
    double x_ = 0.0;        // 0 = plain input, 1 = processed
    double g_ = 0.5, tau_ = 0.0, lag_ = 0.0;
    double dA_[kDelayLen] = {}, dB_[kDelayLen] = {};
    int w_ = 0;
    double yA_ = 0.0, yB_ = 0.0;
    Loop lA_, lB_;
    static constexpr double kBalLoHz = 775.0, kBalLoQ = 0.7, kBalHiHz = 3464.0, kBalHiQ = 0.55;
    Biquad bal_[4];               // left lo, left hi, right lo, right hi
    BiquadState sBal_[4];
    bool balOn_ = false;
    Biquad split_[2];             // portrait crossover: Butterworth low-pass, high-pass (each run twice = LR4)
    BiquadState sSplit_[4];
};

}  // namespace pvb

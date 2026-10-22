// PVB speaker engine - DSP building blocks.
//
// Everything here is plain C++17 with no platform dependencies, so the same code runs on the phone
// (NDK) and in the host test harness. Filter states are double precision; audio I/O is float.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iterator>

namespace pvb {

constexpr double kPi = 3.14159265358979323846;

// Non-finite test on the bit pattern, so it keeps working when the build uses -ffast-math.
inline bool isFiniteBits(float x) {
    uint32_t u;
    std::memcpy(&u, &x, sizeof u);
    return (u & 0x7f800000u) != 0x7f800000u;
}

inline bool isFiniteBits(double x) {
    uint64_t u;
    std::memcpy(&u, &x, sizeof u);
    return (u & 0x7ff0000000000000ull) != 0x7ff0000000000000ull;
}

inline double dbToLin(double db) { return std::pow(10.0, db / 20.0); }
inline double linToDb(double lin) { return 20.0 * std::log10(std::max(lin, 1e-12)); }

template <typename T>
inline T clampv(T v, T lo, T hi) { return v < lo ? lo : (v > hi ? hi : v); }

// ------------------------------------------------------------------------------------------------
// State variable filter (A. Simper, "Linear trapezoidal integrated SVF", Cytomic 2013).
// The analogue prototypes are the RBJ cookbook ones and the bilinear transform is pre-warped at fc,
// so the magnitude responses equal the RBJ biquads used by EQ v1.1 and the Python reference.
// Unlike a direct-form biquad, the SVF stays well behaved when its coefficients move every sample,
// which is what makes click-free parameter changes possible.
// ------------------------------------------------------------------------------------------------
struct SvfCoef {
    double g = 0.0;   // tan(pi * fc / fs)
    double k = 1.0;   // damping
    double m0 = 1.0;  // output mix: m0 * input + m1 * band + m2 * low
    double m1 = 0.0;
    double m2 = 0.0;
};

inline double prewarp(double fs, double fc) {
    const double f = clampv(fc, 1.0, 0.45 * fs);
    return std::tan(kPi * f / fs);
}

// 2nd-order high-pass, quality q (0.7071 = Butterworth).
inline SvfCoef svfHighpass(double fs, double fc, double q) {
    SvfCoef c;
    c.g = prewarp(fs, fc);
    c.k = 1.0 / std::max(q, 0.05);
    c.m0 = 1.0;
    c.m1 = -c.k;
    c.m2 = -1.0;
    return c;
}

// RBJ "peakingEQ" bell: gain in dB at fc, quality q.
inline SvfCoef svfBell(double fs, double fc, double db, double q) {
    SvfCoef c;
    const double A = std::pow(10.0, db / 40.0);
    c.g = prewarp(fs, fc);
    c.k = 1.0 / (std::max(q, 0.05) * A);
    c.m0 = 1.0;
    c.m1 = c.k * (A * A - 1.0);
    c.m2 = 0.0;
    return c;
}

// RBJ high shelf (Simper's SVF form): gain db above fc, shelf quality q (0.7071 = no overshoot).
inline SvfCoef svfHighShelf(double fs, double fc, double db, double q) {
    SvfCoef c;
    const double A = std::pow(10.0, db / 40.0);
    c.g = prewarp(fs, fc) * std::sqrt(A);
    c.k = 1.0 / std::max(q, 0.05);
    c.m0 = A * A;
    c.m1 = c.k * (1.0 - A) * A;
    c.m2 = 1.0 - A * A;
    return c;
}

// Band-pass with unity gain at fc.
inline SvfCoef svfBandpass(double fs, double fc, double q) {
    SvfCoef c;
    c.g = prewarp(fs, fc);
    c.k = 1.0 / std::max(q, 0.05);
    c.m0 = 0.0;
    c.m1 = c.k;
    c.m2 = 0.0;
    return c;
}

struct SvfState {
    double ic1 = 0.0;
    double ic2 = 0.0;
    void reset() { ic1 = ic2 = 0.0; }
    // Zero tiny states so long silences never reach denormal numbers.
    void flushTiny() {
        if (std::fabs(ic1) < 1e-25) ic1 = 0.0;
        if (std::fabs(ic2) < 1e-25) ic2 = 0.0;
    }
};

// Smooth glide shape: 3t^2 - 2t^3 (zero slope at both ends, so a glide adds no corner to the output).
inline double smoothstep(double t) { return t * t * (3.0 - 2.0 * t); }

// SVF coefficients that glide to a new target over a number of samples (smoothstep shape).
// One instance is shared by all channels; call advance() once per frame, then tick() per channel.
class RampedSvf {
public:
    void snap(const SvfCoef& c) {
        cur_ = c;
        start_ = c;
        tgt_ = c;
        remain_ = 0;
        update();
    }

    void setTarget(const SvfCoef& c, int rampSamples) {
        if (rampSamples <= 0) {
            snap(c);
            return;
        }
        start_ = cur_;  // a glide in progress continues from where it is
        tgt_ = c;
        len_ = rampSamples;
        remain_ = rampSamples;
    }

    inline void advance() {
        if (remain_ <= 0) return;
        if (--remain_ == 0) {
            cur_ = tgt_;
        } else {
            const double s = smoothstep(1.0 - static_cast<double>(remain_) / len_);
            cur_.g = start_.g + (tgt_.g - start_.g) * s;
            cur_.k = start_.k + (tgt_.k - start_.k) * s;
            cur_.m0 = start_.m0 + (tgt_.m0 - start_.m0) * s;
            cur_.m1 = start_.m1 + (tgt_.m1 - start_.m1) * s;
            cur_.m2 = start_.m2 + (tgt_.m2 - start_.m2) * s;
        }
        update();
    }

    inline double tick(SvfState& s, double v0) const {
        const double v3 = v0 - s.ic2;
        const double v1 = a1_ * s.ic1 + a2_ * v3;
        const double v2 = s.ic2 + a2_ * s.ic1 + a3_ * v3;
        s.ic1 = 2.0 * v1 - s.ic1;
        s.ic2 = 2.0 * v2 - s.ic2;
        return cur_.m0 * v0 + cur_.m1 * v1 + cur_.m2 * v2;
    }

    bool ramping() const { return remain_ > 0; }
    const SvfCoef& current() const { return cur_; }

private:
    void update() {
        a1_ = 1.0 / (1.0 + cur_.g * (cur_.g + cur_.k));
        a2_ = cur_.g * a1_;
        a3_ = cur_.g * a2_;
    }

    SvfCoef cur_, start_, tgt_;
    double a1_ = 1, a2_ = 0, a3_ = 0;
    int remain_ = 0, len_ = 1;
};

// A scalar that glides to its target (smoothstep shape).
class RampedValue {
public:
    void snap(double v) {
        cur_ = start_ = tgt_ = v;
        remain_ = 0;
    }
    void setTarget(double v, int rampSamples) {
        if (rampSamples <= 0) {
            snap(v);
            return;
        }
        start_ = cur_;
        tgt_ = v;
        len_ = rampSamples;
        remain_ = rampSamples;
    }
    inline double next() {
        if (remain_ > 0) {
            if (--remain_ == 0) cur_ = tgt_;
            else cur_ = start_ + (tgt_ - start_) * smoothstep(1.0 - static_cast<double>(remain_) / len_);
        }
        return cur_;
    }
    double value() const { return cur_; }
    double target() const { return tgt_; }

private:
    double cur_ = 0, start_ = 0, tgt_ = 0;
    int remain_ = 0, len_ = 1;
};

// ------------------------------------------------------------------------------------------------
// Coarse model of the phone's own dynamics processor (before the volume control), for display only.
// Fitted to the measurements in tools/pvb-harness/study/phone_model.py ('octx' variant):
//   - octave bands 125 Hz .. 8 kHz; each band reduces itself by the measured static curve of stepped
//     1 kHz sines (0 dB at -34 dBFS ... 6.0 at -16, 10.2 at -13, 19.9 at -1);
//   - loud content in band m pulls band b down by s(f_m) * exp(-|octaves between| / 3) times the measured
//     cross-band curve of the masker level (equal to the static curve at -1 dBFS, but falling much faster:
//     8.0 at -4, 4.5 at -8, 2.4 at -12 dBFS), s = 0.5 at <= 300 Hz rising to 1 at >= 1 kHz.
//     Masker tests: 2 kHz -> 315 Hz -7.9/-3.1/-2.3/-1.3 dB at -1/-4/-8/-12 dBFS, model -8.0/-3.2/-1.8/-1.0;
//   - level: mean square over 1024 samples (like the model's 1024-point frames), fast rise, 50 ms fall;
//     reduction: 5 ms rise, 250 ms recovery;
//   - each band filters left and right separately and averages their powers, so out-of-phase content
//     (R = -L) reads as loud as in-phase content of the same channel level (a mid signal (L+R)/2 would read
//     it as silence). For identical channels this equals the mid signal's power, so the fit is unchanged.
// It is a rough picture (the exact band layout of the phone is unknown); treat its numbers as estimates.
// ------------------------------------------------------------------------------------------------
class PhoneModel {
public:
    static constexpr int kBands = 7;
    static constexpr int kBlock = 64;
    static constexpr int kAvgBlocks = 16;  // level = mean square over kBlock * kAvgBlocks = 1024 samples

    void configure(double fs) {
        static const double centers[kBands] = {125, 250, 500, 1000, 2000, 4000, 8000};
        fs_ = fs;
        for (int b = 0; b < kBands; ++b) {
            const double fc = std::min(centers[b], 0.4 * fs);
            bp_[b].snap(svfBandpass(fs, fc, 0.9));  // two in series: about one octave, steep skirts
            fc_[b] = centers[b];
        }
        for (int b = 0; b < kBands; ++b) {
            for (int m = 0; m < kBands; ++m) {
                if (b == m) {
                    coupling_[b][m] = 1.0;
                    continue;
                }
                const double d = std::fabs(std::log2(fc_[b] / fc_[m]));
                const double t = clampv((std::log2(fc_[m]) - std::log2(300.0)) / (std::log2(1000.0) - std::log2(300.0)), 0.0, 1.0);
                coupling_[b][m] = (0.5 + 0.5 * t) * std::exp(-d / 3.0);
            }
        }
        const double blockS = kBlock / fs;
        levelFall_ = 1.0 - std::exp(-blockS / 0.05);
        grRise_ = 1.0 - std::exp(-blockS / 0.005);
        grFall_ = 1.0 - std::exp(-blockS / 0.25);
        reset();
    }

    void reset() {
        for (int b = 0; b < kBands; ++b) {
            for (int c = 0; c < 2; ++c) {
                st_[c][b].reset();
                st2_[c][b].reset();
            }
            acc_[b] = 0.0;
            level_[b] = -120.0;
            gr_[b] = 0.0;
            ringSum_[b] = 0.0;
            for (double& r : ring_[b]) r = 0.0;
        }
        count_ = 0;
        ringPos_ = 0;
    }

    inline void push(double left, double right) {
        for (int b = 0; b < kBands; ++b) {
            const double vl = bp_[b].tick(st2_[0][b], bp_[b].tick(st_[0][b], left));
            const double vr = bp_[b].tick(st2_[1][b], bp_[b].tick(st_[1][b], right));
            acc_[b] += 0.5 * (vl * vl + vr * vr);
        }
        if (++count_ >= kBlock) update();
    }

    double grDb(int band) const { return gr_[band]; }
    double maxLevelDb() const {
        double m = -120.0;
        for (double l : level_) m = std::max(m, l);
        return m;
    }

    // Measured static gain reduction of the phone (stepped 1 kHz sines), dB, for a sine-equivalent level.
    static double staticGr(double levelDb) {
        static const double pts[][2] = {{-34.0, 0.0}, {-31.0, 0.42}, {-28.0, 0.90}, {-25.0, 1.19}, {-22.0, 2.06},
                                        {-19.0, 3.39}, {-16.0, 6.02}, {-13.0, 10.19}, {-1.0, 19.9}};
        const int n = 9;
        if (levelDb <= pts[0][0]) return 0.0;
        for (int i = 1; i < n; ++i) {
            if (levelDb <= pts[i][0]) {
                const double t = (levelDb - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0]);
                return pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]);
            }
        }
        return pts[n - 1][1] + 0.8 * (levelDb - pts[n - 1][0]);
    }

    // How hard a loud band pulls OTHER bands down, by the loud band's level (masker tests, before coupling).
    static double crossGr(double levelDb) {
        static const double pts[][2] = {{-24.0, 0.0}, {-20.0, 0.3}, {-16.0, 1.0}, {-12.0, 2.4}, {-8.0, 4.5},
                                        {-4.0, 8.0}, {-1.0, 19.9}};
        const int n = 7;
        if (levelDb <= pts[0][0]) return 0.0;
        for (int i = 1; i < n; ++i) {
            if (levelDb <= pts[i][0]) {
                const double t = (levelDb - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0]);
                return pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]);
            }
        }
        return pts[n - 1][1] + 0.8 * (levelDb - pts[n - 1][0]);
    }

private:
    void update() {
        double own[kBands], cross[kBands];
        const bool resum = ringPos_ == 0;  // re-add the ring once per lap so rounding cannot build up
        for (int b = 0; b < kBands; ++b) {
            const double p = acc_[b] / count_;
            ringSum_[b] += p - ring_[b][ringPos_];
            ring_[b][ringPos_] = p;
            if (resum) {
                double sum = 0.0;
                for (double r : ring_[b]) sum += r;
                ringSum_[b] = sum;
            }
            const double ms = std::max(ringSum_[b] / kAvgBlocks, 1e-14);
            const double l = 10.0 * std::log10(ms) + 3.0103;  // sine-equivalent
            level_[b] = l > level_[b] ? l : level_[b] + (l - level_[b]) * levelFall_;
            own[b] = staticGr(level_[b]);
            cross[b] = crossGr(level_[b]);
            acc_[b] = 0.0;
            for (int c = 0; c < 2; ++c) {
                st_[c][b].flushTiny();
                st2_[c][b].flushTiny();
            }
        }
        ringPos_ = (ringPos_ + 1) % kAvgBlocks;
        for (int b = 0; b < kBands; ++b) {
            double target = own[b];
            for (int m = 0; m < kBands; ++m)
                if (m != b) target = std::max(target, coupling_[b][m] * cross[m]);
            gr_[b] += (target - gr_[b]) * (target > gr_[b] ? grRise_ : grFall_);
        }
        count_ = 0;
    }

    double fs_ = 48000.0;
    double fc_[kBands] = {};
    double coupling_[kBands][kBands] = {};
    RampedSvf bp_[kBands];
    SvfState st_[2][kBands], st2_[2][kBands];  // [channel][band]
    double acc_[kBands] = {};
    double ring_[kBands][kAvgBlocks] = {};
    double ringSum_[kBands] = {};
    double level_[kBands] = {};
    double gr_[kBands] = {};
    double levelFall_ = 0.0, grRise_ = 0.0, grFall_ = 0.0;
    int count_ = 0;
    int ringPos_ = 0;
};

// ------------------------------------------------------------------------------------------------
// Look-ahead true-peak limiter (stereo linked).
//
// Peak detection runs on an 8x oversampled estimate (windowed-sinc fractional-delay interpolation at
// offsets 1/8 .. 7/8, 32 taps each). The gain path is
//     required gain r = min(1, ceiling / peak)
//  -> minimum over the next L positions (look-ahead)
//  -> moving average over L + 1 values (a linear fade that reaches r exactly when the peak arrives)
//  -> exponential release.
// The minimum and the moving average together guarantee gain <= r at every detected peak.
// The audio is delayed by D + L samples (D = 16 for the interpolator), the same for every setting.
// ------------------------------------------------------------------------------------------------
class TruePeakLimiter {
public:
    static constexpr int kTaps = 32;      // interpolator support x[j-15] .. x[j+16]
    static constexpr int kPhases = 7;     // 8x oversampled estimate: offsets 1/8 .. 7/8
    static constexpr int kDetectDelay = 16;
    static constexpr int kMaxLookahead = 300;  // 1.5 ms up to 192 kHz
    static constexpr int kDelayLen = kDetectDelay + kMaxLookahead + 1;

    TruePeakLimiter() {
        initInterpolator();
        reset();  // consistent state (rRing_ / rMin_) even before configure()
    }

    void configure(double fs, double lookaheadMs) {
        fs_ = fs;
        L_ = clampv(static_cast<int>(std::lround(lookaheadMs * 1e-3 * fs)), 1, kMaxLookahead);
        setReleaseMs(releaseMs_);
        reset();
    }

    void reset() {
        std::fill(std::begin(histL_), std::end(histL_), 0.0);
        std::fill(std::begin(histR_), std::end(histR_), 0.0);
        std::fill(std::begin(delayL_), std::end(delayL_), 0.0);
        std::fill(std::begin(delayR_), std::end(delayR_), 0.0);
        std::fill(std::begin(rRing_), std::end(rRing_), 1.0);
        std::fill(std::begin(mRing_), std::end(mRing_), 1.0);
        hpos_ = 0;
        dpos_ = 0;
        rpos_ = 0;
        mpos_ = 0;
        mSum_ = static_cast<double>(L_ + 1);
        sinceResum_ = 0;
        g_ = 1.0;
        minGain_ = 1.0;
        quiet_ = 0;
        rMin_ = 1.0;
    }

    void setCeilingDb(double db) {
        // 0.1 dB margin covers the residual error of the 4x estimate.
        ceiling_ = dbToLin(db - 0.1);
        // Below quietLevel_ no interpolated value can exceed the ceiling (see process()). Margin 1e-9 >> rounding.
        quietLevel_ = ceiling_ / (coefAbsMax_ * (1.0 + 1e-9));
        quiet_ = 0;
    }

    void setReleaseMs(double ms) {
        releaseMs_ = clampv(ms, 1.0, 5000.0);
        relCoef_ = 1.0 - std::exp(-1.0 / (releaseMs_ * 1e-3 * fs_));
    }

    int latency() const { return kDetectDelay + L_; }
    int lookahead() const { return L_; }
    // Gain applied to the delayed sample by the most recent process() call. Audio thread only.
    double currentGain() const { return g_; }

    // Lowest gain applied since the last call (for metering).
    double takeMinGain() {
        const double m = minGain_;
        minGain_ = 1.0;
        return m;
    }

    inline void process(double inL, double inR, double& outL, double& outR) {
        // Audio delay line and interpolator history. The history is stored twice (positions h and h + kTaps), so the
        // last 32 inputs are always one contiguous run, oldest first: hist + hpos_ + 1 .. hist + hpos_ + kTaps.
        delayL_[dpos_] = inL;
        delayR_[dpos_] = inR;
        histL_[hpos_] = histL_[hpos_ + kTaps] = inL;
        histR_[hpos_] = histR_[hpos_ + kTaps] = inR;
        // Frames in a row (up to kTaps) at or below quietLevel_ in both channels. When all kTaps inputs of the window
        // are that quiet, |each interpolated value| <= sum |coef| * quietLevel_ < ceiling (rounding is far inside the
        // 1e-9 margin), so the detection below would find no peak above the ceiling: r = 1 exactly, without it.
        if (std::fabs(inL) <= quietLevel_ && std::fabs(inR) <= quietLevel_) {
            if (quiet_ < kTaps) ++quiet_;
        } else {
            quiet_ = 0;
        }

        // Detection at position j = i - D, using x[j-15] .. x[j+16] = the last 32 inputs.
        double r = 1.0;
        if (quiet_ < kTaps) {
            const double* xl = histL_ + hpos_ + 1;
            const double* xr = histR_ + hpos_ + 1;
            double peak = std::max(std::fabs(xl[15]), std::fabs(xr[15]));  // x[j] itself
            for (int p = 0; p < kPhases; ++p) {
                double yl = 0.0, yr = 0.0;
                for (int t = 0; t < kTaps; ++t) {
                    yl += coef_[p][t] * xl[t];
                    yr += coef_[p][t] * xr[t];
                }
                peak = std::max(peak, std::max(std::fabs(yl), std::fabs(yr)));
            }
            if (peak > ceiling_) r = ceiling_ / peak;
        }

        // Minimum of the required gain over the look-ahead window (L + 1 positions), kept up to date: it only has to
        // be searched again when the value leaving the window was the minimum and the new one is larger.
        const double leaving = rRing_[rpos_];
        rRing_[rpos_] = r;
        if (++rpos_ > L_) rpos_ = 0;
        if (r <= rMin_) {
            rMin_ = r;
        } else if (leaving == rMin_) {
            double mm = 1.0;
            for (int k = 0; k <= L_; ++k) mm = std::min(mm, rRing_[k]);
            rMin_ = mm;
        }
        const double m = rMin_;

        // Moving average over L + 1 values.
        mSum_ += m - mRing_[mpos_];
        mRing_[mpos_] = m;
        if (++mpos_ > L_) mpos_ = 0;
        if (++sinceResum_ >= 8192) {  // remove floating-point drift of the running sum
            sinceResum_ = 0;
            double s = 0.0;
            for (int k = 0; k <= L_; ++k) s += mRing_[k];
            mSum_ = s;
        }
        const double box = std::min(1.0, mSum_ / static_cast<double>(L_ + 1));

        // Release (attack is already shaped by the look-ahead fade).
        if (box < g_) g_ = box;
        else g_ += (box - g_) * relCoef_;
        if (g_ < minGain_) minGain_ = g_;

        // Output: the sample that entered D + L frames ago.
        const int lat = kDetectDelay + L_;
        int rd = dpos_ - lat;  // lat < kDelayLen
        if (rd < 0) rd += kDelayLen;
        outL = delayL_[rd] * g_;
        outR = delayR_[rd] * g_;

        if (++dpos_ >= kDelayLen) dpos_ = 0;
        if (++hpos_ >= kTaps) hpos_ = 0;
    }

private:

    static double besselI0(double x) {
        double sum = 1.0, term = 1.0;
        for (int k = 1; k < 50; ++k) {
            term *= (x / (2.0 * k)) * (x / (2.0 * k));
            sum += term;
            if (term < 1e-12 * sum) break;
        }
        return sum;
    }

    void initInterpolator() {
        const double beta = 9.0, R = 16.0;
        for (int p = 0; p < kPhases; ++p) {
            const double mu = (p + 1) / 8.0;
            double sum = 0.0;
            for (int t = 0; t < kTaps; ++t) {
                const double x = (t - 15) - mu;  // distance from the interpolation point
                const double s = (std::fabs(x) < 1e-12) ? 1.0 : std::sin(kPi * x) / (kPi * x);
                const double u = x / R;
                const double w = (std::fabs(u) < 1.0) ? besselI0(beta * std::sqrt(1.0 - u * u)) / besselI0(beta) : 0.0;
                coef_[p][t] = s * w;
                sum += coef_[p][t];
            }
            for (int t = 0; t < kTaps; ++t) coef_[p][t] /= sum;
        }
        coefAbsMax_ = 1.0;
        for (int p = 0; p < kPhases; ++p) {
            double a = 0.0;
            for (int t = 0; t < kTaps; ++t) a += std::fabs(coef_[p][t]);
            coefAbsMax_ = std::max(coefAbsMax_, a);
        }
        quietLevel_ = ceiling_ / (coefAbsMax_ * (1.0 + 1e-9));
    }

    double coef_[kPhases][kTaps] = {};
    double coefAbsMax_ = 1.0;       // max over phases of sum |coef|
    double quietLevel_ = 0.0;       // see process()
    int quiet_ = 0;
    double rMin_ = 1.0;             // minimum of rRing_
    double histL_[2 * kTaps] = {}, histR_[2 * kTaps] = {};
    double delayL_[kDelayLen] = {}, delayR_[kDelayLen] = {};
    double rRing_[kMaxLookahead + 1] = {};
    double mRing_[kMaxLookahead + 1] = {};
    int hpos_ = 0, dpos_ = 0, rpos_ = 0, mpos_ = 0, sinceResum_ = 0;
    int L_ = 72;
    double fs_ = 48000.0;
    double mSum_ = 73.0;
    double ceiling_ = 0.8799;
    double releaseMs_ = 60.0;
    double relCoef_ = 0.0;
    double g_ = 1.0;
    double minGain_ = 1.0;
};

// ------------------------------------------------------------------------------------------------
// Live loudness match ("끌 때 음량 맞춤"): the gain that makes the unprocessed input as loud as the processed output.
//
// Loudness here is a proxy: energy after an approximate K-shaped weighting times the measured response of the
// phone speaker (third octaves 125 Hz - 16 kHz, tools/pvb-harness/study/phone_model.py), fitted with six RBJ biquads
// (shape error after removing constant offset, 125 Hz to 12.5 kHz: rms <0.7 dB, max <2 dB at 44.1/48 kHz).
// It approximates the spectral weighting used by the blind-comparison trims. The speaker weighting discounts
// sub-bass that the speaker cannot play. This detector omits the nonlinear phone model used for those trims;
// agreement with ISO 532-1 or perceived loudness has not been established.
// Sum channel powers after weighting; opposite-polarity stereo must not disappear from the detector.
// This is not a calibrated acoustic loudness meter. Phone dynamics and listening position remain unmodelled.
//
// Both weighted energies are averaged with one time constant (about 10 s), as energies (loud passages count most,
// like integrated loudness); steps whose weighted input is below -70 dB are skipped, so pauses and silence between
// tracks keep the value. gain = sqrt(E_out / E_in), clamped to [kMinDb, kMaxDb]. The applied gain glides over each
// step (no zipper noise). Until the first measured step the gain is the seed (the value the app saved last time).
// ------------------------------------------------------------------------------------------------
class LoudnessMatcher {
public:
    static constexpr double kMinDb = -30.0;
    static constexpr double kMaxDb = 3.0;
    static constexpr double kTauS = 10.0;
    static constexpr double kStepS = 0.02;
    static constexpr double kSilenceMs = 1e-7;  // -70 dB, weighted mean square of the input
    static constexpr int kSections = 6;

    void configure(double fs) {
        fs_ = fs;
        // high-pass 60.7 Hz Q 0.40, high-pass 343.8 Hz Q 0.986, bells 2726 Hz +8.83 dB Q 1.454, 5119 Hz +11.29 dB
        // Q 1.449, 432.3 Hz -8.67 dB Q 1.170, low-pass 7436 Hz Q 2.082 (tools/pvb-harness/match/fit_weighting.py)
        coef_[0] = rbj(0, 60.7, 0.0, 0.40);
        coef_[1] = rbj(0, 343.8, 0.0, 0.986);
        coef_[2] = rbj(2, 2726.0, 8.83, 1.454);
        coef_[3] = rbj(2, 5119.0, 11.29, 1.449);
        coef_[4] = rbj(2, 432.3, -8.67, 1.170);
        coef_[5] = rbj(1, 7436.0, 0.0, 2.082);
        step_ = std::max(1, static_cast<int>(std::lround(kStepS * fs)));
        alpha_ = 1.0 - std::exp(-static_cast<double>(step_) / (kTauS * fs));
        resetFilters();
        gain_.snap(gain_.target());  // a new rate: finish the glide (the measured ratio stays valid)
    }

    // Filter memory and the step in progress (the averages and the gain stay: they describe the music, not a buffer).
    void resetFilters() {
        for (auto& channel : stIn_) for (auto& s : channel) s = State{};
        for (auto& channel : stOut_) for (auto& s : channel) s = State{};
        accIn_ = accOut_ = 0.0;
        count_ = 0;
    }

    // Starting value until the first measured step (any number of calls; ignored once measured).
    void seed(double db) {
        if (measured_) return;
        db = clampv(db, kMinDb, kMaxDb);
        gainDb_ = db;
        gain_.snap(dbToLin(db));
    }

    void setHold(bool hold) { hold_ = hold; }
    bool measured() const { return measured_; }
    double gainDb() const { return gainDb_; }

    // One stereo frame, time aligned, before output gates and switching fades.
    inline void push(double il, double ir, double ol, double oright) {
        const double wil = weigh(stIn_[0], il), wir = weigh(stIn_[1], ir);
        const double wol = weigh(stOut_[0], ol), wor = weigh(stOut_[1], oright);
        accIn_ += 0.5 * (wil * wil + wir * wir);
        accOut_ += 0.5 * (wol * wol + wor * wor);
        if (++count_ >= step_) update();
    }

    // Gain for the next frame (glides over a step).
    inline double nextGain() { return gain_.next(); }

    void flushTiny() {
        for (int ch = 0; ch < 2; ++ch) for (int k = 0; k < kSections; ++k) {
            flush(stIn_[ch][k]);
            flush(stOut_[ch][k]);
        }
    }

private:
    struct Coef {
        double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    };
    struct State {
        double s1 = 0, s2 = 0;
    };
    static void flush(State& s) {
        if (std::fabs(s.s1) < 1e-25) s.s1 = 0.0;
        if (std::fabs(s.s2) < 1e-25) s.s2 = 0.0;
    }

    // kind: 0 = high-pass, 1 = low-pass, 2 = bell (RBJ cookbook)
    Coef rbj(int kind, double f, double db, double q) const {
        const double A = std::pow(10.0, db / 40.0);
        const double w = 2.0 * kPi * clampv(f, 1.0, 0.45 * fs_) / fs_;
        const double al = std::sin(w) / (2.0 * q), c = std::cos(w);
        double b0, b1, b2, a0, a1, a2;
        if (kind == 0) {
            b0 = (1 + c) / 2; b1 = -(1 + c); b2 = (1 + c) / 2; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al;
        } else if (kind == 1) {
            b0 = (1 - c) / 2; b1 = 1 - c; b2 = (1 - c) / 2; a0 = 1 + al; a1 = -2 * c; a2 = 1 - al;
        } else {
            b0 = 1 + al * A; b1 = -2 * c; b2 = 1 - al * A; a0 = 1 + al / A; a1 = -2 * c; a2 = 1 - al / A;
        }
        Coef k;
        k.b0 = b0 / a0; k.b1 = b1 / a0; k.b2 = b2 / a0; k.a1 = a1 / a0; k.a2 = a2 / a0;
        return k;
    }

    inline double weigh(State* st, double x) const {
        for (int k = 0; k < kSections; ++k) {
            const Coef& c = coef_[k];
            State& s = st[k];
            const double y = c.b0 * x + s.s1;  // direct form II transposed
            s.s1 = c.b1 * x - c.a1 * y + s.s2;
            s.s2 = c.b2 * x - c.a2 * y;
            x = y;
        }
        return x;
    }

    void update() {
        const double mi = accIn_ / count_, mo = accOut_ / count_;
        accIn_ = accOut_ = 0.0;
        count_ = 0;
        if (hold_ || !std::isfinite(mi) || !std::isfinite(mo) || mi < kSilenceMs) return;
        if (!measured_) {
            // the seed stands for the past: same energy as this step, the seed's ratio
            eIn_ = mi;
            eOut_ = mi * dbToLin(2.0 * gainDb_);
            measured_ = true;
        }
        eIn_ += (mi - eIn_) * alpha_;
        eOut_ += (mo - eOut_) * alpha_;
        gainDb_ = clampv(10.0 * std::log10(std::max(eOut_, 1e-30) / std::max(eIn_, 1e-30)), kMinDb, kMaxDb);
        gain_.setTarget(dbToLin(gainDb_), step_);
    }

    Coef coef_[kSections];
    State stIn_[2][kSections], stOut_[2][kSections];
    double fs_ = 48000.0;
    int step_ = 960, count_ = 0;
    double alpha_ = 0.0, accIn_ = 0.0, accOut_ = 0.0, eIn_ = 0.0, eOut_ = 0.0;
    double gainDb_ = -6.0;
    bool measured_ = false, hold_ = false;
    RampedValue gain_;

public:
    LoudnessMatcher() { gain_.snap(dbToLin(gainDb_)); }
};

}  // namespace pvb


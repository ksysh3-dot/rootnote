// GPL-3.0. Stereo, linear-phase rational conversion for the harmonic branch.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>

namespace pvb {
struct RatePair { double l = 0, r = 0; };

template<int Phases>
class RateFilter {
public:
    static constexpr int taps = 90;
    struct Bank {
        struct Row { int offset; std::array<double, taps> weights; };
        std::array<Row, Phases> rows;
        Bank(int rate, double delay, int direction) {
            constexpr double pi = 3.14159265358979323846, beta = 11.4;
            const double radius = rate == 44100 ? 41. : 44.;
            const double cutoff = 2. * 20025. / rate;
            for (int p = 0; p < Phases; ++p) {
                const double center = delay + direction * double(p) / Phases;
                Row& row = rows[p];
                row.offset = int(std::floor(center - radius));
                for (int i = 0; i < taps; ++i) {
                    const double x = row.offset + i - center;
                    const double z = x / radius;
                    row.weights[i] = std::abs(z) > 1. ? 0. :
                        (std::abs(x) < 1e-13 ? cutoff : std::sin(pi*cutoff*x)/(pi*x)) *
                        i0(beta*std::sqrt(std::max(0., 1.-z*z))) / i0(beta);
                }
            }
        }
    private:
        static double i0(double x) {
            double term = 1., sum = 1.;
            for (int k = 1; k <= 40; ++k) { term *= (x*x)/(4.*k*k); sum += term; }
            return sum;
        }
    };
    void reset() { history_.fill({}); pos_ = 0; }
    void push(RatePair in) {
        pos_ = (pos_ - 1) & (size - 1);
        history_[pos_] = history_[pos_ + size] = in;
    }
    RatePair read(const Bank& bank, int phase, int older = 0) const {
        const auto& row = bank.rows[phase];
        const auto* in = history_.data() + pos_ + row.offset + older;
        RatePair out;
        for (int i = 0; i < taps; ++i) {
            out.l += row.weights[i] * in[i].l;
            out.r += row.weights[i] * in[i].r;
        }
        return out;
    }
private:
    static constexpr int size = 128;
    std::array<RatePair, size*2> history_{};
    int pos_ = 0;
};

class HarmonicRateIsland {
public:
    // 160 ticks per host frame, 147 per generator frame.
    static constexpr int upDelay = 46;       // generator frames of input look-ahead
    static constexpr int downDelay = 6742;   // common-clock ticks
    static constexpr int alignTicks = 92;    // separate delay before output conversion
    static_assert(((6048 + upDelay)*147 + downDelay) % 160 == 0);
    static_assert(((7052 + upDelay)*147 + downDelay + alignTicks) % 160 == 0);
    static constexpr double returnDelay() { return (downDelay + alignTicks)/160.; }
    static const RateFilter<160>::Bank& upBank() {
        static const RateFilter<160>::Bank bank(44100, upDelay*147./160, 1);
        return bank;
    }
    static const RateFilter<147>::Bank& downBank() {
        static const RateFilter<147>::Bank bank(48000, downDelay/147., -1);
        return bank;
    }
    static void prepareBanks() { (void)upBank(); (void)downBank(); }
    void prepare() { upBank_ = &upBank(); downBank_ = &downBank(); }
    int phaseTicks() const { return phase_; }
    static double sourceOffset(double frames, int phase) {
        return ((frames - upDelay)*147. - phase)/160.;
    }
    static double outputOffset(double frames, int phase) {
        return (frames*147. - phase)/160. + returnDelay();
    }
    static int latency(int nativeFrames) {
        return ((nativeFrames + upDelay)*147 + downDelay + alignTicks)/160;
    }
    void reset() {
        up_.reset(); left_.fill(0.); right_.fill(0.); side_.fill({});
        downPos_ = stereoHistory_ = 0;
        phase_ = sidePos_ = 0;
        lookahead_ = upDelay;
    }
    RatePair sidechain(RatePair input, int delay) {
        const auto result = side_[(sidePos_ - delay + 8192) & 8191];
        side_[sidePos_] = input; sidePos_ = (sidePos_+1)&8191;
        return result;
    }
    template<class Generate>
    RatePair tick(RatePair input, Generate generate) {
        up_.push(input);
        // Generate through floor(n*160/147), inclusive, before reading output n.
        while (phase_ >= 0) {
            // The first centered input sample belongs to source time zero.
            // Earlier positions are the output filter's zero initial condition.
            if (lookahead_ > 0) --lookahead_;
            else pushReturn(generate(up_.read(*upBank_, phase_)));
            phase_ -= 147;
        }
        const int fraction = phase_ + 147 - alignTicks;
        const auto result = readReturn((fraction + 147) % 147, fraction < 0);
        phase_ += 160;
        return result;
    }
private:
    const RateFilter<160>::Bank* upBank_ = nullptr;
    const RateFilter<147>::Bank* downBank_ = nullptr;
    RateFilter<160> up_;
    static constexpr int historySize = 128;
    std::array<double, historySize*2> left_{}, right_{};
    int downPos_ = 0, stereoHistory_ = 0;
    void pushReturn(RatePair v) {
        downPos_ = (downPos_ - 1) & (historySize - 1);
        left_[downPos_] = left_[downPos_ + historySize] = v.l;
        right_[downPos_] = right_[downPos_ + historySize] = v.r;
        if (std::memcmp(&v.l, &v.r, sizeof(double)) != 0) stereoHistory_ = historySize;
        else if (stereoHistory_) --stereoHistory_;
    }
    RatePair readReturn(int phase, int older) const {
        const auto& row = downBank_->rows[phase];
        const int start = downPos_ + row.offset + older;
        auto filter = [&](const auto& samples) {
            double sum = 0.;
            for (int i = 0; i < RateFilter<147>::taps; ++i)
                sum += row.weights[i] * samples[start+i];
            return sum;
        };
        const double l = filter(left_);
        return {l, stereoHistory_ ? filter(right_) : l};
    }
    std::array<RatePair, 8192> side_{};
    int phase_ = 0, lookahead_ = upDelay, sidePos_ = 0;
};
}

// PVB speaker engine - live spectrum analysis. See pvb_analysis.h.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include <chrono>
#include <complex>
#include <limits>

#include "pvb_engine.h"

namespace pvb {

namespace {

constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();
constexpr double kFloorDb = -160.0;
constexpr double kRiseS = 0.03;        // display: rise time constant
constexpr double kFallDbPerS = 30.0;   // display: fall rate
constexpr double kDiffS = 0.12;        // measured change: smoothing time constant
constexpr double kDiffMinInDb = -110.0;

// Magnitude (dB) of the trapezoidal SVF at frequency f. With g = tan(pi fc / fs) the digital filter is
// the bilinear transform of the analogue prototype, so its response at f equals the prototype at
// Omega = tan(pi f / fs) / g:  H = m0 + m1 * jW / (1 - W^2 + jkW) + m2 / (1 - W^2 + jkW).
double svfMagDb(const double* c, double f, double fs) {
    const double g = c[0], k = c[1], m0 = c[2], m1 = c[3], m2 = c[4];
    if (g <= 0.0) return 0.0;
    const double w = std::tan(kPi * f / fs) / g;
    const std::complex<double> jw(0.0, w);
    const std::complex<double> den(1.0 - w * w, k * w);
    const std::complex<double> h = m0 + (m1 * jw + m2) / den;
    return 10.0 * std::log10(std::max(std::norm(h), 1e-30));
}

}  // namespace

struct AnalysisState {
    // FFT tables (fixed size).
    std::vector<double> window, cosT, sinT;
    std::vector<int> bitrev;
    double norm = 1.0;  // power scale: a full-scale sine at a bin centre reads 0 dB in that bin

    // Band map for the current (sample rate, point count).
    struct Band {
        int a = -1, b = -1;  // inclusive bin range, or a < 0 for interpolation at (i0, t)
        int i0 = 0;
        double t = 0.0;
        bool none = false;   // above Nyquist
    };
    int mapSr = 0, mapPts = 0;
    std::vector<Band> bands;
    std::vector<double> freqs;

    // Work buffers.
    std::vector<float> frameIn, frameOut;   // interleaved stereo, kAnaFft frames
    std::vector<double> re, im, power;
    std::vector<double> rawIn, rawOut;

    // Display state.
    std::vector<double> sIn, sOut, sDiff;
    uint64_t lastFrames = 0;
    uint64_t dropped = 0;  // windows dropped because the audio thread overtook the copy
    bool haveTime = false;
    std::chrono::steady_clock::time_point lastTime;

    AnalysisState() {
        const int n = kAnaFft;
        window.resize(n);
        double sum = 0.0;
        for (int i = 0; i < n; ++i) {
            const double x = 2.0 * kPi * i / n;  // periodic 4-term Blackman-Harris (sidelobes -92 dB)
            window[i] = 0.35875 - 0.48829 * std::cos(x) + 0.14128 * std::cos(2 * x) - 0.01168 * std::cos(3 * x);
            sum += window[i];
        }
        norm = 4.0 / (sum * sum);
        cosT.resize(n / 2);
        sinT.resize(n / 2);
        for (int i = 0; i < n / 2; ++i) {
            cosT[i] = std::cos(2.0 * kPi * i / n);
            sinT[i] = -std::sin(2.0 * kPi * i / n);
        }
        bitrev.resize(n);
        int bits = 0;
        while ((1 << bits) < n) ++bits;
        for (int i = 0; i < n; ++i) {
            int r = 0;
            for (int b = 0; b < bits; ++b) r |= ((i >> b) & 1) << (bits - 1 - b);
            bitrev[i] = r;
        }
        frameIn.resize(2 * n);
        frameOut.resize(2 * n);
        re.resize(n);
        im.resize(n);
        power.resize(n / 2 + 1);
    }

    void prepare(int sr, int pts) {
        if (sr == mapSr && pts == mapPts) return;
        mapSr = sr;
        mapPts = pts;
        bands.assign(pts, Band());
        freqs.resize(pts);
        const double binHz = static_cast<double>(sr) / kAnaFft;
        const int half = kAnaFft / 2;
        for (int i = 0; i < pts; ++i) {
            const double f = anaPointHz(i, pts);
            freqs[i] = f;
            Band& b = bands[i];
            if (f >= 0.499 * sr) {
                b.none = true;
                continue;
            }
            const double lo = f * std::pow(2.0, -1.0 / 24.0) / binHz;
            const double hi = f * std::pow(2.0, 1.0 / 24.0) / binHz;
            const int a = std::max(1, static_cast<int>(std::ceil(lo)));
            const int e = std::min(half - 1, static_cast<int>(std::floor(hi)));
            if (a <= e) {
                b.a = a;
                b.b = e;
            } else {
                const double x = f / binHz;
                b.i0 = clampv(static_cast<int>(std::floor(x)), 0, half - 1);
                b.t = x - b.i0;
            }
        }
        rawIn.assign(pts, kFloorDb);
        rawOut.assign(pts, kFloorDb);
        sIn.assign(pts, kFloorDb);
        sOut.assign(pts, kFloorDb);
        sDiff.assign(pts, std::numeric_limits<double>::quiet_NaN());
    }

    // Power spectrum of an interleaved stereo frame, averaged over the two channels. Left goes into the
    // real part and right into the imaginary part of one complex FFT; then
    // (|L_k|^2 + |R_k|^2) / 2 = (|Z_k|^2 + |Z_{N-k}|^2) / 4.
    void spectrum(const float* lr) {
        const int n = kAnaFft;
        for (int i = 0; i < n; ++i) {
            float l = lr[2 * i], r = lr[2 * i + 1];
            if (!isFiniteBits(l)) l = 0.f;
            if (!isFiniteBits(r)) r = 0.f;
            const int j = bitrev[i];
            re[j] = l * window[i];
            im[j] = r * window[i];
        }
        for (int len = 2; len <= n; len <<= 1) {
            const int half = len >> 1, step = n / len;
            for (int i = 0; i < n; i += len) {
                for (int k = 0; k < half; ++k) {
                    const double wr = cosT[k * step], wi = sinT[k * step];
                    const int p = i + k, q = p + half;
                    const double tr = re[q] * wr - im[q] * wi;
                    const double ti = re[q] * wi + im[q] * wr;
                    re[q] = re[p] - tr;
                    im[q] = im[p] - ti;
                    re[p] += tr;
                    im[p] += ti;
                }
            }
        }
        for (int k = 0; k <= n / 2; ++k) {
            const int m = (n - k) & (n - 1);
            const double a = re[k] * re[k] + im[k] * im[k];
            const double b = re[m] * re[m] + im[m] * im[m];
            power[k] = 0.25 * (a + b) * norm;
        }
    }

    void band(std::vector<double>& out) const {
        for (size_t i = 0; i < bands.size(); ++i) {
            const Band& b = bands[i];
            if (b.none) {
                out[i] = std::numeric_limits<double>::quiet_NaN();
                continue;
            }
            double p;
            if (b.a >= 0) {
                p = 0.0;
                for (int k = b.a; k <= b.b; ++k) p += power[k];
                p /= (b.b - b.a + 1);
            } else {
                const int i1 = std::min(b.i0 + 1, kAnaFft / 2);
                p = power[b.i0] + (power[i1] - power[b.i0]) * b.t;
            }
            out[i] = std::max(kFloorDb, 10.0 * std::log10(std::max(p, 1e-30)));
        }
    }
};

Engine::~Engine() { delete ana_; }

int Engine::analyze(float* inDb, float* outDb, float* diffDb, float* eqDb, int nPts, float* info, int nInfo,
                    double dtSeconds) {
    if (inDb == nullptr || outDb == nullptr || diffDb == nullptr || eqDb == nullptr) return 0;
    if (nPts < 2 || nPts > kAnaMaxPoints) return 0;

    std::lock_guard<std::mutex> lock(anaMtx_);
    if (ana_ == nullptr) ana_ = new AnalysisState();
    AnalysisState& A = *ana_;

    const int sr = srMeter_.load(std::memory_order_relaxed);
    A.prepare(sr, nPts);


    // Filter coefficients and gains in use (sequence counter: retry while the audio thread writes).
    double c[kPubCount];
    for (int attempt = 0;; ++attempt) {
        const uint32_t s0 = pubSeq_.load(std::memory_order_acquire);
        for (int i = 0; i < kPubCount; ++i) c[i] = pub_[i].load(std::memory_order_relaxed);
        std::atomic_thread_fence(std::memory_order_acquire);
        const uint32_t s1 = pubSeq_.load(std::memory_order_relaxed);
        if ((s0 & 1u) == 0 && s0 == s1) break;
        if (attempt > 1000) break;  // cannot happen in practice; use what we have
    }
    const double outGainDb = linToDb(std::max(c[15], 1e-6));
    const double mix = clampv(c[16], 0.0, 1.0);
    const double lowDbNow = c[17];
    const double bypassDb = c[23];  // flat bypass: its loudness-match gain (0 = plain bypass)

    const uint64_t total = tapFrames_.load(std::memory_order_acquire);
    bool fresh = total != A.lastFrames;
    if (fresh) {
        const int n = kAnaFft;
        const int lat = latency_.load(std::memory_order_relaxed);
        // Output: the newest n frames. Input: the n frames that produced them (latency earlier).
        for (int i = 0; i < n; ++i) {
            const int64_t to = static_cast<int64_t>(total) - n + i;
            const int64_t ti = to - lat;
            if (to >= 0) {
                const size_t k = static_cast<size_t>(to & (kAnaRing - 1));
                A.frameOut[2 * i] = tapOut_[2 * k].load(std::memory_order_relaxed);
                A.frameOut[2 * i + 1] = tapOut_[2 * k + 1].load(std::memory_order_relaxed);
            } else {
                A.frameOut[2 * i] = A.frameOut[2 * i + 1] = 0.f;
            }
            if (ti >= 0) {
                const size_t k = static_cast<size_t>(ti & (kAnaRing - 1));
                A.frameIn[2 * i] = tapIn_[2 * k].load(std::memory_order_relaxed);
                A.frameIn[2 * i + 1] = tapIn_[2 * k + 1].load(std::memory_order_relaxed);
            } else {
                A.frameIn[2 * i] = A.frameIn[2 * i + 1] = 0.f;
            }
        }
        // Did the audio thread reach any of the copied frames meanwhile? The oldest copied frame is
        // total - n - lat; the writer overwrites it once it writes frame (total - n - lat) + kAnaRing.
        std::atomic_thread_fence(std::memory_order_acquire);
        const uint64_t writeEnd = tapWriteEnd_.load(std::memory_order_relaxed);
        const int64_t oldest = static_cast<int64_t>(total) - n - lat;
        if (static_cast<int64_t>(writeEnd) > oldest + kAnaRing) {
            fresh = false;  // this window may be torn: drop it, keep showing the previous one
            A.dropped++;
        }
    }
    if (fresh) {
        A.lastFrames = total;
        // Display smoothing runs per new frame of audio, so its time step is the time since the previous
        // fresh call (blocks can arrive less often than the caller polls).
        const auto now = std::chrono::steady_clock::now();
        double dt = dtSeconds;
        if (dt < 0.0) dt = A.haveTime ? std::chrono::duration<double>(now - A.lastTime).count() : 1.0;
        dt = clampv(dt, 0.0, 10.0);
        A.lastTime = now;
        A.haveTime = true;

        A.spectrum(A.frameIn.data());
        A.band(A.rawIn);
        A.spectrum(A.frameOut.data());
        A.band(A.rawOut);

        const double rise = 1.0 - std::exp(-dt / kRiseS);
        const double diffK = 1.0 - std::exp(-dt / kDiffS);
        const double fall = kFallDbPerS * dt;
        for (int i = 0; i < nPts; ++i) {
            for (int which = 0; which < 2; ++which) {
                const double x = which == 0 ? A.rawIn[i] : A.rawOut[i];
                double& s = which == 0 ? A.sIn[i] : A.sOut[i];
                if (!isFiniteBits(x)) {
                    s = x;
                } else if (!isFiniteBits(s) || x >= s) {
                    s = isFiniteBits(s) ? s + (x - s) * rise : x;
                } else {
                    s = std::max(x, s - fall);
                }
            }
            const double ri = A.rawIn[i], ro = A.rawOut[i];
            double& sd = A.sDiff[i];
            if (isFiniteBits(ri) && isFiniteBits(ro) && ri > kDiffMinInDb) {
                const double d = ro - ri - mix * outGainDb - (1.0 - mix) * bypassDb;
                sd = isFiniteBits(sd) ? sd + (d - sd) * diffK : d;
            } else {
                sd = std::numeric_limits<double>::quiet_NaN();
            }
        }
    }

    for (int i = 0; i < nPts; ++i) {
        inDb[i] = static_cast<float>(A.sIn[i]);
        outDb[i] = static_cast<float>(A.sOut[i]);
        diffDb[i] = static_cast<float>(A.sDiff[i]);
        const double f = A.freqs[i];
        if (A.bands[i].none) {
            eqDb[i] = kNaN;
        } else {
            eqDb[i] = static_cast<float>(2.0 * svfMagDb(c + 0, f, sr) + svfMagDb(c + 5, f, sr) + svfMagDb(c + 10, f, sr) +
                                         svfMagDb(c + 18, f, sr));
        }
    }

    if (info != nullptr && nInfo > 0) {
        float v[A_COUNT];
        v[A_FRESH] = fresh ? 1.f : 0.f;
        v[A_LIM_GR_DB] = static_cast<float>(std::max(0.0, -linToDb(anaLimMin_.exchange(1.f, std::memory_order_relaxed))));
        v[A_EST_GR_DB] = mEstGr_.load(std::memory_order_relaxed);
        v[A_LOW_DB_NOW] = static_cast<float>(lowDbNow);
        v[A_MIX] = static_cast<float>(mix);
        v[A_OUT_DB] = static_cast<float>(outGainDb);
        v[A_SAMPLE_RATE] = static_cast<float>(sr);
        v[A_DYN_DB] = mDyn_.load(std::memory_order_relaxed);
        const int n = nInfo < A_COUNT ? nInfo : static_cast<int>(A_COUNT);
        for (int i = 0; i < n; ++i) info[i] = v[i];
    }
    return nPts;
}

}  // namespace pvb

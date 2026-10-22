// The P1 modulation fit (pvb_vb_modulation.h) against a frozen copy of the original implementation
// (ref/pvb_vb_modulation_ref.h), on synthetic 128 ms frames: the speed-up (normal equations with refinement, the
// original Gram-Schmidt only for poorly conditioned solves, vectorised sums, fastmath sine/cosine) must not change
// any acceptance decision and may change the accepted parameters only far below audibility. On real music the
// accepted fits agree to about 1e-13 (relative); on these synthetic frames, built to stress the method (strong
// polynomial envelopes, steep glides, close neighbours), the 4-step carrier iteration can take a slightly different
// path, and the worst accepted fit differs by about 1e-9 Hz.
//
//   g++ -std=c++17 -O2 -Iapp/src/main/cpp/libpvb tools/pvb-harness/fit_equivalence.cpp -o /tmp/fit && /tmp/fit
#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

#include "pvb_vb_modulation.h"
#include "ref/pvb_vb_modulation_ref.h"

using namespace pvb;

namespace {
constexpr int N = modulation::N;
constexpr double Fs = modulation::Fs, Pi = modulation::Pi;

struct Frame {
    double x[N];
    double seed = 60;
    double neighbors[3] = {};
    int count = 0;
};

// Partials with a polynomial amplitude envelope and a frequency glide, plus white noise. kind selects the scene.
Frame makeFrame(std::mt19937_64& g, int kind) {
    std::uniform_real_distribution<double> U(0, 1);
    Frame f;
    int partials = 1;
    double noise = 1e-4;
    switch (kind) {
        case 0: partials = 1; noise = std::pow(10, -1 - 4 * U(g)); break;               // clean tone (valid fits)
        case 1: partials = 2 + static_cast<int>(3 * U(g)); noise = std::pow(10, -2 - 3 * U(g)); break;  // chords
        case 2: partials = 1; noise = std::pow(10, -0.3 - U(g)); break;                  // noisy (residual near -20 dB)
        case 3: partials = 0; noise = 0.1; break;                                         // noise only
        case 4: partials = 2; noise = 1e-3; break;                                        // close neighbour
        default: partials = 1; noise = 0; break;                                          // pure, extreme slopes
    }
    double freqs[6];
    for (int n = 0; n < N; ++n) f.x[n] = 0;
    for (int p = 0; p < partials; ++p) {
        const double hz = 25 + 165 * U(g);
        freqs[p] = hz;
        const double amp = std::pow(10, -2 * U(g)) * (p == 0 ? 1.0 : 0.7);
        const double ph = 2 * Pi * U(g);
        const double slope = (kind == 5 ? 800 : 160) * (U(g) - 0.5);
        const double a1 = 0.6 * (U(g) - 0.5), a2 = 0.4 * (U(g) - 0.5);
        for (int n = 0; n < N; ++n) {
            const double t = (n - N / 2) / Fs, u = t / modulation::Half;
            f.x[n] += amp * (1 + a1 * u + a2 * u * u) * std::cos(2 * Pi * hz * t + Pi * slope * t * t + ph);
        }
    }
    std::normal_distribution<double> G(0, 1);
    for (int n = 0; n < N; ++n) f.x[n] += noise * G(g);
    f.seed = partials ? freqs[0] + 3 * (U(g) - 0.5) : 25 + 165 * U(g);
    if (kind == 4) {
        // a neighbour 12-14 Hz from the carrier: the most collinear case the vocoder can produce
        f.count = 1;
        f.neighbors[0] = f.seed + (U(g) < 0.5 ? -1 : 1) * (12 + 2 * U(g));
    } else {
        f.count = static_cast<int>(4 * U(g));
        for (int j = 0; j < f.count; ++j)
            f.neighbors[j] = j + 1 < partials ? freqs[j + 1] : 25 + 175 * U(g);
    }
    return f;
}

int failures = 0;
void check(bool ok, const char* what) {
    std::printf("[%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++failures;
}

// A decision may differ only where the original itself sits on a threshold (to rounding).
bool nearThreshold(const ModulationFit& m) {
    return std::fabs(m.residual + 20) < 1e-6 || std::fabs(m.qrDiagonalRatio / 1e4 - 1) < 1e-6 ||
           std::fabs(m.frequency - 25) < 1e-6 || std::fabs(m.frequency - 190) < 1e-6;
}
}  // namespace

int main() {
    std::mt19937_64 g(20261022);
    const int perKind = 4000;
    std::vector<Frame> frames;
    for (int kind = 0; kind < 6; ++kind)
        for (int i = 0; i < perKind; ++i) frames.push_back(makeFrame(g, kind));
    // edge cases: silence, tiny values, a seed outside the band, an exact neighbour duplicate (singular)
    {
        Frame f;
        for (double& v : f.x) v = 0;
        frames.push_back(f);
        for (int n = 0; n < N; ++n) f.x[n] = 1e-9 * std::cos(2 * Pi * 60 * (n - N / 2) / Fs);
        frames.push_back(f);
        f.seed = 230;
        frames.push_back(f);
        for (int n = 0; n < N; ++n) f.x[n] = std::cos(2 * Pi * 80 * (n - N / 2) / Fs);
        f.seed = 80; f.count = 2; f.neighbors[0] = 80; f.neighbors[1] = 140;
        frames.push_back(f);
    }

    std::vector<ModulationFit> a(frames.size()), b(frames.size());
    const auto t0 = std::chrono::steady_clock::now();
    for (size_t i = 0; i < frames.size(); ++i)
        a[i] = modulation_ref::fit(frames[i].x, frames[i].seed, frames[i].neighbors, frames[i].count);
    const auto t1 = std::chrono::steady_clock::now();
    for (size_t i = 0; i < frames.size(); ++i)
        b[i] = modulation::fit(frames[i].x, frames[i].seed, frames[i].neighbors, frames[i].count);
    const auto t2 = std::chrono::steady_clock::now();

    size_t valid = 0, mismatch = 0, excused = 0;
    double dF = 0, dA = 0, dP = 0, dAs = 0, dFs = 0, dR = 0, dQ = 0;  // dR: residuals above -120 dB only
    for (size_t i = 0; i < frames.size(); ++i) {
        const ModulationFit &p = a[i], &q = b[i];
        valid += p.valid;
        if (p.valid != q.valid) {
            if (nearThreshold(p)) ++excused;
            else {
                ++mismatch;
                std::printf("  decision differs #%zu: residual %.9f/%.9f ratio %.6g/%.6g f %.9f/%.9f\n", i, p.residual,
                            q.residual, p.qrDiagonalRatio, q.qrDiagonalRatio, p.frequency, q.frequency);
            }
            continue;
        }
        if (!p.valid) continue;
        dF = std::max(dF, std::fabs(p.frequency - q.frequency));
        dA = std::max(dA, std::fabs(p.amplitude - q.amplitude) / p.amplitude);
        dP = std::max(dP, std::fabs(std::remainder(p.phase - q.phase, 2 * Pi)));
        dAs = std::max(dAs, std::fabs(p.amplitudeSlope - q.amplitudeSlope) / std::max(std::fabs(p.amplitudeSlope), p.amplitude));
        dFs = std::max(dFs, std::fabs(p.frequencySlope - q.frequencySlope));
        if (p.residual > -120) dR = std::max(dR, std::fabs(p.residual - q.residual));  // below: rounding noise
        dQ = std::max(dQ, std::fabs(p.qrDiagonalRatio - q.qrDiagonalRatio) / p.qrDiagonalRatio);
    }
    std::printf("frames %zu, accepted by the original %zu, decisions differing %zu (+%zu on a threshold)\n",
                frames.size(), valid, mismatch, excused);
    std::printf("accepted fits, largest difference: frequency %.2e Hz, amplitude %.2e (rel), phase %.2e rad,\n"
                "  amplitude slope %.2e (rel), frequency slope %.2e Hz/s, residual %.2e dB, diagonal ratio %.2e (rel)\n",
                dF, dA, dP, dAs, dFs, dR, dQ);
    const double ta = std::chrono::duration<double>(t1 - t0).count(), tb = std::chrono::duration<double>(t2 - t1).count();
    std::printf("time per fit: original %.1f us, now %.1f us (%.1fx)\n", 1e6 * ta / frames.size(),
                1e6 * tb / frames.size(), ta / tb);

    check(valid > 3000, "the synthetic set has plenty of accepted fits");
    check(mismatch == 0, "no acceptance decision differs (away from a threshold)");
    check(dF < 1e-7 && dA < 1e-7 && dP < 1e-7 && dAs < 1e-6 && dFs < 1e-3 && dR < 1e-6 && dQ < 1e-7,
          "accepted parameters agree far below audibility (< 1e-7)");

    // Both solve paths are exercised: normal equations for a clean frame, the original method for a collinear one.
    {
        Frame f;
        for (int n = 0; n < N; ++n) f.x[n] = std::cos(2 * Pi * 70 * (n - N / 2) / Fs);
        modulation::Solver s(f.x);
        double c[modulation::Columns] = {};
        const double nb[3] = {130, 160, 33};
        s.solve(70, 0, nb, 3, c);
        check(s.usedGram, "a well-conditioned solve uses the normal equations");
        const double close[1] = {70.0001};
        modulation::Solver s2(f.x);
        s2.solve(70, 0, close, 1, c);
        check(!s2.usedGram, "a nearly collinear solve falls back to the original method");
    }
    std::printf(failures ? "fit_equivalence: %d FAILED\n" : "fit_equivalence: all passed\n", failures);
    return failures ? 1 : 0;
}

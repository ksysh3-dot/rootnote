#pragma once
// P1 host research: 128-ms complex polynomial envelope, not source separation.
// Numerical fit acceptance is NOT an instrument/buzz/quality probability.
//
// Cost (2026-10-22 profile): this fit runs once per vocoder frame (187.5 per second) and solves the least-squares
// problem 2 to 5 times, so it was about three quarters of the whole engine's CPU time with P1 on. The solver below is
// the same algorithm as before (the same columns in the same order, modified Gram-Schmidt with two passes, the same
// checks), arranged for speed:
//   - the window, time and polynomial axes are one shared table (they never change);
//   - sine and cosine come from fastmath::sincos (no library calls, so the column loops vectorise; within 0.8 ulp);
//   - the neighbour columns do not depend on the carrier or the slope: they are built once per frame, not per solve;
//   - every sum over the 384 samples uses several running partial sums in a fixed order, so the processor can
//     overlap them; sums that share an input are taken in one pass (dotsK, dots2K).
// Only the summation order of those sums differs from the straightforward loops, so results agree to rounding
// (tools/pvb-harness/fit_equivalence.cpp checks this against a frozen copy of the original).
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstring>
#include "pvb_fastmath.h"
#include "pvb_simd.h"
namespace pvb {
struct ModulationFit {
    bool valid=false;
    double frequency=0, amplitude=0, phase=0, amplitudeSlope=0, frequencySlope=0;
    double carrier=0, slope=0, residual=0, qrDiagonalRatio=0;
    std::complex<double> z[5]={};
};
// Keep strong mode's operation order and instantiate the same solver at 96 ms.
namespace modulation {
#define PVB_MODULATION_SAMPLES 384
#include "pvb_vb_modulation_impl.inc"
#undef PVB_MODULATION_SAMPLES
}
namespace modulation183 {
#define PVB_MODULATION_SAMPLES 288
#include "pvb_vb_modulation_impl.inc"
#undef PVB_MODULATION_SAMPLES
}
struct ModulationFitCache {
    bool valid = false;
    int n = 0;
    int count = 0;
    double seed = 0;
    double neighbors[3] = {};
    double frame[384] = {};
    ModulationFit result{};
    uint64_t hits = 0;
    uint64_t misses = 0;
};
inline ModulationFit fitCached(ModulationFitCache* cache, bool shortWindow, const double* x, double seed,
                               const double* neighbors = nullptr, int count = 0) {
    const int n = shortWindow ? 288 : 384;
    const int nn = neighbors ? std::max(0, std::min(3, count)) : 0;
    if (cache) {
        if (cache->valid && cache->n == n && cache->count == nn &&
            std::memcmp(&cache->seed, &seed, sizeof(double)) == 0 &&
            (nn == 0 || std::memcmp(cache->neighbors, neighbors, static_cast<size_t>(nn) * sizeof(double)) == 0) &&
            std::memcmp(cache->frame, x, static_cast<size_t>(n) * sizeof(double)) == 0) {
            ++cache->hits;
            return cache->result;
        }
        ++cache->misses;
    }
    const ModulationFit m = shortWindow ? modulation183::fit(x, seed, neighbors, count)
                                        : modulation::fit(x, seed, neighbors, count);
    if (cache) {
        cache->valid = true;
        cache->n = n;
        cache->count = nn;
        std::memcpy(&cache->seed, &seed, sizeof(double));
        if (nn > 0) std::memcpy(cache->neighbors, neighbors, static_cast<size_t>(nn) * sizeof(double));
        std::memcpy(cache->frame, x, static_cast<size_t>(n) * sizeof(double));
        cache->result = m;
    }
    return m;
}
} // namespace pvb

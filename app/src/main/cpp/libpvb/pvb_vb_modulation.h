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
} // namespace pvb

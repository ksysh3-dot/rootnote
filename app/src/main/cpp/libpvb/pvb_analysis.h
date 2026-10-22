// PVB speaker engine - live spectrum analysis (shared definitions).
//
// The audio thread only copies its input and output into a ring buffer and publishes the filter
// coefficients it is using. Engine::analyze() (any other thread) turns that into:
//   - input and output spectra, Blackman-Harris 8192-point FFT, power-averaged over 1/12 octave,
//   - the measured change (output - input, output gain removed),
//   - the exact response of the filters as they are right now (including a glide in progress),
// on a log-spaced grid from 20 Hz to 20 kHz.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <cmath>

namespace pvb {

constexpr int kAnaFft = 8192;          // 171 ms at 48 kHz, 5.9 Hz per bin
constexpr int kAnaRing = 32768;        // frames; power of two > kAnaFft + latency + largest block
constexpr int kAnaMaxPoints = 1024;
constexpr double kAnaFmin = 20.0;
constexpr double kAnaFmax = 20000.0;

// Order of the info array filled by Engine::analyze(). Keep in sync with PvbEngine.kt.
enum AnaInfo : int {
    A_FRESH = 0,      // 1 = new audio since the previous call, 0 = nothing played (values kept)
    A_LIM_GR_DB,      // largest app limiter gain reduction since the previous call, dB (>= 0)
    A_EST_GR_DB,      // rough phone limiter gain reduction estimate, dB
    A_LOW_DB_NOW,     // low-mid bell gain in use (follows the glide), dB
    A_MIX,            // 0 = bypass, 1 = processed
    A_OUT_DB,         // output gain in use, dB
    A_SAMPLE_RATE,
    A_DYN_DB,         // low-mid change from the dynamic stage, dB (+ adds, - takes back)
    A_COUNT
};

// Frequency of point i of n on the analysis grid.
inline double anaPointHz(int i, int n) {
    return kAnaFmin * std::pow(kAnaFmax / kAnaFmin, n > 1 ? static_cast<double>(i) / (n - 1) : 0.0);
}

}  // namespace pvb

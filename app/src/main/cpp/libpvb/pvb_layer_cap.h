// Layer envelope guard: COMBO detects 100-500 Hz; other fixed modes retain 125-250 Hz.
// A common layer gain follows the 5/120 ms detector; this is not a hard sample-peak bound.
// The -18 dBFS phone threshold used here is an unmeasured assumption.
// This detector adds no latency and is designed for 48 kHz only.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <algorithm>
#include <cmath>

namespace pvb {

struct LayerCap {
    bool enabled = false;
    double cap = 1, env = 0, z[2][2] = {};
    // 0 dB or above = off. State stays, so moving the level does not click.
    void set(float db) {
        enabled = db < 0.f;
        if (enabled) cap = std::pow(10., static_cast<double>(db) / 20.);
    }
    void reset() {
        env = 0;
        for (auto& v : z) v[0] = v[1] = 0.;
    }
    double gain(double x,bool wideBand=false) {
        static constexpr double c[2][6] = {
            {6.6165543533214314e-05, 0.00013233108706642863, 6.6165543533214314e-05, 1, -1.9847624578326157, 0.98564751964811703},
            {1, -2, 1, 1, -1.991033839829627, 0.99135405123199727}};
        static constexpr double wide[2][6]={{0.0006607790982303774,0.0013215581964607548,0.0006607790982303774,1,-1.9395039007033319,0.94275352355026698},{1,-2,1,1,-1.9847980379311307,0.98501576809571501}};
        const auto& cf=wideBand?wide:c;
        for (int j = 0; j < 2; ++j) {
            const double y = cf[j][0] * x + z[j][0];
            z[j][0] = cf[j][1] * x - cf[j][4] * y + z[j][1];
            z[j][1] = cf[j][2] * x - cf[j][5] * y;
            x = y;
        }
        x = std::abs(x);
        static const double attack = 1. - std::exp(-1. / (.005 * 48000.));
        static const double release = 1. - std::exp(-1. / (.120 * 48000.));
        env += (x - env) * (x > env ? attack : release);
        return std::min(1., cap / std::max(env, 1e-30));
    }
};

}  // namespace pvb

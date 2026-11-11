// Speaker guard of the fixed bass modes: holds the 125-250 Hz envelope of the layer under a level, by a gain on
// the whole layer. The phone's speaker limits near -18 dBFS at 200 Hz, and internal recordings do not show it.
// Same filter and times as the s94 research cap (K24, K30). No added latency, 48 kHz only.
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
    double gain(double x) {
        static constexpr double c[2][6] = {
            {6.6165543533214314e-05, 0.00013233108706642863, 6.6165543533214314e-05, 1, -1.9847624578326157, 0.98564751964811703},
            {1, -2, 1, 1, -1.991033839829627, 0.99135405123199727}};
        for (int j = 0; j < 2; ++j) {
            const double y = c[j][0] * x + z[j][0];
            z[j][0] = c[j][1] * x - c[j][4] * y + z[j][1];
            z[j][1] = c[j][2] * x - c[j][5] * y;
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

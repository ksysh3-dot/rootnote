#pragma once
#include <algorithm>

namespace pvb {
// Research candidate C1. Music amplitude is never filtered by this policy.
// Bounds are in 16/3000-second hops; default hold32ms, release32ms.
struct ContinuityParams {
    bool enabled = false;
    int attack = 2, hold = 6, release = 6, fastRelease = 2;
};
struct HarmonicPermission {
    double value = 0;
    int missing = 0;
    double step(double evidence, const ContinuityParams& p, bool fast = false) {
        // Existing support corresponds to evidence1. Existing partials may
        // persist into a narrow margin; new partials still need full support.
        const bool supported = evidence >= 1.0 || (value > 0 && evidence >= .5);
        if (supported) missing = 0; else ++missing;
        // A brief false peak must not finish growing after support disappears.
        if(!supported && !fast && value > 0 && missing <= p.hold) return value;
        const double delta = supported ? 1.0/std::max(1,p.attack)
                                : -1.0/std::max(1,fast?p.fastRelease:p.release);
        value = std::max(0.0,std::min(1.0,value+delta));
        if(value<1e-12) value=0;
        return value;
    }
};
}

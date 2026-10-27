#pragma once
#include <algorithm>
#include <cmath>
namespace pvb { namespace trackprotection {
// Host-only R01 prototype, not an instrument separator or an app listening model.
// At a transient onset, an established near-stationary track can retain a
// frequency identity for 40 vocoder hops (213 ms at 3 kHz / 16 samples).
// New tracks and genuine travelling pitches do not acquire protection.
// Constant memory, no allocation, deterministic: safe for audio processing.
struct State {
    double smoothedHz=0, lockedHz=0, lastMatureHz=0;
    int steadyHops=0, lockHops=0, matureAgo=100000;
    bool pendingBornCut=false; // delayed fast-release once a protected note is genuinely missing
    void observe(double frequency) {
        if(!(std::isfinite(frequency) && frequency>0)) {steadyHops=0;return;}
        pendingBornCut=false; // matching a peak clears any earlier deferred termination
        if(lockHops>0) {--lockHops;return;}
        if(matureAgo<100000) ++matureAgo;
        if(steadyHops>0 && std::abs(frequency-smoothedHz)<=.015*smoothedHz) {
            smoothedHz+=.03*(frequency-smoothedHz);
            steadyHops=std::min(steadyHops+1,100000);
        } else {smoothedHz=frequency;steadyHops=1;}
        // A kick can steal the peak *before* amplitude-onset or percussion
        // classifiers react. Retain the last mature reference for 24 hops
        // (128 ms) even if the immediate tracker is already drifting.
        if(steadyHops>=56) {lastMatureHz=smoothedHz;matureAgo=0;}
    }
    bool recentlyMature() const {return matureAgo<=24 && lastMatureHz>0;}
    bool arm(bool transientOnset,bool confirmed) {
        if(transientOnset && confirmed && lockHops==0 && recentlyMature()) {
            lockedHz=lastMatureHz;lockHops=40;pendingBornCut=false;return true;
        }
        return false;
    }
    bool allows(double observedHz) const {
        return lockHops==0 || (std::isfinite(observedHz) &&
            std::abs(observedHz-lockedHz)<=.03*lockedHz);
    }
    void missing() {if(lockHops>0) --lockHops;}
};
}}  // namespace pvb::trackprotection

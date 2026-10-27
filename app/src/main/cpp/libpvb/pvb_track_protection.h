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
    double smoothedHz=0, lockedHz=0;
    int steadyHops=0, lockHops=0;
    void observe(double frequency) {
        if(!(std::isfinite(frequency) && frequency>0)) {steadyHops=0;return;}
        if(lockHops>0) {--lockHops;return;}
        if(steadyHops>0 && std::abs(frequency-smoothedHz)<=.015*smoothedHz) {
            smoothedHz+=.03*(frequency-smoothedHz);
            steadyHops=std::min(steadyHops+1,100000);
        } else {smoothedHz=frequency;steadyHops=1;}
    }
    bool arm(bool transientOnset,bool confirmed) {
        if(transientOnset && confirmed && lockHops==0 && steadyHops>=56) {
            lockedHz=smoothedHz;lockHops=40;return true;
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

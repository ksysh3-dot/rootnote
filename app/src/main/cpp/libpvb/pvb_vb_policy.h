// Experimental shared-phase harmonic-budget selector. No learned quality score.
#pragma once
#include <algorithm>
#include <cstdint>

namespace pvb {
class UpperHarmonicPolicy {
public:
    void reset() { frame_=0; lastSwitch_=-1000000; pending_=-1; run_=0; target_=1; blend_=1.; switches_=0; }
    void step(bool steady) {
        ++frame_;
        const int proposal=steady ? 0 : 1;
        if(proposal==target_) { pending_=-1; run_=0; }
        else {
            if(pending_!=proposal) { pending_=proposal; run_=1; } else ++run_;
            // Relaxation needs 512 ms evidence + 2 s dwell. Tightening needs
            // 64 ms evidence and may override dwell. All clocks are audio clocks.
            const int evidence=proposal ? 12 : 96;
            if(run_>=evidence && (proposal || frame_-lastSwitch_>=375)) {
                target_=proposal; lastSwitch_=frame_; pending_=-1; run_=0; ++switches_;
            }
        }
        constexpr double dt=16./3000.;
        if(target_) blend_=std::min(1.,blend_+dt/.04);
        else blend_=std::max(0.,blend_-dt/.25);
    }
    double blend() const { return blend_; }
    int target() const { return target_; }
    uint64_t switches() const { return switches_; }
private:
    int64_t frame_=0,lastSwitch_=-1000000;
    int pending_=-1,run_=0,target_=1;
    double blend_=1.;
    uint64_t switches_=0;
};
} // namespace pvb

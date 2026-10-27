#include "pvb_track_protection.h"
#include <cassert>
#include <cmath>
#include <cstdio>
using pvb::trackprotection::State;
int main() {
    // Steady bed: mature after 56 hops; only impact-onset + admitted track can lock.
    State bed;
    for(int i=0;i<70;++i) bed.observe(75.);
    assert(bed.steadyHops>=56);
    assert(!bed.arm(false,true));
    assert(!bed.arm(true,false));
    assert(bed.arm(true,true));
    assert(bed.allows(75.) && bed.allows(76.5));
    assert(!bed.allows(70.) && !bed.allows(64.));
    for(int i=0;i<40;++i) bed.missing();
    assert(bed.lockHops==0 && bed.allows(64.)); // time-bounded; no permanent frequency freeze

    // Continuous glissando: frequency change over 300 ms prevents maturation.
    State slide;
    for(int i=0;i<110;++i) slide.observe(70.+.18*i);
    assert(slide.steadyHops<56);
    assert(!slide.arm(true,true));

    // A new transient note cannot masquerade as a mature background tone.
    State born;
    for(int i=0;i<20;++i) born.observe(90.);
    assert(!born.arm(true,true));

    // Locked frequency is not updated by a crossing transient peak.
    State overlap;
    for(int i=0;i<90;++i) overlap.observe(75.);
    assert(overlap.arm(true,true));
    for(int i=0;i<8;++i) overlap.observe(74.8);
    assert(std::abs(overlap.lockedHz-75.)<.2);
    assert(!overlap.allows(66.));

    std::puts("track-protection: stable/attack/gliss/new-note/expiry tests passed");
}

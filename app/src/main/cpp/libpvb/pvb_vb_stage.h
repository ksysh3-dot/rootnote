#pragma once
#include <cstdint>
namespace pvb {
// Host research controls; configured before processing, never a saved app mode.
enum StageResearchFlag : unsigned {
    StageBypassHpss=1, StageBypassGain=2, StageBypassPermission=4, StageFreezePhase=8, StageShortDetail=16, StageConditionalGain=32, StageAmFamily=64, StageFamilyFilterComp=128, StageGlobalTrack=256,
    StageTrackLinear=512,StageTrackBurg=1024,
    StageOscillator=2048,StageOscillatorCorrect=4096,
    // Study 2 (#4) candidate C1: the envelope target's nominal amplitude is the power sum of the tracks' nominal
    // amplitudes (sqrt of the sum of squares) instead of their linear sum; one track is unchanged.
    StageNominalPower=8192
};
struct StageCapture52 {
    static constexpr int kValues=26, kFields=kValues+2, kVersion=3;
    // Clock is the CURRENT3kHz core sample, not a promise that every tap has
    // the same source/filter delay. Wire fields0/1 are exact low/high32 limbs.
    // values: decimated,band,band_delayed191,originalH,originalP,selectedH,
    // selectedP,analyticEnvelope,rawGrain,nominalAmplitude,envA,envP,
    // originalGain,appliedGain,tonalAfterGain,percussion,preFilter,postFilter,
    // upperBlend,flags,modulationMode,percussionGate,detailApplied(last hop),familyApplied,familyResidual,familyCoherence.
    using Sink=void(*)(void*,uint64_t,const double*);
};
}

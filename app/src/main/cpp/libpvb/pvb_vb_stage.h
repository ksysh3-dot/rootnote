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
    StageNominalPower=8192,
    // Study 3 (#4) candidates for short low notes. C2: a peak's frequency is taken from the unfiltered input
    // spectrum (the one the harmonic grid already reads) when it has a peak within 10 % of it; the band filter's
    // high-pass tilts a short note's spectrum and pushes the filtered peak up. C3: below 65 Hz the harmonic grid
    // accepts a fundamental within 10 % (the grid tolerance times k otherwise shrinks to about 1 Hz there).
    // C4: C3 outside an impact context only (an impact's low tail keeps the original grid).
    // C5: without lookahead, the HPSS harmonic mask of a prominent current peak is taken at once (causal median kept
    // for flat spectra), so a short note's onset is not held in the percussive part while the median fills.
    // C6: the C5 mask for the analysis only (vocoder spectrum and music envelope); output paths keep the causal HPSS,
    // and so does the percussive layer's polyphony mute (counted on the causal harmonic part).
    StageRawFrequency=16384, StageLowGridTolerance=32768, StageLowGridOutsideImpact=65536, StageCausalProminence=131072,
    StageAnalysisProminence=262144,
    StageNoPolyMute=524288   // diagnostic only: the percussive layer's polyphony mute is left off
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

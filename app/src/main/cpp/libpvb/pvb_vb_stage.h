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
    StageNoPolyMute=524288,  // diagnostic only: the percussive layer's polyphony mute is left off
    // Resultant R1 (#4 follow-up): a harmonic without a partial of its own in the input takes the crest-optimal
    // offset of pvb_vb_r1_tables.h (kPsi plus a change per fundamental) as its target instead of kPsi; a track is
    // still born with kPsi and the existing phase slew moves it there. A harmonic that follows an input partial's
    // phase, and the percussive layer, are unchanged.
    StagePhaseCrest=1048576,
    // Resultant R3: a note whose unfiltered spectrum has the odd partial 1.5 T (strict variant: and 2.5 T) but no
    // fundamental is taken as the second harmonic of T / 2 (pvFrame52), so the layer follows the real bass instead of
    // the octave above it.
    StageSubOctave=2097152, StageSubOctaveStrict=4194304,
    // Resultant R3-a: R3 without the relaxation while a track already holds T / 2 (always 10 / 20 dB). On the BabySlakh
    // confirmation the wrong halvings of a true fundamental took their T / 2 level from other tonal instruments.
    StageSubOctaveNoHold=8388608,
    // Resultant R4: the sustained upper roll-off starts at max(220 Hz, 3 f) instead of 220 Hz (renderTrack52 and the
    // burst copy), so a fundamental of 80-150 Hz keeps its 3rd and 4th harmonics; below 73.3 Hz nothing changes, and a
    // track at twice or three times a live lower track keeps 220 Hz.
    StageRegisterCorner=16777216,
    // Resultant R4, with StageRegisterCorner: while a low-band onset is recent (onsetLeft_, 24 hops = 128 ms) the
    // 220 Hz roll-off returns within ~10 ms and the register corner comes back over ~60 ms afterwards; bursts keep 220 Hz.
    StageOnsetProtect=33554432
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

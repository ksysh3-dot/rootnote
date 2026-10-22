#pragma once

namespace pvb {
// Float wire format; absolute time is added by the audio owner. Core counters
// are four exact 16-bit limbs (low first), never a lossy float timestamp.
struct HarmonicTrace {
    static constexpr int kVersion = 1, kHeader = 28, kTrack = 56, kTracks = 12;
    static constexpr int kFields = kHeader + kTrack * kTracks;
    static constexpr int kBlockRows = 72; // > ceil(16384 / 44100 * 3000 / 16)
    enum Reason { Absolute=1, Relative=2, NoPeak=4, Fit=8, Grid=16,
                  Lost=32, Capacity=64, Weight=128, Nonfinite=256, Dependent=512 };
    enum State { Birth=1, Tracked=2, Held=3, Release=4, End=5 };
    // Header: callback offset, algorithm, epoch, core index limbs[4],
    // analysis start offset(core), HPSS delay(core), source centre offset(host),
    // grain centre output offset(host), active, ending, frame reason bits,
    // maximum analysis amplitude, harmonic power, percussion power,
    // envelope compensation, poly envelope, raw vocoder sample, grain RMS,
    // omitted candidates/records, lost tracks, wire version, onset hold,
    // falling-amplitude flag, residual hold count, reserved0.
    // Track: id,state,f,df/dt,a,wrapped phase,residual,fade,age,missing,
    // reason,life gain,raw residual,id high16; then 7*(target amplitude, actual amplitude,
    // mask weight, phase adjustment, reason, evidence). Amplitudes are PRE envelope,
    // output filtering, user layer gain and limiter, not WAV amplitudes.
    float data[kFields] = {};
};
}

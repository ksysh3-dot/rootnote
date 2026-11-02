S54 level-dependent strength backoff (host research)
==================================================

Base: 9d408fb, app-integration-fixed S30 FULL (P1+++).
The new control is OFF at construction. It is not connected to JNI, UI,
serialized presets, or the app's P_COUNT parameter vector.

Host API:

```
pvb_set_level54(engine, mode, kneeDb, grSlope, enterDb, exitDb, attackMs, releaseMs)
pvb_copy_level54_state(engine, output, capacity)
```

Configure on the processing thread before audio starts. Mode 0 is OFF;
mode 1 enables the experiment at 48 kHz for algorithm 6. Other algorithms
and sample rates skip the new arithmetic. The API rejects unsupported
sample rates, nonfinite values and invalid hysteresis/time constants
without changing state. It is not a concurrent app parameter API.

The proposed and reference stereo sums use the same dry and generator
samples. The proposal includes S30's extra layer gain. The reference uses
the original P1 strength at that point, with the current candidate dry
path. This is not a parallel full P1 rerender and not a measured phone
gain detector. The prediction is before controller A and the final
limiter, so it can overestimate the phone's actual exposure.

Twenty-millisecond causal mean-square followers feed a 1-ms control
update. Predicted additional GR is

```
grSlope * (max(0, proposedRmsDb-kneeDb) - max(0, referenceRmsDb-kneeDb))
```

clamped below at zero. Separate enter/exit thresholds hold the mode.
The target backoff is at most 6 dB, smoothed in dB with attack/release.
It scales only EXTRA strength:

```
newGain = P1Gain + (proposedGain-P1Gain) * 10^(-backoffDb/20)
```

No audio delay/buffer is introduced. Existing controller A, the native
shared limiter, and s50's conservative TP8 bound remain after this point.
An absolute limiter ceiling and the relative TP8 <= P1+0.5 dB rule are
different contracts; the latter must be measured for each evaluated input.

The fixed experiment parameters are knee -24 dBFS RMS, GR slope 1.5,
enter 1.5 dB, exit 0.5 dB, attack 40 ms and release 250 ms. These are
scenario settings, not a calibrated Galaxy or Huawei protection profile.
No excursion, coil temperature, Android hardware volume or smart-amp
state is observed. This is not a speaker-protection guarantee.

Reset clears detector, hysteresis, smoothing and switch count. Repeating
identical parameters preserves live state. ON -> OFF stops new control
arithmetic; already buffered samples and old limiter/controller state
remain until drained or a shared engine reset. Exact immediate live-OFF
equality is not promised. OFF plus the shared reset is verified against
P1+++ OFF after the same reset.

The accompanying s54 work directory contains the DEV registration,
native V0/causality checks, synthetic threshold/AM/volume/silence stress,
REW magnitude-only fit and its limitations, L5 identifiability witness,
per-song/level results and Korean report. It does not contain copied or
rendered user music. Physical-phone IMD/music validation and blind
listening are separate pending evidence.

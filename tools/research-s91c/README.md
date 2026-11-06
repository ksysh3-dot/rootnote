# Frozen s91 Stage C personal APK

Base: a87b687ef95fae3073ca4f8892d67c454c0a057d. Local branch research/s91c-apk.
This change neither evaluates nor reads Stage A/B full-run results. No installation or publishing.

Modes use the existing capture-generation stop/join/start path. StageCApp prepares the chosen
model on service main before AudioWorker.start; PvbEngineParams sends the unchanged P1/P1+++ or
separator atomic preset. configure/reset preserves the frozen engine transition clock.
Stage C IDs: 0 preset off/P1, 1 strong/P1+++, 2 T3a16 separator, 3 E60KD control, 4 developer epoch6.
The saved default remains off; the ordinary default strength remains +4 dB. Frozen presets
retain their existing effective layer of 0 dB. Existing stable saved values still mean epoch6.

The common developer entry offers epoch6 comparison, default-off asynchronous control,
default-off file telemetry, log path and ZIP export. General's previous developer page remains
a separate item. S26u uses the same test menu through the existing preference row.
Control uses the a87b687e tau_b (full precision), tau=0.5, epsilon=0.5, modules=33, origin=0.
Neither separator weights nor separator tick() are used in control mode.

Telemetry is disabled by default. Callback hooks update counters only. s91-log writes UTF-8 JSONL
under files/s91_telemetry every 5 seconds and at session end. Timings include FFT, feature,
network, compact and frame publication. p50/p99 are upper bounds of 10 us histogram bins;
the overflow bin uses the measured maximum. No-frame percentiles are null.
Late control frames count distinct requested frame indices unavailable at their first late
request. I/O dropout observations (AudioTrack underruns, capture gaps, discarded write blocks)
are separated in the JSON; they do not establish audible gaps. Overruns compare DSP block time
with frames/sampleRate and exclude blocking capture/write. The developer export explicitly
creates a ZIP through the existing non-exported FileProvider. No audio is stored.

ControlStream timing observations persist through context resets; preparation starts a new
session. Snapshots read atomic counters and may include an in-progress callback.
The service closes the writer after the prior generation ends and before model reconfiguration.
Only lifecycle prepare may load/allocate models, change control workers or unload a separator.

Validation:
- tools/pvb-harness/build_host.sh builds the actual JNI and C APIs.
- tools/pvb-harness/jvm/run_jvm_test.sh includes StageCModesJniTest; the s78 single-compile
  runner in ~/r3a-dev/plan16/s91c/kotlin-fast.py runs that same source/test set.
- StageCModesJniTest uses the actual native library for every mode, repeated mode switches,
  engine-state/latency/model-isolation checks, optional worker and byte-identity comparisons.
- control_off_regression.py compares P1/P1+++/epoch6 with an independently built frozen base
  at 37/64/256/1024 frame blocks. It uses deterministic synthetic input, no confirmation music.
- stage_c_stress.cpp covers lifecycle preparation, resets, timing, snapshots and zero callback
  operator-new allocations under ASan/UBSan. JNI is also tested using an instrumented library.
- Offline Gradle uses the cached s56 SDK/NDK and an isolated copy of its Gradle home. Build
  commands and complete logs live in ~/r3a-dev/plan16/s91c. All compilers run at nice 10,
  Gradle/Ninja have at most four workers, and signing uses only the Android Debug test key.

The new E60KD/T3a16 weights are git-ignored; the unchanged pre-existing epoch6 asset stays in
the base history. All three APK assets are hashed during verification. Rootless General and
S26u release variants retain their own existing application IDs. Device playback, physical
dropouts/heat and blind preference are subsequent evidence, not host-test conclusions.

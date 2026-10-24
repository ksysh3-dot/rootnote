# Rootnote for rooted phones (Android 8-10 and up, via Magisk)

Status: 2026-10-24. Stage 1 done (the audio effect with the engine, host tested); stages 2-4 to do. Test phone: a
Galaxy S8 (Android 9) the owner will root.

## Why it is a separate build

The rootless build captures the music into the app and runs JamesDSP and then the PVB engine there (Android 10+:
playback capture). The rooted JamesDSP works the other way: the system's audio server runs an audio effect library
(libjamesdsp, installed by a Magisk module) on the output, and the app only sends it settings. So the engine has to
run inside that effect library, and the phone needs our own Magisk module with it.

## Stages

1. **Effect library (done).** `app/src/main/cpp/rootfx/`: a marked copy of the JamesDSP effect wrapper
   (libjamesdsp submodule, `Main/libjamesdsp/jni/jamesdsp/jamesdsp.c`) with the PVB engine after the JamesDSP chain,
   as in the rootless build. Same effect type and UUID as the stock JamesDSP (the app's root flavour finds it as
   before). New commands: SET_PARAM 41000 = the engine's parameter array (exactly `PvbEngineParams.encode()`),
   GET_PARAM 41002 = interface version, 41003 = engine active. The engine is bypassed until the first parameter
   array; float and 16-bit buffers (other formats skip it). Host test `tools/rootfx/build_host.sh` (in CI): loaded
   and driven like audioserver does; output = JamesDSP then the engine's own C API, bit exact.
2. **Android build and Magisk module.** NDK build (arm64-v8a and armeabi-v7a: many Android 9 phones run a 32-bit
   audio server), module zip: the library into `vendor/lib(64)/soundfx`, the audio effects configuration (XML or
   .conf, system and vendor) patched to point the JamesDSP entry at it, SELinux rules the JamesDSP modules use
   (execmem for the script engine). Refuses to install next to the stock JamesDSP module. Built and attached by CI.
3. **App, root flavour of the general build.** Package `…rootnote.root` (installs next to the rootless one),
   minSdk 26; the PVB controller sends its parameter array to the effect (`AudioEffect.setParameter`, 41000) instead
   of an in-process engine, checks the module's version (41002) and says when the stock JamesDSP module is in use.
   Features that need the engine in the app process (developer-mode meters, bass fit microphone checks, live A/B,
   recording) are hidden in this flavour at first.
4. **Phone test (S8, Android 9).** Install order, effect attached to music, parameter changes heard, no audio
   server crash after hours, battery; then the release notes and a "rooted" section in the README.

## Risks

- Audio server differences between phones (32/64-bit, offload paths that skip effects, vendor effect configs in
  /odm): stage 4 decides what the module must handle.
- The engine's CPU cost inside the audio server (it runs on the audio thread there too).
- Without a rooted phone nothing past stage 1 can be checked beyond building.

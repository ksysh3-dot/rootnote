# Model scope after 2026-11-02 (option B)

Both general and s26u APKs compile P1 (native ID 6). P1+++ is an experimental,
default-OFF preset, requested separately through param 57. It is available now in
both flavors; enabling it never happens as a migration side effect. The atomic
s50 preset fixes EQ, layer 0 dB, output -5 dB, and disables spatial, dynamic bass,
volume links and developer voicing. It requires 48 kHz. Status distinguishes
applied, transitioning and unsupported (including 44.1 kHz or a suspended path).
At an unsupported stream rate the Kotlin encoder sends the saved P1 settings
with bit 57 OFF, so even a cold start keeps working instead of losing the whole
packet to the native atomic validation gate. The requested switch stays visible
as unsupported; 48 kHz can apply it again without silently changing preferences.
OFF restores saved EQ/strength/spatial/voicing settings. Audio fade/reset/latency
and native limiter protections are unchanged from s50.

| Surface | Kept | Removed |
|---|---|---|
| Android general/s26u | P1, P1+++ opt-in, VB off/EQ/XTC/diagnostics | models 0-5, 7-17; deep/Gentle12; four X switches; obsolete AB sides/pairs |
| Host default/JNI | same app contract | standalone factory rejects removed IDs |
| Explicit reference C API | fixed modified Resultant v1.6-c, ID 16, fixes 27-29 ON | arbitrary Resultant presets, v1.5/a/b/d |

JNI IDs are sparse and never renumbered: 0-5/7-17 stay reserved in the app.
Param count 58, meter count 28 and diagnostic count 90 remain unchanged. Slots
29-32 always sanitize to zero, including direct JNI, rootfx and damaged packets.
Native default model is now 6, replacing the deleted ID 0. In a rejected 44.1 kHz
P1+++ packet, the inactive default-model trace field changes from 0 to 6; PCM and
layer outputs remain bit-identical. This intentional metadata change is asserted
separately by the V0 fixture checker.

Settings schema 4 maps any deleted/unknown key, numeric ID or damaged type to
alpha2_p1. Strength, EQ, enabled state and old AB records survive; removed-model
-3 dB trims do not transfer. The obsolete derived deep/mode key is removed.
The four old X preference values are explicitly written false by migration;
load/encoder/native also ignore them after a late restore. Re-running migration
is idempotent. Track memory uses the same PvbModels allowlist. A stored explicit
P1+++ opt-in survives; missing/invalid values remain false.

RN1 shared-code bitmap indexes remain append-only. Four private reserved specs
occupy the historical positions but have no developer UI/lookup, always read zero,
encode zero and decode legacy ON bits as OFF. Other sliders keep their original
positions, signed-strength handling and checksum validation.

Historical code and original research commands/results remain at local annotated
tag archive/models-pre-prune-20261102, base 9d408fb. See reference/README.md for
an explicit host-only c build. Current CI no longer runs removed model suites.
Historical research documents describe their original refs and are not current
app catalogues. No audio assets are added.

The existing live blind comparisons retain P1 strength/link and independent XTC
comparisons. A P1/P1+++ live pair is deferred: current blind mode forcibly disables
the atomic preset. Enabling that path correctly needs new transition/masking
contracts; adding a pair alone would compare P1 with P1. External host comparison
is available. Phone RT, thermal, device playback and blind-listening gates remain
outside this source/build verification.

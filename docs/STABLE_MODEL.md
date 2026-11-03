# Experimental STABLE asset
Frozen s69c A+B complex-mask student: 132802 float32 parameters, 531208 bytes.
SHA256: 70f4a90c34568f46d4677e4799397991a2cb2f6577988fb3ea704332330c9b98
Training provenance: A uses the approved Slakh TRAIN-derived teacher material (185-song pool,12.78h;176 fit/9 holdout); B uses user phone-backup music (1218-song pool,15.08h selected excerpts;1147 fit/71 holdout), htdemucs teacher distillation. Combined A+B uses1323 fit/80 holdout songs; the selected checkpoint is epoch6. No validation/test used for training. s73 MUSDB18 official test30 is evaluation only.
The weights are distributed as part of this GPL application by explicit user instruction. This records training provenance and is not a separate legal clearance for source recordings. Source recordings, features, stems and teacher checkpoints are excluded from Git/APK.
STABLE adds3192 frames/66.5ms at48kHz; total10332/215.25ms. OFF and STRONG retain prior delay.
Rootless playback capture has no public Android API for telling the originating third-party player about added DSP latency. JNI latencyFrames and Android status expose the true engine delay; automatic upstream A/V compensation is not guaranteed.

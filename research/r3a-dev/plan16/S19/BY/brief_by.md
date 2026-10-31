# Brief S19-BY — where and why "쿠쿠쿵" is still strong in "Beyond" with v1.6-c (RESULTANT_CORE.md 19.10)

You are a Sonnet worker. OFFLINE measurement only: no source changes, no commits, no downloads, never copy or commit the user's audio (read in place, keep only numbers), never touch slakh2100/validation or slakh2100/test, never create folders on the Windows C: drive. Work in `~/r3a-dev/plan16/S19/BY/`.

Song: `/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/10. Beyond.flac` (read in place; the path has Korean and spaces — quote it). The user hears the "쿠쿠쿵" still strong there with v1.6-c on a phone speaker at strength +6 dB (blind 19.10: v1.6-c better than v1.5 but "둘 다 심함"). Reference set: the 14 vanila songs (`/mnt/c/Users/ksysh/Music/vanila/`) and the 7 user windows used before.

Library `~/r3-work/tools/pvb-harness/build_core19/libpvbcapi.so`; rows P1 (algo 6), v1.5 (15 defaults), v1.6-b, v1.6-c (v1.6-b + layerHpHz 150, layerHpOrder 8, layerHpComp 1) via `research_core_api.set_resultant`; render the whole song like `~/r3a-dev/plan16/S19/L/` (layer capture) and with traces for v1.6-c. Metrics: the S19-L definitions (Hann-FFT 20-140 Hz absolute and 20-140 / 150-600, 20-140 Hz 5 ms burst share, 150-260 Hz level re 150-600, 2-12 Hz pulsing of the 20-150 envelope minus the input's).

Do:
1. Over the whole song in 2 s windows (hop 0.5 s): rank the windows by v1.6-c's 20-140 Hz absolute level and by its excess over P1; list the top 8 with timestamps (m:ss) so the user can check them by ear. Compare the song's distribution with the 14 vanila songs (is Beyond an outlier, and in which metric?).
2. In the top windows: what is in the input (lowest notes and their f from the trace, how many voices, f_track below 100 Hz?, the input's own 20-150 Hz level), which voices carry the layer's 20-140 Hz energy (B1-2 per-voice reconstruction as in `~/r3a-dev/plan16/S19/` — reuse s19_attr.py event tags: is the residual event-bound or no-event?), and the k=2 / k=3 levels vs P1.
3. Whether the residual 20-140 Hz in those windows comes from partials below 150 Hz that the layer synthesizes on purpose (k·f < 150 Hz for very low notes, e.g. f < 75 Hz with k = 2) — report the share of 20-140 energy from voices with 2·f_osc < 150 Hz.
4. The same table for the English version `31 Beyond (English ver.) (Ending Movie).mp3.flac` only if (1) shows Beyond is an outlier and the second file decodes; otherwise skip.

Report in concise Korean: the top windows with m:ss, the comparison with vanila, the cause breakdown, MEASURED vs INTERPRETATION, file paths. No adoption decisions. Long jobs in the background with logs.

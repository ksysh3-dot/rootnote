package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * The engine's parameter array ([PvbParam], same order and meaning as `pvb::Param` in pvb_engine.h) from the settings
 * that play now and the conditions of the moment.
 *
 * Pure: reads only its arguments and writes nothing. [PvbController.push] reads the Android state into [Inputs]
 * (output device, volume, posture, rotation, the comparison), calls [encode], then sends the array to the engine,
 * updates its own bookkeeping and publishes the status. Called on the main thread when something changes, never per
 * audio block.
 *
 * States kept apart on purpose (none of them is "active"):
 * - `enabled` ([PvbSettings.enabled]): the user switched the effect on.
 * - in the path ([PvbController.isActive], [JdspChain.pvbInPath]): the engine sees the samples. Not decided here.
 * - `routeAllowed`: this output may be processed ("내장 스피커에서만" off, or the speaker is playing).
 * - `processing`: the effect is audible: enabled and the route allowed.
 * - `matchedBypassReady`: a flat path at matched loudness and the same latency is kept ready; heard when the effect is
 *   off (`ENABLED` 0), unheard while it processes.
 * - Virtual-bass level: [PvbSettings.vbLevelDb] is what the user set, [VolumeLevelLink.levelFor] what plays at this
 *   volume (the array carries the second).
 * - Rotation: [Inputs.rotation] is the screen now, [Inputs.upright] the physical posture (accelerometer),
 *   [PvbSettings.xtcBalRotation] the rotation the balance was set in.
 */
object PvbEngineParams {
    /** `android.view.Surface.ROTATION_90` / `ROTATION_270` (kept here so this file needs no Android classes). */
    private const val ROTATION_90 = 1
    private const val ROTATION_270 = 3

    /** Everything besides the settings, read once by [PvbController.push]. */
    data class Inputs(
        val rampMs: Float,
        /** The output now is the phone's own speaker. */
        val speaker: Boolean,
        /** Held upright (accelerometer, with a hold time); always false while spatial is off. */
        val upright: Boolean,
        /** Screen rotation now, `Surface.ROTATION_*`. */
        val rotation: Int,
        val volumeIndex: Int,
        val volumeMax: Int,
        /** Low-mid bell level after the volume link ([VolumeCompensation.lowGainDb]), dB. */
        val lowDb: Float,
        /** Last measured matched-bypass gain, dB. */
        val matchSeedDb: Float,
        /** Solo monitor as requested ([PvbController.setDiagnosticSolo]); [encode] drops it when not allowed. */
        val diagnosticSolo: Boolean,
        val abActive: Boolean,
        val abHidden: Boolean,
        val abTag: Int,
        /** Final output gate (comparison mute or headroom), dB. */
        val gateDb: Float,
        val measuring: Boolean,
        val devMeter: Boolean,
    )

    class Encoded(
        val params: FloatArray,
        /** The solo monitor after this push: false once it is no longer allowed (it stays off afterwards). */
        val diagnosticSolo: Boolean,
    )

    fun encode(s: PvbSettings, i: Inputs): Encoded {
        val routeAllowed = !s.speakerOnly || i.speaker
        val processing = s.enabled && routeAllowed
        val matchedBypassReady = s.matchOnDisable && routeAllowed && !i.abHidden
        // Alpha 3.2: the layer gets weaker as the volume rises (link on); applied here only, never stored. A volume not
        // read yet (index 0) gives no reduction. Comparison conditions switch the link off (PvbAbConditions.v11).
        val vbAppliedLevelDb = VolumeLevelLink.levelFor(s, i.volumeIndex, i.volumeMax)
        val p = FloatArray(PvbParam.COUNT)
        p[PvbParam.ENABLED] = if (processing) 1f else 0f
        p[PvbParam.HP_HZ] = s.hpHz
        p[PvbParam.LOW_HZ] = s.lowHz
        p[PvbParam.LOW_DB] = i.lowDb
        p[PvbParam.LOW_Q] = s.lowQ
        p[PvbParam.HI_HZ] = s.hiHz
        p[PvbParam.HI_DB] = s.hiDb
        p[PvbParam.HI_Q] = s.hiQ
        p[PvbParam.OUT_DB] = s.outDb
        p[PvbParam.CEIL_DB] = s.ceilDb
        p[PvbParam.REL_MS] = s.releaseMs
        p[PvbParam.RAMP_MS] = i.rampMs
        p[PvbParam.DYN_ON] = if (s.dynOn) 1f else 0f
        // Level where quiet-passage bass starts, independent of the volume (UMIK-1 sweeps, 2026-10-21: the phone's
        // bass limiter sits after the volume control).
        p[PvbParam.DYN_REF_DB] = s.dynRefDb
        p[PvbParam.DYN_DOWN_RATIO] = 0.5f
        p[PvbParam.DYN_DOWN_MAX_DB] = 0f   // loud passages: no take-back (album study, 2026-10-16)
        p[PvbParam.DYN_UP_RATIO] = 0.19f   // same equal-loudness slope as the volume link
        p[PvbParam.DYN_UP_MAX_DB] = s.dynUpMaxDb
        p[PvbParam.HS_HZ] = s.hsHz
        p[PvbParam.HS_DB] = s.hsDb
        p[PvbParam.GATE_DB] = i.gateDb
        p[PvbParam.TAG] = if (i.abActive) i.abTag.toFloat() else 0f
        // In matched bypass, retain the processed reference and equal delay, but only the flat path is audible.
        // A route bypass still removes virtual bass and its delay.
        p[PvbParam.VB_ON] = if (s.vbOn && (processing || matchedBypassReady)) 1f else 0f
        p[PvbParam.VB_ALGO] = s.vbAlgo.toFloat()
        p[PvbParam.VB_LEVEL_DB] = vbAppliedLevelDb
        p[PvbParam.FLAT] = if (matchedBypassReady) 1f else 0f
        p[PvbParam.MATCH_HOLD] = if (i.abActive || i.measuring || !routeAllowed) 1f else 0f
        p[PvbParam.MATCH_SEED_DB] = i.matchSeedDb
        val soloAllowed = processing && s.vbOn && !i.abActive && !i.measuring
        val diagnosticSolo = i.diagnosticSolo && soloAllowed
        p[PvbParam.DIAGNOSTIC_SOLO] = if (diagnosticSolo) 1f else 0f
        // Experimental layer options: only with virtual bass on (the engine also ignores them without it).
        val vbIn = p[PvbParam.VB_ON] == 1f
        p[PvbParam.X_SMOOTH] = if (vbIn && s.xSmooth) 1f else 0f
        p[PvbParam.X_RISE] = if (vbIn && s.xRise) 1f else 0f
        p[PvbParam.X_S1M] = if (vbIn && s.xS1m) 1f else 0f
        p[PvbParam.X_DENSE] = if (vbIn && s.xDense) 1f else 0f
        // Developer mode (general build only: PvbSettings.load keeps devOn false elsewhere). Off = every value ignored.
        val dev = s.devOn && !i.abActive
        p[PvbParam.DEV_ON] = if (dev) 1f else 0f
        p[PvbParam.DEV_METER] = if (i.devMeter) 1f else 0f
        p[PvbParam.D_BOUNDARY_HZ] = s.devBoundaryHz
        p[PvbParam.D_OUT_LO_HZ] = s.devOutLoHz
        p[PvbParam.D_OUT_HI_HZ] = s.devOutHiHz
        p[PvbParam.D_H2_DB] = s.devH2Db
        p[PvbParam.D_H3_DB] = s.devH3Db
        p[PvbParam.D_H4_DB] = s.devH4Db
        p[PvbParam.D_H5_DB] = s.devH5Db
        p[PvbParam.D_ROLLOFF_DB_OCT] = s.devRolloffOffset
        p[PvbParam.D_SUST_DB] = s.devSustDb
        p[PvbParam.D_PERC_DB] = s.devPercDb
        p[PvbParam.D_ATTACK_MS] = s.devAttackMs
        p[PvbParam.D_RELEASE_MS] = s.devReleaseMs
        // virtual-bass table matched to this speaker floor: 150 Hz (the S26 Ultra) = 1 = the model, bit exact
        p[PvbParam.D_TABLE_SCALE] = s.devTableFloorHz / DevParams.TABLE_FLOOR.default
        // Crosstalk cancellation: the phone's own speakers only (designed for landscape, the two speakers left and
        // right of the listener; not tied to the screen rotation, which a locked rotation would misreport); never
        // during a measurement. During a comparison it follows the condition: EQ v1.1 has it off
        // ([PvbAbConditions.v11]); only the spatial comparisons set a mode, including the M/S widener (6, 7).
        val spatialOn = s.xtcMode != PvbSettings.XTC_OFF && i.speaker && !i.measuring
        // Held upright: no left/right to cancel; off, mono, or the two-way split (pvb_xtc.h PORTRAIT_*).
        val spatialMode = when {
            !spatialOn -> 0
            !i.upright -> s.xtcMode
            s.xtcPortrait == PvbSettings.XTC_PORTRAIT_MONO -> 3
            s.xtcPortrait == PvbSettings.XTC_PORTRAIT_SPLIT -> if (s.xtcPortraitLowRight) 5 else 4
            else -> 0
        }
        p[PvbParam.XTC_MODE] = spatialMode.toFloat()
        p[PvbParam.XTC_STRENGTH_DB] = s.xtcStrengthDb
        p[PvbParam.XTC_DIST_CM] = s.xtcDistanceCm
        p[PvbParam.XTC_HAT_CM] = s.xtcHatCm
        p[PvbParam.XTC_SPACING_CM] = PvbSettings.XTC_SPACING_CM
        p[PvbParam.XTC_LO_HZ] = PvbSettings.XTC_LO_HZ
        p[PvbParam.XTC_HI_HZ] = PvbSettings.XTC_HI_HZ
        // Speaker balance: set in one landscape rotation; turned round, the phone swaps its channels with the
        // speakers, so the correction swaps sides too. Portrait and unknown rotations keep it as set.
        val landscape = i.rotation == ROTATION_90 || i.rotation == ROTATION_270
        val balanceSign = if (s.xtcBalRotation != 0 && landscape && i.rotation != s.xtcBalRotation) -1f else 1f
        p[PvbParam.XTC_BAL_LO_DB] = if (i.upright) 0f else balanceSign * s.xtcBalLoDb   // the balance is a sideways one
        p[PvbParam.XTC_BAL_HI_DB] = if (i.upright) 0f else balanceSign * s.xtcBalHiDb
        return Encoded(p, diagnosticSolo)
    }
}

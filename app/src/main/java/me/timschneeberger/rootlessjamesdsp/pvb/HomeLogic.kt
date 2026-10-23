package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * What the general build's home screen shows, as plain Kotlin (no Android types), so the host tests check the same
 * decisions the screen makes: master state and headline, preset chip selection, slider range, preset writes and the
 * volume-link line.
 *
 * The screen only reads and writes the existing PVB keys (pvb_enable, pvb_vb_enable, pvb_vb_algo,
 * pvb_vb_strength_db, pvb_vb_vol_link); nothing here is stored.
 */
object HomeLogic {
    /** The sentence at the top of the screen. */
    enum class Headline {
        /** Service running, PVB processing on, virtual bass on. */
        FILLING,
        /** Service running, PVB processing on, virtual bass off (turned off in the advanced settings). */
        CORRECTION_ONLY,
        /** Nothing of ours is audible: service stopped or PVB processing off. */
        ORIGINAL,
    }

    /** The three preset chips. [presetKey] is the PvbModels preset key ([PvbModels.PRESET_CUSTOM] for the last). */
    enum class Chip(val presetKey: String) {
        FULLNESS(PvbModels.PRESET_FULLNESS),
        DEEP(PvbModels.PRESET_DEEP),
        CUSTOM(PvbModels.PRESET_CUSTOM),
    }

    /** The master switch is on only when the bass is really being filled. */
    fun masterOn(s: PvbSettings, serviceRunning: Boolean): Boolean = headline(s, serviceRunning) == Headline.FILLING

    fun headline(s: PvbSettings, serviceRunning: Boolean): Headline = when {
        !serviceRunning || !s.enabled -> Headline.ORIGINAL
        s.vbOn -> Headline.FILLING
        else -> Headline.CORRECTION_ONLY
    }

    /** Top of the strength slider: the general build's cap (9 dB), else the full slider range (12 dB). */
    fun sliderMax(caps: SafeCaps?): Int =
        (caps?.vbLevelMax ?: PvbSettings.VB_LEVEL_MAX).coerceIn(PvbSettings.VB_LEVEL_MIN, PvbSettings.VB_LEVEL_MAX).toInt()

    /** A stored level as a slider position: whole dB, inside 0..[sliderMax]; non-finite gives the default. */
    fun sliderValue(levelDb: Float, caps: SafeCaps?): Int =
        PvbSettings.clampLevel(levelDb).roundToInt().coerceIn(0, sliderMax(caps))

    /**
     * The selected chip, derived from model + level exactly like the preset list of the advanced screen
     * ([PvbModels.presetFor]). [customPinned]: the user tapped "custom" on this screen; it stays selected (and the
     * slider keeps its value) until a preset chip is tapped, even when the level happens to match a preset.
     */
    fun selectedChip(modelKey: String?, levelDb: Float, customPinned: Boolean = false): Chip {
        if (customPinned) return Chip.CUSTOM
        return when (PvbModels.presetFor(modelKey, levelDb)?.key) {
            PvbModels.PRESET_FULLNESS -> Chip.FULLNESS
            PvbModels.PRESET_DEEP -> Chip.DEEP
            else -> Chip.CUSTOM
        }
    }

    /** Model key of a [PvbSettings.vbAlgo] id (unknown ids give the default model, as [PvbModels.fromKey] does). */
    fun modelKey(algo: Int): String = PvbModels.fromId(algo)?.key ?: PvbModels.DEFAULT_KEY

    /** What tapping [chip] writes: model key and level (within the caps). Custom writes nothing (null). */
    fun presetWrite(chip: Chip, caps: SafeCaps?): Pair<String, Float>? {
        val preset = PvbModels.presets.firstOrNull { it.key == chip.presetKey } ?: return null
        return preset.modelKey to sliderValue(preset.levelDb, caps).toFloat()
    }

    /** The second line of the volume-link row. */
    sealed class LinkLine {
        /** Link off: the same strength at any volume. */
        object Off : LinkLine()
        /** Link on, but the volume is not known (no audio service, unknown maximum). */
        object VolumeUnknown : LinkLine()
        /** Link on, at this volume nothing is taken off. */
        data class NoReduction(val volumePct: Int) : LinkLine()
        /** Link on: [reductionDb] (> 0) taken off, the engine plays [appliedDb]. */
        data class Reduced(val volumePct: Int, val reductionDb: Float, val appliedDb: Float) : LinkLine()
    }

    /**
     * The line for these settings at media volume [volumeIndex] of [volumeMax], with the same arithmetic the
     * controller applies at push time ([VolumeLevelLink]).
     */
    fun linkLine(s: PvbSettings, volumeIndex: Int, volumeMax: Int): LinkLine {
        if (!s.vbVolLink) return LinkLine.Off
        if (volumeMax <= 0 || volumeIndex < 0) return LinkLine.VolumeUnknown
        val pct = VolumeLevelLink.volumePct(volumeIndex, volumeMax)
        val reduction = VolumeLevelLink.reductionFor(s, volumeIndex, volumeMax)
        val shown = pct.roundToInt()
        if (round1(reduction) <= 0f) return LinkLine.NoReduction(shown)
        return LinkLine.Reduced(shown, reduction, VolumeLevelLink.levelFor(s, volumeIndex, volumeMax))
    }

    /** "+6 dB"-style strength label for the slider value. */
    fun levelLabel(level: Int): String = "+$level"

    /** Limiter working share (%, PvbMeter.LIM_ACTIVE_PCT, ~3 s) at or above which the home suggests a lower strength. */
    const val PRESSURE_ON_PCT = 30f
    /** ... and below which the hint goes away again (hysteresis: no flicker around one value). */
    const val PRESSURE_OFF_PCT = 15f

    /**
     * "지금 세기에서 소리가 눌리고 있어요": shown while virtual bass plays and the limiter works a large share of the
     * time; [shown] is the previous answer.
     */
    fun limiterPressure(shown: Boolean, vbPlaying: Boolean, activePct: Float): Boolean = when {
        !vbPlaying || !activePct.isFinite() -> false
        activePct >= PRESSURE_ON_PCT -> true
        activePct < PRESSURE_OFF_PCT -> false
        else -> shown
    }

    /**
     * Signed dB number for display: one decimal at most, "+" for positive, a real minus sign (U+2212) for negative,
     * "0" for zero (including -0.04 and the like).
     */
    fun signedDb(v: Float): String {
        if (!v.isFinite()) return "?"
        val r = round1(v)
        if (r == 0f) return "0"
        val mag = abs(r)
        val text = if (mag == mag.roundToInt().toFloat()) mag.roundToInt().toString()
            else String.format(java.util.Locale.ROOT, "%.1f", mag)
        return (if (r > 0f) "+" else "−") + text
    }

    private fun round1(v: Float): Float = (v * 10f).roundToInt() / 10f

    // ------------------------------------------------------------------ spatial (crosstalk cancellation, pvb_xtc.h)

    /** Spatial presets on the home screen: mode + strength only (distance and head size are the listener's). */
    enum class XtcPreset(val mode: Int, val strengthDb: Float) {
        SUBTLE(PvbSettings.XTC_CENTRE, -6f),
        BALANCED(PvbSettings.XTC_FULL, -4.5f),
        CLEAR(PvbSettings.XTC_FULL, -3f),
        CUSTOM(-1, 0f),
    }

    /** Presets offered as chips (CUSTOM only appears while the settings match none of them). */
    val xtcChips = listOf(XtcPreset.SUBTLE, XtcPreset.BALANCED, XtcPreset.CLEAR)

    /** The preset the stored mode + strength amount to; CUSTOM for any other pair (also while off). */
    fun xtcPreset(mode: Int, strengthDb: Float): XtcPreset =
        xtcChips.firstOrNull { it.mode == mode && it.strengthDb == strengthDb } ?: XtcPreset.CUSTOM

    /**
     * Turning spatial back on from the home switch: the mode it had before it was turned off (the strength was left
     * as it was), or null for none (first time: the balanced preset).
     */
    fun xtcResumeMode(lastMode: Int?): Int? = lastMode?.takeIf { it == PvbSettings.XTC_CENTRE || it == PvbSettings.XTC_FULL }

    /** Distance slider: 25..60 cm in 5 cm steps (step index 0..7). */
    const val XTC_DIST_STEP_CM = 5
    fun xtcDistanceStep(cm: Float): Int =
        Math.round((cm.coerceIn(PvbSettings.XTC_DISTANCE_MIN, PvbSettings.XTC_DISTANCE_MAX) - PvbSettings.XTC_DISTANCE_MIN) / XTC_DIST_STEP_CM)
    fun xtcDistanceSteps(): Int =
        Math.round((PvbSettings.XTC_DISTANCE_MAX - PvbSettings.XTC_DISTANCE_MIN) / XTC_DIST_STEP_CM)
    fun xtcDistanceCm(step: Int): Int = (PvbSettings.XTC_DISTANCE_MIN + step * XTC_DIST_STEP_CM).toInt()
}

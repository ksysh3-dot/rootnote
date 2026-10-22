package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Alpha 3.2 "볼륨 연동 세기": the virtual bass layer gets weaker as the media volume rises.
 *
 * Why: the phone has a bass-weighted protection limiter after the volume control (UMIK-1 sine sweeps, 2026-10-21).
 * At 80% volume it already clamps 150-400 Hz for inputs above about -27 dBFS, at 50% above about -15 dBFS (about
 * 0.4 dB of threshold per volume %). Above that threshold more layer level is not louder bass; it only drives the
 * limiter harder, which ducks the midrange and raises H3. The defaults use half that slope on purpose.
 *
 * Pure Kotlin (no Android types): PvbController applies it at push time on top of the slider value, which stays what
 * the user (or the per-song memory) set and is never written back.
 */
object VolumeLevelLink {
    const val REF_PCT_DEFAULT = 40f
    const val REF_PCT_MIN = 20f
    const val REF_PCT_MAX = 70f
    const val SLOPE_DEFAULT = 0.2f      // dB of layer level per volume %
    const val SLOPE_MIN = 0.1f
    const val SLOPE_MAX = 0.5f
    const val MAX_DB_DEFAULT = 12f
    const val MAX_DB_MIN = 3f
    const val MAX_DB_MAX = 12f
    /** Lowest level the reduction may bring the layer to (dB re the 'faithful' level). */
    const val FLOOR_DB = -12f

    /**
     * Volume index -> percentage of the fine scale, the inverse of the reference mapping in PvbController
     * (refIndex = floor(pct / 100 * max) + 1; Samsung's 150-step volume: 15 indices, "80%" = index 13).
     * Index 0 (muted) or 1 -> 0%; an unknown volume (max <= 0) -> 0%.
     */
    fun volumePct(index: Int, max: Int): Float {
        if (max <= 0) return 0f
        return ((index - 1).toFloat() / max * 100f).coerceIn(0f, 100f)
    }

    /** How much weaker the layer gets at [volumePct]: clamp((volume - ref) * slope, 0, maxDb). Non-finite -> 0. */
    fun reductionDb(
        volumePct: Float,
        refPct: Float = REF_PCT_DEFAULT,
        slopeDbPerPct: Float = SLOPE_DEFAULT,
        maxDb: Float = MAX_DB_DEFAULT,
    ): Float {
        if (!volumePct.isFinite() || !refPct.isFinite() || !slopeDbPerPct.isFinite() || !maxDb.isFinite()) return 0f
        val r = (volumePct - refPct) * slopeDbPerPct
        return r.coerceIn(0f, maxDb.coerceAtLeast(0f))
    }

    /**
     * The level the engine plays: the slider value minus the reduction, not below [floorDb]. A slider value already
     * at or below the floor (for example [PvbSettings.VB_LEVEL_OFF], the silent layer of a comparison) is kept as it
     * is, so the reduction can never switch a silent layer on. A non-finite reduction counts as none.
     */
    fun effectiveLevelDb(sliderDb: Float, reductionDb: Float, floorDb: Float = FLOOR_DB): Float {
        if (!sliderDb.isFinite() || sliderDb <= floorDb) return sliderDb
        val r = if (reductionDb.isFinite()) reductionDb.coerceAtLeast(0f) else 0f
        return maxOf(sliderDb - r, floorDb)
    }

    /** Reduction for a volume index with the user's settings; link off -> 0. */
    fun reductionFor(s: PvbSettings, index: Int, max: Int): Float =
        if (!s.vbVolLink) 0f else reductionDb(volumePct(index, max), s.vbVolRefPct, s.vbVolSlope, s.vbVolMaxDb)

    /** The level the engine plays for these settings at this volume (link off -> the slider value unchanged). */
    fun levelFor(s: PvbSettings, index: Int, max: Int): Float =
        if (!s.vbVolLink) s.vbLevelDb else effectiveLevelDb(s.vbLevelDb, reductionFor(s, index, max))
}

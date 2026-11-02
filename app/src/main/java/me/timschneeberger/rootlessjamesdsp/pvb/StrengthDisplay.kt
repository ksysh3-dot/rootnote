package me.timschneeberger.rootlessjamesdsp.pvb

/** UI coordinate system only. Preferences, profiles, RN1, research records and JNI always carry actual dB. */
class StrengthDisplay(val offsetDb: Int = STRENGTH_DISPLAY_OFFSET_DB) {
    companion object {
        // Chosen later from s59. Changing this never changes the engine range or requires a storage migration.
        const val STRENGTH_DISPLAY_OFFSET_DB = 0
        val UI = StrengthDisplay()
    }

    /** Also accepts applied levels below the slider floor (volume link) and reference/silent levels. */
    fun toDisplay(actualDb: Float): Float =
        (if (actualDb.isFinite()) actualDb else PvbSettings.VB_LEVEL_DEFAULT) + offsetDb

    /** UI edits become actual dB before any persistence; limits and fallback are in actual units. */
    fun toActual(displayDb: Float, maxActualDb: Float = PvbSettings.VB_LEVEL_MAX): Float =
        (if (displayDb.isFinite()) displayDb - offsetDb else PvbSettings.VB_LEVEL_DEFAULT)
            .coerceIn(PvbSettings.VB_LEVEL_MIN, maxActualDb)

    fun sliderValue(actualDb: Float, maxActualDb: Float = PvbSettings.VB_LEVEL_MAX): Float =
        toDisplay(PvbSettings.clampLevel(actualDb).coerceAtMost(maxActualDb))

    fun range(minActualDb: Float, maxActualDb: Float): ClosedFloatingPointRange<Float> =
        toDisplay(minActualDb)..toDisplay(maxActualDb)
}

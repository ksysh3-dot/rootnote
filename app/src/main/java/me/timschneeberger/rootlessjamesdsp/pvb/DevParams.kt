package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Developer mode ("개발자 모드", general build): the values the screen exposes, their ranges and how they map to the
 * engine. Pure Kotlin (host tests). Texts are in res (strings_devmode.xml), keyed by [DevSpec.id].
 *
 * Mapping (pvb_engine.h):
 * - new engine values: generator input edge (P_D_BOUNDARY_HZ), output band (P_D_OUT_LO_HZ / P_D_OUT_HI_HZ), harmonic
 *   offsets k = 2, 3, 4, 5+ (P_D_H*_DB, re the model's own table), upper roll-off offset (P_D_ROLLOFF_DB_OCT, added to
 *   the model's 24 dB/oct, 12 for "부드러운 저음"), sustained / percussive path (P_D_SUST_DB / P_D_PERC_DB), attack and
 *   release of the P1-family track life (P_D_ATTACK_MS / P_D_RELEASE_MS, 16/3 ms hops), the speaker floor the layer's
 *   table is matched to (P_D_TABLE_SCALE = Hz / 150). They only act while
 *   [PvbSettings.devOn] (P_DEV_ON); each value at its default is the model bit for bit.
 * - existing settings: high-pass (P_HP_HZ), strength (P_VB_LEVEL_DB; up to +12 in developer mode instead of +9), volume
 *   link start / slope / maximum ([VolumeLevelLink]), and the four experimental options (P_X_*).
 *
 * The order of [ALL] is the order of the share code (format RN1, [DevShareCode]); append only.
 */
enum class DevGroup { BAND, TIME, SIZE }

/** Evidence tags of the copy source (docs/DEVMODE_COPY.md). */
enum class DevEvidence { RESEARCH, MAKER, MEASURED, ESTIMATE }

enum class DevUnit { HZ, DB, DB_OCT, MS, PCT, DB_PER_PCT, SWITCH }

/** What a value moves in the graphs (the card being touched highlights it). */
enum class DevHighlight { BOUNDARY, OUT_BAND, FUNDAMENTAL, H2, H3, H4, H5_UP, UPPER, ALL_BARS, ATTACK, RELEASE, LAYER, THRESHOLD, NONE }

data class DevSpec(
    val id: String,
    /** Key in pvb_settings ([PvbSettings]). */
    val key: String,
    val group: DevGroup,
    val unit: DevUnit,
    val min: Float,
    val max: Float,
    val step: Float,
    /** The model's own value (the device profile may override it, see [DevParams.defaultValue]). */
    val default: Float,
    /** Recommended sub-range (teal on the track); the rest of [min]..[max] is the experimental range (orange). */
    val recMin: Float,
    val recMax: Float,
    val evidence: List<DevEvidence>,
    val highlight: DevHighlight,
) {
    val isSwitch: Boolean get() = unit == DevUnit.SWITCH
    /** Number of steps from [min] to [max] (share code index range 0..steps). */
    val steps: Int get() = if (isSwitch) 1 else ((max - min) / step).roundToInt()

    /** Any number to a value on the slider grid (non-finite -> [fallback]). */
    fun snap(v: Float, fallback: Float = default): Float {
        if (isSwitch) return if (v >= 0.5f) 1f else 0f
        if (!v.isFinite()) return snap(fallback, default)
        return valueAt(indexOf(v))
    }

    fun indexOf(v: Float): Int = if (isSwitch) (if (v >= 0.5f) 1 else 0)
        else ((v.coerceIn(min, max) - min) / step).roundToInt().coerceIn(0, steps)

    fun valueAt(index: Int): Float = if (isSwitch) (if (index >= 1) 1f else 0f)
        else (min.toDouble() + index.coerceIn(0, steps) * step.toDouble()).toFloat().let { if (abs(it) < 1e-6f) 0f else it }

    fun recommended(v: Float): Boolean = isSwitch || (v >= recMin - 1e-4f && v <= recMax + 1e-4f)
}

object DevParams {
    const val KEY_DEV_ON = "pvb_dev_on"
    const val KEY_BOUNDARY = "pvb_dev_boundary_hz"
    const val KEY_OUT_LO = "pvb_dev_out_lo_hz"
    const val KEY_OUT_HI = "pvb_dev_out_hi_hz"
    const val KEY_H2 = "pvb_dev_h2_db"
    const val KEY_H3 = "pvb_dev_h3_db"
    const val KEY_H4 = "pvb_dev_h4_db"
    const val KEY_H5 = "pvb_dev_h5_db"
    const val KEY_ROLLOFF = "pvb_dev_rolloff_offset"
    const val KEY_SUST = "pvb_dev_sust_db"
    const val KEY_PERC = "pvb_dev_perc_db"
    const val KEY_ATTACK = "pvb_dev_attack_ms"
    const val KEY_RELEASE = "pvb_dev_release_ms"
    const val KEY_TABLE_FLOOR = "pvb_dev_table_floor_hz"

    /** One continuity hop of the P1 family: 16 samples at 3 kHz. */
    const val HOP_MS = 16f / 3f
    const val ATTACK_DEFAULT = 2 * HOP_MS
    const val RELEASE_DEFAULT = 6 * HOP_MS
    /** Strength cap in developer mode (the general build otherwise stops at [SafeCaps.GENERAL] +9). */
    const val DEV_VB_LEVEL_MAX = 12f
    /** Sustained upper roll-off of the model (P1 family 24 dB/oct, "부드러운 저음" 12 dB/oct). */
    fun rolloffBase(vbAlgo: Int): Float = if (vbAlgo == PvbModels.GENTLE12) 12f else 24f
    /** Recommended absolute roll-off (dB/oct), whatever the model. */
    const val ROLLOFF_REC_MIN = 12f
    const val ROLLOFF_REC_MAX = 30f

    private val R = DevEvidence.RESEARCH
    private val M = DevEvidence.MAKER
    private val S = DevEvidence.MEASURED
    private val E = DevEvidence.ESTIMATE

    /** Up to 280 Hz (the engine's limit): a speaker that stops higher than the S26 Ultra needs a higher edge (저음 맞추기). */
    val BOUNDARY = DevSpec("boundary", KEY_BOUNDARY, DevGroup.BAND, DevUnit.HZ, 100f, 280f, 5f, 190f, 140f, 260f,
        listOf(R, S), DevHighlight.BOUNDARY)
    val OUT_LO = DevSpec("out_lo", KEY_OUT_LO, DevGroup.BAND, DevUnit.HZ, 80f, 250f, 10f, 150f, 120f, 200f,
        listOf(R, S), DevHighlight.OUT_BAND)
    val OUT_HI = DevSpec("out_hi", KEY_OUT_HI, DevGroup.BAND, DevUnit.HZ, 400f, 1000f, 25f, 600f, 450f, 800f,
        listOf(R, S), DevHighlight.OUT_BAND)
    val HP = DevSpec("hp", PvbSettings.KEY_HP_HZ, DevGroup.BAND, DevUnit.HZ, 80f, 200f, 5f, 100f, 90f, 150f,
        listOf(R, M, E), DevHighlight.FUNDAMENTAL)
    val H2 = DevSpec("h2", KEY_H2, DevGroup.BAND, DevUnit.DB, -12f, 12f, 1f, 0f, -6f, 3f, listOf(R, S, E), DevHighlight.H2)
    val H3 = DevSpec("h3", KEY_H3, DevGroup.BAND, DevUnit.DB, -12f, 12f, 1f, 0f, -6f, 3f, listOf(R, S, E), DevHighlight.H3)
    val H4 = DevSpec("h4", KEY_H4, DevGroup.BAND, DevUnit.DB, -12f, 12f, 1f, 0f, -6f, 3f, listOf(R, S, E), DevHighlight.H4)
    val H5 = DevSpec("h5", KEY_H5, DevGroup.BAND, DevUnit.DB, -12f, 12f, 1f, 0f, -6f, 3f, listOf(R, S, E), DevHighlight.H5_UP)
    /** Stored as an offset to the model's slope; shown as the absolute dB/oct ([rolloffBase] + offset). */
    val ROLLOFF = DevSpec("rolloff", KEY_ROLLOFF, DevGroup.BAND, DevUnit.DB_OCT, -24f, 24f, 1f, 0f,
        ROLLOFF_REC_MIN - 24f, ROLLOFF_REC_MAX - 24f, listOf(R, S), DevHighlight.UPPER)
    val SUST = DevSpec("sust", KEY_SUST, DevGroup.BAND, DevUnit.DB, -12f, 6f, 1f, 0f, -6f, 3f, listOf(R, S), DevHighlight.ALL_BARS)
    val PERC = DevSpec("perc", KEY_PERC, DevGroup.BAND, DevUnit.DB, -12f, 6f, 1f, 0f, -6f, 3f, listOf(R, S), DevHighlight.ALL_BARS)
    val ATTACK = DevSpec("attack", KEY_ATTACK, DevGroup.TIME, DevUnit.MS, HOP_MS, 19 * HOP_MS, HOP_MS, ATTACK_DEFAULT,
        HOP_MS, 6 * HOP_MS, listOf(E), DevHighlight.ATTACK)
    val RELEASE = DevSpec("release", KEY_RELEASE, DevGroup.TIME, DevUnit.MS, HOP_MS, 56 * HOP_MS, HOP_MS, RELEASE_DEFAULT,
        4 * HOP_MS, 23 * HOP_MS, listOf(S, E), DevHighlight.RELEASE)
    val X_RISE = DevSpec("x_rise", PvbSettings.KEY_X_RISE, DevGroup.TIME, DevUnit.SWITCH, 0f, 1f, 1f, 0f, 0f, 1f,
        listOf(S), DevHighlight.ATTACK)
    val X_SMOOTH = DevSpec("x_smooth", PvbSettings.KEY_X_SMOOTH, DevGroup.TIME, DevUnit.SWITCH, 0f, 1f, 1f, 0f, 0f, 1f,
        listOf(S), DevHighlight.LAYER)
    val X_S1M = DevSpec("x_s1m", PvbSettings.KEY_X_S1M, DevGroup.TIME, DevUnit.SWITCH, 0f, 1f, 1f, 0f, 0f, 1f,
        listOf(E), DevHighlight.RELEASE)
    val STRENGTH = DevSpec("strength", PvbSettings.KEY_VB_STRENGTH_DB, DevGroup.SIZE, DevUnit.DB, 0f, DEV_VB_LEVEL_MAX, 1f,
        4f, 2f, 6f, listOf(R, M, S), DevHighlight.LAYER)
    val VOL_START = DevSpec("vol_start", PvbSettings.KEY_VB_VOL_REF_PCT, DevGroup.SIZE, DevUnit.PCT,
        VolumeLevelLink.REF_PCT_MIN, VolumeLevelLink.REF_PCT_MAX, 1f, VolumeLevelLink.REF_PCT_DEFAULT, 30f, 50f,
        listOf(M, S), DevHighlight.THRESHOLD)
    val VOL_SLOPE = DevSpec("vol_slope", PvbSettings.KEY_VB_VOL_SLOPE, DevGroup.SIZE, DevUnit.DB_PER_PCT,
        VolumeLevelLink.SLOPE_MIN, VolumeLevelLink.SLOPE_MAX, 0.01f, VolumeLevelLink.SLOPE_DEFAULT, 0.15f, 0.3f,
        listOf(M, S), DevHighlight.THRESHOLD)
    val VOL_MAX = DevSpec("vol_max", PvbSettings.KEY_VB_VOL_MAX_DB, DevGroup.SIZE, DevUnit.DB,
        VolumeLevelLink.MAX_DB_MIN, VolumeLevelLink.MAX_DB_MAX, 0.5f, VolumeLevelLink.MAX_DB_DEFAULT, 6f, 12f,
        listOf(M, S), DevHighlight.THRESHOLD)
    val X_DENSE = DevSpec("x_dense", PvbSettings.KEY_X_DENSE, DevGroup.SIZE, DevUnit.SWITCH, 0f, 1f, 1f, 0f, 0f, 1f,
        listOf(E, S), DevHighlight.LAYER)
    /**
     * Speaker floor the virtual-bass weight/gain table is matched to (P_D_TABLE_SCALE = value / 150): 150 Hz is the
     * S26 Ultra's measured floor, the model itself; set by "저음 맞추기" from the floor it finds.
     */
    val TABLE_FLOOR = DevSpec("table_floor", KEY_TABLE_FLOOR, DevGroup.BAND, DevUnit.HZ, 115f, 260f, 5f, 150f, 120f, 220f,
        listOf(S, E), DevHighlight.LAYER)

    /** Share-code order (RN1). Append only. */
    val ALL: List<DevSpec> = listOf(
        BOUNDARY, OUT_LO, OUT_HI, HP, H2, H3, H4, H5, ROLLOFF, SUST, PERC,
        ATTACK, RELEASE, X_RISE, X_SMOOTH, X_S1M,
        STRENGTH, VOL_START, VOL_SLOPE, VOL_MAX, X_DENSE,
        TABLE_FLOOR,
    )

    fun byId(id: String): DevSpec? = ALL.firstOrNull { it.id == id }
    fun group(g: DevGroup): List<DevSpec> = ALL.filter { it.group == g }

    /** Default of [spec] on this phone: the device profile's high-pass and strength, else the model's value. */
    fun defaultValue(spec: DevSpec, profileSettings: Map<String, Any>): Float {
        val fromProfile = (profileSettings[spec.key] as? Float)?.takeIf { it.isFinite() }
        return if (fromProfile != null && (spec === HP || spec === STRENGTH)) spec.snap(fromProfile) else spec.default
    }

    fun defaults(profileSettings: Map<String, Any>): FloatArray = FloatArray(ALL.size) { defaultValue(ALL[it], profileSettings) }

    /** Range of the roll-off slider (as an offset) so the absolute slope stays within 0..48 dB/oct for [vbAlgo]. */
    fun rolloffRange(vbAlgo: Int): ClosedFloatingPointRange<Float> {
        val base = rolloffBase(vbAlgo)
        return maxOf(ROLLOFF.min, -base)..minOf(ROLLOFF.max, 48f - base)
    }

    /** Current values in [ALL] order. */
    fun read(s: PvbSettings): FloatArray = FloatArray(ALL.size) { get(ALL[it], s) }

    fun get(spec: DevSpec, s: PvbSettings): Float = when (spec) {
        BOUNDARY -> s.devBoundaryHz
        OUT_LO -> s.devOutLoHz
        OUT_HI -> s.devOutHiHz
        HP -> s.hpHz
        H2 -> s.devH2Db
        H3 -> s.devH3Db
        H4 -> s.devH4Db
        H5 -> s.devH5Db
        ROLLOFF -> s.devRolloffOffset
        SUST -> s.devSustDb
        PERC -> s.devPercDb
        ATTACK -> s.devAttackMs
        RELEASE -> s.devReleaseMs
        X_RISE -> if (s.xRise) 1f else 0f
        X_SMOOTH -> if (s.xSmooth) 1f else 0f
        X_S1M -> if (s.xS1m) 1f else 0f
        STRENGTH -> s.vbLevelDb
        VOL_START -> s.vbVolRefPct
        VOL_SLOPE -> s.vbVolSlope
        VOL_MAX -> s.vbVolMaxDb
        X_DENSE -> if (s.xDense) 1f else 0f
        TABLE_FLOOR -> s.devTableFloorHz
        else -> spec.default
    }

    /** [s] with [values] (in [ALL] order) applied, each snapped to its grid. */
    fun apply(s: PvbSettings, values: FloatArray): PvbSettings {
        require(values.size == ALL.size) { "expected ${ALL.size} values" }
        fun v(spec: DevSpec) = spec.snap(values[ALL.indexOf(spec)])
        fun b(spec: DevSpec) = v(spec) >= 0.5f
        return s.copy(
            devBoundaryHz = v(BOUNDARY), devOutLoHz = v(OUT_LO), devOutHiHz = v(OUT_HI), hpHz = v(HP),
            devH2Db = v(H2), devH3Db = v(H3), devH4Db = v(H4), devH5Db = v(H5), devRolloffOffset = v(ROLLOFF),
            devSustDb = v(SUST), devPercDb = v(PERC), devAttackMs = v(ATTACK), devReleaseMs = v(RELEASE),
            xRise = b(X_RISE), xSmooth = b(X_SMOOTH), xS1m = b(X_S1M), vbLevelDb = v(STRENGTH),
            vbVolRefPct = v(VOL_START), vbVolSlope = v(VOL_SLOPE), vbVolMaxDb = v(VOL_MAX), xDense = b(X_DENSE),
            devTableFloorHz = v(TABLE_FLOOR),
        )
    }

    /** Writes [values] (in [ALL] order) as preferences: switches as booleans, everything else as floats. */
    fun write(values: FloatArray, putFloat: (String, Float) -> Unit, putBoolean: (String, Boolean) -> Unit) {
        require(values.size == ALL.size) { "expected ${ALL.size} values" }
        ALL.forEachIndexed { i, spec ->
            val v = spec.snap(values[i])
            if (spec.isSwitch) putBoolean(spec.key, v >= 0.5f) else putFloat(spec.key, v)
        }
    }

    /** True when every value equals its default (nothing for the "되돌리기" buttons to do). */
    fun allDefault(values: FloatArray, defaults: FloatArray): Boolean =
        values.indices.all { ALL[it].indexOf(values[it]) == ALL[it].indexOf(defaults[it]) }

    /** [values] with every value of [group] (or all, null) back at [defaults]. */
    fun reset(values: FloatArray, defaults: FloatArray, group: DevGroup?): FloatArray =
        FloatArray(values.size) { if (group == null || ALL[it].group == group) defaults[it] else values[it] }

    /** Load-time clamp of a stored developer value (unknown keys unchanged). */
    fun clampStored(key: String, v: Float): Float = ALL.firstOrNull { it.key == key }?.snap(v) ?: v
}

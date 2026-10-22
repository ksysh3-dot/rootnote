package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.max
import kotlin.math.min

/**
 * Volume-linked low-mid gain (design doc, section 6).
 *
 * Quieter than the reference volume: the bell gain rises by [slope] dB per dB of level drop (0.19 follows
 * the ISO 226 equal-loudness contours at 200 Hz around 70 phon), up to [capDb] in total.
 * Louder than the reference: the gain moves from [baseDb] towards [atMaxDb] at maximum volume, because the
 * phone already cuts more low end there.
 */
object VolumeCompensation {
    fun lowGainDb(
        baseDb: Float,
        dropDb: Float,
        riseAtMaxDb: Float,
        slope: Float,
        capDb: Float,
        atMaxDb: Float,
    ): Float {
        if (!dropDb.isFinite()) return baseDb
        return if (dropDb >= 0f) {
            min(baseDb + slope * dropDb, max(capDb, baseDb))
        } else {
            val t = if (riseAtMaxDb > 0.1f) (-dropDb / riseAtMaxDb).coerceIn(0f, 1f) else 1f
            baseDb + (atMaxDb - baseDb) * t
        }
    }

    /**
     * Whether the dB values the platform reports per volume index (index 1..max, [table] index = volume
     * index, entry 0 unused) look like a real volume curve. Some phones (Samsung) apply the media volume
     * somewhere else and report about 0 dB for every index; such a table would make the volume link think
     * the volume never changes.
     */
    fun plausibleSystemTable(table: FloatArray): Boolean {
        if (table.size < 3) return false
        for (i in 1 until table.size) {
            val v = table[i]
            if (!v.isFinite() || v <= -150f || v > 6f) return false
            if (i > 1 && v < table[i - 1] - 0.05f) return false
        }
        return table[table.size - 1] - table[1] >= MIN_PLAUSIBLE_SPAN_DB
    }

    private const val MIN_PLAUSIBLE_SPAN_DB = 12f

    /**
     * Android's default speaker volume curve (fraction of the maximum index -> dB), used when the platform
     * does not report a usable dB value for a volume index.
     */
    private val FALLBACK_CURVE = arrayOf(
        floatArrayOf(0.01f, -56f),
        floatArrayOf(0.20f, -34f),
        floatArrayOf(0.60f, -11f),
        floatArrayOf(1.00f, 0f),
    )

    fun fallbackDb(fraction: Float): Float {
        val f = fraction.coerceIn(0f, 1f)
        if (f <= FALLBACK_CURVE[0][0]) return FALLBACK_CURVE[0][1]
        for (i in 1 until FALLBACK_CURVE.size) {
            val (x1, y1) = FALLBACK_CURVE[i].let { it[0] to it[1] }
            if (f <= x1) {
                val (x0, y0) = FALLBACK_CURVE[i - 1].let { it[0] to it[1] }
                return y0 + (f - x0) / (x1 - x0) * (y1 - y0)
            }
        }
        return 0f
    }
}

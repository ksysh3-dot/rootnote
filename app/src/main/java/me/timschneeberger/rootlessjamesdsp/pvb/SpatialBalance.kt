package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Spatial "좌우 맞추기", measured with the phone's own microphones (pure logic; tested on the host JVM by
 * SpatialBalanceTest). The phone plays a sweep from the left channel only, then from the right channel only
 * ([DevTestKind.XTC_SWEEP_L] / [DevTestKind.XTC_SWEEP_R]), while it records its two microphones (top and bottom).
 *
 * Cross method: for speaker S and microphone m the recorded band power is S * M_m * P(distance m-S). Per mic the
 * ratio left / right is S_L / S_R times a path ratio, and the path ratios of the two mics are inverse to each other
 * (each mic is near one speaker and far from the other), so the geometric mean of the two mics' ratios is S_L / S_R:
 * the microphones' own responses and the distances cancel. If both channels carry the same microphone
 * ([Result.distinctMics] false) the path does not cancel and the result is only indicative.
 *
 * Result: "the left speaker is this many dB louder" per third-octave band, and the two averages the engine takes
 * (400-1250 Hz -> P_XTC_BAL_LO_DB, 1.6-8 kHz -> P_XTC_BAL_HI_DB).
 */
object SpatialBalance {
    /** Third-octave centres in the spatial band. */
    val BANDS = doubleArrayOf(400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0, 2500.0, 3150.0, 4000.0,
        5000.0, 6300.0, 8000.0)
    const val SPLIT_HZ = 1500.0
    /** Band power at least this much above the noise floor (dB) to count. */
    const val MIN_SNR_DB = 10.0

    /** A stereo recording: interleaved samples of the two microphone channels. */
    class Recording(val samples: FloatArray, val frames: Int)

    data class Result(
        val loDb: Float,
        val hiDb: Float,
        /** Per band (left louder, dB), NaN where the band was too close to the noise. */
        val bandsDb: List<Double>,
        /** The two channels are different microphones (the cross method holds). */
        val distinctMics: Boolean,
        /** Enough bands above the noise on both sides of [SPLIT_HZ]. */
        val usable: Boolean,
    )

    /** Band powers (mean square) of channel [ch] of [r] for every band in [BANDS] (two cascaded RBJ band-passes). */
    fun bandPowers(r: Recording, ch: Int, sampleRate: Int): DoubleArray {
        val out = DoubleArray(BANDS.size)
        for ((i, f0) in BANDS.withIndex()) {
            if (f0 >= sampleRate * 0.45) { out[i] = Double.NaN; continue }
            val w = 2 * PI * f0 / sampleRate
            val q = 4.32  // a third of an octave
            val al = sin(w) / (2 * q)
            val a0 = 1 + al
            val b0 = al / a0
            val b2 = -al / a0
            val a1 = -2 * cos(w) / a0
            val a2 = (1 - al) / a0
            var z1 = 0.0; var z2 = 0.0; var y1 = 0.0; var y2 = 0.0
            var sum = 0.0
            for (n in 0 until r.frames) {
                val x = r.samples[2 * n + ch].toDouble()
                val u = b0 * x + z1
                z1 = -a1 * u + z2
                z2 = b2 * x - a2 * u
                val y = b0 * u + y1
                y1 = -a1 * y + y2
                y2 = b2 * u - a2 * y
                sum += y * y
            }
            out[i] = sum / r.frames.coerceAtLeast(1)
        }
        return out
    }

    /** True if the two channels are (nearly) the same signal: one microphone copied to both. */
    fun sameChannels(r: Recording): Boolean {
        var ab = 0.0; var aa = 0.0; var bb = 0.0
        for (n in 0 until r.frames) {
            val a = r.samples[2 * n].toDouble()
            val b = r.samples[2 * n + 1].toDouble()
            ab += a * b; aa += a * a; bb += b * b
        }
        if (aa <= 0.0 || bb <= 0.0) return false
        val corr = ab / sqrt(aa * bb)
        return corr > 0.999 && abs(10 * log10(aa / bb)) < 0.3
    }

    /**
     * [noise]: a recording of the room with nothing playing; [left] / [right]: recordings made while the left /
     * right sweep played (several each are summed).
     */
    fun analyze(noise: Recording, left: List<Recording>, right: List<Recording>, sampleRate: Int): Result {
        val nz = Array(2) { bandPowers(noise, it, sampleRate) }
        fun mean(recs: List<Recording>, ch: Int): DoubleArray {
            val acc = DoubleArray(BANDS.size)
            for (r in recs) bandPowers(r, ch, sampleRate).forEachIndexed { i, p -> acc[i] += p / recs.size }
            return acc
        }
        val l = Array(2) { mean(left, it) }
        val r = Array(2) { mean(right, it) }
        val bands = BANDS.indices.map { i ->
            var sum = 0.0
            for (m in 0..1) {
                val el = l[m][i] - nz[m][i]
                val er = r[m][i] - nz[m][i]
                val floor = nz[m][i] * Math.pow(10.0, MIN_SNR_DB / 10)
                if (!(el > floor && er > floor) || el.isNaN() || er.isNaN()) return@map Double.NaN
                sum += 10 * log10(el / er)
            }
            sum / 2   // geometric mean of the two mics' power ratios, in dB
        }
        val distinct = (left + right).none { sameChannels(it) }
        fun avg(sel: (Double) -> Boolean): Double? {
            val v = BANDS.indices.filter { sel(BANDS[it]) }.map { bands[it] }.filter { !it.isNaN() }
            return if (v.size >= 3) v.average() else null
        }
        val lo = avg { it < SPLIT_HZ }
        val hi = avg { it >= SPLIT_HZ }
        return Result(
            loDb = PvbSettings.clampBalance((lo ?: 0.0).toFloat()),
            hiDb = PvbSettings.clampBalance((hi ?: 0.0).toFloat()),
            bandsDb = bands,
            distinctMics = distinct,
            usable = lo != null && hi != null,
        )
    }
}

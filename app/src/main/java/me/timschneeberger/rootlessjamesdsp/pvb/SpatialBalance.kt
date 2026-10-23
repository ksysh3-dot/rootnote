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
 * Limits (code review 2026-10-23, F1/F2): the cancellation needs the two path ratios to be exact inverses, which a
 * real phone only approximates (mic port placement, directivity, the hand). The leftover is
 * 10·log10((H_L0·H_L1)/(H_R0·H_R1)) dB for amplitude transfers H and cannot be seen in the recordings (three
 * unknowns, two equations). So the result is an estimate for this grip: [Result.reliable] only says the recording was
 * sound (two microphones positively told apart, the runs agree, enough signal), never that the path assumption holds.
 * A mixed (beamformed) pair or a per-channel level stage can still pass, so the screen never saves a measured value
 * directly: a sound result only places the by-ear slider, and the listener's "저장" is what stores it. Two microphones are established positively: the per-mic
 * left/right ratios must differ clearly ([MIN_MIC_SPREAD_DB]); one microphone copied to both channels with any gain,
 * delay or filter gives the same ratio on both channels, and the recorder's own microphone list
 * (AudioRecord.getActiveMicrophones, [analyze] micsReported) overrides when it reports a single microphone.
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
    /** The two microphones' left/right ratios differ at least this much on average (dB) for two microphones. */
    const val MIN_MIC_SPREAD_DB = 4.0
    /** ...with the same sign in at least this share of the valid bands. */
    const val MIN_SPREAD_AGREEMENT = 0.8
    /** The repeated runs agree within this (median over bands and mics, worse side, dB) for a reliable result. */
    const val MAX_REPEAT_DB = 1.0
    /** ...and no more than a tenth of the bands differ by more than this (a burst in a few bands, dB). */
    const val MAX_REPEAT_WORST_DB = 3.0
    /** Lags (samples, either way) tried when looking for one microphone copied to both channels. */
    const val CLONE_MAX_LAG = 48

    /** A stereo recording: interleaved samples of the two microphone channels. */
    class Recording(val samples: FloatArray, val frames: Int)

    data class Result(
        val loDb: Float,
        val hiDb: Float,
        /** Per band (left louder, dB), NaN where the band was too close to the noise. */
        val bandsDb: List<Double>,
        /**
         * Two different microphones, established positively: not a copy of one channel, the two hear the speakers
         * clearly differently ([micSpreadDb]), and the recorder did not report a single microphone.
         */
        val distinctMics: Boolean,
        /** Enough bands above the noise on both sides of [SPLIT_HZ]. */
        val usable: Boolean,
        /** Mean over the valid bands of mic 0's left/right ratio minus mic 1's (dB); 0 for one microphone. */
        val micSpreadDb: Double = Double.NaN,
        /** Difference between the first two runs of each side (dB, the worse side's median); NaN with one run per side. */
        val repeatDb: Double = Double.NaN,
        /** The same, the worse side's 90th percentile (a burst confined to a few bands). */
        val repeatWorstDb: Double = Double.NaN,
        /** Microphones the recorder reported (AudioRecord.getActiveMicrophones); -1 when unknown. */
        val micsReported: Int = -1,
    ) {
        /**
         * The recording itself was sound: usable, two microphones, repeatable. Not a proof that the paths cancel
         * (see the class notes): the value is still offered as an estimate to confirm by ear.
         */
        val reliable: Boolean get() = usable && distinctMics && !(repeatDb > MAX_REPEAT_DB) && !(repeatWorstDb > MAX_REPEAT_WORST_DB)
    }

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

    /**
     * True if the two channels are one signal: one microphone copied to both, at any level and up to
     * [CLONE_MAX_LAG] samples apart (normalised cross-correlation, so a gain difference does not hide it).
     */
    fun sameChannels(r: Recording): Boolean {
        var aa = 0.0; var bb = 0.0
        for (n in 0 until r.frames) {
            val a = r.samples[2 * n].toDouble()
            val b = r.samples[2 * n + 1].toDouble()
            aa += a * a; bb += b * b
        }
        if (aa <= 0.0 || bb <= 0.0) return false
        val norm = sqrt(aa * bb)
        for (lag in -CLONE_MAX_LAG..CLONE_MAX_LAG) {
            var ab = 0.0
            val from = maxOf(0, -lag)
            val to = minOf(r.frames, r.frames - lag)
            for (n in from until to) ab += r.samples[2 * n].toDouble() * r.samples[2 * (n + lag) + 1].toDouble()
            if (abs(ab) / norm > 0.999) return true
        }
        return false
    }

    /**
     * [noise]: a recording of the room with nothing playing; [left] / [right]: recordings made while the left /
     * right sweep played (several each are summed).
     */
    fun analyze(
        noise: Recording,
        left: List<Recording>,
        right: List<Recording>,
        sampleRate: Int,
        micsReported: Int = -1,
    ): Result {
        val nz = Array(2) { bandPowers(noise, it, sampleRate) }
        val lRuns = left.map { rec -> Array(2) { bandPowers(rec, it, sampleRate) } }
        val rRuns = right.map { rec -> Array(2) { bandPowers(rec, it, sampleRate) } }
        fun mean(runs: List<Array<DoubleArray>>, ch: Int): DoubleArray {
            val acc = DoubleArray(BANDS.size)
            for (run in runs) run[ch].forEachIndexed { i, p -> acc[i] += p / runs.size }
            return acc
        }
        val l = Array(2) { mean(lRuns, it) }
        val r = Array(2) { mean(rRuns, it) }
        fun above(p: Double, m: Int, i: Int): Boolean {
            val e = p - nz[m][i]
            return !e.isNaN() && e > nz[m][i] * Math.pow(10.0, MIN_SNR_DB / 10)
        }
        // per band: each mic's left/right ratio (dB), NaN where either side is too close to the noise
        val perMic = Array(2) { DoubleArray(BANDS.size) { Double.NaN } }
        val bands = BANDS.indices.map { i ->
            var sum = 0.0
            for (m in 0..1) {
                if (!above(l[m][i], m, i) || !above(r[m][i], m, i)) return@map Double.NaN
                val d = 10 * log10((l[m][i] - nz[m][i]) / (r[m][i] - nz[m][i]))
                perMic[m][i] = d
                sum += d
            }
            sum / 2   // geometric mean of the two mics' power ratios, in dB
        }
        // two microphones, positively: the two hear the speakers clearly differently, in the same direction across
        // the bands (one mic copied to both channels gives equal ratios whatever its gain, delay or filter)
        val spreads = BANDS.indices.filter { !bands[it].isNaN() }.map { perMic[0][it] - perMic[1][it] }
        val spread = if (spreads.isEmpty()) Double.NaN else spreads.average()
        val agree = if (spreads.isEmpty()) 0.0 else spreads.count { it * spread > 0 }.toDouble() / spreads.size
        val copied = (left + right).any { sameChannels(it) }
        val distinct = !copied && micsReported != 1 && !spread.isNaN() &&
            abs(spread) >= MIN_MIC_SPREAD_DB && agree >= MIN_SPREAD_AGREEMENT
        // repeatability: the first two runs of each side, per band and mic where both are clear of the noise; the
        // worse side's median
        var repeat = Double.NaN
        var repeatWorst = Double.NaN
        for (runs in listOf(lRuns, rRuns)) {
            if (runs.size < 2) continue
            val diffs = ArrayList<Double>()
            for (m in 0..1) for (i in BANDS.indices) {
                val a = runs[0][m][i]; val b = runs[1][m][i]
                if (above(a, m, i) && above(b, m, i)) diffs += abs(10 * log10((a - nz[m][i]) / (b - nz[m][i])))
            }
            if (diffs.isEmpty()) continue
            val sorted = diffs.sorted()
            val median = sorted[sorted.size / 2]
            val p90 = sorted[minOf(sorted.size - 1, (sorted.size * 9) / 10)]
            if (repeat.isNaN() || median > repeat) repeat = median
            if (repeatWorst.isNaN() || p90 > repeatWorst) repeatWorst = p90
        }
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
            micSpreadDb = spread,
            repeatDb = repeat,
            repeatWorstDb = repeatWorst,
            micsReported = micsReported,
        )
    }
}

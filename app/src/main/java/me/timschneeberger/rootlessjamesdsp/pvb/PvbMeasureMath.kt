package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Signal generation and analysis for the in-app measurement (no Android dependencies, so it runs in the JVM test).
 */
object PvbMeasureMath {
    /** Octave bands 125 Hz .. 4 kHz, then the broadband level 300 Hz .. 5 kHz used as "the level". */
    val BAND_HZ = doubleArrayOf(125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0)
    const val BROAD = 6
    val BAND_EDGES: List<Pair<Double, Double>> =
        BAND_HZ.map { it / sqrt(2.0) to it * sqrt(2.0) } + listOf(300.0 to 5000.0)

    fun db(p: Double): Double = 10.0 * log10(max(p, 1e-20))

    /** A measured point needs at least this much signal above the background. */
    const val MIN_SNR_DB = 12.0
    /** Microphone peak at or above this may be clipped. */
    const val MAX_MIC_PEAK = 0.98
    /** Repeat measurements agree within about 0.3 dB (stable()), so a compressor curve may dip that much. */
    const val MONOTONIC_TOL_DB = 0.3
    /** The output-headroom plan is only used if its microphone check came out within this (a start, not a norm). */
    const val STAGE_TOL_DB = 0.5

    /**
     * The one acceptance rule for every measured point, used while measuring and again whenever a curve is rebuilt
     * from the saved JSON: the level settled (two windows agree), the phone took the volume step (readback), enough
     * signal above the background, the microphone not near clipping, and a finite level.
     */
    fun acceptPoint(stable: Boolean, readbackOk: Boolean, snrDb: Double, micPeak: Double, levelDb: Double): Boolean =
        stable && readbackOk && snrDb.isFinite() && snrDb >= MIN_SNR_DB && micPeak.isFinite() && micPeak < MAX_MIC_PEAK &&
            levelDb.isFinite()

    /** Points sorted by digital level, finite, and rising (within [MONOTONIC_TOL_DB]): fit for interpolation. */
    fun curveUsable(p: DoubleArray, l: DoubleArray): Boolean {
        if (p.size != l.size || p.size < 3) return false
        for (i in p.indices) if (!p[i].isFinite() || !l[i].isFinite()) return false
        for (i in 1 until p.size) {
            if (p[i] <= p[i - 1]) return false
            if (l[i] < l[i - 1] - MONOTONIC_TOL_DB) return false
        }
        return true
    }

    /**
     * Whether the microphone check of an output-headroom plan allows using it now: measured at this volume
     * [base], for the same plan, both sides accepted, and the two sides within [STAGE_TOL_DB].
     */
    fun stageCheckOk(base: Int, checkBase: Int, checkSteps: Int, planSteps: Int, checkDropDb: Double, planDropDb: Double,
                     sidesOk: Boolean, residualDb: Double): Boolean =
        base == checkBase && checkSteps == planSteps && kotlin.math.abs(checkDropDb - planDropDb) <= 0.15 && sidesOk &&
            residualDb.isFinite() && kotlin.math.abs(residualDb) <= STAGE_TOL_DB

    /** Pink noise (Paul Kellet's filter on white noise), roughly unit RMS. */
    class Pink(seed: Long) {
        private val rnd = java.util.Random(seed)
        private var b0 = 0.0; private var b1 = 0.0; private var b2 = 0.0; private var b3 = 0.0
        private var b4 = 0.0; private var b5 = 0.0; private var b6 = 0.0

        fun next(): Double {
            val w = rnd.nextGaussian()
            b0 = 0.99886 * b0 + w * 0.0555179
            b1 = 0.99332 * b1 + w * 0.0750759
            b2 = 0.96900 * b2 + w * 0.1538520
            b3 = 0.86650 * b3 + w * 0.3104856
            b4 = 0.55000 * b4 + w * 0.5329522
            b5 = -0.7616 * b5 - w * 0.0168980
            val out = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362
            b6 = w * 0.115926
            return out * 0.11
        }
    }

    /** RBJ biquad (direct form I, double). */
    class Biquad(private val b0: Double, private val b1: Double, private val b2: Double,
                 private val a1: Double, private val a2: Double) {
        private var x1 = 0.0; private var x2 = 0.0; private var y1 = 0.0; private var y2 = 0.0
        fun tick(x: Double): Double {
            val y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2 = x1; x1 = x; y2 = y1; y1 = y
            return y
        }

        companion object {
            private fun make(fs: Double, f: Double, high: Boolean): Biquad {
                val w = 2 * PI * f / fs
                val alpha = sin(w) / (2 * 0.7071067811865476)
                val c = cos(w)
                val a0 = 1 + alpha
                return if (high) Biquad((1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0, -2 * c / a0, (1 - alpha) / a0)
                else Biquad((1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0, -2 * c / a0, (1 - alpha) / a0)
            }
            fun highpass(fs: Double, f: Double) = make(fs, f, true)
            fun lowpass(fs: Double, f: Double) = make(fs, f, false)
        }
    }

    /**
     * Band-limited pink noise with a known RMS: [hpHz] 4th-order high-pass, optional [lpHz] 4th-order low-pass.
     * [next] returns samples whose RMS is 1 (calibrated on 4 s of the same generator).
     */
    class Noise(private val fs: Double, private val hpHz: Double, private val lpHz: Double?, seed: Long) {
        private val pink = Pink(seed)
        private val f = buildList {
            add(Biquad.highpass(fs, hpHz)); add(Biquad.highpass(fs, hpHz))
            if (lpHz != null) { add(Biquad.lowpass(fs, lpHz)); add(Biquad.lowpass(fs, lpHz)) }
        }
        private val gain: Double

        init {
            val cal = Noise.raw(fs, hpHz, lpHz, seed + 1, (4 * fs).toInt())
            gain = 1.0 / sqrt(cal)
            repeat((0.5 * fs).toInt()) { step() }   // let the filters settle
        }

        private fun step(): Double {
            var v = pink.next()
            for (b in f) v = b.tick(v)
            return v
        }

        fun next(): Double = step() * gain

        companion object {
            /** Mean square of the unscaled generator. */
            fun raw(fs: Double, hp: Double, lp: Double?, seed: Long, n: Int): Double {
                val p = Pink(seed)
                val f = buildList {
                    add(Biquad.highpass(fs, hp)); add(Biquad.highpass(fs, hp))
                    if (lp != null) { add(Biquad.lowpass(fs, lp)); add(Biquad.lowpass(fs, lp)) }
                }
                repeat((0.5 * fs).toInt()) { var v = p.next(); for (b in f) v = b.tick(v) }
                var s = 0.0
                repeat(n) { var v = p.next(); for (b in f) v = b.tick(v); s += v * v }
                return s / n
            }
        }
    }

    /** In-place radix-2 FFT. */
    fun fft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j xor bit
            if (i < j) {
                var t = re[i]; re[i] = re[j]; re[j] = t
                t = im[i]; im[i] = im[j]; im[j] = t
            }
        }
        var len = 2
        while (len <= n) {
            val ang = -2 * PI / len
            val wr = cos(ang); val wi = sin(ang)
            var i = 0
            while (i < n) {
                var cr = 1.0; var ci = 0.0
                for (k in 0 until len / 2) {
                    val ur = re[i + k]; val ui = im[i + k]
                    val vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci
                    val vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr
                    re[i + k] = ur + vr; im[i + k] = ui + vi
                    re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi
                    val nr = cr * wr - ci * wi
                    ci = cr * wi + ci * wr
                    cr = nr
                }
                i += len
            }
            len = len shl 1
        }
    }

    /**
     * Band levels (dB, mean square per sample within each band of [BAND_EDGES]) of x[from until to]:
     * Welch average of 4096-point Hann frames with 50 % overlap. A full-scale sine reads -3 dB in its band.
     */
    fun bandLevels(x: FloatArray, from: Int, to: Int, fs: Double): DoubleArray {
        val n = 4096
        val hop = n / 2
        val win = DoubleArray(n) { 0.5 - 0.5 * cos(2 * PI * it / n) }
        val wss = win.sumOf { it * it }
        val acc = DoubleArray(n / 2 + 1)
        var frames = 0
        var start = from
        val re = DoubleArray(n); val im = DoubleArray(n)
        while (start + n <= to) {
            for (i in 0 until n) { re[i] = x[start + i] * win[i]; im[i] = 0.0 }
            fft(re, im)
            for (k in 0..n / 2) acc[k] += re[k] * re[k] + im[k] * im[k]
            frames++
            start += hop
        }
        val out = DoubleArray(BAND_EDGES.size)
        if (frames == 0) return out.also { it.fill(-200.0) }
        for ((b, e) in BAND_EDGES.withIndex()) {
            var s = 0.0
            for (k in 0..n / 2) {
                val f = k * fs / n
                if (f >= e.first && f < e.second) s += acc[k] * (if (k == 0 || k == n / 2) 1.0 else 2.0)
            }
            out[b] = db(s / frames / wss / n)
        }
        return out
    }

    fun peak(x: FloatArray, from: Int, to: Int): Double {
        var p = 0.0
        for (i in from until to) p = max(p, kotlin.math.abs(x[i].toDouble()))
        return p
    }

    /** Linear interpolation of y(x) over sorted xs (clamped at the ends). */
    fun interp(xs: DoubleArray, ys: DoubleArray, x: Double): Double {
        if (x <= xs.first()) return ys.first()
        if (x >= xs.last()) return ys.last()
        for (i in 1 until xs.size) {
            if (x <= xs[i]) {
                val t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
                return ys[i - 1] + t * (ys[i] - ys[i - 1])
            }
        }
        return ys.last()
    }

    /**
     * Plan for the output-headroom comparison: raise the volume by k steps and lower our output by X dB so the
     * level after the phone stays the same. [volDb] measured level per volume index (NaN = unreliable),
     * [compP]/[compL] measured level after the phone vs our digital level (pink noise), [p0] the usual level of
     * our output. Picks the k whose X is closest to [targetX] within 6..14 dB.
     */
    data class StagePlan(val steps: Int, val outDropDb: Double, val volumeGainDb: Double, val phoneLossDb: Double)

    fun stagePlan(volDb: DoubleArray, base: Int, compP: DoubleArray, compL: DoubleArray, p0: Double = -18.0,
                  targetX: Double = 10.0): StagePlan? {
        if (base !in volDb.indices || volDb[base].isNaN() || !curveUsable(compP, compL)) return null
        // only inside the measured range: no extrapolation (interp would clamp at the ends)
        if (p0 > compP.last() || p0 - 6.0 < compP.first()) return null
        val xMax = minOf(14.0, p0 - compP.first())
        fun lossAt(x: Double) = interp(compP, compL, p0) - interp(compP, compL, p0 - x)
        var best: StagePlan? = null
        for (k in 1..6) {
            val i = base + k
            if (i !in volDb.indices || volDb[i].isNaN()) break
            val v = volDb[i] - volDb[base]
            // smallest X in 6..14 (within the measured range) where the output loss after the phone reaches the volume gain
            var x = 6.0
            var found = Double.NaN
            while (x <= xMax + 1e-9) {
                if (lossAt(x) >= v) { found = x; break }
                x += 0.1
            }
            if (found.isNaN() || lossAt(6.0) > v) continue
            val plan = StagePlan(k, found, v, lossAt(found))
            if (best == null || kotlin.math.abs(found - targetX) < kotlin.math.abs(best.outDropDb - targetX)) best = plan
        }
        return best
    }
}

package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * "저음 검사" (developer mode, experimental): how low this phone's speakers play, and how cleanly, measured with the
 * phone's own microphones. It decides nothing by itself: the result is shown as an estimate and is to be checked
 * against a measurement microphone (S26U and UMIK-1) before any value is derived from it.
 *
 * Signal ([DevTestKind.BASS_STEPS]): 1 s of silence (noise floor), then tones at 23 frequencies (80 Hz-905 Hz in
 * sixth-octave steps, and 1 kHz as the reference), each 0.40 s with a 0.15 s gap, at -24, then -18, then -12 dBFS
 * (the loudest last). About 39 s.
 *
 * What is measured per step, from the two microphones' power (Goertzel at f, 2f, 3f in the middle 0.25 s of the
 * tone): the fundamental, the 2nd and 3rd harmonics relative to it, and the signal-to-noise ratio against the
 * silence at the start. Only relative values are used (re the 1 kHz step, harmonics re the fundamental, level
 * growth between levels), because the microphones' own response and the 1-3 cm distance to the speaker are unknown.
 *
 * Derived:
 * - response: fundamental at -18 dBFS re 1 kHz;
 * - growth: fundamental at -12 minus at -18 dBFS (6 dB when linear; less = compression);
 * - clean: harmonics (2nd + 3rd) at least 20 dB below the fundamental at -12 dBFS, growth at least 5 dB, SNR >= 15 dB;
 * - [Result.kneeHz]: the lowest frequency from which the response stays at or above -10 dB up to 1 kHz;
 * - [Result.cleanFromHz]: the lowest frequency from which every step is clean up to 1 kHz.
 *
 * Known biases (why it is an estimate): vibration through the phone's body reaching the microphones (bass reads too
 * strong), the near field of the speaker, a microphone high-pass or processing. Two passes must agree
 * ([agreementDb]); a placement that changes the result (on a table vs held) shows such a bias.
 *
 * Pure Kotlin (host-tested in tools/pvb-harness/jvm/BassCheckTest.kt).
 */
object BassCheck {
    const val LEAD_S = 1.0
    const val TONE_S = 0.40
    const val GAP_S = 0.15
    const val STEP_S = TONE_S + GAP_S
    const val FADE_S = 0.01
    /** Analysis window inside a tone (after the onset and the latency), seconds. */
    const val WIN_START_S = 0.10
    const val WIN_S = 0.25
    const val REF_HZ = 1000.0
    val LEVELS_DB = doubleArrayOf(-24.0, -18.0, -12.0)
    /** 80 Hz * 2^(k/6), k = 0..21 (80-905 Hz), then 1 kHz. */
    val FREQS: DoubleArray = DoubleArray(23) { k -> if (k < 22) 80.0 * 2.0.pow(k / 6.0) else REF_HZ }

    const val MIN_SNR_DB = 15.0
    const val MAX_HARMONICS_DB = -20.0
    const val MIN_GROWTH_DB = 5.0
    const val KNEE_DB = -10.0
    const val MAX_LATENCY_S = 1.5

    data class Step(val index: Int, val hz: Double, val levelDb: Double) {
        val amplitude: Double get() = 10.0.pow(levelDb / 20.0)
    }

    /** Level-major: every frequency at -24 dBFS, then at -18, then at -12. */
    val STEPS: List<Step> = LEVELS_DB.flatMapIndexed { li, db -> FREQS.mapIndexed { fi, f -> Step(li * FREQS.size + fi, f, db) } }

    val DURATION_S: Double = LEAD_S + STEPS.size * STEP_S

    fun stepStart(index: Int): Double = LEAD_S + index * STEP_S

    /** The step sounding at [time] (seconds since the sound started), or null in the lead, a gap or after the end. */
    fun stepAt(time: Double): Step? {
        if (time < LEAD_S) return null
        val i = ((time - LEAD_S) / STEP_S).toInt()
        if (i >= STEPS.size) return null
        return if (time - stepStart(i) < TONE_S) STEPS[i] else null
    }

    class StepResult(
        val step: Step,
        val fundDb: Double,
        val harmonicsDb: Double,   // 2nd + 3rd re the fundamental
        val snrDb: Double,
    )

    class Result(
        val latencyS: Double,
        val steps: List<StepResult>,
        /** Fundamental at -18 dBFS re 1 kHz, per frequency (NaN when below the noise). */
        val responseDb: DoubleArray,
        /** Fundamental at -12 minus at -18 dBFS, per frequency. */
        val growthDb: DoubleArray,
        /** Harmonics re the fundamental at -12 dBFS, per frequency. */
        val harmonicsDb: DoubleArray,
        val clean: BooleanArray,
        val kneeHz: Double?,
        val cleanFromHz: Double?,
        /** The reference step was heard well enough to measure anything. */
        val usable: Boolean,
    )

    private fun goertzelPower(x: FloatArray, ch: Int, from: Int, n: Int, hz: Double, sr: Int): Double {
        val w = 2 * PI * hz / sr
        val c = 2 * cos(w)
        var s1 = 0.0
        var s2 = 0.0
        for (k in 0 until n) {
            // Hann window: no leakage from the fundamental into the harmonic bins
            val win = 0.5 - 0.5 * cos(2 * PI * k / (n - 1))
            val s0 = x[2 * (from + k) + ch] * win + c * s1 - s2
            s2 = s1
            s1 = s0
        }
        return (s1 * s1 + s2 * s2 - c * s1 * s2) / (n * n)
    }

    private fun power(x: FloatArray, from: Int, n: Int, hz: Double, sr: Int): Double =
        0.5 * (goertzelPower(x, 0, from, n, hz, sr) + goertzelPower(x, 1, from, n, hz, sr))

    private fun db(p: Double): Double = 10 * log10(max(p, 1e-30))

    /**
     * Where the tones start in the recording: the lag (0..[MAX_LATENCY_S]) that best lines the 10 ms envelope up with
     * the schedule's tones at 400 Hz and above (the ones every phone plays).
     */
    fun latency(x: FloatArray, frames: Int, sr: Int): Double {
        val hop = sr / 100
        val env = DoubleArray(frames / hop) { i ->
            var s = 0.0
            for (k in 0 until hop) { val a = x[2 * (i * hop + k)].toDouble(); val b = x[2 * (i * hop + k) + 1].toDouble(); s += a * a + b * b }
            sqrt(s / (2 * hop))
        }
        val sched = DoubleArray(env.size) { i ->
            val st = stepAt(i * 0.01 + 0.005)
            if (st != null && st.hz >= 400.0) st.amplitude else 0.0
        }
        var best = 0
        var bestScore = Double.NEGATIVE_INFINITY
        for (lag in 0..(MAX_LATENCY_S * 100).toInt()) {
            var s = 0.0
            for (i in sched.indices) { val j = i + lag; if (j < env.size) s += sched[i] * env[j] }
            if (s > bestScore) { bestScore = s; best = lag }
        }
        return best * 0.01
    }

    /** Analyses one recording of [DevTestKind.BASS_STEPS] (interleaved stereo float, [frames] frames at [sr]). */
    fun analyze(x: FloatArray, frames: Int, sr: Int): Result {
        val lat = latency(x, frames, sr)
        val n = (WIN_S * sr).toInt()
        // noise: the lead silence before any tone (0.1-0.9 s; the latency only moves the tones later)
        val noiseFrom = (0.1 * sr).toInt()
        val noiseN = minOf((0.8 * sr).toInt(), frames - noiseFrom)
        fun noiseDb(hz: Double): Double = db(power(x, noiseFrom, noiseN.coerceAtLeast(16), hz, sr))
        val steps = STEPS.map { st ->
            val from = ((stepStart(st.index) + lat + WIN_START_S) * sr).roundToInt()
            if (from + n > frames || st.hz * 3 >= sr / 2.0) return@map StepResult(st, Double.NaN, Double.NaN, Double.NaN)
            val f = db(power(x, from, n, st.hz, sr))
            val h2 = power(x, from, n, 2 * st.hz, sr)
            val h3 = power(x, from, n, 3 * st.hz, sr)
            StepResult(st, f, db(h2 + h3) - f, f - noiseDb(st.hz))
        }
        fun at(fi: Int, li: Int) = steps[li * FREQS.size + fi]
        val refIndex = FREQS.size - 1
        val ref = at(refIndex, 1)
        val usable = ref.snrDb.isFinite() && ref.snrDb >= MIN_SNR_DB
        val response = DoubleArray(FREQS.size) { fi ->
            val s = at(fi, 1)
            if (usable && s.snrDb >= MIN_SNR_DB) s.fundDb - ref.fundDb else Double.NaN
        }
        val growth = DoubleArray(FREQS.size) { fi -> at(fi, 2).fundDb - at(fi, 1).fundDb }
        val harm = DoubleArray(FREQS.size) { fi -> at(fi, 2).harmonicsDb }
        val clean = BooleanArray(FREQS.size) { fi ->
            val loud = at(fi, 2)
            usable && loud.snrDb >= MIN_SNR_DB && at(fi, 1).snrDb >= MIN_SNR_DB &&
                harm[fi] <= MAX_HARMONICS_DB && growth[fi] >= MIN_GROWTH_DB
        }
        // lowest frequency from which the condition holds for every step above it (frequencies ascend; 1 kHz last)
        fun lowestFrom(ok: (Int) -> Boolean): Double? {
            var from: Double? = null
            for (fi in FREQS.indices.reversed()) { if (ok(fi)) from = FREQS[fi] else break }
            return from
        }
        val knee = if (usable) lowestFrom { fi -> response[fi].isFinite() && response[fi] >= KNEE_DB } else null
        val cleanFrom = if (usable) lowestFrom { fi -> clean[fi] } else null
        return Result(lat, steps, response, growth, harm, clean, knee, cleanFrom, usable)
    }

    /** Median absolute difference of the response between two passes over the frequencies both measured, dB. */
    fun agreementDb(a: Result, b: Result): Double {
        val d = FREQS.indices.mapNotNull { fi ->
            val x = a.responseDb[fi]; val y = b.responseDb[fi]
            if (x.isFinite() && y.isFinite()) abs(x - y) else null
        }.sorted()
        if (d.isEmpty()) return Double.POSITIVE_INFINITY
        return if (d.size % 2 == 1) d[d.size / 2] else 0.5 * (d[d.size / 2 - 1] + d[d.size / 2])
    }

    /** Two passes agree well enough to show a result. */
    const val MAX_AGREEMENT_DB = 1.5

    /** Plain-text report (copy button; compared against a measurement microphone). */
    fun report(r: Result, model: String, agreement: Double?): String = buildString {
        fun f1(v: Double) = if (v.isFinite()) String.format(java.util.Locale.US, "%.1f", v) else "-"
        appendLine("Rootnote bass check · $model · latency ${f1(r.latencyS * 1000)} ms" +
            (agreement?.let { " · pass agreement ${f1(it)} dB" } ?: ""))
        appendLine("knee (-10 dB re 1 kHz): ${r.kneeHz?.let { "${it.roundToInt()} Hz" } ?: "-"} · clean from: ${r.cleanFromHz?.let { "${it.roundToInt()} Hz" } ?: "-"}")
        appendLine("Hz\tresp_dB\tgrowth_dB\tharm_dB@-12\tsnr_dB@-18\tclean")
        for (fi in FREQS.indices) {
            val s = r.steps[1 * FREQS.size + fi]
            appendLine("${FREQS[fi].roundToInt()}\t${f1(r.responseDb[fi])}\t${f1(r.growthDb[fi])}\t${f1(r.harmonicsDb[fi])}\t${f1(s.snrDb)}\t${r.clean[fi]}")
        }
    }
}

package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log2
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * "마이크가 듣는 값" (reference only, never applied): what the phone's own microphone, centimetres from the speaker,
 * hears of the probe sweep ([DevTestKind.PROBE_SWEEP], played with the speaker alone: no layer, flat EQ). Pure
 * Kotlin, host tested (tools/pvb-harness/jvm/SpeakerProbeTest.kt).
 *
 * The sweep's frequency comes from its schedule, refined to the strongest tone within 0.2 octave (the latency is only
 * estimated). The microphone's own level in dB means nothing, so only ratios inside one recording are used:
 * - the fundamental against the loudest part of the sweep (40-500 Hz): more than 10 dB down = "weak" (the same
 *   -10 dB point the published phone measurements use);
 * - the fundamental against its 2nd and 3rd harmonics: harmonics louder = the speaker makes buzz instead of the note
 *   (the "윙·지직만" answer of step 1), whatever the volume or the microphone's gain.
 * The phone microphone hears less than is there below about 100 Hz (its own high-pass), and the body can carry
 * vibration to it; both are why this stays a reference.
 */
class SpeakerProbe(val fs: Double) {
    enum class Verdict { PLAYS, WEAK, BUZZ }

    data class Bin(val hz: Double, val relDb: Double, val ratioDb: Double, val verdict: Verdict)

    /** 1/6-octave bins from 40 Hz up to 500 Hz. */
    val centers: DoubleArray = generateSequence(LO_HZ) { it * 2.0.pow(1.0 / 6) }.takeWhile { it <= HI_HZ * 1.001 }
        .toList().toDoubleArray()
    private val fund = DoubleArray(centers.size) { Double.NaN }
    private val ratio = DoubleArray(centers.size) { Double.NaN }
    private val dist = DoubleArray(centers.size) { Double.POSITIVE_INFINITY }

    var clipped = false; private set
    /** The last window: sweep frequency, fundamental re the loudest bin so far, fundamental re its harmonics. */
    var nowHz = Double.NaN; private set
    var nowRelDb = Double.NaN; private set
    var nowRatioDb = Double.NaN; private set

    private val loudest: Double get() = fund.filter { !it.isNaN() }.maxOrNull() ?: Double.NaN

    /**
     * One analysis window of the recording whose middle is [tMid] s into the sweep (latency already taken off).
     * Outside the sweep (its first and last 0.1 s, the pause) nothing happens.
     */
    fun window(x: FloatArray, tMid: Double) {
        if (x.any { abs(it) >= CLIP }) clipped = true
        val expected = sweepHz(tMid) ?: return
        // the sweep's real place: the strongest tone within 0.2 octave of where it should be (a latency off by
        // half a second is 0.2 octave); its harmonics are an octave and more away, so a weak note is not mistaken
        var f = expected
        var f1 = -400.0
        for (k in -8..8) {
            val c = expected * 2.0.pow(k / 40.0)
            val l = tone(x, c)
            if (l > f1) { f1 = l; f = c }
        }
        val h = maxOf(tone(x, 2 * f), tone(x, 3 * f))
        val r = f1 - h
        val b = centers.indices.minByOrNull { abs(log2(centers[it] / f)) }!!
        val d = abs(log2(centers[b] / f))
        // per bin: the window nearest its centre (a later sweep at about the same place replaces it: live view)
        if (d < dist[b] + 0.01) { dist[b] = minOf(d, dist[b]); fund[b] = f1; ratio[b] = r }
        nowHz = f
        nowRelDb = f1 - loudest
        nowRatioDb = r
    }

    /** A whole recording that starts when the sweep was asked for; [latencyS]: when it really started. */
    fun analyze(x: FloatArray, latencyS: Double): SpeakerProbe {
        var start = 0
        while (start + WINDOW <= x.size) {
            window(x.copyOfRange(start, start + WINDOW), (start + WINDOW / 2) / fs - latencyS)
            start += HOP
        }
        return this
    }

    fun bins(): List<Bin> {
        val top = loudest
        return centers.indices.filter { !fund[it].isNaN() }.map { i ->
            val rel = fund[i] - top
            Bin(centers[i], rel, ratio[i], verdict(rel, ratio[i]))
        }
    }

    /**
     * Lowest bin of the unbroken run of "plays" bins that reaches up to [TOP_HZ]; null when the bins up there are
     * not measured or not a clear tone (nothing to stand on: silence, noise), or the recording clipped.
     */
    fun floorHz(): Double? {
        if (clipped) return null
        val bins = bins()
        val topBins = bins.filter { it.hz >= TOP_HZ / 2.0.pow(1.0 / 12) }
        // up top the tone must stand clearly over its harmonics (noise alone gives about 0 dB there)
        if (bins.size < 8 || topBins.isEmpty() || topBins.none { it.verdict == Verdict.PLAYS && it.ratioDb >= CLEAR_DB }) return null
        var floor: Double? = null
        for (b in bins.sortedByDescending { it.hz }) {
            if (b.hz > TOP_HZ * 1.01) continue
            if (b.verdict != Verdict.PLAYS) break
            floor = b.hz
        }
        return floor
    }

    private var hannTable = DoubleArray(0)
    private fun hann(n: Int): DoubleArray {
        if (hannTable.size != n) hannTable = DoubleArray(n) { 0.5 - 0.5 * cos(2 * PI * it / n) }
        return hannTable
    }

    // Goertzel on a Hann-windowed block: amplitude of [f] in dBFS (a full-scale sine is 0 dB).
    private fun tone(x: FloatArray, f: Double): Double {
        if (f >= fs / 2) return -200.0
        val n = x.size
        val w = 2 * PI * f / fs
        val coeff = 2 * cos(w)
        val win = hann(n)
        var s1 = 0.0; var s2 = 0.0; var wsum = 0.0
        for (i in 0 until n) {
            val h = win[i]
            wsum += h
            val s = x[i] * h + coeff * s1 - s2
            s2 = s1; s1 = s
        }
        val power = s1 * s1 + s2 * s2 - coeff * s1 * s2
        val amp = 2 * sqrt(maxOf(power, 0.0)) / wsum
        return PvbMeasureMath.db(amp * amp)
    }

    companion object {
        const val LO_HZ = DevTestSignal.PROBE_LO_HZ
        const val HI_HZ = DevTestSignal.PROBE_HI_HZ
        const val SWEEP_S = DevTestSignal.PROBE_SWEEP_S
        const val PERIOD_S = DevTestSignal.PROBE_PERIOD_S
        /** The "plays" run has to reach this high (phone speakers are near their midband here). */
        const val TOP_HZ = 400.0
        const val WEAK_DB = -10.0
        /** The top of the sweep must be this far over its harmonics to count as a recording of the sweep at all. */
        const val CLEAR_DB = 10.0
        const val WINDOW = 4096
        const val HOP = 1024
        const val CLIP = 0.98f

        fun verdict(relDb: Double, ratioDb: Double): Verdict = when {
            ratioDb < 0 -> Verdict.BUZZ
            relDb < WEAK_DB -> Verdict.WEAK
            else -> Verdict.PLAYS
        }

        /** Frequency of the probe sweep [t] s after it started (null in its first and last 0.1 s and the pause). */
        fun sweepHz(t: Double): Double? {
            if (t < 0) return null
            val x = t % PERIOD_S
            if (x < 0.1 || x > SWEEP_S - 0.1) return null
            return LO_HZ * exp(ln(HI_HZ / LO_HZ) * x / SWEEP_S)
        }

        /** "약 150 Hz" style rounding: to 5 Hz. */
        fun roundHz(hz: Double): Int = (hz / 5).roundToInt() * 5
    }
}

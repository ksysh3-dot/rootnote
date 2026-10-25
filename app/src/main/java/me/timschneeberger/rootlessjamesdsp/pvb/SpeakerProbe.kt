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

/**
 * Harmonic distortion of the probe sweep by exponential-sweep deconvolution (the method of A. Farina, AES 2000):
 * the recording is convolved with the sweep's inverse filter (the sweep reversed in time, amplitude falling 6 dB per
 * octave), which turns it into the linear impulse response plus one impulse response per harmonic, each [harmonicLagS]
 * earlier. Cut out and transformed, the n-th one at frequency n*f over the linear one at f is the n-th harmonic's
 * level relative to the fundamental when the sweep was at f (for an exponential sweep both pass that frequency at the
 * same sweep rate, so no further scaling). Unlike [SpeakerProbe] (band levels, live), this needs the whole sweep.
 *
 * The inverse filter only holds the sweep's own band, so the n-th harmonic is found only where n*f stays under the
 * sweep's top (500 Hz): the 2nd up to 250 Hz, the 3rd up to 167 Hz, the 4th up to 125 Hz (NaN above); THD sums the
 * orders found. That is the speaker's bass, where the distortion is.
 *
 * Everything runs at fs / [DECIM] (6 kHz from 48 kHz): the sweep stops at 500 Hz, so harmonics up to the 4th (2 kHz)
 * stay under its Nyquist; FFTs of 2^17 points instead of 2^20.
 */
object SweepDistortion {
    const val DECIM = 8
    const val ORDERS = 4
    /** Each impulse response is cut from 20 ms before its peak to [WIN_S] after (the next one is 0.79 s away). */
    const val PRE_S = 0.02
    const val WIN_S = 0.35

    data class Point(val hz: Double, val linDb: Double, val h2Db: Double, val h3Db: Double, val thdDb: Double)

    /** The frequencies shown and logged: the speaker's bass, where [analyze] finds the 2nd and 3rd harmonics. */
    val SHOWN_HZ = doubleArrayOf(63.0, 80.0, 100.0, 125.0, 160.0, 200.0)

    /** THD (dB re the fundamental) at [hz] from [pts]: the nearest point within 1/12 octave, else null. */
    fun thdAt(pts: List<Point>, hz: Double): Double? = pts.minByOrNull { kotlin.math.abs(ln(it.hz / hz)) }
        ?.takeIf { kotlin.math.abs(log2(it.hz / hz)) <= 1.0 / 12 + 1e-9 && it.thdDb.isFinite() }?.thdDb

    /** "63 Hz −12 · 80 Hz −13 · ..." for the screens. */
    fun line(pts: List<Point>): String = SHOWN_HZ.toList().mapNotNull { f ->
        thdAt(pts, f)?.let { String.format(java.util.Locale.ROOT, "%d Hz %s%.0f", f.toInt(), if (it < 0) "\u2212" else "+", kotlin.math.abs(it)) }
    }.joinToString(" · ")

    /** How much earlier than the linear response the n-th harmonic's impulse response appears, s. */
    fun harmonicLagS(n: Int): Double =
        DevTestSignal.PROBE_SWEEP_S * ln(n.toDouble()) / ln(DevTestSignal.PROBE_HI_HZ / DevTestSignal.PROBE_LO_HZ)

    /** Windowed-sinc low-pass (Blackman) at 0.4 of the decimated rate, then every [DECIM]-th sample. */
    fun decimate(x: FloatArray): DoubleArray {
        val taps = 127
        val fc = 0.4 / DECIM
        val h = DoubleArray(taps) { i ->
            val m = i - (taps - 1) / 2.0
            val sinc = if (m == 0.0) 2 * fc else kotlin.math.sin(2 * PI * fc * m) / (PI * m)
            sinc * (0.42 - 0.5 * cos(2 * PI * i / (taps - 1)) + 0.08 * cos(4 * PI * i / (taps - 1)))
        }
        val g = h.sum()
        val out = DoubleArray(x.size / DECIM)
        for (o in out.indices) {
            val c = o * DECIM
            var s = 0.0
            for (k in 0 until taps) {
                val j = c + k - (taps - 1) / 2
                if (j in x.indices) s += h[k] * x[j]
            }
            out[o] = s / g
        }
        return out
    }

    /** The probe sweep (unit amplitude, the same raised-cosine edges as DevTestSound) at [fs]. */
    fun sweep(fs: Double): DoubleArray {
        val T = DevTestSignal.PROBE_SWEEP_S
        val k = ln(DevTestSignal.PROBE_HI_HZ / DevTestSignal.PROBE_LO_HZ)
        val n = (T * fs).toInt()
        return DoubleArray(n) { i ->
            val t = i / fs
            val fade = 0.02
            val env = when {
                t < fade -> 0.5 - 0.5 * cos(PI * t / fade)
                t > T - fade -> 0.5 - 0.5 * cos(PI * (T - t) / fade)
                else -> 1.0
            }
            env * kotlin.math.sin(2 * PI * DevTestSignal.PROBE_LO_HZ * T / k * (exp(k * t / T) - 1))
        }
    }

    private fun nextPow2(n: Int): Int { var p = 1; while (p < n) p = p shl 1; return p }

    /**
     * [x]: the microphone recording at [fs] that holds the whole sweep, which starts about [startS] into it.
     * Null when the linear response can't be found (no sweep in the recording).
     */
    fun analyze(x: FloatArray, fs: Double, startS: Double): List<Point>? {
        val y = decimate(x)
        val fsd = fs / DECIM
        val s = sweep(fsd)
        val ns = s.size
        val k = ln(DevTestSignal.PROBE_HI_HZ / DevTestSignal.PROBE_LO_HZ)
        // inverse filter: reversed, -6 dB per octave of the sweep's frequency at that point
        val inv = DoubleArray(ns) { i -> s[ns - 1 - i] * exp(-k * i / ns) }
        val n = nextPow2(y.size + ns)
        val yr = DoubleArray(n); val yi = DoubleArray(n)
        val ir = DoubleArray(n); val ii = DoubleArray(n)
        for (i in y.indices) yr[i] = y[i]
        for (i in inv.indices) ir[i] = inv[i]
        PvbMeasureMath.fft(yr, yi); PvbMeasureMath.fft(ir, ii)
        // normalise with the sweep through its own inverse: the linear response of a wire is then 1
        val sr = DoubleArray(n); val si = DoubleArray(n)
        for (i in s.indices) sr[i] = s[i]
        PvbMeasureMath.fft(sr, si)
        var refPeak = 0.0
        run {
            val pr = DoubleArray(n); val pi = DoubleArray(n)
            for (i in 0 until n) { pr[i] = sr[i] * ir[i] - si[i] * ii[i]; pi[i] = -(sr[i] * ii[i] + si[i] * ir[i]) }
            PvbMeasureMath.fft(pr, pi)     // conjugate trick: ifft(z) = conj(fft(conj(z))) / n
            for (i in 0 until n) refPeak = maxOf(refPeak, abs(pr[i] / n))
        }
        val hr = DoubleArray(n); val hi = DoubleArray(n)
        for (i in 0 until n) { hr[i] = yr[i] * ir[i] - yi[i] * ii[i]; hi[i] = -(yr[i] * ii[i] + yi[i] * ir[i]) }
        PvbMeasureMath.fft(hr, hi)
        val h = DoubleArray(n) { hr[it] / n / refPeak }
        // the linear peak: about startS + the sweep length in (the inverse filter's length); search +-1 s
        val expect = ((startS * fsd) + ns - 1).toInt()
        val lo = (expect - fsd).toInt().coerceAtLeast(0)
        val hiI = (expect + fsd).toInt().coerceAtMost(n - 1)
        var peak = lo
        for (i in lo..hiI) if (abs(h[i]) > abs(h[peak])) peak = i
        if (abs(h[peak]) < 1e-6) return null
        val pre = (PRE_S * fsd).toInt()
        val win = (WIN_S * fsd).toInt()
        val nf = nextPow2(win + pre) * 4
        fun spectrum(center: Int): Pair<DoubleArray, DoubleArray> {
            val re = DoubleArray(nf); val im = DoubleArray(nf)
            for (j in 0 until pre + win) {
                val idx = center - pre + j
                if (idx !in 0 until n) continue
                // half-Hann fade-in over the pre part, flat, half-Hann fade-out over the last 30 %
                val w = when {
                    j < pre -> 0.5 - 0.5 * cos(PI * j / pre)
                    j > pre + win * 0.7 -> 0.5 + 0.5 * cos(PI * (j - pre - win * 0.7) / (win * 0.3))
                    else -> 1.0
                }
                re[j] = h[idx] * w
            }
            PvbMeasureMath.fft(re, im)
            return re to im
        }
        fun magDb(sp: Pair<DoubleArray, DoubleArray>, f: Double): Double {
            val b = (f * nf / fsd).roundToInt().coerceIn(1, nf / 2)
            // power over +-1/12 octave around f
            val b0 = (f / 2.0.pow(1.0 / 12) * nf / fsd).roundToInt().coerceIn(1, nf / 2)
            val b1 = (f * 2.0.pow(1.0 / 12) * nf / fsd).roundToInt().coerceIn(b, nf / 2)
            var p = 0.0
            for (q in b0..b1) p += sp.first[q] * sp.first[q] + sp.second[q] * sp.second[q]
            return 10 * kotlin.math.log10(p / (b1 - b0 + 1) + 1e-30)
        }
        val lin = spectrum(peak)
        val harm = (2..ORDERS).associateWith { o -> spectrum(peak - (harmonicLagS(o) * fsd).roundToInt()) }
        val centers = generateSequence(DevTestSignal.PROBE_LO_HZ * 1.12) { it * 2.0.pow(1.0 / 6) }
            .takeWhile { it <= DevTestSignal.PROBE_HI_HZ * 0.9 }.toList()
        return centers.map { f ->
            val l = magDb(lin, f)
            val d = (2..ORDERS).associateWith { o -> if (o * f <= DevTestSignal.PROBE_HI_HZ * 0.95) magDb(harm.getValue(o), o * f) - l else Double.NaN }
            val thd = 10 * kotlin.math.log10(d.values.filter { it.isFinite() }.sumOf { 10.0.pow(it / 10) } + 1e-30)
            Point(f, l, d.getValue(2), d.getValue(3), thd)
        }
    }
}

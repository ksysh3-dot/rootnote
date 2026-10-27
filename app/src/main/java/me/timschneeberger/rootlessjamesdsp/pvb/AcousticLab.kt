package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.*

/** Deterministic acoustic experiment, not an audibility score or a microphone calibration. */
object AcousticLab {
    const val VERSION = 1
    const val RATE = 48000
    const val SECONDS = 3.2
    const val MARKER_S = 0.25
    const val MARKER_LENGTH_S = 0.04
    const val EVENT_S = 1.5
    const val IMPACT_END_S = 0.16
    const val BIN_S = 0.01
    val MODELS = listOf(6, 11, 12, 13)
    val WINDOWS = listOf("before" to (-0.45 to -0.08), "attack" to (0.0 to 0.08),
        "early" to (0.08 to 0.30), "late" to (0.30 to 0.80))

    data class Trial(val model: Int, val inputDb: Int, val repeat: Int, val impact: Boolean)

    /** Counterbalance the pair order and randomize complete pairs, preserving the pairing in the report. */
    fun plan(seed: Long): List<Trial> {
        val rng = java.util.Random(seed)
        val pairs = MODELS.flatMap { m -> listOf(-12, 0).flatMap { db ->
            (0..2).map { r -> listOf(Trial(m, db, r, false), Trial(m, db, r, true)).let {
                if (rng.nextBoolean()) it.reversed() else it
            } }
        } }.shuffled(rng)
        return pairs.flatten()
    }

    /** Same sustained 100 Hz bed, with/without a short kick/noise impact; no music/file metadata. */
    fun signal(trial: Trial, fs: Int = RATE): FloatArray {
        val out = FloatArray((SECONDS * fs).roundToInt() * 2)
        val gain = 10.0.pow(trial.inputDb / 20.0)
        val eventFrame = (EVENT_S * fs).roundToInt()
        val impactEndFrame = eventFrame + (IMPACT_END_S * fs).roundToInt()
        var rng = 0x2545F4914F6CDD1DL
        for (n in 0 until out.size / 2) {
            val t = n.toDouble() / fs
            var x = 0.0
            if (t >= MARKER_S && t < MARKER_S + MARKER_LENGTH_S) {
                val u = t - MARKER_S
                val fade = minOf(1.0, u / 0.003, (MARKER_LENGTH_S - u) / 0.003)
                x += 0.12 * fade * sin(2 * PI * (1700 * u + 900 * u * u / MARKER_LENGTH_S))
            }
            if (t >= 0.65) x += gain * 0.04 * minOf(1.0, (t - 0.65) / 0.05) * sin(2 * PI * 100 * t)
            val u = (n - eventFrame).toDouble() / fs
            if (trial.impact && n in eventFrame until impactEndFrame) {
                rng = rng xor (rng shl 13); rng = rng xor (rng ushr 7); rng = rng xor (rng shl 17)
                val white = (rng ushr 11).toDouble() / (1L shl 53) * 2 - 1
                val fade = minOf(1.0, u / 0.001, (IMPACT_END_S - u) / 0.008)
                x += gain * fade * (0.52 * exp(-u / 0.045) * sin(2 * PI * (85 * u - 90 * u * u)) +
                    0.20 * exp(-u / 0.030) * white)
            }
            out[2 * n] = x.toFloat(); out[2 * n + 1] = x.toFloat()
        }
        return out
    }

    data class Alignment(val frame: Int, val correlation: Double)

    /** Match the actual rendered high-frequency marker, including the engine's delay, to the acoustic recording. */
    fun align(recorded: FloatArray, marker: FloatArray, fs: Int): Alignment {
        require(marker.isNotEmpty() && recorded.size > marker.size)
        val step = 4
        var ee = 0.0
        for (j in marker.indices step step) ee += marker[j] * marker[j].toDouble()
        if (ee < 1e-16) return Alignment(0, 0.0)
        var best = 0.0; var at = 0
        val end = minOf(recorded.size - marker.size, (1.4 * fs).toInt())
        for (p in 0..end step step) {
            var xy = 0.0; var yy = 0.0
            for (j in marker.indices step step) {
                val y = recorded[p + j].toDouble(); xy += marker[j] * y; yy += y * y
            }
            val c = abs(xy) / sqrt(ee * yy.coerceAtLeast(1e-30))
            if (c > best) { best = c; at = p }
        }
        // Coarse search alone can leave a multi-sample error at a high-frequency marker.
        var exactBest = 0.0; var exactAt = at
        for (p in maxOf(0, at - step)..minOf(end, at + step)) {
            var xy = 0.0; var yy = 0.0; var xx = 0.0
            for (j in marker.indices) {
                val x = marker[j].toDouble(); val y = recorded[p + j].toDouble()
                xy += x * y; xx += x * x; yy += y * y
            }
            val c = abs(xy) / sqrt(xx * yy.coerceAtLeast(1e-30))
            if (c > exactBest) { exactBest = c; exactAt = p }
        }
        return Alignment(exactAt, exactBest)
    }

    /** Causal 150-2000 Hz band, identical for ambient, bed and impact. No centered window/pre-ringing. */
    fun band(x: FloatArray, fs: Int): FloatArray {
        var data = x.copyOf()
        for ((hz, hp) in listOf(150.0 to true, 2000.0 to false)) {
            val w = 2 * PI * hz / fs; val cw = cos(w); val a = sin(w) / sqrt(2.0); val a0 = 1 + a
            val b0 = (if (hp) 1 + cw else 1 - cw) / 2 / a0
            val b1 = (if (hp) -(1 + cw) else 1 - cw) / a0
            val a1 = -2 * cw / a0; val a2 = (1 - a) / a0
            var z1 = 0.0; var z2 = 0.0
            data = FloatArray(data.size) { i ->
                val v = data[i].toDouble(); val y = b0 * v + z1
                z1 = b1 * v - a1 * y + z2; z2 = b0 * v - a2 * y
                y.toFloat()
            }
        }
        return data
    }

    fun power(x: FloatArray, from: Int, until: Int): Double {
        if (from < 0 || until > x.size || until <= from) return Double.NaN
        var sum = 0.0
        for (i in from until until) sum += x[i] * x[i].toDouble()
        return sum / (until - from)
    }

    data class Measurement(val markerCorrelation: Double, val markerFrame: Int, val eventFrame: Int,
        val ambientPower: Double, val windowPowers: Map<String, Double>, val binPowers: List<Double>,
        val recoveryMs: Double?, val clippedSamples: Int, val complete: Boolean)

    fun measure(recorded: FloatArray, marker: FloatArray, fs: Int): Measurement {
        val lag = align(recorded, marker, fs)
        val event = lag.frame + ((EVENT_S - MARKER_S) * fs).roundToInt()
        val y = band(recorded, fs)
        val ambient = power(y, (0.03 * fs).toInt(), (0.15 * fs).toInt())
        val windows = WINDOWS.associate { (name, w) -> name to power(y,
            event + (w.first * fs).roundToInt(), event + (w.second * fs).roundToInt()) }
        val bins = (0 until 140).map { i ->
            val start = event + ((i * BIN_S - 0.50) * fs).roundToInt()
            power(y, start, start + (BIN_S * fs).roundToInt())
        }
        val before = windows.getValue("before")
        val baseline = before - ambient
        var recovery: Double? = null
        if (baseline > ambient * 9 && bins.all { it.isFinite() }) {
            for (i in (50 + ceil(IMPACT_END_S / BIN_S).toInt())..(bins.size - 5)) {
                if ((i until i + 5).all { j ->
                    val p = bins[j] - ambient
                    p > 0 && abs(10 * log10(p / baseline)) <= 1.0
                }) { recovery = (i - 50) * BIN_S * 1000; break }
            }
        }
        return Measurement(lag.correlation, lag.frame, event, ambient, windows, bins, recovery,
            recorded.count { abs(it) >= 0.999f }, bins.all { it.isFinite() } && windows.values.all { it.isFinite() })
    }
}

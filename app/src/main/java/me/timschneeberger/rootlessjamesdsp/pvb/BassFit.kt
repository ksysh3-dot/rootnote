package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt

/*
 * "저음 맞추기" (bass fit, docs/BASS_FIT_PLAN.md): the pure logic of the in-app listening tests. No Android types;
 * host JVM tested in tools/pvb-harness/jvm/BassFitTest.kt. The screen plays what a step asks for and feeds the answers
 * back; every random choice comes from a seed. The screen draws a new seed for every run, so the order of the
 * questions and the A/B/X sides differ each time, and records it, so a run can be replayed exactly.
 *
 *  - NoiseGate: is the room quiet enough (strict), and was a trial disturbed. FitLatency: when a sound really plays.
 *  - AbxRun: one ABX decision (up to 8 trials, 7/8 or 6/6 = distinguishable).
 *  - FloorStaircase: step 1, the speaker floor by a two-interval forced choice with catch trials (2-down/1-up).
 *  - StrengthBracket: step 2b, preferred virtual-bass strength by blind A/B bracketing (ties take the lower).
 *  - BreakupStaircase: step 3, the level where harmonics start to break up (yes/no with catch trials).
 *  - BradleyTerry / ShapeGrid: step 4 (optional), harmonic shape from blind pairwise preferences.
 *  - BassFitMapping: what a found floor sets.
 */

/** Seeded generator (SplitMix64), the same on every device and JVM. */
class FitRng(seed: Long) {
    private var state = seed
    fun next(): Long {
        state += -0x61c8864680b583ebL
        var z = state
        z = (z xor (z ushr 30)) * -0x40a7b892e31b1a47L
        z = (z xor (z ushr 27)) * -0x6b2fb644ecceee15L
        return z xor (z ushr 31)
    }
    fun bit(): Boolean = next() < 0
    fun below(n: Int): Int = ((next() ushr 1) % n).toInt()
}

/** Catch trials every staircase asks at least (a false-alarm rate needs more than one). */
const val MIN_CATCH = 2

object FitStats {
    /** P(X >= k) for X ~ Binomial(n, 1/2): one-sided chance of k or more right answers by guessing. */
    fun guessP(k: Int, n: Int): Double {
        if (k <= 0) return 1.0
        if (k > n) return 0.0
        var c = 1.0
        var tail = 0.0
        for (i in 0..n) {
            if (i > 0) c = c * (n - i + 1) / i
            if (i >= k) tail += c
        }
        return tail / 2.0.pow(n)
    }
}

// ------------------------------------------------------------------------------------------------ noise gate

/**
 * Strict room check with the phone microphone. Everything is a ratio between two recordings through the same
 * microphone, so the microphone needs no calibration.
 */
object NoiseGate {
    /**
     * Was 35 dB; an ordinary room with the door closed measured 18. The floor test now sets its bursts from the
     * listener's own threshold in that room (RefLevelStaircase), so moderate noise shifts the reference and the bursts
     * alike; what is left to catch is a room so loud the bursts drown.
     */
    const val MIN_SNR_DB = 15.0
    const val MAX_JUMP_DB = 6.0
    /** A silent trial interval louder than the room by this much discards the trial. */
    const val DISTURB_DB = 6.0
    val TEST_BANDS = doubleArrayOf(63.0, 80.0, 100.0, 125.0, 160.0, 200.0, 250.0, 315.0, 400.0, 500.0)
    val SPEECH_BANDS = doubleArrayOf(630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0, 2500.0, 3150.0, 4000.0)

    enum class Reason { SNR_LOW, ROOM_UNSTEADY, NO_MIC }

    data class Verdict(
        val pass: Boolean,
        /** Lowest margin over the test bands ([judge]), dB, and the band where it occurred. */
        val worstSnrDb: Double,
        val worstBandHz: Double,
        /** Room level jumps: max - median of 100 ms frame levels, dB. */
        val jumpDb: Double,
        val reasons: List<Reason>,
    )

    /** Third-octave band power (dB, mean square) of x: Welch average of 4096-point Hann frames, 50 % overlap. */
    fun bandLevels(x: FloatArray, fs: Double, centers: DoubleArray): DoubleArray {
        val n = 4096
        val win = DoubleArray(n) { 0.5 - 0.5 * kotlin.math.cos(2 * Math.PI * it / n) }
        val wss = win.sumOf { it * it }
        val acc = DoubleArray(n / 2 + 1)
        var frames = 0
        var start = 0
        val re = DoubleArray(n); val im = DoubleArray(n)
        while (start + n <= x.size) {
            for (i in 0 until n) { re[i] = x[start + i] * win[i]; im[i] = 0.0 }
            PvbMeasureMath.fft(re, im)
            for (k in 0..n / 2) acc[k] += re[k] * re[k] + im[k] * im[k]
            frames++
            start += n / 2
        }
        if (frames == 0) return DoubleArray(centers.size) { -200.0 }
        val g = 2.0.pow(1.0 / 6.0)
        return DoubleArray(centers.size) { b ->
            var s = 0.0
            for (k in 1 until n / 2) {
                val f = k * fs / n
                if (f >= centers[b] / g && f < centers[b] * g) s += 2 * acc[k]
            }
            PvbMeasureMath.db(s / frames / wss / n)
        }
    }

    /** max - median of the 100 ms frame levels of x, dB. */
    fun jumpDb(x: FloatArray, fs: Double): Double {
        val len = (0.1 * fs).roundToInt().coerceAtLeast(1)
        val levels = ArrayList<Double>()
        var i = 0
        while (i + len <= x.size) {
            var s = 0.0
            for (j in i until i + len) s += x[j].toDouble() * x[j]
            levels += PvbMeasureMath.db(s / len)
            i += len
        }
        if (levels.isEmpty()) return 0.0
        val sorted = levels.sorted()
        return sorted.last() - sorted[sorted.size / 2]
    }

    /** A band whose reference is this far below the reference's strongest band is one the speaker barely plays. */
    const val PLAYS_DB = 20.0

    /**
     * [room]: the room with nothing playing (3 s); [withSignal]: the test reference playing (2 s), same microphone.
     * The signal power is (with - room) per band. In the bands the speaker plays (within [PLAYS_DB] of its strongest
     * test band) the margin is the signal-to-noise ratio. A phone speaker barely plays 63-100 Hz, so there the ratio
     * would be low in any room; those bands are judged by the room against the speaker's strongest band instead (a
     * rumble there still masks the tones above it). Pass: every margin >= [MIN_SNR_DB] and the room steady.
     */
    fun judge(room: FloatArray?, withSignal: FloatArray?, fs: Double): Verdict {
        if (room == null || withSignal == null) return Verdict(false, Double.NaN, Double.NaN, Double.NaN, listOf(Reason.NO_MIC))
        val n = bandLevels(room, fs, TEST_BANDS)
        val s = bandLevels(withSignal, fs, TEST_BANDS)
        val sigDb = DoubleArray(TEST_BANDS.size) { b ->
            val sig = 10.0.pow(s[b] / 10) - 10.0.pow(n[b] / 10)
            if (sig <= 0) -200.0 else 10 * log10(sig)
        }
        val strongest = sigDb.maxOrNull() ?: -200.0
        var worst = Double.POSITIVE_INFINITY
        var worstHz = TEST_BANDS[0]
        for (b in TEST_BANDS.indices) {
            val plays = sigDb[b] >= strongest - PLAYS_DB
            val margin = if (plays) sigDb[b] - n[b] else strongest - n[b]
            if (margin < worst) { worst = margin; worstHz = TEST_BANDS[b] }
        }
        val jump = jumpDb(room, fs)
        val reasons = ArrayList<Reason>()
        if (worst < MIN_SNR_DB) reasons += Reason.SNR_LOW
        if (jump > MAX_JUMP_DB) reasons += Reason.ROOM_UNSTEADY
        return Verdict(reasons.isEmpty(), worst, worstHz, jump, reasons)
    }

    /** The silent interval of a trial ([silent]) is louder than the room ([roomBandsDb], from [bandLevels]) by more
     *  than [DISTURB_DB] in any test band: discard and repeat the trial. */
    fun disturbed(silent: FloatArray, fs: Double, roomBandsDb: DoubleArray): Boolean {
        val l = bandLevels(silent, fs, TEST_BANDS)
        return l.indices.any { l[it] > roomBandsDb[it] + DISTURB_DB }
    }
}

/**
 * How late a requested sound reaches the microphone (the capture, the engine and the output buffers in between): the
 * screen asks for the reference at frame [from] of its recording and looks for where it starts. Used to find the
 * silent interval of each trial in the recording, and to light the interval marks when the sound really plays.
 */
object FitLatency {
    const val TYPICAL_S = 0.15
    const val MAX_S = 1.0

    /**
     * First 10 ms frame after [from] louder than halfway (in dB) between the quiet half second before [from] and the
     * reference 1.0-1.6 s after it. Null when the reference rose by less than 15 dB or [x] is too short.
     */
    fun onsetFrame(x: FloatArray, fs: Double, from: Int): Int? {
        val len = (0.01 * fs).roundToInt().coerceAtLeast(1)
        fun lvl(i: Int): Double {
            var s = 0.0
            for (j in i until i + len) s += x[j].toDouble() * x[j]
            return PvbMeasureMath.db(s / len)
        }
        fun median(a: Int, b: Int): Double? {
            val l = ArrayList<Double>()
            var i = a
            while (i + len <= b) { l += lvl(i); i += len }
            return if (l.isEmpty()) null else l.sorted()[l.size / 2]
        }
        val loudEnd = from + (1.6 * fs).toInt()
        if (from < 0 || loudEnd > x.size) return null
        val quiet = median(max(0, from - (0.5 * fs).toInt()), from) ?: return null
        val loud = median(from + (1.0 * fs).toInt(), loudEnd) ?: return null
        if (loud - quiet < 15.0) return null
        val threshold = (quiet + loud) / 2
        var i = from
        while (i + len <= from + (MAX_S * fs).toInt()) {
            if (lvl(i) > threshold) return i
            i += len
        }
        return null
    }
}

// ------------------------------------------------------------------------------------------------ ABX

/**
 * One ABX decision. Each trial hides A or B behind X (seeded). Distinguishable at [passAt] of [maxTrials] right
 * (7/8: p = 0.035) or [earlyPass] right in a row from the start (6/6: p = 0.016); stops as soon as the decision can't
 * change any more.
 */
class AbxRun(private val seed: Long, val maxTrials: Int = 8, val passAt: Int = 7, val earlyPass: Int = 6) {
    enum class State { RUNNING, DISTINGUISHED, NOT_DISTINGUISHED }

    var trials = 0; private set
    var correct = 0; private set
    var state = State.RUNNING; private set

    /** Whether X is A in the current trial. */
    fun xIsA(trial: Int = trials): Boolean = FitRng(seed xor (trial.toLong() * 0x9E3779B97F4A7C15uL.toLong())).bit()

    /** [saidXIsA] null: "잘 모르겠어요", counted as a wrong answer (so it can only make passing harder; two of
     *  them end an 8-trial run as not distinguished). */
    fun answer(saidXIsA: Boolean?): State {
        check(state == State.RUNNING) { "decided" }
        if (saidXIsA != null && saidXIsA == xIsA()) correct++
        trials++
        state = when {
            correct >= passAt -> State.DISTINGUISHED
            trials == earlyPass && correct == earlyPass -> State.DISTINGUISHED
            correct + (maxTrials - trials) < passAt -> State.NOT_DISTINGUISHED
            trials >= maxTrials -> State.NOT_DISTINGUISHED
            else -> State.RUNNING
        }
        return state
    }

    /** Chance of this many right answers or more by guessing. */
    fun p(): Double = FitStats.guessP(correct, trials)
}

// ------------------------------------------------------------------------------------------------ step 1: floor

/**
 * The speaker floor by a two-interval forced choice: a tone burst plays in one of two intervals ("어느 쪽에서 소리가
 * 났나요?"). Frequencies from [startHz] down in 1/6-octave steps. 1-down/1-up until the first miss (fast descent),
 * then 2-down/1-up (converges where 70.7 % are heard, Levitt 1971). A buzz-only answer counts as not heard. About one
 * trial in five is a catch trial (both intervals silent; the right answer is "neither"), at least [MIN_CATCH].
 */
class FloorStaircase(
    private val seed: Long,
    /** The listener's threshold at the reference, dB re the full tone ([RefLevelStaircase.thresholdDb]). */
    val refDb: Double = -SL_DB,
    val startHz: Double = 300.0,
    val minHz: Double = 70.0,
    val maxTrials: Int = 30,
    val stopReversals: Int = 6,
    /** Optional room-noise correction of the burst level at a frequency, dB ([NoiseMasking.correctionDb]). */
    val noiseDb: ((Double) -> Double)? = null,
) {
    companion object {
        /** How far over the threshold the bursts play (the -10 dB point the published measurements use). */
        const val SL_DB = 10.0
    }

    enum class Choice { FIRST, SECOND, NEITHER, BUZZ_ONLY }
    sealed class Trial {
        /** [levelDb]: the burst's level re the test tone's full level (DevTestSignal.FIT_TONE_AMP), at most 0. */
        data class Tone(val hz: Double, val inFirst: Boolean, val levelDb: Double = 0.0) : Trial()
        object Catch : Trial()
    }

    /**
     * Level of the burst at [hz]: [SL_DB] over the listener's own threshold at the reference ([refDb], from
     * [RefLevelStaircase]), plus how much less sensitive hearing is at [hz] than at the reference (ISO 226). So a
     * burst stops being heard where the speaker plays [SL_DB] less than at the reference: the floor is the speaker's
     * -10 dB point, not the lowest note that is audible at all. Capped at 0 (the tone's full level).
     */
    fun levelDb(hz: Double): Double = wantedDb(hz).coerceAtMost(0.0)

    /** [levelDb] before the cap (plus the optional noise correction, [noiseDb]). */
    private fun wantedDb(hz: Double): Double =
        refDb + SL_DB + HearingThreshold.db(hz) - HearingThreshold.db(RefLevelStaircase.REF_HZ) + (noiseDb?.invoke(hz) ?: 0.0)

    /** Missed trials whose wanted level was above the cap (the volume was too low for them). */
    var cappedTrials = 0; private set
    private val cappedMissHz = ArrayList<Double>()

    /**
     * A capped miss at or above the found floor: that note might have been heard at the right level, so the floor may
     * be too high (misses well below the floor are expected and do not count).
     */
    fun cappedNearFloor(): Boolean {
        val f = floorHz() ?: return false
        return cappedMissHz.any { it >= f / 2.0.pow(1.0 / 12.0) }
    }

    val freqs: DoubleArray = generateSequence(startHz) { it / 2.0.pow(1.0 / 6.0) }.takeWhile { it >= minHz * 0.999 }
        .toList().toDoubleArray()
    private val rng = FitRng(seed)
    private var idx = 0
    private var streak = 0
    private var missedOnce = false
    private var lastDir = 0
    private val reversals = ArrayList<Double>()
    var toneTrials = 0; private set
    var catchTrials = 0; private set
    var falseAlarms = 0; private set
    var current: Trial = nextTrial(); private set

    /** Enough reversals and at least [MIN_CATCH] catch trials, or [maxTrials] asked. */
    val done: Boolean get() = (reversals.size >= stopReversals && catchTrials >= MIN_CATCH) || toneTrials + catchTrials >= maxTrials

    private fun nextTrial(): Trial = when {
        reversals.size >= stopReversals -> Trial.Catch          // only the missing catch trials are left
        toneTrials + catchTrials >= 2 && rng.below(5) == 0 -> Trial.Catch
        else -> Trial.Tone(freqs[idx], rng.bit(), levelDb(freqs[idx]))
    }

    fun answer(c: Choice) {
        check(!done) { "done" }
        when (val t = current) {
            is Trial.Catch -> { catchTrials++; if (c != Choice.NEITHER) falseAlarms++ }
            is Trial.Tone -> {
                toneTrials++
                val heard = (c == Choice.FIRST && t.inFirst) || (c == Choice.SECOND && !t.inFirst)
                if (!heard && wantedDb(t.hz) > 0.0) {
                    cappedTrials++; cappedMissHz += t.hz
                }
                val dir: Int
                if (heard) {
                    streak++
                    val need = if (missedOnce) 2 else 1
                    if (streak >= need) { streak = 0; dir = +1 } else dir = 0     // +1 = lower (harder)
                } else {
                    missedOnce = true; streak = 0; dir = -1
                }
                if (dir != 0) {
                    if (lastDir != 0 && dir != lastDir) reversals += freqs[idx]
                    lastDir = dir
                    idx = (idx + dir).coerceIn(0, freqs.size - 1)
                }
            }
        }
        if (!done) current = nextTrial()
    }

    /** Geometric mean of the last four reversal frequencies (fewer if fewer); null before two reversals. */
    fun floorHz(): Double? {
        if (reversals.size < 2) return null
        val r = reversals.takeLast(4)
        return exp(r.sumOf { ln(it) } / r.size)
    }

    /** Too many "heard" answers on silent catch trials (over a third) or too few reversals: don't apply. */
    val reliable: Boolean
        get() = reversals.size >= 4 && (catchTrials == 0 || falseAlarms * 3 <= catchTrials)
}

/**
 * Typical frequency response of a phone's own microphone, dB re its level at 1 kHz, in third octaves from 100 Hz to
 * 2 kHz: the median of published microphone measurements of 53 Android phones ([ANDROID]) and of the 11 Galaxy
 * phones among them ([GALAXY]), smoothed over three bands and rounded to 0.5 dB. Deliberately coarse: one phone can
 * be 5 dB off this at 100-300 Hz (and 20 dB below 100 Hz, which is why nothing below 100 Hz is corrected). It takes
 * off the typical tilt, not the phone's own. Only aggregates are kept here (no per-phone values).
 */
object MicResponse {
    val BANDS = doubleArrayOf(100.0, 125.0, 160.0, 200.0, 250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0, 2000.0)
    val GALAXY = doubleArrayOf(-0.5, -0.5, 0.0, 1.5, 1.5, 0.5, 0.5, 1.5, 1.5, 1.0, 0.0, 0.0, 0.5, 1.0)
    val ANDROID = doubleArrayOf(-1.0, -1.0, -1.0, 0.5, 0.5, 0.0, 0.0, 1.0, 1.5, 1.0, 0.0, 0.0, 1.0, 1.0)

    /** The table for a phone maker (Build.MANUFACTURER): Galaxy for Samsung, the Android median otherwise. */
    fun forMaker(maker: String?): DoubleArray = if (maker.equals("samsung", ignoreCase = true)) GALAXY else ANDROID

    /** Response at [hz], dB re 1 kHz (log-frequency interpolation; the end values outside 100 Hz-2 kHz). */
    fun db(table: DoubleArray, hz: Double): Double {
        val c = BANDS
        if (hz <= c.first()) return table.first()
        if (hz >= c.last()) return table.last()
        var i = 0
        while (c[i + 1] < hz) i++
        val u = ln(hz / c[i]) / ln(c[i + 1] / c[i])
        return table[i] + (table[i + 1] - table[i]) * u
    }

    /** Band levels measured at [centers] with the microphone's typical response taken off. */
    fun correct(table: DoubleArray, bandsDb: DoubleArray, centers: DoubleArray): DoubleArray =
        DoubleArray(bandsDb.size) { bandsDb[it] - db(table, centers[it]) }
}

/**
 * Optional room-noise correction of the floor bursts ("소음 보정", off unless the listener turns it on). The bursts are
 * set from the listener's threshold at 300 Hz plus how much less sensitive hearing is at the burst's frequency in quiet
 * ([HearingThreshold]). In a room with noise, the noise raises each threshold by its own amount: room noise is mostly
 * in the mids, so the 300 Hz threshold rises more than a low note's, the bursts play too loud and the floor comes out
 * too low. This adds back the difference of the two rises.
 *
 * The rise at a frequency: the room's third-octave level there ([roomBandsDb], from [NoiseGate.bandLevels] of the room
 * check), in dB SPL by Android's nominal input sensitivity ([SPL_OFFSET_DB]), as a masked tone level ([MASK_K_DB]),
 * power-added to the threshold in quiet. Nothing is calibrated, so the result is limited to [MAX_DOWN_DB] /
 * [MAX_UP_DB]; the validation log keeps the value at 100 Hz to check it against the UMIK-1.
 */
object NoiseMasking {
    /**
     * Android's input sensitivity per recording source (Android CDD), dB SPL = dB re full scale + this.
     * VOICE_RECOGNITION: a 90 dB SPL tone reads RMS 2500 of 32768 (-22.4 dB), flat within 3 dB from 100 Hz to 4 kHz.
     * UNPROCESSED: 94 dB SPL reads -36 dB re full scale, flat only within 10 dB from 100 Hz to 7 kHz and 20 dB below
     * 100 Hz. (0.9.0-beta.10 used the VOICE_RECOGNITION value for both, so with UNPROCESSED it took the room 17.6 dB
     * too quiet and hardly corrected.)
     */
    const val SPL_OFFSET_DB = 112.4
    const val SPL_OFFSET_UNPROCESSED_DB = 130.0
    fun splOffsetDb(unprocessed: Boolean): Double = if (unprocessed) SPL_OFFSET_UNPROCESSED_DB else SPL_OFFSET_DB
    /** Below this the microphone's response is allowed to be off by 20 dB: the bands under it are not used. */
    const val LOWEST_TRUSTED_HZ = 100.0
    /** A tone is just masked about this far from the noise power in its third-octave band (critical ratio ~17 dB
     *  at 300 Hz over a band ~70 Hz wide). */
    const val MASK_K_DB = -2.0
    const val MAX_DOWN_DB = 12.0
    const val MAX_UP_DB = 6.0

    /** Room level (dB re full scale) at [hz], log-frequency interpolation between [NoiseGate.TEST_BANDS]; below
     *  [LOWEST_TRUSTED_HZ] the level there is used (the bands under it are not trusted). */
    fun roomDb(roomBandsDb: DoubleArray, hz0: Double): Double {
        val c = NoiseGate.TEST_BANDS
        val hz = maxOf(hz0, LOWEST_TRUSTED_HZ)
        if (hz <= c.first()) return roomBandsDb.first()
        if (hz >= c.last()) return roomBandsDb.last()
        var i = 0
        while (c[i + 1] < hz) i++
        val u = ln(hz / c[i]) / ln(c[i + 1] / c[i])
        return roomBandsDb[i] + (roomBandsDb[i + 1] - roomBandsDb[i]) * u
    }

    /** How far the room raises the threshold at [hz], dB (0 in a silent room). */
    fun riseDb(roomBandsDb: DoubleArray, hz: Double, splOffsetDb: Double = SPL_OFFSET_DB): Double {
        val q = HearingThreshold.db(hz)
        val masked = roomDb(roomBandsDb, hz) + splOffsetDb + MASK_K_DB
        return 10 * log10(10.0.pow(q / 10) + 10.0.pow(masked / 10)) - q
    }

    /** Correction of the burst at [hz]: its rise minus the reference's, limited. Negative = quieter bursts. */
    fun correctionDb(roomBandsDb: DoubleArray, hz: Double, splOffsetDb: Double = SPL_OFFSET_DB): Double =
        (riseDb(roomBandsDb, hz, splOffsetDb) - riseDb(roomBandsDb, RefLevelStaircase.REF_HZ, splOffsetDb))
            .coerceIn(-MAX_DOWN_DB, MAX_UP_DB)
}

/**
 * Threshold of hearing in quiet (ISO 226:2003, dB SPL) from 20 Hz to 1 kHz, log-frequency interpolation. Only the
 * difference between two frequencies is used: how much louder a low note must be to be just heard.
 */
object HearingThreshold {
    private val HZ = doubleArrayOf(20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0, 200.0, 250.0, 315.0,
        400.0, 500.0, 630.0, 800.0, 1000.0)
    private val DB = doubleArrayOf(78.5, 68.7, 59.5, 51.1, 44.0, 37.5, 31.5, 26.5, 22.1, 17.9, 14.4, 11.4, 8.6, 6.2,
        4.4, 3.0, 2.2, 2.4)

    fun db(hz: Double): Double {
        val f = hz.coerceIn(HZ.first(), HZ.last())
        var i = 0
        while (i < HZ.size - 2 && f > HZ[i + 1]) i++
        val u = ln(f / HZ[i]) / ln(HZ[i + 1] / HZ[i])
        return DB[i] + (DB[i + 1] - DB[i]) * u
    }
}

/**
 * Step 1, first part: the listener's own threshold for a [REF_HZ] tone at this volume, by the same two-interval
 * question as the floor, 2-down/1-up (70.7 % right, Levitt 1971) from [startDb] (re the full tone): 6 dB steps until
 * the second reversal, then 3 dB steps; [stopReversals] reversals of the small steps (a lucky guess in the fast
 * descent then costs little). Catch trials as in [FloorStaircase] (at least
 * [MIN_CATCH]). Threshold: mean of the last four reversal levels. The room's noise raises it, and the floor bursts
 * that follow are set from it, so a not quite silent room shifts both alike.
 */
class RefLevelStaircase(
    seed: Long,
    val startDb: Double = -10.0,
    val minDb: Double = -66.0,
    val maxTrials: Int = 44,
    val stopReversals: Int = 6,
) {
    companion object { const val REF_HZ = 300.0 }

    private val rng = FitRng(seed)
    private var levelDb = startDb
    private var streak = 0
    private var lastDir = 0
    private var allReversals = 0
    private val reversals = ArrayList<Double>()
    var toneTrials = 0; private set
    var catchTrials = 0; private set
    var falseAlarms = 0; private set
    var current: FloorStaircase.Trial = next(); private set

    val done: Boolean get() = (reversals.size >= stopReversals && catchTrials >= MIN_CATCH) || toneTrials + catchTrials >= maxTrials

    private fun next(): FloorStaircase.Trial = when {
        reversals.size >= stopReversals -> FloorStaircase.Trial.Catch
        toneTrials + catchTrials >= 2 && rng.below(5) == 0 -> FloorStaircase.Trial.Catch
        else -> FloorStaircase.Trial.Tone(REF_HZ, rng.bit(), levelDb)
    }

    fun answer(c: FloorStaircase.Choice) {
        check(!done) { "done" }
        when (val t = current) {
            is FloorStaircase.Trial.Catch -> { catchTrials++; if (c != FloorStaircase.Choice.NEITHER) falseAlarms++ }
            is FloorStaircase.Trial.Tone -> {
                toneTrials++
                val heard = (c == FloorStaircase.Choice.FIRST && t.inFirst) || (c == FloorStaircase.Choice.SECOND && !t.inFirst)
                val dir: Int
                if (heard) {
                    streak++
                    if (streak >= 2) { streak = 0; dir = -1 } else dir = 0     // -1 = quieter (harder)
                } else {
                    streak = 0; dir = +1
                }
                if (dir != 0) {
                    if (lastDir != 0 && dir != lastDir) {
                        allReversals++
                        // the first two reversals (big steps) only find the region; the threshold uses the rest
                        if (allReversals > 2) reversals += levelDb
                    }
                    lastDir = dir
                    val step = if (allReversals < 2) 6.0 else 3.0
                    levelDb = (levelDb + dir * step).coerceIn(minDb, 0.0)
                }
            }
        }
        if (!done) current = next()
    }

    /** Mean of the last four reversal levels (dB re the full tone); null before two reversals. */
    fun thresholdDb(): Double? = if (reversals.size < 2) null else reversals.takeLast(4).average()

    val reliable: Boolean
        get() = reversals.size >= 4 && (catchTrials == 0 || falseAlarms * 3 <= catchTrials)
}

// ------------------------------------------------------------------------------------------------ step 2b: strength

/**
 * Preferred virtual-bass strength in {0, 3, 6, 9} dB by blind A/B pairs ("어느 쪽이 더 좋나요 / 차이 없음"),
 * climbing from the middle: 3 vs 6; then 0 vs 3 or 6 vs 9. (Was 2 dB apart: a listener on the S26 Ultra could not
 * tell the pairs apart and answered at random.) "No difference" counts as a win for
 * the lower level (virtual bass is a spice). At most three pairs, then the first pair again with the sides swapped:
 * a reversed answer marks the result inconsistent (not applied).
 */
class StrengthBracket(private val seed: Long) {
    enum class Answer { A, B, SAME }
    data class Pair(val lo: Int, val hi: Int, val loIsA: Boolean)

    private val rng = FitRng(seed)
    private val first = Pair(3, 6, rng.bit())
    var current: Pair? = first; private set
    var result: Int? = null; private set
    var consistent = true; private set
    var asked = 0; private set
    private var firstWinner: Int? = null

    /** Level the listener preferred in pair [p] (null = no difference). */
    private fun winner(p: Pair, a: Answer): Int? = when (a) {
        Answer.SAME -> null
        Answer.A -> if (p.loIsA) p.lo else p.hi
        Answer.B -> if (p.loIsA) p.hi else p.lo
    }

    fun answer(a: Answer) {
        val p = current ?: error("done")
        val w = winner(p, a)
        val keep = w ?: p.lo
        asked++
        if (result != null) {                                     // the repeated first pair: consistency only
            if (firstWinner != null && w != null && w != firstWinner) consistent = false
            current = null
            return
        }
        if (asked == 1) firstWinner = w
        val next: Pair? = when {
            p.lo == 3 && p.hi == 6 -> if (keep == 3) Pair(0, 3, rng.bit()) else Pair(6, 9, rng.bit())
            else -> null
        }
        if (next == null) { result = keep; current = Pair(first.lo, first.hi, !first.loIsA) } else current = next
    }

    val done: Boolean get() = current == null
}

// ------------------------------------------------------------------------------------------------ step 3: break-up

/**
 * Break-up limit: the bass clip with the layer at a level in 0..[maxDb], [stepDb] apart, answered "깨끗해요",
 * "떨려요" (rattle: the body or the cone flapping, a fluttering hum) or "지직거려요" (buzz: crackling, torn sound).
 * Either kind of break-up lowers the next level, "clean" raises it (1-up/1-down: converges where the listener hears
 * break-up half the time); the kind is kept apart for the result (which one comes first on this device). About one
 * trial in five after the first two (at least [MIN_CATCH]) is a catch trial: the same clip with the layer off; break-up
 * there is a false alarm (the volume alone makes the device rattle or buzz, or an answer by habit).
 *
 * Not an ABX of a level against a lower one: any audible layer differs from itself 6 dB lower, so an ABX would only
 * find that the two levels differ, not where the sound starts to break up.
 *
 * Break-up level: mean of the last four reversal levels. Limit: 3 dB below it, rounded down to whole dB. Clean three
 * times in a row at [maxDb] and never buzzing there: no break-up found, limit [maxDb].
 */
class BreakupStaircase(
    seed: Long,
    startDb: Double,
    val stepDb: Double = 2.0,
    val maxDb: Double = 12.0,
    val maxTrials: Int = 24,
    val stopReversals: Int = 6,
) {
    enum class Answer { CLEAN, RATTLE, BUZZ;
        val broke: Boolean get() = this != CLEAN
    }
    sealed class Trial {
        data class Level(val db: Double) : Trial()
        object Catch : Trial()
    }

    private val rng = FitRng(seed)
    private var levelDb = (Math.round(startDb / stepDb) * stepDb).coerceIn(0.0, maxDb)
    private var lastDir = 0
    private val reversals = ArrayList<Double>()
    var levelTrials = 0; private set
    var catchTrials = 0; private set
    var falseAlarms = 0; private set
    /** Level trials answered "rattle" / "buzz" (either is break-up). */
    var rattleAnswers = 0; private set
    var buzzAnswers = 0; private set
    /** Catch trials (layer off) answered "rattle" / "buzz". */
    var catchRattles = 0; private set
    var catchBuzzes = 0; private set
    val breakAnswers: Int get() = rattleAnswers + buzzAnswers
    /** Levels of the level trials heard as rattle / buzz. */
    private val rattleLevels = ArrayList<Double>()
    private val buzzLevels = ArrayList<Double>()
    private var cleanAtMax = 0
    private var buzzAtMax = 0
    /** Clean three times in a row at the top and never buzzing there: no break-up within the range. */
    private val cleanAtTop: Boolean get() = cleanAtMax >= 3 && buzzAtMax == 0
    var current: Trial = next(); private set

    /** Enough reversals (or clean three times at the top) and at least [MIN_CATCH] catch trials, or [maxTrials] asked. */
    val done: Boolean
        get() = ((reversals.size >= stopReversals || cleanAtTop) && catchTrials >= MIN_CATCH) ||
            levelTrials + catchTrials >= maxTrials

    private fun next(): Trial = when {
        reversals.size >= stopReversals || cleanAtTop -> Trial.Catch   // only the missing catch trials are left
        levelTrials + catchTrials >= 2 && rng.below(5) == 0 -> Trial.Catch
        else -> Trial.Level(levelDb)
    }

    fun answer(a: Answer) {
        check(!done) { "done" }
        when (current) {
            is Trial.Catch -> {
                catchTrials++
                if (a.broke) falseAlarms++
                if (a == Answer.RATTLE) catchRattles++
                if (a == Answer.BUZZ) catchBuzzes++
            }
            is Trial.Level -> {
                levelTrials++
                if (a == Answer.RATTLE) { rattleAnswers++; rattleLevels += levelDb }
                if (a == Answer.BUZZ) { buzzAnswers++; buzzLevels += levelDb }
                val dir = if (a.broke) -1 else 1
                if (lastDir != 0 && dir != lastDir) reversals += levelDb
                lastDir = dir
                val atTop = levelDb >= maxDb - 1e-9
                cleanAtMax = if (a == Answer.CLEAN && atTop) cleanAtMax + 1 else 0
                if (a.broke && atTop) buzzAtMax++
                levelDb = (levelDb + dir * stepDb).coerceIn(0.0, maxDb)
            }
        }
        if (!done) current = next()
    }

    /** Mean of the last four reversal levels (fewer if fewer); null before two reversals. */
    fun breakupDb(): Double? = if (reversals.size < 2) null else reversals.takeLast(4).average()

    /** Strength cap, whole dB: break-up - 3, or [maxDb] when no break-up was found; null while running or undecided. */
    val limitDb: Double?
        get() = when {
            !done -> null
            cleanAtTop || breakAnswers == 0 -> maxDb
            else -> breakupDb()?.let { kotlin.math.floor(it - 3.0).coerceIn(0.0, maxDb) }
        }

    /**
     * The kind of break-up this device makes first: the one heard at the lower levels (mean level of its answers);
     * the other kind only when it was never heard. Null when nothing broke up.
     */
    val firstKind: Answer?
        get() = when {
            rattleLevels.isEmpty() && buzzLevels.isEmpty() -> null
            buzzLevels.isEmpty() -> Answer.RATTLE
            rattleLevels.isEmpty() -> Answer.BUZZ
            rattleLevels.average() < buzzLevels.average() - 1e-9 -> Answer.RATTLE
            buzzLevels.average() < rattleLevels.average() - 1e-9 -> Answer.BUZZ
            else -> if (rattleAnswers > buzzAnswers) Answer.RATTLE else Answer.BUZZ
        }

    /** Mean level of the answers of one kind (null: never heard). */
    fun meanDb(kind: Answer): Double? = when (kind) {
        Answer.RATTLE -> rattleLevels.takeIf { it.isNotEmpty() }?.average()
        Answer.BUZZ -> buzzLevels.takeIf { it.isNotEmpty() }?.average()
        Answer.CLEAN -> null
    }

    /** Enough reversals (or clean at the top) and no more than a third of the catch trials heard as breaking up. */
    val reliable: Boolean
        get() = (reversals.size >= 4 || cleanAtTop) && (catchTrials == 0 || falseAlarms * 3 <= catchTrials)
}

// ------------------------------------------------------------------------------------------------ step 4: shape

/** Bradley-Terry strengths from pairwise wins (ties count half to each), MM algorithm with a weak prior. */
object BradleyTerry {
    fun fit(wins: Array<DoubleArray>, iterations: Int = 200): DoubleArray {
        val n = wins.size
        val prior = 0.5
        var p = DoubleArray(n) { 1.0 }
        repeat(iterations) {
            val q = DoubleArray(n) { i ->
                var w = prior
                var d = 0.0
                for (j in 0 until n) if (j != i) {
                    w += wins[i][j]
                    val nij = wins[i][j] + wins[j][i] + 2 * prior / (n - 1)
                    d += nij / (p[i] + p[j])
                }
                w / d
            }
            val g = exp(q.sumOf { ln(it) } / n)
            p = DoubleArray(n) { q[it] / g }
        }
        return p
    }
}

/**
 * 3 x 3 grid of (roll-off offset, low-order weight). The first pair is the centre against a corner the seed picks;
 * then the pair whose scores are closest, penalised by how often it has been asked; [maxPairs] pairs, the first pair
 * repeated at the end (sides swapped) for consistency.
 */
class ShapeGrid(private val seed: Long, val maxPairs: Int = 18) {
    data class Cell(val rolloffDbOct: Double, val lowOrderDb: Double)
    enum class Answer { A, B, SAME }

    val cells = listOf(-6.0, 0.0, 6.0).flatMap { r -> listOf(-4.0, 0.0, 4.0).map { w -> Cell(r, w) } }
    private val wins = Array(cells.size) { DoubleArray(cells.size) }
    private val asked = Array(cells.size) { IntArray(cells.size) }
    private val rng = FitRng(seed)
    var pairs = 0; private set
    private val first = Triple(4, intArrayOf(0, 2, 6, 8)[rng.below(4)], rng.bit())   // (i, j, iIsA)
    var current: Triple<Int, Int, Boolean>? = first
        private set
    private var firstAnswer: Int = -2
    var consistent = true; private set

    fun answer(a: Answer) {
        val (i, j, iIsA) = current ?: error("done")
        val win = when (a) { Answer.SAME -> -1; Answer.A -> if (iIsA) i else j; Answer.B -> if (iIsA) j else i }
        if (win == -1) { wins[i][j] += 0.5; wins[j][i] += 0.5 } else wins[win][if (win == i) j else i] += 1.0
        asked[i][j]++; asked[j][i]++
        pairs++
        if (pairs == 1) firstAnswer = win
        current = when {
            pairs < maxPairs - 1 -> nextPair()
            pairs == maxPairs - 1 -> Triple(first.first, first.second, !first.third)
            else -> {
                if (firstAnswer != -1 && win != -1 && firstAnswer != win) consistent = false
                null
            }
        }
    }

    private fun nextPair(): Triple<Int, Int, Boolean> {
        val s = BradleyTerry.fit(wins).map { ln(it) }
        var best = 0 to 1
        var bestCost = Double.POSITIVE_INFINITY
        for (i in cells.indices) for (j in i + 1 until cells.size) {
            val cost = abs(s[i] - s[j]) + 0.7 * asked[i][j] + 1e-6 * rng.below(1000)
            if (cost < bestCost) { bestCost = cost; best = i to j }
        }
        return Triple(best.first, best.second, rng.bit())
    }

    val done: Boolean get() = current == null
    fun scores(): DoubleArray = BradleyTerry.fit(wins)
    fun best(): Cell = cells[scores().withIndex().maxByOrNull { it.value }!!.index]
}

// ------------------------------------------------------------------------------------------------ mapping

/** What a found speaker floor sets (the S26 Ultra's measured floor of 150 Hz gives its own values). */
object BassFitMapping {
    const val REF_FLOOR_HZ = 150.0
    /** Highest generator edge the engine takes (pvb_engine.cpp sanitize). */
    const val MAX_EDGE_HZ = 280.0
    data class FloorSettings(val speakerFloorHz: Double, val hpHz: Double, val boundaryHz: Double, val outLoHz: Double,
                             val tableScale: Double)

    fun fromFloor(floorHz: Double): FloorSettings {
        val f = floorHz.coerceIn(100.0, 300.0)
        val k = (f / REF_FLOOR_HZ).coerceIn(0.75, 1.75)
        return FloorSettings(
            speakerFloorHz = f,
            hpHz = max(80.0, f / 1.5),
            boundaryHz = min(MAX_EDGE_HZ, 190.0 * k),
            outLoHz = min(300.0, 150.0 * k),
            tableScale = k,
        )
    }

    /** Low-order weight w (dB) as harmonic offsets k = 2, 3, 4, 5+: k = 2 gets +w, the others -w/3 each. */
    fun harmonicOffsets(lowOrderDb: Double): DoubleArray = doubleArrayOf(lowOrderDb, -lowOrderDb / 3, -lowOrderDb / 3, -lowOrderDb / 3)
}

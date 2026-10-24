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
    const val MIN_SNR_DB = 35.0
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

    fun answer(saidXIsA: Boolean): State {
        check(state == State.RUNNING) { "decided" }
        if (saidXIsA == xIsA()) correct++
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
    val startHz: Double = 300.0,
    val minHz: Double = 70.0,
    val maxTrials: Int = 30,
    val stopReversals: Int = 6,
) {
    enum class Choice { FIRST, SECOND, NEITHER, BUZZ_ONLY }
    sealed class Trial {
        data class Tone(val hz: Double, val inFirst: Boolean) : Trial()
        object Catch : Trial()
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
        else -> Trial.Tone(freqs[idx], rng.bit())
    }

    fun answer(c: Choice) {
        check(!done) { "done" }
        when (val t = current) {
            is Trial.Catch -> { catchTrials++; if (c != Choice.NEITHER) falseAlarms++ }
            is Trial.Tone -> {
                toneTrials++
                val heard = (c == Choice.FIRST && t.inFirst) || (c == Choice.SECOND && !t.inFirst)
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

// ------------------------------------------------------------------------------------------------ step 2b: strength

/**
 * Preferred virtual-bass strength in {0, 2, 4, 6, 8} dB by blind A/B pairs ("어느 쪽이 더 좋나요 / 차이 없음"),
 * climbing from the middle: 2 vs 4; then 0 vs 2 or 4 vs 6; then 6 vs 8 if 6 won. "No difference" counts as a win for
 * the lower level (virtual bass is a spice). At most three pairs, then the first pair again with the sides swapped:
 * a reversed answer marks the result inconsistent (not applied).
 */
class StrengthBracket(private val seed: Long) {
    enum class Answer { A, B, SAME }
    data class Pair(val lo: Int, val hi: Int, val loIsA: Boolean)

    private val rng = FitRng(seed)
    private val first = Pair(2, 4, rng.bit())
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
            p.lo == 2 && p.hi == 4 -> if (keep == 2) Pair(0, 2, rng.bit()) else Pair(4, 6, rng.bit())
            p.lo == 4 && p.hi == 6 && keep == 6 -> Pair(6, 8, rng.bit())
            else -> null
        }
        if (next == null) { result = keep; current = Pair(first.lo, first.hi, !first.loIsA) } else current = next
    }

    val done: Boolean get() = current == null
}

// ------------------------------------------------------------------------------------------------ step 3: break-up

/**
 * Break-up limit: yes/no on the bass clip ("지직거림이나 찌그러짐이 들리나요?") with the layer at a level in
 * 0..[maxDb], [stepDb] apart. "Buzz" lowers the next level, "clean" raises it (1-up/1-down: converges where the
 * listener hears break-up half the time). About one trial in five after the first two (at least [MIN_CATCH]) is a
 * catch trial: the same clip with the layer off; "buzz" there is a false alarm (the volume alone makes the speaker
 * buzz, or "buzz" by habit).
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
    enum class Answer { CLEAN, BUZZ }
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
    var buzzAnswers = 0; private set
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
            is Trial.Catch -> { catchTrials++; if (a == Answer.BUZZ) falseAlarms++ }
            is Trial.Level -> {
                levelTrials++
                if (a == Answer.BUZZ) buzzAnswers++
                val dir = if (a == Answer.BUZZ) -1 else 1
                if (lastDir != 0 && dir != lastDir) reversals += levelDb
                lastDir = dir
                val atTop = levelDb >= maxDb - 1e-9
                cleanAtMax = if (a == Answer.CLEAN && atTop) cleanAtMax + 1 else 0
                if (a == Answer.BUZZ && atTop) buzzAtMax++
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
            cleanAtTop || buzzAnswers == 0 -> maxDb
            else -> breakupDb()?.let { kotlin.math.floor(it - 3.0).coerceIn(0.0, maxDb) }
        }

    /** Enough reversals (or clean at the top) and no more than a third of the catch trials heard as buzzing. */
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

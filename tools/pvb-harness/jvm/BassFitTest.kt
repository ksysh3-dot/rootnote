import me.timschneeberger.rootlessjamesdsp.pvb.AbxRun
import me.timschneeberger.rootlessjamesdsp.pvb.BassFitMapping
import me.timschneeberger.rootlessjamesdsp.pvb.BreakupStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.FitLatency
import me.timschneeberger.rootlessjamesdsp.pvb.FitRng
import me.timschneeberger.rootlessjamesdsp.pvb.FitStats
import me.timschneeberger.rootlessjamesdsp.pvb.FloorStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.HearingThreshold
import me.timschneeberger.rootlessjamesdsp.pvb.RefLevelStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.NoiseGate
import me.timschneeberger.rootlessjamesdsp.pvb.NoiseMasking
import me.timschneeberger.rootlessjamesdsp.pvb.ShapeGrid
import me.timschneeberger.rootlessjamesdsp.pvb.StrengthBracket
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log2
import kotlin.math.pow
import kotlin.math.sin
import kotlin.system.exitProcess

// "저음 맞추기" pure logic (BassFit.kt) against simulated listeners and rooms.

private var passed = 0
private fun check(ok: Boolean, what: String) {
    if (!ok) { println("[FAIL] $what"); exitProcess(1) }
    println("[PASS] $what"); passed++
}

private const val FS = 48000.0

private fun noise(n: Int, db: Double, seed: Long): FloatArray {
    val r = FitRng(seed)
    val a = 10.0.pow(db / 20) * Math.sqrt(3.0)
    return FloatArray(n) { (((r.next() ushr 11).toDouble() / (1L shl 53)) * 2 - 1).times(a).toFloat() }
}

private fun tones(n: Int, db: Double, hz: DoubleArray): FloatArray {
    val a = 10.0.pow(db / 20) * Math.sqrt(2.0)
    return FloatArray(n) { i -> hz.sumOf { a * sin(2 * PI * it * i / FS) }.toFloat() }
}

private fun add(a: FloatArray, b: FloatArray) = FloatArray(a.size) { a[it] + b[it] }

fun main() {
    // --- statistics
    check(abs(FitStats.guessP(7, 8) - 9.0 / 256) < 1e-12 && abs(FitStats.guessP(6, 6) - 1.0 / 64) < 1e-12,
        "guessing odds: 7/8 = 9/256, 6/6 = 1/64")

    // --- noise gate
    val n3 = (3 * FS).toInt(); val n2 = (2 * FS).toInt()
    val bands = NoiseGate.TEST_BANDS
    val quiet = noise(n3, -75.0, 1)
    val ref = tones(n2, -30.0, bands)
    val okV = NoiseGate.judge(quiet, add(noise(n2, -75.0, 2), ref), FS)
    check(okV.pass && okV.worstSnrDb > 35, "quiet room passes (worst SNR ${"%.1f".format(okV.worstSnrDb)} dB)")
    val loud = noise(n3, -20.0, 3)   // broadband: about -53 dB per low third-octave, a TV or fan in the room
    val loudV = NoiseGate.judge(loud, add(noise(n2, -20.0, 4), ref), FS)
    check(!loudV.pass && NoiseGate.Reason.SNR_LOW in loudV.reasons, "noisy room fails on SNR (${"%.1f".format(loudV.worstSnrDb)} dB)")
    val bursty = quiet.copyOf().also { for (i in 60000 until 64800) it[i] += (0.05 * sin(2 * PI * 300 * i / FS)).toFloat() }
    val burstV = NoiseGate.judge(bursty, add(noise(n2, -75.0, 5), ref), FS)
    check(!burstV.pass && NoiseGate.Reason.ROOM_UNSTEADY in burstV.reasons, "a voice-like burst in the room fails (jump ${"%.1f".format(burstV.jumpDb)} dB)")
    check(NoiseGate.judge(null, null, FS).reasons == listOf(NoiseGate.Reason.NO_MIC), "no microphone: says so")
    // a phone speaker barely plays 63-100 Hz: in a quiet room that is not "noise"
    val phoneRef = add(tones(n2, -30.0, bands.filter { it >= 125.0 }.toDoubleArray()), tones(n2, -62.0, bands.filter { it < 125.0 }.toDoubleArray()))
    val phoneV = NoiseGate.judge(quiet, add(noise(n2, -75.0, 8), phoneRef), FS)
    check(phoneV.pass, "quiet room, speaker silent below 125 Hz: passes (worst margin ${"%.1f".format(phoneV.worstSnrDb)} dB at ${phoneV.worstBandHz.toInt()} Hz)")
    // ... but a rumble there still fails (it masks the tones above it)
    val rumble = add(quiet, tones(n3, -44.0, doubleArrayOf(63.0)))
    val rumbleV = NoiseGate.judge(rumble, add(add(noise(n2, -75.0, 9), tones(n2, -44.0, doubleArrayOf(63.0))), phoneRef), FS)
    check(!rumbleV.pass && rumbleV.worstBandHz == 63.0 && NoiseGate.Reason.SNR_LOW in rumbleV.reasons,
        "a 63 Hz rumble under ${NoiseGate.MIN_SNR_DB.toInt()} dB below the speaker's strongest band fails (${"%.1f".format(rumbleV.worstSnrDb)} dB at ${rumbleV.worstBandHz.toInt()} Hz)")
    // latency: the reference starts 230 ms after it was asked for
    run {
        val from = (1.0 * FS).toInt(); val lat = (0.23 * FS).toInt()
        val x = noise((3.0 * FS).toInt(), -75.0, 10)
        val r = tones(x.size, -30.0, doubleArrayOf(160.0, 315.0))
        for (i in from + lat until x.size) x[i] += r[i]
        val on = FitLatency.onsetFrame(x, FS, from)
        check(on != null && abs(on - (from + lat)) <= (0.012 * FS).toInt(), "latency: onset found at ${on?.let { (it - from) * 1000 / FS }} ms (230)")
        check(FitLatency.onsetFrame(noise(x.size, -75.0, 11), FS, from) == null, "latency: no reference -> null (typical latency used)")
    }
    val roomBands = NoiseGate.bandLevels(quiet, FS, bands)
    check(!NoiseGate.disturbed(noise(n2, -75.0, 6), FS, roomBands) &&
        NoiseGate.disturbed(add(noise(n2, -75.0, 7), tones(n2, -50.0, doubleArrayOf(160.0))), FS, roomBands),
        "silent interval: room noise passes, a 160 Hz sound 25 dB over it discards the trial")

    // --- ABX
    run {
        val perfect = AbxRun(42)
        while (perfect.state == AbxRun.State.RUNNING) perfect.answer(perfect.xIsA())
        check(perfect.state == AbxRun.State.DISTINGUISHED && perfect.trials == 6, "ABX: a perfect listener stops at 6/6")
        var falsePos = 0
        val runs = 4000
        for (s in 0 until runs) {
            val r = FitRng(s * 7919L + 1)
            val a = AbxRun(s.toLong())
            while (a.state == AbxRun.State.RUNNING) a.answer(r.bit())
            if (a.state == AbxRun.State.DISTINGUISHED) falsePos++
        }
        val rate = falsePos.toDouble() / runs
        check(rate < 0.06, "ABX: a guessing listener is 'distinguished' in ${"%.1f".format(100 * rate)} % of runs (< 6 %)")
        var hits = 0
        for (s in 0 until 2000) {
            val r = FitRng(s * 104729L + 3)
            val a = AbxRun(s.toLong() + 99)
            while (a.state == AbxRun.State.RUNNING) { val right = r.below(100) < 95; a.answer(if (right) a.xIsA() else !a.xIsA()) }
            if (a.state == AbxRun.State.DISTINGUISHED) hits++
        }
        check(hits / 2000.0 > 0.9, "ABX: a 95 %-right listener is distinguished in ${hits / 20} % of runs (> 90 %)")
    }

    // --- floor staircase: listener with a logistic psychometric function around the true floor
    fun floorRun(trueHz: Double, seed: Long, catchLiar: Boolean = false): FloorStaircase {
        val st = FloorStaircase(seed)
        val r = FitRng(seed * 31 + 7)
        while (!st.done) {
            when (val t = st.current) {
                is FloorStaircase.Trial.Catch -> st.answer(if (catchLiar) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.NEITHER)
                is FloorStaircase.Trial.Tone -> {
                    val pHear = 1 / (1 + exp(-log2(t.hz / trueHz) / 0.06))
                    val heard = (r.next() ushr 11).toDouble() / (1L shl 53) < pHear
                    val c = if (heard) (if (t.inFirst) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND)
                            else if (r.bit()) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND   // guess
                    st.answer(c)
                }
            }
        }
        return st
    }
    for (f in doubleArrayOf(130.0, 150.0, 200.0, 240.0)) {
        val errs = (0 until 200).map { s -> floorRun(f, s.toLong()).floorHz()?.let { abs(log2(it / f)) } ?: 9.0 }.sorted()
        val med = errs[errs.size / 2]; val p90 = errs[errs.size * 9 / 10]
        check(med < 1.0 / 6 && p90 < 1.0 / 3,
            "floor ${f.toInt()} Hz: median error ${"%.2f".format(med)} oct, 90th ${"%.2f".format(p90)} oct (< 1/6, < 1/3)")
    }
    run {
        val st = floorRun(150.0, 5, catchLiar = true)
        check(!st.reliable && st.catchTrials > 0, "floor: a listener who 'hears' silent catch trials is marked unreliable")
        val ok = floorRun(150.0, 5)
        check(ok.reliable && ok.toneTrials + ok.catchTrials <= 30, "floor: an honest listener is reliable within 30 trials")
    }

    // --- step 1 with a level: the listener's threshold at 300 Hz first, then bursts 10 dB over it (re ISO 226).
    // A physical listener: speaker = 4th-order high-pass at fc (24 dB/oct below), hearing = ISO 226 threshold,
    // threshold at 300 Hz [thr300] dB re the full tone; logistic with a 1 dB slope on the sensation level.
    fun lr4Db(f: Double, fc: Double): Double { val r = (f / fc).pow(4); return 20 * kotlin.math.log10(r / (1 + r)) }
    fun sensation(level: Double, f: Double, fc: Double, thr300: Double) =
        level - (thr300 + HearingThreshold.db(f) - HearingThreshold.db(300.0) - (lr4Db(f, fc) - lr4Db(300.0, fc)))
    // [guess]: when not heard, a forced guess (worst case); otherwise "neither" (what the screen offers).
    fun levelRun(fc: Double, thr300: Double, seed: Long, guess: Boolean = false): Pair<RefLevelStaircase, FloorStaircase> {
        val r = FitRng(seed * 977 + 13)
        fun hear(level: Double, f: Double) = (r.next() ushr 11).toDouble() / (1L shl 53) < 1 / (1 + exp(-sensation(level, f, fc, thr300) / 1.0))
        fun ans(t: FloorStaircase.Trial): FloorStaircase.Choice = when (t) {
            is FloorStaircase.Trial.Catch -> FloorStaircase.Choice.NEITHER
            is FloorStaircase.Trial.Tone -> if (hear(t.levelDb, t.hz)) (if (t.inFirst) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND)
                else if (!guess) FloorStaircase.Choice.NEITHER else if (r.bit()) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND
        }
        val ref = RefLevelStaircase(seed)
        while (!ref.done) ref.answer(ans(ref.current))
        val fl = FloorStaircase(seed + 1, refDb = ref.thresholdDb() ?: -FloorStaircase.SL_DB)
        while (!fl.done) fl.answer(ans(fl.current))
        return ref to fl
    }
    /** Where the speaker plays 10 dB less than at 300 Hz (what step 1 should find now). */
    fun minus10(fc: Double): Double {
        var lo = 20.0; var hi = 300.0
        repeat(60) { val m = kotlin.math.sqrt(lo * hi); if (lr4Db(m, fc) - lr4Db(300.0, fc) < -10) lo = m else hi = m }
        return kotlin.math.sqrt(lo * hi)
    }
    for (guess in listOf(false, true)) {
        val runs = (0 until 200).map { levelRun(150.0, -35.0, it.toLong(), guess).first }
        val errs = runs.map { it.thresholdDb()?.let { t -> abs(t - (-35.0)) } ?: 99.0 }.sorted()
        check(errs[errs.size / 2] < 2.0 && errs[errs.size * 9 / 10] < (if (guess) 4.0 else 3.0) && runs.count { it.reliable } >= 190,
            "reference threshold at 300 Hz (${if (guess) "forced guesses" else "\"neither\" when unheard"}): median error ${"%.1f".format(errs[errs.size / 2])} dB, 90th ${"%.1f".format(errs[errs.size * 9 / 10])} dB, reliable in ${runs.count { it.reliable }} / 200")
    }
    for (guess in listOf(false, true)) for (fc in doubleArrayOf(120.0, 150.0, 180.0, 220.0)) {
        val want = minus10(fc)
        val res = (0 until 120).map { levelRun(fc, -35.0, it.toLong() + 500, guess) }
        val errs = res.map { it.second.floorHz()?.let { f -> abs(log2(f / want)) } ?: 9.0 }.sorted()
        val med = errs[errs.size / 2]; val p90 = errs[errs.size * 9 / 10]
        check(med < 0.2 && p90 < (if (guess) 0.6 else 0.3) && res.count { it.second.cappedNearFloor() } <= 6,
            "hidden high-pass ${fc.toInt()} Hz${if (guess) " (forced guesses)" else ""}: floor near its -10 dB point ${want.toInt()} Hz (median ${"%.2f".format(med)} oct, 90th ${"%.2f".format(p90)} oct), capped near the floor in ${res.count { it.second.cappedNearFloor() }} / 120")
    }
    run {
        // the old way (bursts at full level) for a 220 Hz high-pass at a sensitive listener: far too low, the bug
        val r = FitRng(77)
        val st = FloorStaircase(3)
        while (!st.done) when (val t = st.current) {
            is FloorStaircase.Trial.Catch -> st.answer(FloorStaircase.Choice.NEITHER)
            is FloorStaircase.Trial.Tone -> st.answer(if ((r.next() ushr 11).toDouble() / (1L shl 53) < 1 / (1 + exp(-sensation(0.0, t.hz, 220.0, -35.0))))
                (if (t.inFirst) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND) else FloorStaircase.Choice.NEITHER)
        }
        val now = levelRun(220.0, -35.0, 3).second.floorHz()!!
        check(st.floorHz()!! < now / 1.4, "full-level bursts under a 220 Hz high-pass found ${st.floorHz()!!.toInt()} Hz; with the reference level ${now.toInt()} Hz")
    }
    run {
        // too low a volume: the bursts at the lowest notes would need more than the full tone; missed ones are counted
        val (_, fl) = levelRun(150.0, -8.0, 9)
        check(fl.cappedTrials > 0 && fl.cappedNearFloor(), "threshold only 8 dB under the full tone: capped bursts are counted (${fl.cappedTrials}) and flag the floor")
        check(abs(HearingThreshold.db(100.0) - 26.5) < 1e-9 && HearingThreshold.db(300.0) in 8.6..11.4, "ISO 226 threshold table")
    }

    // --- strength bracket: listener preferring the level nearest an ideal; equal distance = no difference
    fun bracket(ideal: Double, seed: Long, flip: Boolean = false): StrengthBracket {
        val b = StrengthBracket(seed)
        var k = 0
        while (!b.done) {
            val p = b.current!!
            val dLo = abs(p.lo - ideal); val dHi = abs(p.hi - ideal)
            var pref: Int? = when { abs(dLo - dHi) < 1e-9 -> null; dLo < dHi -> p.lo; else -> p.hi }
            if (flip && b.result != null) pref = if (pref == p.lo) p.hi else p.lo   // the repeat answered the other way
            val a = when (pref) { null -> StrengthBracket.Answer.SAME; p.lo -> if (p.loIsA) StrengthBracket.Answer.A else StrengthBracket.Answer.B
                else -> if (p.loIsA) StrengthBracket.Answer.B else StrengthBracket.Answer.A }
            b.answer(a); k++
        }
        return b
    }
    val want = mapOf(0.0 to 0, 2.2 to 3, 5.8 to 6, 9.0 to 9)
    check(want.all { (ideal, lvl) -> (0 until 20).all { s -> bracket(ideal, s.toLong()).let { it.result == lvl && it.consistent } } },
        "strength: lands on the level nearest the listener's ideal (0, 3, 6, 9), consistent, 3 pairs at most")
    check((0 until 20).all { s -> bracket(4.5, s.toLong()).result == 3 }, "strength: ideal halfway between 3 and 6 -> ties keep the lower")
    check(bracket(6.0, 3, flip = true).let { !it.consistent }, "strength: a reversed answer on the repeated first pair -> inconsistent")

    // --- break-up staircase: yes/no listener, logistic around the true break-up level, honest on catch trials
    fun breakup(trueDb: Double, seed: Long, start: Double = 4.0, liar: Boolean = false): BreakupStaircase {
        val b = BreakupStaircase(seed, start)
        val r = FitRng(seed * 6151 + 11)
        while (!b.done) {
            val buzz = when (val t = b.current) {
                is BreakupStaircase.Trial.Catch -> liar
                is BreakupStaircase.Trial.Level -> (r.next() ushr 11).toDouble() / (1L shl 53) < 1 / (1 + exp(-(t.db - trueDb) / 0.7))
            }
            b.answer(if (buzz) BreakupStaircase.Answer.BUZZ else BreakupStaircase.Answer.CLEAN)
        }
        return b
    }
    for (t in doubleArrayOf(5.0, 8.0, 10.0, 11.5)) {
        val runs = (0 until 200).map { breakup(t, it.toLong()) }
        val errs = runs.map { it.breakupDb()?.let { b -> abs(b - t) } ?: 99.0 }.sorted()
        val med = errs[errs.size / 2]; val p90 = errs[errs.size * 9 / 10]
        val limits = runs.mapNotNull { it.limitDb }
        check(med < 1.0 && p90 < 2.5 && runs.count { it.reliable } >= 180 && limits.count { it <= t - 1.0 } >= 190,
            "break-up at $t dB: median error ${"%.2f".format(med)} dB, 90th ${"%.2f".format(p90)} dB, limits ${limits.minOrNull()}..${limits.maxOrNull()}, ${limits.count { it <= t - 1.0 }} / 200 at least 1 dB under it (break-up - 3, whole dB)")
    }
    run {
        val never = (0 until 200).count { s -> breakup(99.0, s.toLong()).let { it.limitDb == 12.0 && it.reliable } }
        check(never >= 195, "break-up: never buzzes -> limit 12 dB in $never / 200 runs")
        val lie = (0 until 100).count { s -> !breakup(8.0, s.toLong(), liar = true).reliable }
        check(lie >= 95, "break-up: 'buzz' on catch trials (layer off) -> unreliable in $lie / 100 runs")
        val b = breakup(8.0, 3)
        check(b.levelTrials + b.catchTrials <= 24, "break-up: at most 24 questions (${b.levelTrials + b.catchTrials})")
    }
    run {
        // three answers: a device that rattles from rattleDb and buzzes from buzzDb (the higher one wins when both)
        fun kinds(rattleDb: Double, buzzDb: Double, seed: Long): BreakupStaircase {
            val b = BreakupStaircase(seed, 4.0)
            val r = FitRng(seed * 7919 + 3)
            fun p(x: Double, t: Double) = (r.next() ushr 11).toDouble() / (1L shl 53) < 1 / (1 + exp(-(x - t) / 0.7))
            while (!b.done) {
                val a = when (val t = b.current) {
                    is BreakupStaircase.Trial.Catch -> BreakupStaircase.Answer.CLEAN
                    is BreakupStaircase.Trial.Level -> when {
                        p(t.db, buzzDb) -> BreakupStaircase.Answer.BUZZ
                        p(t.db, rattleDb) -> BreakupStaircase.Answer.RATTLE
                        else -> BreakupStaircase.Answer.CLEAN
                    }
                }
                b.answer(a)
            }
            return b
        }
        val rattleFirst = (0 until 200).map { kinds(6.0, 99.0, it.toLong()) }
        check(rattleFirst.count { it.firstKind == BreakupStaircase.Answer.RATTLE } == 200 &&
            rattleFirst.count { it.breakupDb()?.let { d -> abs(d - 6.0) < 1.5 } == true } >= 180,
            "break-up: rattle alone counts as break-up (limit from it), kind 'rattle'")
        val buzzOnly = (0 until 200).map { kinds(99.0, 7.0, it.toLong()) }
        check(buzzOnly.count { it.firstKind == BreakupStaircase.Answer.BUZZ } == 200, "break-up: buzz alone, kind 'buzz'")
        val clean = BreakupStaircase(1, 4.0).also { while (!it.done) it.answer(BreakupStaircase.Answer.CLEAN) }
        check(clean.firstKind == null && clean.limitDb == 12.0, "break-up: always clean -> no kind, limit 12 dB")
        val rattleCatch = BreakupStaircase(2, 4.0).also { b ->
            while (!b.done) b.answer(if (b.current is BreakupStaircase.Trial.Catch) BreakupStaircase.Answer.RATTLE else BreakupStaircase.Answer.CLEAN)
        }
        check(rattleCatch.catchRattles == rattleCatch.catchTrials && rattleCatch.falseAlarms == rattleCatch.catchTrials && !rattleCatch.reliable,
            "break-up: rattle with the layer off -> false alarm, counted as a rattle, unreliable")
    }

    // --- shape grid: listener utility peaked at one cell, Thurstone noise
    fun grid(target: Int, seed: Long): ShapeGrid {
        val g = ShapeGrid(seed)
        val r = FitRng(seed * 13 + 5)
        fun u(i: Int): Double { val c = g.cells[i]; val t = g.cells[target]
            return -((c.rolloffDbOct - t.rolloffDbOct) / 6).pow(2) - ((c.lowOrderDb - t.lowOrderDb) / 4).pow(2) }
        while (!g.done) {
            val (i, j, iIsA) = g.current!!
            val d = u(i) - u(j) + 0.35 * (((r.next() ushr 11).toDouble() / (1L shl 53)) * 2 - 1)
            val a = when { abs(d) < 0.08 -> ShapeGrid.Answer.SAME; (d > 0) == iIsA -> ShapeGrid.Answer.A; else -> ShapeGrid.Answer.B }
            g.answer(a)
        }
        return g
    }
    check((0 until 40).map { ShapeGrid(it.toLong()).current!!.let { (i, j, _) -> i * 10 + j } }.toSet().size == 4,
        "shape: the first pair (centre vs a corner) changes with the seed")
    for (target in intArrayOf(0, 4, 8, 5)) {
        val right = (0 until 40).count { s -> grid(target, s.toLong()).best() == ShapeGrid(0).cells[target] }
        check(right >= 30, "shape: preferred cell $target found in $right / 40 runs (18 pairs)")
    }

    // --- ABX "not sure": counted as wrong, two of them end the run
    val unsure = AbxRun(5)
    unsure.answer(null); check(unsure.state == AbxRun.State.RUNNING, "ABX: one 'not sure' keeps going")
    unsure.answer(null); check(unsure.state == AbxRun.State.NOT_DISTINGUISHED && unsure.correct == 0, "ABX: two 'not sure' end as not distinguished")
    val oneUnsure = AbxRun(6)
    oneUnsure.answer(null); for (t in 1 until 8) if (oneUnsure.state == AbxRun.State.RUNNING) oneUnsure.answer(oneUnsure.xIsA())
    check(oneUnsure.state == AbxRun.State.DISTINGUISHED, "ABX: one 'not sure' then all right still passes (7 / 8)")

    // --- noise correction (optional "소음 보정")
    val silent = DoubleArray(NoiseGate.TEST_BANDS.size) { -200.0 }
    check(abs(NoiseMasking.correctionDb(silent, 100.0)) < 1e-6, "noise correction: a silent room changes nothing")
    // an ordinary room, dB SPL per third octave (63 .. 500 Hz), mostly in the mids
    val office = doubleArrayOf(35.0, 33.0, 30.0, 28.0, 27.0, 27.0, 27.0, 27.0, 26.0, 25.0).map { it - NoiseMasking.SPL_OFFSET_DB }.toDoubleArray()
    val c100 = NoiseMasking.correctionDb(office, 100.0)
    check(c100 < -5 && c100 >= -NoiseMasking.MAX_DOWN_DB, "noise correction: room noise in the mids lowers the 100 Hz burst (${"%.1f".format(c100)} dB)")
    check(abs(NoiseMasking.correctionDb(office, RefLevelStaircase.REF_HZ)) < 1e-9, "noise correction: none at the reference")
    val lowRumble = doubleArrayOf(60.0, 55.0, 45.0, 35.0, 25.0, 15.0, 10.0, 8.0, 8.0, 8.0).map { it - NoiseMasking.SPL_OFFSET_DB }.toDoubleArray()
    check(NoiseMasking.correctionDb(lowRumble, 100.0) > 0, "noise correction: a low rumble raises the lowest bursts")
    val rawRoom = doubleArrayOf(35.0, 33.0, 30.0, 28.0, 27.0, 27.0, 27.0, 27.0, 26.0, 25.0).map { it - NoiseMasking.SPL_OFFSET_UNPROCESSED_DB }.toDoubleArray()
    check(abs(NoiseMasking.correctionDb(rawRoom, 100.0, NoiseMasking.splOffsetDb(true)) - c100) < 1e-9,
        "noise correction: the same room recorded UNPROCESSED (17.6 dB lower in full scale) gives the same correction")
    check(NoiseMasking.correctionDb(rawRoom, 100.0) > c100 + 3, "noise correction: UNPROCESSED read with the VOICE_RECOGNITION value corrects far too little (the beta.10 bug)")
    check(NoiseMasking.correctionDb(lowRumble, 70.0) == NoiseMasking.correctionDb(lowRumble, 100.0), "noise correction: bands under 100 Hz are not trusted")
    val plain = FloorStaircase(1, refDb = -40.0)
    val corrected = FloorStaircase(1, refDb = -40.0, noiseDb = { hz -> NoiseMasking.correctionDb(office, hz) })
    check(abs(corrected.levelDb(100.0) - (plain.levelDb(100.0) + c100)) < 1e-9, "noise correction: applied to the floor bursts")

    // --- mapping
    val m150 = BassFitMapping.fromFloor(150.0)
    check(m150.hpHz == 100.0 && m150.boundaryHz == 190.0 && m150.outLoHz == 150.0 && m150.tableScale == 1.0,
        "floor 150 Hz gives the S26 Ultra's own values (HP 100, edge 190, out low 150, scale 1)")
    val m200 = BassFitMapping.fromFloor(200.0)
    check(abs(m200.hpHz - 133.33) < 0.01 && abs(m200.boundaryHz - 253.33) < 0.01 && m200.outLoHz == 200.0 &&
        abs(m200.tableScale - 4.0 / 3) < 1e-9, "floor 200 Hz: HP 133, edge 253, out low 200, scale 1.33")
    check(BassFitMapping.fromFloor(500.0).boundaryHz <= 280.0 && BassFitMapping.fromFloor(50.0).tableScale >= 0.75,
        "mapping stays inside the engine's ranges")
    check(BassFitMapping.harmonicOffsets(3.0).let { it[0] == 3.0 && it[1] == -1.0 }, "low-order weight: k=2 +w, others -w/3")

    println("BassFitTest: $passed checks passed")
}

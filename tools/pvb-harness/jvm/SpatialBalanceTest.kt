// Host JVM test of SpatialBalance (spatial "좌우 맞추기" with the phone's microphones): a simulated phone with two
// unequal speakers and two unequal microphones, each mic near one speaker; the cross method must return the speaker
// difference whatever the mics and the distances are. One mic copied to both channels must be flagged.
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import me.timschneeberger.rootlessjamesdsp.pvb.SpatialBalance
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.system.exitProcess

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

/** RBJ peaking filter applied in place (a speaker or mic colouration). */
private fun peaking(x: DoubleArray, sr: Int, f0: Double, q: Double, db: Double) {
    val a = 10.0.pow(db / 40); val w = 2 * PI * f0 / sr; val al = sin(w) / (2 * q); val cw = cos(w); val a0 = 1 + al / a
    val b0 = (1 + al * a) / a0; val b1 = -2 * cw / a0; val b2 = (1 - al * a) / a0; val a1 = -2 * cw / a0; val a2 = (1 - al / a) / a0
    var z1 = 0.0; var z2 = 0.0
    for (i in x.indices) { val y = b0 * x[i] + z1; z1 = b1 * x[i] - a1 * y + z2; z2 = b2 * x[i] - a2 * y; x[i] = y }
}

private data class Quad(val name: String, val gain: Double, val lag: Int, val filtered: Boolean)

private fun delayed(x: DoubleArray, d: Int, g: Double) = DoubleArray(x.size) { if (it >= d) g * x[it - d] else 0.0 }

fun main() {
    val sr = 48000
    val n = (4.5 * sr).toInt()
    val rng = java.util.Random(7)
    fun sweep(kind: DevTestKind): DoubleArray {
        val g = DevTestSignal(); g.set(kind, 55.0)
        val b = FloatArray(2 * n); g.render(b, n, sr)
        val ch = if (kind == DevTestKind.XTC_SWEEP_L) 0 else 1
        return DoubleArray(n) { b[2 * it + ch].toDouble() }
    }
    val sl = sweep(DevTestKind.XTC_SWEEP_L)
    val sr2 = sweep(DevTestKind.XTC_SWEEP_R)
    check("sweeps carry signal", sl.any { abs(it) > 0.05 } && sr2.any { abs(it) > 0.05 })

    // speakers: left (bottom) louder in the mids and 3 dB louder overall; right (earpiece) with a bump at 3 kHz
    fun speakerL(x: DoubleArray) = x.copyOf().also { peaking(it, sr, 800.0, 0.8, 4.0) }.map { it * 1.41 }.toDoubleArray()
    fun speakerR(x: DoubleArray) = x.copyOf().also { peaking(it, sr, 3000.0, 1.0, 2.0) }
    // microphones: different sensitivities and tilts; mic 0 near the left speaker, mic 1 near the right one
    fun mic0(x: DoubleArray) = x.copyOf().also { peaking(it, sr, 5000.0, 0.7, -3.0) }
    fun mic1(x: DoubleArray) = x.copyOf().also { peaking(it, sr, 600.0, 0.7, 2.0) }.map { it * 0.7 }.toDoubleArray()

    fun record(play: DoubleArray, fromLeft: Boolean, oneMic: Boolean = false): SpatialBalance.Recording {
        val near = delayed(play, 2400 + 4, 1.0)      // 50 ms system delay, close
        val far = delayed(play, 2400 + 21, 0.35)     // ~15 cm further, quieter
        val c0 = mic0(if (fromLeft) near else far)
        val c1 = if (oneMic) c0 else mic1(if (fromLeft) far else near)
        val out = FloatArray(2 * n)
        for (i in 0 until n) {
            out[2 * i] = (c0[i] + 1e-4 * rng.nextGaussian()).toFloat()
            out[2 * i + 1] = (c1[i] + 1e-4 * rng.nextGaussian()).toFloat()
        }
        return SpatialBalance.Recording(out, n)
    }
    val noise = SpatialBalance.Recording(FloatArray(2 * n) { (1e-4 * rng.nextGaussian()).toFloat() }, n)
    val pl = speakerL(sl)
    val pr = speakerR(sr2)

    // the truth: left/right speaker difference per band (same filters, measured directly)
    val truthL = SpatialBalance.Recording(FloatArray(2 * n) { pl[it / 2].toFloat() }, n)
    val truthR = SpatialBalance.Recording(FloatArray(2 * n) { pr[it / 2].toFloat() }, n)
    val tl = SpatialBalance.bandPowers(truthL, 0, sr)
    val trr = SpatialBalance.bandPowers(truthR, 0, sr)
    val truth = SpatialBalance.BANDS.indices.map { 10 * kotlin.math.log10(tl[it] / trr[it]) }

    val res = SpatialBalance.analyze(noise, listOf(record(pl, true), record(pl, true)), listOf(record(pr, false), record(pr, false)), sr)
    val err = res.bandsDb.indices.maxOf { abs(res.bandsDb[it] - truth[it]) }
    check("cross method: per-band speaker difference within 0.5 dB (mics and distances cancel)", err < 0.5,
        "max_err=${"%.2f".format(err)} lo=${res.loDb} hi=${res.hiDb}")
    val loTruth = truth.filterIndexed { i, _ -> SpatialBalance.BANDS[i] < SpatialBalance.SPLIT_HZ }.average()
    val hiTruth = truth.filterIndexed { i, _ -> SpatialBalance.BANDS[i] >= SpatialBalance.SPLIT_HZ }.average()
    check("band averages match (half-dB steps)", abs(res.loDb - loTruth) <= 0.3 && abs(res.hiDb - hiTruth) <= 0.3,
        "lo ${res.loDb} vs ${"%.2f".format(loTruth)}, hi ${res.hiDb} vs ${"%.2f".format(hiTruth)}")
    check("distinct microphones recognised, result usable", res.distinctMics && res.usable)

    val mono = SpatialBalance.analyze(noise, listOf(record(pl, true, oneMic = true)), listOf(record(pr, false, oneMic = true)), sr)
    check("one microphone on both channels: flagged", !mono.distinctMics)

    check("two real microphones, steady runs: reliable", res.reliable, "spread=${"%.1f".format(res.micSpreadDb)} repeat=${"%.2f".format(res.repeatDb)}")

    // --- code review 2026-10-23 (F1): one microphone copied with a different gain, a delay or a filter ---
    fun copied(play: DoubleArray, fromLeft: Boolean, gain: Double, lag: Int, filtered: Boolean): SpatialBalance.Recording {
        val heard = mic0(delayed(play, 2400 + if (fromLeft) 4 else 21, if (fromLeft) 1.0 else 0.35))
        val other = delayed(heard, lag, gain).let { if (filtered) it.copyOf().also { x -> peaking(x, sr, 2000.0, 0.7, 4.0) } else it }
        val out = FloatArray(2 * n)
        for (i in 0 until n) {
            out[2 * i] = (heard[i] + 1e-4 * rng.nextGaussian()).toFloat()
            out[2 * i + 1] = (other[i] + 1e-4 * rng.nextGaussian()).toFloat()
        }
        return SpatialBalance.Recording(out, n)
    }
    for ((name, g, lag, f) in listOf(
        Quad("half gain", 0.5, 0, false), Quad("one sample later", 1.0, 1, false),
        Quad("half gain, 20 samples later", 0.5, 20, false), Quad("through a different filter", 0.8, 0, true),
    )) {
        val one = SpatialBalance.analyze(noise, listOf(copied(pl, true, g, lag, f), copied(pl, true, g, lag, f)),
            listOf(copied(pr, false, g, lag, f), copied(pr, false, g, lag, f)), sr)
        check("one microphone copied ($name): not two microphones, not reliable", !one.distinctMics && !one.reliable,
            "spread=${"%.2f".format(one.micSpreadDb)}")
    }
    val reported = SpatialBalance.analyze(noise, listOf(record(pl, true), record(pl, true)),
        listOf(record(pr, false), record(pr, false)), sr, micsReported = 1)
    check("recorder reports one microphone: not two microphones", !reported.distinctMics && !reported.reliable)

    // --- F2: the path assumption. Equal speakers, mirror-asymmetric paths: the bias is the documented term and the
    // recording alone cannot reveal it (the screen therefore always asks to confirm by ear) ---
    fun pathRec(play: DoubleArray, g0: Double, g1: Double): SpatialBalance.Recording {
        val c0 = delayed(play, 2404, g0); val c1 = delayed(play, 2421, g1)
        return SpatialBalance.Recording(FloatArray(2 * n) { i ->
            ((if (i % 2 == 0) c0[i / 2] else c1[i / 2]) + 1e-4 * rng.nextGaussian()).toFloat() }, n)
    }
    val asym = SpatialBalance.analyze(noise, listOf(pathRec(sl, 1.0, 0.2), pathRec(sl, 1.0, 0.2)),
        listOf(pathRec(sr2, 0.4, 1.0), pathRec(sr2, 0.4, 1.0)), sr)
    val expected = 10 * kotlin.math.log10((1.0 * 0.2) / (0.4 * 1.0))
    check("asymmetric paths: bias equals 10*log10(HL0*HL1/(HR0*HR1)) (a known limit, not detectable)",
        abs(asym.loDb - expected) < 0.3 && abs(asym.hiDb - expected) < 0.3, "lo=${asym.loDb} hi=${asym.hiDb} expected=${"%.2f".format(expected)}")

    // repeatability: the second left run 3 dB louder (the phone moved, a noise burst) -> not reliable
    val unsteady = SpatialBalance.analyze(noise, listOf(record(pl, true), record(pl.map { it * 1.41 }.toDoubleArray(), true)),
        listOf(record(pr, false), record(pr, false)), sr)
    check("runs that disagree by 3 dB: not reliable", !unsteady.reliable, "repeat=${"%.2f".format(unsteady.repeatDb)}")

    val silent = SpatialBalance.analyze(noise, listOf(noise), listOf(noise), sr)
    check("nothing played (noise only): not usable, balance 0", !silent.usable && silent.loDb == 0f && silent.hiDb == 0f)

    if (failed > 0) { println("SpatialBalanceTest: $failed failed"); exitProcess(1) }
    println("SpatialBalanceTest: all passed")
}

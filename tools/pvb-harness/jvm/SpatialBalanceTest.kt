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

    val silent = SpatialBalance.analyze(noise, listOf(noise), listOf(noise), sr)
    check("nothing played (noise only): not usable, balance 0", !silent.usable && silent.loDb == 0f && silent.hiDb == 0f)

    if (failed > 0) { println("SpatialBalanceTest: $failed failed"); exitProcess(1) }
    println("SpatialBalanceTest: all passed")
}

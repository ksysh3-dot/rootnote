import me.timschneeberger.rootlessjamesdsp.pvb.PvbMeasureMath
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin
import kotlin.system.exitProcess

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

fun main() {
    val fs = 48000.0
    // a -10 dBFS (peak) 1 kHz sine reads -13 dB (mean square) in the 1 kHz band and the broadband level
    val n = 48000
    val a = Math.pow(10.0, -10.0 / 20)
    val x = FloatArray(n) { (a * sin(2 * PI * 1000 * it / fs)).toFloat() }
    val b = PvbMeasureMath.bandLevels(x, 0, n, fs)
    check("sine level in its band and broadband", abs(b[3] + 13.01) < 0.1 && abs(b[PvbMeasureMath.BROAD] + 13.01) < 0.1 && b[0] < -60,
        "1k=${"%.2f".format(b[3])} broad=${"%.2f".format(b[PvbMeasureMath.BROAD])} 125=${"%.1f".format(b[0])}")

    // band-limited pink noise has unit RMS and equal energy per octave inside its pass band
    val noise = PvbMeasureMath.Noise(fs, 100.0, null, 3)
    val y = FloatArray(4 * n) { noise.next().toFloat() }
    var ms = 0.0
    for (v in y) ms += v.toDouble() * v
    ms /= y.size
    val nb = PvbMeasureMath.bandLevels(y, 0, y.size, fs)
    val oct = nb.copyOfRange(2, 6)   // 500 Hz .. 4 kHz
    check("pink noise: unit RMS, flat per octave (500 Hz - 4 kHz)", abs(PvbMeasureMath.db(ms)) < 0.3 && (oct.maxOrNull()!! - oct.minOrNull()!!) < 1.0,
        "rms_db=${"%.2f".format(PvbMeasureMath.db(ms))} octaves=${oct.joinToString { "%.1f".format(it) }}")

    // staging plan: 3 dB per volume step, compressor with slope 0.5 above -26 dBFS
    val vol = DoubleArray(16) { if (it == 0) Double.NaN else 3.0 * it }
    val p = doubleArrayOf(-34.0, -30.0, -26.0, -22.0, -18.0, -14.0, -10.0)
    val l = DoubleArray(p.size) { if (p[it] <= -26.0) p[it] else -26.0 + 0.5 * (p[it] + 26.0) }
    val plan = PvbMeasureMath.stagePlan(vol, 5, p, l)
    // drop X from -18: loss = 4 (compressed part) + (X - 8) for X > 8 -> X=10 gives 6 dB = 2 steps
    check("stage plan picks 2 steps and 10 dB", plan != null && plan.steps == 2 && abs(plan.outDropDb - 10.0) < 0.15,
        "plan=$plan")
    check("stage plan: none when the base step is unmeasured", PvbMeasureMath.stagePlan(vol, 0, p, l) == null)

    // review F05: one acceptance rule for every point
    val ok = PvbMeasureMath.acceptPoint(true, true, 40.0, 0.5, -30.0)
    check("accept: a good point", ok)
    check("accept: unstable point rejected", !PvbMeasureMath.acceptPoint(false, true, 40.0, 0.5, -30.0))
    check("accept: volume readback mismatch rejected", !PvbMeasureMath.acceptPoint(true, false, 40.0, 0.5, -30.0))
    check("accept: mic peak 0.990 rejected (the -18 dBFS point of the 08:18 measurement)",
        !PvbMeasureMath.acceptPoint(true, true, 47.5, 0.990, -25.2))
    check("accept: low SNR / NaN rejected", !PvbMeasureMath.acceptPoint(true, true, 11.9, 0.5, -30.0) &&
        !PvbMeasureMath.acceptPoint(true, true, Double.NaN, 0.5, -30.0) && !PvbMeasureMath.acceptPoint(true, true, 40.0, 0.5, Double.NaN))
    // the 08:18 measurement without its rejected -18 point: still a usable, rising curve (dip of 0.1 dB tolerated)
    val p818 = doubleArrayOf(-34.0, -30.0, -26.0, -22.0, -14.0, -10.0)
    val l818 = doubleArrayOf(-30.6, -28.7, -27.5, -26.2, -24.9, -25.0)
    check("curve: 08:18 accepted points usable", PvbMeasureMath.curveUsable(p818, l818))
    check("curve: a real dip or unsorted points are not", !PvbMeasureMath.curveUsable(doubleArrayOf(-34.0, -30.0, -26.0),
        doubleArrayOf(-30.0, -31.0, -29.0)) && !PvbMeasureMath.curveUsable(doubleArrayOf(-30.0, -34.0, -26.0), doubleArrayOf(-30.0, -29.0, -28.0)))
    // a plan never extrapolates outside the measured range
    val pShort = doubleArrayOf(-26.0, -22.0, -18.0, -14.0)
    val lShort = DoubleArray(pShort.size) { -26.0 + 0.5 * (pShort[it] + 26.0) }
    check("stage plan: X stays inside the measured curve (from -26 dBFS: X <= 8 dB)", PvbMeasureMath.stagePlan(vol, 5, pShort, lShort) == null ||
        PvbMeasureMath.stagePlan(vol, 5, pShort, lShort)!!.outDropDb <= 8.0 + 1e-9, "plan=${PvbMeasureMath.stagePlan(vol, 5, pShort, lShort)}")
    check("stage check: same volume, same plan, both sides ok, within 0.5 dB",
        PvbMeasureMath.stageCheckOk(5, 5, 2, 2, 10.1, 10.08, true, 0.3) &&
            !PvbMeasureMath.stageCheckOk(6, 5, 2, 2, 10.1, 10.08, true, 0.3) &&
            !PvbMeasureMath.stageCheckOk(5, 5, 3, 2, 10.1, 10.08, true, 0.3) &&
            !PvbMeasureMath.stageCheckOk(5, 5, 2, 2, 10.1, 10.08, false, 0.3) &&
            !PvbMeasureMath.stageCheckOk(5, 5, 2, 2, 10.1, 10.08, true, 0.8) &&
            !PvbMeasureMath.stageCheckOk(5, 5, 2, 2, 10.1, 10.08, true, Double.NaN))
    if (failed > 0) exitProcess(1)
    println("all measurement math checks passed")
}

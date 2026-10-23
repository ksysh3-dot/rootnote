import me.timschneeberger.rootlessjamesdsp.pvb.BassCheck
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.random.Random

// "저음 검사": the analysis on a simulated phone whose answers are known.
// Speaker: 4th-order high-pass at 350 Hz (the -10 dB point re 1 kHz falls between the 254 and 285 Hz steps), a 2nd
// harmonic of 0.035 * (amplitude / -12 dBFS) * (200 Hz / f)^2 (clean, <= -20 dB at -12 dBFS, from the 127 Hz step up),
// 230 ms of output latency, white noise at -70 dBFS on each microphone.

private var failures = 0
private fun check(name: String, ok: Boolean) {
    println("[${if (ok) "PASS" else "FAIL"}] $name")
    if (!ok) failures++
}

private fun hp4(f: Double, fc: Double): Double { val r = (f / fc).pow(4); return r / sqrt(1 + r * r) }

private fun phone(sr: Int, latency: Double, seed: Int, sound: Boolean = true, h2Scale: Double = 0.035): FloatArray {
    val frames = ((BassCheck.DURATION_S + latency + 0.5) * sr).toInt()
    val out = FloatArray(2 * frames)
    val rng = Random(seed)
    for (n in 0 until frames) {
        val t = n.toDouble() / sr - latency
        var v = 0.0
        val st = if (sound) BassCheck.stepAt(t) else null
        if (st != null) {
            val x = t - BassCheck.stepStart(st.index)
            val g = hp4(st.hz, 350.0)
            val a = st.amplitude * g
            val rel = h2Scale * (st.amplitude / 0.25) * (200.0 / st.hz).pow(2)
            val edge = min(1.0, min(x / 0.01, (BassCheck.TONE_S - x) / 0.01))
            v = 0.5 * edge * (a * sin(2 * PI * st.hz * x) + a * rel * sin(2 * PI * 2 * st.hz * x))
        }
        for (ch in 0..1) out[2 * n + ch] = (v + 10.0.pow(-70.0 / 20) * rng.nextGaussian()).toFloat()
    }
    return out
}

private fun Random.nextGaussian(): Double {
    var u = 0.0; var w = 0.0
    while (u == 0.0) u = nextDouble()
    w = nextDouble()
    return sqrt(-2 * kotlin.math.ln(u)) * kotlin.math.cos(2 * PI * w)
}

fun main() {
    val sr = 48000
    check("schedule: 23 frequencies x 3 levels, loudest last, ~39 s",
        BassCheck.STEPS.size == 69 && BassCheck.STEPS.last().levelDb == -12.0 && abs(BassCheck.DURATION_S - 38.95) < 1e-9)
    // the test sound renders exactly the schedule (peak -12 dBFS, silence in the lead)
    val sig = DevTestSignal(); sig.set(DevTestKind.BASS_STEPS, 55.0)
    val buf = FloatArray(2 * (BassCheck.DURATION_S * sr).toInt())
    sig.render(buf, buf.size / 2, sr)
    val leadPeak = (0 until sr).maxOf { abs(buf[2 * it]) }
    val peak = buf.maxOf { abs(it) }
    check("test sound: silent lead, peak -12 dBFS", leadPeak == 0f && abs(peak - 0.2512f) < 0.002f)

    val a = BassCheck.analyze(phone(sr, 0.23, 1).also { }, ((BassCheck.DURATION_S + 0.73) * sr).toInt(), sr)
    println("latency ${a.latencyS} knee ${a.kneeHz} clean ${a.cleanFromHz}")
    check("latency found within 20 ms (0.23 s)", abs(a.latencyS - 0.23) <= 0.02)
    check("usable", a.usable)
    check("knee between the 254 and 285 Hz steps (true -10 dB point ~266 Hz)", a.kneeHz != null && a.kneeHz!! in 280.0..290.0)
    val i1k = BassCheck.FREQS.size - 1
    check("1 kHz response is 0 dB", abs(a.responseDb[i1k]) < 1e-9)
    val i400 = BassCheck.FREQS.indexOfFirst { it > 400 }
    val want400 = 20 * kotlin.math.log10(hp4(BassCheck.FREQS[i400], 350.0) / hp4(1000.0, 350.0))
    check("response at ${BassCheck.FREQS[i400].toInt()} Hz within 0.5 dB of the speaker model", abs(a.responseDb[i400] - want400) < 0.5)
    check("growth -18 -> -12 dBFS is 6 dB where heard", abs(a.growthDb[i400] - 6.0) < 0.3)
    check("clean from the 127 Hz step (2nd harmonic <= -20 dB from there up)", a.cleanFromHz != null && abs(a.cleanFromHz!! - 127.0) < 1.0)
    val i113 = BassCheck.FREQS.indexOfFirst { it > 110 }
    check("113 Hz: harmonic measured at about -19.2 dB (not clean)", abs(a.harmonicsDb[i113] + 19.2) < 0.6 && !a.clean[i113])

    val b = BassCheck.analyze(phone(sr, 0.23, 2), ((BassCheck.DURATION_S + 0.73) * sr).toInt(), sr)
    val agree = BassCheck.agreementDb(a, b)
    check("two passes with different noise agree within 0.3 dB (got $agree)", agree < 0.3)

    val late = BassCheck.analyze(phone(sr, 0.9, 3), ((BassCheck.DURATION_S + 1.4) * sr).toInt(), sr)
    check("a 0.9 s latency is found too", abs(late.latencyS - 0.9) <= 0.02 && late.kneeHz == a.kneeHz)

    val none = BassCheck.analyze(phone(sr, 0.23, 4, sound = false), ((BassCheck.DURATION_S + 0.73) * sr).toInt(), sr)
    check("nothing played: not usable, no knee, no clean range", !none.usable && none.kneeHz == null && none.cleanFromHz == null)

    val dirty = BassCheck.analyze(phone(sr, 0.23, 5, h2Scale = 0.2), ((BassCheck.DURATION_S + 0.73) * sr).toInt(), sr)
    check("more distortion moves the clean range up (got ${dirty.cleanFromHz})", dirty.cleanFromHz != null && dirty.cleanFromHz!! > 250.0)

    val report = BassCheck.report(a, "SM-TEST", agree)
    check("report: header, knee line, 23 rows", report.lines().count { it.firstOrNull()?.isDigit() == true } == 23 && "knee" in report)

    println(if (failures == 0) "BassCheckTest: all checks passed" else "BassCheckTest: $failures FAILED")
    if (failures != 0) kotlin.system.exitProcess(1)
}

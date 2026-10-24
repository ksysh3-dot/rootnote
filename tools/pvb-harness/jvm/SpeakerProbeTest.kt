import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import me.timschneeberger.rootlessjamesdsp.pvb.FitRng
import me.timschneeberger.rootlessjamesdsp.pvb.SpeakerProbe
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log2
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.system.exitProcess

// "마이크가 듣는 값" (SpeakerProbe.kt): a simulated phone speaker and microphone through the probe sweep.

private var passed = 0
private fun check(ok: Boolean, what: String) {
    if (!ok) { println("[FAIL] $what"); exitProcess(1) }
    println("[PASS] $what"); passed++
}

private const val FS = 48000.0

/**
 * The microphone's recording of one probe sweep: speaker = 4th-order high-pass at [fc] (24 dB/oct below), a 2nd
 * harmonic [distDb] under the input, microphone = 1st-order high-pass at [micHz], room noise at -80 dBFS, the sweep
 * starting [latS] after it was asked for, [gainDb] overall (the volume and the microphone's unknown sensitivity).
 */
private fun record(fc: Double, distDb: Double = -35.0, micHz: Double = 80.0, latS: Double = 0.2, gainDb: Double = -6.0,
                   seed: Long = 1): FloatArray {
    val n = ((latS + DevTestSignal.PROBE_SWEEP_S + 0.5) * FS).toInt()
    val r = FitRng(seed)
    val k = ln(DevTestSignal.PROBE_HI_HZ / DevTestSignal.PROBE_LO_HZ)
    val g = 10.0.pow(gainDb / 20)
    val d = 10.0.pow(distDb / 20)
    fun spk(f: Double) = 1 / sqrt(1 + (fc / f).pow(8))
    fun mic(f: Double) = 1 / sqrt(1 + (micHz / f).pow(2))
    return FloatArray(n) { i ->
        val t = i / FS - latS
        val noise = ((r.next() ushr 11).toDouble() / (1L shl 53) * 2 - 1) * 1e-4
        if (t < 0 || t > DevTestSignal.PROBE_SWEEP_S) return@FloatArray noise.toFloat()
        val f = DevTestSignal.PROBE_LO_HZ * exp(k * t / DevTestSignal.PROBE_SWEEP_S)
        val ph = 2 * PI * DevTestSignal.PROBE_LO_HZ * DevTestSignal.PROBE_SWEEP_S / k * (exp(k * t / DevTestSignal.PROBE_SWEEP_S) - 1)
        val a = DevTestSignal.FIT_TONE_AMP * g
        (a * spk(f) * mic(f) * sin(ph) + a * d * mic(2 * f) * sin(2 * ph) + noise).toFloat()
    }
}

fun main() {
    // the speaker's own -10 dB point of a 4th-order high-pass: fc / 9^(1/8)
    for (fc in doubleArrayOf(150.0, 200.0, 260.0)) {
        val want = fc / 9.0.pow(1.0 / 8)
        val p = SpeakerProbe(FS).analyze(record(fc), 0.2)
        val f = p.floorHz()
        check(f != null && abs(log2(f / want)) <= 1.0 / 6 + 1e-9,
            "speaker -10 dB at ${want.toInt()} Hz: microphone reference floor ${f?.toInt()} Hz (within 1/6 octave)")
    }
    run {
        // the volume and the microphone's sensitivity don't matter (ratios only)
        val a = SpeakerProbe(FS).analyze(record(170.0, gainDb = -20.0), 0.2).floorHz()
        val b = SpeakerProbe(FS).analyze(record(170.0, gainDb = -2.0), 0.2).floorHz()
        check(a != null && a == b, "level 18 dB apart: same floor ($a, $b)")
        // a latency 0.3 s off moves it by little (the sweep is slow: 0.4 octave a second)
        val c = SpeakerProbe(FS).analyze(record(170.0, latS = 0.5), 0.2).floorHz()
        check(c != null && abs(log2(c / a!!)) <= 0.25, "latency off by 0.3 s: $c vs $a Hz")
    }
    run {
        // a buzzy speaker: the 2nd harmonic only 14 dB under the input -> below the floor the buzz is louder
        val p = SpeakerProbe(FS).analyze(record(150.0, distDb = -14.0), 0.2)
        val bins = p.bins()
        val lowBuzz = bins.filter { it.hz < 90 }.all { it.verdict == SpeakerProbe.Verdict.BUZZ }
        check(lowBuzz && p.floorHz() != null && p.floorHz()!! > 120, "buzzy speaker: low bins 'buzz only', floor ${p.floorHz()?.toInt()} Hz")
        val clean = SpeakerProbe(FS).analyze(record(150.0), 0.2).bins()
        check(clean.filter { it.hz in 85.0..120.0 }.all { it.verdict == SpeakerProbe.Verdict.WEAK }, "clean speaker (buzz 35 dB down): just below the floor weak, not buzz")
    }
    run {
        val silent = SpeakerProbe(FS).analyze(FloatArray((10 * FS).toInt()), 0.2)
        check(silent.floorHz() == null, "nothing recorded: no floor")
        val loud = record(150.0, gainDb = 20.0)
        val p = SpeakerProbe(FS).analyze(FloatArray(loud.size) { loud[it].coerceIn(-1f, 1f) }, 0.2)
        check(p.clipped && p.floorHz() == null, "clipped recording: flagged, no floor")
    }
    run {
        // live: windows fed one by one update the 'now' values
        val p = SpeakerProbe(FS)
        val x = record(150.0)
        val start = ((0.2 + 5.0) * FS).toInt()
        p.window(x.copyOfRange(start, start + SpeakerProbe.WINDOW), 5.0 + SpeakerProbe.WINDOW / 2 / FS)
        val f = SpeakerProbe.sweepHz(5.0 + SpeakerProbe.WINDOW / 2 / FS)!!
        check(abs(p.nowHz - f) < 1e-6 && p.nowRatioDb > 20, "live: now ${p.nowHz.toInt()} Hz, fundamental ${"%.0f".format(p.nowRatioDb)} dB over its harmonics")
    }
    run {
        // the sweep the app plays is the one analysed
        val g = DevTestSignal(); g.set(DevTestKind.PROBE_SWEEP, 55.0)
        val b = FloatArray(2 * (10 * FS).toInt()); g.render(b, (10 * FS).toInt(), FS.toInt())
        val mono = FloatArray(b.size / 2) { b[2 * it] }
        val p = SpeakerProbe(FS).analyze(mono, 0.0)
        check(p.bins().size == p.centers.size && p.bins().all { abs(it.relDb) < 1.0 && it.verdict == SpeakerProbe.Verdict.PLAYS } &&
            p.floorHz() == p.centers.first(), "the app's own sweep, unfiltered: every bin plays, floor ${p.floorHz()?.toInt()} Hz")
    }
    println("SpeakerProbeTest: $passed checks passed")
}

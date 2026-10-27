import me.timschneeberger.rootlessjamesdsp.pvb.AcousticLab
import kotlin.math.*

fun main() {
    var checks = 0
    fun verify(ok: Boolean, why: String) { check(ok) { why }; checks++ }
    val plan = AcousticLab.plan(20261027)
    verify(plan.size == 48 && plan.toSet().size == 48, "all four models, levels, repeats and controls exactly once")
    verify(plan == AcousticLab.plan(20261027) && plan != AcousticLab.plan(20261028), "seeded replay and independent orders")
    val t = AcousticLab.Trial(11, 0, 0, true)
    val hit = AcousticLab.signal(t)
    val control = AcousticLab.signal(t.copy(impact = false))
    val event = (AcousticLab.EVENT_S * 48000).toInt()
    val end = event + (AcousticLab.IMPACT_END_S * 48000).toInt()
    verify(hit.all { it.isFinite() && abs(it) < 0.95 }, "generated source neither clips nor uses non-finite samples")
    verify((0 until event * 2).all { hit[it] == control[it] }, "impact cannot alter source before the event")
    verify((end * 2 until hit.size).all { hit[it] == control[it] }, "no artificial source tail beyond the declared impact end")
    for (i in plan.indices step 2) verify(plan[i].copy(impact = plan[i+1].impact) == plan[i+1], "adjacent matched pairs")
    for (fs in listOf(44100, 48000)) {
        val source = AcousticLab.signal(t, fs)
        val mono = FloatArray(source.size / 2) { source[it * 2] }
        val start = (AcousticLab.MARKER_S * fs).roundToInt()
        val marker = mono.copyOfRange(start, start + (AcousticLab.MARKER_LENGTH_S * fs).toInt())
        val delay = (0.37 * fs).roundToInt()
        val captured = FloatArray((4.4 * fs).toInt())
        mono.forEachIndexed { n, x -> captured[n + delay] = -x * 0.25f }
        val m = AcousticLab.measure(captured, marker, fs)
        verify(abs(m.markerFrame - start - delay) <= 4, "physical latency/gain/polarity do not move the event")
        verify(m.markerCorrelation > 0.98 && m.complete, "full experiment windows covered")
        verify(m.windowPowers.getValue("attack") > m.windowPowers.getValue("before") * 1.1, "known transient raises the attack energy")
        val c = AcousticLab.measure(captured.copyOf(fs / 2), marker, fs)
        verify(!c.complete && c.recoveryMs == null, "truncation is missing, not zero-energy success")
    }
    val impulse = FloatArray(5000); impulse[2000] = 1f
    val filtered = AcousticLab.band(impulse, 48000)
    verify((0 until 2000).all { filtered[it] == 0f }, "causal measuring filter does not create pre-impact energy")
    val silence = AcousticLab.measure(FloatArray(48000 * 5), FloatArray(1920), 48000)
    verify(silence.markerCorrelation == 0.0 && silence.recoveryMs == null, "silence has no alignment/recovery proof")
    println("AcousticLabTest: $checks checks passed (synthetic input, no device claim)")
}

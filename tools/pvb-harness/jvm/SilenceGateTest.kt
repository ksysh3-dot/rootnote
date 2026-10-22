// Host JVM test of the service's silence pause (battery): when it pauses, when it resumes, what counts as silence.
// (The service processes every block; the gate only decides which processed blocks are written.)
import me.timschneeberger.rootlessjamesdsp.service.SilenceGate
import kotlin.system.exitProcess

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

/** Simulates the loop: one block per entry (true = silent input and output). Returns the block index of each pause
 *  and resume, and which blocks were not written. */
private fun run(gate: SilenceGate, blocks: List<Boolean>, frames: Int, allowed: (Int) -> Boolean = { true }): Triple<List<Int>, List<Int>, List<Int>> {
    val pauses = ArrayList<Int>()
    val resumes = ArrayList<Int>()
    val skipped = ArrayList<Int>()
    var wasPaused = false
    for ((i, silent) in blocks.withIndex()) {
        if (gate.skip(silent, allowed(i))) { skipped += i; continue }
        if (wasPaused) { resumes += i; wasPaused = false }
        if (gate.afterBlock(silent, frames, allowed(i))) { pauses += i; wasPaused = true }
    }
    return Triple(pauses, resumes, skipped)
}

fun main() {
    val rate = 48000
    val frames = 4096                      // the default block (8192 samples)
    val hold = (SilenceGate.HOLD_SECONDS * rate).toLong()
    val blocksToPause = ((hold + frames - 1) / frames).toInt()   // 24 blocks = 2.05 s

    // 1. Music, then silence: pauses once, exactly when 2 s of silence have been processed and played.
    run {
        val g = SilenceGate.forRate(rate)
        val blocks = List(10) { false } + List(60) { true }
        val (p, r, s) = run(g, blocks, frames)
        check("pauses once after the hold", p == listOf(10 + blocksToPause - 1), "pauses=$p")
        check("no resume while silent", r.isEmpty())
        check("silent blocks after the pause are not written", s == (10 + blocksToPause until 70).toList(), "skipped=${s.size}")
        check("hold is at least 2 s", blocksToPause.toLong() * frames >= hold && (blocksToPause - 1).toLong() * frames < hold)
    }
    // 2. Sound comes back: the first sounding block resumes and is processed; a new silence needs the full hold.
    run {
        val g = SilenceGate.forRate(rate)
        val blocks = List(30) { true } + List(3) { false } + List(30) { true }
        val (p, r, s) = run(g, blocks, frames)
        check("pause, resume on the first sound, pause again", p == listOf(blocksToPause - 1, 33 + blocksToPause - 1) && r == listOf(30), "p=$p r=$r")
        check("the sounding blocks are always written", s.none { it in 30..32 })
    }
    // 3. Gaps shorter than the hold (between songs) never pause.
    run {
        val g = SilenceGate.forRate(rate)
        val blocks = ArrayList<Boolean>()
        repeat(20) { blocks += List(5) { false }; blocks += List(blocksToPause - 1) { true } }
        val (p, _, _) = run(g, blocks, frames)
        check("short gaps never pause", p.isEmpty(), "p=$p")
    }
    // 4. Not allowed (research mode, test sound, power save off): never pauses; becoming not allowed resumes.
    run {
        val g = SilenceGate.forRate(rate)
        val (p, _, _) = run(g, List(100) { true }, frames) { false }
        check("never pauses while not allowed", p.isEmpty())
        val g2 = SilenceGate.forRate(rate)
        val (p2, r2, s2) = run(g2, List(60) { true }, frames) { it < 40 }
        check("resumes when pausing stops being allowed", p2 == listOf(blocksToPause - 1) && r2 == listOf(40) && s2.max() == 39, "p=$p2 r=$r2")
    }
    // 5. What counts as silence.
    run {
        val f = FloatArray(8192)
        check("zeros are silent", SilenceGate.isSilent(f, f.size))
        f[100] = 1f / 32768f; f[200] = -1f / 32768f
        check("one 16-bit step is silent", SilenceGate.isSilent(f, f.size))
        f[300] = 1.01f / 32768f
        check("more than one step is not", !SilenceGate.isSilent(f, f.size))
        check("only the first n samples count", SilenceGate.isSilent(f, 300))
        f[300] = Float.NaN
        check("NaN is not silent", !SilenceGate.isSilent(f, f.size))
        val sh = ShortArray(8192)
        sh[5] = 1; sh[6] = -1
        check("short: +-1 is silent", SilenceGate.isSilent(sh, sh.size))
        sh[7] = 2
        check("short: 2 is not", !SilenceGate.isSilent(sh, sh.size))
    }
    // 6. reset() forgets a pause (the track was stopped or rebuilt by someone else).
    run {
        val g = SilenceGate.forRate(rate)
        run(g, List(30) { true }, frames)
        check("paused before reset", g.paused)
        g.reset()
        check("reset clears the pause", !g.paused && !g.skip(true, true))
    }
    if (failed > 0) {
        println("SilenceGateTest: $failed failed")
        exitProcess(1)
    }
    println("SilenceGateTest: all passed")
}

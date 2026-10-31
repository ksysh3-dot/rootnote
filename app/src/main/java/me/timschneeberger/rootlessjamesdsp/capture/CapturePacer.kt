package me.timschneeberger.rootlessjamesdsp.capture

/**
 * Holds unpaced capture reads to real time. With "가로채기" the captured players are consumed at the pace the
 * capture is read; normally the blocking output write sets that pace, but while the output rests (silence gate)
 * nothing does, and the players would run fast. [afterRead] returns how long to wait so that the frames read since
 * the first unpaced read take their real duration; [reset] when the output plays again.
 *
 * Pure Kotlin (no Android types): host-tested in tools/pvb-harness/jvm/CapturePacerTest.kt.
 */
class CapturePacer(private val sampleRate: Int) {
    private var startNs = 0L
    private var frames = 0L
    private var running = false

    /** [read] frames were just read at [nowNs] (a monotonic clock); returns the nanoseconds to wait (0 = none). */
    fun afterRead(read: Int, nowNs: Long): Long {
        if (!running) { running = true; startNs = nowNs; frames = 0 }
        frames += read
        val due = startNs + frames * 1_000_000_000L / sampleRate
        val wait = due - nowNs
        // far behind (the thread was held up): start again from now rather than reading the backlog at full speed
        if (wait < -MAX_BEHIND_NS) { startNs = nowNs; frames = 0; return 0 }
        return if (wait > 0) minOf(wait, MAX_WAIT_NS) else 0
    }

    fun reset() { running = false }

    companion object {
        const val MAX_BEHIND_NS = 500_000_000L
        const val MAX_WAIT_NS = 200_000_000L
    }
}

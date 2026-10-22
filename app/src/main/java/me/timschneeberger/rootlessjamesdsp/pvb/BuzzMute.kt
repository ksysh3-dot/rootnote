package me.timschneeberger.rootlessjamesdsp.pvb

/** One control thread. Every mute expires independently of audio callbacks and export completion. */
class BuzzMute(
    private val now: () -> Long,
    private val post: (Runnable, Long) -> Unit,
    private val apply: (Float) -> Unit,
) {
    private var rampToken = 0
    private var session = 0
    private var target = 1f
    private var value = 1f
    var startedAt = 0L; private set
    var restoreRequestedAt = 0L; private set

    fun begin() {
        val token = ++session
        startedAt = now(); restoreRequestedAt = 0
        fade(0f, 40)
        post(Runnable { if (token == session) restore() }, 5000)
    }

    fun restore() {
        ++session
        if (restoreRequestedAt == 0L) restoreRequestedAt = now()
        // Repeated stop/poll calls must not restart and indefinitely stretch the recovery fade.
        if (target == 1f) return
        fade(1f, 100)
    }

    private fun fade(to: Float, duration: Long) {
        target = to
        val token = ++rampToken
        val from = value; val start = now()
        val ramp = object : Runnable {
            override fun run() {
                if (token != rampToken) return
                val t = ((now() - start).toFloat() / duration).coerceIn(0f, 1f)
                value = from + (to - from) * t
                apply(value)
                if (t < 1f) post(this, 10)
            }
        }
        post(ramp, 0)
    }
}

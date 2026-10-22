import me.timschneeberger.rootlessjamesdsp.pvb.BuzzMute
import java.util.PriorityQueue

private class Clock {
    var now = 100L
    var value = 1f
    private var order = 0
    private class Task(val at: Long, val order: Int, val run: Runnable)
    private val tasks = PriorityQueue<Task>(compareBy<Task> { it.at }.thenBy { it.order })
    val mute = BuzzMute({ now }, { task, delay -> tasks.add(Task(now + delay, order++, task)); Unit }, { value = it })
    fun advance(ms: Long) {
        val end = now + ms
        while (tasks.isNotEmpty() && tasks.peek().at <= end) {
            val t = tasks.poll(); now = t.at; t.run.run()
            check(value in 0f..1f)
        }
        now = end
    }
}

fun main() {
    val c = Clock()
    c.mute.begin(); c.advance(20); check(c.value in 0.49f..0.51f)
    c.advance(20); check(c.value == 0f)
    c.advance(4959); check(c.value == 0f)
    c.advance(1); c.advance(100); check(c.value == 1f) { "wall watchdog failed without audio" }
    check(c.mute.restoreRequestedAt - c.mute.startedAt == 5000L)
    val early = Clock()
    early.mute.begin(); early.advance(40); early.mute.restore()
    repeat(10) { early.advance(10); early.mute.restore() }
    check(early.value == 1f) { "repeated stop restarted fade" }
    early.advance(6000); check(early.value == 1f)
    val restart = Clock()
    restart.mute.begin(); restart.advance(20); restart.mute.restore(); restart.advance(20)
    restart.mute.begin(); restart.advance(40); check(restart.value == 0f)
    restart.advance(4950); check(restart.value == 0f) { "stale previous watchdog ended new mute" }
    restart.advance(110); check(restart.value == 1f)
    val immediate = Clock()
    immediate.mute.begin(); immediate.mute.restore(); immediate.advance(6000)
    check(immediate.value == 1f) { "queued fade ran after cancellation" }
    println("BuzzMute: 5s watchdog, fade, early stop, repeated restore and stale-callback cancellation passed")
}

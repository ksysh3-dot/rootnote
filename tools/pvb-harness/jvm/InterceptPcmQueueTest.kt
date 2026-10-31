import me.timschneeberger.rootlessjamesdsp.capture.InterceptPcmQueue
import kotlin.concurrent.thread
import kotlin.system.exitProcess

private var failures = 0
private fun checkCase(name: String, ok: Boolean) {
    println("[${if (ok) "PASS" else "FAIL"}] $name")
    if (!ok) failures++
}

private fun frames(vararg values: Int): ByteArray = ByteArray(values.size * 4).also { a ->
    values.forEachIndexed { i, v ->
        val l = v.toShort().toInt()
        val r = (-v).toShort().toInt()
        a[i * 4] = l.toByte(); a[i * 4 + 1] = (l shr 8).toByte()
        a[i * 4 + 2] = r.toByte(); a[i * 4 + 3] = (r shr 8).toByte()
    }
}

fun main() {
    val q = InterceptPcmQueue(3)
    q.start()
    val bytes = frames(1, 2, 3, 4, 5)
    // Arbitrary pipe boundaries, including half samples and split stereo frames.
    for (i in bytes.indices) q.offer(bytes, i, 1)
    val data = ShortArray(8)
    val n = q.read(data, 0, 8)
    checkCase("overflow drops only old complete stereo frames", n == 6 && data.take(n) == listOf<Short>(3, -3, 4, -4, 5, -5) && q.droppedFrames == 2L)

    // Drain-and-restart never replays stale samples or swaps the stereo channels.
    q.stop()
    q.offer(frames(10, 11), 0, 8)
    checkCase("stopped queue returns promptly", q.read(data, 0, 8) == 0)
    q.start()
    q.offer(frames(12), 0, 4)
    checkCase("restart keeps only fresh PCM", q.read(data, 0, 7) == 2 && data[0] == 12.toShort() && data[1] == (-12).toShort())
    q.offer(frames(13, 14), 0, 8)
    val floats = FloatArray(8)
    checkCase("float output is normalized and always stereo-aligned", q.read(floats, 1, 6) == 4 &&
        floats[1] == 13 / 32768f && floats[2] == -13 / 32768f && floats[3] == 14 / 32768f)

    val blocked = InterceptPcmQueue(8)
    blocked.start()
    var answer = Int.MIN_VALUE
    val reader = thread { answer = blocked.read(ShortArray(4), 0, 4) }
    Thread.sleep(30)
    checkCase("empty live queue blocks instead of returning fictitious silence", reader.isAlive)
    blocked.offer(frames(7), 0, 4)
    reader.join(1000)
    checkCase("producer wakes reader with a real partial read", !reader.isAlive && answer == 2)

    val shutdown = InterceptPcmQueue(8)
    shutdown.start()
    var eof = 0
    val waiter = thread { eof = shutdown.read(ShortArray(8), 0, 8) }
    Thread.sleep(20)
    shutdown.close()
    waiter.join(1000)
    checkCase("close unblocks waiting read with EOF", !waiter.isAlive && eof == -1)

    // Stress repeated wraparound, partial pipe chunks, and queue/consumer asymmetry.
    val stress = InterceptPcmQueue(16)
    stress.start()
    var stereoOk = true
    for (i in 0 until 1000) {
        val incoming = frames(i, i + 1)
        stress.offer(incoming, 0, 3)
        stress.offer(incoming, 3, 5)
        val received = ShortArray(4)
        stereoOk = stereoOk && stress.read(received, 0, 4) == 4 &&
            received.contentEquals(shortArrayOf(i.toShort(), (-i).toShort(), (i+1).toShort(), (-(i+1)).toShort()))
    }
    checkCase("1000 consecutive fragment and ring-wrap cycles preserve stereo order", stereoOk)
    if (failures > 0) exitProcess(1)
    println("all intercept PCM queue tests passed")
}

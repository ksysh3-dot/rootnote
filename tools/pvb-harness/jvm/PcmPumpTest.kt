// Host JVM test of the service's read/process/write arithmetic (review F01) with fake partial reads and writes.
import me.timschneeberger.rootlessjamesdsp.service.PcmPump
import kotlin.random.Random
import kotlin.system.exitProcess

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

/** Source of a numbered sample stream that returns short reads, 0 and errors at random. */
private class FakeRecord(val rnd: Random, val total: Int) {
    var next = 0
    fun read(buf: FloatArray, off: Int, len: Int): Int {
        when (rnd.nextInt(10)) {
            0 -> return 0
            1 -> return -6       // ERROR_DEAD_OBJECT
            2 -> return -3       // ERROR_INVALID_OPERATION
        }
        val n = minOf(len, 1 + rnd.nextInt(len), total - next)
        if (n <= 0) return 0
        for (i in 0 until n) buf[off + i] = (next + i).toFloat()
        next += n
        return n
    }
}

/** Sink that takes random partial writes, sometimes nothing, sometimes fails. */
private class FakeTrack(val rnd: Random, val failEvery: Int) {
    val got = ArrayList<Float>()
    var calls = 0
    fun write(buf: FloatArray, off: Int, len: Int): Int {
        calls++
        if (failEvery > 0 && calls % failEvery == 0) return -6
        if (rnd.nextInt(8) == 0) return 0
        val n = 1 + rnd.nextInt(len)
        for (i in 0 until n) got.add(buf[off + i])
        return n
    }
}

fun main() {
    // The worker loop's arithmetic: read after the carry, process whole frames, write all, keep the odd sample.
    for (seed in 0 until 20) {
        val rnd = Random(seed)
        val src = FakeRecord(rnd, 200_000)
        val dst = FakeTrack(rnd, failEvery = 0)
        val bufSize = 1 + rnd.nextInt(5000)
        val inBuf = FloatArray(bufSize)
        val outBuf = FloatArray(bufSize)
        var carry = 0
        var guard = 0
        var shortWrites = 0
        while (src.next < src.total && guard++ < 10_000_000) {
            val got = src.read(inBuf, carry, bufSize - carry)
            if (got <= 0) continue                       // never reprocess an old buffer
            val total = carry + got
            val samples = PcmPump.wholeFrames(carry, got)
            for (i in 0 until samples) outBuf[i] = inBuf[i]   // "processing"
            val w = PcmPump.writeAll(samples, 1_000_000, { false }) { off, len -> dst.write(outBuf, off, len) }
            if (w != samples) shortWrites++
            carry = PcmPump.keepCarry(inBuf, total, samples)
        }
        val ok = shortWrites == 0 && dst.got.size >= src.total - 1 && dst.got.size % 2 == 0 &&
            dst.got.withIndex().all { (i, v) -> v == i.toFloat() }
        if (!ok || seed == 19) {
            check("random short reads, 0, errors, partial writes (20 runs): every sample read is played once, in order, " +
                "in whole frames", ok, "last: buffer $bufSize, played ${dst.got.size} of ${src.total}")
        }
    }
    // Errors on write: the failing write returns its code and the samples already written stay written.
    run {
        val rnd = Random(99)
        val dst = FakeTrack(rnd, failEvery = 3)
        val buf = FloatArray(1000) { it.toFloat() }
        val r = PcmPump.writeAll(1000, 3, { false }) { off, len -> dst.write(buf, off, len) }
        check("write error code returned, earlier samples kept in order", r == -6 &&
            dst.got.withIndex().all { (i, v) -> v == i.toFloat() }, "r=$r written=${dst.got.size}")
    }
    // Stop: writeAll returns at once.
    run {
        var calls = 0
        val r = PcmPump.writeAll(1000, 3, { calls > 2 }) { _, len -> calls++; minOf(len, 10) }
        check("stop ends a blocking write loop", r == 30 && calls == 3, "r=$r calls=$calls")
    }
    // Zero-length writes (track paused) do not spin forever.
    run {
        var calls = 0
        val r = PcmPump.writeAll(100, 3, { false }) { _, _ -> calls++; 0 }
        check("repeated empty writes drop the block", r == 0 && calls == 4, "calls=$calls")
    }
    check("odd counts: whole frames only", PcmPump.wholeFrames(0, 5) == 4 && PcmPump.wholeFrames(1, 5) == 6 &&
        PcmPump.wholeFrames(1, 0) == 0)
    if (failed > 0) exitProcess(1)
    println("all PCM pump checks passed")
}

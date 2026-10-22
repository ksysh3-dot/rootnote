import me.timschneeberger.rootlessjamesdsp.pvb.BuzzRing
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzWav
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicReference

private fun fill(r: BuzzRing, frames: Int, base: Long = r.recordedFrames) {
    val src = FloatArray(frames * 2) { i -> (base * 2 + i).toFloat() }
    val dst = FloatArray(frames * 2) { i -> -src[i] - 0.5f }
    r.recordFloat(src, dst, src.size, null, 7130, 3, 0.5f, true)
    check(src[0] == (base * 2).toFloat() && dst[0] == -src[0] - 0.5f) { "capture mutated buffers" }
}

fun main() {
    val sr = 8000
    // Long-running rolling history, exact 5 s before/3 s after, and events near the clip rather than startup.
    val r = BuzzRing(sr).apply { armed = true }
    repeat(5000) { fill(r, 800) }
    val marker = r.recordedFrames
    check(r.trigger()); check(!r.trigger())
    repeat(31) { fill(r, 800) }
    check(r.frozen)
    val w = r.window()
    check(w.trigger == marker && w.start == marker - 5 * sr && w.end == marker + 3 * sr)
    check(w.complete && w.reason == "complete" && !w.timelineTruncated)
    for (f in w.start until w.end step 137) {
        check(r.sample(f, 0, false) == (f * 2).toFloat())
        check(r.sample(f, 1, true) == -(f * 2 + 1).toFloat() - 0.5f)
    }
    var events = 0; var previous = -1L
    r.forEachEvent { f, _, _, _, _, _ -> check(f > previous); previous = f; ++events }
    check(events in 1..4096)
    val before = r.sample(w.start, 0, false)
    fill(r, 400)
    check(r.sample(w.start, 0, false) == before) { "frozen export changed" }

    // WAV header sizes/format and stereo float bits, including values beyond full-scale.
    val wav = ByteArrayOutputStream(); BuzzWav.write(wav, r, false)
    val bytes = wav.toByteArray(); val b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    check(String(bytes, 0, 4) == "RIFF" && b.getInt(4) == bytes.size - 8)
    check(b.getShort(20).toInt() == 3 && b.getShort(22).toInt() == 2)
    check(b.getInt(24) == sr && b.getShort(34).toInt() == 32)
    check(String(bytes, 36, 4) == "fact" && b.getInt(44) == w.frames)
    check(String(bytes, 48, 4) == "data" && b.getInt(52) == w.frames * 8)
    check(b.getFloat(56) == before && bytes.size == 56 + w.frames * 8)

    // Export gaps cannot be stitched back into a later report; short pre-roll is explicit.
    r.release(); fill(r, 800, 0)
    check(r.recordedFrames == 800L && r.trigger())
    fill(r, 800)
    r.finish("wall_timeout")
    check(r.frozen && !r.window().complete && r.window().start == 0L)
    check(r.window().trigger == 800L && r.window().reason == "wall_timeout")

    // Exact PCM16 normalization; diagnostic capture never replaces output with the muted signal.
    val s = BuzzRing(sr).apply { armed = true }
    val ins = shortArrayOf(Short.MIN_VALUE, Short.MAX_VALUE, 0, -16384)
    val outs = shortArrayOf(123, -456, 10000, -10000)
    s.recordShort(ins, outs, 4, null, -1, -1, Float.NaN, false)
    s.finish("stop")
    check(s.sample(0, 0, false) == -1f && s.sample(0, 1, false) == 32767f / 32768)
    check(s.sample(1, 0, true) == 10000f / 32768 && outs[0] == 123.toShort())

    // Optional microphone is native mono, not duplicated stereo; its clock/window stays independent.
    val mic = BuzzRing(sr, channels = 1, paired = false).apply { armed = true }
    mic.recordShort(ins, ins, 4, null, -1, -1, Float.NaN, false)
    check(mic.trigger()); mic.finish("mic_stop")
    val micBytes = ByteArrayOutputStream().apply { BuzzWav.write(this, mic, false) }.toByteArray()
    val mb = ByteBuffer.wrap(micBytes).order(ByteOrder.LITTLE_ENDIAN)
    check(mb.getShort(22).toInt() == 1 && mb.getInt(28) == sr * 4 && mb.getInt(52) == 4 * 4)
    check(mb.getFloat(56) == -1f && mb.getFloat(68) == -0.5f)

    // Trigger without another block: retain useful pre-roll and mark it incomplete.
    val idle = BuzzRing(sr).apply { armed = true }
    fill(idle, 1000); check(idle.trigger()); idle.finish("idle")
    check(idle.window().trigger == 1000L && idle.window().end == 1000L && !idle.window().complete)

    // Trigger before the first audio callback; no stale memory in initial history.
    val first = BuzzRing(sr).apply { armed = true }
    check(first.trigger()); fill(first, 800)
    first.armed = false; fill(first, 800)
    check(first.frozen && first.window().trigger == 0L && first.window().end == 800L)

    // Concurrent stop/export: once frozen, frames are immutable even if the writer is still called.
    repeat(25) {
        val c = BuzzRing(sr).apply { armed = true }
        val start = CountDownLatch(1); val error = AtomicReference<Throwable?>()
        val t = Thread {
            try { start.await(); repeat(100) { fill(c, 400) } } catch (e: Throwable) { error.set(e) }
        }
        t.start(); start.countDown(); c.finish("concurrent_stop")
        t.join(); error.get()?.let { throw it }
        check(c.frozen)
        val window = c.window(); val out = ByteArrayOutputStream()
        BuzzWav.write(out, c, true)
        check(out.size() == 56 + window.frames * 8)
        check(c.recordedFrames == window.end)
    }
    // Detailed stems and block trace use the SAME ring freeze/window, including wrap and a partial last block.
    val detail = BuzzRing(8000, detailed = true).apply { armed = true }
    val trace = FloatArray(BuzzRing.DETAIL_FIELDS)
    val a = FloatArray(800); val detailOutput = FloatArray(800); val layer = FloatArray(800); val full = FloatArray(800)
    var frame = 0L
    repeat(460) { block ->
        if (block == 400) check(detail.trigger())
        for (j in a.indices) { a[j] = (frame * 2 + j).toFloat(); detailOutput[j] = -a[j]; layer[j] = a[j] * 2; full[j] = a[j] * 3 }
        trace.fill(block.toFloat()); trace[0] = 1f
        detail.recordFloat(a,detailOutput,a.size,null,7140,5,1f,true,layer,full,trace,block.toLong()*50000000)
        frame += 400
    }
    check(detail.frozen && detail.window().frames == 64000 && !detail.detailTruncated())
    val dw = detail.window()
    for (f in dw.start until dw.end step 173) {
        check(detail.diagnosticSample(f, 0, 1) == detail.sample(f, 0, false)*2)
        check(detail.diagnosticSample(f, 1, 2) == detail.sample(f, 1, false)*3)
    }
    trace.fill(-999f) // ring must own each historical trace, not aliases to this reusable array
    var covered = 0L
    detail.forEachDetail { f, n, elapsed, values, offset ->
        if (f < dw.end && f+n > dw.start) {
            check(values[offset] == 1f && values[offset+1] == (f/400).toFloat())
            check(elapsed == (f/400)*50000000)
            covered += minOf(f+n,dw.end)-maxOf(f,dw.start)
        }
    }
    check(covered == dw.frames.toLong())
    val stem = java.io.ByteArrayOutputStream(); BuzzWav.write(stem, detail, false, 1)
    val stemBytes = java.nio.ByteBuffer.wrap(stem.toByteArray()).order(java.nio.ByteOrder.LITTLE_ENDIAN)
    check(stemBytes.getFloat(56) == detail.diagnosticSample(dw.start,0,1))
    val missing = BuzzRing(8000,detailed=true).apply { armed = true }
    missing.recordShort(shortArrayOf(10,20),shortArrayOf(30,40),2,null,-1,-1,0f,false)
    missing.finish("unavailable")
    check(missing.diagnosticSample(0,0,1).isNaN())
    missing.forEachDetail { _,_,_,v,o -> check(v[o] == 0f && v[o+1].isNaN()) }
    println("Detailed diagnostics: aligned stems, wrap, owned block timeline, complete coverage and unavailable markers passed")
    println("BuzzRing/WAV: rolling pre/post, wrap, freeze race, partial stop, PCM16 and float WAV passed")
}

// Host JVM test of the real Kotlin wrapper (PvbNative.kt, PvbEngine.kt, VolumeCompensation.kt) against the
// host build of libpvbengine.so. Run with run_jvm_test.sh.
import me.timschneeberger.rootlessjamesdsp.pvb.PvbAnaInfo
import me.timschneeberger.rootlessjamesdsp.pvb.PvbEngine
import me.timschneeberger.rootlessjamesdsp.pvb.PvbMeter
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeCompensation
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import kotlin.random.Random
import kotlin.system.exitProcess

var failures = 0
fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name ${if (info.isNotEmpty()) "($info)" else ""}")
    if (!ok) failures++
}

fun main(args: Array<String>) {
    val outFile = File(args.getOrElse(0) { "jni_out.f32" })
    val sr = 48000
    val e = PvbEngine(sr)
    check("engine created", e.isValid)
    check("latency 88 frames at 48 kHz", e.latencyFrames == 88, "${e.latencyFrames}")

    // Deterministic noise, 10 blocks of 4096 frames, default parameters (EQ v1.1, -5 dB, -1 dBTP).
    val rnd = Random(42)
    val frames = 4096
    val all = FloatArray(10 * frames * 2)
    for (i in all.indices) all[i] = (rnd.nextFloat() * 2f - 1f) * 0.3f
    all.copyOf().let { input ->
        val out = FloatArray(all.size)
        val inBlock = FloatArray(frames * 2)
        val outBlock = FloatArray(frames * 2)
        for (b in 0 until 10) {
            System.arraycopy(input, b * frames * 2, inBlock, 0, frames * 2)
            e.processFloat(inBlock, outBlock)
            System.arraycopy(outBlock, 0, out, b * frames * 2, frames * 2)
        }
        fun save(f: File, a: FloatArray) {
            val bb = ByteBuffer.allocate(a.size * 4).order(ByteOrder.LITTLE_ENDIAN)
            a.forEach { bb.putFloat(it) }
            f.writeBytes(bb.array())
        }
        save(outFile, out)
        save(File(outFile.path + ".in"), input)
        check("output finite", out.all { it.isFinite() })

        // Analysis right after the same audio, raw values (dt 10 s); compare_jni.py repeats it in C.
        val n = 240
        val a = Array(4) { FloatArray(n) }
        val info = FloatArray(PvbAnaInfo.COUNT)
        val ok = e.analyze(a[0], a[1], a[2], a[3], info, 10.0)
        save(File(outFile.path + ".ana"), a[0] + a[1] + a[2] + a[3] + info)
        check("analysis runs", ok && info[PvbAnaInfo.FRESH] == 1f && a[3].all { it.isFinite() },
            "eq@220=${a[3][(0 until n).minByOrNull { abs(PvbAnaInfo.pointHz(it, n) - 220f) }!!]}")
        check("analysis rejects mismatched arrays", !e.analyze(FloatArray(10), FloatArray(9), FloatArray(10), FloatArray(10), info))
    }

    val m = FloatArray(PvbMeter.COUNT)
    check("meters readable", e.readMeters(m) && m[PvbMeter.SAMPLE_RATE] == 48000f && m[PvbMeter.MIX] == 1f,
        "rate=${m[PvbMeter.SAMPLE_RATE]} mix=${m[PvbMeter.MIX]} load=${m[PvbMeter.LOAD_PCT]}%")

    // Odd length: the trailing sample passes through untouched.
    val odd = FloatArray(4097) { 0.25f }
    val oddOut = FloatArray(4097)
    e.processFloat(odd, oddOut, odd.size)
    check("odd length keeps the last sample", oddOut[4096] == 0.25f)

    // Length shorter than the array: the rest of the output array is not touched.
    val part = FloatArray(1000) { 0.1f }
    val partOut = FloatArray(1000) { 7f }
    e.processFloat(part, partOut, 500)
    check("partial length leaves the rest alone", partOut[499] != 7f && partOut[500] == 7f)

    // 16-bit path.
    val si = ShortArray(8192) { ((it % 200) * 100 - 10000).toShort() }
    val so = ShortArray(8192)
    e.processShort(si, so)
    check("16-bit path runs", so.any { it.toInt() != 0 })

    // Parameter array size is enforced on the Kotlin side.
    val bad = try { e.setParams(FloatArray(3)); false } catch (_: IllegalArgumentException) { true }
    check("wrong parameter count rejected", bad)
    val p = PvbEngine.defaultParams()
    p[PvbParam.LOW_DB] = 6f
    e.setParams(p)
    e.processFloat(FloatArray(8192), FloatArray(8192))
    e.readMeters(m)
    check("parameter reaches the engine", abs(m[PvbMeter.LOW_DB_NOW] - 6f) < 1e-4, "low=${m[PvbMeter.LOW_DB_NOW]}")

    // After close the wrapper passes audio through (handle 0) instead of crashing.
    e.close()
    val pin = FloatArray(16) { it * 0.01f }
    val pout = FloatArray(16)
    e.processFloat(pin, pout)
    check("closed engine passes through", pin.contentEquals(pout) && !e.isValid)
    check("closed engine: other calls do nothing", !e.readMeters(m) && e.latencyFrames == 0 && e.openMs(0) == -1)

    // Lifetime (review F02): close while other threads keep processing, analysing and setting parameters. The native
    // engine must be freed only after the last call returns; a use-after-free would crash the JVM here.
    var lifetimeOk = true
    var calls = 0L
    for (round in 0 until 30) {
        val eng = PvbEngine(48000)
        val stop = java.util.concurrent.atomic.AtomicBoolean(false)
        val counter = java.util.concurrent.atomic.AtomicLong(0)
        val workers = (0 until 4).map { w ->
            Thread {
                val a = FloatArray(4096) { (it % 64) * 0.003f }
                val b = FloatArray(4096)
                val arrs = Array(4) { FloatArray(64) }
                val info = FloatArray(PvbAnaInfo.COUNT)
                val mm = FloatArray(PvbMeter.COUNT)
                while (!stop.get()) {
                    when (w) {
                        0 -> eng.processFloat(a, b)
                        1 -> eng.analyze(arrs[0], arrs[1], arrs[2], arrs[3], info, 10.0)
                        2 -> { eng.readMeters(mm); eng.openMs(0) }
                        else -> eng.setParams(PvbEngine.defaultParams())
                    }
                    counter.incrementAndGet()
                }
            }.also { it.start() }
        }
        Thread.sleep(3L + round % 5)
        eng.close()
        Thread.sleep(3)
        stop.set(true)
        workers.forEach { it.join() }
        calls += counter.get()
        lifetimeOk = lifetimeOk && !eng.isValid
        val pa = FloatArray(8) { 0.5f }
        val pb = FloatArray(8)
        eng.processFloat(pa, pb)
        lifetimeOk = lifetimeOk && pa.contentEquals(pb)
    }
    check("close while 4 threads use the engine (30 rounds): no crash, passes through after", lifetimeOk, "calls=$calls")

    // Volume rule.
    check("vol: reference volume keeps the base gain", VolumeCompensation.lowGainDb(3f, 0f, 17f, 0.19f, 6f, 1f) == 3f)
    check("vol: 10 dB quieter adds 1.9 dB", abs(VolumeCompensation.lowGainDb(3f, 10f, 17f, 0.19f, 6f, 1f) - 4.9f) < 1e-5)
    check("vol: cap at +6 dB", VolumeCompensation.lowGainDb(3f, 40f, 17f, 0.19f, 6f, 1f) == 6f)
    check("vol: max volume goes to +1 dB", abs(VolumeCompensation.lowGainDb(3f, -17f, 17f, 0.19f, 6f, 1f) - 1f) < 1e-5)
    check("vol: halfway up goes halfway", abs(VolumeCompensation.lowGainDb(3f, -8.5f, 17f, 0.19f, 6f, 1f) - 2f) < 1e-5)
    check("vol: NaN drop keeps base", VolumeCompensation.lowGainDb(3f, Float.NaN, 17f, 0.19f, 6f, 1f) == 3f)
    check("vol: fallback curve", abs(VolumeCompensation.fallbackDb(0.4f) - (-22.5f)) < 1e-4 && VolumeCompensation.fallbackDb(1f) == 0f)

    println(if (failures == 0) "all JVM checks passed" else "$failures JVM check(s) failed")
    exitProcess(if (failures == 0) 0 else 1)
}

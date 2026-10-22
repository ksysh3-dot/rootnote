import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

fun main(args: Array<String>) {
    val dest = File(args.single()).apply { mkdirs() }
    for (fs in listOf(44100, 48000)) for (model in PvbModels.models) {
        PvbEngine(fs).use { e ->
            val p = PvbEngine.defaultParams().apply {
                this[PvbParam.VB_ON] = 1f; this[PvbParam.VB_ALGO] = model.id.toFloat()
                this[PvbParam.VB_LEVEL_DB] = 9f; this[PvbParam.OUT_DB] = -18f; this[PvbParam.RAMP_MS] = 0f
            }
            e.setParams(p)
            val samples = (fs * 1.6).toInt() * 2
            val input = FloatArray(samples) { i ->
                val t = (i / 2).toDouble() / fs
                (.1 * (1 + .7 * sin(2 * PI * 20 * t)) * cos(2 * PI * 80 * t)).toFloat()
            }
            val output = FloatArray(samples)
            var offset = 0
            while (offset < samples) {
                val n = min(4096, samples - offset)
                val block = input.copyOfRange(offset, offset + n); val out = FloatArray(n)
                e.processFloat(block, out, n); out.copyInto(output, offset); offset += n
            }
            val meters = FloatArray(PvbMeter.COUNT); check(e.readMeters(meters))
            check(meters[PvbMeter.VB].toInt() == model.id + 1)
            check(e.latencyFrames == if (fs == 48000) 7140 else 6561)
            check(output.all { it.isFinite() } && output.any { abs(it) > 1e-5f })
            check(output.maxOf { abs(it) } < 1f)
            for ((suffix, x) in listOf("in" to input, "out" to output)) {
                val bytes = ByteBuffer.allocate(x.size * 4).order(ByteOrder.LITTLE_ENDIAN)
                x.forEach { bytes.putFloat(it) }
                File(dest, "alpha2-$fs-${model.id}.$suffix.f32").writeBytes(bytes.array())
            }
        }
    }
    check(PvbModels.models.size == 7)
    println("Alpha2/3 JNI: seven selectable models (incl. gentle12 ID3) at 44.1/48kHz, finite audio, IDs and latency passed")
}

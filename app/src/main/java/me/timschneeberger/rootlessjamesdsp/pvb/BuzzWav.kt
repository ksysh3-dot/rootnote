package me.timschneeberger.rootlessjamesdsp.pvb

import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** IEEE-float WAV preserves the callback's samples; exports run only on a background worker. */
object BuzzWav {
    fun write(stream: OutputStream, ring: BuzzRing, processed: Boolean, diagnosticTrack: Int = 0) {
        val w = ring.window()
        val frameBytes = ring.channels * 4
        val bytes = w.frames * frameBytes
        val header = ByteBuffer.allocate(56).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray()).putInt(48 + bytes).put("WAVE".toByteArray())
        header.put("fmt ".toByteArray()).putInt(16).putShort(3).putShort(ring.channels.toShort())
        header.putInt(ring.sampleRate).putInt(ring.sampleRate * frameBytes).putShort(frameBytes.toShort()).putShort(32)
        header.put("fact".toByteArray()).putInt(4).putInt(w.frames)
        header.put("data".toByteArray()).putInt(bytes)
        stream.write(header.array())
        val chunk = ByteBuffer.allocate(8192).order(ByteOrder.LITTLE_ENDIAN)
        for (f in w.start until w.end) {
            for (c in 0 until ring.channels) chunk.putFloat(if (diagnosticTrack == 0) ring.sample(f, c, processed) else ring.diagnosticSample(f, c, diagnosticTrack))
            if (!chunk.hasRemaining()) { stream.write(chunk.array()); chunk.clear() }
        }
        if (chunk.position() > 0) stream.write(chunk.array(), 0, chunk.position())
    }
}

package me.timschneeberger.rootlessjamesdsp.service

/**
 * Pure arithmetic of the capture -> process -> playback loop (no Android types, so the host JVM test in
 * tools/pvb-harness/jvm/PcmPumpTest.kt runs exactly this code with fake partial reads and writes).
 *
 * AudioRecord.read and AudioTrack.write may move fewer samples than asked, nothing (0: paused, stopped,
 * interrupted) or fail (negative codes, ERROR_DEAD_OBJECT = the object must be rebuilt). The loop only ever
 * processes and plays the samples actually read, in whole stereo frames, and continues partial writes.
 */
object PcmPump {
    /** After a read of [got] (> 0) samples placed after [carry] kept samples: samples to process (whole frames). */
    fun wholeFrames(carry: Int, got: Int): Int {
        val total = carry + got
        return total - (total and 1)
    }

    /**
     * Writes [n] samples through [write] (offset, length) -> written or error, continuing partial writes.
     * Returns the number written (n = all; less when [stop] turned true or more than [maxEmpty] zero-length writes
     * came in a row, the rest is dropped) or the negative error code of the failing write.
     */
    inline fun writeAll(n: Int, maxEmpty: Int, stop: () -> Boolean, write: (Int, Int) -> Int): Int {
        var off = 0
        var empty = 0
        while (off < n && !stop()) {
            val w = write(off, n - off)
            if (w > 0) {
                off += w
                empty = 0
            } else if (w == 0) {
                if (++empty > maxEmpty) return off
            } else {
                return w
            }
        }
        return off
    }

    /** Moves an odd trailing sample (index [samples] of [total]) to the front; returns the new carry (0 or 1). */
    fun keepCarry(buf: FloatArray, total: Int, samples: Int): Int {
        if (total > samples) buf[0] = buf[samples]
        return total - samples
    }

    fun keepCarry(buf: ShortArray, total: Int, samples: Int): Int {
        if (total > samples) buf[0] = buf[samples]
        return total - samples
    }
}

package me.timschneeberger.rootlessjamesdsp.capture

/**
 * Bounded PCM16 stereo queue between the shell capture process and the DSP worker.
 *
 * The producer must never wait for the AudioTrack/DSP consumer: otherwise stdout backpressure can reach the
 * remote-submix AudioRecord and disrupt the playback clock of video apps. On overload, discard the *oldest*
 * complete stereo frames instead of allowing latency to grow indefinitely. The caller always receives whole
 * stereo frames, even when a pipe read splits a sample or channel pair.
 *
 * No Android dependencies: exercised by the host-side InterceptPcmQueueTest.
 */
internal class InterceptPcmQueue(capacityFrames: Int) {
    init { require(capacityFrames > 0) }

    private val monitor = java.lang.Object()
    private val samples = ShortArray(capacityFrames * 2)
    private val capacity = capacityFrames
    private val partial = ByteArray(4)
    private var partialBytes = 0
    private var first = 0
    private var queued = 0
    private var accepting = false
    private var closed = false
    private var discarded = 0L

    val droppedFrames: Long get() = synchronized(monitor) { discarded }

    fun start() = synchronized(monitor) {
        if (!closed) {
            first = 0
            queued = 0 // do not replay audio accumulated before resume
            accepting = true
            monitor.notifyAll()
        }
    }

    fun stop() = synchronized(monitor) {
        accepting = false
        queued = 0
        first = 0
        monitor.notifyAll()
    }

    fun close() = synchronized(monitor) {
        closed = true
        accepting = false
        queued = 0
        monitor.notifyAll()
    }

    /** Accept a fragment of a 16-bit little-endian stereo stream (fragment boundaries are arbitrary). */
    fun offer(src: ByteArray, offset: Int, length: Int) = synchronized(monitor) {
        require(offset >= 0 && length >= 0 && offset <= src.size - length)
        if (closed) return@synchronized
        for (i in offset until offset + length) {
            partial[partialBytes++] = src[i]
            if (partialBytes != 4) continue
            partialBytes = 0
            if (!accepting) continue
            if (queued == capacity) {
                first = (first + 1) % capacity
                queued--
                discarded++
            }
            val pos = ((first + queued) % capacity) * 2
            samples[pos] = ((partial[0].toInt() and 0xff) or (partial[1].toInt() shl 8)).toShort()
            samples[pos + 1] = ((partial[2].toInt() and 0xff) or (partial[3].toInt() shl 8)).toShort()
            queued++
        }
        if (queued > 0) monitor.notifyAll()
    }

    /** Positive number of samples, zero when stopped, or -1 when closed/interrupted. Never an odd count. */
    fun read(dst: ShortArray, offset: Int, requestedSamples: Int): Int = synchronized(monitor) {
        require(offset >= 0 && requestedSamples >= 0 && offset <= dst.size - requestedSamples)
        val wanted = requestedSamples / 2
        if (wanted == 0) return@synchronized 0
        if (!awaitFrames()) return@synchronized if (closed) -1 else 0
        val n = minOf(wanted, queued)
        for (i in 0 until n) {
            val p = ((first + i) % capacity) * 2
            dst[offset + 2 * i] = samples[p]
            dst[offset + 2 * i + 1] = samples[p + 1]
        }
        first = (first + n) % capacity
        queued -= n
        n * 2
    }

    fun read(dst: FloatArray, offset: Int, requestedSamples: Int): Int = synchronized(monitor) {
        require(offset >= 0 && requestedSamples >= 0 && offset <= dst.size - requestedSamples)
        val wanted = requestedSamples / 2
        if (wanted == 0) return@synchronized 0
        if (!awaitFrames()) return@synchronized if (closed) -1 else 0
        val n = minOf(wanted, queued)
        for (i in 0 until n) {
            val p = ((first + i) % capacity) * 2
            dst[offset + 2 * i] = samples[p] / 32768f
            dst[offset + 2 * i + 1] = samples[p + 1] / 32768f
        }
        first = (first + n) % capacity
        queued -= n
        n * 2
    }

    /** Only called with [monitor] held. */
    private fun awaitFrames(): Boolean {
        while (queued == 0 && accepting && !closed) {
            try { monitor.wait() }
            catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return false
            }
        }
        return !closed && accepting && queued > 0
    }
}

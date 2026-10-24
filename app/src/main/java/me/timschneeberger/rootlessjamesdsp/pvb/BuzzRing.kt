package me.timschneeberger.rootlessjamesdsp.pvb

import java.util.concurrent.atomic.AtomicInteger

/** Bounded input/output history. One audio writer, one frozen export reader; no audio-thread locks or I/O. */
class BuzzRing(val sampleRate: Int, val preSeconds: Int = 5, val postSeconds: Int = 3,
               val channels: Int = 2, private val paired: Boolean = true, val detailed: Boolean = false) {
    private val capacity = sampleRate * (preSeconds + postSeconds + 2)
    private val input = FloatArray(capacity * channels)
    private val output = if (paired) FloatArray(capacity * channels) else input
    private val generated = if (detailed) FloatArray(capacity * channels) else null
    private val fullMix = if (detailed) FloatArray(capacity * channels) else null
    private val detailFrames = if (detailed) LongArray(MAX_EVENTS) else null
    private val detailTimes = if (detailed) LongArray(MAX_EVENTS) else null
    private val detailSamples = if (detailed) IntArray(MAX_EVENTS) else null
    private val detailTrace = if (detailed) FloatArray(MAX_EVENTS * DETAIL_FIELDS) else null
    private var detailCount = 0L
    val harmonicHistory = if (detailed) HarmonicHistory() else null
    private val owner = AtomicInteger(ACTIVE)
    @Volatile var armed = false
    @Volatile private var triggerRequested = false
    @Volatile private var freezeRequested: String? = null
    @Volatile private var resetRequested = false
    @Volatile var recordedFrames = 0L; private set
    private var started = false
    private var total = 0L
    private var mark = -1L
    private var target = Long.MAX_VALUE
    @Volatile private var collecting = false
    private var reason = ""
    private val eventFrame = LongArray(MAX_EVENTS)
    private val eventLatency = IntArray(MAX_EVENTS)
    private val eventAlgo = IntArray(MAX_EVENTS)
    private val eventBlend = FloatArray(MAX_EVENTS)
    private val eventUsingPvb = BooleanArray(MAX_EVENTS)
    private val eventParams = arrayOfNulls<FloatArray>(MAX_EVENTS)
    private var eventCount = 0L

    init { require(sampleRate in 8000..192000 && preSeconds in 1..10 && postSeconds in 1..10 && channels in 1..2) }
    val frozen: Boolean get() = owner.get() == FROZEN

    /** Main thread. A report is explicitly requested, never inferred by a buzz detector. */
    fun trigger(): Boolean {
        if (!armed || frozen || resetRequested || triggerRequested || collecting) return false
        triggerRequested = true
        return true
    }

    /** May be called on timeout/stop. CAS freezes immediately only between audio writes. */
    fun finish(why: String) {
        freezeRequested = why
        owner.compareAndSet(ACTIVE, FROZEN)
    }

    /** Export completed: the next audio block starts a fresh history, never joins across the export gap. */
    fun release() {
        check(frozen)
        resetRequested = true
        freezeRequested = null
        owner.set(ACTIVE)
    }

    private fun reset() {
        total = 0; recordedFrames = 0; mark = -1; target = Long.MAX_VALUE
        collecting = false; triggerRequested = false; reason = ""; started = false
        eventCount = 0; detailCount = 0
        harmonicHistory?.reset()
        eventParams.fill(null)
        resetRequested = false
    }

    private fun event(params: FloatArray?, latency: Int, algo: Int, blend: Float, usingPvb: Boolean) {
        val p = if (eventCount > 0) ((eventCount - 1) % MAX_EVENTS).toInt() else -1
        if (p >= 0 && total - eventFrame[p] < sampleRate / 10 && eventParams[p] === params &&
            eventLatency[p] == latency && eventAlgo[p] == algo && eventUsingPvb[p] == usingPvb) return
        // At most 10 Hz plus configuration/algorithm changes. Old timeline records may be discarded;
        // raw PCM coverage is independent and truncation is explicitly exported.
        val i = (eventCount++ % MAX_EVENTS).toInt()
        eventFrame[i] = total; eventParams[i] = params; eventLatency[i] = latency
        eventAlgo[i] = algo; eventBlend[i] = blend; eventUsingPvb[i] = usingPvb
    }

    fun recordFloat(src: FloatArray, dst: FloatArray, samples: Int, params: FloatArray?,
                    latency: Int, algo: Int, blend: Float, usingPvb: Boolean,
                    generated: FloatArray? = null, fullMix: FloatArray? = null, trace: FloatArray? = null,
                    elapsedNs: Long = 0L, harmonic: FloatArray? = null, harmonicRows: Int = -1) {
        record(src, dst, null, null, samples, params, latency, algo, blend, usingPvb, generated, fullMix, trace, elapsedNs, harmonic, harmonicRows)
    }

    fun recordShort(src: ShortArray, dst: ShortArray, samples: Int, params: FloatArray?,
                    latency: Int, algo: Int, blend: Float, usingPvb: Boolean,
                    generated: FloatArray? = null, fullMix: FloatArray? = null, trace: FloatArray? = null,
                    elapsedNs: Long = 0L, harmonic: FloatArray? = null, harmonicRows: Int = -1) {
        record(null, null, src, dst, samples, params, latency, algo, blend, usingPvb, generated, fullMix, trace, elapsedNs, harmonic, harmonicRows)
    }

    private fun record(fi: FloatArray?, fo: FloatArray?, si: ShortArray?, so: ShortArray?, samples: Int,
                       params: FloatArray?, latency: Int, algo: Int, blend: Float, usingPvb: Boolean,
                       layer: FloatArray?, full: FloatArray?, trace: FloatArray?, elapsedNs: Long,
                       harmonic: FloatArray?, harmonicRows: Int) {
        require(samples >= 0 && samples % channels == 0)
        require(samples <= (fi?.size ?: si!!.size) && samples <= (fo?.size ?: so!!.size))
        require(layer == null || layer.size >= samples)
        require(full == null || full.size >= samples)
        require(trace == null || trace.size == DETAIL_FIELDS)
        if (!owner.compareAndSet(ACTIVE, WRITING)) return
        try {
            if (resetRequested) reset()
            if (!armed && !collecting) { started = false; return }
            if (!started) { val pending = triggerRequested; reset(); started = true; triggerRequested = pending }
            if (triggerRequested && !collecting) {
                triggerRequested = false; collecting = true; mark = total
                target = mark + sampleRate.toLong() * postSeconds
            }
            if (!armed && collecting) { reason = "disarmed"; return }
            event(params, latency, algo, blend, usingPvb)
            val frames = samples / channels
            harmonicHistory?.record(total, frames, harmonic, harmonicRows)
            if (detailed) {
                val i = (detailCount++ % MAX_EVENTS).toInt()
                detailFrames!![i] = total; detailTimes!![i] = elapsedNs; detailSamples!![i] = frames
                val off = i * DETAIL_FIELDS
                if (trace != null && layer != null && full != null) trace.copyInto(detailTrace!!, off)
                else {
                    detailTrace!!.fill(Float.NaN, off, off + DETAIL_FIELDS)
                    detailTrace[off] = 0f // unavailable, never infer a clean/zero generated signal
                }
            }
            for (j in 0 until frames) {
                val d = ((total % capacity).toInt()) * channels
                val s = j * channels
                for (c in 0 until channels) {
                    if (fi != null && fo != null) {
                        input[d + c] = fi[s + c]
                        if (paired) output[d + c] = fo[s + c]
                    } else {
                        input[d + c] = si!![s + c] / 32768f
                        if (paired) output[d + c] = so!![s + c] / 32768f
                    }
                }
                if (detailed) for (c in 0 until channels) {
                    generated!![d + c] = layer?.get(s + c) ?: Float.NaN
                    fullMix!![d + c] = full?.get(s + c) ?: Float.NaN
                }
                ++total
                if (collecting && total >= target) { reason = "complete"; break }
            }
        } finally {
            recordedFrames = total
            if (reason.isNotEmpty() || freezeRequested != null) owner.set(FROZEN)
            else {
                owner.set(ACTIVE)
                // A stop may arrive after the above test while owner is still WRITING.
                if (freezeRequested != null) owner.compareAndSet(ACTIVE, FROZEN)
            }
        }
    }

    data class Window(val start: Long, val end: Long, val trigger: Long, val reason: String,
                      val complete: Boolean, val timelineTruncated: Boolean) {
        val frames: Int get() = (end - start).toInt()
    }

    fun window(): Window {
        check(frozen)
        val t = if (mark >= 0) mark else total // trigger may time out while AudioRecord is idle
        val start = maxOf(0L, total - capacity, t - sampleRate.toLong() * preSeconds)
        val oldest = maxOf(0L, eventCount - MAX_EVENTS)
        val truncated = eventCount > MAX_EVENTS && eventFrame[(oldest % MAX_EVENTS).toInt()] > start
        return Window(start, total, t, reason.ifEmpty { freezeRequested ?: "interrupted" },
            reason == "complete", truncated)
    }

    fun sample(frame: Long, channel: Int, processed: Boolean): Float {
        check(frozen)
        return (if (processed) output else input)[(frame % capacity).toInt() * channels + channel]
    }

    fun diagnosticSample(frame: Long, channel: Int, track: Int): Float {
        check(frozen && detailed)
        return (if (track == 1) generated!! else fullMix!!)[(frame % capacity).toInt() * channels + channel]
    }

    fun detailTruncated(): Boolean {
        check(frozen)
        return detailed && detailCount > MAX_EVENTS && detailFrames!![(detailCount % MAX_EVENTS).toInt()] > window().start
    }

    fun forEachDetail(block: (Long, Int, Long, FloatArray, Int) -> Unit) {
        check(frozen)
        if (!detailed) return
        for (n in maxOf(0L, detailCount - MAX_EVENTS) until detailCount) {
            val i = (n % MAX_EVENTS).toInt()
            block(detailFrames!![i], detailSamples!![i], detailTimes!![i], detailTrace!!, i * DETAIL_FIELDS)
        }
    }

    /** Frozen reader only. Requested params are immutable snapshots, not guaranteed active values. */
    fun forEachEvent(block: (Long, Int, Int, Float, Boolean, FloatArray?) -> Unit) {
        check(frozen)
        for (n in maxOf(0L, eventCount - MAX_EVENTS) until eventCount) {
            val i = (n % MAX_EVENTS).toInt()
            block(eventFrame[i], eventLatency[i], eventAlgo[i], eventBlend[i], eventUsingPvb[i], eventParams[i])
        }
    }

    companion object {
        const val DETAIL_FIELDS = 89 // 32 observed fields + 57 applied native parameters (PvbParam.COUNT; DiagnosticJniTest)
        private const val ACTIVE = 0
        private const val WRITING = 1
        private const val FROZEN = 2
        private const val MAX_EVENTS = 4096
    }
}

/** Owned by BuzzRing's writer/frozen reader. 5,681,536-byte arrays, no per-hop allocations. */
class HarmonicHistory {
    private val frames = LongArray(CAPACITY)
    private val values = FloatArray(CAPACITY * FIELDS)
    private val blockFrames = LongArray(BLOCKS)
    private val blockSizes = IntArray(BLOCKS)
    private val blockStatus = IntArray(BLOCKS)
    private var count = 0L
    private var blocks = 0L
    fun reset() { count = 0; blocks = 0 }
    fun record(start: Long, size: Int, data: FloatArray?, rows: Int) {
        val valid = rows in 0..ROWS && (rows == 0 || (data != null && data.size >= rows * FIELDS))
        val status = if (valid) rows else if (rows < 0) rows else -3
        val b = (blocks++ % BLOCKS).toInt()
        blockFrames[b] = start; blockSizes[b] = size; blockStatus[b] = status
        if (!valid) return
        repeat(rows) { r ->
            val offset = r * FIELDS
            val event = data!![offset]
            // Reject malformed timing/version as a visible unavailable block.
            if (!event.isFinite() || event < 0 || event >= size || event != event.toInt().toFloat() || data[offset+23] != 1f) {
                blockStatus[b] = -3
                return@repeat
            }
            val i = (count++ % CAPACITY).toInt()
            frames[i] = start + event.toInt()
            data.copyInto(values, i * FIELDS, offset, offset + FIELDS)
        }
    }
    fun truncated(start: Long): Boolean =
        (count > CAPACITY && frames[(count % CAPACITY).toInt()] > start) ||
        (blocks > BLOCKS && blockFrames[(blocks % BLOCKS).toInt()] > start)
    fun forEach(start: Long, end: Long, block: (Long, FloatArray, Int) -> Unit) {
        for (n in maxOf(0L, count - CAPACITY) until count) {
            val i = (n % CAPACITY).toInt()
            if (frames[i] in start until end) block(frames[i], values, i * FIELDS)
        }
    }
    fun forEachBlock(start: Long, end: Long, block: (Long, Int, Int) -> Unit) {
        for (n in maxOf(0L, blocks - BLOCKS) until blocks) {
            val i = (n % BLOCKS).toInt()
            if (blockFrames[i] < end && blockFrames[i] + blockSizes[i] > start)
                block(blockFrames[i], blockSizes[i], blockStatus[i])
        }
    }
    companion object {
        const val HEADER = 28
        const val TRACK = 56
        const val TRACKS = 12
        const val FIELDS = HEADER + TRACK * TRACKS
        const val ROWS = 72
        private const val CAPACITY = 2000 // > 10 seconds at 187.5 Hz
        private const val BLOCKS = 4096
    }
}

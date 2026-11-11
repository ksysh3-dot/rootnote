package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/** No file IO, allocation, or locking in the callback hooks. File work belongs to s91-log. */
class StageCTelemetry(private val context: Context, private val engine: PvbEngine) : AutoCloseable {
    @Volatile var enabled = false
        private set
    private var writer: ScheduledExecutorService? = null
    private var task: ScheduledFuture<*>? = null
    private val callbacks = AtomicLong()
    private val overruns = AtomicLong()
    private val underruns = AtomicLong()
    private val readGaps = AtomicLong()
    private val droppedBlocks = AtomicLong()
    private var lastUnderruns = 0
    private var file: File? = null
    private var mode = "off"
    private var worker = false
    private var familyP2 = false
    private var rate = 48000
    private val native = LongArray(2012)

    fun start() {
        check(writer == null)
        val p = context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        if (!p.getBoolean(StageCApp.TELEMETRY, false)) return
        val s = PvbSettings.load(p)
        mode = s.bassMode; worker = s.conducted && p.getBoolean(StageCApp.WORKER, false); rate = engine.sampleRateHz
        familyP2 = mode == "conducted" && rate == 48000 && p.getBoolean(StageCApp.FAMILY_P2, true)
        if (familyP2) worker = false
        callbacks.set(0); overruns.set(0); underruns.set(0); readGaps.set(0); droppedBlocks.set(0); lastUnderruns = 0
        file = File(context.filesDir, "s91_telemetry/s91-" + System.currentTimeMillis() + "-" + mode + ".jsonl")
        enabled = true
        writer = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "s91-log") }.also {
            task = it.scheduleAtFixedRate({ snapshot("periodic") }, 0, 5, TimeUnit.SECONDS)
        }
    }

    fun callback(frames: Int, elapsedNs: Long, trackUnderruns: Int) {
        if (!enabled) return
        callbacks.incrementAndGet()
        if (elapsedNs > frames * 1_000_000_000L / rate) overruns.incrementAndGet()
        if (trackUnderruns >= lastUnderruns) underruns.addAndGet((trackUnderruns - lastUnderruns).toLong())
        else underruns.addAndGet(trackUnderruns.toLong()) // newly recreated AudioTrack
        lastUnderruns = trackUnderruns
    }
    fun readGap() { if (enabled) readGaps.incrementAndGet() }
    fun droppedBlock() { if (enabled) droppedBlocks.incrementAndGet() }

    private fun snapshot(reason: String) {
        try {
            if (!engine.copyStageC(native)) return
            val count = native.drop(12).sum()
            fun percentile(pct: Double): Long? {
                if (count == 0L) return null
                val target = kotlin.math.ceil(count * pct).toLong()
                var sum = 0L
                for (i in 0 until 2000) {
                    sum += native[12 + i]
                    if (sum >= target) return if (i == 1999) native[1] else (i + 1) * 10_000L
                }
                return native[1]
            }
            val json = JSONObject().put("schema", "s91c-v1").put("utc_ms", System.currentTimeMillis())
                .put("reason", reason).put("build_id", BuildConfig.COMMIT_SHA).put("build_time", BuildConfig.BUILD_TIME)
                .put("family_p2", familyP2)
                .put("package_id", context.packageName).put("mode", mode).put("worker", worker).put("sample_rate_hz", rate)
                .put("control_frames", native[0]).put("control_frame_p50_ns", percentile(.50) ?: JSONObject.NULL)
                .put("control_frame_p99_ns", percentile(.99) ?: JSONObject.NULL).put("control_frame_max_ns", native[1])
                .put("percentile_bin_ns", 10_000).put("histogram_frames", count)
                .put("callback_count", callbacks.get()).put("callback_overruns", overruns.get())
                .put("audio_track_underruns", underruns.get()).put("capture_read_gaps", readGaps.get())
                .put("playback_dropped_blocks", droppedBlocks.get()).put("late_control_frames", native[2])
                .put("control_queue_drops", native[3]).put("separator_ticks", native[4])
                .put("native_mode", native[5]).put("native_flags", native[6]).put("engine_state", native[7])
                .put("engine_latency_frames", native[8]).put("control_modules", native[9])
                .put("dropouts", underruns.get() + readGaps.get() + droppedBlocks.get())
                .put("dropouts_definition", "I/O observations; audible gaps must be recorded separately")
            synchronized(StageCApp.fileLock) {
                file!!.parentFile!!.mkdirs()
                file!!.appendText(json.toString() + "\n", Charsets.UTF_8)
            }
        } catch (e: Exception) { android.util.Log.e("s91", "telemetry write failed", e) }
    }

    /** Called with audio stopped, before the next model is prepared or the engine is closed. */
    override fun close() {
        enabled = false
        val w = writer ?: return
        task?.cancel(false)
        task = null
        // A slow export holds the file lock: that must not stop the service from preparing or closing the engine.
        try {
            w.submit { snapshot("session_end") }.get(10, TimeUnit.SECONDS)
            w.shutdown()
            if (!w.awaitTermination(10, TimeUnit.SECONDS)) android.util.Log.e("s91", "telemetry writer still busy")
        } catch (e: Exception) {
            android.util.Log.e("s91", "telemetry close failed", e)
            w.shutdownNow()
        } finally {
            writer = null
        }
    }
}

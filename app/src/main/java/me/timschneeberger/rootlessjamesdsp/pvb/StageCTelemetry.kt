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

/** No file IO, allocation, or locking in the callback hooks. File work runs on the telemetry writer thread. */
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
    private var rate = 48000

    fun start() {
        check(writer == null)
        val p = context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        if (!p.getBoolean(StageCApp.TELEMETRY, false)) return
        val s = PvbSettings.load(p)
        mode = s.bassMode
        rate = engine.sampleRateHz
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
            val json = JSONObject().put("schema", "combo-v1").put("utc_ms", System.currentTimeMillis())
                .put("reason", reason).put("build_id", BuildConfig.COMMIT_SHA).put("build_time", BuildConfig.BUILD_TIME)
                .put("package_id", context.packageName).put("mode", mode).put("sample_rate_hz", rate)
                .put("callback_count", callbacks.get()).put("callback_overruns", overruns.get())
                .put("audio_track_underruns", underruns.get()).put("capture_read_gaps", readGaps.get())
                .put("playback_dropped_blocks", droppedBlocks.get())
                .put("engine_latency_frames", engine.latencyFrames)
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

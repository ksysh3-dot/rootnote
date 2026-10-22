package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.service.BuzzMicrophoneService
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.DigestOutputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.Executors
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Main-thread control; audio only writes [ring] and signals discontinuity. Nothing is uploaded. */
class BuzzDiagnostics(
    context: Context,
    private val engine: PvbEngine,
    private val changed: () -> Unit,
    private val gain: (Float) -> Unit,
    private val ioSnapshot: () -> JSONObject,
    private val result: (String) -> Unit,
) {
    private val app = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val exporter = Executors.newSingleThreadExecutor { r -> Thread(r, "pvb-buzz-export") }
    private val meters = FloatArray(PvbMeter.COUNT)
    private var sampleRate = 48000
    private var attached = false
    private var disposed = false
    private var pending: Pending? = null
    private var exporting = false
    private val mute = BuzzMute({ SystemClock.elapsedRealtime() }, { task, delay -> main.postDelayed(task, delay); Unit }, gain)
    @Volatile private var discontinuity: String? = null
    @Volatile var ring: BuzzRing? = null; private set
    @Volatile var armed = false; private set
    @Volatile var observedAlgo = -1; private set
    @Volatile var observedBlend = Float.NaN; private set

    val stateText: String get() = when {
        exporting -> "버즈 리포트 저장 중 · 재생 복구됨"
        pending != null -> if (pending!!.report.optBoolean("mute_requested", true)) "버즈 기록 중 · 잠시 무음" else "버즈 기록 중 · 재생 유지"
        armed -> "버즈 진단 켜짐 · 최근 5초 보관"
        else -> "버즈 진단 꺼짐"
    }
    val busy: Boolean get() = pending != null || exporting

    private class Pending(val ring: BuzzRing, val report: JSONObject, val deadline: Long,
                          val mic: BuzzMicrophone?, val micRing: BuzzRing?)

    fun attach(rate: Int) {
        detach("audio_generation_changed")
        sampleRate = rate; attached = true
        if (armed && !busy) newHistory()
        schedule()
    }

    fun detach(reason: String) {
        attached = false
        ring?.finish(reason)
        if (pending == null) ring = null
        restore()
        schedule()
    }

    /** Audio thread: one volatile flag, no handler allocation, file I/O or waiting. */
    fun audioDiscontinuity(reason: String) {
        ring?.finish(reason)
        discontinuity = reason
    }

    fun toggle() {
        if (!PvbBuild.recordFeatures) return  // general build: diagnostics (recordings) cannot be armed
        if (!armed && (PvbRuntime.abActive || PvbRuntime.measuring)) {
            result("블라인드 비교·측정이 끝난 뒤 진단을 켜 주세요."); return
        }
        armed = !armed
        if (armed && attached && !busy) newHistory()
        if (!armed) {
            app.stopService(Intent(app, BuzzMicrophoneService::class.java))
            ring?.armed = false
            ring?.finish("user_disarmed")
            if (pending == null) ring = null
            restore()
        }
        changed(); schedule()
    }

    fun trigger(): Boolean {
        if (!PvbBuild.recordFeatures) return false
        if (disposed || !attached || !armed || busy || PvbRuntime.abActive || PvbRuntime.measuring) return false
        val r = ring ?: return false
        val request = snapshot().put("schema", "pvb.buzz_report.v2")
            .put("mute_requested", app.getSharedPreferences("pvb_buzz", Context.MODE_PRIVATE).getBoolean("mute_on_report", true))
            .put("id", UUID.randomUUID().toString())
            .put("user_reported_buzz", true).put("automatically_confirmed_buzz", false)
            .put("button_wall_time_ms", System.currentTimeMillis())
            .put("button_elapsed_realtime_ns", SystemClock.elapsedRealtimeNanos())
            .put("published_frames_at_button", r.recordedFrames)
            .put("io_at_button", ioSnapshot())
            .put("limitations", JSONArray(listOf(
                "The button is a user marker after an unknown reaction delay, not the buzz onset.",
                "input.wav/processed.wav are digital; microphone.wav, when explicitly enabled, is a separate acoustic recording.",
                "processed.wav is before diagnostic AudioTrack gain; it is intentionally not muted.",
                "With diagnostic_solo enabled, processed.wav contains the generated-layer monitor, not the full mix. See parameter timeline; switching crossfades for 100 ms.",
                "Solo preserves full-mix analysis, gain, limiter sidechain and latency; a parallel isolated-layer limiter may add attenuation. Physical speaker processing differs when the full mix is not played.",
                "Input/output at the same frame are callback-paired, not latency-aligned.",
                "Requested parameter snapshots can precede native application and ramps.",
                "Native meters are polled on the main thread, approximately every 100 ms.",
                "AudioTrack queue/system DSP/output volume/speaker distortion are not embedded in digital WAVs.",
                "A short clip lacks earlier native filter state; byte-exact replay is not guaranteed."
            )))
        if (!r.trigger()) return false
        val mic = BuzzMicRuntime.capture?.takeIf { it.running }
        val mr = mic?.ring?.takeIf { it.trigger() }
        request.put("microphone_at_button", mic?.snapshot() ?: JSONObject().put("enabled", false))
            .put("microphone_capture_requested", mr != null)
        pending = Pending(r, request, SystemClock.elapsedRealtime() + 5000L, mic, mr)
        if (request.getBoolean("mute_requested")) mute.begin()
        // Independent wall-clock restoration even if audio stops delivering blocks.
        main.postDelayed({ if (pending?.ring === r && !exporting) {
            r.finish("wall_timeout"); pending?.micRing?.finish("wall_timeout"); restore(); schedule()
        } }, 5000L)
        changed(); schedule()
        return true
    }

    private fun newHistory() {
        ring = BuzzRing(sampleRate, detailed = true).apply { armed = true }
        discontinuity = null
    }

    private fun schedule() {
        main.removeCallbacks(poll)
        if (pending != null || (armed && attached && !disposed)) main.postDelayed(poll, 100L)
    }

    private val poll = object : Runnable {
        override fun run() {
            if (PvbRuntime.abActive || PvbRuntime.measuring) {
                app.stopService(Intent(app, BuzzMicrophoneService::class.java))
                armed = false; ring?.armed = false; ring?.finish("comparison_or_measurement_started")
                if (pending == null) ring = null
                restore(); changed()
            }
            if (armed && attached && engine.readMeters(meters)) {
                observedAlgo = meters[PvbMeter.VB].toInt() - 1
                observedBlend = meters[PvbMeter.VB_UPPER_BLEND]
            }
            val p = pending
            if (p != null) {
                if (!attached || SystemClock.elapsedRealtime() >= p.deadline) {
                    p.ring.finish(if (attached) "wall_timeout" else "audio_stopped")
                    p.micRing?.finish(if (attached) "wall_timeout" else "audio_stopped")
                    restore()
                }
                if (p.ring.frozen && !p.ring.window().complete) p.micRing?.finish("digital_collection_interrupted")
                if (p.ring.frozen && (p.micRing == null || p.micRing.frozen) && !exporting) {
                    restore()
                    p.report.put("io_at_freeze", ioSnapshot())
                        .put("status_at_freeze", statusJson())
                        .put("native_meters_at_freeze", metersJson())
                        .put("microphone_at_freeze", p.mic?.snapshot() ?: JSONObject().put("enabled", false))
                        .put("mute_restore_requested_after_ms", if (p.report.getBoolean("mute_requested")) mute.restoreRequestedAt - mute.startedAt else JSONObject.NULL)
                        .put("mute_gain_application_verified", false)
                        .put("mute_fade_down_ms", 40).put("mute_fade_up_ms", 100)
                        .put("mute_application", "AudioTrack gain; system volume unchanged")
                        .put("pre_roll_requested_s", 5).put("post_roll_requested_s", 3)
                    exporting = true; ring = null
                    changed()
                    exporter.execute {
                        val message = try { save(p); "버즈 리포트 저장 완료 · 눌러서 공유" }
                        catch (e: Exception) { "버즈 리포트 저장 실패: ${e.javaClass.simpleName}. 저장 공간과 기록 목록을 확인해 주세요." }
                        main.post {
                            pending = null; exporting = false
                            if (!disposed && armed && p.mic === BuzzMicRuntime.capture) p.mic?.restartHistory()
                            if (!disposed && attached && armed) newHistory()
                            changed(); result(message); schedule()
                            if (disposed) exporter.shutdown()
                        }
                    }
                }
            } else if (discontinuity != null) {
                // A pause/recreation breaks the frame clock; never join unrelated history.
                discontinuity = null; ring = null
                if (armed && attached && !disposed) newHistory()
            }
            schedule()
        }
    }

    private fun restore() = mute.restore()

    fun close() {
        disposed = true; armed = false
        app.stopService(Intent(app, BuzzMicrophoneService::class.java))
        detach("service_destroyed")
        changed()
        if (pending == null) { main.removeCallbacks(poll); exporter.shutdown() }
    }

    private fun snapshot() = JSONObject()
        .put("app_version", BuildConfig.VERSION_NAME).put("app_version_code", BuildConfig.VERSION_CODE)
        .put("source_commit", BuildConfig.COMMIT_SHA)
        .put("manufacturer", Build.MANUFACTURER).put("device_model", Build.MODEL)
        .put("device", Build.DEVICE).put("android_sdk", Build.VERSION.SDK_INT)
        .put("android_release", Build.VERSION.RELEASE).put("build_incremental", Build.VERSION.INCREMENTAL)
        .put("status_at_button", statusJson())
        .put("recent_volume_settings", JSONArray(PvbRuntime.recentSettings()))
        .put("requested_parameters_at_button", paramsJson(engine.diagnosticParams))
        .put("native_meters_at_button", metersJson())

    private fun metersJson(): JSONObject {
        val obj = JSONObject().put("observation_elapsed_realtime_ns", SystemClock.elapsedRealtimeNanos())
        if (!engine.readMeters(meters)) return obj.put("available", false)
        val names = arrayOf("in_peak_db", "out_peak_db", "limiter_gr_db", "low_db_now", "mix", "load_pct", "sample_rate_hz",
            "latency_frames", "blocks", "nan_events", "estimated_level_db", "estimated_gr_db", "dyn_db", "dyn_level_db",
            "vb_meter_id", "match_db", "vb_scene", "unknown_frames", "steady_frames", "transient_frames", "complex_frames",
            "upper_blend", "upper_target", "upper_transitions", "diagnostic_solo_blend", "diagnostic_solo_extra_gr_db")
        meters.forEachIndexed { i, value -> obj.put(names[i], finite(value)) }
        return obj.put("available", true).put("peak_window", "since previous native meter read, including other UI readers")
    }

    private fun statusJson(): JSONObject {
        val s = PvbRuntime.status
        return JSONObject().put("processing", s.processing).put("using_pvb", s.usingPvb)
            .put("matched_bypass", s.matchedBypass).put("speaker", s.speaker)
            .put("route", s.routeName).put("route_known", s.routeKnown)
            .put("volume_index", s.volumeIndex).put("volume_max", s.volumeMax)
            .put("volume_label", PvbRuntime.volumeLabel(s.volumeIndex, s.volumeMax))
            .put("volume_db", finite(s.volumeDb)).put("volume_db_source", s.volumeDbSource)
            .put("volume_system_db", finite(s.volumeSysDb)).put("volume_link", s.volLink)
            .put("vb_on_requested", s.vbOn).put("vb_algo_requested", s.vbAlgo)
            .put("vb_model_name", PvbSettings.vbAlgoName(s.vbAlgo)).put("vb_model_schema", PvbSettings.VB_MODEL_SCHEMA)
            .put("vb_level_db_requested", finite(s.vbLevelDb))
            .put("vb_volume_link", s.vbVolLink).put("vb_volume_reduction_db", finite(s.vbVolReductionDb))
            .put("vb_level_db_applied", finite(s.vbAppliedLevelDb))
    }

    private fun save(p: Pending) {
        val r = p.ring; val w = r.window()
        val micWindow = p.micRing?.window()
        check(w.frames > 0) { "No audio was captured" }
        val dir = File(app.filesDir, "buzz_reports").apply { check(isDirectory || mkdirs()) }
        // No automatic deletion of user recordings. Refuse new files when the local quota is full.
        val used = dir.listFiles()?.sumOf { if (it.isFile) it.length() else 0L } ?: 0L
        check(used + w.frames.toLong() * (if (r.detailed) 32 else 16) + (micWindow?.frames?.toLong() ?: 0) * 4 + 1048576L <= 100L * 1024 * 1024) { "Report quota full" }
        val name = "buzz-${p.report.getLong("button_wall_time_ms")}-${p.report.getString("id").take(8)}.zip"
        val temp = File(dir, "$name.part")
        val destination = File(dir, name)
        try {
            p.report.put("sample_rate_hz", r.sampleRate).put("channels", 2)
                .put("wav_encoding", "IEEE_FLOAT_32_LE")
                .put("frame_clock", "relative to this uninterrupted diagnostic history")
                .put("clip_start_frame", w.start).put("clip_end_frame_exclusive", w.end)
                .put("button_marker_frame", w.trigger)
                .put("marker_definition", "first audio block after trigger is observed; not an acoustic timestamp")
                .put("marker_in_clip_s", (w.trigger - w.start).toDouble() / r.sampleRate)
                .put("pre_roll_actual_s", (w.trigger - w.start).toDouble() / r.sampleRate)
                .put("post_roll_actual_s", (w.end - w.trigger).toDouble() / r.sampleRate)
                .put("post_roll_complete", w.complete).put("finish_reason", w.reason)
                .put("timeline_truncated", w.timelineTruncated)
            val events = JSONArray()
            var prior: JSONObject? = null
            val latencies = HashSet<Int>()
            r.forEachEvent { f, latency, algo, blend, using, params ->
                if (f < w.end) {
                    val event = JSONObject().put("frame", f).put("in_clip_s", (f - w.start).toDouble() / r.sampleRate)
                        .put("engine_latency_frames", latency).put("using_pvb", using)
                        .put("observed_algo_approx", algo).put("observed_upper_blend_approx", finite(blend))
                        .put("requested_parameters", paramsJson(params))
                    if (f < w.start) prior = event else {
                        if (events.length() == 0 && prior != null) events.put(prior)
                        events.put(event); latencies.add(latency)
                    }
                }
            }
            if (events.length() == 0 && prior != null) {
                events.put(prior); latencies.add(prior!!.getInt("engine_latency_frames"))
            } else if (prior != null) latencies.add(prior!!.getInt("engine_latency_frames"))
            p.report.put("audio_block_timeline", events)
                .put("constant_engine_latency_frames", if (latencies.size == 1 && latencies.first() >= 0) latencies.first() else JSONObject.NULL)
                .put("alignment", "processed[n] corresponds approximately to input[n - engine_latency_frames] when latency is constant; JamesDSP latency unknown")
            if (r.detailed) {
                val rows = JSONArray()
                r.forEachDetail { f, count, elapsed, data, off ->
                    if (f < w.end && f + count > w.start) {
                        val row = JSONObject().put("block_start_frame", f).put("block_frames", count)
                            .put("clip_start_s", (maxOf(f, w.start) - w.start).toDouble() / r.sampleRate)
                            .put("clip_end_s", (minOf(f + count, w.end) - w.start).toDouble() / r.sampleRate)
                            .put("callback_completed_elapsed_realtime_ns", elapsed)
                        DETAIL_NAMES.forEachIndexed { i, name -> row.put(name, finite(data[off+i])) }
                        val active = JSONObject()
                        PARAM_NAMES.forEachIndexed { i, name -> active.put(name, finite(data[off+32+i])) }
                        row.put("native_applied_parameters", active)
                        rows.put(row)
                    }
                }
                p.report.put("detailed_processing", JSONObject().put("schema", "pvb.processing_trace.v1")
                    .put("timeline_truncated", r.detailTruncated()).put("blocks", rows)
                    .put("resolution", "one row per native process callback; metrics cover the entire block, including clipped edge blocks")
                    .put("limitations", "Block extrema/RMS and boundary states, not every internal FFT/pitch/harmonic decision. Native timing excludes capture, JNI copies, ring writes, playback queue and OS processing."))
                    .put("generated_track", JSONObject().put("file", "generated.wav")
                        .put("definition", "Actual generated contribution with layer/output gains, shared full-mix limiter gain, mix/gate/fades and limiter delay. Excludes solo-only extra protection. No normalization.")
                        .put("alignment", "Same frames as full_mix.wav and processed.wav. Generated contribution can exceed the mixed sum through cancellation; IEEE float preserves values.")
                        .put("unavailable", "NaN samples and available=0 when not captured; never substitute fabricated silence."))
                    .put("full_mix_track", "full_mix.wav: ordinary complete output before the solo monitor and diagnostic AudioTrack mute, generated in the same pass")
            }
            if (micWindow != null && p.micRing != null) {
                val mw = micWindow; val rate = p.micRing.sampleRate
                p.report.put("microphone_clip", JSONObject().put("file", if (mw.frames > 0) "microphone.wav" else JSONObject.NULL)
                    .put("sample_rate_hz", rate).put("channels", 1).put("clip_start_frame", mw.start)
                    .put("clip_end_frame_exclusive", mw.end).put("button_marker_frame", mw.trigger)
                    .put("marker_in_clip_s", (mw.trigger - mw.start).toDouble() / rate)
                    .put("pre_roll_actual_s", (mw.trigger - mw.start).toDouble() / rate)
                    .put("post_roll_actual_s", (mw.end - mw.trigger).toDouble() / rate)
                    .put("post_roll_complete", mw.complete).put("finish_reason", mw.reason)
                    .put("alignment", "Separate microphone clock. Use timestamp anchors/correlation; never assume frame alignment with digital WAVs. Post-mute sound may be silent."))
            }
            ZipOutputStream(temp.outputStream().buffered()).use { zip ->
                val hashes = JSONObject()
                val recordings = arrayListOf(Triple("input.wav", r, false), Triple("processed.wav", r, true))
                if (p.micRing != null && micWindow != null && micWindow.frames > 0) recordings.add(Triple("microphone.wav", p.micRing, false))
                for ((entry, capturedRing, processed) in recordings) {
                    zip.putNextEntry(ZipEntry(entry))
                    val digest = MessageDigest.getInstance("SHA-256")
                    val stream = DigestOutputStream(zip, digest)
                    BuzzWav.write(stream, capturedRing, processed); stream.flush(); zip.closeEntry()
                    hashes.put(entry, digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) })
                }
                if (r.detailed) for ((entry, track) in listOf("generated.wav" to 1, "full_mix.wav" to 2)) {
                    zip.putNextEntry(ZipEntry(entry))
                    val digest = MessageDigest.getInstance("SHA-256")
                    val stream = DigestOutputStream(zip, digest)
                    BuzzWav.write(stream, r, false, track); stream.flush(); zip.closeEntry()
                    hashes.put(entry, digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) })
                }
                p.report.put("sha256", hashes)
                if (r.detailed) HarmonicTraceWriter.write(zip, r, p.report, hashes)
                zip.putNextEntry(ZipEntry("report.json"))
                zip.write(p.report.toString(2).toByteArray(Charsets.UTF_8)); zip.closeEntry()
            }
            check(used + temp.length() <= 100L * 1024 * 1024) { "Report quota full" }
            check(temp.renameTo(destination)) { "Cannot finalize report" }
        } finally { temp.delete() }
    }

    companion object {
        private fun finite(v: Float): Any = if (v.isFinite()) v else JSONObject.NULL
        private val DETAIL_NAMES = arrayOf("available", "frames", "native_processing_us", "sample_rate_hz", "latency_frames",
            "algorithm_start", "algorithm_end", "scene_end", "upper_blend_start", "upper_blend_end", "upper_target_end", "upper_transitions_total",
            "input_peak_dbfs", "input_rms_dbfs", "generated_before_limiter_peak_dbfs", "generated_before_limiter_rms_dbfs",
            "generated_peak_dbfs", "generated_rms_dbfs", "full_mix_peak_dbfs", "full_mix_rms_dbfs", "output_peak_dbfs", "output_rms_dbfs",
            "full_mix_limiter_max_gr_db", "solo_extra_max_gr_db", "solo_blend_start", "solo_blend_end", "output_gain_linear_start", "output_gain_linear_end",
            "dynamic_low_db_end", "match_db_end", "nan_events_total", "algorithm_switch_phase_end")
        private val PARAM_NAMES = arrayOf("enabled", "hp_hz", "low_hz", "low_db", "low_q", "hi_hz", "hi_db", "hi_q",
            "out_db", "ceiling_db", "release_ms", "ramp_ms", "dyn_on", "dyn_ref_db", "dyn_down_ratio", "dyn_down_max_db",
            "dyn_up_ratio", "dyn_up_max_db", "hs_hz", "hs_db", "gate_db", "tag", "vb_on", "vb_algo", "vb_level_db",
            "flat", "match_hold", "match_seed_db", "diagnostic_solo", "x_smooth", "x_rise", "x_s1m", "x_dense",
            "dev_on", "dev_meter", "d_boundary_hz", "d_out_lo_hz", "d_out_hi_hz", "d_h2_db", "d_h3_db", "d_h4_db",
            "d_h5_db", "d_rolloff_db_oct", "d_sust_db", "d_perc_db", "d_attack_ms", "d_release_ms",
            "xtc_mode", "xtc_strength_db", "xtc_dist_cm", "xtc_hat_cm", "xtc_spacing_cm", "xtc_lo_hz", "xtc_hi_hz", "xtc_bal_lo_db", "xtc_bal_hi_db")
        private fun paramsJson(params: FloatArray?): Any {
            if (params == null) return JSONObject.NULL
            val obj = JSONObject()
            params.forEachIndexed { i, value -> obj.put(PARAM_NAMES.getOrElse(i) { "param_$i" }, finite(value)) }
            return obj
        }
    }
}

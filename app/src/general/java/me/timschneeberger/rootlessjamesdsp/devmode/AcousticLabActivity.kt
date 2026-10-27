package me.timschneeberger.rootlessjamesdsp.devmode

import android.Manifest
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.media.*
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import androidx.compose.runtime.*
import androidx.compose.ui.res.stringResource
import androidx.core.content.ContextCompat
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.*
import me.timschneeberger.rootlessjamesdsp.ui.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.math.abs

/** Foreground, opt-in band-only measurements. Separate engine, fixed gain, no preference/profile writes. */
class AcousticLabActivity : RnActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val generation = AtomicInteger()
    private var busy by mutableStateOf(false)
    private var status by mutableStateOf("")
    private var calibrationReady by mutableStateOf(false)
    private var fitReady by mutableStateOf(false)
    @Volatile private var recorder: LabRecorder? = null
    @Volatile private var track: AudioTrack? = null
    @Volatile private var expectedVolumeIndex = -1
    private val audio by lazy { getSystemService(AudioManager::class.java) }
    private val calFile by lazy { File(filesDir, "acoustic_lab_calibration.json") }
    private val impactFile by lazy { File(filesDir, "acoustic_lab_impact.json") }
    private var calibration = JSONObject()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val flags = getSharedPreferences(PvbGeneral.FLAGS_PREFS, MODE_PRIVATE)
        if (!flags.getBoolean(PvbGeneral.KEY_DEV_CONSENT, false)) { finish(); return }
        calibration = try { JSONObject(calFile.readText()) } catch (_: Exception) { newReport("calibration") }
        calibrationReady = calibration.optJSONObject("phases")?.has("room") == true
        fitReady = calibration.optJSONObject("phases")?.has("fit") == true
        setRnContent {
            RnPage(stringResource(R.string.lab_title), onBack = { finish() }) {
                RnParagraph(stringResource(R.string.lab_intro))
                RnSectionTitle(stringResource(R.string.lab_cal_title))
                RnParagraph(stringResource(R.string.lab_cal_note))
                RnNavRow(stringResource(R.string.lab_room), enabled = !busy, onClick = { calibrationPhase("room") })
                RnNavRow(stringResource(R.string.lab_fit), enabled = !busy && calibrationReady, onClick = { calibrationPhase("fit") })
                RnNavRow(stringResource(R.string.lab_validation), enabled = !busy && fitReady, onClick = { calibrationPhase("validation") })
                RnNavRow(stringResource(R.string.lab_cal_export), enabled = !busy, onClick = { share(calFile) })
                RnBand()
                RnSectionTitle(stringResource(R.string.lab_impact_title))
                RnParagraph(stringResource(R.string.lab_impact_note))
                RnNavRow(stringResource(R.string.lab_impact_start), enabled = !busy, onClick = { impactRun() })
                RnNavRow(stringResource(R.string.lab_impact_export), enabled = !busy, onClick = { share(impactFile) })
                if (busy) RnNavRow(stringResource(R.string.lab_stop), onClick = { cancel() })
                if (status.isNotEmpty()) RnParagraph(status)
                RnNote(stringResource(R.string.lab_limits))
                RnNavRow(stringResource(R.string.lab_clear), enabled = !busy, onClick = {
                    calFile.delete(); impactFile.delete(); calibration = newReport("calibration"); calibrationReady = false; fitReady = false
                    status = getString(R.string.lab_cleared)
                })
                RnEndSpace()
            }
        }
    }

    override fun onStop() { cancel(); super.onStop() }

    private fun newReport(kind: String) = JSONObject().put("schema", "rootnote.acoustic_lab.v1").put("kind", kind)
        .put("protocol_version", AcousticLab.VERSION).put("app_version", BuildConfig.VERSION_NAME)
        .put("model", Build.MODEL).put("manufacturer", Build.MANUFACTURER).put("device", Build.DEVICE)
        .put("os_build", Build.DISPLAY).put("sdk", Build.VERSION.SDK_INT).put("sample_rate_hz", AcousticLab.RATE)
        .put("created_epoch_ms", System.currentTimeMillis()).put("audio_saved", false)
        .put("unprocessed_support_advertised", audio.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true")

    private fun save(file: File, report: JSONObject) {
        val tmp = File(file.parentFile, file.name + ".tmp")
        tmp.writeText(report.toString(2) + "\n")
        check(tmp.renameTo(file)) { "report_write_failed" }
    }

    private fun share(file: File) {
        if (!file.exists()) { status = getString(R.string.lab_no_result); return }
        startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("application/json")
            .putExtra(Intent.EXTRA_SUBJECT, file.name).putExtra(Intent.EXTRA_TEXT, file.readText()), getString(R.string.lab_title)))
    }

    private fun cancel() {
        generation.incrementAndGet(); recorder?.stop()
        try { track?.stop() } catch (_: Exception) {}
        if (busy) status = getString(R.string.lab_cancelled)
        busy = false
        DevTestSound.stop(); PvbRuntime.calibrating = false
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
    }

    private fun launch(work: (Int) -> Unit) {
        if (busy) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 19)
            status = getString(R.string.lab_permission); return
        }
        val token = generation.incrementAndGet()
        expectedVolumeIndex = -1
        busy = true; status = getString(R.string.lab_running)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LOCKED
        PvbRuntime.calibrating = true; DevTestSound.start(DevTestKind.FIT_SILENCE)
        Thread({
            try { work(token) }
            catch (e: Exception) { main.post { if (generation.get() == token) status = getString(R.string.lab_failed, e.message ?: e.javaClass.simpleName) } }
            finally { main.post {
                if (generation.get() == token) {
                    busy = false; DevTestSound.stop(); PvbRuntime.calibrating = false
                    window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                }
            } }
        }, "rootnote-acoustic-lab").start()
    }

    private fun checkRun(token: Int) {
        check(generation.get() == token && !isFinishing) { "cancelled" }
        if (expectedVolumeIndex >= 0) check(audio.getStreamVolume(AudioManager.STREAM_MUSIC) == expectedVolumeIndex) { "system_volume_changed" }
    }
    private fun sources(): List<Int> =
        (if (audio.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true")
            listOf(MediaRecorder.AudioSource.UNPROCESSED) else emptyList()) + MediaRecorder.AudioSource.VOICE_RECOGNITION

    private fun capture(source: Int, seconds: Double, token: Int, onReady: () -> Unit = {}): LabRecorder.Capture {
        val r = LabRecorder(this, source)
        recorder = r
        try { return r.capture(seconds, { checkRun(token) }, onReady) }
        finally { r.close(); if (recorder === r) recorder = null }
    }

    private fun calibrationPhase(phase: String) = launch { token ->
        // Re-measuring ambient invalidates both old phases; no calibration/validation mixing across sessions.
        if (phase == "room") calibration = newReport("calibration").put("phases", JSONObject())
        val report = calibration
        val rows = JSONArray()
        val failed = JSONArray()
        val roomRows = report.optJSONObject("phases")?.optJSONArray("room")
        val selectedSources = if (phase == "room" || roomRows == null) sources() else
            (0 until roomRows.length()).map { roomRows.getJSONObject(it).getInt("source") }
        for (source in selectedSources) {
            checkRun(token)
            main.post { if (generation.get() == token) status = getString(R.string.lab_cal_source,
                getString(if (source == MediaRecorder.AudioSource.UNPROCESSED) R.string.fit_mcal_src_raw else R.string.fit_mcal_src_voice)) }
            val c = try { capture(source, if (phase == "room") 3.0 else 10.0, token) }
            catch (e: Exception) {
                checkRun(token)
                if (phase != "room") throw e
                failed.put(JSONObject().put("source", source).put("error", e.message)); continue
            }
            checkRun(token)
            rows.put(JSONObject().put("source", source).put("path_start", c.start).put("path_end", c.end)
                .put("frequencies_hz", JSONArray(MicCal.BANDS.toList()))
                .put("levels_dbfs", numbers(MicCal.levels(c.samples, AcousticLab.RATE.toDouble()).toList()))
                .put("clipped_samples", c.samples.count { abs(it) >= 0.999f })
                .put("frames", c.samples.size).put("epoch_ms", System.currentTimeMillis()))
        }
        check(rows.length() > 0) { "no_recording_source" }
        if (phase == "room") report.put("unavailable_sources", failed)
        report.getJSONObject("phases").put(phase, rows)
        if (phase == "fit") report.getJSONObject("phases").remove("validation")
        save(calFile, report)
        main.post { if (generation.get() == token) {
            val label = getString(when (phase) { "room" -> R.string.lab_room; "fit" -> R.string.lab_fit; else -> R.string.lab_validation })
            calibrationReady = true; fitReady = report.getJSONObject("phases").has("fit")
            status = getString(R.string.lab_cal_done, label, rows.length())
        } }
    }

    private fun rendered(trial: AcousticLab.Trial): Triple<FloatArray, FloatArray, FloatArray> {
        val fs = AcousticLab.RATE
        val input = AcousticLab.signal(trial) + FloatArray((fs * 0.40).toInt() * 2)
        val output = FloatArray(input.size)
        val params = PvbEngine.defaultParams().apply {
            this[PvbParam.VB_ON] = 1f; this[PvbParam.VB_ALGO] = trial.model.toFloat()
            this[PvbParam.VB_LEVEL_DB] = 4f; this[PvbParam.RAMP_MS] = 0f
            this[PvbParam.OUT_DB] = -5f; this[PvbParam.MATCH_HOLD] = 1f
        }
        val engine = PvbEngine(fs)
        try {
            check(engine.isValid) { "engine_unavailable" }; engine.setParams(params)
            val block = 256; val a = FloatArray(block * 2); val b = FloatArray(block * 2)
            for (at in input.indices step block * 2) {
                val n = minOf(block * 2, input.size - at); input.copyInto(a, 0, at, at + n)
                engine.processFloat(a, b, n); b.copyInto(output, at, 0, n)
            }
            val start = (AcousticLab.MARKER_S * fs).toInt() + engine.latencyFrames
            val marker = FloatArray((AcousticLab.MARKER_LENGTH_S * fs).toInt()) { output[2 * (start + it)] }
            return Triple(output, marker, params)
        } finally { engine.close() }
    }

    private fun play(output: FloatArray, token: Int, error: AtomicReference<Throwable?>): Thread = Thread({
        var player: AudioTrack? = null
        try {
            Thread.sleep(250); checkRun(token)
            val fs = AcousticLab.RATE
            player = AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).setAllowedCapturePolicy(AudioAttributes.ALLOW_CAPTURE_BY_NONE).build())
                .setAudioFormat(AudioFormat.Builder().setSampleRate(fs).setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build())
                .setBufferSizeInBytes(fs / 5 * 8).setTransferMode(AudioTrack.MODE_STREAM).build()
            val speaker = audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS).first { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
            check(player.setPreferredDevice(speaker)) { "speaker_preference_rejected" }
            track = player
            val primed = player.write(output, 0, minOf(9600, output.size), AudioTrack.WRITE_NON_BLOCKING)
            check(primed > 0) { "playback_prime_failed" }
            player.play()
            var at = primed
            while (at < output.size) {
                checkRun(token)
                val n = player.write(output, at, minOf(2048, output.size - at), AudioTrack.WRITE_BLOCKING)
                check(n > 0) { "playback_write_gap:$n" }; at += n
                player.routedDevice?.let { check(it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) { "external_output_route" } }
            }
            // Last submitted samples must actually leave the output buffer before release.
            val deadline = System.nanoTime() + 1_000_000_000L
            while (player.playbackHeadPosition.toLong() < output.size / 2 && System.nanoTime() < deadline) {
                checkRun(token); Thread.sleep(10)
            }
            check(player.playbackHeadPosition.toLong() >= output.size / 2) { "playback_incomplete" }
            check(player.underrunCount == 0) { "playback_underrun" }
            check(player.routedDevice?.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) { "output_route_unknown" }
        } catch (e: Throwable) { error.set(e) }
        finally {
            try { player?.stop() } catch (_: Exception) {}; player?.release()
            if (track === player) track = null
        }
    }, "rootnote-lab-play").also { it.start() }

    private fun impactRun() = launch { token ->
        val seed = SecureRandom().nextLong()
        val report = newReport("impact").put("seed", seed).put("trials", JSONArray()).put("complete", false)
            .put("system_volume_index", audio.getStreamVolume(AudioManager.STREAM_MUSIC))
            .put("system_volume_max", audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC))
            .put("band_hz", JSONArray(listOf(150, 2000))).put("bin_start_relative_s", -0.5).put("bin_seconds", AcousticLab.BIN_S)
            .put("limits", "Recorded speaker-room-body-microphone loop; energy is not identified noise or calibrated SPL/THD. No automatic model winner.")
        val trials = AcousticLab.plan(seed)
        expectedVolumeIndex = report.getInt("system_volume_index")
        val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build())
            .setOnAudioFocusChangeListener { change -> if (change < 0) main.post {
                if (generation.get() == token) cancel()
            } }.build()
        check(audio.requestAudioFocus(focus) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED) { "audio_focus_denied" }
        var selected: Int? = null
        try {
            for ((index, trial) in trials.withIndex()) {
                checkRun(token)
                val (pcm, marker, params) = rendered(trial)
                checkRun(token)
                val playbackError = AtomicReference<Throwable?>(null)
                var playback: Thread? = null
                val volume = report.getInt("system_volume_index")
                var got: LabRecorder.Capture? = null
                val failures = JSONArray()
                // Fallback is allowed before the first trial only; never mix sources inside a comparison.
                for (source in selected?.let { listOf(it) } ?: sources()) {
                    try {
                        got = capture(source, 4.4, token) { playback = play(pcm, token, playbackError) }
                        selected = source; break
                    } catch (e: Exception) {
                        playback?.join(1000)
                        if (selected != null || playback != null) throw e
                        failures.put(JSONObject().put("source", source).put("error", e.message))
                    }
                }
                playback?.join(1000); playbackError.get()?.let { throw IllegalStateException("playback_failed", it) }
                checkRun(token); check(audio.getStreamVolume(AudioManager.STREAM_MUSIC) == volume) { "system_volume_changed" }
                val c = checkNotNull(got) { "no_recording_source" }
                val m = AcousticLab.measure(c.samples, marker, AcousticLab.RATE)
                val row = JSONObject().put("model_id", trial.model).put("input_db", trial.inputDb).put("repeat", trial.repeat)
                    .put("impact", trial.impact).put("source", selected).put("path_start", c.start).put("path_end", c.end)
                    .put("fallback_failures", failures).put("marker_correlation", m.markerCorrelation)
                    .put("marker_frame", m.markerFrame).put("event_frame", m.eventFrame).put("ambient_power", m.ambientPower)
                    .put("window_powers", JSONObject(m.windowPowers)).put("bin_powers", numbers(m.binPowers))
                    .put("recovery_ms", m.recoveryMs ?: JSONObject.NULL).put("clipped_samples", m.clippedSamples)
                    .put("valid", m.complete && m.markerCorrelation >= 0.35 && m.clippedSamples == 0)
                    .put("engine_params", numbers(params.map { it.toDouble() })).put("render_sha256", hash(pcm))
                report.getJSONArray("trials").put(row)
                save(impactFile, report)
                main.post { if (generation.get() == token) status = getString(R.string.lab_progress, index + 1, trials.size) + " · " +
                    getString(if (selected == MediaRecorder.AudioSource.UNPROCESSED) R.string.fit_mcal_src_raw else R.string.fit_mcal_src_voice) }
            }
            report.put("complete", true); save(impactFile, report)
            main.post { if (generation.get() == token) status = getString(R.string.lab_impact_done, trials.size) }
        } finally { audio.abandonAudioFocusRequest(focus) }
    }

    private fun numbers(values: List<Double>) = JSONArray(values.map { if (it.isFinite()) it else JSONObject.NULL })
    private fun hash(x: FloatArray): String {
        val md = MessageDigest.getInstance("SHA-256")
        val bytes = java.nio.ByteBuffer.allocate(x.size * 4).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        x.forEach { bytes.putFloat(it) }
        return md.digest(bytes.array()).joinToString("") { "%02x".format(it) }
    }
}

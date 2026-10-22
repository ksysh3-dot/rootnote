package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTimestamp
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AudioEffect
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/** Optional physical microphone stream. No audio focus, communication mode or feedback into playback. */
class BuzzMicrophone(context: Context) {
    private val manager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val rawSupported = manager.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
    private val source = if (rawSupported) MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
    private val effects = ArrayList<AudioEffect>()
    private val effectInfo = JSONArray()
    private val recorder: AudioRecord
    private var preferredBuiltin = false
    @Volatile private var stopped = false
    @Volatile private var ended = false
    @Volatile private var error = ""
    @Volatile private var absoluteFramesRead = 0L
    @Volatile private var epochCaptureFrame = 0L
    @Volatile var ring: BuzzRing; private set
    val sampleRate: Int
    private val thread: Thread

    init {
        val rate = 48000
        val minimum = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        check(minimum > 0) { "Microphone format unsupported" }
        val builder = AudioRecord.Builder().setAudioSource(source)
            .setAudioFormat(AudioFormat.Builder().setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
            .setBufferSizeInBytes(maxOf(minimum * 2, rate / 5 * 2))
        if (Build.VERSION.SDK_INT >= 30) builder.setPrivacySensitive(false)
        recorder = builder.build()
        try {
            check(recorder.state == AudioRecord.STATE_INITIALIZED)
            val builtin = manager.getDevices(AudioManager.GET_DEVICES_INPUTS).firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC }
            if (builtin != null) preferredBuiltin = recorder.setPreferredDevice(builtin)
            fun disable(name: String, create: () -> AudioEffect?) {
                val info = JSONObject().put("effect", name)
                try {
                    val effect = create()
                    if (effect == null) info.put("client_effect_available", false)
                    else {
                        effects.add(effect)
                        info.put("disable_result", effect.setEnabled(false)).put("enabled_after_request", effect.enabled)
                    }
                } catch (e: Exception) { info.put("request_error", e.javaClass.simpleName) }
                effectInfo.put(info)
            }
            disable("AGC") { if (AutomaticGainControl.isAvailable()) AutomaticGainControl.create(recorder.audioSessionId) else null }
            disable("NS") { if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(recorder.audioSessionId) else null }
            disable("AEC") { if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(recorder.audioSessionId) else null }
            sampleRate = recorder.sampleRate
            ring = newRing()
        } catch (e: Exception) {
            effects.forEach { it.release() }; recorder.release(); throw e
        }
        thread = Thread({ run() }, "pvb-buzz-mic")
    }

    private fun newRing() = BuzzRing(sampleRate, channels = 1, paired = false).apply { armed = true }
    fun start() { thread.start() }
    val running: Boolean get() = !stopped && !ended

    fun restartHistory() { if (running) ring = newRing() }

    fun stop(reason: String = "microphone_stopped") {
        stopped = true; ring.finish(reason)
        try { recorder.stop() } catch (_: Exception) {}
        thread.interrupt()
    }

    private fun run() {
        var epoch: BuzzRing? = null
        val buffer = ShortArray(sampleRate / 50)
        try {
            if (stopped) return
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING)
            while (!stopped) {
                val n = recorder.read(buffer, 0, buffer.size, AudioRecord.READ_BLOCKING)
                if (stopped) break
                if (n <= 0) { error = "read:$n"; ring.finish("microphone_read_gap"); break }
                val r = ring
                if (epoch !== r) { epoch = r; epochCaptureFrame = absoluteFramesRead }
                r.recordShort(buffer, buffer, n, null, -1, -1, Float.NaN, false)
                absoluteFramesRead += n
            }
        } catch (e: Exception) {
            if (!stopped) error = e.javaClass.simpleName
        } finally {
            ended = true; ring.finish(if (error.isEmpty()) "microphone_ended" else "microphone_error")
            try { recorder.stop() } catch (_: Exception) {}
            effects.forEach { try { it.release() } catch (_: Exception) {} }
            recorder.release()
        }
    }

    /** A clock anchor for later correlation; no claim of exact digital/acoustic alignment. */
    fun snapshot(): JSONObject {
        val obj = JSONObject().put("enabled", true).put("running", running)
            .put("sample_rate_hz", sampleRate).put("channels", 1).put("source_id", source)
            .put("source", if (rawSupported) "UNPROCESSED" else "VOICE_RECOGNITION")
            .put("unprocessed_support_advertised", rawSupported).put("client_effect_disable_requests", effectInfo)
            .put("builtin_mic_preference_accepted", preferredBuiltin)
            .put("absolute_frames_read", absoluteFramesRead).put("history_epoch_capture_frame", epochCaptureFrame)
            .put("published_history_frames", ring.recordedFrames)
            .put("observation_monotonic_ns", System.nanoTime()).put("error", error)
            .put("limitations", "Independent input clock/latency, room response and vendor processing; post-mute portion may contain silence or room sound. No calibrated SPL/THD.")
        try {
            recorder.routedDevice?.let { obj.put("routed_device_type", it.type).put("routed_device_name", it.productName.toString()) }
            val timestamp = AudioTimestamp()
            val result = recorder.getTimestamp(timestamp, AudioTimestamp.TIMEBASE_MONOTONIC)
            obj.put("timestamp_result", result)
            if (result == AudioRecord.SUCCESS) obj.put("timestamp_frame", timestamp.framePosition).put("timestamp_monotonic_ns", timestamp.nanoTime)
            if (Build.VERSION.SDK_INT >= 29) recorder.activeRecordingConfiguration?.let {
                obj.put("client_silenced", it.isClientSilenced).put("actual_source", it.audioSource)
            }
        } catch (_: Exception) { obj.put("recorder_observation_unavailable", true) }
        return obj
    }
}

object BuzzMicRuntime {
    @Volatile var capture: BuzzMicrophone? = null
}

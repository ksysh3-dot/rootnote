package me.timschneeberger.rootlessjamesdsp.devmode

import android.content.Context
import android.media.*
import android.media.audiofx.*
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/** One explicit foreground recording. Audio stays in RAM; callers persist only band powers and path metadata. */
internal class LabRecorder(context: Context, val source: Int) : AutoCloseable {
    private val manager = context.getSystemService(AudioManager::class.java)
    private val effects = ArrayList<AudioEffect>()
    private val requests = JSONArray()
    private val rate = 48000
    private val rec: AudioRecord
    @Volatile private var stopped = false

    init {
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        require(min > 0) { "record_format_unsupported" }
        val b = AudioRecord.Builder().setAudioSource(source).setBufferSizeInBytes(maxOf(min * 2, rate / 5 * 2))
            .setAudioFormat(AudioFormat.Builder().setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
        if (Build.VERSION.SDK_INT >= 30) b.setPrivacySensitive(true)
        @Suppress("MissingPermission")
        val built = b.build()
        rec = built
        try {
            check(rec.state == AudioRecord.STATE_INITIALIZED && rec.sampleRate == rate) { "record_initialization_failed" }
            val builtins = manager.getDevices(AudioManager.GET_DEVICES_INPUTS).filter { it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC }
            val preferred = builtins.firstOrNull { it.address.contains("bottom", true) } ?: builtins.firstOrNull()
            preferred?.let { rec.setPreferredDevice(it) }
            fun disable(name: String, create: () -> AudioEffect?) {
                val obj = JSONObject().put("name", name)
                try {
                    create()?.let { e -> effects.add(e); obj.put("result", e.setEnabled(false)).put("enabled", e.enabled) }
                        ?: obj.put("available", false)
                } catch (e: Exception) { obj.put("error", e.javaClass.simpleName) }
                requests.put(obj)
            }
            disable("AGC") { if (AutomaticGainControl.isAvailable()) AutomaticGainControl.create(rec.audioSessionId) else null }
            disable("NS") { if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(rec.audioSessionId) else null }
            disable("AEC") { if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(rec.audioSessionId) else null }
        } catch (e: Exception) { close(); throw e }
    }

    fun snapshot(): JSONObject {
        val o = JSONObject().put("requested_source", source).put("sample_rate_hz", rec.sampleRate)
            .put("encoding", "PCM_16BIT").put("channels", 1).put("client_effect_requests", requests)
        try {
            val config = rec.activeRecordingConfiguration
            o.put("actual_source", config?.audioSource ?: JSONObject.NULL).put("silenced", config?.isClientSilenced ?: false)
            o.put("stream_effects", JSONArray(config?.effects?.map { it.uuid.toString() }.orEmpty().sorted()))
            o.put("client_effects", JSONArray(config?.clientEffects?.map { it.uuid.toString() }.orEmpty().sorted()))
        } catch (_: Exception) { o.put("configuration_unknown", true) }
        try {
            val list = rec.activeMicrophones.sortedBy { it.description }
            o.put("active_mics", JSONArray(list.map { m -> JSONObject().put("id", m.id).put("description", m.description)
                .put("address", m.address).put("type", m.type).put("mapping", JSONArray(m.channelMapping.map { p ->
                    JSONObject().put("channel", p.first).put("kind", p.second)
                })) }))
        } catch (_: Exception) { o.put("active_mics_unknown", true) }
        rec.routedDevice?.let { o.put("input_type", it.type).put("input_id", it.id).put("input_address", it.address) }
        val ts = AudioTimestamp()
        if (rec.getTimestamp(ts, AudioTimestamp.TIMEBASE_MONOTONIC) == AudioRecord.SUCCESS)
            o.put("clock_frame", ts.framePosition).put("clock_ns", ts.nanoTime)
        o.put("monotonic_ns", System.nanoTime())
        o.put("path_key", listOf(source, o.opt("actual_source"), rate, "PCM16/mono", o.opt("input_type"),
            o.opt("input_address"), o.opt("active_mics"), o.opt("stream_effects"), o.opt("client_effects")).joinToString("|"))
        return o
    }

    data class Capture(val samples: FloatArray, val start: JSONObject, val end: JSONObject)

    fun capture(seconds: Double, checkCancelled: () -> Unit, onReady: () -> Unit = {}): Capture {
        rec.startRecording()
        check(rec.recordingState == AudioRecord.RECORDSTATE_RECORDING) { "record_not_running" }
        val buf = ShortArray(rate / 50)
        var skip = rate / 2
        while (skip > 0) {
            checkCancelled(); check(!stopped) { "cancelled" }
            val n = rec.read(buf, 0, minOf(skip, buf.size), AudioRecord.READ_BLOCKING)
            check(n > 0) { "record_read_gap:$n" }; skip -= n
        }
        val start = snapshot()
        check(!start.optBoolean("silenced")) { "record_silenced" }
        check(start.optInt("input_type", AudioDeviceInfo.TYPE_BUILTIN_MIC) == AudioDeviceInfo.TYPE_BUILTIN_MIC) { "external_microphone_route" }
        val out = FloatArray((seconds * rate).toInt())
        onReady()
        var at = 0
        while (at < out.size) {
            checkCancelled(); check(!stopped) { "cancelled" }
            val n = rec.read(buf, 0, minOf(buf.size, out.size - at), AudioRecord.READ_BLOCKING)
            check(n > 0) { "record_read_gap:$n" }
            for (i in 0 until n) out[at + i] = buf[i] / 32768f
            at += n
            if (at % rate < n) {
                val current = snapshot()
                check(!current.optBoolean("silenced")) { "record_silenced" }
                check(current.getString("path_key") == start.getString("path_key")) { "record_route_changed" }
            }
        }
        val end = snapshot()
        check(!end.optBoolean("silenced")) { "record_silenced" }
        check(start.getString("path_key") == end.getString("path_key")) { "record_route_changed" }
        return Capture(out, start, end)
    }

    fun stop() { stopped = true; try { rec.stop() } catch (_: Exception) {} }
    override fun close() {
        stop()
        effects.forEach { try { it.release() } catch (_: Exception) {} }
        try { rec.release() } catch (_: Exception) {}
    }
}

package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * In-app measurement with the phone's own microphone. Plays pink noise through the speaker (not through PVB, and
 * hidden from our own capture), records it and measures:
 *  1. the level of every volume step (quiet noise, so the phone's compressor stays idle): dB per step, and whether
 *     the low end drops at high volume (250 Hz vs 1 kHz band);
 *  2. the phone's compressor in place: level after the phone vs our digital level (-34 .. -10 dBFS), per band;
 *  3. from both, the plan for the output-headroom blind comparison (raise the volume k steps, send X dB less).
 * Only differences between steps matter, so the microphone's own response cancels out.
 */
class PvbMeasure(
    private val context: Context,
    private val onProgress: (String) -> Unit,
    private val onDone: (JSONObject?, String?) -> Unit,
) {
    private val main = Handler(Looper.getMainLooper())
    private val am = context.getSystemService(AudioManager::class.java)

    @Volatile private var cancelled = false
    @Volatile private var playing = true
    @Volatile private var source: PvbMeasureMath.Noise? = null
    @Volatile private var gain = 0.0
    @Volatile private var measTrack: AudioTrack? = null
    private var lastRouteCheck = 0L

    fun start() {
        Thread({ run() }, "pvb-measure").start()
    }

    fun cancel() {
        cancelled = true
    }

    private fun progress(text: String) = main.post { onProgress(text) }

    private class Cancelled : Exception()
    private class RouteChanged : Exception()

    private fun run() {
        val startIndex = am.getStreamVolume(AudioManager.STREAM_MUSIC)
        val maxIndex = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        PvbRuntime.measuring = true
        // if the app dies mid-sweep, the next app or service start puts the volume back
        prefs(context).edit().putInt(KEY_RESTORE, startIndex).commit()
        var track: AudioTrack? = null
        var rec: AudioRecord? = null
        var writer: Thread? = null
        var finalResult: JSONObject? = null
        var error: String? = null
        try {
            val unprocessed = Build.VERSION.SDK_INT >= 24 &&
                am.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
            val micSource = if (unprocessed) MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
            val recBuf = max(AudioRecord.getMinBufferSize(FS, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_FLOAT), FS)
            @Suppress("MissingPermission")
            val r = AudioRecord(micSource, FS, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_FLOAT, recBuf * 4)
            rec = r
            if (r.state != AudioRecord.STATE_INITIALIZED) throw IllegalStateException("마이크를 열 수 없습니다")

            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            if (Build.VERSION.SDK_INT >= 29) attrs.setAllowedCapturePolicy(AudioAttributes.ALLOW_CAPTURE_BY_NONE)
            val t = AudioTrack.Builder()
                .setAudioAttributes(attrs.build())
                .setAudioFormat(
                    AudioFormat.Builder().setSampleRate(FS).setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build(),
                )
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(max(AudioTrack.getMinBufferSize(FS, AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_FLOAT), 4096 * 8))
                .build()
            track = t
            measTrack = t

            progress("준비 중…")
            val quiet = PvbMeasureMath.Noise(FS.toDouble(), 200.0, 8000.0, 11)   // volume steps: 200 Hz - 8 kHz
            val music = PvbMeasureMath.Noise(FS.toDouble(), 100.0, null, 12)      // compressor: like EQ v1.1 output
            gain = 0.0
            source = quiet
            t.play()
            r.startRecording()
            if (r.recordingState != AudioRecord.RECORDSTATE_RECORDING) throw IllegalStateException("마이크 녹음을 시작할 수 없습니다")
            writer = Thread({
                val block = FloatArray(1024 * 2)
                while (playing) {
                    val src = source
                    val g = gain
                    for (i in 0 until 1024) {
                        val v = if (src == null) 0f else (src.next() * g).toFloat()
                        block[2 * i] = v
                        block[2 * i + 1] = v
                    }
                    if (t.write(block, 0, block.size, AudioTrack.WRITE_BLOCKING) < 0) break
                }
            }, "pvb-measure-out").also { it.start() }

            // 0. background (writer plays silence: gain 0); the route must be the built-in speaker
            progress("1/4 주변 소리 재는 중 (조용히 해 주세요)")
            val noise = segment(r, 0.6, 1.2)
            val routed = t.routedDevice
            if (routed != null && routed.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER &&
                routed.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER_SAFE) {
                throw IllegalStateException("출력이 내장 스피커가 아닙니다. 이어폰·블루투스를 끊고 다시 하세요")
            }
            lastRouteCheck = 0L
            check()
            if (noise.bands[PvbMeasureMath.BROAD] < -150) {
                throw IllegalStateException("마이크 소리가 들어오지 않습니다(마이크 차단 또는 화면 꺼짐)")
            }

            // 1. volume steps
            val vol = JSONArray()
            val volDb = DoubleArray(maxIndex + 1) { Double.NaN }
            source = quiet
            gain = 10.0.pow(QUIET_DBFS / 20)
            for (i in 1..maxIndex) {
                check()
                progress("2/4 볼륨 단계 재는 중: $i / $maxIndex")
                am.setStreamVolume(AudioManager.STREAM_MUSIC, i, 0)
                val got = am.getStreamVolume(AudioManager.STREAM_MUSIC)
                val s = stable(r)
                val snr = s.bands[PvbMeasureMath.BROAD] - noise.bands[PvbMeasureMath.BROAD]
                val point = JSONObject().apply {
                    put("index", i)
                    put("readback", got)
                    put("stable", s.stable)
                    put("fine", fineVolume())
                    put("level_db", r1(s.bands[PvbMeasureMath.BROAD]))
                    put("snr_db", r1(snr))
                    put("mic_peak", r3(s.peak))
                    put("bands_db", JSONArray(s.bands.take(PvbMeasureMath.BROAD).map { r1(it) }))
                }
                // the same rule (on the same rounded values) as volumeTable() applies to the saved JSON later
                if (accepted(point, i)) volDb[i] = point.getDouble("level_db")
                vol.put(point)
            }

            // 2. the phone's compressor (level after the phone vs our digital level), at a volume with enough signal
            val compIndex = min(maxIndex, max(startIndex, COMP_MIN_INDEX))
            am.setStreamVolume(AudioManager.STREAM_MUSIC, compIndex, 0)
            val compReadback = am.getStreamVolume(AudioManager.STREAM_MUSIC)
            source = music
            val comp = JSONArray()
            val compP = ArrayList<Double>()
            val compL = ArrayList<Double>()
            for ((n, p) in COMP_DBFS.withIndex()) {
                check()
                progress("3/4 폰 압축 재는 중: ${n + 1} / ${COMP_DBFS.size}")
                gain = 10.0.pow(p / 20)
                val s = stable(r)
                val snr = s.bands[PvbMeasureMath.BROAD] - noise.bands[PvbMeasureMath.BROAD]
                val point = JSONObject().apply {
                    put("digital_dbfs", p)
                    put("readback", am.getStreamVolume(AudioManager.STREAM_MUSIC))
                    put("stable", s.stable)
                    put("level_db", r1(s.bands[PvbMeasureMath.BROAD]))
                    put("snr_db", r1(snr))
                    put("mic_peak", r3(s.peak))
                    put("bands_db", JSONArray(s.bands.take(PvbMeasureMath.BROAD).map { r1(it) }))
                }
                if (accepted(point, compIndex)) {
                    compP += p
                    compL += point.getDouble("level_db")
                }
                comp.put(point)
            }
            gain = 0.0

            val validSteps = volDb.count { !it.isNaN() }
            if (validSteps < 5 || compP.size < 3 || compReadback != compIndex) {
                throw IllegalStateException("믿을 만한 측정점이 부족합니다(볼륨 ${validSteps}개, 압축 ${compP.size}개). 음악을 멈추고 조용한 곳에서 다시 하세요")
            }

            // 4. check the output-headroom plan for the starting volume with the microphone: noise at the usual
            // level at the start volume vs X dB less at k steps up should arrive equally loud
            var verify: JSONObject? = null
            val plan = PvbMeasureMath.stagePlan(volDb, startIndex, compP.toDoubleArray(), compL.toDoubleArray())
            if (plan != null) {
                check()
                progress("4/4 출력 여유 계획 확인 중")
                source = music
                am.setStreamVolume(AudioManager.STREAM_MUSIC, startIndex, 0)
                val rbA = am.getStreamVolume(AudioManager.STREAM_MUSIC)
                gain = 10.0.pow(P0_DBFS / 20)
                val a = stable(r)
                am.setStreamVolume(AudioManager.STREAM_MUSIC, startIndex + plan.steps, 0)
                val rbB = am.getStreamVolume(AudioManager.STREAM_MUSIC)
                gain = 10.0.pow((P0_DBFS - plan.outDropDb) / 20)
                val b = stable(r)
                gain = 0.0
                val la = r1(a.bands[PvbMeasureMath.BROAD])
                val lb = r1(b.bands[PvbMeasureMath.BROAD])
                val aOk = PvbMeasureMath.acceptPoint(a.stable, rbA == startIndex, la - noise.bands[PvbMeasureMath.BROAD], r3(a.peak), la)
                val bOk = PvbMeasureMath.acceptPoint(b.stable, rbB == startIndex + plan.steps, lb - noise.bands[PvbMeasureMath.BROAD], r3(b.peak), lb)
                val residual = r1(lb - la)
                verify = JSONObject().apply {
                    put("base_index", startIndex)
                    put("steps", plan.steps)
                    put("out_drop_db", r1(plan.outDropDb))
                    put("residual_db", residual)
                    put("sides_ok", aOk && bOk)
                    put("tolerance_db", PvbMeasureMath.STAGE_TOL_DB)
                    put("ok", PvbMeasureMath.stageCheckOk(startIndex, startIndex, plan.steps, plan.steps, r1(plan.outDropDb),
                        plan.outDropDb, aOk && bOk, residual))
                }
            }

            val result = JSONObject().apply {
                put("time", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date()))
                put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
                put("route", "speaker")   // checked at every step; a route change aborts the measurement
                put("mic_source", if (unprocessed) "unprocessed" else "voice_recognition")
                put("start_index", startIndex)
                put("max_index", maxIndex)
                put("comp_index", compIndex)
                put("noise_bands_db", JSONArray(noise.bands.map { r1(it) }))
                put("band_hz", JSONArray(PvbMeasureMath.BAND_HZ.toList()))
                put("quiet_dbfs", QUIET_DBFS)
                put("volume", vol)
                put("compressor", comp)
                put("p0_dbfs", P0_DBFS)
                verify?.let { put("stage_check", it) }
            }
            save(context, result)
            finalResult = result
        } catch (e: Cancelled) {
            error = "중단했습니다."
        } catch (e: RouteChanged) {
            error = "출력 장치가 바뀌어 측정을 중단했습니다. 내장 스피커로만 측정할 수 있습니다."
        } catch (e: Exception) {
            error = "측정 실패: ${e.message ?: e.javaClass.simpleName}"
        } finally {
            playing = false
            gain = 0.0
            measTrack = null
            try { writer?.join(500) } catch (ignored: Exception) {}
            try { track?.pause() } catch (ignored: Exception) {}
            try { track?.release() } catch (ignored: Exception) {}
            try { rec?.stop() } catch (ignored: Exception) {}
            try { rec?.release() } catch (ignored: Exception) {}
            // the restore key is cleared only once the phone reports the old volume again
            val restored = restoreVolume(am, startIndex)
            if (restored) prefs(context).edit().remove(KEY_RESTORE).apply()
            PvbRuntime.measuring = false
            val warn = if (restored) null else "볼륨을 ${startIndex}단계로 되돌리지 못했습니다. 직접 맞춰 주세요."
            val r = finalResult
            val msg = listOfNotNull(error, warn).joinToString(" ").ifEmpty { null }
            main.post { onDone(r, msg) }
        }
    }

    /** Stops at a cancel request, and when the sound no longer goes to the built-in speaker. */
    private fun check() {
        if (cancelled) throw Cancelled()
        val now = SystemClock.elapsedRealtime()
        if (now - lastRouteCheck < ROUTE_CHECK_MS) return
        lastRouteCheck = now
        val routed = try { measTrack?.routedDevice } catch (ignored: Exception) { null }
        if (routed != null && routed.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER &&
            routed.type != AudioDeviceInfo.TYPE_BUILTIN_SPEAKER_SAFE) throw RouteChanged()
        val external = try {
            am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).any { it.type in EXTERNAL_OUTPUTS }
        } catch (ignored: Exception) {
            false
        }
        if (external) throw RouteChanged()
    }

    private class Segment(val bands: DoubleArray, val peak: Double, val stable: Boolean = true)

    /** Two consecutive 0.5 s windows after 0.45 s; up to 3 tries until their levels agree within 0.3 dB. */
    private fun stable(r: AudioRecord): Segment {
        read(r, (0.45 * FS).toInt(), null)
        var prev = segment(r, 0.0, 0.5)
        repeat(3) {
            val cur = segment(r, 0.0, 0.5)
            if (kotlin.math.abs(cur.bands[PvbMeasureMath.BROAD] - prev.bands[PvbMeasureMath.BROAD]) <= 0.3) {
                val bands = DoubleArray(cur.bands.size) {
                    PvbMeasureMath.db((10.0.pow(cur.bands[it] / 10) + 10.0.pow(prev.bands[it] / 10)) / 2)
                }
                return Segment(bands, max(cur.peak, prev.peak), true)
            }
            prev = cur
        }
        return Segment(prev.bands, prev.peak, false)
    }

    /** Reads and drops [settleS] seconds, then analyses the next [lengthS] seconds of the microphone. */
    private fun segment(r: AudioRecord, settleS: Double, lengthS: Double): Segment {
        read(r, (settleS * FS).toInt(), null)
        val n = (lengthS * FS).toInt()
        val buf = FloatArray(n)
        read(r, n, buf)
        return Segment(PvbMeasureMath.bandLevels(buf, 0, n, FS.toDouble()), PvbMeasureMath.peak(buf, 0, n))
    }

    private fun read(r: AudioRecord, n: Int, into: FloatArray?) {
        val tmp = FloatArray(2048)
        var got = 0
        while (got < n) {
            check()
            val want = min(tmp.size, n - got)
            val k = r.read(tmp, 0, want, AudioRecord.READ_BLOCKING)
            if (k <= 0) throw IllegalStateException("마이크 읽기 오류 $k")
            into?.let { System.arraycopy(tmp, 0, it, got, k) }
            got += k
        }
    }

    private fun fineVolume(): String = try {
        Settings.System.getString(context.contentResolver, "volume_music_speaker") ?: ""
    } catch (ignored: Exception) {
        ""
    }

    companion object {
        const val FS = 48000
        private const val QUIET_DBFS = -30.0
        private val COMP_DBFS = doubleArrayOf(-34.0, -30.0, -26.0, -22.0, -18.0, -14.0, -10.0)
        private const val COMP_MIN_INDEX = 7
        private const val ROUTE_CHECK_MS = 100L
        private const val PREFS = "pvb_measure"
        private const val KEY_LAST = "last"
        private const val KEY_RESTORE = "restore_volume"
        private const val P0_DBFS = -18.0   // usual RMS of EQ v1.1 output (album study)

        private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        /** Outputs that end a measurement (the measurement is for the built-in speaker only). */
        val EXTERNAL_OUTPUTS = setOf(
            AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_BLUETOOTH_A2DP,
            AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLE_SPEAKER, AudioDeviceInfo.TYPE_USB_HEADSET,
            AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_HEARING_AID,
        )

        /** Sets the music volume and checks that the phone took it (a few tries). */
        fun restoreVolume(am: AudioManager, index: Int): Boolean {
            repeat(3) {
                try {
                    am.setStreamVolume(AudioManager.STREAM_MUSIC, index, 0)
                    if (am.getStreamVolume(AudioManager.STREAM_MUSIC) == index) return true
                } catch (ignored: Exception) {
                }
                try { Thread.sleep(50) } catch (ignored: InterruptedException) { return false }
            }
            return false
        }

        /**
         * A measurement was cut off by the app dying: put the volume back (called at app and service start). The key
         * is kept until the phone reports the old volume, so a refused restore is tried again next time.
         */
        fun restoreIfInterrupted(context: Context) {
            if (PvbRuntime.measuring) return
            val p = prefs(context)
            val v = p.getInt(KEY_RESTORE, -1)
            if (v < 0) return
            if (restoreVolume(context.getSystemService(AudioManager::class.java), v)) p.edit().remove(KEY_RESTORE).apply()
        }

        /** The acceptance rule of [PvbMeasureMath.acceptPoint] applied to a saved point (volume index [index]). */
        fun accepted(o: JSONObject, index: Int): Boolean = PvbMeasureMath.acceptPoint(
            stable = o.optBoolean("stable", false),
            readbackOk = !o.has("readback") || o.optInt("readback", -1) == index,
            snrDb = o.optDouble("snr_db", Double.NaN),
            micPeak = o.optDouble("mic_peak", Double.NaN),
            levelDb = o.optDouble("level_db", Double.NaN),
        )

        private fun r1(v: Double) = Math.round(v * 10) / 10.0
        private fun r3(v: Double) = Math.round(v * 1000) / 1000.0

        fun save(context: Context, result: JSONObject) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_LAST, result.toString()).apply()
        }

        fun load(context: Context): JSONObject? = try {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_LAST, null)?.let { JSONObject(it) }
        } catch (ignored: Exception) {
            null
        }

        /** Level per volume index from a result (NaN where the point is not accepted, see [accepted]). */
        fun volumeTable(result: JSONObject): DoubleArray {
            val max = result.optInt("max_index", 15)
            val out = DoubleArray(max + 1) { Double.NaN }
            val arr = result.optJSONArray("volume") ?: return out
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val idx = o.optInt("index", -1)
                if (idx in out.indices && accepted(o, idx)) out[idx] = o.optDouble("level_db", Double.NaN)
            }
            return out
        }

        /** Accepted compressor points (sorted by digital level). */
        private fun compressorPoints(result: JSONObject): List<JSONObject> {
            val arr = result.optJSONArray("compressor") ?: return emptyList()
            val comp = result.optInt("comp_index", -1)
            return (0 until arr.length()).map { arr.getJSONObject(it) }
                .filter { it.has("digital_dbfs") && accepted(it, comp) }
                .sortedBy { it.getDouble("digital_dbfs") }
        }

        /** Level after the phone vs our digital level (accepted points only; empty if they do not form a curve). */
        fun compressorCurve(result: JSONObject): Pair<DoubleArray, DoubleArray> {
            val pts = compressorPoints(result)
            val p = pts.map { it.getDouble("digital_dbfs") }.toDoubleArray()
            val l = pts.map { it.getDouble("level_db") }.toDoubleArray()
            return if (PvbMeasureMath.curveUsable(p, l)) p to l else DoubleArray(0) to DoubleArray(0)
        }

        fun stagePlan(result: JSONObject, base: Int): PvbMeasureMath.StagePlan? {
            val (p, l) = compressorCurve(result)
            return PvbMeasureMath.stagePlan(volumeTable(result), base, p, l)
        }

        class CheckedPlan(val plan: PvbMeasureMath.StagePlan?, val reason: String)

        /**
         * The output-headroom plan for volume [base], only if the measurement's microphone check confirmed exactly that
         * plan at that volume on the speaker (both sides accepted, within [PvbMeasureMath.STAGE_TOL_DB]).
         */
        fun checkedStagePlan(result: JSONObject, base: Int): CheckedPlan {
            val plan = stagePlan(result, base) ?: return CheckedPlan(null,
                "지금 볼륨(${base}단계)에서는 측정 결과로 크기를 맞출 수 없습니다. 볼륨을 조금 바꾸거나 다시 측정해 보세요.")
            val c = result.optJSONObject("stage_check") ?: return CheckedPlan(null,
                "이 측정에는 출력 여유 계획을 마이크로 확인한 결과가 없습니다. 지금 볼륨(${base}단계)에서 다시 측정하세요.")
            val cb = c.optInt("base_index", -1)
            if (cb != base) return CheckedPlan(null,
                "출력 여유 계획은 ${cb}단계에서 확인했습니다. 볼륨을 ${cb}단계로 맞추거나 지금 볼륨에서 다시 측정하세요.")
            if (result.optString("route", "speaker") != "speaker") return CheckedPlan(null, "내장 스피커에서 잰 측정이 아닙니다.")
            val ok = PvbMeasureMath.stageCheckOk(base, cb, c.optInt("steps", -1), plan.steps,
                c.optDouble("out_drop_db", Double.NaN), plan.outDropDb, c.optBoolean("sides_ok", false),
                c.optDouble("residual_db", Double.NaN))
            if (!ok) return CheckedPlan(null, "측정 확인에서 두 쪽 크기가 ${fmt(c.optDouble("residual_db", Double.NaN))} dB 달랐습니다" +
                "(허용 ±${PvbMeasureMath.STAGE_TOL_DB} dB). 조용한 곳에서 다시 측정해 보세요.")
            return CheckedPlan(plan, "")
        }

        /** Plain-language summary for the card. */
        fun summary(result: JSONObject, base: Int): String {
            val lines = ArrayList<String>()
            val max = result.optInt("max_index", 15)
            val start = result.optInt("start_index", base)
            val vol = volumeTable(result)
            lines += "측정 ${result.optString("time")} · 마이크 ${if (result.optString("mic_source") == "unprocessed") "원음" else "음성 인식용"}"
            val ref = if (start in vol.indices && !vol[start].isNaN()) start else vol.indices.firstOrNull { !vol[it].isNaN() } ?: -1
            if (ref < 0) {
                lines += "볼륨 단계: 신호가 주변 소리보다 충분히 크지 않아 잴 수 없었습니다."
            } else {
                lines += "볼륨 단계별 크기 (${ref}단계 기준, dB):"
                val row = StringBuilder()
                for (i in 1..max) {
                    val v = vol[i]
                    row.append(if (v.isNaN()) " $i:—" else " $i:${fmt(v - vol[ref])}")
                    if (i % 5 == 0) { lines += " " + row.toString().trim(); row.setLength(0) }
                }
                if (row.isNotEmpty()) lines += " " + row.toString().trim()
                // low end vs volume: 250 Hz band minus 1 kHz band, relative to the reference step
                val arr = result.optJSONArray("volume")
                if (arr != null) {
                    var refTilt = Double.NaN
                    val tilts = HashMap<Int, Double>()
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)
                        val idx = o.getInt("index")
                        if (idx !in vol.indices || vol[idx].isNaN()) continue
                        val b = o.getJSONArray("bands_db")
                        if (bandOk(result, b, 1) && bandOk(result, b, 3)) tilts[idx] = b.getDouble(1) - b.getDouble(3)
                    }
                    refTilt = tilts[ref] ?: Double.NaN
                    if (!refTilt.isNaN()) {
                        val hi = tilts.keys.filter { it > ref }.sorted()
                        if (hi.isNotEmpty()) {
                            lines += "볼륨을 올릴 때 저음(250 Hz) 대 1 kHz 변화: " +
                                hi.filter { it == hi.last() || it % 3 == 0 }.joinToString(", ") { "${it}단계 ${fmt(tilts[it]!! - refTilt)}" } + " dB"
                        }
                    }
                }
            }
            val (p, l) = compressorCurve(result)
            if (p.size >= 3) {
                val loss = { x: Double -> PvbMeasureMath.interp(p, l, -18.0) - PvbMeasureMath.interp(p, l, -18.0 - x) }
                lines += "폰 압축 (분홍 잡음): 앱 출력을 10 dB 줄이면 폰 뒤 소리는 ${fmt1(loss(10.0))} dB 줄어듭니다 (압축이 없으면 10)."
                // per band, from accepted points only (the same ones as the curve above): change from the quietest
                // accepted point (<= -30 dBFS) to -18 dBFS (interpolated if -18 itself was rejected), minus the input change
                val pts = compressorPoints(result)
                val pp = pts.map { it.getDouble("digital_dbfs") }.toDoubleArray()
                val lo = pp.firstOrNull()
                if (lo != null && lo <= -30.0 && pp.last() >= -18.0) {
                    val names = listOf("125", "250", "500", "1k", "2k", "4k")
                    lines += "대역별 눌림 (${fmt1(lo)} → −18 dBFS, 받아들인 측정점만, dB): " + names.indices.joinToString(" ") { b ->
                        val bl = pts.first().getJSONArray("bands_db")
                        if (pts.all { bandOk(result, it.getJSONArray("bands_db"), b) }) {
                            val lb = pts.map { it.getJSONArray("bands_db").getDouble(b) }.toDoubleArray()
                            val change = PvbMeasureMath.interp(pp, lb, -18.0) - bl.getDouble(b)
                            "${names[b]} ${fmt1((-18.0 - lo) - change)}"
                        } else "${names[b]} —"
                    }
                }
            } else {
                lines += "폰 압축: 신호가 충분히 크지 않아 잴 수 없었습니다."
            }
            result.optJSONObject("stage_check")?.let {
                val pass = it.optBoolean("ok", false)
                lines += "출력 여유 계획 확인(${it.optInt("base_index")}단계에서 마이크로): 두 쪽 크기 차이 " +
                    "${fmt(it.optDouble("residual_db"))} dB → ${if (pass) "통과" else "불합격"} (허용 ±${PvbMeasureMath.STAGE_TOL_DB} dB)"
            }
            val checked = checkedStagePlan(result, base)
            val plan = checked.plan
            lines += if (plan != null) {
                "출력 여유 비교(지금 ${base}단계에서): 볼륨 +${plan.steps}단계(+${fmt1(plan.volumeGainDb)} dB), 앱 출력 −${fmt1(plan.outDropDb)} dB"
            } else {
                "출력 여유 비교: ${checked.reason}"
            }
            lines += "이 측정은 블라인드 비교용입니다. 실시간 볼륨 연동 보정에는 쓰이지 않습니다."
            return lines.joinToString("\n")
        }

        /** Band [i] of [bands] is at least 10 dB above the background in that band. */
        private fun bandOk(result: JSONObject, bands: JSONArray, i: Int): Boolean {
            val noise = result.optJSONArray("noise_bands_db") ?: return true
            return bands.getDouble(i) - noise.getDouble(i) >= 10.0
        }

        private fun fmt(v: Double) = String.format(Locale.US, "%+.1f", v)
        private fun fmt1(v: Double) = String.format(Locale.US, "%.1f", v)
    }
}

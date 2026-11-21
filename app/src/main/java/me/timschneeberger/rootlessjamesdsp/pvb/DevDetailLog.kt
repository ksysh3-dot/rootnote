package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.media.MediaMetadata
import android.media.session.PlaybackState
import android.os.SystemClock
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.session.shared.BaseSessionManager
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.Writer
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

/**
 * Developer-mode detailed debug log, for offline (AI) analysis. Off by default; developer menu toggle.
 *
 * Every 250 ms on its own thread it copies the engine's developer meters ([PvbEngine.copyDevMeters]) and appends the
 * 5 ms ring bins written since the last copy, so the file holds every bin without gaps while the meters run
 * (the ring holds 2.56 s). The audio thread is never touched beyond the existing lock-free meter copy; no audio is
 * stored, only levels and tracker decisions. Each poll also stores the instantaneous developer fields (held tracks,
 * harmonic levels), and once a second the runtime status. Files: filesDir/dev_detail_log/, JSONL, one file per
 * processing session and at most [FILE_MINUTES] minutes, oldest files removed above [MAX_TOTAL_BYTES].
 *
 * Bin fields (arrays, oldest first, 0.1 dB): common = common input low band, gen = generator (synth) input low band,
 * req = layer before the dedicated layer control, act = layer after it (what plays), f0 = tracked fundamental Hz
 * (0 = none), reason = observation reason bits, state = track state (1 new, 2 held observed,
 * 3 held estimated, -1 no valid track, 0 waiting), final_gr = final limiter gain reduction dB, layer_gr = dedicated
 * layer reduction dB. Detail of the strongest track at its latest hop (COMBO): miss = hops without a new
 * observation, life = life gain, lv_T / lv_J / lv_mix = the three terms of the level rule A = min(T, G*sqrt(2J), mix)
 * in dB and lv_win the one that won (0 T, 1 J, 2 mix, -1 not COMBO), lv_med = level after the 5-hop median,
 * age_db = start attenuation (<= 0), x35_db = expander loss (>= 0), amp = final track amplitude dB, fade = track fade 0..1 (COMBO plays a*gain*fade*life;
 * no per-harmonic permission); n_trk = live tracks; f2/a2, f3/a3 = second and third loudest tracks
 * (Hz, dB). decay_db is the added downward extrapolation loss before the median, in dB. lv_pred is the resulting amplitude in dB. Values are held between hops. The bin index "c0" counts bins since the engine's meter reset; a reset or a gap is a line
 * {"type":"gap"}. Once a second a "media" line gives each player's song and playback position (notification access
 * needed). A blind comparison pauses the log (nothing that reveals it is written).
 */
class DevDetailLog(
    private val context: Context,
    private val engine: PvbEngine,
    private val sessions: BaseSessionManager? = null,
) : AutoCloseable {
    private var lastNoAccessMs = 0L
    @Volatile var enabled = false
        private set
    private var exec: ScheduledExecutorService? = null
    private var out: Writer? = null
    private var file: File? = null
    private var fileStartMs = 0L
    private var lastCount = -1L
    private var polls = 0L
    private val buf = FloatArray(PvbDevMeter.SIZE)

    fun start() {
        if (!BuildConfig.RECORD_FEATURES) return
        check(exec == null)
        val p = context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        if (!p.getBoolean(PREF, false)) return
        enabled = true
        lastCount = -1L
        PvbRuntime.setDevLog(true)
        exec = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "dev-detail-log") }.also {
            it.scheduleAtFixedRate({ poll() }, 250, 250, TimeUnit.MILLISECONDS)
        }
    }

    private fun dir() = File(context.filesDir, DIR)

    private fun openFile(now: Long) {
        out?.close()
        val d = dir(); d.mkdirs()
        val f = File(d, "devlog-$now.jsonl")
        file = f; fileStartMs = now
        out = f.bufferedWriter(Charsets.UTF_8)
        val s = PvbSettings.load(context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE))
        line(JSONObject().put("type", "header").put("schema", "rootnote.devlog.v3").put("utc_ms", now)
            .put("build_id", BuildConfig.COMMIT_SHA).put("build_time", BuildConfig.BUILD_TIME)
            .put("package_id", context.packageName).put("sample_rate_hz", engine.sampleRateHz)
            .put("bass_mode", s.bassMode)
            .put("bin_fields", JSONArray(BIN_FIELDS)).put("ring_bins", PvbDevMeter.RING)
            .put("dev_fields_layout", "PvbDevMeter: F0, H2..H8 dB, DRY_BAND_DB, LAYER_BAND_DB, RING_COUNT, RING_BIN_MS, " +
                "GAIN, BOUNDARY_HZ, OUT_LO_HZ, OUT_HI_HZ, T2_F0, T2_H2..H8, T3_F0, T3_H2..H8")
            .put("note", "levels and tracker decisions only; no audio. Bins are aligned to the original (dry) time."))
        prune()
    }

    private fun line(o: JSONObject) { out?.apply { write(o.toString()); write(10) } }

    private fun r1(v: Float): Any = if (v.isFinite()) Math.round(v * 10f) / 10.0 else JSONObject.NULL

    private fun poll() {
        try {
            if (PvbRuntime.abActive) { lastCount = -1L; return }
            if (!engine.copyDevMeters(buf)) return
            val now = System.currentTimeMillis()
            if (out == null || now - fileStartMs > FILE_MINUTES * 60_000L) openFile(now)
            val count = buf[PvbDevMeter.RING_COUNT].toLong()  // wraps at 1e6
            val ring = PvbDevMeter.RING
            var fresh = if (lastCount < 0) 0L else ((count - lastCount) % 1_000_000L + 1_000_000L) % 1_000_000L
            if (lastCount >= 0 && (count < lastCount && lastCount - count < 900_000L)) {
                line(JSONObject().put("type", "gap").put("utc_ms", now).put("why", "meter reset").put("count", count))
                fresh = minOf(count, ring.toLong())
            } else if (fresh > ring) {
                line(JSONObject().put("type", "gap").put("utc_ms", now).put("why", "poll late").put("lost_bins", fresh - ring))
                fresh = ring.toLong()
            }
            lastCount = count
            if (fresh > 0) {
                val n = fresh.toInt()
                val first = ring - n  // oldest-first layout: the newest n entries are at the end
                val arrays = Array(BIN_FIELDS.size) { JSONArray() }
                for (i in first until ring) {
                    val st = PvbDevMeter.STAGE_START + i * PvbDevMeter.STAGE_FIELDS
                    arrays[0].put(r1(buf[st + 0])); arrays[1].put(r1(buf[st + 1])); arrays[2].put(r1(buf[st + 2]))
                    arrays[3].put(r1(buf[PvbDevMeter.FIELDS + 2 * i + 1]))
                    arrays[4].put(r1(buf[st + 3])); arrays[5].put(buf[st + 4].toInt())  // st + 5 (fit residual) unused by COMBO
                    arrays[6].put(buf[st + 6].toInt()); arrays[7].put(r1(buf[st + 7])); arrays[8].put(r1(buf[st + 8]))
                    for (k in 0 until DETAIL_FIELDS.size) {  // engine stage fields 9..26
                        val v = buf[st + 9 + k]
                        arrays[9 + k].put(if (k == 0 || k == 9 || k == 11) v.toInt() else if (k == 10) Math.round(v * 1000f) / 1000.0 else r1(v))
                    }
                }
                val o = JSONObject().put("type", "bins").put("utc_ms", now).put("c0", count - n).put("n", n)
                    .put("bin_ms", r1(buf[PvbDevMeter.RING_BIN_MS]))
                BIN_FIELDS.forEachIndexed { k, name -> o.put(name, arrays[k]) }
                line(o)
            }
            val dev = JSONArray()
            for (i in 0 until PvbDevMeter.FIELDS) dev.put(r1(buf[i]))
            line(JSONObject().put("type", "dev").put("utc_ms", now).put("count", count).put("v", dev))
            if (++polls % 4 == 0L) {
                line(JSONObject().put("type", "status").put("utc_ms", now).put("status", PvbRuntime.status.toString()))
                media(now)
                out?.flush()
            }
        } catch (e: Exception) { android.util.Log.e("devlog", "poll failed", e) }
    }

    /**
     * Once a second: the song each media session reports and its playback position now (extrapolated from the
     * session's last position report), so bins can be matched to a place in the song. Needs notification access;
     * without it one line a minute says so.
     */
    private fun media(now: Long) {
        val s = sessions ?: return
        if (!s.hasNotificationAccess()) {
            if (now - lastNoAccessMs >= 60_000L) {
                lastNoAccessMs = now
                line(JSONObject().put("type", "media").put("utc_ms", now).put("access", false)
                    .put("note", "notification access is off: song and position unknown"))
            }
            return
        }
        val players = JSONArray()
        for (c in s.activeMediaControllers()) {
            try {
                val st = c.playbackState
                val md = c.metadata
                fun text(key: String): String? = md?.getText(key)?.toString()?.takeIf { it.isNotBlank() }
                val playing = st?.state == PlaybackState.STATE_PLAYING
                var pos = st?.position ?: -1L
                if (playing && pos >= 0 && st != null && st.lastPositionUpdateTime > 0)
                    pos += ((SystemClock.elapsedRealtime() - st.lastPositionUpdateTime) * st.playbackSpeed).toLong()
                players.put(JSONObject().put("package", c.packageName)
                    .put("title", text(MediaMetadata.METADATA_KEY_TITLE) ?: text(MediaMetadata.METADATA_KEY_DISPLAY_TITLE) ?: JSONObject.NULL)
                    .put("artist", text(MediaMetadata.METADATA_KEY_ARTIST) ?: text(MediaMetadata.METADATA_KEY_ALBUM_ARTIST) ?: JSONObject.NULL)
                    .put("album", text(MediaMetadata.METADATA_KEY_ALBUM) ?: JSONObject.NULL)
                    .put("duration_ms", md?.getLong(MediaMetadata.METADATA_KEY_DURATION) ?: JSONObject.NULL)
                    .put("state", st?.state ?: JSONObject.NULL).put("playing", playing)
                    .put("position_ms", if (pos >= 0) pos else JSONObject.NULL))
            } catch (_: Exception) { }  // a session can die at any time
        }
        line(JSONObject().put("type", "media").put("utc_ms", now).put("access", true).put("players", players))
    }

    private fun prune() {
        val files = dir().listFiles()?.filter { it.extension == "jsonl" }?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (f in files) {
            if (total <= MAX_TOTAL_BYTES || f == file) continue
            total -= f.length(); f.delete()
        }
    }

    /** Called with audio stopped, before the next model is prepared or the engine is closed. */
    override fun close() {
        if (!enabled) return
        enabled = false
        val e = exec ?: return
        exec = null
        try {
            e.submit { poll(); out?.flush(); out?.close(); out = null }.get(5, TimeUnit.SECONDS)
        } catch (x: Exception) { android.util.Log.e("devlog", "close failed", x) }
        e.shutdownNow()
        PvbRuntime.setDevLog(false)
    }

    companion object {
        const val PREF = "pvb_dev_detail_log"
        const val DIR = "dev_detail_log"
        private const val FILE_MINUTES = 15
        private const val MAX_TOTAL_BYTES = 300L * 1024 * 1024
        /** Strongest track's level rule and tracker detail, then the other tracks (engine stage fields 9..26). */
        val DETAIL_FIELDS = listOf("miss", "life", "lv_T", "lv_J", "lv_mix", "lv_med", "age_db", "x35_db", "amp",
            "lv_win", "fade", "n_trk", "f2", "a2", "f3", "a3", "decay_db", "lv_pred")
        val BIN_FIELDS = listOf("common", "gen", "req", "act", "f0", "reason", "state", "final_gr", "layer_gr") +
            DETAIL_FIELDS
    }
}

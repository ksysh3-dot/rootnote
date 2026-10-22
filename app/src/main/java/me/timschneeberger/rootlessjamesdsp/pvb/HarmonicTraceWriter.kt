package me.timschneeberger.rootlessjamesdsp.pvb

import org.json.JSONArray
import org.json.JSONObject
import java.security.DigestOutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Streaming export; usable without Android service/Context. */
object HarmonicTraceWriter {
    /** Worker only: one JSON object at a time, never materialize all hops as a DOM. */
    fun write(zip: ZipOutputStream, r: BuzzRing, report: JSONObject, hashes: JSONObject) {
        val history = r.harmonicHistory ?: return
        val w = r.window()
        val contextStart = maxOf(0L, w.start - r.sampleRate / 50)
        val digest = MessageDigest.getInstance("SHA-256")
        zip.putNextEntry(ZipEntry("harmonics.jsonl"))
        val stream = DigestOutputStream(zip, digest)
        fun line(value: JSONObject) { stream.write(value.toString().toByteArray(Charsets.UTF_8)); stream.write(10) }
        val headerNames = arrayOf("callback_frame_offset", "algorithm", "reset_epoch", "core_index_u16_0", "core_index_u16_1", "core_index_u16_2", "core_index_u16_3",
            "analysis_start_offset_core", "hpss_delay_core", "source_center_offset_host", "nominal_output_grain_center_offset_host",
            "observed_tracks", "ending_tracks", "frame_reasons", "maximum_peak_amplitude", "harmonic_power", "percussion_power",
            "envelope_gain", "poly_envelope", "raw_vocoder_sample", "grain_rms", "omitted_candidates", "lost_tracks", "wire_version", "onset_hold_hops", "falling_amplitude", "residual_hold_count", "reserved0")
        val trackNames = arrayOf("id_u16_low", "state", "frequency_hz", "frequency_slope_hz_s", "analysis_amplitude", "phase_rad", "residual_db", "fit_fade", "age_hops", "missing_hops", "reasons", "life_gain", "raw_residual_db", "id_u16_high")
        line(JSONObject().put("schema", "pvb.harmonic_hops.v1").put("sample_rate_hz", r.sampleRate)
            .put("core_rate_hz", 3000).put("hop_core_samples", 16).put("header_fields", JSONArray(headerNames.toList()))
            .put("track_fields", JSONArray(trackNames.toList()))
            .put("harmonic_fields", JSONArray(listOf("target_amplitude", "actual_amplitude", "permission", "phase_adjustment_rad", "reasons", "evidence")))
            .put("harmonic_orders", JSONArray(listOf(2,3,4,5,6,7,8)))
            .put("state_codes", JSONObject().put("1", "birth").put("2", "tracked").put("3", "held").put("4", "releasing").put("5", "ended"))
            .put("reason_bits", JSONObject().put("1", "absolute_floor").put("2", "relative_floor").put("4", "no_peak").put("8", "fit_residual")
                .put("16", "source_grid").put("32", "track_lost").put("64", "capacity").put("128", "weight_floor").put("256", "nonfinite").put("512", "dependent_peak"))
            .put("definition", "Synthesis-hop observations for algorithms 2-5. Track identity is (algorithm, reset_epoch, id_low + 65536*id_high). Evidence is a heuristic, not a probability or buzz label. Amplitudes are before envelope compensation, output filters, user level and limiter. Envelope gain and raw vocoder sample are snapshots at the event, not the complete envelope across the new grain.")
            .put("timing", "Event is on the digital input clock. Source centre includes FIR/HPSS structural delays; frequency-dependent IIR group delay is not compensated. Grain centre includes output resampler FIR and limiter delay; it is a nominal centre, not a sample-level contribution boundary. Up to20ms earlier event context is included."))
        var hops = 0
        history.forEach(contextStart, w.end) { frame, data, off ->
            val tracks = JSONArray()
            repeat(HarmonicHistory.TRACKS) { t ->
                val base = off + HarmonicHistory.HEADER + t * HarmonicHistory.TRACK
                if (data[base+1] > 0) {
                    val fields = JSONArray()
                    repeat(HarmonicHistory.TRACK) { j -> fields.put(finite(data[base+j])) }
                    tracks.put(fields)
                }
            }
            val header = JSONArray()
            repeat(HarmonicHistory.HEADER) { j -> header.put(finite(data[off+j])) }
            line(JSONObject().put("event_frame", frame).put("event_in_clip_s", (frame-w.start).toDouble()/r.sampleRate)
                .put("source_center_in_clip_s", (frame-w.start+data[off+9]).toDouble()/r.sampleRate)
                .put("nominal_output_grain_center_in_clip_s", (frame-w.start+data[off+10]).toDouble()/r.sampleRate)
                .put("context_before_clip", frame<w.start).put("header", header).put("tracks", tracks))
            ++hops
        }
        stream.flush(); zip.closeEntry()
        hashes.put("harmonics.jsonl", digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) })
        val blocks = JSONArray()
        history.forEachBlock(w.start, w.end) { start, size, status ->
            blocks.put(JSONObject().put("block_start_frame", start).put("block_frames", size).put("rows_or_error", status))
        }
        report.put("harmonic_processing", JSONObject().put("schema", "pvb.harmonic_hops.v1").put("file", "harmonics.jsonl")
            .put("recorded_hops", hops).put("timeline_truncated", history.truncated(contextStart))
            .put("callback_status", blocks).put("errors", "-1 unavailable, -2 native capacity exceeded, -3 malformed layout; zero rows can be valid before warmup, without a hop in the callback, or for unsupported algorithms"))
    }

    private fun finite(v: Float): Any = if (v.isFinite()) v else JSONObject.NULL
}

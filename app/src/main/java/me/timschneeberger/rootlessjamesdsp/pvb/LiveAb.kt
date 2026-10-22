package me.timschneeberger.rootlessjamesdsp.pvb

import java.io.File
import java.util.Locale

/*
 * Alpha 3.3 "실청 블라인드 비교": the pure part (no Android types; host JVM tested in
 * tools/pvb-harness/jvm/LiveAbTest.kt). Seeded per-trial shuffle of the hidden mapping, the saved trial record,
 * its JSON / CSV form, the per-comparison tally and the file store. The comparisons themselves are in
 * LiveAbComparisons, the screen in LiveAbView, the results list in LiveAbResultsFragment.
 */

/** Seeded label shuffle: which condition plays behind A, B (and C) in one trial. */
object LiveAbShuffle {
    val LETTERS = listOf("A", "B", "C")

    /**
     * Fisher-Yates over 0 until [n] driven by SplitMix64 seeded from ([seed], [trial]). Element i is the index of the
     * condition behind letter i. Same seed and trial -> same mapping on every device and JVM (the record keeps both,
     * so a mapping can be re-derived).
     */
    fun permutation(seed: Long, trial: Int, n: Int): IntArray {
        require(n in 1..LETTERS.size) { "n=$n" }
        val rng = SplitMix64(seed xor (trial.toLong() * GOLDEN))
        val p = IntArray(n) { it }
        for (i in n - 1 downTo 1) {
            val j = ((rng.next() ushr 1) % (i + 1)).toInt()
            val t = p[i]
            p[i] = p[j]
            p[j] = t
        }
        return p
    }

    private val GOLDEN = 0x9E3779B97F4A7C15uL.toLong()

    private class SplitMix64(private var state: Long) {
        fun next(): Long {
            state += GOLDEN
            var z = state
            z = (z xor (z ushr 30)) * 0xBF58476D1CE4E5B9uL.toLong()
            z = (z xor (z ushr 27)) * 0x94D049BB133111EBuL.toLong()
            return z xor (z ushr 31)
        }
    }
}

/** One condition as it played behind a letter in a trial (the revealed mapping). */
data class LiveAbSide(
    val letter: String,
    val id: String,
    val label: String,
    val algo: Int,
    val levelDb: Float,           // the condition's virtual bass level (slider value of that condition)
    val effectiveLevelDb: Float,  // what the engine played at the saved volume (after the volume link, if on)
    val volLink: Boolean,
    val trimDb: Float,
    val trimMeasured: Boolean,
)

data class LiveAbTrack(val packageName: String, val title: String?, val artist: String?, val album: String?)

data class LiveAbRecord(
    val id: String,
    val timeMs: Long,
    val timeLocal: String,
    val comparisonId: String,
    val comparisonLabel: String,
    val seed: Long,
    val trial: Int,
    val sides: List<LiveAbSide>,  // in letter order: the hidden mapping
    val verdict: String,          // "A", "B", "C" or [SAME]
    val chips: List<String>,
    val note: String,
    val track: LiveAbTrack?,
    val volumeIndex: Int,
    val volumeMax: Int,
    val volumePct: Float,
    val vbSliderDb: Float,        // the user's own slider value
    val vbUserEffectiveDb: Float, // the user's own setting at this volume (after the user's volume link)
    val vbUserVolLink: Boolean,
    val headroomDb: Float,
    val switches: Int,
    val listenSeconds: Double,
    val batteryPct: Int,          // -1 = unknown
    val appVersion: String,
    val route: String,
) {
    /** The condition the listener preferred, or null for "차이 모름". */
    fun winner(): LiveAbSide? = sides.firstOrNull { it.letter == verdict }

    companion object {
        const val SAME = "same"
        /** Symptom chips, in display order (saved as these strings). */
        val CHIPS = listOf("쿠훙", "가각", "지직", "훙훙", "저음 약함", "저음 풍성")

        fun verdictValid(verdict: String, sides: Int): Boolean =
            verdict == SAME || LiveAbShuffle.LETTERS.take(sides).contains(verdict)
    }
}

/** Per-comparison tally (conditions by stable id; the newest label is shown). */
object LiveAbTally {
    data class Row(
        val comparisonId: String,
        val comparisonLabel: String,
        val trials: Int,
        val conditionIds: List<String>,
        val labels: Map<String, String>,
        val wins: Map<String, Int>,
        val same: Int,
        val chips: Map<String, Int>,
        /** Two-sided sign test over the decided trials of a two-condition comparison (null otherwise). */
        val pValue: Double?,
    )

    /** Rows in the order of each comparison's newest trial (newest first). Input order does not matter. */
    fun tally(records: List<LiveAbRecord>): List<Row> {
        val byCmp = LinkedHashMap<String, MutableList<LiveAbRecord>>()
        for (r in records.sortedByDescending { it.timeMs }) byCmp.getOrPut(r.comparisonId) { ArrayList() }.add(r)
        return byCmp.map { (cmp, rs) ->
            val ids = ArrayList<String>()
            val labels = HashMap<String, String>()
            for (r in rs) for (s in r.sides) {
                if (s.id !in ids) ids.add(s.id)
                if (s.id !in labels) labels[s.id] = s.label   // newest first: the first label seen is the newest
            }
            ids.sort()
            val wins = LinkedHashMap<String, Int>().apply { for (i in ids) put(i, 0) }
            var same = 0
            val chips = LinkedHashMap<String, Int>()
            for (r in rs) {
                val w = r.winner()
                if (w == null) same++ else wins[w.id] = (wins[w.id] ?: 0) + 1
                for (c in r.chips) chips[c] = (chips[c] ?: 0) + 1
            }
            val p = if (ids.size == 2) {
                val a = wins[ids[0]] ?: 0
                val b = wins[ids[1]] ?: 0
                signTestP(a, a + b)
            } else null
            Row(cmp, rs.first().comparisonLabel, rs.size, ids, labels, wins, same, chips, p)
        }
    }

    /** Two-sided sign test: probability of a split at least this uneven with no real difference. */
    fun signTestP(k: Int, n: Int): Double {
        if (n <= 0) return 1.0
        val m = minOf(k, n - k)
        var tail = 0.0
        var c = 1.0
        for (i in 0..m) {
            if (i > 0) c = c * (n - i + 1) / i
            tail += c
        }
        return minOf(1.0, 2.0 * tail / Math.pow(2.0, n.toDouble()))
    }
}

/** JSON form of the records (saved file and export). Hand-written: no Android, no library. */
object LiveAbJson {
    const val FORMAT = "pvb_live_ab_v1"

    fun encodeRecord(r: LiveAbRecord): String = obj(
        "id" to str(r.id),
        "time_ms" to r.timeMs.toString(),
        "time_local" to str(r.timeLocal),
        "comparison_id" to str(r.comparisonId),
        "comparison_label" to str(r.comparisonLabel),
        "seed" to r.seed.toString(),
        "trial" to r.trial.toString(),
        "mapping" to arr(r.sides.map { s ->
            obj(
                "letter" to str(s.letter),
                "id" to str(s.id),
                "label" to str(s.label),
                "algo" to s.algo.toString(),
                "level_db" to num(s.levelDb),
                "effective_level_db" to num(s.effectiveLevelDb),
                "vol_link" to s.volLink.toString(),
                "trim_db" to num(s.trimDb),
                "trim_measured" to s.trimMeasured.toString(),
            )
        }),
        "verdict" to str(r.verdict),
        "winner_id" to (r.winner()?.let { str(it.id) } ?: "null"),
        "winner_label" to (r.winner()?.let { str(it.label) } ?: "null"),
        "chips" to arr(r.chips.map { str(it) }),
        "note" to str(r.note),
        "track" to (r.track?.let { t ->
            obj("package" to str(t.packageName), "title" to nstr(t.title), "artist" to nstr(t.artist), "album" to nstr(t.album))
        } ?: "null"),
        "volume_index" to r.volumeIndex.toString(),
        "volume_max" to r.volumeMax.toString(),
        "volume_pct" to num(r.volumePct),
        "vb_slider_db" to num(r.vbSliderDb),
        "vb_user_effective_db" to num(r.vbUserEffectiveDb),
        "vb_user_vol_link" to r.vbUserVolLink.toString(),
        "headroom_db" to num(r.headroomDb),
        "switches" to r.switches.toString(),
        "listen_seconds" to num(r.listenSeconds),
        "battery_pct" to r.batteryPct.toString(),
        "app_version" to str(r.appVersion),
        "route" to str(r.route),
    )

    fun encodeList(records: List<LiveAbRecord>): String = arr(records.map { encodeRecord(it) })

    /** The export document: newest trial first, the tally, and when and by which version it was made. */
    fun encodeExport(records: List<LiveAbRecord>, exportedLocal: String, appVersion: String): String {
        val sorted = records.sortedByDescending { it.timeMs }
        val tally = LiveAbTally.tally(sorted).map { row ->
            obj(
                "comparison_id" to str(row.comparisonId),
                "comparison_label" to str(row.comparisonLabel),
                "trials" to row.trials.toString(),
                "wins" to obj(*row.conditionIds.map { it to (row.wins[it] ?: 0).toString() }.toTypedArray()),
                "labels" to obj(*row.conditionIds.map { it to str(row.labels[it] ?: it) }.toTypedArray()),
                "same" to row.same.toString(),
                "chips" to obj(*row.chips.map { (k, v) -> k to v.toString() }.toTypedArray()),
                "p_value" to (row.pValue?.let { num(it) } ?: "null"),
            )
        }
        return obj(
            "format" to str(FORMAT),
            "exported_local" to str(exportedLocal),
            "app_version" to str(appVersion),
            "count" to sorted.size.toString(),
            "tally" to arr(tally),
            "records" to encodeList(sorted),
        )
    }

    /** Records from a saved list (or an export document). Damaged entries are skipped; damaged text gives none. */
    fun decodeList(text: String?): List<LiveAbRecord> {
        if (text.isNullOrBlank()) return emptyList()
        val root = try { MiniJson.parse(text) } catch (_: Exception) { return emptyList() }
        val list = when (root) {
            is List<*> -> root
            is Map<*, *> -> root["records"] as? List<*> ?: return emptyList()
            else -> return emptyList()
        }
        return list.mapNotNull { (it as? Map<*, *>)?.let { m -> decodeRecord(m) } }
    }

    private fun decodeRecord(m: Map<*, *>): LiveAbRecord? = try {
        val sides = (m["mapping"] as List<*>).map { e ->
            val s = e as Map<*, *>
            LiveAbSide(
                letter = s["letter"] as String,
                id = s["id"] as String,
                label = s["label"] as? String ?: "",
                algo = (s["algo"] as? Number)?.toInt() ?: -1,
                levelDb = fl(s["level_db"]),
                effectiveLevelDb = fl(s["effective_level_db"]),
                volLink = s["vol_link"] as? Boolean ?: false,
                trimDb = fl(s["trim_db"]),
                trimMeasured = s["trim_measured"] as? Boolean ?: false,
            )
        }
        val verdict = m["verdict"] as String
        require(sides.isNotEmpty() && LiveAbRecord.verdictValid(verdict, sides.size))
        val t = m["track"] as? Map<*, *>
        LiveAbRecord(
            id = m["id"] as String,
            timeMs = (m["time_ms"] as Number).toLong(),
            timeLocal = m["time_local"] as? String ?: "",
            comparisonId = m["comparison_id"] as String,
            comparisonLabel = m["comparison_label"] as? String ?: "",
            seed = (m["seed"] as? Number)?.toLong() ?: 0L,
            trial = (m["trial"] as? Number)?.toInt() ?: 0,
            sides = sides,
            verdict = verdict,
            chips = (m["chips"] as? List<*>)?.mapNotNull { it as? String } ?: emptyList(),
            note = m["note"] as? String ?: "",
            track = t?.let { LiveAbTrack(it["package"] as? String ?: "", it["title"] as? String, it["artist"] as? String, it["album"] as? String) },
            volumeIndex = (m["volume_index"] as? Number)?.toInt() ?: -1,
            volumeMax = (m["volume_max"] as? Number)?.toInt() ?: -1,
            volumePct = fl(m["volume_pct"]),
            vbSliderDb = fl(m["vb_slider_db"]),
            vbUserEffectiveDb = fl(m["vb_user_effective_db"]),
            vbUserVolLink = m["vb_user_vol_link"] as? Boolean ?: false,
            headroomDb = fl(m["headroom_db"]),
            switches = (m["switches"] as? Number)?.toInt() ?: 0,
            listenSeconds = (m["listen_seconds"] as? Number)?.toDouble() ?: Double.NaN,
            batteryPct = (m["battery_pct"] as? Number)?.toInt() ?: -1,
            appVersion = m["app_version"] as? String ?: "",
            route = m["route"] as? String ?: "",
        )
    } catch (_: Exception) {
        null
    }

    private fun fl(v: Any?): Float = (v as? Number)?.toFloat() ?: Float.NaN

    // ---- writing
    private fun obj(vararg kv: Pair<String, String>): String =
        kv.joinToString(",", "{", "}") { (k, v) -> str(k) + ":" + v }

    private fun arr(items: List<String>): String = items.joinToString(",", "[", "]")
    private fun nstr(s: String?): String = if (s == null) "null" else str(s)

    /** Finite numbers only (NaN / infinity -> null); plain decimal, never a locale's comma. */
    private fun num(v: Float): String = if (v.isFinite()) trimNum(String.format(Locale.ROOT, "%.3f", v)) else "null"
    private fun num(v: Double): String = if (v.isFinite()) trimNum(String.format(Locale.ROOT, "%.4f", v)) else "null"
    private fun trimNum(s: String): String {
        if (!s.contains('.')) return s
        val t = s.trimEnd('0').trimEnd('.')
        return if (t == "-0") "0" else t
    }

    fun str(s: String): String {
        val b = StringBuilder(s.length + 2)
        b.append('"')
        for (ch in s) {
            when (ch) {
                '"' -> b.append("\\\"")
                '\\' -> b.append("\\\\")
                '\n' -> b.append("\\n")
                '\r' -> b.append("\\r")
                '\t' -> b.append("\\t")
                else -> if (ch < ' ' || ch == ' ' || ch == ' ') b.append(String.format(Locale.ROOT, "\\u%04x", ch.code)) else b.append(ch)
            }
        }
        b.append('"')
        return b.toString()
    }
}

/** Minimal strict JSON reader for [LiveAbJson] (objects -> Map, arrays -> List, numbers -> Long or Double). */
object MiniJson {
    fun parse(text: String): Any? {
        val p = P(text)
        p.ws()
        val v = p.value()
        p.ws()
        require(p.i == text.length) { "trailing data at ${p.i}" }
        return v
    }

    private class P(val s: String) {
        var i = 0
        fun ws() { while (i < s.length && s[i] in " \t\r\n﻿") i++ }
        fun value(): Any? {
            require(i < s.length) { "end of input" }
            return when (val c = s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                else -> if (c == '-' || c in '0'..'9') num() else throw IllegalArgumentException("bad char '$c' at $i")
            }
        }
        fun lit(word: String, v: Any?): Any? {
            require(s.startsWith(word, i)) { "bad literal at $i" }
            i += word.length
            return v
        }
        fun obj(): Map<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++; ws()
            if (s[i] == '}') { i++; return m }
            while (true) {
                ws()
                require(s[i] == '"') { "key expected at $i" }
                val k = str()
                ws(); require(s[i] == ':') { "':' expected at $i" }; i++; ws()
                m[k] = value()
                ws()
                when (s[i]) {
                    ',' -> i++
                    '}' -> { i++; return m }
                    else -> throw IllegalArgumentException("',' or '}' expected at $i")
                }
            }
        }
        fun arr(): List<Any?> {
            val l = ArrayList<Any?>()
            i++; ws()
            if (s[i] == ']') { i++; return l }
            while (true) {
                ws()
                l.add(value())
                ws()
                when (s[i]) {
                    ',' -> i++
                    ']' -> { i++; return l }
                    else -> throw IllegalArgumentException("',' or ']' expected at $i")
                }
            }
        }
        fun str(): String {
            val b = StringBuilder()
            i++
            while (true) {
                val c = s[i++]
                when {
                    c == '"' -> return b.toString()
                    c == '\\' -> {
                        when (val e = s[i++]) {
                            '"' -> b.append('"')
                            '\\' -> b.append('\\')
                            '/' -> b.append('/')
                            'b' -> b.append('\b')
                            'f' -> b.append('\u000C')
                            'n' -> b.append('\n')
                            'r' -> b.append('\r')
                            't' -> b.append('\t')
                            'u' -> {
                                b.append(s.substring(i, i + 4).toInt(16).toChar())
                                i += 4
                            }
                            else -> throw IllegalArgumentException("bad escape '$e'")
                        }
                    }
                    c < ' ' -> throw IllegalArgumentException("control char in string at ${i - 1}")
                    else -> b.append(c)
                }
            }
        }
        fun num(): Any {
            val start = i
            if (s[i] == '-') i++
            while (i < s.length && (s[i].isDigit() || s[i] in ".eE+-")) i++
            val t = s.substring(start, i)
            return if (t.any { it == '.' || it == 'e' || it == 'E' }) t.toDouble() else (t.toLongOrNull() ?: t.toDouble())
        }
    }
}

/** CSV export (UTF-8 with BOM so spreadsheet apps read Korean correctly), one row per trial, newest first. */
object LiveAbCsv {
    val HEADER = listOf(
        "time_local", "time_ms", "comparison_id", "comparison_label", "trial", "seed",
        "A_id", "A_label", "B_id", "B_label", "C_id", "C_label",
        "verdict", "winner_id", "winner_label", "chips", "note",
        "track_title", "track_artist", "track_package",
        "volume_index", "volume_max", "volume_pct", "vb_slider_db", "vb_user_effective_db", "vb_user_vol_link",
        "A_effective_db", "B_effective_db", "C_effective_db", "headroom_db", "trims_measured",
        "switches", "listen_seconds", "battery_pct", "app_version", "route", "id",
    )

    fun encode(records: List<LiveAbRecord>): String {
        val b = StringBuilder("﻿")
        b.append(HEADER.joinToString(",")).append("\r\n")
        for (r in records.sortedByDescending { it.timeMs }) {
            fun side(l: String) = r.sides.firstOrNull { it.letter == l }
            val cells = listOf(
                r.timeLocal, r.timeMs.toString(), r.comparisonId, r.comparisonLabel, r.trial.toString(), r.seed.toString(),
                side("A")?.id ?: "", side("A")?.label ?: "", side("B")?.id ?: "", side("B")?.label ?: "",
                side("C")?.id ?: "", side("C")?.label ?: "",
                r.verdict, r.winner()?.id ?: "", r.winner()?.label ?: "", r.chips.joinToString(";"), r.note,
                r.track?.title ?: "", r.track?.artist ?: "", r.track?.packageName ?: "",
                r.volumeIndex.toString(), r.volumeMax.toString(), n(r.volumePct), n(r.vbSliderDb), n(r.vbUserEffectiveDb),
                r.vbUserVolLink.toString(),
                n(side("A")?.effectiveLevelDb), n(side("B")?.effectiveLevelDb), n(side("C")?.effectiveLevelDb),
                n(r.headroomDb), r.sides.all { it.trimMeasured }.toString(),
                r.switches.toString(), if (r.listenSeconds.isFinite()) String.format(Locale.ROOT, "%.1f", r.listenSeconds) else "",
                r.batteryPct.toString(), r.appVersion, r.route, r.id,
            )
            b.append(cells.joinToString(",") { cell(it) }).append("\r\n")
        }
        return b.toString()
    }

    private fun n(v: Float?): String =
        if (v == null || !v.isFinite()) "" else String.format(Locale.ROOT, "%.2f", v)

    /** RFC 4180 quoting; a leading = + - @ is prefixed with ' so a spreadsheet never runs it as a formula. */
    fun cell(v: String): String {
        val safe = if (v.isNotEmpty() && v[0] in "=+-@" && v.toDoubleOrNull() == null) "'$v" else v
        return if (safe.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) "\"" + safe.replace("\"", "\"\"") + "\"" else safe
    }
}

/**
 * The saved trials: one JSON array in [file], rewritten through a temporary file and a rename so a crash never
 * leaves half a list. Newest records are kept when [capacity] is exceeded. Not thread-safe: main thread only.
 */
class LiveAbStore(private val file: File, private val capacity: Int = DEFAULT_CAPACITY) {
    fun load(): List<LiveAbRecord> = try {
        if (file.isFile) LiveAbJson.decodeList(file.readText(Charsets.UTF_8)) else emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    /** Newest first. */
    fun newestFirst(): List<LiveAbRecord> = load().sortedByDescending { it.timeMs }

    fun add(r: LiveAbRecord): Boolean {
        val all = load().filter { it.id != r.id } + r
        return save(if (all.size > capacity) all.sortedBy { it.timeMs }.takeLast(capacity) else all)
    }

    fun delete(id: String): Boolean = save(load().filter { it.id != id })

    fun clear(): Boolean = save(emptyList())

    private fun save(list: List<LiveAbRecord>): Boolean = try {
        file.parentFile?.let { if (!it.isDirectory) it.mkdirs() }
        val tmp = File(file.path + ".tmp")
        tmp.writeText(LiveAbJson.encodeList(list.sortedBy { it.timeMs }), Charsets.UTF_8)
        if (!tmp.renameTo(file)) {
            file.delete()
            check(tmp.renameTo(file))
        }
        true
    } catch (_: Exception) {
        false
    }

    companion object {
        const val DEFAULT_CAPACITY = 5000
    }
}

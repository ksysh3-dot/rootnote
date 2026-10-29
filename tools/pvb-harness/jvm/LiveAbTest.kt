import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbComparisons
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbCsv
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbJson
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbRecord
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbShuffle
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbSide
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbStore
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbTally
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbTrack
import me.timschneeberger.rootlessjamesdsp.pvb.MiniJson
import me.timschneeberger.rootlessjamesdsp.pvb.PvbAbConditions
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink
import java.io.File
import kotlin.math.abs

// Alpha 3.3 live blind A/B: seeded shuffle, record JSON round trip and CSV, tally, file store, comparison catalogue.

private fun side(letter: String, id: String, label: String = id, eff: Float = 6f) =
    LiveAbSide(letter, id, label, PvbModels.P1, 6f, eff, false, 0f, false)

private fun rec(
    id: String, time: Long, cmp: String, a: String, b: String, verdict: String,
    chips: List<String> = emptyList(), c: String? = null, note: String = "",
): LiveAbRecord {
    val sides = listOfNotNull(side("A", a), side("B", b), c?.let { side("C", it) })
    return LiveAbRecord(
        id = id, timeMs = time, timeLocal = "2026-10-22 10:00:00", comparisonId = cmp, comparisonLabel = "label $cmp",
        seed = -1234567890123L, trial = 3, sides = sides, verdict = verdict, chips = chips, note = note,
        track = LiveAbTrack("com.spotify.music", "Sunrise", "Ana", null),
        volumeIndex = 9, volumeMax = 15, volumePct = 53.333f, vbSliderDb = 6f, vbUserEffectiveDb = 3.333f,
        vbUserVolLink = true, headroomDb = 10f, switches = 7, listenSeconds = 41.25, batteryPct = 77,
        appVersion = "1.6.23-alpha3.3 (61)", route = "내장 스피커",
    )
}

private fun shuffle() {
    val S = LiveAbShuffle
    // deterministic, a permutation, depends on seed and trial
    for (n in 1..3) for (seed in listOf(0L, 1L, -1L, Long.MIN_VALUE, 42L)) for (t in 0 until 50) {
        val p = S.permutation(seed, t, n)
        check(p.contentEquals(S.permutation(seed, t, n)))
        check(p.sorted() == (0 until n).toList()) { "not a permutation: ${p.toList()}" }
    }
    // roughly uniform: 2 sides ~50 %, 3 sides each of the 6 orders ~1/6
    var aFirst = 0
    val counts = HashMap<List<Int>, Int>()
    val trials = 60000
    for (t in 0 until trials) {
        if (S.permutation(987654321L, t, 2)[0] == 0) aFirst++
        val p = S.permutation(t.toLong() * 31 + 7, t, 3).toList()
        counts[p] = (counts[p] ?: 0) + 1
    }
    check(abs(aFirst / trials.toDouble() - 0.5) < 0.01) { "A=first ${aFirst / trials.toDouble()}" }
    check(counts.size == 6)
    for ((p, c) in counts) check(abs(c / trials.toDouble() - 1.0 / 6) < 0.01) { "$p ${c / trials.toDouble()}" }
    // consecutive trials of one session are not all the same
    val run = (0 until 16).map { S.permutation(5L, it, 2)[0] }
    check(run.toSet().size == 2) { "16 trials all identical: $run" }
    // different seeds give different sequences
    check((0 until 32).map { S.permutation(1L, it, 3).toList() } != (0 until 32).map { S.permutation(2L, it, 3).toList() })
    // fixed values: same on every JVM (SplitMix64 is fully specified)
    val fixed = (0 until 8).map { S.permutation(20261022L, it, 3).joinToString("") }
    println("LiveAb shuffle fixture (seed 20261022): $fixed")
    check(fixed == listOf("201", "210", "021", "021", "120", "201", "120", "201")) { "shuffle changed: $fixed" }
}

private fun records() {
    val r = rec("r1", 1000L, "p1_vs_d2", "d2", "p1", "B", listOf("쿠훙", "저음 풍성"),
        note = "따옴표 \" 역슬래시 \\ 줄바꿈\n탭\t, 쉼표 =SUM(A1) \u0001")
    check(r.winner()?.id == "p1")
    check(rec("r2", 1L, "x", "a", "b", LiveAbRecord.SAME).winner() == null)
    check(LiveAbRecord.verdictValid("C", 3) && !LiveAbRecord.verdictValid("C", 2) && LiveAbRecord.verdictValid("same", 2))
    check(!LiveAbRecord.verdictValid("D", 3) && !LiveAbRecord.verdictValid("", 2))

    // JSON round trip (incl. escapes, null album, negative seed, NaN -> null)
    val withNan = r.copy(listenSeconds = Double.NaN, sides = r.sides.map { it.copy(effectiveLevelDb = Float.NaN) })
    val text = LiveAbJson.encodeList(listOf(r, withNan.copy(id = "r1b")))
    MiniJson.parse(text)   // valid JSON
    val back = LiveAbJson.decodeList(text)
    check(back.size == 2)
    check(back[0] == r.copy(volumePct = 53.333f, vbUserEffectiveDb = 3.333f)) { "round trip:\n${back[0]}\n$r" }
    check(back[1].listenSeconds.isNaN() && back[1].sides.all { it.effectiveLevelDb.isNaN() })
    check(back[0].note == r.note && back[0].seed == -1234567890123L && back[0].track?.album == null)
    // the export document: tally + newest first, readable by the same decoder
    val exp = LiveAbJson.encodeExport(listOf(r, rec("r3", 5000L, "p1_vs_d2", "p1", "d2", "A")), "2026-10-22 11:00", "v")
    val doc = MiniJson.parse(exp) as Map<*, *>
    check(doc["format"] == LiveAbJson.FORMAT && doc["count"] == 2L)
    check(((doc["records"] as List<*>)[0] as Map<*, *>)["id"] == "r3")       // newest first
    val tallyDoc = (doc["tally"] as List<*>)[0] as Map<*, *>
    check((tallyDoc["wins"] as Map<*, *>)["p1"] == 2L) { tallyDoc.toString() }
    check(LiveAbJson.decodeList(exp).map { it.id } == listOf("r3", "r1"))
    // damaged input: nothing, or only the damaged entry skipped
    check(LiveAbJson.decodeList("").isEmpty() && LiveAbJson.decodeList("{oops").isEmpty() && LiveAbJson.decodeList(null).isEmpty())
    val oneBad = "[" + LiveAbJson.encodeRecord(r) + ",{\"id\":\"x\"}," + LiveAbJson.encodeRecord(r.copy(id = "r9", verdict = "C")) + "]"
    check(LiveAbJson.decodeList(oneBad).map { it.id } == listOf("r1"))   // missing fields, and C with two sides

    // CSV: BOM, header, quoting, formula guard, one row per record, newest first
    val csv = LiveAbCsv.encode(listOf(r, rec("r3", 5000L, "p1_vs_d2", "p1", "d2", "A")))
    check(csv.startsWith("﻿" + LiveAbCsv.HEADER.joinToString(",") + "\r\n"))
    check(LiveAbCsv.cell("a,b") == "\"a,b\"" && LiveAbCsv.cell("say \"hi\"") == "\"say \"\"hi\"\"\"")
    check(LiveAbCsv.cell("=SUM(A1)") == "'=SUM(A1)" && LiveAbCsv.cell("-3.00") == "-3.00" && LiveAbCsv.cell("+ x") == "'+ x")
    check(csv.indexOf("r3") < csv.indexOf(",r1"))
    check(csv.contains("쿠훙;저음 풍성") && csv.contains("Sunrise,Ana,com.spotify.music"))
    check(csv.contains("\"따옴표 \"\" 역슬래시 \\ 줄바꿈\n탭\t, 쉼표 =SUM(A1) \u0001\""))
    // header and every row have the same number of columns (count outside quotes)
    fun columns(line: String): Int { var q = false; var n = 1; for (ch in line) { if (ch == '"') q = !q else if (ch == ',' && !q) n++ }; return n }
    val rows = csv.removePrefix("﻿").split("\r\n").filter { it.isNotEmpty() }
    check(rows.size == 3 && rows.all { columns(it) == LiveAbCsv.HEADER.size }) { rows.map { columns(it) }.toString() }
}

private fun tally() {
    val rs = listOf(
        rec("1", 1, "ab", "p1", "d2", "A"),
        rec("2", 2, "ab", "d2", "p1", "B", listOf("쿠훙")),
        rec("3", 3, "ab", "d2", "p1", "A", listOf("쿠훙", "지직")),
        rec("4", 4, "ab", "p1", "d2", LiveAbRecord.SAME),
        rec("5", 10, "abc", "p1", "d2", "C", c = "id4"),
        rec("6", 11, "abc", "id4", "p1", "B", c = "d2"),
        rec("7", 12, "abc", "id4", "d2", LiveAbRecord.SAME, c = "p1"),
    )
    val rows = LiveAbTally.tally(rs.shuffled(java.util.Random(3)))
    check(rows.map { it.comparisonId } == listOf("abc", "ab"))        // newest comparison first
    val ab = rows[1]
    check(ab.trials == 4 && ab.same == 1 && ab.wins == mapOf("d2" to 1, "p1" to 2)) { ab.toString() }
    check(ab.chips == mapOf("쿠훙" to 2, "지직" to 1))
    check(abs(ab.pValue!! - 1.0) < 1e-9)                               // 2:1 is nothing
    val abc = rows[0]
    check(abc.conditionIds == listOf("d2", "id4", "p1") && abc.wins == mapOf("d2" to 0, "id4" to 1, "p1" to 1) && abc.same == 1)
    check(abc.pValue == null)
    // sign test values (same as the existing card)
    check(abs(LiveAbTally.signTestP(8, 8) - 0.0078125) < 1e-12)
    check(abs(LiveAbTally.signTestP(7, 8) - 0.0703125) < 1e-12)
    check(LiveAbTally.signTestP(0, 0) == 1.0)
    check(LiveAbTally.tally(emptyList()).isEmpty())
}

private fun store() {
    val dir = File(System.getProperty("java.io.tmpdir"), "liveab-test-" + System.nanoTime())
    val f = File(dir, "sub/trials.json")
    val s = LiveAbStore(f, capacity = 3)
    check(s.load().isEmpty())
    check(s.add(rec("a", 1, "x", "p1", "d2", "A")) && s.add(rec("b", 2, "x", "p1", "d2", "B")))
    check(s.newestFirst().map { it.id } == listOf("b", "a"))
    check(s.add(rec("c", 3, "x", "p1", "d2", "A")) && s.add(rec("d", 4, "x", "p1", "d2", "A")))
    check(s.newestFirst().map { it.id } == listOf("d", "c", "b"))       // capacity: oldest dropped
    check(s.add(rec("c", 3, "x", "p1", "d2", "B")))                      // same id replaces
    check(s.newestFirst().first { it.id == "c" }.verdict == "B" && s.load().size == 3)
    check(s.delete("c") && s.newestFirst().map { it.id } == listOf("d", "b"))
    check(LiveAbStore(f).load().size == 2)                               // survives a new instance
    check(!File(f.path + ".tmp").exists())
    f.writeText("garbage")
    check(s.load().isEmpty())                                            // damaged file reads as empty, never throws
    check(s.clear() && s.load().isEmpty())
    dir.deleteRecursively()
}

private fun catalogue() {
    val C = LiveAbComparisons
    val ids = C.ALL.map { it.id }
    check(ids.toSet().size == ids.size)
    check(C.ALL.size >= 4 && C.ALL.any { it.sides.size == 3 })
    val user = PvbSettings(xtcMode = PvbSettings.XTC_FULL, xtcStrengthDb = -4.5f, xtcPortrait = PvbSettings.XTC_PORTRAIT_MONO,
        xtcDistanceCm = 33f, xtcHatCm = 60f, vbOn = false, vbAlgo = PvbModels.GENTLE12, vbLevelDb = 7f, vbVolLink = true,
        vbVolRefPct = 30f, vbVolSlope = 0.3f, vbVolMaxDb = 9f, outDb = -9f, hsDb = -4f, hpHz = 150f, dynOn = true, volLink = true)
    for (cmp in C.ALL) {
        check(cmp.sides.size in 2..3)
        check(cmp.sides.map { it.id }.toSet().size == cmp.sides.size)
        check(PvbAbConditions.v11(user).xtcMode == PvbSettings.XTC_OFF)   // spatial off unless a comparison sets it
        if (cmp.id.startsWith("xtc_")) {
            // spatial: EQ v1.1 with only the spatial mode (and upright off) changed; canceller vs its M/S widener
            val ref = PvbAbConditions.v11(user)
            val modes = cmp.sides.map { side ->
                val s = side.apply(user)
                check(s.copy(xtcMode = ref.xtcMode, xtcPortrait = ref.xtcPortrait) == ref) { side.id }
                check(!s.vbOn && s.xtcPortrait == PvbSettings.XTC_PORTRAIT_OFF && !side.trimMeasured && side.trimDb == 0f)
                check(s.xtcStrengthDb == user.xtcStrengthDb && s.xtcDistanceCm == user.xtcDistanceCm && s.xtcHatCm == user.xtcHatCm)
                s.xtcMode
            }
            check(modes == listOf(PvbSettings.XTC_CENTRE_ALIGNED, PvbSettings.XTC_MS_CENTRE) ||
                modes == listOf(PvbSettings.XTC_FULL_ALIGNED, PvbSettings.XTC_MS_FULL)) { "${cmp.id}: $modes" }
            check(cmp.headroomDb == PvbAbConditions.HEADROOM_DB)
            continue
        }
        for (side in cmp.sides) {
            val s = side.apply(user)
            val ref = PvbAbConditions.v11(user)
            // EQ v1.1 base: everything except the virtual bass fields is the v11 reference
            check(s.copy(vbOn = ref.vbOn, vbAlgo = ref.vbAlgo, vbLevelDb = ref.vbLevelDb, vbVolLink = ref.vbVolLink) == ref) { side.id }
            check(s.vbOn && s.enabled && !s.volLink && !s.dynOn && s.outDb == -5f && s.hsDb == 0f)
            // the volume link is on only on the "link on" side of the link comparison
            check(s.vbVolLink == (side.id == "p1_link_on")) { side.id }
            if (s.vbVolLink) check(cmp.id == "p1_link_on_vs_off" && s.vbVolRefPct == 30f && s.vbVolSlope == 0.3f && s.vbVolMaxDb == 9f)
            check(!side.trimMeasured && side.trimDb == 0f)
            val cond = cmp.condition(side, user)
            check(cond.id == side.id && cond.headroomDb == cmp.headroomDb && cond.label == side.label(user))
        }
        // headroom as the existing comparison, except the link comparison (it reads the volume)
        check(cmp.headroomDb == if (cmp.id == "p1_link_on_vs_off") 0f else PvbAbConditions.HEADROOM_DB) { cmp.id }
    }
    val lower = C.byId("p1_vs_p1_minus3")!!
    check(lower.sides[0].apply(user).vbLevelDb == 7f && lower.sides[1].apply(user).vbLevelDb == 4f)
    check(lower.sides[0].apply(user).vbAlgo == PvbModels.P1 && lower.sides[1].apply(user).vbAlgo == PvbModels.P1)
    check(lower.sides.map { it.label(user) } == listOf("Legato 1.0 +7 dB", "Legato 1.0 +4 dB (3 dB 작게)"))
    check(lower.sides[1].apply(user.copy(vbLevelDb = 0f)).vbLevelDb == -3f)
    check(C.byId("p1_vs_d2")!!.sides.map { it.apply(user).vbAlgo } == listOf(PvbModels.P1, PvbModels.D2))
    check(C.byId("p1_vs_id4")!!.sides.map { it.apply(user).vbAlgo } == listOf(PvbModels.P1, PvbModels.REFERENCE))
    check(PvbModels.D2 == 7 && PvbModels.REFERENCE == 4)
    check(C.byId("p1_vs_d2_vs_id4")!!.sides.map { it.apply(user).vbAlgo } == listOf(PvbModels.P1, PvbModels.D2, PvbModels.REFERENCE))
    // link comparison: at 80 % (index 13 of 15) the "on" side plays (80-30)*0.3 = 15 -> max 9 dB less, the "off" side not
    val link = C.byId("p1_link_on_vs_off")!!
    val on = link.sides[0].apply(user)
    val off = link.sides[1].apply(user)
    check(abs(VolumeLevelLink.levelFor(on, 13, 15) - (7f - 9f)) < 1e-4 && VolumeLevelLink.levelFor(off, 13, 15) == 7f)
    check(C.byId("nope") == null)
}

fun main() {
    shuffle()
    records()
    tally()
    store()
    catalogue()
    println("LiveAbTest OK")
}

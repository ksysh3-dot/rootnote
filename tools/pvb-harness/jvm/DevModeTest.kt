import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidence
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidenceText
import me.timschneeberger.rootlessjamesdsp.pvb.DevGroup
import me.timschneeberger.rootlessjamesdsp.pvb.DevMath
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevShareCode
import me.timschneeberger.rootlessjamesdsp.pvb.DevSnapshot
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarning
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarningStore
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarningTracker
import me.timschneeberger.rootlessjamesdsp.pvb.DeviceProfiles
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbDevMeter
import me.timschneeberger.rootlessjamesdsp.pvb.PvbEngine
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.math.abs

// Developer mode: value specs and settings, share code (encode/decode/round trip/malformed), warning rules and
// counting, evidence badges from the device profile, test sounds, and (with --jni) the engine's meters through JNI.
// Arguments: the repository root, then --jni to run the native part.

private var passed = 0
private fun check(ok: Boolean, what: String) {
    if (!ok) throw AssertionError(what)
    passed++
    println("[PASS] $what")
}

private class DPrefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
    val values = initial.toMutableMap()
    override val all: Map<String, *> get() = values.toMap()
    override fun getString(key: String, defValue: String?): String? = values[key] as? String ?: defValue
    override fun getFloat(key: String, defValue: Float): Float =
        if (values.containsKey(key)) values[key] as Float else defValue
    override fun getBoolean(key: String, defValue: Boolean): Boolean =
        if (values.containsKey(key)) values[key] as Boolean else defValue
    override fun getInt(key: String, defValue: Int): Int = if (values.containsKey(key)) values[key] as Int else defValue
    override fun edit(): SharedPreferences.Editor = throw UnsupportedOperationException()
}

private class MapStore : DevWarningStore {
    val counts = HashMap<DevWarning, Int>()
    val hidden = HashSet<DevWarning>()
    override fun count(w: DevWarning) = counts[w] ?: 0
    override fun setCount(w: DevWarning, n: Int) { counts[w] = n }
    override fun hidden(w: DevWarning) = w in hidden
    override fun setHidden(w: DevWarning, hidden: Boolean) { if (hidden) this.hidden += w else this.hidden -= w }
}

private fun snapshot(
    f0: Float = 55f, harm: FloatArray = floatArrayOf(-120f, -20f, -22f, -30f, -120f, -120f, -120f),
    dry: Float = -40f, layer: Float = -36f, threshold: Float = -27f, outPeak: Float = -6f, gr: Float = 0f,
    vol: Float = 50f, link: Boolean = true, ringDry: FloatArray = FloatArray(512) { -120f },
    ringLayer: FloatArray = FloatArray(512) { -120f },
) = DevSnapshot(f0, harm, dry, layer, ringDry, ringLayer, 5f, outPeak, gr, -1f, vol, link, 0f, threshold)

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })
    val jni = "--jni" in args

    // ---------------------------------------------------------------------------------------- specs
    val specs = DevParams.ALL
    check(specs.size == 21 && specs.map { it.id }.toSet().size == 21 && specs.map { it.key }.toSet().size == 21,
        "21 values, unique ids and keys")
    for (s in specs) {
        check(s.min < s.max && s.recMin >= s.min - 1e-4f && s.recMax <= s.max + 1e-4f && s.recMin <= s.recMax,
            "${s.id}: recommended range inside the range")
        check(s.snap(s.default) == s.snap(s.snap(s.default)) && abs(s.snap(s.default) - s.default) < 1e-3f,
            "${s.id}: default on the grid")
        check(s.steps in 1..255, "${s.id}: ${s.steps} steps fit one share-code byte")
        check(s.snap(Float.NaN) == s.snap(s.default) && s.snap(1e9f) == s.valueAt(s.steps) && s.snap(-1e9f) == s.valueAt(0),
            "${s.id}: NaN -> default, out of range -> clamped")
    }
    check(DevParams.group(DevGroup.BAND).size == 11 && DevParams.group(DevGroup.TIME).size == 5 &&
        DevParams.group(DevGroup.SIZE).size == 5, "groups: band 11, time 5, level 5")
    check(DevParams.STRENGTH.max == 12f && DevParams.HP.min == 80f, "strength up to +12, high-pass from 80 Hz (general cap)")
    check(DevParams.ATTACK.default == 32f / 3f && abs(DevParams.RELEASE.snap(DevParams.RELEASE.default) - 32f) < 1e-4f,
        "attack 2 hops (10.7 ms), release 6 hops (32 ms) = model")
    check(DevParams.rolloffRange(PvbModels.P1) == -24f..24f && DevParams.rolloffRange(PvbModels.GENTLE12) == -12f..24f,
        "roll-off offset range keeps the absolute slope within 0..48 dB/oct")
    // engine indices and defaults
    check(PvbParam.DEV_ON == 33 && PvbParam.DEV_METER == 34 && PvbParam.D_BOUNDARY_HZ == 35 && PvbParam.D_RELEASE_MS == 46 &&
        PvbParam.COUNT == 47, "parameter indices follow pvb_engine.h")
    val dp = PvbEngine.defaultParams()
    check(dp.size == PvbParam.COUNT && dp[PvbParam.DEV_ON] == 0f && dp[PvbParam.DEV_METER] == 0f &&
        dp[PvbParam.D_BOUNDARY_HZ] == 190f && dp[PvbParam.D_OUT_LO_HZ] == 150f && dp[PvbParam.D_OUT_HI_HZ] == 600f &&
        (PvbParam.D_H2_DB..PvbParam.D_PERC_DB).all { dp[it] == 0f } && dp[PvbParam.D_ATTACK_MS] == 32f / 3f &&
        dp[PvbParam.D_RELEASE_MS] == 32f, "defaultParams: developer mode off, model values")
    check(PvbDevMeter.SIZE == 16 + 2 * 512, "meter layout 16 + 2 x 512")

    // ---------------------------------------------------------------------------------------- settings
    PvbBuild.reset()
    val s26uBuild = PvbSettings.load(DPrefs(mapOf(DevParams.KEY_DEV_ON to true, DevParams.KEY_H3 to 6f)))
    check(!s26uBuild.devOn, "s26u build: developer mode never on")
    PvbBuild.general = true; PvbBuild.researchUiBuild = false; PvbBuild.firstRunConfirmed = true
    val d = PvbSettings.load(DPrefs())
    check(!d.devOn && DevParams.read(d).contentEquals(DevParams.read(PvbSettings())), "general: defaults, developer mode off")
    val on = PvbSettings.load(DPrefs(mapOf(DevParams.KEY_DEV_ON to true, DevParams.KEY_H3 to 6.4f,
        DevParams.KEY_BOUNDARY to 999f, DevParams.KEY_RELEASE to 120f, PvbSettings.KEY_VB_STRENGTH_DB to 12f)))
    check(on.devOn && on.devH3Db == 6f && on.devBoundaryHz == 210f && on.devReleaseMs == DevParams.RELEASE.snap(120f) && abs(on.devReleaseMs - 120f) < 3f,
        "general: stored values read, snapped to the grid and clamped (${on.devOn} ${on.devH3Db} ${on.devBoundaryHz} ${on.devReleaseMs})")
    check(on.vbLevelDb == 12f, "developer mode: strength cap +12")
    val off12 = PvbSettings.load(DPrefs(mapOf(PvbSettings.KEY_VB_STRENGTH_DB to 12f)))
    check(off12.vbLevelDb == 9f, "without developer mode: strength cap stays +9")
    val typed = PvbSettings.load(DPrefs(mapOf(DevParams.KEY_DEV_ON to "yes", DevParams.KEY_H2 to "3")))
    check(!typed.devOn && typed.devH2Db == 0f, "wrong stored types fall back to the defaults")
    for (k in specs.map { it.key }.filter { it.startsWith("pvb_dev_") } + DevParams.KEY_DEV_ON)
        check(k !in DeviceProfiles.FLOAT_KEYS && k !in DeviceProfiles.BOOL_KEYS, "$k is not part of device profiles")
    // apply / write / reset round trip
    val vals = DevParams.read(on)
    val applied = DevParams.apply(PvbSettings(), vals)
    val back = DevParams.read(applied)
    check(specs.indices.all { specs[it].indexOf(back[it]) == specs[it].indexOf(vals[it]) }, "apply then read returns the same values")
    val written = HashMap<String, Any>()
    DevParams.write(vals, { k, v -> written[k] = v }, { k, v -> written[k] = v })
    check(written.size == 21 && written[PvbSettings.KEY_X_RISE] is Boolean && written[DevParams.KEY_H3] == 6f,
        "write: floats and switches under their keys")
    val profileSettings = mapOf<String, Any>(PvbSettings.KEY_HP_HZ to 100f, PvbSettings.KEY_VB_STRENGTH_DB to 4f)
    val defaults = DevParams.defaults(profileSettings)
    val resetBand = DevParams.reset(vals, defaults, DevGroup.BAND)
    check(DevParams.ALL.indices.all { i ->
        if (specs[i].group == DevGroup.BAND) resetBand[i] == defaults[i] else resetBand[i] == vals[i] },
        "reset of one group only touches that group")
    check(DevParams.allDefault(DevParams.reset(vals, defaults, null), defaults) && !DevParams.allDefault(vals, defaults),
        "reset all -> every value at its default")

    // ---------------------------------------------------------------------------------------- share code
    val code = DevShareCode.encode("SM-S948N", "0.9.0-beta.1", vals, defaults)
    println("share code: $code")
    check(code.startsWith("RN1-SM-S948N-0.9.0-beta.1-") && Regex("^[A-Za-z0-9._+\\-]+$").matches(code),
        "format RN1-model-version-groups")
    val dec = DevShareCode.decode(code, defaults)
    check(dec is DevShareCode.Result.Ok && dec.values.contentEquals(vals) && dec.model == "SM-S948N" &&
        dec.appVersion == "0.9.0-beta.1", "round trip: values, model and version")
    val allDef = DevShareCode.encode("Pixel 9", "1.0", defaults, defaults)
    println("defaults code: $allDef")
    val decDef = DevShareCode.decode(allDef, defaults)
    check(decDef is DevShareCode.Result.Ok && decDef.moved == 0 && decDef.model == "Pixel_9", "all defaults: short code, 0 moved")
    check(allDef.length < code.length, "unchanged values are not stored")
    // every value at both ends of its range
    for (end in listOf(0, 1)) {
        val v = FloatArray(specs.size) { specs[it].valueAt(if (end == 0) 0 else specs[it].steps) }
        val r = DevShareCode.decode(DevShareCode.encode("X", "1", v, defaults), defaults)
        check(r is DevShareCode.Result.Ok && r.values.contentEquals(v), "round trip with every value at its ${if (end == 0) "minimum" else "maximum"}")
    }
    // random values (deterministic)
    val rnd = java.util.Random(20261022)
    var allOk = true
    repeat(300) {
        val v = FloatArray(specs.size) { specs[it].valueAt(rnd.nextInt(specs[it].steps + 1)) }
        val r = DevShareCode.decode(DevShareCode.encode("SM-A546E", "0.9.${rnd.nextInt(9)}", v, defaults), defaults)
        if (r !is DevShareCode.Result.Ok || !r.values.contentEquals(v) || r.model != "SM-A546E") allOk = false
    }
    check(allOk, "300 random value sets round trip (model with a base32-looking part)")
    // case, spaces and O/I/L substitutions are accepted
    val spaced = DevShareCode.decode(code.replace("-", "- \n"), defaults)
    check(spaced is DevShareCode.Result.Ok && spaced.values.contentEquals(vals), "spaces and line breaks ignored")
    val parts = code.split('-').toMutableList()
    val lowerData = (parts.take(parts.size - 5) + parts.takeLast(5).map { it.lowercase() }).joinToString("-")
    val dLow = DevShareCode.decode(lowerData, defaults)
    check(dLow is DevShareCode.Result.Ok && dLow.values.contentEquals(vals), "data groups in lower case accepted")
    fun reason(t: String) = (DevShareCode.decode(t, defaults) as? DevShareCode.Result.Error)?.reason
    check(reason("") == DevShareCode.Reason.EMPTY, "empty -> EMPTY")
    check(reason("hello world") == DevShareCode.Reason.NOT_A_CODE, "text -> NOT_A_CODE")
    check(reason(code.replaceFirst("RN1", "RN2")) == DevShareCode.Reason.UNKNOWN_VERSION, "RN2 -> UNKNOWN_VERSION")
    val flipped = code.substring(0, code.length - 6) + (if (code[code.length - 6] == 'A') 'B' else 'A') + code.substring(code.length - 5)
    check(reason(flipped) == DevShareCode.Reason.CHECKSUM, "one changed character -> CHECKSUM")
    check(reason(code.replace("SM-S948N", "SM-S948U")) == DevShareCode.Reason.CHECKSUM, "changed model -> CHECKSUM")
    check(reason(code.dropLast(1)) == DevShareCode.Reason.BAD_CHARACTERS, "cut tail -> rejected")
    check(reason(code.substring(0, code.lastIndexOf('-', code.length - 6)) + code.substring(code.length - 5)) != null,
        "missing data group -> rejected")
    check(reason("RN1-" + "A".repeat(300)) == DevShareCode.Reason.TOO_LONG, "very long -> TOO_LONG")
    check(reason("RN1-X-1-!!!!-0000") != null, "bad characters -> rejected")
    // unknown value-set version inside a valid checksum
    run {
        val head = "RN1-X-1-" + "4000-0000"     // byte 0 = 0x20 (not 1)
        val crc = DevShareCode.crc16(head.toByteArray())
        val tail = (2 shl 16) or crc
        val alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        val t = (3 downTo 0).map { alphabet[(tail shr (5 * it)) and 31] }.joinToString("")
        check(reason("$head-$t") == DevShareCode.Reason.UNKNOWN_VERSION, "valid checksum, unknown value-set -> UNKNOWN_VERSION")
    }
    // an index beyond the range is clamped (forward compatibility of ranges)
    run {
        // boundary (bit 0) moved with index 255
        val alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        val bytes = intArrayOf(1, 1, 0, 0, 255)
        var buf = 0; var bits = 0; val sb = StringBuilder()
        for (b in bytes) { buf = (buf shl 8) or b; bits += 8; while (bits >= 5) { sb.append(alphabet[(buf shr (bits - 5)) and 31]); bits -= 5 }; buf = buf and ((1 shl bits) - 1) }
        if (bits > 0) sb.append(alphabet[(buf shl (5 - bits)) and 31])
        while (sb.length % 4 != 0) sb.append('0')
        val head = "RN1-X-1-" + sb.chunked(4).joinToString("-")
        val crc = DevShareCode.crc16(head.toByteArray())
        val tail = ((sb.length / 4) shl 16) or crc
        val t = (3 downTo 0).map { alphabet[(tail shr (5 * it)) and 31] }.joinToString("")
        val r = DevShareCode.decode("$head-$t", defaults)
        check(r is DevShareCode.Result.Ok && r.values[0] == DevParams.BOUNDARY.max, "index beyond the range -> clamped to the maximum")
    }

    // ---------------------------------------------------------------------------------------- warnings
    check(DevMath.evaluate(snapshot()).isEmpty(), "quiet, linked, below threshold: no warning")
    check(DevWarning.NEAR_CEILING in DevMath.evaluate(snapshot(outPeak = -1.2f)) &&
        DevWarning.NEAR_CEILING in DevMath.evaluate(snapshot(gr = 4f)), "output at the ceiling / limiter working -> NEAR_CEILING")
    check(DevWarning.BUZZ_ZONE in DevMath.evaluate(snapshot(dry = -25f, layer = -24f, threshold = -27f)),
        "harmonics at 220 Hz and the band over the threshold -> BUZZ_ZONE")
    check(DevWarning.BUZZ_ZONE !in DevMath.evaluate(snapshot(dry = -20f, layer = -45f, threshold = -27f)),
        "over the threshold by the dry band alone (layer small) -> no BUZZ_ZONE")
    check(DevWarning.BUZZ_ZONE !in DevMath.evaluate(snapshot(f0 = 40f, harm = floatArrayOf(-20f, -22f, -120f, -120f, -120f, -120f, -120f),
        dry = -25f, layer = -24f)), "no harmonic in 220-400 Hz -> no BUZZ_ZONE")
    check(DevWarning.VOLUME_NO_LINK in DevMath.evaluate(snapshot(vol = 70f, link = false)) &&
        DevWarning.VOLUME_NO_LINK !in DevMath.evaluate(snapshot(vol = 70f, link = true)) &&
        DevWarning.VOLUME_NO_LINK !in DevMath.evaluate(snapshot(vol = 40f, link = false)), "volume link off at >= 60% -> VOLUME_NO_LINK")
    // tail: dry note ends at bin 300, layer at bin 330 (150 ms)
    val rd = FloatArray(512) { if (it in 100 until 300) -12f else -100f }
    val rl = FloatArray(512) { if (it in 110 until 330) -20f else -110f }
    check(abs((DevMath.tailMs(rd, rl, 5f) ?: -1f) - 150f) < 0.01f, "tail measured: 150 ms")
    check(DevWarning.TAIL in DevMath.evaluate(snapshot(ringDry = rd, ringLayer = rl)), "tail 150 ms -> TAIL")
    val rl2 = FloatArray(512) { if (it in 110 until 305) -20f else -110f }
    check(DevWarning.TAIL !in DevMath.evaluate(snapshot(ringDry = rd, ringLayer = rl2)), "tail 25 ms -> no TAIL")
    check(DevMath.tailMs(FloatArray(512) { -100f }, rl, 5f) == null, "no dry note -> no tail")
    check(DevMath.inlineWarning(setOf(DevWarning.TAIL, DevWarning.NEAR_CEILING)) == DevWarning.NEAR_CEILING,
        "inline note: the loud output first")
    // tracker
    val store = MapStore()
    val tr = DevWarningTracker(store)
    var t = 0L
    fun step(active: Set<DevWarning>, ms: Long): DevWarning? { t += ms; return tr.update(active, t) }
    // the screen polls ~25 times a second; two readings 2.5 s apart stand for "clear for 2.5 s"
    fun clear() { step(emptySet(), 40); step(emptySet(), 2500) }
    fun hold(a: Set<DevWarning>, ms: Long): DevWarning? { step(a, 40); return step(a, ms) }
    check(step(setOf(DevWarning.TAIL), 100) == null && step(setOf(DevWarning.TAIL), 500) == null,
        "a condition must hold 0.8 s before its dialog")
    check(step(setOf(DevWarning.TAIL), 300) == DevWarning.TAIL && store.count(DevWarning.TAIL) == 1,
        "dialog after 0.8 s; occurrence 1 counted")
    check(!tr.offerHide(DevWarning.TAIL), "1st occurrence: no hide option")
    check(step(setOf(DevWarning.TAIL), 5000) == null, "one dialog per episode")
    check(step(emptySet(), 1000) == null && step(setOf(DevWarning.TAIL), 1000) == null && step(setOf(DevWarning.TAIL), 31000) == null,
        "a short gap (< 2 s) does not start a new episode")
    clear()
    check(hold(setOf(DevWarning.TAIL), 900) == DevWarning.TAIL && store.count(DevWarning.TAIL) == 2, "2nd episode -> 2nd dialog")
    check(!tr.offerHide(DevWarning.TAIL), "2nd occurrence: still no hide option")
    clear()
    check(hold(setOf(DevWarning.TAIL), 900) == null, "within 30 s of the last dialog: none")
    check(step(setOf(DevWarning.TAIL), 30000) == DevWarning.TAIL && tr.offerHide(DevWarning.TAIL),
        "still on after the 30 s pause: 3rd dialog, which offers hiding")
    tr.hide(DevWarning.TAIL)
    clear(); step(setOf(DevWarning.TAIL), 40000)
    check(store.count(DevWarning.TAIL) == 3 && tr.hiddenTypes() == listOf(DevWarning.TAIL), "hidden: no more dialogs")
    // the loud-output warning can never be hidden
    repeat(5) { clear(); hold(setOf(DevWarning.NEAR_CEILING), 31000) }
    check(store.count(DevWarning.NEAR_CEILING) == 5 && !tr.offerHide(DevWarning.NEAR_CEILING), "NEAR_CEILING: dialogs keep coming, never hideable")
    tr.hide(DevWarning.NEAR_CEILING)
    check(DevWarning.NEAR_CEILING !in tr.hiddenTypes(), "hide() ignored for NEAR_CEILING")
    tr.restoreAll()
    check(tr.hiddenTypes().isEmpty() && store.count(DevWarning.TAIL) == 3, "restore: hidden warnings show again, counts kept")
    check(tr.update(setOf(DevWarning.BUZZ_ZONE), t + 100000, dialogOpen = true) == null, "no new dialog while one is open")
    check(tr.unmeasuredOnEntry(false) && !tr.unmeasuredOnEntry(false) && !DevWarningTracker(MapStore()).unmeasuredOnEntry(true),
        "unmeasured notice once, never on a measured phone")

    // ---------------------------------------------------------------------------------------- evidence badges (profile)
    val profiles = File(root, "app/src/general/assets/pvb_profiles").listFiles { f -> f.name.endsWith(".json") }!!
        .map { DeviceProfiles.parse(it.readText()) }
    val s26u = profiles.first { it.id == "s26u" }
    val neutral = profiles.first { it.id == "neutral" }
    val measuredOn = profiles.firstOrNull { it.id == DevEvidenceText.MEASURED_ON_ID }
    check(s26u.shortName == "S26U" && neutral.shortName.isEmpty(), "profiles carry the short device name")
    check(DevEvidenceText.measuredBadge(s26u, measuredOn) == DevEvidenceText.MeasuredBadge(true, "S26U"),
        "on the S26U: \"실측됨\" (here)")
    check(DevEvidenceText.measuredBadge(neutral, measuredOn) == DevEvidenceText.MeasuredBadge(false, "S26U"),
        "on other phones: \"실측 S26U\"")
    val pixel = DeviceProfiles.select(profiles, "Google", "Pixel 9")
    check(!DevEvidenceText.measuredBadge(pixel, measuredOn).here && !DevEvidenceText.thresholdMeasured(pixel) &&
        DevEvidenceText.thresholdMeasured(DeviceProfiles.select(profiles, "samsung", "SM-S948N")),
        "profile picked by model: threshold measured only on the S26U")
    check(abs(s26u.protectThresholdDb(50f) + 15f) < 1e-4f && abs(s26u.protectThresholdDb(80f) + 27f) < 1e-4f &&
        abs(neutral.protectThresholdDb(80f) + 27f) < 1e-4f, "protection threshold: -15 dBFS at 50%, -27 at 80% (S26U line)")
    check(s26u.speakerFloorHz == 150f, "speaker floor 150 Hz")
    // strings: badge texts, the S26U note, threshold labels, same keys en/ko
    fun strings(dir: String): Map<String, String> {
        val f = File(root, "app/src/general/res/$dir/strings_devmode.xml")
        val nl = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(f).getElementsByTagName("string")
        return (0 until nl.length).map { nl.item(it) as org.w3c.dom.Element }.associate { it.getAttribute("name") to it.textContent }
    }
    val en = strings("values")
    val ko = strings("values-ko")
    check(en.keys == ko.keys && en.size > 200, "developer-mode strings: same keys in English and Korean (${en.size})")
    check(ko["dev_tag_measured_here"] == "실측됨" && ko["dev_tag_measured_on"] == "실측 %1\$s" &&
        en["dev_tag_measured_here"] == "Measured" && en["dev_tag_measured_on"] == "Measured on %1\$s", "badge texts (ko/en)")
    check(ko["dev_ev_measured_here_note"] == "정확성은 보장하지 않지만, 이 기기에서 측정용 마이크(UMIK-1)로 여러 차례 실제로 측정한 값이에요.",
        "S26U measurement note (ko)")
    check(ko["dev_threshold_measured"] == "문턱: 실측값" && ko["dev_threshold_estimate"] == "문턱: 추정값 (%1\$s 실측 기준)",
        "threshold labels (ko)")
    for ((k, v) in en + ko) {
        val args = { s: String -> Regex("%(\\d)\\$").findAll(s).map { it.groupValues[1] }.toSet() }
        check(args(en[k] ?: "") == args(ko[k] ?: ""), "same format arguments en/ko in $k")
    }
    for (spec in specs) check("dev_p_${spec.id}_name" in ko && "dev_p_${spec.id}_line" in ko, "${spec.id}: name and one line")
    check(ko["dev_warn_tail_body"]!!.contains("릴리즈를 줄여 보세요") && ko["dev_warn_ceiling_body"] ==
        "소리가 갑자기 커질 수 있어요. 귀를 보호하려고 출력을 제한하고 있어요.", "warning texts from the copy source")

    // ---------------------------------------------------------------------------------------- test sounds
    for (kind in DevTestKind.values()) {
        val g = DevTestSignal()
        g.set(kind, 55.0)
        val buf = FloatArray(2 * 48000 * 4)
        g.render(buf, 48000 * 4, 48000)
        val peak = buf.maxOf { abs(it) }
        check(buf.all { it.isFinite() } && peak in 0.1f..0.4f && (0 until buf.size step 2).all { buf[it] == buf[it + 1] },
            "$kind: finite, peak ${"%.2f".format(peak)} (-8..-20 dBFS), same on both channels")
        val g2 = DevTestSignal(); g2.set(kind, 55.0)
        val buf2 = FloatArray(buf.size); g2.render(buf2, 48000 * 4, 48000)
        check(buf.contentEquals(buf2), "$kind: deterministic")
        val sh = ShortArray(2 * 4800); g2.set(kind, 55.0); g2.renderShort(sh, 4800, 44100)
        check(sh.any { it.toInt() != 0 }, "$kind: 16-bit at 44.1 kHz")
    }
    run {
        // 55 Hz tone: dominant frequency by zero crossings
        val g = DevTestSignal(); g.set(DevTestKind.TONE, 55.0)
        val b = FloatArray(2 * 48000); g.render(b, 48000, 48000)
        var zc = 0
        for (i in 1 until 48000) if ((b[2 * i] >= 0f) != (b[2 * (i - 1)] >= 0f)) zc++
        check(zc in 100..112, "tone 55 Hz: $zc zero crossings in 1 s")
    }
    val buf = FloatArray(2 * 960) { 0.5f }
    check(!DevTestSound.render(buf, 960, 48000) && buf.all { it == 0.5f }, "no test sound: the captured audio is untouched")
    DevTestSound.start(DevTestKind.KICK)
    check(DevTestSound.playing && DevTestSound.render(buf, 960, 48000) && buf.any { it != 0.5f }, "test sound replaces the block")
    DevTestSound.stop()
    val buf3 = FloatArray(2 * 960) { 0.25f }
    check(!DevTestSound.playing && !DevTestSound.render(buf3, 960, 48000) && buf3.all { it == 0.25f }, "stop: captured audio again")

    // ---------------------------------------------------------------------------------------- engine meters (JNI)
    if (jni) {
        fun run(release: Float, kind: DevTestKind): DevSnapshot {
            val e = PvbEngine(48000)
            val p = PvbEngine.defaultParams()
            p[PvbParam.VB_ON] = 1f; p[PvbParam.VB_ALGO] = PvbModels.P1.toFloat(); p[PvbParam.VB_LEVEL_DB] = 4f
            p[PvbParam.DEV_ON] = 1f; p[PvbParam.DEV_METER] = 1f; p[PvbParam.D_RELEASE_MS] = release
            e.setParams(p)
            val g = DevTestSignal(); g.set(kind, 55.0)
            val b = FloatArray(2 * 960)
            val o = FloatArray(2 * 960)
            // kick: 2.25 s = 4.5 kicks, ending just after the last kick's tail
            repeat(if (kind == DevTestKind.KICK) 113 else 150) { g.render(b, 960, 48000); e.processFloat(b, o, b.size) }
            val m = FloatArray(PvbDevMeter.SIZE)
            check(e.copyDevMeters(m), "JNI copyDevMeters")
            e.close()
            return DevSnapshot.fromMeters(m, -6f, 0f, -1f, 50f, true, 0f, -15f)
        }
        val tone = run(32f, DevTestKind.TONE)
        val sum = DevMath.harmonicSummary(tone)
        check(sum != null && abs(sum.f0Hz - 55) <= 2 && sum.count >= 2 && sum.loudestHz in 150..300,
            "JNI meters, 55 Hz tone: f0 ${sum?.f0Hz} Hz, ${sum?.count} harmonics, loudest ${sum?.loudestHz} Hz")
        val k0 = run(32f, DevTestKind.KICK)
        val k1 = run(250f, DevTestKind.KICK)
        val t0 = DevMath.tailMs(k0.ringDry, k0.ringLayer, k0.binMs)
        val t1 = DevMath.tailMs(k1.ringDry, k1.ringLayer, k1.binMs)
        println("kick tail: model release ${t0} ms, release 250 ms ${t1} ms")
        check(t0 != null && t0 < DevMath.TAIL_WARN_MS, "kick loop with the model's release: tail ${t0} ms, no TAIL warning")
        check(t1 != null && t1 > (t0 ?: 0f) + 20f, "release 250 ms: longer tail (${t1} ms)")
    }
    PvbBuild.reset()
    println("DevModeTest: $passed checks passed")
}

import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.DeviceProfiles
import me.timschneeberger.rootlessjamesdsp.pvb.FirstRun
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.ProfileJson
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.SafeCaps
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

// General distribution build: device profile matching on the shipped assets, safe caps when settings are read,
// first-run gate, and the backup/transfer exclusions. Argument: the repository root.

private class Prefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
    val values = initial.toMutableMap()
    override val all: Map<String, *> get() = values.toMap()
    override fun getString(key: String, defValue: String?): String? =
        if (values.containsKey(key)) values[key] as String? else defValue
    override fun getFloat(key: String, defValue: Float): Float =
        if (values.containsKey(key)) values[key] as Float else defValue
    override fun getBoolean(key: String, defValue: Boolean): Boolean =
        if (values.containsKey(key)) values[key] as Boolean else defValue
    override fun getInt(key: String, defValue: Int): Int =
        if (values.containsKey(key)) values[key] as Int else defValue
    override fun edit(): SharedPreferences.Editor = throw UnsupportedOperationException()
}

private fun check(ok: Boolean, what: String) {
    if (!ok) throw AssertionError(what)
}

private fun near(a: Float, b: Float) = kotlin.math.abs(a - b) < 1e-6f

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })
    val assetDir = File(root, "app/src/general/assets/pvb_profiles")
    val profiles = assetDir.listFiles { f -> f.name.endsWith(".json") }!!.sortedBy { it.name }
        .map { DeviceProfiles.parse(it.readText()) }
    check(profiles.map { it.id }.toSet() == setOf("neutral", "s26u"), "shipped profiles: ${profiles.map { it.id }}")

    // --- profile matching ---
    fun pick(man: String?, model: String?) = DeviceProfiles.select(profiles, man, model).id
    check(pick("samsung", "SM-S948N") == "s26u", "S26 Ultra (Korean model) -> s26u")
    check(pick("samsung", "sm-s948b") == "s26u", "case-insensitive model prefix")
    check(pick("SAMSUNG", "SM-S948U1") == "s26u", "case-insensitive manufacturer")
    check(pick("samsung", "SM-S938N") == "neutral", "S25 Ultra is not the S26 Ultra")
    check(pick("samsung", "SM-S928B") == "neutral", "S24 Ultra -> neutral")
    check(pick("samsung", "SM-S947N") == "neutral", "S26+ (other model) -> neutral")
    check(pick("Google", "Pixel 9 Pro") == "neutral", "Pixel -> neutral")
    check(pick("xiaomi", "SM-S948N") == "neutral", "model prefix needs the manufacturer too")
    check(pick(null, null) == "neutral", "unknown device -> neutral")
    check(pick("", "") == "neutral", "empty build values -> neutral")
    val neutral = profiles.first { it.id == "neutral" }
    val s26u = profiles.first { it.id == "s26u" }
    check(!neutral.measured && !neutral.phoneModelCurves, "neutral: not measured, no S26U curves")
    check(s26u.measured && s26u.phoneModelCurves, "s26u: measured, S26U curves")
    check(!neutral.matches("samsung", "SM-S948N"), "neutral never matches by model")

    // Neutral profile values (release audit, section 7)
    val n = neutral.settings
    check(n[PvbSettings.KEY_HP_HZ] == 100f && n[PvbSettings.KEY_LOW_DB] == 0f && n[PvbSettings.KEY_HI_DB] == 0f &&
        n[PvbSettings.KEY_HS_DB] == 0f && n[PvbSettings.KEY_OUT_DB] == -3f && n[PvbSettings.KEY_CEIL_DB] == -1f,
        "neutral EQ values: $n")
    check(n[PvbSettings.KEY_MATCH_ON_DISABLE] == false && n[PvbSettings.KEY_VOL_LINK] == false &&
        n[PvbSettings.KEY_DYN_ON] == false && n[PvbSettings.KEY_VB_ON] == false, "neutral switches off: $n")
    // s26u profile = the s26u build defaults
    val d = PvbSettings()
    val s = s26u.settings
    check(s[PvbSettings.KEY_HP_HZ] == d.hpHz && s[PvbSettings.KEY_LOW_HZ] == d.lowHz && s[PvbSettings.KEY_LOW_DB] == d.lowDb &&
        s[PvbSettings.KEY_LOW_Q] == d.lowQ && s[PvbSettings.KEY_HI_HZ] == d.hiHz && s[PvbSettings.KEY_HI_DB] == d.hiDb &&
        s[PvbSettings.KEY_HI_Q] == d.hiQ && s[PvbSettings.KEY_OUT_DB] == d.outDb && s[PvbSettings.KEY_CEIL_DB] == d.ceilDb &&
        s[PvbSettings.KEY_RELEASE_MS] == d.releaseMs && s[PvbSettings.KEY_MATCH_ON_DISABLE] == d.matchOnDisable,
        "s26u profile must equal the s26u defaults: $s")
    check(s[PvbSettings.KEY_VB_STRENGTH_DB] == 4f && s[PvbSettings.KEY_VB_VOL_LINK] == true,
        "s26u profile: virtual bass +4 with the volume link on: $s")
    // unmeasured phones: EQ first, virtual bass added low (the home "spice" tip)
    check(n[PvbSettings.KEY_VB_STRENGTH_DB] == 2f && n[PvbSettings.KEY_VB_VOL_LINK] == true,
        "neutral profile: virtual bass +2 with the volume link on: $n")

    // Values written on a fresh general install: processing off until the first-run notice, caps applied.
    val wn = DeviceProfiles.valuesFor(neutral, SafeCaps.GENERAL)
    check(wn[PvbSettings.KEY_ENABLE] == false, "fresh install: processing off")
    check(wn[DeviceProfiles.KEY_PROFILE_ID] == "neutral", "profile id recorded")
    val loud = neutral.copy(settings = neutral.settings + mapOf(PvbSettings.KEY_OUT_DB to 0f, PvbSettings.KEY_LOW_DB to 9f,
        PvbSettings.KEY_HP_HZ to 40f, PvbSettings.KEY_RELEASE_MS to 10f, PvbSettings.KEY_CEIL_DB to 0f))
    val wl = DeviceProfiles.valuesFor(loud, SafeCaps.GENERAL)
    check(wl[PvbSettings.KEY_OUT_DB] == -3f && wl[PvbSettings.KEY_LOW_DB] == 6f && wl[PvbSettings.KEY_HP_HZ] == 80f &&
        wl[PvbSettings.KEY_RELEASE_MS] == 30f && wl[PvbSettings.KEY_CEIL_DB] == -1f, "profile values capped: $wl")
    // Unknown keys and wrong types in a profile are ignored.
    val odd = DeviceProfiles.parse("""{"id":"x","match":{"manufacturer":["a"],"model_prefixes":["B"]},
        "settings":{"pvb_out_db":"-3","pvb_hp_hz":90,"evil_key":1,"pvb_vb_enable":1,"pvb_dyn_enable":true}}""")
    check(odd.settings == mapOf(PvbSettings.KEY_HP_HZ to 90f, PvbSettings.KEY_DYN_ON to true), "typed allowlist: ${odd.settings}")
    check(ProfileJson.parse("""{"a":[1,2.5,-3e1],"b":"x\"\u0041\n","c":null,"d":true}""") ==
        mapOf("a" to listOf(1.0, 2.5, -30.0), "b" to "x\"A\n", "c" to null, "d" to true), "ProfileJson")
    var threw = false
    try { ProfileJson.parse("{\"a\":1,}") } catch (e: IllegalArgumentException) { threw = true }
    check(threw, "ProfileJson rejects bad input")

    // --- caps and gate in PvbSettings.load ---
    val extreme = Prefs(mapOf(
        PvbSettings.KEY_ENABLE to true, PvbSettings.KEY_MATCH_ON_DISABLE to true, PvbSettings.KEY_VB_ON to true,
        PvbSettings.KEY_OUT_DB to 0f, PvbSettings.KEY_CEIL_DB to 0f, PvbSettings.KEY_LOW_DB to 9f,
        PvbSettings.KEY_LOW_Q to 3f, PvbSettings.KEY_HP_HZ to 40f, PvbSettings.KEY_RELEASE_MS to 10f,
        PvbSettings.KEY_VB_STRENGTH_DB to 12f, PvbSettings.KEY_HI_DB to 3f,
    ))
    PvbBuild.reset()
    check(PvbModels.fullnessLevelDb == 6f, "s26u fullness preset stays +6")
    val s26uLoad = PvbSettings.load(extreme)
    check(s26uLoad.outDb == 0f && s26uLoad.ceilDb == 0f && s26uLoad.lowDb == 9f && s26uLoad.lowQ == 3f &&
        s26uLoad.hpHz == 40f && s26uLoad.releaseMs == 10f && s26uLoad.vbLevelDb == 12f && s26uLoad.enabled,
        "s26u build: full ranges, unchanged ($s26uLoad)")

    PvbBuild.general = true; PvbBuild.researchUiBuild = false; PvbBuild.recordFeatures = false
    PvbBuild.firstRunConfirmed = true
    val g = PvbSettings.load(extreme)
    check(g.outDb == -3f, "out <= -3 dB: ${g.outDb}")
    check(g.ceilDb == -1f, "ceiling <= -1 dBTP: ${g.ceilDb}")
    check(g.lowDb == 6f, "low-mid <= +6 dB: ${g.lowDb}")
    check(g.lowQ == 2f, "Q <= 2: ${g.lowQ}")
    check(g.hpHz == 80f, "low cut >= 80 Hz: ${g.hpHz}")
    check(g.releaseMs == 30f, "release >= 30 ms: ${g.releaseMs}")
    check(g.vbLevelDb == 9f, "virtual bass <= 9 dB: ${g.vbLevelDb}")
    check(g.hiDb == 3f && g.enabled && g.vbOn, "other values untouched")
    // values inside the caps pass unchanged; research unlock does not lift the caps
    val inside = Prefs(mapOf(PvbSettings.KEY_OUT_DB to -7.5f, PvbSettings.KEY_LOW_DB to -2f, PvbSettings.KEY_HP_HZ to 120f,
        PvbSettings.KEY_RELEASE_MS to 200f, PvbSettings.KEY_VB_STRENGTH_DB to 4f, PvbSettings.KEY_CEIL_DB to -3f))
    PvbBuild.researchUnlocked = true
    val gi = PvbSettings.load(inside)
    check(near(gi.outDb, -7.5f) && gi.lowDb == -2f && gi.hpHz == 120f && gi.releaseMs == 200f && gi.vbLevelDb == 4f &&
        gi.ceilDb == -3f, "values inside the caps unchanged: $gi")
    check(PvbSettings.load(extreme).outDb == -3f, "research unlock keeps the caps")
    PvbBuild.researchUnlocked = false

    // --- 풍성함 증가: +4 in the general build (+6 in s26u), the preset list and the home chip agree ---
    check(PvbModels.fullnessLevelDb == 4f, "general fullness preset is +4")
    val full = PvbModels.presets.first { it.key == PvbModels.PRESET_FULLNESS }
    check(full.levelDb == 4f && PvbModels.presetFor(PvbModels.P1_KEY, 4f)?.key == PvbModels.PRESET_FULLNESS &&
        PvbModels.presetFor(PvbModels.P1_KEY, 6f) == null, "general: P1 +4 is 풍성함 증가, +6 is custom")
    check(HomeLogic.presetWrite(HomeLogic.Chip.FULLNESS, PvbBuild.caps) == (PvbModels.P1_KEY to 4f), "chip writes P1 +4")

    // --- first-run gate ---
    check(FirstRun.processingAllowed(general = false, confirmed = false), "s26u: never gated")
    check(!FirstRun.processingAllowed(general = true, confirmed = false), "general: gated before the notice")
    check(FirstRun.processingAllowed(general = true, confirmed = true), "general: allowed after the notice")
    check(FirstRun.mustShowNotice(true, false) && !FirstRun.mustShowNotice(true, true) && !FirstRun.mustShowNotice(false, false),
        "notice only in general until confirmed")
    PvbBuild.firstRunConfirmed = false
    val gated = PvbSettings.load(extreme)
    check(!gated.enabled && !gated.matchOnDisable && !gated.vbOn, "unconfirmed general: PVB and match-on-disable off ($gated)")
    check(!PvbBuild.processingAllowed, "PvbBuild.processingAllowed follows the gate")
    PvbBuild.firstRunConfirmed = true
    check(PvbSettings.load(extreme).enabled && PvbBuild.processingAllowed, "confirmed: settings as stored")
    check(FirstRun.valuesOnConfirm() == mapOf(PvbSettings.KEY_ENABLE to true, PvbSettings.KEY_VB_ON to true),
        "confirm turns processing and virtual bass on (one consent)")
    check(FirstRun.valuesOnConfirm().keys.none { it == PvbSettings.KEY_VB_STRENGTH_DB }, "confirm keeps the profile's strength")
    val cmds = FirstRun.adbCommands("kr.ksysh3.rootnote")
    check(cmds.size == 3 && cmds.all { "kr.ksysh3.rootnote" in it } &&
        cmds[0] == "adb shell pm grant kr.ksysh3.rootnote android.permission.DUMP" &&
        cmds[1] == "adb shell appops set kr.ksysh3.rootnote PROJECT_MEDIA allow", "ADB commands use the package: $cmds")
    PvbBuild.reset()
    check(PvbSettings.load(extreme).outDb == 0f, "reset restores the s26u behaviour")

    // --- backup / device transfer exclusions ---
    val required = listOf("pvb_settings", "pvb_track_levels", "pvb_ab", "pvb_measure", "pvb_buzz", "pvb_match_cache",
        "pvb_ui", "pvb_flags")
    val xml = File(root, "app/src/main/res/xml")
    fun excludes(file: String, section: String): Set<String> {
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(File(xml, file))
        val sections = doc.getElementsByTagName(section)
        check(sections.length == 1, "$file: one <$section>")
        val el = sections.item(0) as org.w3c.dom.Element
        val ex = el.getElementsByTagName("exclude")
        return (0 until ex.length).map { ex.item(it) as org.w3c.dom.Element }
            .filter { it.getAttribute("domain") == "sharedpref" }.map { it.getAttribute("path").removeSuffix(".xml") }.toSet()
    }
    for ((file, section) in listOf("backup_rules.xml" to "full-backup-content",
        "data_extraction_rules.xml" to "cloud-backup", "data_extraction_rules.xml" to "device-transfer")) {
        val ex = excludes(file, section)
        val missing = required.filter { it !in ex }
        check(missing.isEmpty(), "$file <$section> must exclude $missing")
    }
    // every PVB preferences file named in the app source is excluded
    val src = File(root, "app/src/main/java")
    val direct = Regex("getSharedPreferences\\(\\s*\"(pvb_[a-z_]+)\"")
    val constant = Regex("(?:PREFS|PREFS_NAME|AB_PREFS|FLAGS_PREFS)\\s*=\\s*\"(pvb_[a-z_]+)\"")
    val named = src.walkTopDown().filter { it.extension == "kt" }.flatMap { f ->
        val text = f.readText()
        direct.findAll(text).map { it.groupValues[1] } + constant.findAll(text).map { it.groupValues[1] }
    }.toSet()
    check(named.isNotEmpty() && required.containsAll(named), "pvb prefs files in source $named all excluded")

    println("General build: profiles (s26u SM-S948*, neutral fallback), caps (out -3, ceil -1, low +6, Q 2, HP 80, " +
        "release 30, VB 9), first-run gate, ADB commands, backup/transfer exclusions (${required.size} files) passed")
}

import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic.Chip
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic.Headline
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic.LinkLine
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.SafeCaps
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

// General build home screen ("Rootnote" main screen): master state, preset chips, slider range and caps, the
// volume-link line, and the English/Korean strings of the screen. Argument: the repository root.

private class HomePrefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
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

private fun expect(ok: Boolean, what: String) {
    if (!ok) throw AssertionError(what)
}

private fun close(a: Float, b: Float) = kotlin.math.abs(a - b) < 1e-4f

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })
    val general = SafeCaps.GENERAL

    // --- slider range and caps ---
    expect(HomeLogic.sliderMax(general) == 9, "general slider is 0..9 dB")
    expect(HomeLogic.sliderMax(null) == 12, "s26u slider is 0..12 dB")
    expect(HomeLogic.sliderValue(12f, general) == 9, "12 dB shows as the 9 dB cap")
    expect(HomeLogic.sliderValue(3.6f, general) == 4, "whole dB steps")
    expect(HomeLogic.sliderValue(-5f, general) == 0, "below 0 -> 0")
    expect(HomeLogic.sliderValue(Float.NaN, general) == 6, "non-finite -> default 6")
    expect(HomeLogic.sliderValue(12f, null) == 12, "s26u keeps 12")

    // --- preset chips: derived from model + level like the advanced screen's mode list ---
    expect(HomeLogic.selectedChip(PvbModels.P1_KEY, 6f) == Chip.FULLNESS, "P1 at +6 -> 풍성함 증가")
    expect(HomeLogic.selectedChip(PvbModels.GENTLE12_KEY, 9f) == Chip.DEEP, "12 dB/oct model at +9 -> 초저역 강조")
    expect(HomeLogic.selectedChip(PvbModels.P1_KEY, 9f) == Chip.CUSTOM, "P1 at +9 -> custom")
    expect(HomeLogic.selectedChip(PvbModels.GENTLE12_KEY, 6f) == Chip.CUSTOM, "12 dB/oct model at +6 -> custom")
    expect(HomeLogic.selectedChip(PvbModels.REFERENCE_KEY, 6f) == Chip.CUSTOM, "reference model -> custom")
    expect(HomeLogic.selectedChip("no-such-model", 6f) == Chip.FULLNESS, "unknown key = default model (P1)")
    expect(HomeLogic.selectedChip(PvbModels.P1_KEY, 6f, customPinned = true) == Chip.CUSTOM, "custom tapped stays custom")
    for (p in PvbModels.presets) {
        val chip = HomeLogic.selectedChip(p.modelKey, p.levelDb)
        expect(chip.presetKey == p.key, "every preset is its own chip (${p.key} -> $chip)")
    }
    expect(HomeLogic.modelKey(PvbModels.P1) == PvbModels.P1_KEY, "P1 id -> key")
    expect(HomeLogic.modelKey(PvbModels.GENTLE12) == PvbModels.GENTLE12_KEY, "12 dB/oct id -> key")
    expect(HomeLogic.modelKey(999) == PvbModels.DEFAULT_KEY, "unknown id -> default key")

    // what tapping a chip writes: model + level within the caps; custom writes nothing
    expect(HomeLogic.presetWrite(Chip.FULLNESS, general) == (PvbModels.P1_KEY to 6f), "풍성함 증가 writes P1, +6")
    expect(HomeLogic.presetWrite(Chip.DEEP, general) == (PvbModels.GENTLE12_KEY to 9f), "초저역 강조 writes 12 dB/oct, +9")
    expect(HomeLogic.presetWrite(Chip.CUSTOM, general) == null, "사용자 지정 writes nothing")
    val tight = general.copy(vbLevelMax = 7f)
    expect(HomeLogic.presetWrite(Chip.DEEP, tight) == (PvbModels.GENTLE12_KEY to 7f), "a preset level never exceeds the cap")
    // a written preset reads back as the same chip (through the real settings reader, general caps)
    try {
        PvbBuild.general = true; PvbBuild.firstRunConfirmed = true
        for (chip in listOf(Chip.FULLNESS, Chip.DEEP)) {
            val (model, level) = HomeLogic.presetWrite(chip, PvbBuild.caps)!!
            val s = PvbSettings.load(HomePrefs(mapOf(PvbSettings.KEY_VB_ALGO to model, PvbSettings.KEY_VB_STRENGTH_DB to level)))
            expect(HomeLogic.selectedChip(HomeLogic.modelKey(s.vbAlgo), s.vbLevelDb) == chip, "$chip round trip")
        }
        // a stored level above the general cap is played (and shown) as 9: the deep preset then matches
        val s = PvbSettings.load(HomePrefs(mapOf(PvbSettings.KEY_VB_ALGO to PvbModels.GENTLE12_KEY, PvbSettings.KEY_VB_STRENGTH_DB to 12f)))
        expect(close(s.vbLevelDb, 9f) && HomeLogic.sliderValue(s.vbLevelDb, PvbBuild.caps) == 9, "12 dB stored -> 9 dB")
    } finally {
        PvbBuild.reset()
    }

    // --- master switch and headline ---
    val on = PvbSettings(enabled = true, vbOn = true)
    expect(HomeLogic.headline(on, serviceRunning = true) == Headline.FILLING, "running + on + vb -> filling")
    expect(HomeLogic.masterOn(on, true), "master on")
    expect(HomeLogic.headline(on, serviceRunning = false) == Headline.ORIGINAL, "service stopped -> original")
    expect(!HomeLogic.masterOn(on, false), "master off when the service is stopped")
    expect(HomeLogic.headline(on.copy(enabled = false), true) == Headline.ORIGINAL, "PVB off -> original")
    expect(HomeLogic.headline(on.copy(vbOn = false), true) == Headline.CORRECTION_ONLY, "vb off -> correction only")
    expect(!HomeLogic.masterOn(on.copy(vbOn = false), true), "correction only is not 'on'")
    // first-run gate: before the notice is confirmed the general build reads processing as off
    try {
        PvbBuild.general = true; PvbBuild.firstRunConfirmed = false
        val gated = PvbSettings.load(HomePrefs(mapOf(PvbSettings.KEY_ENABLE to true, PvbSettings.KEY_VB_ON to true)))
        expect(HomeLogic.headline(gated, true) == Headline.ORIGINAL && !HomeLogic.masterOn(gated, true), "gate keeps the master off")
        PvbBuild.firstRunConfirmed = true
        val open = PvbSettings.load(HomePrefs(mapOf(PvbSettings.KEY_ENABLE to true, PvbSettings.KEY_VB_ON to true)))
        expect(HomeLogic.masterOn(open, true), "confirmed -> master follows the settings")
    } finally {
        PvbBuild.reset()
    }

    // --- volume-link line (same arithmetic as the controller: VolumeLevelLink) ---
    val link = PvbSettings(vbLevelDb = 6f, vbVolLink = true)
    expect(HomeLogic.linkLine(link.copy(vbVolLink = false), 10, 15) == LinkLine.Off, "link off")
    expect(HomeLogic.linkLine(link, 0, 0) == LinkLine.VolumeUnknown, "unknown max -> unknown volume")
    expect(HomeLogic.linkLine(link, -1, 15) == LinkLine.VolumeUnknown, "unknown index -> unknown volume")
    // Samsung 15 steps: index 10 = 60 %; (60 - 40) * 0.2 = 4 dB off; 6 - 4 = +2 dB played (the mockup's example)
    val at60 = HomeLogic.linkLine(link, 10, 15)
    expect(at60 is LinkLine.Reduced && at60.volumePct == 60 && close(at60.reductionDb, 4f) && close(at60.appliedDb, 2f),
        "60 % -> -4 dB, applied +2 dB ($at60)")
    expect(HomeLogic.linkLine(link, 7, 15) == LinkLine.NoReduction(40), "40 % (reference) -> no reduction")
    expect(HomeLogic.linkLine(link, 1, 15) == LinkLine.NoReduction(0), "lowest step -> no reduction")
    val loud = HomeLogic.linkLine(link.copy(vbLevelDb = 0f), 16, 15)
    expect(loud is LinkLine.Reduced && loud.volumePct == 100 && close(loud.reductionDb, 12f) && close(loud.appliedDb, -12f),
        "100 % at 0 dB -> -12 dB, floor -12 ($loud)")
    val capped = HomeLogic.linkLine(link.copy(vbVolMaxDb = 3f), 16, 15)
    expect(capped is LinkLine.Reduced && close(capped.reductionDb, 3f) && close(capped.appliedDb, 3f), "max reduction setting respected")

    // --- number formatting ---
    expect(HomeLogic.signedDb(4f) == "+4", "positive whole")
    expect(HomeLogic.signedDb(-4f) == "−4", "negative uses U+2212")
    expect(HomeLogic.signedDb(2.44f) == "+2.4", "one decimal")
    expect(HomeLogic.signedDb(-0.04f) == "0", "rounds to zero")
    expect(HomeLogic.signedDb(0f) == "0", "zero")
    expect(HomeLogic.signedDb(Float.NaN) == "?", "non-finite")
    expect(HomeLogic.levelLabel(6) == "+6", "slider label")

    // --- strings of the screen: same keys in English and Korean, Android-safe text ---
    fun strings(dir: String): Map<String, String> {
        val f = File(root, "app/src/general/res/$dir/strings_home.xml")
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(f)
        val nodes = doc.getElementsByTagName("string")
        return (0 until nodes.length).associate { i ->
            val e = nodes.item(i) as org.w3c.dom.Element
            e.getAttribute("name") to e.textContent
        }
    }
    val en = strings("values")
    val ko = strings("values-ko")
    expect(en.isNotEmpty() && en.keys == ko.keys, "home strings: same keys (en-only ${en.keys - ko.keys}, ko-only ${ko.keys - en.keys})")
    val placeholder = Regex("%(\\d+\\$)?[sdf]")
    for ((key, text) in en + ko.mapKeys { "ko:" + it.key }) {
        // an apostrophe must be escaped (\') in Android string resources; the parsed text keeps the backslash
        expect(Regex("(?<!\\\\)'").find(text) == null, "bare apostrophe in $key: $text")
        val hasArgs = placeholder.containsMatchIn(text)
        // in a format string a literal percent sign must be written %%
        if (hasArgs) expect(Regex("%(?!(\\d+\\$)?[sdf%])").find(text.replace("%%", "")) == null, "lone % in format string $key")
    }
    for (key in en.keys) {
        fun args(t: String) = placeholder.findAll(t).map { it.value }.sorted().toList()
        expect(args(en[key]!!) == args(ko[key]!!), "same format arguments in $key")
    }
    // the approved Korean copy
    expect(ko["home_headline_filling"] == "저음을 채우고 있어요", "Korean headline (on)")
    expect(ko["home_headline_original"] == "원래 소리로 듣고 있어요", "Korean headline (off)")
    expect(ko["home_chip_fullness"] == "풍성함 증가" && ko["home_chip_deep"] == "초저역 강조" && ko["home_chip_custom"] == "사용자 지정", "chip names")

    // spatial (crosstalk cancellation): presets are mode + strength only; turning on picks balanced unless stored
    expect(HomeLogic.xtcPreset(PvbSettings.XTC_CENTRE, -6f) == HomeLogic.XtcPreset.SUBTLE, "spatial subtle")
    expect(HomeLogic.xtcPreset(PvbSettings.XTC_FULL, -4.5f) == HomeLogic.XtcPreset.BALANCED, "spatial balanced")
    expect(HomeLogic.xtcPreset(PvbSettings.XTC_FULL, -3f) == HomeLogic.XtcPreset.CLEAR, "spatial clear")
    expect(HomeLogic.xtcPreset(PvbSettings.XTC_FULL, -6f) == HomeLogic.XtcPreset.CUSTOM, "spatial full + gentle = custom")
    expect(HomeLogic.xtcPreset(PvbSettings.XTC_OFF, -6f) == HomeLogic.XtcPreset.CUSTOM, "spatial off = no preset")
    expect(HomeLogic.xtcResumeMode(PvbSettings.XTC_CENTRE) == PvbSettings.XTC_CENTRE &&
        HomeLogic.xtcResumeMode(PvbSettings.XTC_FULL) == PvbSettings.XTC_FULL &&
        HomeLogic.xtcResumeMode(PvbSettings.XTC_OFF) == null && HomeLogic.xtcResumeMode(null) == null && HomeLogic.xtcResumeMode(7) == null,
        "spatial on again: the mode it had (subtle stays subtle), else none (balanced)")
    expect(HomeLogic.xtcDistanceSteps() == 7 && HomeLogic.xtcDistanceStep(40f) == 3 && HomeLogic.xtcDistanceCm(3) == 40 &&
        HomeLogic.xtcDistanceStep(99f) == 7 && HomeLogic.xtcDistanceCm(0) == 25, "distance slider 25..60 cm in 5 cm steps")
    expect(PvbSettings().xtcMode == PvbSettings.XTC_OFF, "spatial off by default")
    expect(ko["home_tab_bass"] == "가상 저음" && ko["home_tab_spatial"] == "공간감", "tab names")

    // limiter pressure hint: on at 30 %, off below 15 %, kept in between, never without virtual bass playing
    expect(!HomeLogic.limiterPressure(false, true, 29f) && HomeLogic.limiterPressure(false, true, 30f), "pressure on at 30 %")
    expect(HomeLogic.limiterPressure(true, true, 20f) && !HomeLogic.limiterPressure(false, true, 20f), "pressure hysteresis")
    expect(!HomeLogic.limiterPressure(true, true, 14.9f), "pressure off below 15 %")
    expect(!HomeLogic.limiterPressure(true, false, 90f) && !HomeLogic.limiterPressure(true, true, Float.NaN), "pressure needs vb")
    for (k in listOf("home_pressure_title", "home_pressure_body", "home_pressure_action", "home_hold_novb_title",
            "home_hold_novb_line", "home_hold_novb_active", "home_hold_novb_a11y", "home_spice_title", "home_spice_body"))
        expect(!ko[k].isNullOrBlank(), "ko string $k")

    println("Home screen: caps 0..9, chips derived from model + level (custom pinned), preset writes within caps, " +
        "master/headline with the first-run gate, volume-link line (60 % -> −4 dB, applied +2 dB), strings en/ko: OK")
}

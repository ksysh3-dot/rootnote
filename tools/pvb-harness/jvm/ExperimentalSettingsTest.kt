import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.DeviceProfiles
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

// Experimental layer options ("실험 기능"): keys, defaults off (settings and preference XML), stored values read,
// wrong types fall back, not part of device profiles, parameter indices, en/ko strings.

private class XPrefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
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
    override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
        override fun putString(key: String, value: String?) = this
        override fun putInt(key: String, value: Int) = this
        override fun putFloat(key: String, value: Float) = this
        override fun apply() {}
    }
}

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })
    val keys = listOf(PvbSettings.KEY_X_SMOOTH, PvbSettings.KEY_X_RISE, PvbSettings.KEY_X_S1M, PvbSettings.KEY_X_DENSE)
    check(keys == listOf("pvb_x_smooth", "pvb_x_rise", "pvb_x_s1m", "pvb_x_dense"))

    // 1. Defaults off; stored values are read; a value of another type falls back to off.
    val d = PvbSettings.load(XPrefs())
    check(!d.xSmooth && !d.xRise && !d.xS1m && !d.xDense) { "defaults must be off" }
    check(PvbSettings() == PvbSettings().copy(xSmooth = false, xRise = false, xS1m = false, xDense = false))
    val on = PvbSettings.load(XPrefs(keys.associateWith { true }))
    check(on.xSmooth && on.xRise && on.xS1m && on.xDense)
    val one = PvbSettings.load(XPrefs(mapOf(PvbSettings.KEY_X_RISE to true)))
    check(!one.xSmooth && one.xRise && !one.xS1m && !one.xDense)
    val typed = PvbSettings.load(XPrefs(mapOf(PvbSettings.KEY_X_SMOOTH to "true", PvbSettings.KEY_X_DENSE to 1f)))
    check(!typed.xSmooth && !typed.xDense)

    // 2. Not part of device profiles.
    for (k in keys) check(k !in DeviceProfiles.FLOAT_KEYS && k !in DeviceProfiles.BOOL_KEYS) { "$k in device profiles" }

    // 3. Parameter indices follow DIAGNOSTIC_SOLO in the order of pvb_engine.h.
    check(PvbParam.X_SMOOTH == 29 && PvbParam.X_RISE == 30 && PvbParam.X_S1M == 31 && PvbParam.X_DENSE == 32 &&
        PvbParam.COUNT == 47)   // 33 + 14 developer-mode values (DevModeTest)
    val dp = me.timschneeberger.rootlessjamesdsp.pvb.PvbEngine.defaultParams()
    check(dp.size == PvbParam.COUNT && (PvbParam.X_SMOOTH..PvbParam.X_DENSE).all { dp[it] == 0f }) { "defaultParams" }

    // 4. Preference XML: four switches with defaultValue false, depending on the virtual bass switch; header + link.
    val doc = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder()
        .parse(File(root, "app/src/main/res/xml/dsp_pvb_preferences.xml"))
    val android = "http://schemas.android.com/apk/res/android"
    val all = doc.getElementsByTagName("*")
    val byKey = (0 until all.length).map { all.item(it) as org.w3c.dom.Element }
        .filter { it.hasAttributeNS(android, "key") }.associateBy { it.getAttributeNS(android, "key") }
    for (k in keys) {
        val e = byKey[k] ?: error("$k missing in dsp_pvb_preferences.xml")
        check(e.getAttributeNS(android, "defaultValue") == "false") { "$k default" }
        check(e.getAttributeNS(android, "dependency") == PvbSettings.KEY_VB_ON) { "$k dependency" }
        check(e.tagName.endsWith("MaterialSwitchPreference")) { "$k widget" }
        check((e.parentNode as org.w3c.dom.Element).getAttributeNS(android, "key") == PvbSettings.KEY_ENABLE)
    }
    check(byKey.containsKey(PvbSettings.KEY_X_HEADER) && byKey.containsKey(PvbSettings.KEY_X_FEEDBACK))
    check(byKey[PvbSettings.KEY_X_HEADER]!!.getAttributeNS(android, "persistent") == "false")

    // 5. Strings: same pvb_x_* keys in English and Korean, the feedback link, the agreed Korean summary.
    fun strings(dir: String): Map<String, String> {
        val s = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(File(root, "app/src/main/res/$dir/strings_pvb.xml")).getElementsByTagName("string")
        return (0 until s.length).map { s.item(it) as org.w3c.dom.Element }
            .filter { it.getAttribute("name").startsWith("pvb_x_") }.associate { it.getAttribute("name") to it.textContent }
    }
    val en = strings("values")
    val ko = strings("values-ko")
    check(en.size == 12 && en.keys == ko.keys) { "pvb_x strings: en ${en.keys} ko ${ko.keys}" }
    for ((k, t) in en + ko) check(Regex("(?<!\\\\)'").find(t) == null) { "bare apostrophe in $k" }
    check(ko["pvb_x_header"] == "실험 기능")
    check(ko["pvb_x_header_summary"]!!.startsWith("기본은 꺼짐. 개발자 청취에서는 차이가 작거나 없었지만, 사람·기기에 따라 다르게 들릴 수 있어 넣어 둔 기능입니다."))
    check(en["pvb_x_feedback_summary"]!!.contains("github.com/ksysh3-dot/rootnote/issues") &&
        ko["pvb_x_feedback_summary"]!!.contains("github.com/ksysh3-dot/rootnote/issues"))

    println("ExperimentalSettingsTest: keys, defaults off (settings + XML), not in profiles, indices 29..32, en/ko strings: OK")
}

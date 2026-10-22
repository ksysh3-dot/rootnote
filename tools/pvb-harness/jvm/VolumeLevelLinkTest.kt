import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink
import kotlin.math.abs

// Alpha 3.2 "볼륨 연동 세기": volume index -> %, reduction, effective level, settings defaults and clamps.

private class LinkPrefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
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
        private val next = mutableMapOf<String, Any?>()
        override fun putString(key: String, value: String?) = apply { next[key] = value }
        override fun putInt(key: String, value: Int) = apply { next[key] = value }
        override fun putFloat(key: String, value: Float) = apply { next[key] = value }
        override fun apply() { values.putAll(next) }
    }
}

private fun near(a: Float, b: Float, eps: Float = 0.01f) = abs(a - b) <= eps

fun main() {
    val L = VolumeLevelLink

    // 1. Volume index -> % (inverse of refIndex = floor(pct / 100 * max) + 1).
    check(L.volumePct(1, 15) == 0f)
    check(near(L.volumePct(13, 15), 80f)) { "13/15 -> ${L.volumePct(13, 15)}" }
    check(near(L.volumePct(8, 15), 46.67f)) { "8/15 -> ${L.volumePct(8, 15)}" }
    check(L.volumePct(0, 15) == 0f)                     // muted
    check(L.volumePct(16, 15) == 100f)                  // max index (= fine 150) clamps to 100
    check(L.volumePct(5, 0) == 0f && L.volumePct(0, -1) == 0f)   // unknown volume
    // round trip with the controller's reference mapping for every whole reference %
    for (pct in 20..70) {
        val refIndex = (kotlin.math.floor(pct / 100f * 15).toInt() + 1).coerceIn(1, 15)
        val back = L.volumePct(refIndex, 15)
        check(back <= pct + 0.001f && back > pct - 100f / 15) { "pct $pct -> index $refIndex -> $back" }
    }

    // 2. Reduction with the defaults (ref 40%, 0.2 dB/%, max 12 dB).
    check(L.REF_PCT_DEFAULT == 40f && L.SLOPE_DEFAULT == 0.2f && L.MAX_DB_DEFAULT == 12f)
    val expected = mapOf(30f to 0f, 40f to 0f, 50f to 2f, 80f to 8f, 100f to 12f)
    for ((pct, db) in expected) {
        val r = L.reductionDb(pct, 40f, 0.2f, 12f)
        check(near(r, db)) { "reduction at $pct% = $r, want $db" }
        check(near(L.reductionDb(pct), db))            // same through the defaults
    }
    // index 13 of 15 (phone "80%") -> -8 dB
    check(near(L.reductionDb(L.volumePct(13, 15)), 8f))

    // 3. Max clamp, never negative.
    check(L.reductionDb(100f, 20f, 0.5f, 12f) == 12f)  // 40 dB asked, 12 allowed
    check(L.reductionDb(100f, 40f, 0.5f, 3f) == 3f)
    check(L.reductionDb(10f, 40f, 0.5f, 12f) == 0f)
    check(L.reductionDb(80f, 40f, 0.2f, -5f) == 0f)    // a damaged negative max allows nothing

    // 4. Non-finite inputs -> 0.
    for (bad in listOf(Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)) {
        check(L.reductionDb(bad, 40f, 0.2f, 12f) == 0f)
        check(L.reductionDb(80f, bad, 0.2f, 12f) == 0f)
        check(L.reductionDb(80f, 40f, bad, 12f) == 0f)
        check(L.reductionDb(80f, 40f, 0.2f, bad) == 0f)
        check(L.effectiveLevelDb(6f, bad) == 6f)       // unknown reduction = none
    }

    // 5. Effective level and the floor.
    check(L.effectiveLevelDb(12f, 8f) == 4f)
    check(L.effectiveLevelDb(6f, 0f) == 6f)
    check(L.effectiveLevelDb(0f, 12f) == -12f)           // exactly the floor
    check(L.effectiveLevelDb(2f, 12f) == -10f)
    check(L.effectiveLevelDb(0f, 12f, -6f) == -6f)       // floor clamp
    check(L.effectiveLevelDb(6f, -3f) == 6f)             // a negative reduction never raises the level
    // the comparison's silent layer stays silent (never lifted to the floor)
    check(L.effectiveLevelDb(PvbSettings.VB_LEVEL_OFF, 0f) == PvbSettings.VB_LEVEL_OFF)
    check(L.effectiveLevelDb(PvbSettings.VB_LEVEL_OFF, 12f) == PvbSettings.VB_LEVEL_OFF)

    // 6. Settings: default off, defaults, ranges, link off -> slider unchanged.
    val d = PvbSettings.load(LinkPrefs())
    check(!d.vbVolLink && d.vbVolRefPct == 40f && d.vbVolSlope == 0.2f && d.vbVolMaxDb == 12f)
    check(PvbSettings.KEY_VB_VOL_LINK == "pvb_vb_vol_link" && PvbSettings.KEY_VB_VOL_REF_PCT == "pvb_vb_vol_ref_pct" &&
        PvbSettings.KEY_VB_VOL_SLOPE == "pvb_vb_vol_slope" && PvbSettings.KEY_VB_VOL_MAX_DB == "pvb_vb_vol_max_db")
    val off = PvbSettings.load(LinkPrefs(mapOf(PvbSettings.KEY_VB_STRENGTH_DB to 9f)))
    for (i in 0..16) {
        check(L.levelFor(off, i, 15) == 9f) { "link off changed the level at index $i" }
        check(L.reductionFor(off, i, 15) == 0f)
    }
    val on = PvbSettings.load(LinkPrefs(mapOf(PvbSettings.KEY_VB_STRENGTH_DB to 12f, PvbSettings.KEY_VB_VOL_LINK to true)))
    check(near(L.levelFor(on, 13, 15), 4f))              // "볼륨 80% -> -8 dB (적용 세기 +4 dB)"
    check(near(L.levelFor(on, 8, 15), 10.67f, 0.02f))    // 46.7% -> -1.3 dB
    check(L.levelFor(on, 1, 15) == 12f)
    check(L.levelFor(on, 0, 0) == 12f)                    // volume not read yet: no reduction
    check(on.vbLevelDb == 12f)                            // the stored slider value itself is untouched
    // Damaged / out-of-range stored values are clamped into the slider ranges; wrong types fall back.
    val wild = PvbSettings.load(LinkPrefs(mapOf(
        PvbSettings.KEY_VB_VOL_LINK to true, PvbSettings.KEY_VB_VOL_REF_PCT to 95.4f,
        PvbSettings.KEY_VB_VOL_SLOPE to 3f, PvbSettings.KEY_VB_VOL_MAX_DB to Float.NaN)))
    check(wild.vbVolRefPct == 70f && wild.vbVolSlope == 0.5f && wild.vbVolMaxDb == 12f)
    val low = PvbSettings.load(LinkPrefs(mapOf(
        PvbSettings.KEY_VB_VOL_REF_PCT to 44.6f, PvbSettings.KEY_VB_VOL_SLOPE to 0f, PvbSettings.KEY_VB_VOL_MAX_DB to 1f)))
    check(low.vbVolRefPct == 45f && low.vbVolSlope == 0.1f && low.vbVolMaxDb == 3f)
    val typed = PvbSettings.load(LinkPrefs(mapOf(PvbSettings.KEY_VB_VOL_LINK to "yes", PvbSettings.KEY_VB_VOL_SLOPE to "0.3")))
    check(!typed.vbVolLink && typed.vbVolSlope == 0.2f)

    println("VolumeLevelLinkTest: ok")
}

import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings

// Same semantics as Android's SharedPreferencesImpl for what PvbSettings uses: a getter of the wrong type throws.
private class Prefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
    val values = initial.toMutableMap()
    var writes = 0
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
        override fun apply() { values.putAll(next); writes++ }
    }
}

private fun migrated(initial: Map<String, Any?>): Prefs = Prefs(initial).also {
    PvbSettings.migrateVirtualBassModel(it)
    val writes = it.writes
    PvbSettings.migrateVirtualBassModel(it)   // idempotent: a second run writes nothing
    check(it.writes == writes) { "second migration wrote again for $initial" }
}

fun main() {
    val key = PvbSettings.KEY_VB_ALGO
    val schema = PvbSettings.KEY_VB_MODEL_SCHEMA
    val legacyLevel = PvbSettings.KEY_VB_LEVEL_DB
    val strength = PvbSettings.KEY_VB_STRENGTH_DB

    // Catalogue: every alpha 2 model, P1 + C1 (14, research branch), Resultant core v1.5 / v1.6 (15, 16, experimental),
    // P1+ / P1++ / P1++ v0.3 (11-13), and the re-exposed gentle12 (ID 3); P1 is the default.
    check(PvbModels.models.map { it.id } == listOf(6, 15, 16, 14, 11, 12, 13, 4, 7, 8, 9, 10, 3))
    check(PvbModels.models.map { it.key }.distinct().size == 13)
    check(PvbModels.DEFAULT_KEY == "alpha2_p1" && PvbModels.fromKey(null).id == PvbModels.P1)
    check(PvbModels.fromKey("alpha2_reference").id == 4 && PvbModels.fromKey("alpha3_gentle12").id == 3)
    for (model in PvbModels.models) check(PvbSettings.vbAlgoName(model.id) == model.title)

    // Unrelated controls that no migration may touch.
    val preserved = mapOf<String, Any?>(
        PvbSettings.KEY_VB_ON to true, PvbSettings.KEY_OUT_DB to -13f, PvbSettings.KEY_LOW_DB to 5f,
        PvbSettings.KEY_HP_HZ to 120f, "unrelated" to "keep")

    // 1. Alpha 2 reference (stored by default or chosen) -> P1 once, recorded.
    for (oldSchema in listOf(0, 2)) {
        val p = migrated(preserved + mapOf(key to PvbModels.REFERENCE_KEY, schema to oldSchema, legacyLevel to "6"))
        check(p.values[key] == PvbModels.P1_KEY)
        check(p.values[schema] == PvbSettings.VB_MODEL_SCHEMA && PvbSettings.VB_MODEL_SCHEMA == 3)
        check(p.values[PvbSettings.KEY_VB_ALPHA2_MODEL] == PvbModels.REFERENCE_KEY)
        check(p.values[PvbSettings.KEY_VB_LEGACY_MODEL] == null)
        check(preserved.all { (k, v) -> p.values[k] == v })
        val s = PvbSettings.load(p)
        check(s.vbAlgo == PvbModels.P1 && s.vbOn && s.vbLevelDb == 6f && s.outDb == -13f && s.lowDb == 5f && s.hpHz == 120f)
        check(PvbModels.presetFor(p.values[key] as String, s.vbLevelDb)?.key == PvbModels.PRESET_FULLNESS)
        // Choosing the reference again after the migration is respected.
        p.values[key] = PvbModels.REFERENCE_KEY
        PvbSettings.migrateVirtualBassModel(p)
        check(p.values[key] == PvbModels.REFERENCE_KEY && PvbSettings.load(p).vbAlgo == PvbModels.REFERENCE)
    }

    // 2. Any other current model is kept.
    for (model in PvbModels.models.filter { it.key != PvbModels.REFERENCE_KEY }) {
        val p = migrated(preserved + mapOf(key to model.key, schema to 2, legacyLevel to "3"))
        check(p.values[key] == model.key && PvbSettings.load(p).vbAlgo == model.id)
        check(p.values[PvbSettings.KEY_VB_ALPHA2_MODEL] == null && p.values[PvbSettings.KEY_VB_LEGACY_MODEL] == null)
        check(PvbSettings.load(p).vbLevelDb == 3f)
    }

    // 3. Alpha 1 names / unknown (never migrated) -> default model, old name kept.
    for (old in listOf("hpv", "bankstown", "hpv52m", "gentle128", "gentle_strong", "gentle_adaptive", "unknown")) {
        val p = migrated(preserved + (key to old))
        check(p.values[key] == PvbModels.DEFAULT_KEY && p.values[PvbSettings.KEY_VB_LEGACY_MODEL] == old)
        check(preserved.all { (k, v) -> p.values[k] == v })
        check(PvbSettings.load(p).vbAlgo == PvbModels.P1)
    }

    // 4. Corrupt stored model types never reach the ListPreference.
    for (bad in listOf<Any>(2, true, 1f)) {
        val p = migrated(preserved + mapOf(key to bad, schema to 2))
        check(p.values[key] == PvbModels.DEFAULT_KEY && PvbSettings.load(p).vbAlgo == PvbModels.P1)
    }

    // 5. Old level list -> slider, clamped into 0..12 (whole dB); no old level -> the new default 6.
    val levels = mapOf<Any?, Float>(
        "-6" to 0f, "-3" to 0f, "0" to 0f, "3" to 3f, "6" to 6f, "9" to 9f, "15" to 12f, "12" to 12f,
        "7.4" to 7f, "garbage" to 6f, "NaN" to 6f, 9f to 9f, -3 to 0f, null to 6f)
    for ((old, want) in levels) {
        val init = preserved + mapOf(key to "alpha2_d2", schema to 2) + (if (old == null) emptyMap() else mapOf(legacyLevel to old))
        val p = migrated(init)
        check(p.values[strength] == want) { "level $old -> ${p.values[strength]}, want $want" }
        check(PvbSettings.load(p).vbLevelDb == want)
        if (old != null) check(p.values[legacyLevel] == old)   // the old value itself stays for the record
    }
    // An existing slider value wins over the old list; a damaged one is repaired.
    check(PvbSettings.load(migrated(mapOf(key to "alpha2_p1", schema to 3, strength to 11f, legacyLevel to "-6"))).vbLevelDb == 11f)
    check(migrated(mapOf(key to "alpha2_p1", schema to 3, strength to 20f)).values[strength] == 12f)
    check(migrated(mapOf(key to "alpha2_p1", schema to 3, strength to 4.6f)).values[strength] == 5f)
    check(migrated(mapOf(key to "alpha2_p1", schema to 3, strength to "5", legacyLevel to "9")).values[strength] == 9f)
    check(migrated(mapOf(key to "alpha2_p1", schema to 3, strength to Float.NaN)).values[strength] == 6f)
    // load() alone also clamps (e.g. a value typed into the input dialog before a migration ran).
    check(PvbSettings.load(Prefs(mapOf(strength to 13f))).vbLevelDb == 12f)
    check(PvbSettings.load(Prefs(mapOf(strength to -2f))).vbLevelDb == 0f)
    check(PvbSettings.load(Prefs(mapOf(strength to "x"))).vbLevelDb == 6f)
    check(PvbSettings.clampLevel(Float.POSITIVE_INFINITY) == 6f)

    // 6. Presets: exact model + level, everything else is 사용자 지정.
    check(PvbModels.presets.map { it.key to (it.modelKey to it.levelDb) } == listOf(
        PvbModels.PRESET_FULLNESS to ("alpha2_p1" to 6f), PvbModels.PRESET_DEEP to ("alpha3_gentle12" to 9f)))
    check(PvbModels.presetFor("alpha2_p1", 6f)?.key == PvbModels.PRESET_FULLNESS)
    check(PvbModels.presetFor("alpha3_gentle12", 9f)?.key == PvbModels.PRESET_DEEP)
    check(PvbModels.presetFor(null, 6f)?.key == PvbModels.PRESET_FULLNESS)   // missing key reads as the default
    for ((m, l) in listOf("alpha2_p1" to 7f, "alpha2_p1" to 9f, "alpha3_gentle12" to 6f, "alpha2_reference" to 6f, "alpha2_d2" to 9f))
        check(PvbModels.presetFor(m, l) == null) { "$m/$l must be custom" }
    // Applying a preset is exactly the two writes the fragment makes; nothing else changes.
    for (preset in PvbModels.presets) {
        val p = migrated(preserved + mapOf(key to "alpha2_osc", schema to 3, strength to 2f))
        val before = p.values.toMap()
        p.edit().putString(key, preset.modelKey).putFloat(strength, preset.levelDb).apply()
        check(p.values.keys == before.keys && p.values.filterKeys { it != key && it != strength } == before.filterKeys { it != key && it != strength })
        val s = PvbSettings.load(p)
        check(PvbModels.presetFor(PvbModels.fromId(s.vbAlgo)?.key, s.vbLevelDb) == preset)
    }

    // 7. New install: virtual bass off, P1, +6 dB = 풍성함 증가.
    val fresh = migrated(emptyMap())
    val f = PvbSettings.load(fresh)
    check(!f.vbOn && f.vbAlgo == PvbModels.P1 && f.vbLevelDb == 6f)
    check(fresh.values[key] == PvbModels.P1_KEY && fresh.values[strength] == 6f && fresh.values[schema] == 3)
    check(fresh.values[PvbSettings.KEY_VB_ALPHA2_MODEL] == null && fresh.values[PvbSettings.KEY_VB_LEGACY_MODEL] == null)
    check(PvbModels.presetFor(PvbModels.fromId(f.vbAlgo)?.key, f.vbLevelDb)?.key == PvbModels.PRESET_FULLNESS)
    check(PvbSettings() == f.copy(vbOn = false))   // data class defaults = loaded defaults
    println("Alpha3 settings: catalogue (10 models, P1 default), reference->P1 once, other models kept, alpha1/corrupt, " +
        "level clamp 0..12 (-3->0, 9->9, 15->12), presets and fresh install passed")
}

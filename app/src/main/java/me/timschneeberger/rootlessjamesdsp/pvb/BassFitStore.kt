package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.SharedPreferences

/** Save the fitted values and their one-step undo together in the settings file. */
object BassFitStore {
    const val RECORD = "bass_fit_record"
    const val FLOOR = "bass_fit_floor_hz"
    private const val UNDO = "bass_fit_changed_keys"
    private const val BEFORE = "bass_fit_original_"

    private const val LEGACY_REPLACED = "bass_fit_legacy_replaced"
    private const val KEY_FIT_BEFORE = "bass_fit_before"
    private const val KEY_FIT_BEFORE_LEVEL = "fit_before_fixed_level"

    private fun hasLegacyUndo(prefs: SharedPreferences, flags: SharedPreferences) =
        !prefs.contains(LEGACY_REPLACED) && flags.contains(KEY_FIT_BEFORE)

    fun canRestore(prefs: SharedPreferences, flags: SharedPreferences) =
        prefs.contains(UNDO) || hasLegacyUndo(prefs, flags)

    fun changes(settings: PvbSettings, result: FitResult): Map<String, Any> {
        val current = DevParams.read(settings)
        val proposed = result.applyTo(current)
        val changes = mutableMapOf<String, Any>()
        DevParams.ALL.forEachIndexed { index, spec ->
            if (current[index] != proposed[index]) {
                changes[spec.key] = proposed[index]
                if (spec !== DevParams.HP && !settings.devOn) changes[DevParams.KEY_DEV_ON] = true
            }
        }
        result.strengthDb?.toFloat()?.takeIf { it != settings.fixedLevelDb }?.let {
            changes[PvbSettings.KEY_FIXED_LEVEL_DB] = it
        }
        return changes
    }

    fun preview(settings: PvbSettings, changes: Map<String, Any>): PvbSettings =
        DevParams.applyChanges(settings, changes).copy(
            devOn = changes[DevParams.KEY_DEV_ON] as? Boolean ?: settings.devOn,
            fixedLevelDb = changes[PvbSettings.KEY_FIXED_LEVEL_DB] as? Float ?: settings.fixedLevelDb,
        )

    fun save(prefs: SharedPreferences, flags: SharedPreferences, fit: Map<String, Any>, record: String, floor: Float?) {
        val changes = fit.toMutableMap()
        changes[RECORD] = record
        floor?.let { changes[FLOOR] = it }
        val old = prefs.all.toMutableMap()
        val editor = prefs.edit()
        if (!prefs.contains(LEGACY_REPLACED) && (flags.contains(KEY_FIT_BEFORE) || flags.contains(RECORD) || flags.contains(FLOOR))) {
            // Import the visible result before taking the undo snapshot, in the same editor as the new fit.
            for (key in listOf(RECORD, FLOOR)) {
                if (key !in old) flags.all[key]?.let { old[key] = it; editor.putOriginal(key, it) }
            }
            editor.putBoolean(LEGACY_REPLACED, true)
        }
        prefs.getStringSet(UNDO, emptySet()).orEmpty().forEach { editor.remove(BEFORE + it) }
        val changed = changes.filter { (key, value) -> old[key] != value }
        changed.forEach { (key, value) ->
            editor.putOriginal(BEFORE + key, old[key])
            editor.putOriginal(key, value)
        }
        editor.putStringSet(UNDO, changed.keys.toSet()).apply()
    }

    fun restore(prefs: SharedPreferences, flags: SharedPreferences) {
        val keys = prefs.getStringSet(UNDO, null)
        if (keys == null) {
            if (hasLegacyUndo(prefs, flags)) restoreLegacyBefore(prefs, flags)
            return
        }
        val old = prefs.all
        val editor = prefs.edit()
        keys.forEach { key ->
            editor.putOriginal(key, old[BEFORE + key])
            editor.remove(BEFORE + key)
        }
        editor.remove(UNDO).apply()
    }

    // Older builds stored a list of values without the original key-presence information.
    private fun restoreLegacyBefore(prefs: SharedPreferences, flags: SharedPreferences) {
        val raw = flags.getString(KEY_FIT_BEFORE, null) ?: return
        val v = raw.split(",").map { it.trim().toFloatOrNull() }
        val e = prefs.edit()
        if (flags.contains(KEY_FIT_BEFORE_LEVEL)) e.putFloat(PvbSettings.KEY_FIXED_LEVEL_DB, flags.getFloat(KEY_FIT_BEFORE_LEVEL, 0f))
        DevParams.ALL.forEachIndexed { index, spec ->
            v.getOrNull(index)?.takeIf { it.isFinite() }?.let { original ->
                if (spec.isSwitch) e.putBoolean(spec.key, original >= 0.5f) else e.putFloat(spec.key, original)
            }
        }
        e.apply()
        flags.edit().remove(KEY_FIT_BEFORE_LEVEL).remove(KEY_FIT_BEFORE).remove(RECORD).remove(FLOOR).apply()
    }

    private fun SharedPreferences.Editor.putOriginal(key: String, value: Any?) {
        when (value) {
            null -> remove(key)
            is Float -> putFloat(key, value)
            is Boolean -> putBoolean(key, value)
            is String -> putString(key, value)
            is Int -> putInt(key, value)
            is Long -> putLong(key, value)
            is Set<*> -> putStringSet(key, value.map { it as String }.toSet())
            else -> error("Unsupported preference type")
        }
    }
}

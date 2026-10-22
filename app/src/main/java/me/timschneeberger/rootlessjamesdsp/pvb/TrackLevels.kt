package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.annotation.MainThread
import androidx.core.app.NotificationManagerCompat
import me.timschneeberger.rootlessjamesdsp.service.NotificationListenerService
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Alpha 3.1 "곡별 세기 기억": the process-wide owner of the per-song level memory.
 *
 * The engine keeps reading the normal virtual bass settings (slider [PvbSettings.KEY_VB_STRENGTH_DB] and model
 * [PvbSettings.KEY_VB_ALGO]); recalling a song writes those two keys exactly like the slider and the mode control
 * do, so PvbController pushes it with its usual edit ramp. The global default and the remembered songs live in a
 * separate file ([PREFS_NAME]) so that saving them never reloads the engine settings.
 *
 * Main thread only (shared-preference listeners, media controller callbacks and the UI all run there).
 */
object TrackLevels {
    const val PREFS_NAME = "pvb_track_levels"
    private const val KEY_ENTRIES = "entries"
    private const val KEY_DEFAULT_DB = "default_db"
    private const val KEY_DEFAULT_MODEL = "default_model"
    private const val KEY_OVERRIDE = "override_active"

    /** What the settings screen shows next to the slider. */
    data class Indicator(
        val enabled: Boolean,
        val access: Boolean,
        val watching: Boolean,
        val track: TrackInfo?,
        val usingSaved: Boolean,
        val levelDb: Float,
        val defaultDb: Float,
    )

    private var app: Context? = null
    private lateinit var pvb: SharedPreferences
    private lateinit var own: SharedPreferences
    private lateinit var policy: TrackLevelPolicy
    private var savedRevision = -1L
    private val listeners = CopyOnWriteArrayList<() -> Unit>()

    /** Set by the running [TrackLevelWatcher]: re-read the players (e.g. after the switch was turned on). */
    internal var watcherRefresh: (() -> Unit)? = null
    private var watching = false

    // Held by this object for the process lifetime (SharedPreferences keeps listeners weakly).
    private val pvbListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        when (key) {
            PvbSettings.KEY_VB_STRENGTH_DB, PvbSettings.KEY_VB_ALGO -> settingsChanged()
            PvbSettings.KEY_VB_TRACK_MEMORY -> toggled()
            null -> { toggled(); settingsChanged() }   // whole file cleared (API 30+)
        }
    }

    @MainThread
    fun get(context: Context): TrackLevels {
        if (app == null) load(context.applicationContext)
        return this
    }

    private fun load(ctx: Context) {
        app = ctx
        pvb = ctx.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        own = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        PvbSettings.migrateVirtualBassModel(pvb)
        val current = observed()
        val storedDefault = try {
            val db = own.getFloat(KEY_DEFAULT_DB, Float.NaN)
            if (db.isFinite()) VbLevel.of(db, own.getString(KEY_DEFAULT_MODEL, null)) else null
        } catch (_: ClassCastException) { null }
        val override = try { own.getBoolean(KEY_OVERRIDE, false) } catch (_: ClassCastException) { false }
        val entries = try { own.getString(KEY_ENTRIES, null) } catch (_: ClassCastException) { null }
        policy = TrackLevelPolicy(TrackLevelStore.decode(entries), storedDefault ?: current, memoryOn(), override, current)
        pvb.registerOnSharedPreferenceChangeListener(pvbListener)
        policy.takeStartupRestore()?.let { write(it) }
        persist()
    }

    val enabled: Boolean get() = policy.enabled

    fun entries(): List<TrackLevelEntry> = policy.store.entries()

    fun indicator(context: Context): Indicator = Indicator(
        enabled = policy.enabled,
        access = hasNotificationAccess(context),
        watching = watching,
        track = policy.track,
        usingSaved = policy.usingSaved,
        levelDb = observed().levelDb,
        defaultDb = policy.default.levelDb,
    )

    fun addListener(l: () -> Unit) { listeners += l }
    fun removeListener(l: () -> Unit) { listeners -= l }

    /** The players as the watcher sees them now. Skipped during a blind comparison or a measurement. */
    internal fun onPlayers(players: List<PlayerSnapshot>) {
        if (!policy.enabled || PvbRuntime.abActive || PvbRuntime.measuring) return
        policy.onPlayers(players, now())?.let { write(it) }
        changed()
    }

    internal fun setWatching(value: Boolean) {
        if (watching == value) return
        watching = value
        changed()
    }

    fun remove(key: String) {
        policy.remove(key)?.let { write(it) }
        changed()
    }

    fun clear() {
        policy.clear()?.let { write(it) }
        changed()
    }

    private fun settingsChanged() {
        policy.onSettingsChanged(observed(), now())
        changed()
    }

    private fun toggled() {
        policy.setEnabled(memoryOn(), now())?.let { write(it) }
        changed()
        watcherRefresh?.invoke()
    }

    private fun memoryOn(): Boolean = try {
        pvb.getBoolean(PvbSettings.KEY_VB_TRACK_MEMORY, false)
    } catch (_: ClassCastException) { false }

    private fun observed(): VbLevel {
        val s = PvbSettings.load(pvb)
        return VbLevel.of(s.vbLevelDb, PvbModels.fromId(s.vbAlgo)?.key)
    }

    /** Exactly what the slider and the mode control write; PvbController picks it up and ramps. */
    private fun write(level: VbLevel) {
        pvb.edit()
            .putFloat(PvbSettings.KEY_VB_STRENGTH_DB, level.levelDb)
            .putString(PvbSettings.KEY_VB_ALGO, level.modelKey)
            .apply()
    }

    private fun changed() {
        if (policy.revision != savedRevision) persist()
        for (l in listeners) l()
    }

    private fun persist() {
        own.edit()
            .putString(KEY_ENTRIES, policy.store.encode())
            .putFloat(KEY_DEFAULT_DB, policy.default.levelDb)
            .putString(KEY_DEFAULT_MODEL, policy.default.modelKey)
            .putBoolean(KEY_OVERRIDE, policy.usingSaved)
            .apply()
        savedRevision = policy.revision
    }

    private fun now() = System.currentTimeMillis()

    fun hasNotificationAccess(context: Context): Boolean = try {
        NotificationManagerCompat.getEnabledListenerPackages(context).contains(context.packageName)
    } catch (_: Exception) { false }

    /** Same screen as 설정 > 문제 해결 > 알림 접근 (SettingsTroubleshootingFragment). */
    fun notificationAccessIntent(context: Context): Intent {
        val serviceClassName = NotificationListenerService::class.java.name
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Intent(Settings.ACTION_NOTIFICATION_LISTENER_DETAIL_SETTINGS)
                .putExtra(Settings.EXTRA_NOTIFICATION_LISTENER_COMPONENT_NAME,
                    ComponentName(context.packageName, serviceClassName).flattenToString())
        } else {
            Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS).apply {
                val value = "${context.packageName}/$serviceClassName"
                putExtra(":settings:show_fragment_args", Bundle().also { it.putString(":settings:fragment_args_key", value) })
                putExtra(":settings:fragment_args_key", value)
            }
        }
    }
}

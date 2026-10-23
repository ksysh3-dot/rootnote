package me.timschneeberger.rootlessjamesdsp.ui

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import me.timschneeberger.rootlessjamesdsp.utils.Constants

/**
 * A SharedPreferences file seen from Compose: reading through [bool]/[string]/[float]/[int] during composition
 * subscribes the caller, so a change from anywhere (this page, the service, a preset load) redraws it. Writes are
 * plain `apply()`s with the same keys and types the legacy Preference screens used (see the inventories in the plan).
 *
 * [dsp]: a JamesDSP namespace (dsp_*). The engine does not watch those files; like the legacy
 * PreferenceGroupFragment, every change in the file sends ACTION_PREFERENCES_UPDATED so the service re-reads them.
 */
class RnPrefsFile(
    val prefs: SharedPreferences,
    private val dsp: Boolean,
    private val context: Context,
    private val name: String? = null,
) {
    internal var version by mutableIntStateOf(0)

    internal val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ ->
        version++
        if (dsp) LocalBroadcastManager.getInstance(context).sendBroadcast(Intent(Constants.ACTION_PREFERENCES_UPDATED))
    }

    fun bool(key: String, default: Boolean): Boolean { version; return prefs.getBoolean(key, default) }
    fun string(key: String, default: String): String { version; return prefs.getString(key, default) ?: default }
    fun float(key: String, default: Float): Float {
        version
        // a few legacy values were stored as other number types or strings; read whatever is there
        return when (val v = prefs.all[key]) {
            is Float -> v
            is Int -> v.toFloat()
            is Long -> v.toFloat()
            is String -> v.toFloatOrNull() ?: default
            else -> default
        }
    }
    fun int(key: String, default: Int): Int { version; return prefs.getInt(key, default) }
    fun contains(key: String): Boolean { version; return prefs.contains(key) }

    /** Reads several values at once ([PvbSettings.load] and the like); the caller is redrawn on any change. */
    fun <T> read(block: (SharedPreferences) -> T): T { version; return block(prefs) }

    /**
     * The file was replaced on disk (a preset load, the revert, a profile switch): JamesDSP files are re-read
     * (MODE_MULTI_PROCESS reloads when the file changed) and every reader is redrawn. Reloading does not call the
     * change listeners, so this is the only signal.
     */
    @Suppress("DEPRECATION")
    fun reload() {
        if (dsp && name != null) context.getSharedPreferences(name, Context.MODE_MULTI_PROCESS)
        version++
    }

    fun put(key: String, value: Boolean) = prefs.edit().putBoolean(key, value).apply()
    fun put(key: String, value: String) = prefs.edit().putString(key, value).apply()
    fun put(key: String, value: Float) = prefs.edit().putFloat(key, value).apply()
    fun put(key: String, value: Int) = prefs.edit().putInt(key, value).apply()
    fun remove(key: String) = prefs.edit().remove(key).apply()
}

/**
 * The SharedPreferences file [name], observed while the caller is in the composition. JamesDSP files are opened with
 * MODE_MULTI_PROCESS, as the legacy screens and the engine's PreferenceCache do.
 */
@Suppress("DEPRECATION")
@Composable
fun rememberPrefsFile(name: String, dsp: Boolean = name.startsWith("dsp_")): RnPrefsFile {
    val context = LocalContext.current.applicationContext
    val file = remember(name) {
        RnPrefsFile(context.getSharedPreferences(name, if (dsp) Context.MODE_MULTI_PROCESS else Context.MODE_PRIVATE), dsp, context, name)
    }
    DisposableEffect(file) {
        // SharedPreferences keeps listeners weakly: the file object holds it strongly for as long as it is registered
        file.prefs.registerOnSharedPreferenceChangeListener(file.listener)
        onDispose { file.prefs.unregisterOnSharedPreferenceChangeListener(file.listener) }
    }
    return file
}

/** The app settings file ("application", Preferences.App). */
@Composable
fun rememberAppPrefs(): RnPrefsFile = rememberPrefsFile(Constants.PREF_APP, dsp = false)

/** Sends ACTION_PREFERENCES_UPDATED (the service re-reads every JamesDSP namespace). */
fun notifyDspChanged(context: Context) =
    LocalBroadcastManager.getInstance(context).sendBroadcast(Intent(Constants.ACTION_PREFERENCES_UPDATED))

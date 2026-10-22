package me.timschneeberger.rootlessjamesdsp.pvb

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.getSystemService
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import timber.log.Timber

/**
 * Android side of [FirstWeek] / [KillWatch] (general build): the kill flags in pvb_flags (excluded from backup, so a
 * restore never brings a stale flag), and the battery-optimisation helpers of the battery step. In the s26u build
 * every write is a no-op and nothing here is shown.
 */
object FirstWeekStore {
    private const val KEY_RUNNING = "kill_running"
    private const val KEY_KILLED = "kill_detected"
    private const val KEY_BOOT = "kill_boot"
    private const val KEY_VERSION = "kill_version"

    private val enabled: Boolean get() = BuildConfig.GENERAL_BUILD

    fun bootCount(context: Context): Int = try {
        Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
    } catch (e: Exception) {
        -1
    }

    private val version: Long get() = BuildConfig.VERSION_CODE.toLong()

    fun read(context: Context): KillWatch.Flags {
        val p = PvbGeneral.flags(context)
        return KillWatch.Flags(
            running = p.getBoolean(KEY_RUNNING, false),
            killed = p.getBoolean(KEY_KILLED, false),
            boot = p.getInt(KEY_BOOT, -1),
            version = p.getLong(KEY_VERSION, -1L),
        )
    }

    @SuppressLint("ApplySharedPref")
    private fun write(context: Context, f: KillWatch.Flags) {
        // commit: the service may be killed right after these calls
        PvbGeneral.flags(context).edit()
            .putBoolean(KEY_RUNNING, f.running)
            .putBoolean(KEY_KILLED, f.killed)
            .putInt(KEY_BOOT, f.boot)
            .putLong(KEY_VERSION, f.version)
            .commit()
    }

    private inline fun update(context: Context, change: (KillWatch.Flags) -> KillWatch.Flags) {
        if (!enabled) return
        try {
            val before = read(context)
            val after = change(before)
            if (after != before) write(context, after)
        } catch (e: Exception) {
            Timber.e(e)
        }
    }

    // ------------------------------------------------------------------------------------------- service hooks

    fun onServiceCreated(context: Context) = update(context) {
        KillWatch.serviceCreated(it, bootCount(context), version).also { f ->
            if (f.killed && !it.killed) Timber.w("Previous capture service ended without stopping (killed)")
        }
    }

    fun onCaptureStarted(context: Context) = update(context) { KillWatch.captureStarted(bootCount(context), version) }

    fun onServiceDestroyed(context: Context) = update(context) { KillWatch.serviceDestroyed(it) }

    fun onUserStopped(context: Context) = update(context) { KillWatch.userStopped(it) }

    // ------------------------------------------------------------------------------------------- home screen

    /** Folds a dead service into the flags and returns them. */
    fun check(context: Context, serviceRunning: Boolean): KillWatch.Flags {
        update(context) { KillWatch.check(it, serviceRunning, bootCount(context), version) }
        return read(context)
    }

    fun onUserTurnedOff(context: Context) = update(context) { KillWatch.userTurnedOff(it) }

    fun onBannerDismissed(context: Context) = update(context) { KillWatch.dismissed(it) }

    // ------------------------------------------------------------------------------------------- battery step

    fun isIgnoringBatteryOptimizations(context: Context): Boolean = try {
        context.getSystemService<PowerManager>()?.isIgnoringBatteryOptimizations(context.packageName) ?: false
    } catch (e: Exception) {
        false
    }

    /** The system dialog "allow the app to always run in the background?" (needs REQUEST_IGNORE_BATTERY_OPTIMIZATIONS). */
    @SuppressLint("BatteryLife")
    fun requestIgnoreBatteryOptimizations(context: Context) {
        if (isIgnoringBatteryOptimizations(context)) return
        val request = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}"))
        if (!tryStart(context, request) && !tryStart(context, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)))
            Toast.makeText(context, R.string.no_activity_found, Toast.LENGTH_SHORT).show()
    }

    /** This app's App info page (battery is one tap from there on One UI), else the optimisation list, else Settings. */
    fun openAppBatterySettings(context: Context) {
        val details = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
        if (tryStart(context, details)) return
        if (tryStart(context, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))) return
        if (tryStart(context, Intent(Settings.ACTION_SETTINGS))) return
        Toast.makeText(context, R.string.no_activity_found, Toast.LENGTH_SHORT).show()
    }

    private fun tryStart(context: Context, intent: Intent): Boolean = try {
        if (context !is android.app.Activity) intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        true
    } catch (e: ActivityNotFoundException) {
        false
    } catch (e: SecurityException) {
        Timber.e(e)
        false
    }
}

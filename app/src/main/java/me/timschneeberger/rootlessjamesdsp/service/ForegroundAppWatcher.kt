package me.timschneeberger.rootlessjamesdsp.service

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import timber.log.Timber

/**
 * Polls the usage events once a second (main thread) and reports the main window's package ([ForegroundTracker])
 * whenever it or the screen state ([interactive]) changes.
 * Needs usage access (GET_USAGE_STATS app op); without it [main] stays null and nothing pauses.
 */
class ForegroundAppWatcher(private val context: Context, private val onChange: (main: String?) -> Unit) {
    private val handler = Handler(Looper.getMainLooper())
    private val usm = context.getSystemService(UsageStatsManager::class.java)
    private val power = context.getSystemService(PowerManager::class.java)
    private val tracker = ForegroundTracker()
    private var since = 0L
    private var running = false
    private var lastInteractive = true
    var main: String? = null
        private set

    val interactive: Boolean get() = power?.isInteractive ?: true

    fun start() {
        if (running) return
        running = true
        tracker.clear()
        since = System.currentTimeMillis() - INITIAL_LOOKBACK_MS
        handler.post(poll)
    }

    fun stop() {
        running = false
        handler.removeCallbacks(poll)
        tracker.clear()
        if (main != null) { main = null; onChange(null) }
    }

    private val poll = object : Runnable {
        override fun run() {
            if (!running) return
            read()
            handler.postDelayed(this, POLL_MS)
        }
    }

    private fun read() {
        val m = usm ?: return
        val now = System.currentTimeMillis()
        try {
            val events = m.queryEvents(since, now)
            val e = UsageEvents.Event()
            while (events.hasNextEvent()) {
                events.getNextEvent(e)
                val pkg = e.packageName ?: continue
                when (e.eventType) {
                    UsageEvents.Event.ACTIVITY_RESUMED -> tracker.onResumed(pkg)
                    UsageEvents.Event.ACTIVITY_PAUSED, UsageEvents.Event.ACTIVITY_STOPPED -> tracker.onPaused(pkg)
                }
            }
            since = now
        } catch (ex: Exception) {
            Timber.w(ex, "usage events")
        }
        val next = tracker.main
        val inter = interactive
        if (next != main || inter != lastInteractive) {
            main = next
            lastInteractive = inter
            onChange(next)
        }
    }

    companion object {
        private const val POLL_MS = 1000L
        private const val INITIAL_LOOKBACK_MS = 60 * 60 * 1000L

        /** Usage access granted (Settings > usage access, or `appops set <pkg> GET_USAGE_STATS allow`). */
        fun hasAccess(context: Context): Boolean {
            val ops = context.getSystemService(AppOpsManager::class.java) ?: return false
            val mode = if (Build.VERSION.SDK_INT >= 29)
                ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
            else @Suppress("DEPRECATION")
                ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName)
            return mode == AppOpsManager.MODE_ALLOWED
        }
    }
}

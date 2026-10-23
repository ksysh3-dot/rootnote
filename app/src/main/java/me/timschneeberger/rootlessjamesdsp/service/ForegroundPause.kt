package me.timschneeberger.rootlessjamesdsp.service

/**
 * "제외한 앱을 쓰는 동안 완전히 멈추기": while an excluded app is the main window, the service stops processing and
 * capturing altogether (the muted source sessions are released, so every app plays its own sound as without
 * Rootnote). Reason: playback capture takes an app's audio before its own player volume, so a video an app mutes
 * in-app (Instagram, YouTube, community apps) would be heard through Rootnote.
 *
 * The main window is the app whose activity was resumed most recently and is still resumed: a YouTube picture-in-
 * picture or a floating window behind another app is not the main window (the music player keeps being processed;
 * the excluded app's own sound is not captured anyway). With two apps side by side, the one opened last counts.
 * Usage events do not say which window has focus, so that last rule is the best available guess.
 *
 * Pure Kotlin (host-tested in tools/pvb-harness/jvm/ForegroundPauseTest.kt); [ForegroundAppWatcher] feeds it.
 */
class ForegroundTracker {
    private val resumed = LinkedHashMap<String, Long>()   // package -> order of its last resume
    private var counter = 0L

    /** An activity of [pkg] was resumed (UsageEvents ACTIVITY_RESUMED). */
    fun onResumed(pkg: String) {
        resumed.remove(pkg)
        resumed[pkg] = ++counter
    }

    /** An activity of [pkg] was paused or stopped (ACTIVITY_PAUSED; entering picture-in-picture pauses it too). */
    fun onPaused(pkg: String) {
        resumed.remove(pkg)
    }

    fun clear() = resumed.clear()

    /** The main window's package, or null when nothing is known to be in front. */
    val main: String?
        get() = resumed.maxByOrNull { it.value }?.key
}

object ForegroundPause {
    /**
     * Whether the service should be fully paused now. Never while the screen is off (music then keeps being
     * processed), never during a blind comparison, measurement, calibration or buzz diagnostics.
     */
    fun shouldPause(
        enabled: Boolean,
        mainPackage: String?,
        excludedPackages: Set<String>,
        interactive: Boolean,
        research: Boolean,
    ): Boolean = enabled && interactive && !research && mainPackage != null && mainPackage in excludedPackages
}

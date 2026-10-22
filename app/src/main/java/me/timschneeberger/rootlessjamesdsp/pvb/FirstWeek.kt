package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * First-week helpers of the general build, as plain Kotlin (no Android types) so the host tests check the same
 * decisions the app makes: which onboarding pages a new user sees, the battery step, unexpected-kill detection and
 * the quick-add list of the app exclusion screen. The Android side is [FirstWeekStore] (flags) and the screens.
 */
object FirstWeek {
    /** Onboarding pages (the numbers of OnboardingFragment). */
    enum class Page { WELCOME, LIMITATIONS, METHOD_SELECT, ADB_SETUP, RUNTIME_PERMISSIONS, BATTERY, READY }

    /**
     * Pages the general build leaves out on every first run: the first-run notice already greeted the user and
     * carries the limitations (capture-blocking apps, delay, other effect apps), and the home screen opens straight
     * after the last setup step instead of a "setup complete" page. The battery page exists only in the general
     * build. The s26u build keeps the upstream flow (no battery page).
     */
    fun skippedAlways(general: Boolean): Set<Page> =
        if (general) setOf(Page.WELCOME, Page.LIMITATIONS, Page.READY) else setOf(Page.BATTERY)

    /** The battery step is shown when the app is not yet exempt from battery optimisation (general build only). */
    fun batteryStepNeeded(general: Boolean, ignoringBatteryOptimizations: Boolean): Boolean =
        general && !ignoringBatteryOptimizations
}

/**
 * Unexpected-kill detection (general build). The service records that capture started; a normal stop (the service's
 * onDestroy, a stop from the notification, the tile or the advanced screen) clears it. If the flag is still set while
 * no service runs, the process died without stopping: on Samsung One UI that is almost always the battery manager
 * ("절전 앱", "백그라운드 사용 제한"). A reboot or an app update also ends the process without a stop; the boot count
 * and the app version stored with the flag keep those from counting as a kill.
 */
object KillWatch {
    data class Flags(
        /** Capture started and no normal stop since. */
        val running: Boolean = false,
        /** A kill was detected and not yet dismissed or recovered from. */
        val killed: Boolean = false,
        /** Settings.Global.BOOT_COUNT when [running] was set (-1 unknown). */
        val boot: Int = -1,
        /** App version code when [running] was set. */
        val version: Long = -1L,
    )

    /** Same boot and same app version: the flag belongs to a process of this boot and this install. */
    private fun sameLife(f: Flags, boot: Int, version: Long): Boolean = f.boot == boot && f.version == version

    /** The service captured audio. A recovery clears an earlier kill. */
    fun captureStarted(boot: Int, version: Long): Flags = Flags(running = true, killed = false, boot = boot, version = version)

    /**
     * A service instance is created. If the previous instance never stopped (flag still set, same boot and version),
     * the process was killed; Android may be restarting the service right now with the old capture token, which
     * fails on Android 14+, so the kill is recorded here before that stop clears [Flags.running].
     */
    fun serviceCreated(f: Flags, boot: Int, version: Long): Flags =
        if (f.running && sameLife(f, boot, version)) f.copy(running = false, killed = true) else f.copy(running = false)

    /** onDestroy of the service: every planned stop ends here. */
    fun serviceDestroyed(f: Flags): Flags = f.copy(running = false)

    /** The user stopped processing (notification, tile, advanced screen, home switch): nothing to report. */
    fun userStopped(f: Flags): Flags = f.copy(running = false, killed = false)

    /** The user turned processing off but the service keeps running (home switch): only the report is cleared. */
    fun userTurnedOff(f: Flags): Flags = f.copy(killed = false)

    /** The banner was dismissed. */
    fun dismissed(f: Flags): Flags = f.copy(killed = false)

    /** The app opened (or came to the front): fold a dead service into [Flags.killed]. */
    fun check(f: Flags, serviceRunning: Boolean, boot: Int, version: Long): Flags = when {
        !f.running || serviceRunning -> f
        sameLife(f, boot, version) -> f.copy(running = false, killed = true)
        else -> f.copy(running = false)  // reboot or app update: not a kill
    }

    /** The home banner: a kill, no service now, and the user still wants processing on. */
    fun showBanner(general: Boolean, f: Flags, serviceRunning: Boolean, processingWanted: Boolean): Boolean =
        general && f.killed && !serviceRunning && processingWanted
}

/**
 * Quick-add list of the app exclusion screen (general build): common video, live-streaming and call apps, where the
 * processing delay (about 0.15 s of virtual bass plus capture buffering) breaks lip sync or conversation. Only apps
 * that are installed and not yet excluded are offered, unchecked; the user chooses.
 *
 * Package names were checked against their store listings (2026-10). Each must also be listed in the general
 * manifest's <queries>, so the app may see whether it is installed.
 */
object QuickExclude {
    data class Candidate(val packageName: String, val label: String)

    val APPS: List<Candidate> = listOf(
        Candidate("com.google.android.youtube", "YouTube"),
        Candidate("com.netflix.mediaclient", "Netflix"),
        Candidate("com.disney.disneyplus", "Disney+"),
        Candidate("net.cj.cjhv.gs.tving", "TVING"),
        Candidate("kr.co.captv.pooqV2", "Wavve"),
        Candidate("com.coupang.mobile.play", "Coupang Play"),
        Candidate("tv.twitch.android.app", "Twitch"),
        Candidate("com.navercorp.game.android.community", "CHZZK"),
        Candidate("kr.co.nowcom.mobile.afreeca", "SOOP"),
        Candidate("us.zoom.videomeetings", "Zoom"),
        Candidate("com.google.android.apps.tachyon", "Google Meet"),
        Candidate("com.kakao.talk", "KakaoTalk"),
        Candidate("com.discord", "Discord"),
        Candidate("com.microsoft.teams", "Microsoft Teams"),
    )

    /** Installed apps of [APPS] that are not excluded yet, in list order. */
    fun candidates(installed: Set<String>, excluded: Set<String>): List<Candidate> =
        APPS.filter { it.packageName in installed && it.packageName !in excluded }
}

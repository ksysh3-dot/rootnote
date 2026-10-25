package me.timschneeberger.rootlessjamesdsp.capture

import android.content.Context
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral

/**
 * How other apps' audio is captured. [INTERCEPT] ("가로채기", default in the general build): a shell process started
 * through Shizuku takes the players off the speaker (no consent per start, nothing to mute, nothing leaks). Needs
 * Shizuku running; some games and banking apps refuse to run while it (or USB debugging) is on. [PROJECTION]
 * ("화면 공유 권한"): the MediaProjection capture with per-session muting, no Shizuku needed after setup.
 */
enum class CaptureMode(val key: String) {
    INTERCEPT("intercept"), PROJECTION("projection");

    companion object {
        const val PREF = "capture_mode"

        fun get(context: Context): CaptureMode {
            val v = PvbGeneral.flags(context).getString(PREF, null)
            return values().firstOrNull { it.key == v } ?: if (PvbBuild.general) INTERCEPT else PROJECTION
        }

        fun set(context: Context, mode: CaptureMode) {
            PvbGeneral.flags(context).edit().putString(PREF, mode.key).apply()
        }
    }
}

/** What the running capture really is (the service sets it; screens and the session muting read it). */
object CaptureState {
    /** The capture currently intercepts (so no session may be muted). */
    @Volatile var intercepting = false
    /** "가로채기" was chosen but could not run in this service start; why (InterceptSource.lastError). */
    @Volatile var fallbackReason: String? = null
    /**
     * A start without the screen-share consent failed ("가로채기" could not run after all): the next start asks for the
     * consent. Cleared as soon as "가로채기" runs again (a consent-backed start tries it first).
     */
    @Volatile var interceptStartFailed = false
}

/** How a start begins: without the screen-share consent when "가로채기" is chosen and can run right now. */
object CaptureStart {
    fun withoutConsent(context: Context): Boolean =
        CaptureMode.get(context) == CaptureMode.INTERCEPT && android.os.Build.VERSION.SDK_INT >= 33 &&
            !CaptureState.interceptStartFailed && InterceptSource.shizukuReady()
}

/** [CaptureState.fallbackReason] (InterceptSource.lastError) in the user's words. */
fun captureReasonText(context: Context, reason: String): String = when (reason) {
    "shizuku_off" -> context.getString(me.timschneeberger.rootlessjamesdsp.R.string.capture_reason_shizuku_off)
    "android_13_needed" -> context.getString(me.timschneeberger.rootlessjamesdsp.R.string.capture_reason_android_13)
    // the system's own message, so a report can say what failed
    else -> context.getString(me.timschneeberger.rootlessjamesdsp.R.string.capture_reason_other) +
        " (" + reason.removePrefix("ERROR ").take(160) + ")"
}

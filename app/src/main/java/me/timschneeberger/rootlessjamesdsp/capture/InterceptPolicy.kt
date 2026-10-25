package me.timschneeberger.rootlessjamesdsp.capture

/*
 * The decisions of "가로채기 캡처" that need no phone, kept free of Android classes so a host test can run them
 * (tools/pvb-harness/jvm/InterceptPolicyTest.kt).
 */
object InterceptPolicy {
    /** What a failed intercept start leads to. */
    enum class After { SCREEN_SHARE, ASK_CONSENT }

    /**
     * A start may skip the screen-share consent when intercept is chosen, Android is 13 or later, the last start
     * did not fail without a consent, and Shizuku is ready right now.
     */
    fun startsWithoutConsent(interceptChosen: Boolean, sdk: Int, failedBefore: Boolean, shizukuReady: Boolean): Boolean =
        interceptChosen && sdk >= 33 && !failedBefore && shizukuReady

    /** Intercept could not run: with a consent screen share takes over, without one the app has to ask for it. */
    fun afterFailure(hasProjection: Boolean): After = if (hasProjection) After.SCREEN_SHARE else After.ASK_CONSENT
}

/** The shell process' arguments: sample rate, then the comma-separated UIDs whose sound is never captured. */
object InterceptArgs {
    class Parsed(val rate: Int, val excluded: List<Int>)

    fun build(sampleRate: Int, excludedUids: Collection<Int>): List<String> =
        listOf(sampleRate.toString(), excludedUids.joinToString(","))

    fun parse(args: Array<String>): Parsed = Parsed(
        args.getOrNull(0)?.toIntOrNull() ?: 48000,
        args.getOrNull(1)?.split(',')?.mapNotNull { it.trim().toIntOrNull() }.orEmpty(),
    )
}

/** Why intercept could not run, in the codes the app keeps and the words it shows. */
object InterceptReason {
    enum class Kind { SHIZUKU_OFF, ANDROID_13, OTHER }

    fun kind(reason: String): Kind = when (reason) {
        "shizuku_off" -> Kind.SHIZUKU_OFF
        "android_13_needed" -> Kind.ANDROID_13
        else -> Kind.OTHER
    }

    /** The system's own message for a report: no "ERROR " prefix, at most 160 characters. */
    fun detail(reason: String): String = reason.removePrefix("ERROR ").take(160)

    /** The code stored when the shell process gave no ERROR line itself. */
    fun describe(ended: Boolean, timeoutSec: Int, last: String?): String =
        if (ended) "exited: ${last ?: "no output"}"
        else "timeout $timeoutSec s${last?.let { ": $it" } ?: ""}"
}

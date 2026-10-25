import me.timschneeberger.rootlessjamesdsp.capture.InterceptArgs
import me.timschneeberger.rootlessjamesdsp.capture.InterceptPolicy
import me.timschneeberger.rootlessjamesdsp.capture.InterceptReason
import kotlin.system.exitProcess

// "가로채기" decisions that need no phone: whether a start may skip the screen-share consent, how the server's
// arguments survive the trip to the shell process, and how a failure is told. Expected values are literals written
// from the behaviour agreed with the user (a table), not recomputed with the code's own expressions.

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

fun main() {
    // --- may a start skip the consent? intercept chosen, Android 13+, no earlier failure, Shizuku ready: yes.
    fun go(intercept: Boolean = true, sdk: Int = 36, failedBefore: Boolean = false, shizuku: Boolean = true) =
        InterceptPolicy.startsWithoutConsent(intercept, sdk, failedBefore, shizuku)
    check("intercept + Shizuku ready + Android 16: no consent", go())
    check("Android 13 is enough", go(sdk = 33))
    check("Android 12 needs the consent", !go(sdk = 32))
    check("screen share chosen: consent", !go(intercept = false))
    check("Shizuku not ready: consent", !go(shizuku = false))
    check("intercept failed in the last start: consent", !go(failedBefore = true))
    check("after a failure every other combination still asks", !go(failedBefore = true, sdk = 33, shizuku = true))

    // --- after intercept failed, is there anything to fall back on?
    check("failure with a screen-share consent: fall back to screen share", InterceptPolicy.afterFailure(hasProjection = true) == InterceptPolicy.After.SCREEN_SHARE)
    check("failure without a consent: ask for it", InterceptPolicy.afterFailure(hasProjection = false) == InterceptPolicy.After.ASK_CONSENT)

    // --- the server's arguments: what the app builds is what the shell process reads
    check("args: rate and uids", InterceptArgs.build(48000, listOf(10541, 1000)) == listOf("48000", "10541,1000"))
    check("args: no excluded uids is an empty second argument", InterceptArgs.build(44100, emptyList()) == listOf("44100", ""))
    val p1 = InterceptArgs.parse(arrayOf("48000", "10541,1000"))
    check("parse: rate and uids", p1.rate == 48000 && p1.excluded == listOf(10541, 1000))
    val p2 = InterceptArgs.parse(arrayOf("44100", ""))
    check("parse: empty uid list", p2.rate == 44100 && p2.excluded.isEmpty())
    val p3 = InterceptArgs.parse(arrayOf("48000", " 7 , x, 8 ,,"))
    check("parse: blanks and junk are skipped", p3.excluded == listOf(7, 8))
    val p4 = InterceptArgs.parse(emptyArray())
    check("parse: no arguments means 48000 and nobody excluded", p4.rate == 48000 && p4.excluded.isEmpty())
    val p5 = InterceptArgs.parse(arrayOf("abc"))
    check("parse: a bad rate falls back to 48000", p5.rate == 48000)
    check("round trip", InterceptArgs.parse(InterceptArgs.build(44100, listOf(1, 22, 333)).toTypedArray()).let { it.rate == 44100 && it.excluded == listOf(1, 22, 333) })

    // --- how a failure is told
    check("reason: shizuku_off", InterceptReason.kind("shizuku_off") == InterceptReason.Kind.SHIZUKU_OFF)
    check("reason: android_13_needed", InterceptReason.kind("android_13_needed") == InterceptReason.Kind.ANDROID_13)
    check("reason: server error is OTHER", InterceptReason.kind("ERROR InvocationTargetException: Illegal rule value 32772") == InterceptReason.Kind.OTHER)
    check("detail: the ERROR prefix is cut", InterceptReason.detail("ERROR InvocationTargetException: Illegal rule value 32772") == "InvocationTargetException: Illegal rule value 32772")
    check("detail: long text is cut to 160", InterceptReason.detail("ERROR " + "x".repeat(500)).length == 160)
    check("detail: unknown short code stays", InterceptReason.detail("timeout 8 s") == "timeout 8 s")
    check("describe: process ended with a line", InterceptReason.describe(ended = true, timeoutSec = 8, last = "Exception in thread main") == "exited: Exception in thread main")
    check("describe: process ended silently", InterceptReason.describe(ended = true, timeoutSec = 8, last = null) == "exited: no output")
    check("describe: timeout with the last line", InterceptReason.describe(ended = false, timeoutSec = 8, last = "starting") == "timeout 8 s: starting")
    check("describe: timeout alone", InterceptReason.describe(ended = false, timeoutSec = 8, last = null) == "timeout 8 s")

    if (failed > 0) exitProcess(1)
    println("all intercept policy checks passed")
}

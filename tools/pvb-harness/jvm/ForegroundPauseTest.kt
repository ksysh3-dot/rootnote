import me.timschneeberger.rootlessjamesdsp.service.ForegroundPause
import me.timschneeberger.rootlessjamesdsp.service.ForegroundTracker

// "Pause fully while an excluded app is in front": which app is the main window, and when the service pauses.

private var failures = 0
private fun check(name: String, ok: Boolean) {
    println("[${if (ok) "PASS" else "FAIL"}] $name")
    if (!ok) failures++
}

fun main() {
    val yt = "com.google.android.youtube"; val spotify = "com.spotify.music"; val home = "com.sec.android.app.launcher"
    val excluded = setOf(yt, "com.instagram.android")
    fun pause(main: String?, interactive: Boolean = true, research: Boolean = false, enabled: Boolean = true) =
        ForegroundPause.shouldPause(enabled, main, excluded, interactive, research)

    val t = ForegroundTracker()
    check("nothing known: no main window", t.main == null)
    t.onResumed(spotify); t.onPaused(spotify); t.onResumed(yt)
    check("Spotify playing behind, YouTube in front: main = YouTube, paused", t.main == yt && pause(t.main))
    // YouTube goes to picture-in-picture (paused) and the launcher comes to the front
    t.onPaused(yt); t.onResumed(home)
    check("YouTube in PIP, launcher in front: not paused", t.main == home && !pause(t.main))
    // PIP kept resumed (multi-resume) while another app is opened after it: the app opened last counts
    t.onResumed(yt); t.onResumed(spotify)
    check("both resumed (PIP or split), Spotify opened last: main = Spotify, not paused", t.main == spotify && !pause(t.main))
    t.onResumed(yt)
    check("split screen, YouTube opened last: paused", t.main == yt && pause(t.main))
    t.onPaused(yt)
    check("YouTube leaves: the earlier resumed app is main again", t.main == spotify || t.main == home)
    check("screen off: never paused", !pause(yt, interactive = false))
    check("comparison/measurement running: never paused", !pause(yt, research = true))
    check("option off: never paused", !pause(yt, enabled = false))
    check("not excluded app in front: not paused", !pause(spotify))
    check("unknown main window: not paused", !pause(null))
    t.clear()
    check("clear: no main window", t.main == null)

    println(if (failures == 0) "ForegroundPauseTest: all checks passed" else "ForegroundPauseTest: $failures FAILED")
    if (failures != 0) kotlin.system.exitProcess(1)
}

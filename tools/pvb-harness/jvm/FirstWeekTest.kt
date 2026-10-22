import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeek
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeek.Page
import me.timschneeberger.rootlessjamesdsp.pvb.KillWatch
import me.timschneeberger.rootlessjamesdsp.pvb.KillWatch.Flags
import me.timschneeberger.rootlessjamesdsp.pvb.QuickExclude
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

// General build, first week: onboarding pages, battery step, unexpected-kill detection, quick exclusions (list equal
// to the manifest <queries>), and the en/ko strings of these screens. Argument: the repository root.

private fun expect(ok: Boolean, what: String) {
    if (!ok) throw AssertionError(what)
}

private fun strings(root: File, path: String): Map<String, String> {
    val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(File(root, path))
    val nodes = doc.getElementsByTagName("string")
    return (0 until nodes.length).associate { i ->
        val e = nodes.item(i) as org.w3c.dom.Element
        e.getAttribute("name") to e.textContent
    }
}

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })

    // --- onboarding pages ---
    expect(FirstWeek.skippedAlways(general = true) == setOf(Page.WELCOME, Page.LIMITATIONS, Page.READY),
        "general: welcome, limitations and ready are left out")
    expect(FirstWeek.skippedAlways(general = false) == setOf(Page.BATTERY), "s26u: upstream pages, no battery page")
    expect(FirstWeek.batteryStepNeeded(general = true, ignoringBatteryOptimizations = false), "general, not exempt -> battery step")
    expect(!FirstWeek.batteryStepNeeded(general = true, ignoringBatteryOptimizations = true), "already exempt -> skipped")
    expect(!FirstWeek.batteryStepNeeded(general = false, ignoringBatteryOptimizations = false), "s26u never")

    // --- unexpected-kill detection ---
    val boot = 41
    val ver = 1234L
    val fresh = Flags()
    expect(!KillWatch.showBanner(true, fresh, serviceRunning = false, processingWanted = true), "fresh install: no banner")
    val started = KillWatch.captureStarted(boot, ver)
    expect(started == Flags(running = true, killed = false, boot = boot, version = ver), "capture start sets the flag")
    // running service: nothing changes, no banner
    expect(KillWatch.check(started, serviceRunning = true, boot = boot, version = ver) == started, "service alive")
    // normal stops clear it
    val destroyed = KillWatch.serviceDestroyed(started)
    expect(!destroyed.running && !destroyed.killed, "onDestroy clears running")
    expect(KillWatch.check(destroyed, false, boot, ver) == destroyed, "after a normal stop nothing is detected")
    val userStop = KillWatch.userStopped(started.copy(killed = true))
    expect(!userStop.running && !userStop.killed, "notification/tile/advanced stop clears both")
    // killed process: app opens, no service, same boot and version
    val killed = KillWatch.check(started, serviceRunning = false, boot = boot, version = ver)
    expect(killed.killed && !killed.running, "dead service -> killed ($killed)")
    expect(KillWatch.showBanner(true, killed, serviceRunning = false, processingWanted = true), "banner shown")
    expect(!KillWatch.showBanner(false, killed, false, true), "s26u: never")
    expect(!KillWatch.showBanner(true, killed, serviceRunning = true, processingWanted = true), "service back: hidden")
    expect(!KillWatch.showBanner(true, killed, serviceRunning = false, processingWanted = false), "user turned it off: hidden")
    // reboot / update are not kills
    expect(!KillWatch.check(started, false, boot + 1, ver).killed, "reboot is not a kill")
    expect(!KillWatch.check(started, false, boot, ver + 1).killed, "app update is not a kill")
    expect(!KillWatch.check(started, false, boot + 1, ver).running, "stale flag cleared after reboot")
    // Android restarts the killed service (old token fails on 14+, then onDestroy): the kill survives that stop
    val restarted = KillWatch.serviceCreated(started, boot, ver)
    expect(restarted.killed && !restarted.running, "service re-created after a kill records it")
    val restartFailed = KillWatch.serviceDestroyed(restarted)
    expect(restartFailed.killed, "the failed restart's onDestroy keeps the report")
    expect(KillWatch.showBanner(true, restartFailed, false, true), "banner after a failed restart")
    expect(!KillWatch.serviceCreated(destroyed, boot, ver).killed, "normal create after a normal stop: no kill")
    expect(!KillWatch.serviceCreated(started, boot + 1, ver).killed, "first create after a reboot: no kill")
    // stop intent to a dead service: create (records the kill), then ACTION_STOP clears it
    expect(!KillWatch.userStopped(KillWatch.serviceCreated(started, boot, ver)).killed, "user stop wins")
    // recovery and dismissal
    expect(!KillWatch.captureStarted(boot, ver).killed, "capture again clears the report")
    expect(!KillWatch.dismissed(killed).killed, "dismiss clears the report")
    expect(KillWatch.userTurnedOff(started) == started.copy(killed = false), "home switch off keeps the running flag")

    // --- quick exclusions ---
    val pkgs = QuickExclude.APPS.map { it.packageName }
    expect(pkgs.size == pkgs.toSet().size, "no duplicate packages")
    expect(pkgs.all { Regex("^[a-zA-Z][a-zA-Z0-9_]*(\\.[a-zA-Z][a-zA-Z0-9_]*)+$").matches(it) }, "valid package names")
    val inst = setOf("com.google.android.youtube", "com.kakao.talk", "com.discord", "org.example.game")
    val cand = QuickExclude.candidates(inst, excluded = setOf("com.discord"))
    expect(cand.map { it.packageName } == listOf("com.google.android.youtube", "com.kakao.talk"),
        "installed and not excluded, in list order: $cand")
    expect(QuickExclude.candidates(emptySet(), emptySet()).isEmpty(), "nothing installed")
    // the general manifest may see exactly these packages
    val manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
        .parse(File(root, "app/src/general/AndroidManifest.xml"))
    val queries = manifest.getElementsByTagName("queries")
    expect(queries.length == 1, "one <queries> in the general manifest")
    val listed = (queries.item(0) as org.w3c.dom.Element).getElementsByTagName("package").let { n ->
        (0 until n.length).map { (n.item(it) as org.w3c.dom.Element).getAttribute("android:name") }
    }
    expect(listed.toSet() == pkgs.toSet(), "manifest <queries> = QuickExclude.APPS (manifest-only ${listed - pkgs.toSet()}, " +
        "list-only ${pkgs - listed.toSet()})")
    val perms = manifest.getElementsByTagName("uses-permission").let { n ->
        (0 until n.length).map { (n.item(it) as org.w3c.dom.Element).getAttribute("android:name") }
    }
    expect("android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" in perms, "battery step permission in the general manifest")

    // --- strings: same keys and arguments in English and Korean ---
    val placeholder = Regex("%(\\d+\\$)?[sdf]")
    fun args(t: String) = placeholder.findAll(t).map { it.value }.sorted().toList()
    for ((en, ko) in listOf(
        "app/src/main/res/values/strings_firstweek.xml" to "app/src/main/res/values-ko/strings_firstweek.xml",
        "app/src/general/res/values/strings_overrides.xml" to "app/src/general/res/values-ko-rKR/strings_overrides.xml",
    )) {
        val e = strings(root, en)
        val k = strings(root, ko)
        expect(e.isNotEmpty() && e.keys == k.keys, "$en: same keys (en-only ${e.keys - k.keys}, ko-only ${k.keys - e.keys})")
        for (key in e.keys) expect(args(e[key]!!) == args(k[key]!!), "same format arguments in $key")
        for ((key, text) in e + k.mapKeys { "ko:" + it.key })
            expect(Regex("(?<!\\\\)'").find(text) == null, "bare apostrophe in $key")
    }
    // the region-less Korean copy of the method page matches the ko-KR one
    val koR = strings(root, "app/src/general/res/values-ko-rKR/strings_overrides.xml")
    for ((key, text) in strings(root, "app/src/general/res/values-ko/strings_overrides.xml"))
        expect(koR[key] == text, "values-ko and values-ko-rKR differ in $key")

    // first-run notice (the welcome screen, WelcomeActivity): one consent (virtual bass), the delay line, the
    // per-session capture consent, the labels it points to
    val welEn = strings(root, "app/src/general/res/values/strings_home.xml")
    val welKo = strings(root, "app/src/general/res/values-ko/strings_home.xml")
    expect("0.15 s" in welEn["welcome_know_delay_body"]!! && "0.15초" in welKo["welcome_know_delay_body"]!!, "welcome: 0.15 s delay line")
    expect("Exclude apps" in welEn["welcome_know_delay_body"]!! && "앱별 제외" in welKo["welcome_know_delay_body"]!!,
        "welcome: points to the exclusion row")
    expect(welEn["home_exclude_title"]!!.startsWith("Exclude apps") && welKo["home_exclude_title"]!!.startsWith("앱별 제외"),
        "welcome: the exclusion row is still called that")
    expect(welEn["home_chip_fullness"]!! in welEn["welcome_know_experimental_body"]!! &&
        welKo["home_chip_fullness"]!! in welKo["welcome_know_experimental_body"]!!, "welcome: names the fullness preset")
    expect("Android 14" in welEn["welcome_ready_capture_body_14"]!! && "Android 14" in welKo["welcome_ready_capture_body_14"]!!,
        "welcome: Android 14 capture consent")
    expect(welEn["welcome_start"]!! in welEn["welcome_consent"]!! && welKo["welcome_start"]!! in welKo["welcome_consent"]!!,
        "welcome: the consent line names its button")
    expect("GPL-3.0" in welEn["welcome_ready_legal"]!! && "GPL-3.0" in welKo["welcome_ready_legal"]!!, "welcome: licence line")
    expect("AutoEQ" in welEn["welcome_ready_privacy_body"]!! && "AutoEQ" in welKo["welcome_ready_privacy_body"]!!,
        "welcome: the only network use is named")
    val home = welKo
    expect(home["home_exclude_title"] == "앱별 제외 (영상·게임)", "home exclusion row title")
    expect(home["home_killed_title"]!!.startsWith("시스템이 %1\$s를 종료했습니다"), "kill banner title")

    println("First week: onboarding pages (general skips welcome/limitations/ready, battery step unless exempt), " +
        "kill detection (normal stops, reboot/update, failed restart), quick exclusions = manifest queries, en/ko strings: OK")
}

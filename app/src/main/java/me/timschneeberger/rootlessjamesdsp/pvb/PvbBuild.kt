package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Which build this is, as plain Kotlin flags (no Android, so the host tests can set them).
 *
 * The app sets them once at start from BuildConfig ([PvbGeneral.init]). The defaults are the s26u build, so code and
 * tests that never call init keep the current behaviour.
 *
 * - [general]: the general distribution build (flavor `general`): safe caps, device profiles, first-run gate.
 * - [researchUiBuild]: BuildConfig.RESEARCH_UI. false in general: research tools appear only after the hidden unlock.
 * - [recordFeatures]: BuildConfig.RECORD_FEATURES. false in general: per-song memory, blind comparison records,
 *   buzz diagnostics (recordings, microphone), measurement and anything else that stores titles, audio or records
 *   cannot run at all.
 */
object PvbBuild {
    @Volatile var general: Boolean = false
    @Volatile var researchUiBuild: Boolean = true
    @Volatile var recordFeatures: Boolean = true

    /** Set from the "개발자/연구" unlock (version tapped 7 times). Only matters when [researchUiBuild] is false. */
    @Volatile var researchUnlocked: Boolean = false

    /** First-run notice confirmed (general only; the s26u build has no gate). */
    @Volatile var firstRunConfirmed: Boolean = false

    /** Research tools and codenames are visible. */
    val researchUi: Boolean get() = researchUiBuild || researchUnlocked

    /** The general build's caps, or null (s26u: the full UI ranges). */
    val caps: SafeCaps? get() = if (general) SafeCaps.GENERAL else null

    /** Processing may run: always in s26u; in general only after the first-run notice was confirmed. */
    val processingAllowed: Boolean get() = FirstRun.processingAllowed(general, firstRunConfirmed)

    /** The last step of [PvbSettings.load]: first-run gate, then the caps. */
    fun finish(s: PvbSettings): PvbSettings {
        val gated = if (processingAllowed) s else s.copy(enabled = false, matchOnDisable = false, vbOn = false)
        return caps?.clamp(gated) ?: gated
    }

    /** Restores the s26u defaults (tests). */
    fun reset() {
        general = false; researchUiBuild = true; recordFeatures = true; researchUnlocked = false; firstRunConfirmed = false
    }
}

/**
 * Upper/lower bounds of the general build (release audit S3). Applied when settings are read, so a value written
 * by an older build, a restored backup or a recalled preset can never exceed them, and used as the slider ranges.
 */
data class SafeCaps(
    val outDbMax: Float,
    val ceilDbMax: Float,
    val lowDbMax: Float,
    val lowQMax: Float,
    val hpHzMin: Float,
    val releaseMsMin: Float,
    val vbLevelMax: Float,
) {
    fun clamp(s: PvbSettings): PvbSettings = s.copy(
        outDb = s.outDb.coerceAtMost(outDbMax),
        ceilDb = s.ceilDb.coerceAtMost(ceilDbMax),
        lowDb = s.lowDb.coerceAtMost(lowDbMax),
        lowQ = s.lowQ.coerceAtMost(lowQMax),
        hpHz = s.hpHz.coerceAtLeast(hpHzMin),
        releaseMs = s.releaseMs.coerceAtLeast(releaseMsMin),
        vbLevelDb = s.vbLevelDb.coerceIn(PvbSettings.VB_LEVEL_MIN, vbLevelMax),
    )

    companion object {
        val GENERAL = SafeCaps(
            outDbMax = -3f,
            ceilDbMax = -1f,
            lowDbMax = 6f,
            lowQMax = 2f,
            hpHzMin = 80f,
            releaseMsMin = 30f,
            vbLevelMax = 9f,
        )
    }
}

/** First-run gate of the general build (pure logic; the notice itself is PvbGeneral.showFirstRunNotice). */
object FirstRun {
    const val KEY_CONFIRMED = "first_run_confirmed"

    fun processingAllowed(general: Boolean, confirmed: Boolean): Boolean = !general || confirmed

    /** The notice is shown on launch and instead of starting the service until it was confirmed. */
    fun mustShowNotice(general: Boolean, confirmed: Boolean): Boolean = general && !confirmed

    /** What confirming writes into the PVB settings: processing on, with the device profile already applied. */
    fun valuesOnConfirm(): Map<String, Any> = mapOf(PvbSettings.KEY_ENABLE to true)

    /** Shell commands granting the capture permissions to [applicationId] (ADB setup, shown in the notice). */
    fun adbCommands(applicationId: String): List<String> = listOf(
        "adb shell pm grant $applicationId android.permission.DUMP",
        "adb shell appops set $applicationId PROJECT_MEDIA allow",
        "adb shell appops set $applicationId SYSTEM_ALERT_WINDOW allow",
    )
}

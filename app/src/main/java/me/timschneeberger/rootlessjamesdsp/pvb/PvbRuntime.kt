package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Process-wide state shared by the audio service, the controller and the screens (they all live in the app process,
 * so a singleton is enough). Each value is a separate @Volatile: a reader sees each one up to date, never several
 * changed together as one step. Who owns what (code review refactor R2, 2026-10-23):
 *
 * | state | written by | cleared by | read by |
 * |---|---|---|---|
 * | [status] | PvbController.publish (main thread) | - | screens (main), via [addStatusListener] |
 * | [engine] | PvbController.start / stop (main) | PvbController.stop, only if still its own | status text, analyzer, research screens |
 * | blind comparison ([setAb], [abReturnVolume]) | LiveAbView (s26u, main) | LiveAbView.end / [endAb]; the controller ends the volume wait | controller, service route, status |
 * | [measuring] | PvbMeasure.run (its worker thread) | the same run's finally | controller (holds XTC off, matcher hold), service route |
 * | [calibrating] | SpatialBalanceActivity.previewBalance (main) | SpatialBalanceActivity.clearOverride (every exit) | service route (audio thread) |
 * | [devOverride] | DevModeActivity, SpatialStoryActivity, SpatialBalanceActivity (main) | the same screen when it stops | controller (effective settings) |
 * | [devMeter] | DevModeActivity (main) | DevModeActivity.onStop | controller (P_DEV_METER) |
 *
 * Listeners run on the thread that made the change ([measuring] is set on a worker thread); the controller's
 * listeners post to the main thread before touching anything. [devOverride] has no owner token: the last screen to
 * set or clear it wins. Only one of those screens is visible at a time and each clears it when it stops, so this
 * holds today; a second simultaneous user would need an owner check (a behaviour change, not part of R2).
 */
object PvbRuntime {
    data class Status(
        val enabled: Boolean = false,
        val processing: Boolean = false,      // our engine is in the signal path and not bypassed
        val matchedBypass: Boolean = false,
        val usingPvb: Boolean = false,
        val speaker: Boolean = true,
        val routeName: String = "",
        val routeKnown: Boolean = false,
        val volumeIndex: Int = 0,
        val volumeMax: Int = 0,
        val volumeDb: Float = Float.NaN,
        val referenceDb: Float = Float.NaN,
        val dropDb: Float = 0f,
        val volumeDbSource: String = "",
        val volumeSysDb: Float = Float.NaN,   // raw platform value for this index (shown when not used)
        val volLink: Boolean = false,
        val targetLowDb: Float = 0f,
        val dynRefDb: Float = Float.NaN,       // quiet-passage bass threshold in use (NaN = off)
        val abActive: Boolean = false,         // a blind comparison is running: hide everything that reveals it
        val vbOn: Boolean = false,             // virtual bass setting (what the engine plays is in its meters)
        val vbAlgo: Int = PvbModels.P1,
        val vbLevelDb: Float = PvbSettings.VB_LEVEL_DEFAULT,   // slider (requested) level
        val vbVolLink: Boolean = false,                         // alpha 3.2 volume-linked strength
        val vbVolReductionDb: Float = 0f,                       // what the volume takes off now (0 = none)
        val vbAppliedLevelDb: Float = PvbSettings.VB_LEVEL_DEFAULT,  // level the engine is asked to play
    )

    /**
     * One condition of the blind comparison: how it changes the user's settings, a loudness trim (dB, on the output
     * gain, before the limiter) and the common headroom (dB, in the engine's final output gate after the dry/wet mix,
     * so a bypass cannot escape it).
     */
    class AbCondition(
        val id: String,
        val label: String,
        val trimDb: Float,
        val headroomDb: Float,
        val apply: (PvbSettings) -> PvbSettings,
    )

    /** Condition the engine is playing during a blind comparison (null when no comparison runs). */
    @Volatile
    var abCondition: AbCondition? = null
        private set

    @Volatile
    var abActive: Boolean = false
        private set

    /** Blind comparison is between sounds: output silent (fades over [AB_FADE_MS]). */
    @Volatile
    var abMuted: Boolean = false
        private set

    private val abListeners = java.util.concurrent.CopyOnWriteArrayList<() -> Unit>()

    /**
     * Starts, changes or ends the blind comparison. [condition] null with [active] means the user's own settings:
     * muted before the first trial, or [PvbAbConditions.HEADROOM_DB] quieter while waiting for the volume to come
     * back down after a run; [muted] silences the output.
     */
    fun setAb(active: Boolean, condition: AbCondition?, muted: Boolean = false) {
        abActive = active
        abCondition = if (active) condition else null
        abMuted = active && muted
        abTag = (abTag % 999_999) + 1
        abListeners.forEach { it() }
    }

    /**
     * Changes with every [setAb] call; the controller passes it to the engine as [PvbParam.TAG], and
     * [PvbEngine.openMs] then tells how long that exact state has really been audible (not just requested).
     */
    @Volatile
    var abTag: Int = 0
        private set

    const val AB_FADE_MS = 150f
    const val AB_MUTE_DB = -90f

    /**
     * After a comparison the listener may still have the volume turned up (both sides were sent
     * [PvbAbConditions.HEADROOM_DB] quieter). Until the volume index is back at or below this value the user's own
     * settings play that much quieter, so nothing gets suddenly loud and nothing goes silent (-1 = not waiting).
     * The controller ends the wait when the volume drops, also when the comparison screen is gone.
     */
    @Volatile
    var abReturnVolume: Int = -1
        private set

    /** The comparison itself is running: everything that could reveal the condition stays hidden. */
    val abHidden: Boolean get() = abActive && abReturnVolume < 0

    fun waitForVolumeReturn(index: Int) {
        abReturnVolume = index
        setAb(true, null, muted = false)
    }

    fun endAb() {
        abReturnVolume = -1
        setAb(false, null)
    }

    /** A new comparison starts while still waiting: it takes over. */
    fun cancelReturnWait() {
        abReturnVolume = -1
    }

    /** Volume index as the user sees it: Samsung's 150-step slider maps index i to fine values (i-1)*10 .. +9. */
    fun volumeLabel(index: Int, max: Int): String =
        if (max == 15 && index >= 1) "${index}단계(150 기준 ${(index - 1) * 10}~${(index - 1) * 10 + 9})" else "${index}단계"

    /** Shared preferences of the comparison: results, and the volume before a run (survives the app being killed). */
    const val AB_PREFS = "pvb_ab"
    const val AB_KEY_START_VOLUME = "start_volume"

    fun addAbListener(l: () -> Unit) {
        abListeners.add(l)
    }

    fun removeAbListener(l: () -> Unit) {
        abListeners.remove(l)
    }

    private val routeListeners = java.util.concurrent.CopyOnWriteArrayList<() -> Unit>()

    /** Called on the main thread whenever the output device or the speaker/external state changes. */
    fun addRouteListener(l: () -> Unit) {
        routeListeners.add(l)
    }

    fun removeRouteListener(l: () -> Unit) {
        routeListeners.remove(l)
    }

    fun notifyRouteChanged() {
        routeListeners.forEach { it() }
    }

    /**
     * The in-app measurement (PvbMeasure, s26u research) is playing its noise: no blind comparison may start, the
     * controller holds spatial off and the loudness estimator still, and the service keeps JamesDSP out.
     * Changing it notifies the comparison listeners ([addAbListener]): the controller's one listener re-evaluates
     * the same "what plays now" state for both, so a separate list would only duplicate it. Set on a worker thread.
     */
    @Volatile
    var measuring: Boolean = false
        set(value) {
            if (field == value) return
            field = value
            abListeners.forEach { it() }
        }

    /**
     * Speaker calibration ("좌우 맞추기") is playing its test sounds: JamesDSP stays out of the path, so a crossfeed,
     * stereo widening, reverb or script cannot carry the left-only sweep into the right speaker (code review
     * 2026-10-23, F4). Unlike [measuring] this keeps PVB itself as configured (the by-ear step needs spatial on).
     */
    @Volatile
    var calibrating: Boolean = false

    @Volatile
    var engine: PvbEngine? = null

    /** Published by the controller on the main thread; listeners run there when the status really changed. */
    @Volatile
    var status: Status = Status()
        set(value) {
            if (field == value) return
            field = value
            statusListeners.forEach { it() }
        }

    private val statusListeners = java.util.concurrent.CopyOnWriteArrayList<() -> Unit>()

    fun addStatusListener(l: () -> Unit) {
        statusListeners.add(l)
    }

    fun removeStatusListener(l: () -> Unit) {
        statusListeners.remove(l)
    }

    private val settingLog = LinkedHashMap<String, String>()

    /**
     * Remembers the latest value of system settings whose name contains "volume" (to find the fine-volume key);
     * one line per key, most recently changed first.
     */
    fun recordSetting(key: String, value: String) {
        synchronized(settingLog) {
            settingLog.remove(key)
            settingLog[key] = value
            while (settingLog.size > MAX_LOG) settingLog.remove(settingLog.keys.first())
        }
    }

    fun recentSettings(): List<String> = synchronized(settingLog) {
        settingLog.entries.toList().asReversed().map { "${it.key}=${it.value}" }
    }

    private const val MAX_LOG = 6

    // ------------------------------------------------------------------------------------- developer mode
    /** The developer-mode screen is visible: the engine computes its meters (P_DEV_METER). */
    @Volatile
    var devMeter: Boolean = false
        private set

    /**
     * Settings played instead of the user's while set (developer mode: "누르는 동안 원래 소리" and the share-code
     * preview). Never stored; a blind comparison always wins over it.
     */
    @Volatile
    var devOverride: PvbSettings? = null
        private set

    private val devListeners = java.util.concurrent.CopyOnWriteArrayList<() -> Unit>()

    fun addDevListener(l: () -> Unit) { devListeners.add(l) }
    fun removeDevListener(l: () -> Unit) { devListeners.remove(l) }

    fun setDevMeter(on: Boolean) {
        if (devMeter == on) return
        devMeter = on
        devListeners.forEach { it() }
    }

    fun setDevOverride(s: PvbSettings?) {
        if (devOverride == s) return
        devOverride = s
        devListeners.forEach { it() }
    }
}

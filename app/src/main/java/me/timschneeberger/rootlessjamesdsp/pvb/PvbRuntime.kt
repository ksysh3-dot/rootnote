package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * What the running service publishes for the status card. The service and the UI live in the same process,
 * so a plain singleton is enough. Everything here is read on the UI thread and written on the main thread
 * of the service, except [engine] meters, which the native side makes thread-safe.
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

    /** The in-app measurement is playing its noise (no blind comparison may start meanwhile). */
    @Volatile
    var measuring: Boolean = false
        set(value) {
            if (field == value) return
            field = value
            abListeners.forEach { it() } // also refresh the controller's loudness-estimator hold
        }

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
}

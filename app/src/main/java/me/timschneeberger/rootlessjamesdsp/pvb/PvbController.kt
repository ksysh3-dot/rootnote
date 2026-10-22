package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.database.ContentObserver
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.AudioRouting
import android.media.AudioTrack
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.roundToInt

/**
 * Control layer of the PVB engine (design doc, section 8).
 *
 * Watches the user settings, the media volume and the output device, turns them into engine parameters
 * and publishes a status for the UI. All state changes happen on the main thread; the audio thread only
 * reads [isActive].
 */
class PvbController(private val context: Context, private val engine: PvbEngine) {
    private val main = Handler(Looper.getMainLooper())
    private val prefs: SharedPreferences =
        context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
    private val audioManager: AudioManager = requireNotNull(context.getSystemService(AudioManager::class.java))

    /**
     * Read by the audio thread: true = use the PVB engine, false = use the original JamesDSP engine. During a blind
     * comparison (and its volume-return wait) the PVB engine is always in the path, because its final output gate
     * carries the comparison's mute and headroom.
     */
    @Volatile
    var isActive: Boolean = false
        private set

    private var base = PvbSettings()       // what the user set
    private var diagnosticSolo = false // session-only; never restored after restart

    fun setDiagnosticSolo(value: Boolean) {
        if (!started) return
        val allowed = settings.enabled && settings.vbOn && (!settings.speakerOnly || speaker) &&
            !PvbRuntime.abActive && !PvbRuntime.measuring
        val next = value && allowed
        if (diagnosticSolo == next) return
        diagnosticSolo = next
        push(rampMs = EDIT_RAMP_MS)
    }

    private var settings = PvbSettings()   // what the engine plays (base, or a blind-comparison condition)

    private val abPrefs: SharedPreferences = context.getSharedPreferences(PvbRuntime.AB_PREFS, Context.MODE_PRIVATE)
    // Separate preferences: saving a meter must not trigger a settings update or end an A/B trial.
    private val matchPrefs = context.getSharedPreferences("pvb_match_cache", Context.MODE_PRIVATE)
    private var matchSeedDb = -6f
    private var matchSavePolls = 0

    private fun saveMatch() {
        if (!isActive || PvbRuntime.abActive || PvbRuntime.measuring || (settings.speakerOnly && !speaker)) return
        val measured = engine.matchDb()
        if (measured.isFinite()) {
            matchSeedDb = measured.coerceIn(-30f, 3f)
            matchPrefs.edit().putFloat("gain_db", matchSeedDb).apply()
        }
    }

    private fun effective(b: PvbSettings): PvbSettings {
        if (!PvbRuntime.abActive) return b
        val c = PvbRuntime.abCondition ?: return b    // muted before the first trial, or waiting for the volume
        val t = c.apply(b)
        return t.copy(outDb = t.outDb + c.trimDb)     // loudness trim of the condition
    }

    /**
     * Final output gate (after the dry/wet mix, so a bypass after a route change cannot escape it): the comparison's
     * mute, its common headroom, and after a run the headroom until the volume is back down.
     */
    private fun gateDb(): Float = when {
        !PvbRuntime.abActive -> 0f
        PvbRuntime.abMuted -> PvbRuntime.AB_MUTE_DB
        else -> -(PvbRuntime.abCondition?.headroomDb ?: PvbAbConditions.HEADROOM_DB)
    }

    private fun updateActive() {
        isActive = settings.enabled || settings.matchOnDisable || PvbRuntime.abActive
    }

    private var lastMuted = false
    private var lastTag = 0
    private var lastGate = 0f
    private var lastMeasuring = false

    private val abListener: () -> Unit = {
        main.post {
            if (started) {
                if (!PvbRuntime.abActive) abPrefs.edit().remove(PvbRuntime.AB_KEY_START_VOLUME).apply()
                val next = effective(base)
                val muted = PvbRuntime.abMuted
                val gate = gateDb()
                // Two calls in one tap (e.g. fade out, then end) arrive here reading the same final state: push once.
                // A new tag alone is pushed too: the card waits for the engine to report that exact state as audible.
                if (next != settings || muted != lastMuted || gate != lastGate || PvbRuntime.abTag != lastTag ||
                    PvbRuntime.measuring != lastMeasuring) {
                    settings = next
                    updateActive()
                    // fading in or out takes AB_FADE_MS; switching between A and B is the usual short glide
                    push(rampMs = if (muted != lastMuted || gate != lastGate) PvbRuntime.AB_FADE_MS else EDIT_RAMP_MS)
                    lastMuted = muted
                    lastMeasuring = PvbRuntime.measuring
                }
            }
        }
    }
    private var track: AudioTrack? = null
    private var started = false
    private var lastIndex = Int.MIN_VALUE
    private var speaker = true
    private var routeName = ""
    private var routeKnown = false
    private var volume = VolumeState()

    private var sysTable: FloatArray? = null
    private var sysTableUsable = false

    private data class VolumeState(
        val index: Int = 0,
        val max: Int = 15,
        val db: Float = Float.NaN,
        val refDb: Float = Float.NaN,
        val maxDb: Float = Float.NaN,
        val source: String = "",
        val sysDb: Float = Float.NaN,  // what the platform reported for this index, even when not used
    ) {
        val dropDb: Float get() = if (refDb.isFinite() && db.isFinite()) refDb - db else 0f
        val riseAtMaxDb: Float get() = if (maxDb.isFinite() && refDb.isFinite()) maxDb - refDb else 0f
    }

    fun start() {
        if (started) return
        started = true
        PvbSettings.migrateVirtualBassModel(prefs)
        matchSeedDb = try {
            matchPrefs.getFloat("gain_db", -6f).takeIf { it.isFinite() }?.coerceIn(-30f, 3f) ?: -6f
        } catch (ignored: ClassCastException) { -6f }
        base = PvbSettings.load(prefs)
        settings = effective(base)
        updateActive()
        prefs.registerOnSharedPreferenceChangeListener(prefListener)
        PvbRuntime.addAbListener(abListener)
        try {
            context.contentResolver.registerContentObserver(Settings.System.CONTENT_URI, true, settingsObserver)
        } catch (e: Exception) {
            Log.w(TAG, "settings observer not available", e)
        }
        try {
            val filter = IntentFilter(ACTION_VOLUME_CHANGED)
            if (Build.VERSION.SDK_INT >= 33) {
                context.registerReceiver(volumeReceiver, filter, Context.RECEIVER_EXPORTED)
            } else {
                context.registerReceiver(volumeReceiver, filter)
            }
        } catch (e: Exception) {
            Log.w(TAG, "volume receiver not available", e)
        }
        audioManager.registerAudioDeviceCallback(deviceCallback, main)
        main.postDelayed(poll, POLL_MS)

        PvbRuntime.engine = engine
        PvbMeasure.restoreIfInterrupted(context)
        readVolume()
        // A comparison that was running or waiting when the app was killed: keep the headroom until the volume
        // is back down, so the music does not come back 10 dB louder than the user expects.
        val saved = abPrefs.getInt(PvbRuntime.AB_KEY_START_VOLUME, -1)
        if (saved >= 0 && !PvbRuntime.abActive) {
            if (volume.index > saved) PvbRuntime.waitForVolumeReturn(saved)
            else abPrefs.edit().remove(PvbRuntime.AB_KEY_START_VOLUME).apply()
        }
        settings = effective(base)
        updateActive()
        lastMuted = PvbRuntime.abMuted
        updateRoute(push = false)
        push(rampMs = 0f)
    }

    fun stop() {
        if (!started) return
        saveMatch()
        setDiagnosticSolo(false)
        started = false
        main.removeCallbacks(poll)
        prefs.unregisterOnSharedPreferenceChangeListener(prefListener)
        PvbRuntime.removeAbListener(abListener)
        try {
            context.contentResolver.unregisterContentObserver(settingsObserver)
        } catch (ignored: Exception) {
        }
        try {
            context.unregisterReceiver(volumeReceiver)
        } catch (ignored: Exception) {
        }
        audioManager.unregisterAudioDeviceCallback(deviceCallback)
        track?.removeOnRoutingChangedListener(routingListener)
        track = null
        if (PvbRuntime.engine === engine) PvbRuntime.engine = null
        PvbRuntime.status = PvbRuntime.Status()
    }

    /** Called by the service whenever it creates the output track; its routed device tells us where sound goes. */
    fun attachTrack(newTrack: AudioTrack) {
        main.post {
            if (!started) return@post
            track?.removeOnRoutingChangedListener(routingListener)
            track = newTrack
            newTrack.addOnRoutingChangedListener(routingListener, main)
            updateRoute(push = true)
        }
    }

    // ------------------------------------------------------------------------------------------ inputs

    private val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ ->
        val old = settings
        base = PvbSettings.load(prefs)
        settings = effective(base)
        updateActive()
        if (old.volRefPct != settings.volRefPct) readVolume()
        push(rampMs = EDIT_RAMP_MS)
    }

    private val settingsObserver = object : ContentObserver(main) {
        override fun onChange(selfChange: Boolean, uri: Uri?) {
            val key = uri?.lastPathSegment
            if (key != null && key.contains("volume", ignoreCase = true)) {
                val value = try {
                    Settings.System.getString(context.contentResolver, key)
                } catch (ignored: Exception) {
                    "?"
                }
                PvbRuntime.recordSetting(key, value ?: "null")
            }
            onVolumeMaybeChanged()
        }
    }

    private val volumeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            onVolumeMaybeChanged()
        }
    }

    private val deviceCallback = object : AudioDeviceCallback() {
        override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) = updateRoute(push = true)
        override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) = updateRoute(push = true)
    }

    private val routingListener = AudioRouting.OnRoutingChangedListener { updateRoute(push = true) }

    private val poll = object : Runnable {
        override fun run() {
            onVolumeMaybeChanged()
            updateRoute(push = true)
            if (++matchSavePolls >= 30) { saveMatch(); matchSavePolls = 0 }
            if (started) main.postDelayed(this, POLL_MS)
        }
    }

    // ------------------------------------------------------------------------------------------ volume

    private fun onVolumeMaybeChanged() {
        if (!started) return
        val index = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        if (index == lastIndex) return
        readVolume()
        push(rampMs = VOLUME_RAMP_MS)
        // after a comparison: full output again once the speaker volume is down to where it was (another device's
        // volume does not count: unplugging it later would bring the raised speaker volume back at full output)
        val back = PvbRuntime.abReturnVolume
        if (back >= 0 && PvbRuntime.abActive && speaker && index <= back) PvbRuntime.endAb()
    }

    private fun readVolume() {
        val index = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(2)
        // Samsung's 150-step volume maps to index = fine / 10 + 1 (60 -> 7), so the reference percentage of the
        // fine scale lands on floor(pct * max) + 1.
        val refIndex = (floor(settings.volRefPct / 100f * max).toInt() + 1).coerceIn(1, max)

        // The platform's dB table for the speaker, read once per maximum index and used only when it
        // looks like a real volume curve (Samsung reports about 0 dB for every index).
        val table = sysTable?.takeIf { it.size == max + 1 } ?: FloatArray(max + 1) { i ->
            if (i == 0) -96f else try {
                audioManager.getStreamVolumeDb(AudioManager.STREAM_MUSIC, i, AudioDeviceInfo.TYPE_BUILTIN_SPEAKER)
            } catch (ignored: Exception) {
                Float.NaN
            }
        }.also {
            sysTable = it
            sysTableUsable = VolumeCompensation.plausibleSystemTable(it)
            Log.i(TAG, "speaker volume table (usable=$sysTableUsable): ${it.joinToString()}")
        }

        fun dbAt(i: Int): Float = when {
            i <= 0 -> -96f
            sysTableUsable -> table[i.coerceAtMost(max)]
            else -> VolumeCompensation.fallbackDb(i.toFloat() / max)
        }
        val sysDb = if (index in 1..max) table[index] else Float.NaN
        volume = VolumeState(
            index, max, dbAt(index), dbAt(refIndex), dbAt(max),
            source = if (sysTableUsable) "system" else "fallback",
            sysDb = sysDb,
        )
        lastIndex = index
    }

    // ------------------------------------------------------------------------------------------ routing

    private fun updateRoute(push: Boolean) {
        if (!started) return
        val routed = try {
            track?.routedDevice
        } catch (ignored: Exception) {
            null
        }
        val newSpeaker: Boolean
        val newName: String
        val known: Boolean
        if (routed != null) {
            newSpeaker = routed.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER ||
                routed.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER_SAFE
            newName = deviceName(routed)
            known = true
        } else {
            // No routed device yet (track not playing): any external output counts as "not the speaker".
            val external = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
                .firstOrNull { it.type in EXTERNAL_TYPES }
            newSpeaker = external == null
            newName = external?.let { deviceName(it) } ?: "내장 스피커"
            known = false
        }
        val changed = newSpeaker != speaker || newName != routeName || known != routeKnown
        val deviceChanged = newSpeaker != speaker || newName != routeName   // not just "known now"
        speaker = newSpeaker
        routeName = newName
        routeKnown = known
        if (changed && push) push(rampMs = EDIT_RAMP_MS) else if (changed) publish(currentLowDb())
        if (deviceChanged) PvbRuntime.notifyRouteChanged()
    }

    private fun deviceName(d: AudioDeviceInfo): String = when (d.type) {
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER, AudioDeviceInfo.TYPE_BUILTIN_SPEAKER_SAFE -> "내장 스피커"
        AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_WIRED_HEADSET -> "유선 이어폰"
        AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLE_HEADSET,
        AudioDeviceInfo.TYPE_BLE_SPEAKER, AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> "블루투스"
        AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_USB_ACCESSORY -> "USB"
        AudioDeviceInfo.TYPE_HDMI, AudioDeviceInfo.TYPE_HDMI_ARC, AudioDeviceInfo.TYPE_HDMI_EARC -> "HDMI"
        else -> "장치 ${d.type}"
    }

    // ------------------------------------------------------------------------------------------ output

    private fun currentLowDb(): Float {
        val s = settings
        return if (s.volLink) {
            VolumeCompensation.lowGainDb(s.lowDb, volume.dropDb, volume.riseAtMaxDb, s.volSlope, s.volCapDb, s.volMaxDb)
        } else {
            s.lowDb
        }
    }

    /**
     * Level where quiet-passage bass starts, independent of the volume (unchanged).
     * Superseded 2026-10-21: UMIK-1 sweeps put the phone's bass limiter after the volume control, not before it.
     */
    private fun dynRefNow(): Float = settings.dynRefDb

    private fun push(rampMs: Float) {
        val s = settings
        val processing = s.enabled && (!s.speakerOnly || speaker)
        val routeAllowed = !s.speakerOnly || speaker
        val flat = s.matchOnDisable && routeAllowed && !PvbRuntime.abHidden
        val lowDb = currentLowDb()
        // Alpha 3.2: the layer gets weaker as the volume rises (link on); applied here only, never stored. A volume not
        // read yet (index 0) gives no reduction. Comparison conditions switch the link off (PvbAbConditions.v11).
        val vbLevel = VolumeLevelLink.levelFor(s, volume.index, volume.max)
        val p = FloatArray(PvbParam.COUNT)
        p[PvbParam.ENABLED] = if (processing) 1f else 0f
        p[PvbParam.HP_HZ] = s.hpHz
        p[PvbParam.LOW_HZ] = s.lowHz
        p[PvbParam.LOW_DB] = lowDb
        p[PvbParam.LOW_Q] = s.lowQ
        p[PvbParam.HI_HZ] = s.hiHz
        p[PvbParam.HI_DB] = s.hiDb
        p[PvbParam.HI_Q] = s.hiQ
        p[PvbParam.OUT_DB] = s.outDb
        p[PvbParam.CEIL_DB] = s.ceilDb
        p[PvbParam.REL_MS] = s.releaseMs
        p[PvbParam.RAMP_MS] = rampMs
        p[PvbParam.DYN_ON] = if (s.dynOn) 1f else 0f
        p[PvbParam.DYN_REF_DB] = dynRefNow()
        p[PvbParam.DYN_DOWN_RATIO] = 0.5f
        p[PvbParam.DYN_DOWN_MAX_DB] = 0f   // loud passages: no take-back (album study, 2026-10-16)
        p[PvbParam.DYN_UP_RATIO] = 0.19f   // same equal-loudness slope as the volume link
        p[PvbParam.DYN_UP_MAX_DB] = s.dynUpMaxDb
        p[PvbParam.HS_HZ] = s.hsHz
        p[PvbParam.HS_DB] = s.hsDb
        val gate = gateDb()
        p[PvbParam.GATE_DB] = gate
        lastGate = gate
        lastTag = PvbRuntime.abTag
        p[PvbParam.TAG] = if (PvbRuntime.abActive) lastTag.toFloat() else 0f
        // In matched bypass, retain the processed reference and equal delay, but only the flat path is audible.
        // A route bypass still removes virtual bass and its delay.
        p[PvbParam.VB_ON] = if (s.vbOn && (processing || flat)) 1f else 0f
        p[PvbParam.VB_ALGO] = s.vbAlgo.toFloat()
        p[PvbParam.VB_LEVEL_DB] = vbLevel
        p[PvbParam.FLAT] = if (flat) 1f else 0f
        p[PvbParam.MATCH_HOLD] = if (PvbRuntime.abActive || PvbRuntime.measuring || !routeAllowed) 1f else 0f
        p[PvbParam.MATCH_SEED_DB] = matchSeedDb
        if (!processing || !s.vbOn || PvbRuntime.abActive || PvbRuntime.measuring) diagnosticSolo = false
        p[PvbParam.DIAGNOSTIC_SOLO] = if (diagnosticSolo) 1f else 0f
        engine.setParams(p)
        publish(lowDb)
    }

    private fun publish(lowDb: Float) {
        val s = settings
        val vbReduction = VolumeLevelLink.reductionFor(s, volume.index, volume.max)
        PvbRuntime.status = PvbRuntime.Status(
            enabled = s.enabled,
            processing = s.enabled && (!s.speakerOnly || speaker),
            matchedBypass = !s.enabled && s.matchOnDisable && (!s.speakerOnly || speaker) && !PvbRuntime.abHidden,
            usingPvb = isActive,
            speaker = speaker,
            routeName = routeName,
            routeKnown = routeKnown,
            volumeIndex = volume.index,
            volumeMax = volume.max,
            volumeDb = volume.db,
            referenceDb = volume.refDb,
            dropDb = if (abs(volume.dropDb) < 0.005f) 0f else volume.dropDb,
            volumeDbSource = volume.source,
            volumeSysDb = volume.sysDb,
            volLink = s.volLink,
            targetLowDb = lowDb,
            dynRefDb = if (s.enabled && s.dynOn) dynRefNow() else Float.NaN,
            abActive = PvbRuntime.abActive,
            vbOn = s.vbOn,
            vbAlgo = s.vbAlgo,
            vbLevelDb = s.vbLevelDb,
            vbVolLink = s.vbVolLink,
            vbVolReductionDb = vbReduction,
            vbAppliedLevelDb = VolumeLevelLink.levelFor(s, volume.index, volume.max),
        )
    }

    companion object {
        private const val TAG = "PvbController"
        private const val ACTION_VOLUME_CHANGED = "android.media.VOLUME_CHANGED_ACTION"
        private const val POLL_MS = 1000L
        private const val EDIT_RAMP_MS = 20f
        private const val VOLUME_RAMP_MS = 300f

        private val EXTERNAL_TYPES = setOf(
            AudioDeviceInfo.TYPE_WIRED_HEADSET,
            AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
            AudioDeviceInfo.TYPE_BLUETOOTH_A2DP,
            AudioDeviceInfo.TYPE_BLE_HEADSET,
            AudioDeviceInfo.TYPE_BLE_SPEAKER,
            AudioDeviceInfo.TYPE_USB_HEADSET,
            AudioDeviceInfo.TYPE_USB_DEVICE,
            AudioDeviceInfo.TYPE_USB_ACCESSORY,
            AudioDeviceInfo.TYPE_HEARING_AID,
            AudioDeviceInfo.TYPE_LINE_ANALOG,
            AudioDeviceInfo.TYPE_LINE_DIGITAL,
            AudioDeviceInfo.TYPE_HDMI,
            AudioDeviceInfo.TYPE_HDMI_ARC,
            AudioDeviceInfo.TYPE_HDMI_EARC,
            AudioDeviceInfo.TYPE_AUX_LINE,
            AudioDeviceInfo.TYPE_DOCK,
        )
    }
}


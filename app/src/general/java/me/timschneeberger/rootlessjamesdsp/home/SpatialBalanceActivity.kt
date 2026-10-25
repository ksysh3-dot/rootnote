package me.timschneeberger.rootlessjamesdsp.home

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Surface
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.SpatialBalance
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService

/**
 * Spatial "좌우 맞추기": makes the two phone speakers even for the crosstalk canceller (P_XTC_BAL_*), landscape.
 *
 * - Automatic: the phone plays a sweep from the left channel, then the right (twice each) and records its own two
 *   microphones; SpatialBalance cancels the microphones and the distances (cross method). Spatial and virtual bass
 *   are held off while measuring, so the raw speakers are compared. The result is an estimate for this grip (the
 *   path assumption cannot be checked, SpatialBalance notes): a sound recording only places the by-ear slider
 *   ("귀로 확인하기"), an unsound one (one microphone, runs that disagree) is not used and tuning by ear starts from
 *   the stored values. A measured value is never stored without the listener's "저장".
 * - By ear: band noise (400-1500 Hz, then 1.5-8 kHz) in both channels with spatial on; the listener moves it to the
 *   centre. Starts from a sound automatic result, so the ear only confirms or fine-tunes it.
 *
 * Everything plays through the speaker path with JamesDSP held out (PvbRuntime.calibrating: a crossfeed or widening
 * would carry one channel into the other; DevTestSound replaces the captured music) and through
 * PvbRuntime.setDevOverride. Nothing is stored before the by-ear "저장" (or "값 지우기"); leaving the screen or a step stops the
 * sound, clears the override and goes back to the stored values.
 * The rotation it was set in is stored: turned round, the controller swaps the correction with the speakers.
 */
class SpatialBalanceActivity : BaseActivity() {
    private lateinit var prefs: SharedPreferences
    private val main = Handler(Looper.getMainLooper())
    private var ui by mutableStateOf(BalanceUi())
    /** The measuring run now; a run whose token is no longer current stops at its next short read. */
    @Volatile private var measurementRunId = 0
    private var worker: Thread? = null
    @Volatile private var recorder: AudioRecord? = null
    /** The rotation the values are being set in: the screen is held in it from the first step until saved. */
    private var calRotation = Surface.ROTATION_90

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
        val s = PvbSettings.load(prefs)
        ui = BalanceUi(lowBalanceDb = s.xtcBalLoDb, highBalanceDb = s.xtcBalHiDb)
        setContent {
            SpatialBalanceScreen(
                ui,
                BalanceActions(
                    onAuto = { startAuto() },
                    onEar = { startEar() },
                    onEarValue = { v -> setEarValue(v) },
                    onEarNext = { earNext() },
                    onRefine = { r -> refine(r) },
                    onSave = { commitBalance() },
                    onReset = { clearStoredBalance() },
                    onClose = { finish() },
                ),
            )
        }
    }

    override fun onResume() {
        super.onResume()
        ui = ui.copy(ready = engineReady())
    }

    override fun onStop() {
        stopAll()
        if (ui.step == BalanceStep.MEASURING || ui.step == BalanceStep.EAR_LO || ui.step == BalanceStep.EAR_HI) {
            restoreStored()
            ui = ui.copy(step = BalanceStep.INTRO)
        }
        super.onStop()
    }

    private fun engineReady() =
        BaseAudioProcessorService.activeServices > 0 && PvbRuntime.status.processing && !PvbRuntime.abActive

    /**
     * Ends whatever plays or records now. Invalidates the measuring run (a late read or post of the old run sees a
     * stale [measurementRunId] and drops its result), stops the recorder (unblocks a read; the measuring thread
     * releases it), stops the test sound, clears the preview ([clearOverride]) and unlocks the rotation. Stores
     * nothing and leaves the on-screen values as they are. Safe to call twice.
     */
    private fun stopAll() {
        measurementRunId++
        worker = null
        try { recorder?.stop() } catch (_: Exception) {}   // unblocks a read in progress
        DevTestSound.stop()
        clearOverride()
        unlockRotation()
    }

    /** Ends the preview: the engine plays the stored settings again and JamesDSP is back in the path. */
    private fun clearOverride() {
        PvbRuntime.setDevOverride(null)
        PvbRuntime.calibrating = false
    }

    /** The stored values on screen again (leaving a measurement or the by-ear steps without saving). */
    private fun restoreStored() {
        val s = PvbSettings.load(prefs)
        ui = ui.copy(lowBalanceDb = s.xtcBalLoDb, highBalanceDb = s.xtcBalHiDb, source = prefs.getString(PvbSettings.KEY_XTC_BAL_SOURCE, "") ?: "")
    }

    /** Hold the screen in the rotation calibration started in (a 180-degree turn would swap the speakers). */
    private fun lockRotation() {
        calRotation = currentRotation()
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LOCKED
    }

    private fun unlockRotation() {
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
    }

    /**
     * Plays [lo]/[hi] (dB, "the left speaker is louder by"; the correction lowers that side) without storing them:
     * the stored settings with spatial on ([xtcOn]) or off, these balance values and the calibration rotation, as the
     * engine's temporary override (PvbRuntime.setDevOverride), with JamesDSP held out (PvbRuntime.calibrating).
     * [measuring]: virtual bass held off too. Ended by [clearOverride]. Stores nothing.
     */
    private fun previewBalance(xtcOn: Boolean, lo: Float, hi: Float, measuring: Boolean = false) {
        val s = PvbSettings.load(prefs)
        PvbRuntime.calibrating = true
        val mode = when {
            !xtcOn -> PvbSettings.XTC_OFF
            s.xtcMode != PvbSettings.XTC_OFF -> s.xtcMode
            else -> HomeLogic.XtcPreset.BALANCED.mode
        }
        val strength = if (xtcOn && s.xtcMode == PvbSettings.XTC_OFF) HomeLogic.XtcPreset.BALANCED.strengthDb else s.xtcStrengthDb
        // set in the rotation the screen is in now, so no swap applies while calibrating
        // measuring: the virtual bass layer is added to both speakers, so it is held off too
        PvbRuntime.setDevOverride(s.copy(xtcMode = mode, xtcStrengthDb = strength, xtcBalLoDb = lo, xtcBalHiDb = hi,
            xtcBalRotation = calRotation, vbOn = s.vbOn && !measuring))
    }

    @Suppress("DEPRECATION")
    private fun currentRotation(): Int {
        val r = try {
            if (Build.VERSION.SDK_INT >= 30) display?.rotation ?: Surface.ROTATION_90 else windowManager.defaultDisplay.rotation
        } catch (_: Exception) { Surface.ROTATION_90 }
        return if (r == Surface.ROTATION_270) Surface.ROTATION_270 else Surface.ROTATION_90
    }

    // ------------------------------------------------------------------------------------------------ automatic

    private fun startAuto() {
        if (!engineReady()) { ui = ui.copy(ready = false); return }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ui = ui.copy(step = BalanceStep.FAILED, failure = BalanceFailure.NO_MIC)
            return
        }
        stopAll()
        lockRotation()
        val token = ++measurementRunId
        previewBalance(xtcOn = false, lo = 0f, hi = 0f, measuring = true)
        ui = ui.copy(step = BalanceStep.MEASURING, progress = 0f, measuring = MeasurePhase.QUIET)
        worker = Thread({ measureAll(token) }, "spatial-balance").also { it.start() }
    }

    /**
     * Microphone sources in order of preference: UNPROCESSED (no noise suppression or gain control) where offered,
     * then CAMCORDER (usually a real stereo pair), then VOICE_RECOGNITION. A run that is not sound (one microphone,
     * runs that disagree) is repeated with the next source; the first sound result wins, else the best one.
     */
    private fun measureAll(token: Int) {
        val am = getSystemService(AudioManager::class.java)
        val sources = buildList {
            if (am?.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true") add(MediaRecorder.AudioSource.UNPROCESSED)
            add(MediaRecorder.AudioSource.CAMCORDER)
            add(MediaRecorder.AudioSource.VOICE_RECOGNITION)
        }
        fun rank(r: SpatialBalance.Result) = when {
            r.recordingConsistent -> 3
            r.hasEnoughValidBands && r.channelsDiffer -> 2
            r.hasEnoughValidBands -> 1
            else -> 0
        }
        var best: SpatialBalance.Result? = null
        for ((i, source) in sources.withIndex()) {
            if (token != measurementRunId) return
            val r = measure(token, source, i, sources.size) ?: continue
            if (r.hasEnoughValidBands && (best == null || rank(r) > rank(best))) best = r
            if (r.recordingConsistent) break
        }
        post {
            if (token != measurementRunId) return@post
            DevTestSound.stop()
            clearOverride()
            val b = best
            ui = when {
                b != null -> ui.copy(step = BalanceStep.RESULT, result = b)
                else -> ui.copy(step = BalanceStep.FAILED, failure = BalanceFailure.TOO_QUIET)
            }
        }
    }

    /** One measurement with [source]; null when the recorder could not run or the run was cancelled. */
    private fun measure(token: Int, source: Int, attempt: Int, attempts: Int): SpatialBalance.Result? {
        val sr = 48000
        val minBuf = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_FLOAT)
        val rec = try {
            @Suppress("MissingPermission")
            AudioRecord(source, sr, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_FLOAT, maxOf(minBuf, sr))
        } catch (e: Exception) { null }
        if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) {
            rec?.release()
            return null
        }
        recorder = rec
        var micsReported = -1
        val period = DevTestSignal.XTC_SWEEP_PERIOD
        val total = 1.3 + 4 * (period + 0.3)
        var done = 0.0
        try {
            rec.startRecording()
            // the recorder's own list of the microphones in use (empty or failing on some phones: unknown)
            micsReported = try { rec.activeMicrophones.size.takeIf { it > 0 } ?: -1 } catch (_: Exception) { -1 }
            // short reads: a cancelled run notices within 0.1 s, and the progress moves smoothly
            fun take(seconds: Double): SpatialBalance.Recording? {
                val frames = (seconds * sr).toInt()
                val buf = FloatArray(2 * frames)
                var got = 0
                val chunk = 2 * (sr / 10)
                while (got < buf.size) {
                    if (token != measurementRunId) return null
                    val n = rec.read(buf, got, minOf(chunk, buf.size - got), AudioRecord.READ_BLOCKING)
                    if (n <= 0) return null
                    got += n
                    val f = ((attempt + (done + got / 2.0 / sr) / total) / attempts).toFloat().coerceIn(0f, 1f)
                    post { if (token == measurementRunId) ui = ui.copy(progress = f) }
                }
                done += seconds
                return SpatialBalance.Recording(buf, frames)
            }
            take(0.3) ?: return null                      // settle
            post { if (token == measurementRunId) ui = ui.copy(measuring = MeasurePhase.QUIET) }
            val noise = take(1.0) ?: return null
            val left = ArrayList<SpatialBalance.Recording>()
            val right = ArrayList<SpatialBalance.Recording>()
            for (k in listOf(DevTestKind.XTC_SWEEP_L, DevTestKind.XTC_SWEEP_R, DevTestKind.XTC_SWEEP_L, DevTestKind.XTC_SWEEP_R)) {
                if (token != measurementRunId) return null
                post { if (token == measurementRunId) ui = ui.copy(measuring = if (k == DevTestKind.XTC_SWEEP_L) MeasurePhase.LEFT else MeasurePhase.RIGHT) }
                DevTestSound.start(k)
                val r = take(period)
                DevTestSound.stop()
                r ?: return null
                take(0.3) ?: return null
                if (k == DevTestKind.XTC_SWEEP_L) left.add(r) else right.add(r)
            }
            return SpatialBalance.analyze(noise, left, right, sr, micsReported)
        } catch (e: Exception) {
            return null
        } finally {
            if (token == measurementRunId) DevTestSound.stop()
            try { rec.stop() } catch (_: Exception) {}
            rec.release()
            if (recorder === rec) recorder = null
        }
    }

    private fun post(block: () -> Unit) { main.post { if (!isFinishing) block() } }

    /**
     * "귀로 확인하기" / "귀로 맞추기": the by-ear steps start from a sound result, otherwise from the stored values.
     * Nothing is stored here; "저장" at the end of the by-ear steps does (code review 2026-10-23, F5).
     */
    private fun refine(r: SpatialBalance.Result) {
        if (r.recordingConsistent) ui = ui.copy(lowBalanceDb = r.lowBalanceDb, highBalanceDb = r.highBalanceDb, source = "mic")
        else restoreStored()
        startEar()
    }

    // ------------------------------------------------------------------------------------------------ by ear

    private fun startEar() {
        if (!engineReady()) { ui = ui.copy(ready = false); return }
        if (ui.step != BalanceStep.RESULT) lockRotation()   // after a measurement the screen is already held
        ui = ui.copy(step = BalanceStep.EAR_LO, source = if (ui.source == "mic" || ui.source == "mic+ear") "mic+ear" else "ear")
        previewBalance(xtcOn = true, lo = ui.lowBalanceDb, hi = ui.highBalanceDb)
        DevTestSound.start(DevTestKind.XTC_BAND_LO)
    }

    /** The slider: moving it right moves the sound right (the left speaker gets relatively quieter). */
    private fun setEarValue(v: Float) {
        val b = PvbSettings.clampBalance(v)
        ui = if (ui.step == BalanceStep.EAR_LO) ui.copy(lowBalanceDb = b) else ui.copy(highBalanceDb = b)
        previewBalance(xtcOn = true, lo = ui.lowBalanceDb, hi = ui.highBalanceDb)
    }

    private fun earNext() {
        if (ui.step == BalanceStep.EAR_LO) {
            ui = ui.copy(step = BalanceStep.EAR_HI)
            DevTestSound.start(DevTestKind.XTC_BAND_HI)
        } else {
            commitBalance()
        }
    }

    // ------------------------------------------------------------------------------------------------ store

    /** Stores the on-screen balance (the only place that does, with [clearStoredBalance]) and ends the preview. */
    private fun commitBalance() {
        stopAll()
        prefs.edit()
            .putFloat(PvbSettings.KEY_XTC_BAL_LO, ui.lowBalanceDb)
            .putFloat(PvbSettings.KEY_XTC_BAL_HI, ui.highBalanceDb)
            .putInt(PvbSettings.KEY_XTC_BAL_ROT, calRotation)
            .putString(PvbSettings.KEY_XTC_BAL_SOURCE, ui.source)
            .apply()
        ui = ui.copy(step = BalanceStep.DONE)
    }

    /** "값 지우기": stores a zero balance and forgets its rotation and source (an explicit store, like [commitBalance]). */
    private fun clearStoredBalance() {
        stopAll()
        prefs.edit()
            .putFloat(PvbSettings.KEY_XTC_BAL_LO, 0f)
            .putFloat(PvbSettings.KEY_XTC_BAL_HI, 0f)
            .remove(PvbSettings.KEY_XTC_BAL_ROT)
            .remove(PvbSettings.KEY_XTC_BAL_SOURCE)
            .apply()
        ui = ui.copy(step = BalanceStep.INTRO, lowBalanceDb = 0f, highBalanceDb = 0f, result = null, source = "")
    }

}

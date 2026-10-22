package me.timschneeberger.rootlessjamesdsp.home

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
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
 *   microphones; SpatialBalance cancels the microphones and the distances (cross method). Spatial is held off while
 *   measuring, so the raw speakers are compared.
 * - By ear: band noise (400-1500 Hz, then 1.5-8 kHz) in both channels with spatial on; the listener moves it to the
 *   centre. Starts from the automatic result if there is one, so the ear only fine-tunes it.
 *
 * Everything plays through the normal engine and speaker path (DevTestSound replaces the captured music) and through
 * PvbRuntime.setDevOverride, never stored until "저장"; leaving the screen stops the sound and clears the override.
 * The rotation it was set in is stored: turned round, the controller swaps the correction with the speakers.
 */
class SpatialBalanceActivity : BaseActivity() {
    private lateinit var prefs: SharedPreferences
    private val main = Handler(Looper.getMainLooper())
    private var ui by mutableStateOf(BalanceUi())
    @Volatile private var cancelled = false
    private var worker: Thread? = null

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
        ui = BalanceUi(loDb = s.xtcBalLoDb, hiDb = s.xtcBalHiDb)
        setContent {
            SpatialBalanceScreen(
                ui,
                BalanceActions(
                    onAuto = { startAuto() },
                    onEar = { startEar() },
                    onEarValue = { v -> setEarValue(v) },
                    onEarNext = { earNext() },
                    onApplyAuto = { r -> applyAuto(r) },
                    onSave = { save() },
                    onReset = { reset() },
                    onClose = { finish() },
                ),
            )
        }
    }

    override fun onResume() {
        super.onResume()
        val reduce = try {
            Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        } catch (_: Exception) { false }
        ui = ui.copy(reduceMotion = reduce, ready = engineReady())
    }

    override fun onStop() {
        stopAll()
        if (ui.step == BalanceStep.MEASURING || ui.step == BalanceStep.EAR_LO || ui.step == BalanceStep.EAR_HI)
            ui = ui.copy(step = BalanceStep.INTRO)
        super.onStop()
    }

    private fun engineReady() =
        BaseAudioProcessorService.activeServices > 0 && PvbRuntime.status.processing && !PvbRuntime.abActive

    private fun stopAll() {
        cancelled = true
        worker?.interrupt()
        worker = null
        DevTestSound.stop()
        PvbRuntime.setDevOverride(null)
    }

    private fun override(xtcOn: Boolean, lo: Float, hi: Float) {
        val s = PvbSettings.load(prefs)
        val mode = when {
            !xtcOn -> PvbSettings.XTC_OFF
            s.xtcMode != PvbSettings.XTC_OFF -> s.xtcMode
            else -> HomeLogic.XtcPreset.BALANCED.mode
        }
        val strength = if (xtcOn && s.xtcMode == PvbSettings.XTC_OFF) HomeLogic.XtcPreset.BALANCED.strengthDb else s.xtcStrengthDb
        // set in the rotation the screen is in now, so no swap applies while calibrating
        PvbRuntime.setDevOverride(s.copy(xtcMode = mode, xtcStrengthDb = strength, xtcBalLoDb = lo, xtcBalHiDb = hi,
            xtcBalRotation = currentRotation()))
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
        cancelled = false
        override(xtcOn = false, lo = 0f, hi = 0f)
        ui = ui.copy(step = BalanceStep.MEASURING, progress = 0f, measuring = MeasurePhase.QUIET)
        worker = Thread({ measure() }, "spatial-balance").also { it.start() }
    }

    private fun measure() {
        val sr = 48000
        val am = getSystemService(AudioManager::class.java)
        val unprocessed = am?.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
        val source = if (unprocessed) MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
        val minBuf = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_FLOAT)
        val rec = try {
            @Suppress("MissingPermission")
            AudioRecord(source, sr, AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_FLOAT, maxOf(minBuf, sr))
        } catch (e: Exception) { null }
        if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) {
            rec?.release()
            post { ui = ui.copy(step = BalanceStep.FAILED, failure = BalanceFailure.NO_MIC); stopAll() }
            return
        }
        try {
            rec.startRecording()
            val total = 1.0 + 4 * (DevTestKind_SWEEP_PERIOD + 0.3)
            var done = 0.0
            fun take(seconds: Double): SpatialBalance.Recording? {
                val frames = (seconds * sr).toInt()
                val buf = FloatArray(2 * frames)
                var got = 0
                while (got < buf.size) {
                    if (cancelled) return null
                    val n = rec.read(buf, got, buf.size - got, AudioRecord.READ_BLOCKING)
                    if (n <= 0) return null
                    got += n
                    post { ui = ui.copy(progress = ((done + got / 2.0 / sr) / total).toFloat().coerceIn(0f, 1f)) }
                }
                done += seconds
                return SpatialBalance.Recording(buf, frames)
            }
            take(0.3) ?: return                       // settle
            done = 0.0
            val noise = take(1.0) ?: return
            val left = ArrayList<SpatialBalance.Recording>()
            val right = ArrayList<SpatialBalance.Recording>()
            for (k in listOf(DevTestKind.XTC_SWEEP_L, DevTestKind.XTC_SWEEP_R, DevTestKind.XTC_SWEEP_L, DevTestKind.XTC_SWEEP_R)) {
                post { ui = ui.copy(measuring = if (k == DevTestKind.XTC_SWEEP_L) MeasurePhase.LEFT else MeasurePhase.RIGHT) }
                DevTestSound.start(k)
                val r = take(DevTestKind_SWEEP_PERIOD) ?: return
                DevTestSound.stop()
                take(0.3) ?: return
                if (k == DevTestKind.XTC_SWEEP_L) left.add(r) else right.add(r)
            }
            val result = SpatialBalance.analyze(noise, left, right, sr)
            post {
                DevTestSound.stop()
                PvbRuntime.setDevOverride(null)
                ui = if (result.usable) ui.copy(step = BalanceStep.RESULT, result = result)
                else ui.copy(step = BalanceStep.FAILED, failure = BalanceFailure.TOO_QUIET)
            }
        } catch (e: Exception) {
            post { ui = ui.copy(step = BalanceStep.FAILED, failure = BalanceFailure.NO_MIC); stopAll() }
        } finally {
            DevTestSound.stop()
            try { rec.stop() } catch (_: Exception) {}
            rec.release()
        }
    }

    private fun post(block: () -> Unit) { main.post { if (!isFinishing) block() } }

    private fun applyAuto(r: SpatialBalance.Result) {
        ui = ui.copy(loDb = r.loDb, hiDb = r.hiDb, source = "mic")
        save()
    }

    // ------------------------------------------------------------------------------------------------ by ear

    private fun startEar() {
        if (!engineReady()) { ui = ui.copy(ready = false); return }
        cancelled = false
        ui = ui.copy(step = BalanceStep.EAR_LO, source = if (ui.source == "mic") "mic+ear" else "ear")
        override(xtcOn = true, lo = ui.loDb, hi = ui.hiDb)
        DevTestSound.start(DevTestKind.XTC_BAND_LO)
    }

    /** The slider: moving it right moves the sound right (the left speaker gets relatively quieter). */
    private fun setEarValue(v: Float) {
        val b = PvbSettings.clampBalance(v)
        ui = if (ui.step == BalanceStep.EAR_LO) ui.copy(loDb = b) else ui.copy(hiDb = b)
        override(xtcOn = true, lo = ui.loDb, hi = ui.hiDb)
    }

    private fun earNext() {
        if (ui.step == BalanceStep.EAR_LO) {
            ui = ui.copy(step = BalanceStep.EAR_HI)
            DevTestSound.start(DevTestKind.XTC_BAND_HI)
        } else {
            save()
        }
    }

    // ------------------------------------------------------------------------------------------------ store

    private fun save() {
        stopAll()
        prefs.edit()
            .putFloat(PvbSettings.KEY_XTC_BAL_LO, ui.loDb)
            .putFloat(PvbSettings.KEY_XTC_BAL_HI, ui.hiDb)
            .putInt(PvbSettings.KEY_XTC_BAL_ROT, currentRotation())
            .putString(PvbSettings.KEY_XTC_BAL_SOURCE, ui.source)
            .apply()
        ui = ui.copy(step = BalanceStep.DONE)
    }

    private fun reset() {
        stopAll()
        prefs.edit()
            .putFloat(PvbSettings.KEY_XTC_BAL_LO, 0f)
            .putFloat(PvbSettings.KEY_XTC_BAL_HI, 0f)
            .remove(PvbSettings.KEY_XTC_BAL_ROT)
            .remove(PvbSettings.KEY_XTC_BAL_SOURCE)
            .apply()
        ui = ui.copy(step = BalanceStep.INTRO, loDb = 0f, hiDb = 0f, result = null, source = "")
    }

    private companion object {
        const val DevTestKind_SWEEP_PERIOD = 4.5   // DevTestSignal.XTC_SWEEP_PERIOD: sweep 3 s + 1.5 s silence
    }
}

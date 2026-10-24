package me.timschneeberger.rootlessjamesdsp.home

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService
import java.security.SecureRandom

/**
 * "저음, 왕창 올려도 될까요?": the EQ explanation as a short landscape motion story (BassStory.kt), in the format of
 * the spatial one (SpatialStoryActivity). Opened from the (i) of the advanced screen's tone section and from the
 * JamesDSP equalizer's note. Landscape only while it is open (manifest: sensorLandscape).
 *
 * "직접 들어 보기" (TryUi): the listener is told that within 30 s, at a moment not shown, 63 Hz goes up 10 dB for
 * 8 s; they tap when they think it changed; at the end the real moment is shown. Played through
 * PvbRuntime.setDevOverride, never stored: the trial's base is the user's settings with virtual bass, the volume
 * link and the dynamic lift off and the low bell moved to 63 Hz at 0 dB (low cut 30 Hz), so the only change inside
 * the trial is the 63 Hz bell going to +10 dB (octave wide: no skirt into 200 Hz). The engine ramps filter changes;
 * the output limiter and the ear-protection ceiling stay on. Leaving the screen gives the user's settings back.
 */
class BassStoryActivity : BaseActivity() {
    private var reduceMotion by mutableStateOf(false)
    private var trial by mutableStateOf(TryUi())
    private val handler = Handler(Looper.getMainLooper())
    private val random = SecureRandom()
    private var startedAt = 0L
    private var base: PvbSettings? = null
    private var boosted = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
        val actions = TryActions(
            onStart = { start() },
            onTap = { if (trial.phase == TryUi.RUN && trial.tapAt == null) trial = trial.copy(tapAt = elapsed()) },
            onKind = { k -> trial = trial.copy(kind = k) },
            onAgain = { trial = availability(TryUi()) },
        )
        setContent { BassStory(reduceMotion = reduceMotion, trial = trial, actions = actions, onClose = { finish() }) }
    }

    override fun onResume() {
        super.onResume()
        reduceMotion = try {
            Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        } catch (_: Exception) { false }
        if (trial.phase == TryUi.IDLE) trial = availability(trial)
        handler.removeCallbacks(watch)
        handler.post(watch)
    }

    override fun onStop() {
        // Leaving the story always gives the user's own settings back; a trial in progress is dropped.
        handler.removeCallbacksAndMessages(null)
        if (trial.phase == TryUi.PREP || trial.phase == TryUi.RUN) trial = TryUi()
        restore()
        super.onStop()
    }

    /** Our engine plays on the speaker (not bypassed, not in a comparison); the volume is at most half. */
    private fun availability(t: TryUi): TryUi {
        val st = PvbRuntime.status
        val running = BaseAudioProcessorService.activeServices > 0 && st.processing && st.speaker && !PvbRuntime.abActive
        val high = st.volumeMax > 0 && st.volumeIndex * 2 > st.volumeMax
        return t.copy(canTry = running, volumeTooHigh = high)
    }

    /** While idle, follows the engine and the volume (about twice a second). */
    private val watch = object : Runnable {
        override fun run() {
            if (trial.phase == TryUi.IDLE) trial = availability(trial)
            handler.postDelayed(this, 500)
        }
    }

    private fun elapsed(): Float = (SystemClock.elapsedRealtime() - startedAt) / 1000f

    private fun start() {
        val t = availability(trial)
        if (!t.canTry || t.volumeTooHigh) { trial = t; return }
        val user = PvbSettings.load(getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE))
        val b = user.copy(vbOn = false, volLink = false, dynOn = false, hpHz = 30f, lowHz = 63f, lowDb = 0f, lowQ = 1.41f)
        base = b
        boosted = false
        PvbRuntime.setDevOverride(b)
        // 8 s of +10 dB starting 5-17 s into the 30 s (whole seconds are shown; the start is not)
        val from = 5f + random.nextInt(1300) / 100f
        trial = t.copy(phase = TryUi.PREP, elapsed = 0f, changeFrom = from, changeTo = from + 8f, tapAt = null, kind = null,
            restored = false)
        // the base settings settle (virtual bass off, the low bell moves) before the 30 s begin
        handler.postDelayed({
            startedAt = SystemClock.elapsedRealtime()
            trial = trial.copy(phase = TryUi.RUN)
            handler.post(tick)
        }, 2500)
    }

    private val tick = object : Runnable {
        override fun run() {
            if (trial.phase != TryUi.RUN) return
            val e = elapsed()
            val inside = e >= trial.changeFrom && e < trial.changeTo
            val b = base
            if (b != null && inside != boosted) {
                boosted = inside
                PvbRuntime.setDevOverride(if (inside) b.copy(lowDb = 10f) else b)
            }
            if (e >= trial.lengthS) {
                restore()
                trial = trial.copy(phase = TryUi.DONE, elapsed = trial.lengthS, restored = true)
                return
            }
            trial = trial.copy(elapsed = e)
            handler.postDelayed(this, 100)
        }
    }

    private fun restore() {
        if (base != null) {
            base = null
            boosted = false
            PvbRuntime.setDevOverride(null)
        }
    }

    companion object {
        fun intent(context: Context): Intent = Intent(context, BassStoryActivity::class.java)
    }
}

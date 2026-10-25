package me.timschneeberger.rootlessjamesdsp.home

import android.content.Context
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService

/**
 * "공간감은 어떻게 만들어질까요?": the spatial (crosstalk cancellation) explanation as a short landscape motion story
 * (SpatialStory.kt). Landscape only while it is open (manifest: sensorLandscape); the home screen keeps its own
 * orientation.
 *
 * "들어 보기" (last scene) plays spatial on or off through PvbRuntime.setDevOverride, never stored: closing the story
 * (or leaving it) clears the override, so the user's own settings play again.
 */
class SpatialStoryActivity : BaseActivity() {
    private lateinit var prefs: SharedPreferences
    private var running by mutableStateOf(false)
    /** null = the user's own setting plays; true / false = spatial forced on / off for listening. */
    private var listen by mutableStateOf<Boolean?>(null)
    private var userXtcOn by mutableStateOf(false)
    private var distanceCm by mutableIntStateOf(40)
    private var hatCm by mutableIntStateOf(57)

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
        userXtcOn = s.xtcMode != PvbSettings.XTC_OFF
        distanceCm = s.xtcDistanceCm.toInt()
        hatCm = s.xtcHatCm.toInt()
        setContent {
            SpatialStory(
                state = StoryState(
                    canListen = running,
                    listening = listen ?: userXtcOn,
                    distanceCm = distanceCm,
                    hatCm = hatCm,
                ),
                onListen = { on -> setListen(on) },
                onClose = { finish() },
            )
        }
    }

    override fun onResume() {
        super.onResume()
        // Listening only makes sense while our engine plays on the speaker (not bypassed, not in a comparison).
        running = BaseAudioProcessorService.activeServices > 0 && PvbRuntime.status.processing && !PvbRuntime.abActive
    }

    override fun onStop() {
        // Leaving the story always gives the user's own settings back.
        if (listen != null) {
            listen = null
            PvbRuntime.setDevOverride(null)
        }
        super.onStop()
    }

    private fun setListen(on: Boolean) {
        val s = PvbSettings.load(prefs)
        listen = on
        val mode = when {
            !on -> PvbSettings.XTC_OFF
            s.xtcMode != PvbSettings.XTC_OFF -> s.xtcMode
            else -> HomeLogic.XtcPreset.BALANCED.mode
        }
        val strength = if (on && s.xtcMode == PvbSettings.XTC_OFF) HomeLogic.XtcPreset.BALANCED.strengthDb else s.xtcStrengthDb
        PvbRuntime.setDevOverride(s.copy(xtcMode = mode, xtcStrengthDb = strength))
    }
}

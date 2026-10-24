package me.timschneeberger.rootlessjamesdsp.home

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity

/**
 * "저음, 왕창 올려도 될까요?": the EQ explanation as a short landscape motion story (BassStory.kt), in the format of
 * the spatial one (SpatialStoryActivity). Opened from the (i) of the advanced screen's tone section and from the
 * JamesDSP equalizer's note. Landscape only while it is open (manifest: sensorLandscape). Plays nothing.
 */
class BassStoryActivity : BaseActivity() {
    private var reduceMotion by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
        setContent { BassStory(reduceMotion = reduceMotion, onClose = { finish() }) }
    }

    override fun onResume() {
        super.onResume()
        reduceMotion = try {
            Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        } catch (_: Exception) { false }
    }

    companion object {
        fun intent(context: Context): Intent = Intent(context, BassStoryActivity::class.java)
    }
}

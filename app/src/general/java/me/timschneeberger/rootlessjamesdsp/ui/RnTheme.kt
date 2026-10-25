package me.timschneeberger.rootlessjamesdsp.ui

import android.content.Context
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.SpringSpec
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.snap
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.toArgb
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.home.RootnotePalette
import me.timschneeberger.rootlessjamesdsp.home.rootnotePalette

/*
 * The shared Compose kit of the general build's detail screens (settings, about, excluded apps, advanced, measuring):
 * the theme here, the rows and controls in RnRows.kt, RnSlider.kt and RnOverlays.kt, the preference bindings in
 * RnPrefs.kt. Every value comes from docs/DESIGN.md through RootnotePalette (home/RootnotePalette.kt), and every
 * component is written the way the home screen and the developer mode screen write it, so a new page is built from
 * these pieces and never re-draws a row, a switch or a sheet of its own.
 */

/** The palette of the screen being drawn (theme-aware: home/RootnotePalette.kt). */
val LocalRn = staticCompositionLocalOf<RootnotePalette> { error("RnTheme not applied") }

/** True when the system animations are off: every motion snaps (docs/DESIGN.md 6). */
val LocalRnReduceMotion = staticCompositionLocalOf { false }

/** cubic-bezier(0.32, 0.72, 0, 1): positions, sizes, colours (docs/DESIGN.md 6 IosEase). */
val RnEase = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)

/** docs/DESIGN.md 6: a press answers at once, colours change in 150 ms, things move in 300 ms at most. */
const val RN_MS_COLOR = 150
const val RN_MS_MOVE = 300

/**
 * A control let go of: a spring (slightly under-damped, response about 0.3 s), so a new press takes over its current
 * value and speed instead of starting a timed animation from the beginning. Replaces the 350 ms overshoot curve,
 * whose peak (about 0.5 % of a 0.94 scale) was never visible.
 */
fun <T> rnRelease(): SpringSpec<T> = spring(dampingRatio = 0.8f, stiffness = 439f)

/** A position that settles without bouncing (a slider thumb let go of, a tapped value). */
fun <T> rnSettle(): SpringSpec<T> = spring(dampingRatio = 1f, stiffness = 439f)

/** [spec], or an instant change when the system animations are off. */
@Composable
fun <T> rnMotion(spec: FiniteAnimationSpec<T>): FiniteAnimationSpec<T> = if (LocalRnReduceMotion.current) snap() else spec

/** The system "animator duration scale" is 0 (accessibility: remove animations). */
fun animationsOff(context: Context): Boolean = try {
    Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
} catch (_: Exception) { false }

/** Provides the palette, reduced motion and a Material scheme mapped onto the palette (for dialogs, sheets, text fields). */
@Composable
fun RnTheme(reduceMotion: Boolean, content: @Composable () -> Unit) {
    val c = rootnotePalette()
    val scheme = if (c.dark) darkColorScheme(
        primary = c.fill, onPrimary = c.onFill, background = c.bg, surface = c.bg, onBackground = c.textPrimary,
        onSurface = c.textPrimary, onSurfaceVariant = c.textSecondary, outline = c.chipBorder,
        surfaceContainerHigh = c.bg, surfaceContainerLow = c.bg, surfaceContainer = c.bg,
    ) else lightColorScheme(
        primary = c.fill, onPrimary = c.onFill, background = c.bg, surface = c.bg, onBackground = c.textPrimary,
        onSurface = c.textPrimary, onSurfaceVariant = c.textSecondary, outline = c.chipBorder,
        surfaceContainerHigh = c.bg, surfaceContainerLow = c.bg, surfaceContainer = c.bg,
    )
    CompositionLocalProvider(LocalRn provides c, LocalRnReduceMotion provides reduceMotion) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

/**
 * Base of the kit's activities: the app theme (BaseActivity), the page colour behind the window, status and
 * navigation bar icons that match the mode, edge-to-edge (pages pad for the bars), and reduced motion re-read on
 * every resume. Subclasses call [setRnContent] in onCreate.
 */
abstract class RnActivity : BaseActivity() {
    private var reduceMotion by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
        reduceMotion = animationsOff(this)
    }

    override fun onResume() {
        super.onResume()
        reduceMotion = animationsOff(this)
    }

    protected fun setRnContent(content: @Composable () -> Unit) {
        setContent {
            RnTheme(reduceMotion) {
                val bg = LocalRn.current.bg
                SideEffect { window.setBackgroundDrawable(ColorDrawable(bg.toArgb())) }
                content()
            }
        }
    }
}

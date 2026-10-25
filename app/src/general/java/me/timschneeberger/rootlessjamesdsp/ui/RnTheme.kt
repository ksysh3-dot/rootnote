package me.timschneeberger.rootlessjamesdsp.ui

import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
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

/** Provides the palette, reduced motion and a Material scheme mapped onto the palette (for dialogs, sheets, text fields). */
@Composable
fun RnTheme(content: @Composable () -> Unit) {
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
    CompositionLocalProvider(LocalRn provides c) {
        ProvideRnMotion { MaterialTheme(colorScheme = scheme, content = content) }
    }
}

/**
 * Base of the kit's activities: the app theme (BaseActivity), the page colour behind the window, status and
 * navigation bar icons that match the mode, and edge-to-edge (pages pad for the bars). Subclasses call [setRnContent] in onCreate.
 */
abstract class RnActivity : BaseActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
    }

    protected fun setRnContent(content: @Composable () -> Unit) {
        setContent {
            RnTheme {
                val bg = LocalRn.current.bg
                SideEffect { window.setBackgroundDrawable(ColorDrawable(bg.toArgb())) }
                content()
            }
        }
    }
}

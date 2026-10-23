package me.timschneeberger.rootlessjamesdsp.home

import android.content.Context
import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.colorResource
import com.google.android.material.color.MaterialColors
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.model.preference.AppTheme
import me.timschneeberger.rootlessjamesdsp.utils.Constants

/**
 * The colours every Compose screen of the general build draws with (docs/DESIGN.md 2).
 *
 * Neutrals (page, band, text, chip outline, switch-off, slider track) are always the rn_* tokens. The accent family
 * (fill, accent text, selected chip, text on the fill) follows the app theme chosen in 설정 › 외관: for "심해 틸"
 * (AppTheme.ROOTNOTE, the default) it is exactly the rn_* tokens; for any other theme it is read from that theme's
 * Material colours, so the Compose screens and the remaining View screens look like one app. The spatial purple
 * (rn_xtc_*) stays the same in every theme: it names a feature, not the brand. "퓨어 블랙 다크 모드" turns the page
 * black in dark mode.
 */
@Immutable
data class RootnotePalette(
    val bg: Color,
    val band: Color,
    val press: Color,
    val divider: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val chevron: Color,
    val fill: Color,
    val accentText: Color,
    val chipBg: Color,
    val chipBorder: Color,
    val chipText: Color,
    val chipSelectedBg: Color,
    val chipSelectedBorder: Color,
    val chipSelectedText: Color,
    val switchOff: Color,
    val sliderInactive: Color,
    val thumb: Color,
    val xtcFill: Color,
    val xtcAccentText: Color,
    val xtcChipSelectedBg: Color,
    val xtcChipSelectedBorder: Color,
    val xtcChipSelectedText: Color,
    /** Text and icons on [fill] (rn_m3_onPrimary for 심해 틸: white in light mode, deep teal in dark mode). */
    val onFill: Color,
    val dark: Boolean,
) {
    /** The same palette with the spatial purple in the accent roles (fill, accent text, selected chip). */
    fun spatial(): RootnotePalette = copy(
        fill = xtcFill, accentText = xtcAccentText, chipSelectedBg = xtcChipSelectedBg,
        chipSelectedBorder = xtcChipSelectedBorder, chipSelectedText = xtcChipSelectedText, onFill = Color.White,
    )
}

/** The app theme stored in 설정 › 외관 (prefs "application"), and whether pure black is on. */
internal fun appThemeChoice(context: Context): Pair<AppTheme, Boolean> {
    val prefs = context.getSharedPreferences(Constants.PREF_APP, Context.MODE_PRIVATE)
    val name = prefs.getString(context.getString(R.string.key_appearance_app_theme),
        context.getString(R.string.default_appearance_app_theme))
    val theme = AppTheme.values().firstOrNull { it.name == name } ?: AppTheme.ROOTNOTE
    val black = prefs.getBoolean(context.getString(R.string.key_appearance_pure_black),
        context.resources.getBoolean(R.bool.default_appearance_pure_black))
    return theme to black
}

@Composable
fun rootnotePalette(): RootnotePalette {
    val context = LocalContext.current
    val dark = (LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
    // the activity is recreated when the theme or pure black changes (BaseActivity), so reading once is enough
    val (theme, black) = remember(context) { appThemeChoice(context) }
    val bg = if (dark && black) Color.Black else colorResource(R.color.rn_bg)
    val base = RootnotePalette(
        bg = bg,
        band = colorResource(R.color.rn_band),
        press = colorResource(R.color.rn_press),
        divider = colorResource(R.color.rn_divider),
        textPrimary = colorResource(R.color.rn_text_primary),
        textSecondary = colorResource(R.color.rn_text_secondary),
        chevron = colorResource(R.color.rn_chevron),
        fill = colorResource(R.color.rn_fill),
        accentText = colorResource(R.color.rn_accent_text),
        chipBg = if (dark && black) Color.Black else colorResource(R.color.rn_chip_bg),
        chipBorder = colorResource(R.color.rn_chip_border),
        chipText = colorResource(R.color.rn_chip_text),
        chipSelectedBg = colorResource(R.color.rn_chip_selected_bg),
        chipSelectedBorder = colorResource(R.color.rn_chip_selected_border),
        chipSelectedText = colorResource(R.color.rn_chip_selected_text),
        switchOff = colorResource(R.color.rn_switch_off),
        sliderInactive = colorResource(R.color.rn_slider_inactive),
        thumb = colorResource(R.color.rn_thumb),
        xtcFill = colorResource(R.color.rn_xtc_fill),
        xtcAccentText = colorResource(R.color.rn_xtc_accent_text),
        xtcChipSelectedBg = colorResource(R.color.rn_xtc_chip_selected_bg),
        xtcChipSelectedBorder = colorResource(R.color.rn_xtc_chip_selected_border),
        xtcChipSelectedText = colorResource(R.color.rn_xtc_chip_selected_text),
        onFill = colorResource(R.color.rn_m3_onPrimary),
        dark = dark,
    )
    if (theme == AppTheme.ROOTNOTE) return base
    return remember(context, dark, base) { themedAccents(context, base) }
}

/** The accent family of another app theme, read from its Material colours (the activity's theme). */
private fun themedAccents(context: Context, base: RootnotePalette): RootnotePalette {
    fun attr(id: Int, fallback: Color) = Color(MaterialColors.getColor(context, id, fallback.toArgb()))
    val primary = attr(com.google.android.material.R.attr.colorPrimary, base.fill)
    val onPrimary = attr(com.google.android.material.R.attr.colorOnPrimary, base.onFill)
    val container = attr(com.google.android.material.R.attr.colorPrimaryContainer, base.chipSelectedBg)
    val onContainer = attr(com.google.android.material.R.attr.colorOnPrimaryContainer, base.chipSelectedText)
    return base.copy(
        fill = primary,
        // tone 40 of a Material scheme on white, tone 80 on the dark page: readable as accent text in both modes
        accentText = primary,
        chipSelectedBg = container,
        chipSelectedBorder = primary.copy(alpha = 0.5f).compositeOver(base.bg),
        chipSelectedText = onContainer,
        onFill = onPrimary,
    )
}

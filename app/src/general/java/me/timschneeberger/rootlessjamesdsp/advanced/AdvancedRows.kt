package me.timschneeberger.rootlessjamesdsp.advanced

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringArrayResource
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceRow
import me.timschneeberger.rootlessjamesdsp.ui.RnGroupTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnNote
import me.timschneeberger.rootlessjamesdsp.ui.RnPrefsFile
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.RnValueSlider
import me.timschneeberger.rootlessjamesdsp.ui.rememberPrefsFile
import java.util.Locale

/*
 * The advanced screen's rows bound to a SharedPreferences key, written as the legacy Preference widgets behaved:
 * a switch stores a boolean, a slider a float (MaterialSeekbarPreference), a choice a string (ListPreference).
 * Inside a sealed JamesDSP module ([LocalSealed]) every row is shown disabled, like the legacy lock cover.
 */

/** True inside a JamesDSP module that PVB seals while it processes (rows disabled, settings kept). */
val LocalSealed = compositionLocalOf { false }

/** A JamesDSP namespace that also reloads when files are replaced on disk (presets, revert, imports). */
@Composable
fun rememberDspFile(name: String, host: RnAdvancedActivity): RnPrefsFile {
    val file = rememberPrefsFile(name, dsp = true)
    val tick = host.presetTick
    LaunchedEffect(tick) { if (tick > 0) file.reload() }
    return file
}

/** "%.{precision}f unit" (the legacy slider label, with a space before the unit). */
fun valueLabel(v: Float, precision: Int, unit: String): String =
    String.format(Locale.ROOT, "%.${precision}f", v) + if (unit.isEmpty()) "" else " $unit"

@Composable
fun PrefSwitch(
    file: RnPrefsFile, key: String, title: String, default: Boolean,
    line: String? = null, enabled: Boolean = true, onChange: ((Boolean) -> Unit)? = null,
) {
    RnSwitchRow(title, file.bool(key, default), { on -> onChange?.invoke(on) ?: file.put(key, on) },
        line = line, enabled = enabled && !LocalSealed.current)
}

@Composable
fun PrefSlider(
    file: RnPrefsFile, key: String, title: String, default: Float,
    range: ClosedFloatingPointRange<Float>, step: Float, unit: String, precision: Int,
    line: String? = null, enabled: Boolean = true, strictStep: Boolean = false,
    label: ((Float) -> String)? = null,
) {
    RnValueSlider(
        title = title, value = file.float(key, default), range = range, step = step,
        valueText = label ?: { valueLabel(it, precision, unit) },
        onChange = { file.put(key, it) },
        line = line, default = default.takeIf { it in range }, enabled = enabled && !LocalSealed.current,
        suffix = unit.ifEmpty { null }, decimals = precision, strictStep = strictStep,
    )
}

/** A ListPreference: [entries] and [values] are string-array resources. */
@Composable
fun PrefChoice(
    file: RnPrefsFile, key: String, title: String, default: String, entries: Int, values: Int,
    line: String? = null, enabled: Boolean = true,
) {
    val labels = stringArrayResource(entries)
    val keys = stringArrayResource(values)
    RnChoiceRow(title, keys.mapIndexed { i, v -> RnChoice(v, labels.getOrElse(i) { v }) }, file.string(key, default),
        { file.put(key, it) }, line = line, enabled = enabled && !LocalSealed.current)
}

/** How PVB treats a JamesDSP module while it processes (JdspChain.Policy as shown on the screen). */
enum class Seal { NONE, INFO, LOCKED }

/**
 * One JamesDSP module: the band, its switch (bold, with the module icon when "show icons" is on) or, for the output
 * control, a plain title; the seal note; then its rows while it is on.
 */
@Composable
fun DspModule(
    title: String, icon: Int, showIcons: Boolean, file: RnPrefsFile, enableKey: String?,
    seal: Seal, note: String?, onNote: (() -> Unit)? = null, content: @Composable () -> Unit,
) {
    RnBand()
    val locked = seal == Seal.LOCKED
    val painter = if (showIcons) painterResource(icon) else null
    val on = enableKey == null || file.bool(enableKey, false)
    if (enableKey != null) RnSwitchRow(title, on, { file.put(enableKey, it) }, enabled = !locked, bold = true, icon = painter)
    else RnGroupTitle(title, painter, enabled = !locked)
    if (seal != Seal.NONE && note != null) RnNote(note, warning = locked, onClick = onNote)
    if (on) CompositionLocalProvider(LocalSealed provides locked) { content() }
}

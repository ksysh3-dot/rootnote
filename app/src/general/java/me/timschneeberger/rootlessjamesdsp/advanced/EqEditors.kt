package me.timschneeberger.rootlessjamesdsp.advanced

import android.annotation.SuppressLint
import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.model.GraphicEqNodeList
import me.timschneeberger.rootlessjamesdsp.model.ParametricEqBandList
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnButtonRow
import me.timschneeberger.rootlessjamesdsp.ui.RnDialogTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnOutlineButton
import me.timschneeberger.rootlessjamesdsp.ui.RnPrefsFile
import me.timschneeberger.rootlessjamesdsp.view.BaseEqualizerSurface
import me.timschneeberger.rootlessjamesdsp.view.CompanderSurface
import me.timschneeberger.rootlessjamesdsp.view.EqualizerSurface
import me.timschneeberger.rootlessjamesdsp.view.GraphicEqualizerSurface
import me.timschneeberger.rootlessjamesdsp.view.ParametricEqSurface

/*
 * The JamesDSP curve editors that were preference dialogs (EqualizerDialogFragment, CompanderDialogFragment), and the
 * curve previews of the EQ, compander, GEQ and PEQ rows. The drawing surfaces stay the legacy Views (AndroidView):
 * dragging on them writes the curve at once (commit), cancel or back puts the starting curve back, OK keeps it.
 * The GEQ and PEQ editors stay their own screens.
 */

/** The 15 levels of an "f1;…;f15;g1;…;g15" string (missing ones are 0). */
fun eqLevels(value: String, bands: Int): DoubleArray = value.split(";").drop(bands).dropLastWhile(String::isEmpty)
    .map { it.toDoubleOrNull() ?: 0.0 }.toDoubleArray().copyOf(bands)

/** FIR for type 0, else IIR of order 4/6/8/10/12 (the legacy filter-type list). */
fun applyEqType(view: EqualizerSurface, type: Int) {
    view.mode = if (type == 0) EqualizerSurface.Mode.Fir else EqualizerSurface.Mode.Iir
    view.iirOrder = when (type) { 1 -> 4; 2 -> 6; 3 -> 8; 4 -> 10; else -> 12 }
}

/** A curve preview under a row: tapping it does what the row does. */
@Composable
fun CurvePreview(label: String, onClick: () -> Unit, view: @Composable (Modifier) -> Unit) {
    Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 12.dp).height(112.dp)) {
        view(Modifier.matchParentSize())
        // a transparent cover takes the tap (the surface is a View and does not click)
        Box(Modifier.matchParentSize().clickable(role = Role.Button, onClick = onClick).semantics { contentDescription = label })
    }
}

@Composable
fun EqPreview(value: String, type: Int, modifier: Modifier) {
    AndroidView(factory = { EqualizerSurface(it, null) }, modifier = modifier, update = { v ->
        applyEqType(v, type)
        eqLevels(value, 15).forEachIndexed(v::setBand)
    })
}

@Composable
fun CompanderPreview(value: String, modifier: Modifier) {
    AndroidView(factory = { CompanderSurface(it, null) }, modifier = modifier, update = { v ->
        eqLevels(value, 7).forEachIndexed(v::setBand)
    })
}

@Composable
fun GeqPreview(value: String, modifier: Modifier) {
    AndroidView(factory = { GraphicEqualizerSurface(it, null) }, modifier = modifier, update = { v ->
        v.setNodes(GraphicEqNodeList().apply { deserialize(value) })
    })
}

@Composable
fun PeqPreview(value: String, preampDb: Float, modifier: Modifier) {
    AndroidView(factory = { ParametricEqSurface(it, null) }, modifier = modifier, update = { v ->
        v.setBands(ParametricEqBandList().apply { deserialize(value) }, preampDb.toDouble())
    })
}

/**
 * The 15-band equalizer editor: the surface with its knobs, the preset chips, cancel / OK. [eqType] is the filter
 * type the surface draws (dsp_equalizer eq_filter_type).
 */
@Composable
fun EqEditorDialog(host: RnAdvancedActivity, file: RnPrefsFile, key: String, default: String, eqType: Int, onClose: () -> Unit) {
    val names = stringArrayResource(R.array.equalizer_preset_modes)
    val values = stringArrayResource(R.array.equalizer_preset_values)
    CurveEditorDialog(
        host = host, file = file, key = key, default = default, bands = 15, scale = EqualizerSurface.SCALE,
        title = stringResource(R.string.rn_adv_eq_edit), presets = names.zip(values),
        snapBelow = -0.05, onClose = onClose,
        factory = { ctx -> EqualizerSurface(ctx, null).also { applyEqType(it, eqType) } },
    )
}

/** The compander's 7-band response editor. */
@Composable
fun CompanderEditorDialog(host: RnAdvancedActivity, file: RnPrefsFile, key: String, default: String, onClose: () -> Unit) {
    CurveEditorDialog(
        host = host, file = file, key = key, default = default, bands = 7, scale = CompanderSurface.SCALE,
        title = stringResource(R.string.rn_adv_compander_edit), presets = emptyList(),
        snapBelow = -0.02, onClose = onClose,
        factory = { ctx -> CompanderSurface(ctx, null) },
    )
}

@SuppressLint("ClickableViewAccessibility")
@Composable
private fun CurveEditorDialog(
    host: RnAdvancedActivity, file: RnPrefsFile, key: String, default: String, bands: Int, scale: DoubleArray,
    title: String, presets: List<Pair<String, String>>, snapBelow: Double, onClose: () -> Unit,
    factory: (android.content.Context) -> BaseEqualizerSurface,
) {
    val c = LocalRn.current
    val original = remember { file.prefs.getString(key, default) ?: default }
    val levels = remember { eqLevels(original, bands) }
    val holder = remember { arrayOfNulls<BaseEqualizerSurface>(1) }
    // every change is written at once (the engine follows while dragging), like the legacy dialogs
    fun write(value: String) = file.prefs.edit().putString(key, value).commit()
    fun writeCurrent() = write((scale + levels).joinToString(";"))
    fun setBand(i: Int, gain: Double) {
        levels[i] = gain
        holder[0]?.setBand(i, gain)
    }
    fun cancel() { write(original); onClose() }
    // a preset loaded meanwhile replaces the file: the editor closes, like the legacy dialogs
    val startTick = remember { host.presetTick }
    LaunchedEffect(host.presetTick) { if (host.presetTick != startTick) onClose() }

    Dialog(onDismissRequest = ::cancel, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(
            Modifier.padding(horizontal = 16.dp).fillMaxWidth().background(c.bg, RoundedCornerShape(28.dp))
                .padding(vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(Modifier.padding(horizontal = 24.dp)) { RnDialogTitle(title) }
            Text(stringResource(R.string.rn_adv_editor_hint), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
                modifier = Modifier.padding(horizontal = 24.dp))
            AndroidView(
                factory = { ctx ->
                    factory(ctx).also { view ->
                        holder[0] = view
                        view.areKnobsVisible = true
                        levels.forEachIndexed(view::setBand)
                        view.setOnTouchListener { v, event ->
                            if (event.actionMasked == MotionEvent.ACTION_DOWN) v.parent?.requestDisallowInterceptTouchEvent(true)
                            val band = view.findClosest(event.x)
                            var level = event.y / v.height * (view.minDb - view.maxDb) - view.minDb
                            level = when {
                                level > snapBelow && level < 0.0 -> 0.0
                                level > view.maxDb -> view.maxDb
                                level < view.minDb -> view.minDb
                                else -> level
                            }
                            setBand(band, level)
                            writeCurrent()
                            true
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().height(240.dp).padding(horizontal = 16.dp),
            )
            if (presets.isNotEmpty()) {
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for ((name, value) in presets) PresetChip(name) {
                        value.split(";").dropLastWhile(String::isEmpty).map { it.toDoubleOrNull() ?: 0.0 }
                            .forEachIndexed { i, g -> if (i < bands) setBand(i, g) }
                        writeCurrent()
                    }
                }
            }
            Box(Modifier.padding(horizontal = 8.dp)) {
                RnButtonRow {
                    RnOutlineButton(stringResource(android.R.string.cancel), Modifier.weight(1f), onClick = ::cancel)
                    RnFilledButton(stringResource(android.R.string.ok), Modifier.weight(1f)) { writeCurrent(); onClose() }
                }
            }
        }
    }
}

@Composable
private fun PresetChip(label: String, onClick: () -> Unit) {
    val c = LocalRn.current
    Box(Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onClick), contentAlignment = Alignment.Center) {
        Text(label, color = c.textPrimary, fontSize = 14.sp, lineHeight = 20.sp,
            modifier = Modifier.border(1.dp, c.chipBorder, RoundedCornerShape(50)).padding(horizontal = 14.dp, vertical = 7.dp))
    }
}

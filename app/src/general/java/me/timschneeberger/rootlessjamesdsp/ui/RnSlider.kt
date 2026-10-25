package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.res.stringResource
import me.timschneeberger.rootlessjamesdsp.R
import java.util.Locale
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.roundToInt

/**
 * A slider row (docs/DESIGN.md 5 슬라이더 카드, written like the developer mode's SliderCard):
 * name and value (16/22 Bold; the value in the accent colour when it is not the default), an optional line (13/18),
 * then ± buttons (44 dp in 48 dp targets) around the track (4 dp, fill up to the thumb, a dot under the default,
 * a 26 dp white thumb with a shadow that grows while held). Drag or tap the track; one haptic tick per step; TalkBack
 * reads name and value and can set it. Tapping the name opens [onEdit] (the "값 편집" input), when given.
 *
 * The value is committed with [onChange] when the finger lifts (or on every step with [continuous]); the ± buttons
 * commit at once. [valueText] formats a value for the row and for TalkBack.
 */
@Composable
fun RnSliderRow(
    title: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    step: Float,
    valueText: (Float) -> String,
    onChange: (Float) -> Unit,
    line: String? = null,
    default: Float? = null,
    enabled: Boolean = true,
    continuous: Boolean = false,
    onEdit: (() -> Unit)? = null,
) {
    val c = LocalRn.current
    var local by remember { mutableFloatStateOf(value) }
    var dragging by remember { mutableStateOf(false) }
    LaunchedEffect(value) { if (!dragging) local = value }
    fun snap(v: Float): Float {
        val s = if (step > 0f) range.start + ((v - range.start) / step).roundToInt() * step else v
        return s.coerceIn(range.start, range.endInclusive)
    }
    val shown = if (dragging) local else value
    val nonDefault = default != null && abs(shown - default) > step / 2f
    Column(Modifier.fillMaxWidth().alpha(if (enabled) 1f else 0.4f).padding(horizontal = 16.dp, vertical = 8.dp)) {
        Row(Modifier.fillMaxWidth().heightIn(min = 40.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.weight(1f).then(if (onEdit != null) Modifier.clickable(enabled = enabled, role = Role.Button,
                    onClickLabel = stringResource(R.string.slider_dialog_title), onClick = onEdit) else Modifier)
                    .padding(vertical = 6.dp),
            ) {
                Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            }
            Text(valueText(shown), color = if (nonDefault) c.accentText else c.textPrimary, fontSize = 16.sp,
                lineHeight = 22.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.End, modifier = Modifier.padding(start = 8.dp))
        }
        if (!line.isNullOrEmpty()) Text(line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            RnStepButton(false, stringResource(R.string.rn_minus, title), enabled && value > range.start + step / 2f) {
                onChange(snap(value - step))
            }
            RnTrack(
                value = shown, range = range, default = default, enabled = enabled, name = title, valueText = valueText(shown),
                snap = ::snap, tick = maxOf(step, (range.endInclusive - range.start) / HAPTIC_TICKS),
                onDrag = { v, done ->
                    dragging = !done
                    local = v
                    if (continuous || done) onChange(v)
                },
                modifier = Modifier.weight(1f).padding(horizontal = 4.dp),
            )
            RnStepButton(true, stringResource(R.string.rn_plus, title), enabled && value < range.endInclusive - step / 2f) {
                onChange(snap(value + step))
            }
        }
    }
}

/** 44 dp round button with a minus or plus inside a 48 dp target (DevMode StepButton). */
@Composable
fun RnStepButton(plus: Boolean, label: String, enabled: Boolean, onClick: () -> Unit) {
    val c = LocalRn.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale = pressScale(interaction, enabled, 0.94f)
    Box(
        Modifier.size(48.dp)
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.size(44.dp).graphicsLayer { scaleX = scale; scaleY = scale }
                .background(if (pressed) c.press else c.bg, CircleShape).border(1.dp, c.chipBorder, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(18.dp)) {
                val col = if (enabled) c.textPrimary else c.chevron
                val y = size.height / 2f
                drawLine(col, Offset(2f, y), Offset(size.width - 2f, y), strokeWidth = 2.dp.toPx(), cap = StrokeCap.Round)
                if (plus) drawLine(col, Offset(size.width / 2f, 2f), Offset(size.width / 2f, size.height - 2f),
                    strokeWidth = 2.dp.toPx(), cap = StrokeCap.Round)
            }
        }
    }
}

/** The track: [onDrag] (value, finished) while dragging, tapping, or set by TalkBack. */
@Composable
private fun RnTrack(
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    default: Float?,
    enabled: Boolean,
    name: String,
    valueText: String,
    snap: (Float) -> Float,
    tick: Float,
    onDrag: (Float, Boolean) -> Unit,
    modifier: Modifier,
) {
    val c = LocalRn.current
    val haptic = LocalHapticFeedback.current
    val thumbPx = with(LocalDensity.current) { 26.dp.toPx() }
    var widthPx by remember { mutableFloatStateOf(0f) }
    var dragX by remember { mutableFloatStateOf(0f) }
    var held by remember { mutableStateOf(false) }
    var lastIndex by remember { mutableIntStateOf(0) }
    val rangeNow by rememberUpdatedState(range)
    val onDragNow by rememberUpdatedState(onDrag)
    val span = (range.endInclusive - range.start).takeIf { it > 0f } ?: 1f
    fun frac(v: Float) = ((v - range.start) / span).coerceIn(0f, 1f)
    fun valueAt(x: Float): Float {
        val usable = (widthPx - thumbPx).coerceAtLeast(1f)
        val f = ((x - thumbPx / 2f) / usable).coerceIn(0f, 1f)
        val r = rangeNow
        return snap(r.start + f * (r.endInclusive - r.start))
    }
    fun emit(v: Float, done: Boolean) {
        // one tick per step, but at most about HAPTIC_TICKS per sweep (a fine slider would buzz otherwise)
        val idx = if (tick > 0f) floor((v - rangeNow.start) / tick + 1e-4f).toInt() else ((v - rangeNow.start) * 1000f).roundToInt()
        if (idx != lastIndex) {
            lastIndex = idx
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        }
        onDragNow(v, done)
    }
    val fraction by animateFloatAsState(frac(value), rnMotion(if (held) tween(0) else rnSettle()), label = "thumbX")
    val thumbScale by animateFloatAsState(if (held) 1.15f else 1f,
        rnMotion(if (held) tween(120, easing = RnEase) else rnRelease()), label = "thumbS")
    val dragState = rememberDraggableState { d -> dragX += d; emit(valueAt(dragX), false) }
    Box(
        modifier.height(48.dp)
            .onSizeChanged { widthPx = it.width.toFloat() }
            .semantics(mergeDescendants = true) {
                contentDescription = name
                stateDescription = valueText
                progressBarRangeInfo = ProgressBarRangeInfo(value, range)
                if (enabled) setProgress { target -> onDragNow(snap(target), true); true }
            }
            .then(if (!enabled) Modifier else Modifier
                .draggable(
                    state = dragState, orientation = Orientation.Horizontal,
                    onDragStarted = { start -> held = true; dragX = start.x; emit(valueAt(start.x), false) },
                    onDragStopped = { held = false; onDragNow(valueAt(dragX), true) },
                )
                .pointerInput(Unit) {
                    detectTapGestures(
                        onPress = { held = true; tryAwaitRelease(); held = false },
                        onTap = { pos -> emit(valueAt(pos.x), true) },
                    )
                }),
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = thumbPx / 2f
            val y = size.height / 2f
            val stroke = 4.dp.toPx()
            val start = r
            val end = size.width - r
            val x = start + (end - start) * fraction
            drawLine(c.sliderInactive, Offset(start, y), Offset(end, y), strokeWidth = stroke, cap = StrokeCap.Round)
            drawLine(c.fill, Offset(start, y), Offset(x, y), strokeWidth = stroke, cap = StrokeCap.Round)
            if (default != null) drawCircle(c.textSecondary, radius = 2.5.dp.toPx(),
                center = Offset(start + (end - start) * frac(default.coerceIn(range.start, range.endInclusive)), y + 12.dp.toPx()))
        }
        Box(
            Modifier.align(Alignment.CenterStart)
                .offset { IntOffset(((widthPx - thumbPx).coerceAtLeast(0f) * fraction).roundToInt(), 0) }
                .size(26.dp)
                .graphicsLayer { scaleX = thumbScale; scaleY = thumbScale }
                .shadow(3.dp, CircleShape)
                .background(c.thumb, CircleShape)
        )
    }
}

/** At most this many haptic ticks across a slider's whole range. */
private const val HAPTIC_TICKS = 24f

/**
 * The legacy slider's "값 편집" input: a number in [range]. With [strictStep] it must also be a multiple of [step]
 * counted from the range start (the legacy sliders with a set increment); otherwise any value in range is taken.
 */
@Composable
fun RnNumberInput(
    title: String, value: Float, range: ClosedFloatingPointRange<Float>, step: Float, suffix: String?,
    onDone: (Float) -> Unit, onDismiss: () -> Unit, decimals: Int = if (step % 1f == 0f) 0 else 2,
    strictStep: Boolean = step >= 1f && step % 1f == 0f,
) {
    val formatError = stringResource(R.string.slider_dialog_format_error)
    val stepError = stringResource(R.string.slider_dialog_step_error, step.toInt().coerceAtLeast(1))
    fun onStep(v: Float): Boolean {
        if (!strictStep || step <= 0f) return true
        val n = (v - range.start) / step
        return abs(n - Math.round(n)) < 1e-3f
    }
    RnInputDialog(
        title = stringResource(R.string.slider_dialog_title), hint = title,
        initial = if (decimals == 0) Math.round(value).toString() else String.format(Locale.ROOT, "%.${decimals}f", value),
        suffix = suffix, number = true,
        validate = { t ->
            val v = t.replace(',', '.').toFloatOrNull()
            when {
                v == null || v < range.start || v > range.endInclusive -> formatError
                !onStep(v) -> stepError
                else -> null
            }
        },
        onDone = { t -> t.replace(',', '.').toFloatOrNull()?.let(onDone) },
        onDismiss = onDismiss,
    )
}

/** [RnSliderRow] whose title opens [RnNumberInput] (the legacy MaterialSeekbarPreference: slider plus "값 편집"). */
@Composable
fun RnValueSlider(
    title: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    step: Float,
    valueText: (Float) -> String,
    onChange: (Float) -> Unit,
    line: String? = null,
    default: Float? = null,
    enabled: Boolean = true,
    suffix: String? = null,
    decimals: Int = if (step % 1f == 0f) 0 else 2,
    strictStep: Boolean = false,
) {
    var editing by remember { mutableStateOf(false) }
    RnSliderRow(title, value.coerceIn(range.start, range.endInclusive), range, step, valueText, onChange, line, default,
        enabled, onEdit = { editing = true })
    if (editing) RnNumberInput(title, value, range, step, suffix, onDone = { onChange(it); editing = false },
        onDismiss = { editing = false }, decimals = decimals, strictStep = strictStep)
}

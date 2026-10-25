package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.disabled
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
            RnSliderTrack(
                value = shown, range = range, step = step, enabled = enabled, name = title, valueText = valueText(shown),
                snap = ::snap, default = default,
                colors = RnSliderColors(c.fill, c.sliderInactive, c.thumb, c.textSecondary),
                onChange = { v -> dragging = true; local = v; if (continuous) onChange(v) },
                onFinish = { v -> local = v; dragging = false; onChange(v) },
                modifier = Modifier.weight(1f).padding(horizontal = 4.dp),
            )
            RnStepButton(true, stringResource(R.string.rn_plus, title), enabled && value < range.endInclusive - step / 2f) {
                onChange(snap(value + step))
            }
        }
    }
}

/** 44 dp round button with a minus or plus inside a 48 dp target, in the page's colours. */
@Composable
fun RnStepButton(plus: Boolean, label: String, enabled: Boolean, onClick: () -> Unit) {
    val c = LocalRn.current
    RnStepButton(plus, label, enabled, c.bg, c.press, c.chipBorder, c.textPrimary, c.chevron, onClick)
}

/** The step button for any palette: the one implementation (settings, developer mode). */
@Composable
fun RnStepButton(
    plus: Boolean, label: String, enabled: Boolean,
    bg: Color, press: Color, border: Color, ink: Color, inkOff: Color, onClick: () -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale = pressScale(interaction, enabled, 0.94f)
    val face = rnPressTint(pressed && enabled, bg, press)
    Box(
        Modifier.size(48.dp)
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.size(44.dp).graphicsLayer { scaleX = scale.value; scaleY = scale.value }
                .background(face, CircleShape).border(1.dp, border, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(18.dp)) {
                val col = if (enabled) ink else inkOff
                val y = size.height / 2f
                drawLine(col, Offset(2f, y), Offset(size.width - 2f, y), strokeWidth = 2.dp.toPx(), cap = StrokeCap.Round)
                if (plus) drawLine(col, Offset(size.width / 2f, 2f), Offset(size.width / 2f, size.height - 2f),
                    strokeWidth = 2.dp.toPx(), cap = StrokeCap.Round)
            }
        }
    }
}

/** The colours of a slider track: the filled part, the rest, the thumb and the dot under the default value. */
class RnSliderColors(val fill: Color, val inactive: Color, val thumb: Color, val dot: Color)

/**
 * The one slider track of the general build (the settings rows, the home screen and the developer mode all use it).
 * What the finger holds is the finger: while it drags, the thumb sits exactly under it (the value only snaps to its
 * step), and once it lets go the thumb settles on the value with a spring that carries the speed over
 * ([RnMotion.Apple.settle]). The thumb grows to 1.15x on a press (Seed d3) and returns with [RnMotion.Apple.thumb].
 * The thumb's position, the track and the scale are read while drawing only, so a drag recomposes nothing but the
 * value text. One haptic tick per step, at most [HAPTIC_TICKS] across the whole range.
 *
 * [onChange] is called whenever the snapped value under the finger changes (drag, tap or TalkBack), [onFinish] once
 * when the finger lifts, a tap lands or TalkBack sets a value. [onStart] runs before a drag or tap starts changing it.
 * [paintTrack] replaces the two default lines (developer mode paints its recommended and experimental ranges).
 */
@Composable
fun RnSliderTrack(
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    step: Float,
    enabled: Boolean,
    name: String,
    valueText: String,
    snap: (Float) -> Float,
    colors: RnSliderColors,
    onChange: (Float) -> Unit,
    modifier: Modifier = Modifier,
    onFinish: (Float) -> Unit = {},
    onStart: () -> Unit = {},
    default: Float? = null,
    thumbSize: Dp = 26.dp,
    thumbShadow: Dp = 3.dp,
    stroke: Dp = 4.dp,
    ring: Color? = null,
    paintTrack: (DrawScope.(start: Float, end: Float, px: (Float) -> Float, thumbX: Float) -> Unit)? = null,
) {
    val haptic = LocalHapticFeedback.current
    val reduce = LocalRnReduceMotion.current
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    val thumbPx = with(LocalDensity.current) { thumbSize.toPx() }
    var widthPx by remember { mutableFloatStateOf(0f) }
    var dragX by remember { mutableFloatStateOf(0f) }
    var pressing by remember { mutableStateOf(false) }
    var dragging by remember { mutableStateOf(false) }
    val held = pressing || dragging
    var lastValue by remember { mutableFloatStateOf(value) }
    var lastIndex by remember { mutableIntStateOf(Int.MIN_VALUE) }
    LaunchedEffect(value) { lastValue = value }
    val rangeNow by rememberUpdatedState(range)
    val stepNow by rememberUpdatedState(step)
    val snapNow by rememberUpdatedState(snap)
    val rtlNow by rememberUpdatedState(rtl)
    val onChangeNow by rememberUpdatedState(onChange)
    val onFinishNow by rememberUpdatedState(onFinish)
    val onStartNow by rememberUpdatedState(onStart)
    val span = (range.endInclusive - range.start).takeIf { it > 0f } ?: 1f
    fun frac(v: Float) = ((v - range.start) / span).coerceIn(0f, 1f)
    fun fracAt(x: Float): Float {
        val usable = (widthPx - thumbPx).coerceAtLeast(1f)
        val f = ((x - thumbPx / 2f) / usable).coerceIn(0f, 1f)
        return if (rtlNow) 1f - f else f
    }
    fun valueAt(x: Float): Float {
        val r = rangeNow
        return snapNow(r.start + fracAt(x) * (r.endInclusive - r.start)).coerceIn(r.start, r.endInclusive)
    }

    // the thumb: the finger while held, otherwise a spring that follows the committed value
    val settled = remember { Animatable(frac(value)) }
    var finger by remember { mutableFloatStateOf(frac(value)) }
    LaunchedEffect(value, held, reduce, range.start, range.endInclusive) {
        if (!held) {
            if (reduce) settled.snapTo(frac(value)) else settled.animateTo(frac(value), RnMotion.Apple.settle())
        }
    }
    val thumbScale = animateFloatAsState(
        if (held && enabled) 1.15f else 1f,
        rn(if (held) RnMotion.Seed.pressIn() else RnMotion.Apple.thumb()), label = "thumbScale",
    )
    fun shownFrac() = if (held) finger else settled.value
    fun grid() = if (stepNow > 0f) stepNow * 0.01f else span * 1e-6f

    fun emit(v: Float) {
        if (abs(v - lastValue) <= grid()) return
        lastValue = v
        // one tick per step, but at most about HAPTIC_TICKS per sweep (a fine slider would buzz otherwise)
        val tick = maxOf(stepNow, span / HAPTIC_TICKS)
        val idx = floor((v - rangeNow.start) / tick + 1e-4f).toInt()
        if (idx != lastIndex) {
            lastIndex = idx
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        }
        onChangeNow(v)
    }
    val dragState = rememberDraggableState { d -> dragX += d; finger = fracAt(dragX); emit(valueAt(dragX)) }
    val steps = if (step > 0f) ((span / step).roundToInt() - 1).coerceAtLeast(0) else 0
    Box(
        modifier.height(48.dp)
            .onSizeChanged { widthPx = it.width.toFloat() }
            .semantics(mergeDescendants = true) {
                contentDescription = name
                stateDescription = valueText
                progressBarRangeInfo = ProgressBarRangeInfo(value, range, steps)
                if (enabled) setProgress { target ->
                    val v = snapNow(target).coerceIn(rangeNow.start, rangeNow.endInclusive)
                    onStartNow(); emit(v); onFinishNow(v); true
                } else disabled()
            }
            .then(if (!enabled) Modifier else Modifier
                .draggable(
                    state = dragState, orientation = Orientation.Horizontal,
                    onDragStarted = { start ->
                        dragX = start.x
                        finger = fracAt(start.x)
                        dragging = true
                        onStartNow()
                        emit(valueAt(start.x))
                    },
                    onDragStopped = {
                        // hand the thumb to the spring from where the finger left it
                        settled.snapTo(finger)
                        onFinishNow(valueAt(dragX))
                        dragging = false
                    },
                )
                .pointerInput(Unit) {
                    detectTapGestures(
                        onPress = { finger = settled.value; pressing = true; tryAwaitRelease(); pressing = false },
                        onTap = { pos -> onStartNow(); val v = valueAt(pos.x); emit(v); onFinishNow(v) },
                    )
                }),
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = thumbPx / 2f
            val y = size.height / 2f
            val start = r
            val end = size.width - r
            val sw = stroke.toPx()
            fun px(v: Float): Float {
                val f = ((v - range.start) / span).coerceIn(0f, 1f)
                return if (rtl) end - (end - start) * f else start + (end - start) * f
            }
            val f = shownFrac()
            val thumbX = if (rtl) end - (end - start) * f else start + (end - start) * f
            if (paintTrack != null) paintTrack(start, end, ::px, thumbX)
            else {
                drawLine(colors.inactive, Offset(start, y), Offset(end, y), strokeWidth = sw, cap = StrokeCap.Round)
                drawLine(colors.fill, Offset(if (rtl) end else start, y), Offset(thumbX, y), strokeWidth = sw, cap = StrokeCap.Round)
            }
            if (default != null) drawCircle(colors.dot, radius = 2.5.dp.toPx(),
                center = Offset(px(default.coerceIn(range.start, range.endInclusive)), y + 12.dp.toPx()))
        }
        Box(
            Modifier.align(Alignment.CenterStart)
                .size(thumbSize)
                .graphicsLayer {
                    val s = thumbScale.value
                    scaleX = s; scaleY = s
                    translationX = (widthPx - thumbPx).coerceAtLeast(0f) * shownFrac() * (if (rtl) -1f else 1f)
                }
                .shadow(thumbShadow, CircleShape)
                .background(colors.thumb, CircleShape)
                .then(if (ring != null) Modifier.border(if (held) 3.dp else 2.dp, ring, CircleShape) else Modifier)
        )
    }
}

/** At most this many haptic ticks across a slider's whole range. */
internal const val HAPTIC_TICKS = 24f

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

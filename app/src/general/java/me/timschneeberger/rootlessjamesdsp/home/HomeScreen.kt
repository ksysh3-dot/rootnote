package me.timschneeberger.rootlessjamesdsp.home

import android.content.res.Configuration
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.Crossfade
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
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
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import kotlin.math.roundToInt

/*
 * Home screen of the general build (Rootnote, approved design "E안", palette "심해 틸").
 *
 * One column: top bar, master row (headline + device + switch), strength slider with preset chips, volume link row,
 * and the two navigation rows. No fixed heights on anything holding text (rows only have minimum heights), and the
 * column scrolls, so font scaling up to 200 % grows the rows instead of clipping them.
 *
 * Motion follows the design: iOS-like easing for the switches (350 ms thumb, 300 ms track), chips scale to 0.94 on
 * press and spring back with a small overshoot, the slider thumb grows 1.18x while held, dimming takes 300 ms, the
 * headline fades out completely before the new one fades in. With the system animator scale at 0 every animation
 * snaps (the activity passes reduceMotion; Compose also scales its own clocks by that setting).
 */

/** Screen state, built by HomeActivity from the PVB settings, the service state and the published volume. */
@Immutable
data class HomeUiState(
    val headline: HomeLogic.Headline,
    val masterOn: Boolean,
    /** Profile name of a measured phone, or null (unmeasured: conservative settings). */
    val measuredDeviceName: String?,
    val level: Int,
    val levelMax: Int,
    val chip: HomeLogic.Chip,
    val linkOn: Boolean,
    val linkLine: HomeLogic.LinkLine,
)

class HomeActions(
    val onMaster: (Boolean) -> Unit,
    val onLevel: (Int) -> Unit,
    val onChip: (HomeLogic.Chip) -> Unit,
    val onLink: (Boolean) -> Unit,
    val onAdvanced: () -> Unit,
    val onAbout: () -> Unit,
)

/** The "심해 틸" palette (res/values[-night]/colors_rootnote.xml of the general flavor). */
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
)

@Composable
fun rootnotePalette(): RootnotePalette = RootnotePalette(
    bg = colorResource(R.color.rn_bg),
    band = colorResource(R.color.rn_band),
    press = colorResource(R.color.rn_press),
    divider = colorResource(R.color.rn_divider),
    textPrimary = colorResource(R.color.rn_text_primary),
    textSecondary = colorResource(R.color.rn_text_secondary),
    chevron = colorResource(R.color.rn_chevron),
    fill = colorResource(R.color.rn_fill),
    accentText = colorResource(R.color.rn_accent_text),
    chipBg = colorResource(R.color.rn_chip_bg),
    chipBorder = colorResource(R.color.rn_chip_border),
    chipText = colorResource(R.color.rn_chip_text),
    chipSelectedBg = colorResource(R.color.rn_chip_selected_bg),
    chipSelectedBorder = colorResource(R.color.rn_chip_selected_border),
    chipSelectedText = colorResource(R.color.rn_chip_selected_text),
    switchOff = colorResource(R.color.rn_switch_off),
    sliderInactive = colorResource(R.color.rn_slider_inactive),
    thumb = colorResource(R.color.rn_thumb),
)

private val LocalPalette = staticCompositionLocalOf<RootnotePalette> { error("RootnotePalette not provided") }
private val LocalReduceMotion = staticCompositionLocalOf { false }

/** cubic-bezier(0.32, 0.72, 0, 1): switches, dimming, colour changes. */
private val IosEase = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)
/** cubic-bezier(0.34, 1.56, 0.64, 1): the chip's release with a slight overshoot. */
private val OvershootEase = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)

/** Readability rule for changing text: the old text fades out completely (150 ms), then the new one fades in. */
private fun sequentialFade(): ContentTransform = ContentTransform(
    targetContentEnter = fadeIn(tween(150, delayMillis = 150, easing = LinearEasing)),
    initialContentExit = fadeOut(tween(150, easing = LinearEasing)),
    sizeTransform = SizeTransform(clip = false),
)

/** [spec], or an instant change when the system animations are off. */
@Composable
private fun <T> motion(spec: FiniteAnimationSpec<T>): FiniteAnimationSpec<T> =
    if (LocalReduceMotion.current) snap() else spec

@Composable
fun HomeScreen(state: HomeUiState, actions: HomeActions, reduceMotion: Boolean = false) {
    val palette = rootnotePalette()
    val dark = (androidx.compose.ui.platform.LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    val scheme = if (dark) darkColorScheme(primary = palette.fill, background = palette.bg, surface = palette.bg,
        onBackground = palette.textPrimary, onSurface = palette.textPrimary)
    else lightColorScheme(primary = palette.fill, background = palette.bg, surface = palette.bg,
        onBackground = palette.textPrimary, onSurface = palette.textPrimary)
    CompositionLocalProvider(LocalPalette provides palette, LocalReduceMotion provides reduceMotion) {
        MaterialTheme(colorScheme = scheme) {
            HomeContent(state, actions)
        }
    }
}

@Composable
private fun HomeContent(state: HomeUiState, actions: HomeActions) {
    val c = LocalPalette.current
    Column(
        Modifier
            .fillMaxSize()
            .background(c.bg)
            .verticalScroll(rememberScrollState())
    ) {
        TopBar()
        MasterRow(state, actions)
        Band()

        // Everything that only matters while the bass is filled: dimmed to 40 % and disabled when off.
        val dim by animateFloatAsState(
            targetValue = if (state.masterOn) 1f else 0.4f,
            animationSpec = motion(tween(300, easing = IosEase)),
            label = "dim",
        )
        Column(Modifier.alpha(dim)) {
            StrengthSection(state, actions)
            Box(
                Modifier
                    .padding(start = 16.dp, end = 16.dp, top = 12.dp)
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(c.divider)
            )
            SwitchRow(
                checked = state.linkOn,
                enabled = state.masterOn,
                onCheckedChange = actions.onLink,
                minHeight = 72.dp,
                padding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        stringResource(R.string.home_link_title),
                        color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
                    )
                    Text(linkText(state.linkLine), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
                }
            }
        }

        Band()
        NavRow(stringResource(R.string.home_advanced_title), stringResource(R.string.home_advanced_summary), actions.onAdvanced)
        NavRow(stringResource(R.string.home_about_title), stringResource(R.string.home_about_summary), actions.onAbout)
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun TopBar() {
    val c = LocalPalette.current
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(Modifier.size(10.dp).background(c.fill, CircleShape))
        Text(
            stringResource(R.string.app_brand_name),
            modifier = Modifier.semantics { heading() },
            color = c.textPrimary, fontSize = 20.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp,
            lineHeight = 26.sp,
        )
    }
}

@Composable
private fun MasterRow(state: HomeUiState, actions: HomeActions) {
    val c = LocalPalette.current
    val reduce = LocalReduceMotion.current
    SwitchRow(
        checked = state.masterOn,
        enabled = true,
        onCheckedChange = actions.onMaster,
        minHeight = 96.dp,
        padding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 20.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            // Readability: the old sentence fades out completely, then the new one fades in.
            AnimatedContent(
                targetState = state.headline,
                transitionSpec = {
                    if (reduce) EnterTransition.None togetherWith ExitTransition.None
                    else sequentialFade()
                },
                contentAlignment = Alignment.CenterStart,
                label = "headline",
            ) { headline ->
                Text(
                    headlineText(headline),
                    color = c.textPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold,
                    letterSpacing = (-0.4).sp, lineHeight = 30.sp,
                )
            }
            Text(
                state.measuredDeviceName?.let { stringResource(R.string.home_device_measured, it) }
                    ?: stringResource(R.string.home_device_unmeasured),
                color = c.textSecondary, fontSize = 14.sp, lineHeight = 20.sp,
            )
        }
    }
}

@Composable
private fun headlineText(h: HomeLogic.Headline): String = stringResource(
    when (h) {
        HomeLogic.Headline.FILLING -> R.string.home_headline_filling
        HomeLogic.Headline.CORRECTION_ONLY -> R.string.home_headline_correction_only
        HomeLogic.Headline.ORIGINAL -> R.string.home_headline_original
    }
)

@Composable
private fun linkText(line: HomeLogic.LinkLine): String = when (line) {
    is HomeLogic.LinkLine.Reduced -> stringResource(
        R.string.home_link_reduced, line.volumePct, HomeLogic.signedDb(-line.reductionDb), HomeLogic.signedDb(line.appliedDb),
    )
    is HomeLogic.LinkLine.NoReduction -> stringResource(R.string.home_link_none, line.volumePct)
    HomeLogic.LinkLine.VolumeUnknown -> stringResource(R.string.home_link_unknown)
    HomeLogic.LinkLine.Off -> stringResource(R.string.home_link_off)
}

@Composable
private fun chipLabel(chip: HomeLogic.Chip): String = stringResource(
    when (chip) {
        HomeLogic.Chip.FULLNESS -> R.string.home_chip_fullness
        HomeLogic.Chip.DEEP -> R.string.home_chip_deep
        HomeLogic.Chip.CUSTOM -> R.string.home_chip_custom
    }
)

@Composable
private fun chipHint(chip: HomeLogic.Chip): String = stringResource(
    when (chip) {
        HomeLogic.Chip.FULLNESS -> R.string.home_hint_fullness
        HomeLogic.Chip.DEEP -> R.string.home_hint_deep
        HomeLogic.Chip.CUSTOM -> R.string.home_hint_custom
    }
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun StrengthSection(state: HomeUiState, actions: HomeActions) {
    val c = LocalPalette.current
    val reduce = LocalReduceMotion.current
    val title = stringResource(R.string.home_strength_title)
    val valueText = stringResource(R.string.home_db_value, HomeLogic.levelLabel(state.level))
    Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 8.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                title, modifier = Modifier.weight(1f),
                color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
            )
            // The number changes at once, with a short crossfade.
            Crossfade(targetState = state.level, animationSpec = motion(tween(120)), label = "level") { level ->
                Text(
                    stringResource(R.string.home_db_value, HomeLogic.levelLabel(level)),
                    color = c.accentText, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
                )
            }
        }
        StepSlider(
            value = state.level,
            max = state.levelMax,
            enabled = state.masterOn,
            label = title,
            valueText = valueText,
            onChange = actions.onLevel,
        )
        FlowRow(
            modifier = Modifier.fillMaxWidth().selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            for (chip in HomeLogic.Chip.values()) {
                PresetChip(
                    label = chipLabel(chip),
                    selected = state.chip == chip,
                    enabled = state.masterOn,
                    onClick = { actions.onChip(chip) },
                )
            }
        }
        AnimatedContent(
            targetState = state.chip,
            transitionSpec = {
                if (reduce) EnterTransition.None togetherWith ExitTransition.None
                else sequentialFade()
            },
            contentAlignment = Alignment.TopStart,
            label = "hint",
        ) { chip ->
            Text(
                chipHint(chip),
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                color = c.textSecondary, fontSize = 13.sp, lineHeight = 19.sp,
            )
        }
    }
}

/** A row that toggles a switch: whole row tappable, role switch with its state, 120 ms press tint. */
@Composable
private fun SwitchRow(
    checked: Boolean,
    enabled: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    minHeight: Dp,
    padding: PaddingValues,
    content: @Composable RowScope.() -> Unit,
) {
    val c = LocalPalette.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val bg by animateColorAsState(
        targetValue = if (pressed && enabled) c.press else c.bg,
        animationSpec = motion(tween(120)),
        label = "rowPress",
    )
    Row(
        Modifier
            .fillMaxWidth()
            .background(bg)
            .toggleable(
                value = checked,
                interactionSource = interaction,
                indication = null,
                enabled = enabled,
                role = Role.Switch,
                onValueChange = onCheckedChange,
            )
            .heightIn(min = minHeight)
            .padding(padding),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        content()
        IosSwitch(checked)
    }
}

/** 51 x 31 dp track, 27 dp thumb. Visual only: the row carries the switch semantics. */
@Composable
private fun IosSwitch(checked: Boolean) {
    val c = LocalPalette.current
    val thumbX by animateDpAsState(
        targetValue = if (checked) 22.dp else 2.dp,
        animationSpec = motion(tween(350, easing = IosEase)),
        label = "switchThumb",
    )
    val track by animateColorAsState(
        targetValue = if (checked) c.fill else c.switchOff,
        animationSpec = motion(tween(300, easing = IosEase)),
        label = "switchTrack",
    )
    Box(Modifier.size(width = 51.dp, height = 31.dp).background(track, CircleShape)) {
        Box(
            Modifier
                .offset(x = thumbX, y = 2.dp)
                .size(27.dp)
                .shadow(3.dp, CircleShape)
                .background(c.thumb, CircleShape)
        )
    }
}

/** Pill chip (36 dp, fully rounded) inside a 48 dp touch target; a toggle button with its selected state. */
@Composable
private fun PresetChip(label: String, selected: Boolean, enabled: Boolean, onClick: () -> Unit) {
    val c = LocalPalette.current
    val reduce = LocalReduceMotion.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed && enabled) 0.94f else 1f,
        animationSpec = when {
            reduce -> snap()
            pressed -> tween(120, easing = IosEase)
            else -> tween(350, easing = OvershootEase)
        },
        label = "chipScale",
    )
    val colorSpec = motion(tween<Color>(300, easing = IosEase))
    val bg by animateColorAsState(if (selected) c.chipSelectedBg else c.chipBg, colorSpec, label = "chipBg")
    val border by animateColorAsState(if (selected) c.chipSelectedBorder else c.chipBorder, colorSpec, label = "chipBorder")
    val fg by animateColorAsState(if (selected) c.chipSelectedText else c.chipText, colorSpec, label = "chipText")
    Box(
        Modifier
            .heightIn(min = 48.dp)
            .selectable(
                selected = selected,
                interactionSource = interaction,
                indication = null,
                enabled = enabled,
                role = Role.Button,
                onClick = onClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .graphicsLayer { scaleX = scale; scaleY = scale }
                .heightIn(min = 36.dp)
                .background(bg, CircleShape)
                .border(1.dp, border, CircleShape)
                .padding(horizontal = 14.dp, vertical = 6.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                label,
                color = fg, fontSize = 14.sp, lineHeight = 20.sp,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/**
 * Whole-step slider 0..[max]: 4 dp track, 28 dp white thumb that grows 1.18x (spring) while held. Tap or drag;
 * a light tick on every step. Accessibility: range info, value text, set-progress (TalkBack volume keys/swipes).
 */
@Composable
private fun StepSlider(
    value: Int,
    max: Int,
    enabled: Boolean,
    label: String,
    valueText: String,
    onChange: (Int) -> Unit,
) {
    val c = LocalPalette.current
    val haptic = LocalHapticFeedback.current
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    val thumbSize = 28.dp
    val thumbPx = with(LocalDensity.current) { thumbSize.toPx() }
    var widthPx by remember { mutableFloatStateOf(0f) }
    var dragX by remember { mutableFloatStateOf(0f) }
    var held by remember { mutableStateOf(false) }
    var lastEmitted by remember { mutableIntStateOf(value) }
    LaunchedEffect(value) { lastEmitted = value }
    val maxNow by rememberUpdatedState(max)
    val rtlNow by rememberUpdatedState(rtl)
    val onChangeNow by rememberUpdatedState(onChange)

    fun valueAt(x: Float): Int {
        val usable = (widthPx - thumbPx).coerceAtLeast(1f)
        var f = ((x - thumbPx / 2f) / usable).coerceIn(0f, 1f)
        if (rtlNow) f = 1f - f
        return (f * maxNow).roundToInt().coerceIn(0, maxNow)
    }

    fun emit(v: Int) {
        if (v == lastEmitted) return
        lastEmitted = v
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        onChangeNow(v)
    }

    val fraction by animateFloatAsState(
        targetValue = if (max > 0) value.toFloat() / max else 0f,
        animationSpec = motion(spring(dampingRatio = 0.85f, stiffness = Spring.StiffnessMedium)),
        label = "sliderPosition",
    )
    val thumbScale by animateFloatAsState(
        targetValue = if (held && enabled) 1.18f else 1f,
        animationSpec = motion(spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium)),
        label = "sliderThumb",
    )
    val dragState = rememberDraggableState { delta ->
        dragX += delta
        emit(valueAt(dragX))
    }

    Box(
        Modifier
            .fillMaxWidth()
            .height(48.dp)
            .onSizeChanged { widthPx = it.width.toFloat() }
            .semantics(mergeDescendants = true) {
                contentDescription = label
                stateDescription = valueText
                progressBarRangeInfo = ProgressBarRangeInfo(
                    current = value.toFloat(),
                    range = 0f..max.toFloat(),
                    steps = (max - 1).coerceAtLeast(0),
                )
                if (enabled) {
                    setProgress { target ->
                        val v = target.roundToInt().coerceIn(0, max)
                        if (v != value) onChange(v)
                        true
                    }
                } else {
                    disabled()
                }
            }
            .draggable(
                state = dragState,
                orientation = Orientation.Horizontal,
                enabled = enabled,
                onDragStarted = { start ->
                    held = true
                    dragX = start.x
                    emit(valueAt(start.x))
                },
                onDragStopped = { held = false },
            )
            .pointerInput(enabled) {
                if (!enabled) return@pointerInput
                detectTapGestures(
                    onPress = {
                        held = true
                        tryAwaitRelease()
                        held = false
                    },
                    onTap = { pos -> emit(valueAt(pos.x)) },
                )
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = thumbPx / 2f
            val y = size.height / 2f
            val stroke = 4.dp.toPx()
            val start = r
            val end = size.width - r
            drawLine(c.sliderInactive, Offset(start, y), Offset(end, y), strokeWidth = stroke, cap = StrokeCap.Round)
            if (fraction > 0f) {
                val span = (end - start) * fraction
                if (rtl) drawLine(c.fill, Offset(end, y), Offset(end - span, y), strokeWidth = stroke, cap = StrokeCap.Round)
                else drawLine(c.fill, Offset(start, y), Offset(start + span, y), strokeWidth = stroke, cap = StrokeCap.Round)
            }
        }
        // offset {} follows the layout direction, so the thumb mirrors itself in RTL.
        Box(
            Modifier
                .align(Alignment.CenterStart)
                .offset { IntOffset(((widthPx - thumbPx).coerceAtLeast(0f) * fraction).roundToInt(), 0) }
                .size(thumbSize)
                .graphicsLayer { scaleX = thumbScale; scaleY = thumbScale }
                .shadow(4.dp, CircleShape)
                .background(c.thumb, CircleShape)
        )
    }
}

/** Navigation row: title, short summary, chevron. */
@Composable
private fun NavRow(title: String, summary: String, onClick: () -> Unit) {
    val c = LocalPalette.current
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val bg by animateColorAsState(
        targetValue = if (pressed) c.press else c.bg,
        animationSpec = motion(tween(120)),
        label = "navPress",
    )
    Row(
        Modifier
            .fillMaxWidth()
            .background(bg)
            .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)
            .heightIn(min = 56.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, modifier = Modifier.weight(1f), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp)
        Text(
            summary, modifier = Modifier.weight(1f, fill = false),
            color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, textAlign = TextAlign.End,
        )
        Canvas(
            Modifier
                .size(18.dp)
                .graphicsLayer { scaleX = if (rtl) -1f else 1f }
        ) {
            val s = size.width / 24f
            val path = Path().apply {
                moveTo(9f * s, 6f * s)
                lineTo(15f * s, 12f * s)
                lineTo(9f * s, 18f * s)
            }
            drawPath(path, c.chevron, style = Stroke(width = 2f * s, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
    }
}

@Composable
private fun Band() {
    val c = LocalPalette.current
    Box(Modifier.fillMaxWidth().height(8.dp).background(c.band))
}

// ------------------------------------------------------------------------------------------------- previews

private val previewActions = HomeActions({}, {}, {}, {}, {}, {})

private val previewOn = HomeUiState(
    headline = HomeLogic.Headline.FILLING,
    masterOn = true,
    measuredDeviceName = "Galaxy S26 Ultra",
    level = 6,
    levelMax = 9,
    chip = HomeLogic.Chip.FULLNESS,
    linkOn = true,
    linkLine = HomeLogic.LinkLine.Reduced(60, 4f, 2f),
)

@Preview(name = "Light · on", locale = "ko", widthDp = 390, heightDp = 844, showBackground = true)
@Preview(
    name = "Dark · on", locale = "ko", widthDp = 390, heightDp = 844, showBackground = true,
    uiMode = Configuration.UI_MODE_NIGHT_YES or Configuration.UI_MODE_TYPE_NORMAL,
)
@Composable
private fun HomePreviewOn() {
    HomeScreen(previewOn, previewActions)
}

@Preview(name = "Light · off, unmeasured", locale = "ko", widthDp = 390, heightDp = 844, showBackground = true)
@Preview(
    name = "Dark · off, unmeasured", locale = "ko", widthDp = 390, heightDp = 844, showBackground = true,
    uiMode = Configuration.UI_MODE_NIGHT_YES or Configuration.UI_MODE_TYPE_NORMAL,
)
@Composable
private fun HomePreviewOff() {
    HomeScreen(
        previewOn.copy(
            headline = HomeLogic.Headline.ORIGINAL, masterOn = false, measuredDeviceName = null,
            level = 9, chip = HomeLogic.Chip.DEEP, linkOn = false, linkLine = HomeLogic.LinkLine.Off,
        ),
        previewActions,
    )
}

@Preview(name = "Font 200 %", locale = "en", widthDp = 390, heightDp = 1400, showBackground = true, fontScale = 2f)
@Composable
private fun HomePreviewLargeFont() {
    HomeScreen(previewOn, previewActions)
}

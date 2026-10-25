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
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.runtime.saveable.rememberSaveable
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
import me.timschneeberger.rootlessjamesdsp.ui.RN_MS_COLOR
import me.timschneeberger.rootlessjamesdsp.ui.RN_MS_MOVE
import me.timschneeberger.rootlessjamesdsp.ui.RnEase
import me.timschneeberger.rootlessjamesdsp.ui.rnRelease
import me.timschneeberger.rootlessjamesdsp.ui.rnSettle
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
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.ui.semantics.onClick
import androidx.compose.runtime.DisposableEffect
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
 * One column: top bar, master row (headline + device + switch), the two feature tabs (virtual bass in teal, spatial
 * in purple), the selected tab's controls (strength slider with preset chips and volume link row / spatial switch,
 * presets, distance and head size), and the navigation rows. No fixed heights on anything holding text (rows only have minimum heights), and the
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
    /** The capture service was killed by the system (KillWatch): the dismissible battery banner. */
    val killBanner: Boolean = false,
    /** Spatial (crosstalk cancellation, pvb_xtc.h): on/off, preset, distance step, hat size. */
    val xtcOn: Boolean = false,
    /** Processing is on (with or without virtual bass): spatial can play. */
    val processingOn: Boolean = masterOn,
    /** The stored distance, shown as is (the advanced settings move it in 1 cm steps). */
    val xtcDistanceCm: Int = 40,
    val xtcPreset: HomeLogic.XtcPreset = HomeLogic.XtcPreset.CUSTOM,
    val xtcDistanceStep: Int = 3,
    val xtcDistanceSteps: Int = 7,
    val xtcHatCm: Int = 57,
    /** Speaker balance (left louder, dB), 400-1500 Hz and 1.5-8 kHz; both 0 = not set. */
    val xtcBalLoDb: Float = 0f,
    val xtcBalHiDb: Float = 0f,
    /** The limiter has been working much of the time with virtual bass on (HomeLogic.limiterPressure). */
    val limiterPressure: Boolean = false,
)

class HomeActions(
    val onMaster: (Boolean) -> Unit,
    val onLevel: (Int) -> Unit,
    val onChip: (HomeLogic.Chip) -> Unit,
    val onLink: (Boolean) -> Unit,
    val onAdvanced: () -> Unit,
    val onAbout: () -> Unit,
    /** "Exclude apps (video, games)": the upstream exclusion list. */
    val onExclusions: () -> Unit = {},
    /** Kill banner: open the battery step / dismiss it. */
    val onKillBattery: () -> Unit = {},
    val onKillDismiss: () -> Unit = {},
    val onXtc: (Boolean) -> Unit = {},
    val onXtcPreset: (HomeLogic.XtcPreset) -> Unit = {},
    /** Distance slider step (HomeLogic.xtcDistanceCm). */
    val onXtcDistance: (Int) -> Unit = {},
    /** Hat size, cm: 54 / 57 / 60. */
    val onXtcHead: (Int) -> Unit = {},
    /** (i) next to the tabs: the spatial motion story (SpatialStoryActivity). */
    val onSpatialInfo: () -> Unit = {},
    /** "좌우 맞추기" (SpatialBalanceActivity). */
    val onXtcBalance: () -> Unit = {},
    /** "누르는 동안 가상 저음 빼고 듣기": true while held (a temporary override with the layer silent), false on release. */
    val onHoldWithoutVb: (Boolean) -> Unit = {},
)

private val LocalPalette = staticCompositionLocalOf<RootnotePalette> { error("RootnotePalette not provided") }
private val LocalReduceMotion = staticCompositionLocalOf { false }

/** The one curve of docs/DESIGN.md 6 (defined in ui/RnTheme.kt): switches, dimming, colour changes. */
private val IosEase = RnEase

/** Readability rule for changing text: the old text fades out completely (150 ms), then the new one fades in. */
private fun sequentialFade(): ContentTransform = ContentTransform(
    targetContentEnter = fadeIn(tween(150, delayMillis = 150, easing = LinearEasing)),
    initialContentExit = fadeOut(tween(150, easing = LinearEasing)),
    sizeTransform = SizeTransform(clip = false) { _, _ -> tween(RN_MS_MOVE, easing = IosEase) },
)

/** A tab swap: the two sections cross-fade (150 ms) and the height follows with the same curve and time. */
private fun crossFade(): ContentTransform = ContentTransform(
    targetContentEnter = fadeIn(tween(RN_MS_COLOR, easing = IosEase)),
    initialContentExit = fadeOut(tween(RN_MS_COLOR, easing = IosEase)),
    sizeTransform = SizeTransform(clip = false) { _, _ -> tween(RN_MS_COLOR, easing = IosEase) },
)

/** [spec], or an instant change when the system animations are off. */
@Composable
private fun <T> motion(spec: FiniteAnimationSpec<T>): FiniteAnimationSpec<T> =
    if (LocalReduceMotion.current) snap() else spec

@Composable
fun HomeScreen(state: HomeUiState, actions: HomeActions, reduceMotion: Boolean = false, initialTab: Int = 0) {
    val palette = rootnotePalette()
    val dark = (androidx.compose.ui.platform.LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    val scheme = if (dark) darkColorScheme(primary = palette.fill, background = palette.bg, surface = palette.bg,
        onBackground = palette.textPrimary, onSurface = palette.textPrimary)
    else lightColorScheme(primary = palette.fill, background = palette.bg, surface = palette.bg,
        onBackground = palette.textPrimary, onSurface = palette.textPrimary)
    CompositionLocalProvider(LocalPalette provides palette, LocalReduceMotion provides reduceMotion) {
        MaterialTheme(colorScheme = scheme) {
            HomeContent(state, actions, initialTab)
        }
    }
}

@Composable
private fun HomeContent(state: HomeUiState, actions: HomeActions, initialTab: Int) {
    val c = LocalPalette.current
    Column(
        Modifier
            .fillMaxSize()
            .background(c.bg)
            .verticalScroll(rememberScrollState())
    ) {
        TopBar()
        if (state.killBanner) KillBanner(actions)
        MasterRow(state, actions)
        Band()

        // Everything that only matters while processing is on: dimmed to 40 % and disabled when off.
        val dim by animateFloatAsState(
            targetValue = if (state.masterOn) 1f else 0.4f,
            animationSpec = motion(tween(RN_MS_COLOR, easing = IosEase)),
            label = "dim",
        )
        var tab by rememberSaveable { mutableIntStateOf(initialTab) }
        FeatureTabs(
            tab, onSelect = { tab = it }, bassOn = state.masterOn, spatialOn = state.processingOn && state.xtcOn,
            onInfo = actions.onSpatialInfo,
        )
        val reduce = LocalReduceMotion.current
        AnimatedContent(
            targetState = tab,
            transitionSpec = {
                if (reduce) ContentTransform(EnterTransition.None, ExitTransition.None, sizeTransform = null)
                else crossFade()
            },
            contentAlignment = Alignment.TopStart,
            label = "tab",
        ) { selected ->
            if (selected == TAB_SPATIAL) {
                val spatialDim by animateFloatAsState(
                    targetValue = if (state.processingOn) 1f else 0.4f,
                    animationSpec = motion(tween(RN_MS_COLOR, easing = IosEase)),
                    label = "spatialDim",
                )
                CompositionLocalProvider(LocalPalette provides c.spatial()) {
                    SpatialSection(state, actions, Modifier.graphicsLayer { alpha = spatialDim })
                }
            } else {
                BassSection(state, actions, Modifier.graphicsLayer { alpha = dim })
            }
        }

        Band()
        NavRow(
            stringResource(R.string.home_exclude_title), "", actions.onExclusions,
            description = stringResource(R.string.home_exclude_summary, stringResource(R.string.app_brand_name)),
        )
        NavRow(stringResource(R.string.home_advanced_title), stringResource(R.string.home_advanced_summary), actions.onAdvanced)
        NavRow(stringResource(R.string.home_about_title), stringResource(R.string.home_about_summary), actions.onAbout)
        Spacer(Modifier.height(24.dp))
    }
}

private const val TAB_BASS = 0
private const val TAB_SPATIAL = 1

/**
 * The two features as a segmented control: a rounded band-coloured track with two equal segments, the selected one
 * raised on the page colour in its feature's accent (teal for virtual bass, purple for spatial). A small dot after
 * each label shows whether that feature is playing. Role tab, 48 dp targets, text grows with the font size.
 */
@Composable
private fun FeatureTabs(selected: Int, onSelect: (Int) -> Unit, bassOn: Boolean, spatialOn: Boolean, onInfo: () -> Unit) {
    val c = LocalPalette.current
    Row(
        Modifier.padding(start = 16.dp, end = 4.dp, top = 16.dp, bottom = 4.dp).fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier
                .weight(1f)
                .background(c.band, RoundedCornerShape(14.dp))
                .padding(4.dp)
                .selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            FeatureTab(stringResource(R.string.home_tab_bass), selected == TAB_BASS, bassOn, c.accentText, c.fill) { onSelect(TAB_BASS) }
            FeatureTab(stringResource(R.string.home_tab_spatial), selected == TAB_SPATIAL, spatialOn, c.xtcAccentText, c.xtcFill) {
                onSelect(TAB_SPATIAL)
            }
        }
        InfoButton(stringResource(R.string.home_xtc_info_open), c.xtcAccentText, onInfo)
    }
}

/** (i) in a 48 dp target: opens the friendly long explanation of spatial. */
@Composable
private fun InfoButton(description: String, tint: Color, onClick: () -> Unit) {
    Box(
        Modifier
            .size(48.dp)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.size(22.dp).border(1.5.dp, tint, CircleShape), contentAlignment = Alignment.Center) {
            Text("i", color = tint, fontSize = 13.sp, lineHeight = 13.sp, fontWeight = FontWeight.Bold)
        }
    }
}


@Composable
private fun RowScope.FeatureTab(label: String, selected: Boolean, on: Boolean, accent: Color, dot: Color, onClick: () -> Unit) {
    val c = LocalPalette.current
    val colorSpec = motion(tween<Color>(RN_MS_COLOR, easing = IosEase))
    val bg by animateColorAsState(if (selected) c.bg else c.band, colorSpec, label = "tabBg")
    val fg by animateColorAsState(if (selected) accent else c.textSecondary, colorSpec, label = "tabText")
    val dotColor by animateColorAsState(if (on) dot else c.chevron, colorSpec, label = "tabDot")
    val elevation by animateDpAsState(if (selected) 1.dp else 0.dp, motion(tween(RN_MS_COLOR, easing = IosEase)), label = "tabLift")
    val edge by animateColorAsState(if (selected) c.chipBorder else c.band, colorSpec, label = "tabEdge")
    val state = stringResource(if (on) R.string.home_tab_on else R.string.home_tab_off)
    Row(
        Modifier
            .weight(1f)
            .heightIn(min = 48.dp)
            .shadow(elevation, RoundedCornerShape(10.dp))
            .background(bg, RoundedCornerShape(10.dp))
            .border(1.dp, edge, RoundedCornerShape(10.dp))
            .selectable(selected = selected, role = Role.Tab, onClick = onClick)
            .semantics { stateDescription = state }
            .padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        Text(
            label, color = fg, fontSize = 16.sp, lineHeight = 22.sp, textAlign = TextAlign.Center,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            modifier = Modifier.weight(1f, fill = false),
        )
        Spacer(Modifier.size(6.dp))
        Box(Modifier.size(6.dp).background(dotColor, CircleShape))
    }
}

/** Virtual bass tab: strength slider with preset chips, then the volume link row. */
@Composable
private fun BassSection(state: HomeUiState, actions: HomeActions, modifier: Modifier) {
    val c = LocalPalette.current
    Column(modifier) {
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
        if (state.limiterPressure && state.masterOn && state.level > 0) PressureTip(state, actions)
        HoldWithoutVbRow(enabled = state.masterOn && state.processingOn, onHold = actions.onHoldWithoutVb)
        // A phone without a measured profile: the EQ balance first, virtual bass as a spice on top.
        if (state.measuredDeviceName == null) SpiceTip(actions)
    }
}

/**
 * "누르는 동안 가상 저음 빼고 듣기": while the finger is down only the virtual bass layer goes silent (same model and
 * latency, EQ unchanged, nothing stored), so the listener hears what it adds. TalkBack: a double tap holds it for 5 s.
 */
@Composable
private fun HoldWithoutVbRow(enabled: Boolean, onHold: (Boolean) -> Unit) {
    val c = LocalPalette.current
    var held by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun set(on: Boolean) { if (held != on) { held = on; onHold(on) } }
    DisposableEffect(Unit) { onDispose { if (held) onHold(false) } }
    LaunchedEffect(enabled) { if (!enabled) set(false) }
    val title = stringResource(R.string.home_hold_novb_title)
    val tapLabel = stringResource(R.string.home_hold_novb_a11y)
    val heldState = stringResource(R.string.home_hold_novb_active)
    Column(
        Modifier
            .padding(start = 16.dp, end = 16.dp, top = 8.dp)
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .background(if (held) c.chipSelectedBg else Color.Transparent, RoundedCornerShape(12.dp))
            .border(1.dp, if (held) c.chipSelectedBorder else c.divider, RoundedCornerShape(12.dp))
            .alpha(if (enabled) 1f else 0.45f)
            .pointerInput(enabled) {
                if (!enabled) return@pointerInput
                detectTapGestures(onPress = {
                    set(true)
                    try { tryAwaitRelease() } finally { set(false) }
                })
            }
            .semantics {
                if (!enabled) disabled()
                stateDescription = if (held) heldState else ""
                onClick(tapLabel) {
                    if (enabled) scope.launch { set(true); kotlinx.coroutines.delay(5000); set(false) }
                    true
                }
            }
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(title, color = c.textPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold, lineHeight = 21.sp)
        Text(
            stringResource(if (held) R.string.home_hold_novb_active else R.string.home_hold_novb_line),
            color = if (held) c.accentText else c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        )
    }
}

/** "지금 세기에서 소리가 눌리고 있어요": the limiter works much of the time; one tap lowers the strength by one step. */
@Composable
private fun PressureTip(state: HomeUiState, actions: HomeActions) {
    val c = LocalPalette.current
    Column(
        Modifier
            .padding(start = 16.dp, end = 16.dp, top = 8.dp)
            .fillMaxWidth()
            .background(c.chipSelectedBg, RoundedCornerShape(12.dp))
            .border(1.dp, c.chipSelectedBorder, RoundedCornerShape(12.dp))
            .padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            stringResource(R.string.home_pressure_title),
            modifier = Modifier.padding(end = 8.dp).semantics { heading() },
            color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
        )
        Text(
            stringResource(R.string.home_pressure_body),
            modifier = Modifier.padding(end = 8.dp),
            color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        )
        FlowRowActions {
            BannerAction(stringResource(R.string.home_pressure_action), bold = true,
                onClick = { actions.onLevel((state.level - 1).coerceAtLeast(0)) })
        }
    }
}

/**
 * "가상 저음은 양념이에요" (unmeasured phones): set the balance with the EQ first (low mids up, treble a little down),
 * then add virtual bass low. Neutral card (advice, not a warning); the action opens the advanced settings.
 */
@Composable
private fun SpiceTip(actions: HomeActions) {
    val c = LocalPalette.current
    Column(
        Modifier
            .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 4.dp)
            .fillMaxWidth()
            .border(1.dp, c.divider, RoundedCornerShape(12.dp))
            .padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            stringResource(R.string.home_spice_title),
            modifier = Modifier.padding(end = 8.dp).semantics { heading() },
            color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
        )
        Text(
            stringResource(R.string.home_spice_body),
            modifier = Modifier.padding(end = 8.dp),
            color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        )
        FlowRowActions {
            BannerAction(stringResource(R.string.home_spice_action), bold = true, onClick = actions.onAdvanced)
        }
    }
}

@Composable
private fun xtcChipLabel(p: HomeLogic.XtcPreset): String = stringResource(
    when (p) {
        HomeLogic.XtcPreset.SUBTLE -> R.string.home_xtc_chip_subtle
        HomeLogic.XtcPreset.BALANCED -> R.string.home_xtc_chip_balanced
        HomeLogic.XtcPreset.CLEAR -> R.string.home_xtc_chip_clear
        HomeLogic.XtcPreset.CUSTOM -> R.string.home_xtc_chip_custom
    }
)

@Composable
private fun xtcChipHint(p: HomeLogic.XtcPreset): String = stringResource(
    when (p) {
        HomeLogic.XtcPreset.SUBTLE -> R.string.home_xtc_hint_subtle
        HomeLogic.XtcPreset.BALANCED -> R.string.home_xtc_hint_balanced
        HomeLogic.XtcPreset.CLEAR -> R.string.home_xtc_hint_clear
        HomeLogic.XtcPreset.CUSTOM -> R.string.home_xtc_hint_custom
    }
)

/**
 * Spatial tab (drawn with the purple palette): the on/off row, then presets, listening distance and head size, which
 * dim to 40 % and stop taking input while spatial is off. Head size is chosen by hat size, never measured.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SpatialSection(state: HomeUiState, actions: HomeActions, modifier: Modifier) {
    val c = LocalPalette.current
    val reduce = LocalReduceMotion.current
    val active = state.processingOn && state.xtcOn
    // Only one dimming at a time: the whole tab is already at 40 % while processing is off.
    val innerDim by animateFloatAsState(
        targetValue = if (state.xtcOn || !state.processingOn) 1f else 0.4f,
        animationSpec = motion(tween(RN_MS_COLOR, easing = IosEase)),
        label = "xtcDim",
    )
    Column(modifier) {
        SwitchRow(
            checked = state.xtcOn,
            enabled = state.processingOn,
            onCheckedChange = actions.onXtc,
            minHeight = 72.dp,
            padding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(
                    stringResource(R.string.home_xtc_title),
                    color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
                )
                Text(
                    stringResource(if (state.xtcOn) R.string.home_xtc_line_on else R.string.home_xtc_line_off),
                    color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
                )
            }
        }
        Column(Modifier.graphicsLayer { alpha = innerDim }.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 8.dp)) {
            FlowRow(
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp).selectableGroup(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                val chips = HomeLogic.xtcChips +
                    (if (state.xtcPreset == HomeLogic.XtcPreset.CUSTOM && state.xtcOn) listOf(HomeLogic.XtcPreset.CUSTOM) else emptyList())
                for (p in chips) {
                    PresetChip(
                        label = xtcChipLabel(p),
                        selected = state.xtcOn && state.xtcPreset == p,
                        enabled = active,
                        onClick = { actions.onXtcPreset(p) },
                    )
                }
            }
            AnimatedContent(
                targetState = if (state.xtcOn) state.xtcPreset else null,
                transitionSpec = {
                    if (reduce) EnterTransition.None togetherWith ExitTransition.None
                    else sequentialFade()
                },
                contentAlignment = Alignment.TopStart,
                label = "xtcHint",
            ) { p ->
                Text(
                    if (p != null) xtcChipHint(p) else stringResource(R.string.home_xtc_hint_off),
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    color = c.textSecondary, fontSize = 13.sp, lineHeight = 19.sp,
                )
            }
            Box(Modifier.padding(top = 16.dp).fillMaxWidth().height(1.dp).background(c.divider))
            val distTitle = stringResource(R.string.home_xtc_distance)
            val distText = stringResource(R.string.home_xtc_distance_value, state.xtcDistanceCm)
            Row(Modifier.fillMaxWidth().padding(top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    distTitle, modifier = Modifier.weight(1f),
                    color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
                )
                Crossfade(targetState = distText, animationSpec = motion(tween(120)), label = "xtcDist") { t ->
                    Text(t, color = c.accentText, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp)
                }
            }
            StepSlider(
                value = state.xtcDistanceStep,
                max = state.xtcDistanceSteps,
                enabled = active,
                label = distTitle,
                valueText = distText,
                onChange = actions.onXtcDistance,
            )
            Text(
                stringResource(R.string.home_xtc_head),
                modifier = Modifier.padding(top = 16.dp),
                color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
            )
            FlowRow(
                modifier = Modifier.fillMaxWidth().selectableGroup(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                for ((hat, label) in listOf(54 to R.string.home_xtc_head_s, 57 to R.string.home_xtc_head_m, 60 to R.string.home_xtc_head_l)) {
                    PresetChip(
                        label = stringResource(label),
                        selected = state.xtcHatCm == hat,
                        enabled = active,
                        onClick = { actions.onXtcHead(hat) },
                    )
                }
            }
            Text(
                stringResource(R.string.home_xtc_head_hint),
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                color = c.textSecondary, fontSize = 13.sp, lineHeight = 19.sp,
            )
        }
        Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp).fillMaxWidth().height(1.dp).background(c.divider))
        val balanceLine = if (state.xtcBalLoDb == 0f && state.xtcBalHiDb == 0f) stringResource(R.string.home_xtc_balance_none)
            else stringResource(R.string.home_xtc_balance_set, balanceSide(state.xtcBalLoDb), balanceSide(state.xtcBalHiDb))
        Box(Modifier.graphicsLayer { alpha = innerDim }) {
            NavRow(stringResource(R.string.home_xtc_balance), "", if (active) actions.onXtcBalance else ({}), description = balanceLine)
        }
    }
}

@Composable
private fun balanceSide(db: Float): String = when {
    db > 0f -> stringResource(R.string.balance_side_left, "%.1f".format(db))
    db < 0f -> stringResource(R.string.balance_side_right, "%.1f".format(-db))
    else -> stringResource(R.string.balance_side_even)
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
        animationSpec = motion(if (pressed) tween(0) else tween(RN_MS_COLOR, easing = IosEase)),
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
        animationSpec = motion(tween(RN_MS_MOVE, easing = IosEase)),
        label = "switchThumb",
    )
    val track by animateColorAsState(
        targetValue = if (checked) c.fill else c.switchOff,
        animationSpec = motion(tween(RN_MS_MOVE, easing = IosEase)),
        label = "switchTrack",
    )
    Box(Modifier.size(width = 51.dp, height = 31.dp).background(track, CircleShape)) {
        Box(
            Modifier
                .offset(y = 2.dp)
                .size(27.dp)
                .graphicsLayer { translationX = thumbX.toPx() }
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
            else -> rnRelease()
        },
        label = "chipScale",
    )
    val colorSpec = motion(tween<Color>(RN_MS_COLOR, easing = IosEase))
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
    var lastTick by remember { mutableIntStateOf(-1) }
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
        // one tick per step, but at most about 24 per sweep (a fine slider would buzz otherwise)
        val tick = if (maxNow > 24) v * 24 / maxNow else v
        if (tick != lastTick) {
            lastTick = tick
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        }
        onChangeNow(v)
    }

    val fraction by animateFloatAsState(
        targetValue = if (max > 0) value.toFloat() / max else 0f,
        // under the finger the thumb is the finger (no smoothing); a spring only after it is let go or a tap
        animationSpec = motion(if (held) tween(0) else rnSettle()),
        label = "sliderPosition",
    )
    val thumbScale by animateFloatAsState(
        targetValue = if (held && enabled) 1.18f else 1f,
        animationSpec = motion(if (held) tween(120, easing = IosEase) else rnRelease()),
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

/**
 * "The system stopped the app" banner (general build, KillWatch): the teal tint of the selected chip, a title, one
 * explanation and two text actions with 48 dp touch targets. Only shown while no service runs.
 */
@Composable
private fun KillBanner(actions: HomeActions) {
    val c = LocalPalette.current
    val brand = stringResource(R.string.app_brand_name)
    Column(
        Modifier
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .fillMaxWidth()
            .background(c.chipSelectedBg, RoundedCornerShape(12.dp))
            .border(1.dp, c.chipSelectedBorder, RoundedCornerShape(12.dp))
            .padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            stringResource(R.string.home_killed_title, brand),
            modifier = Modifier.padding(end = 8.dp).semantics { heading() },
            color = c.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp,
        )
        Text(
            stringResource(R.string.home_killed_body, brand),
            modifier = Modifier.padding(end = 8.dp),
            color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        )
        FlowRowActions {
            BannerAction(stringResource(R.string.home_killed_battery), bold = true, onClick = actions.onKillBattery)
            BannerAction(stringResource(R.string.home_killed_dismiss), bold = false, onClick = actions.onKillDismiss)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FlowRowActions(content: @Composable () -> Unit) {
    FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { content() }
}

@Composable
private fun BannerAction(label: String, bold: Boolean, onClick: () -> Unit) {
    val c = LocalPalette.current
    Box(
        Modifier
            .heightIn(min = 48.dp)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            color = c.accentText, fontSize = 14.sp, lineHeight = 20.sp,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium,
        )
    }
}

/** Navigation row: title (with an optional line below it), short summary, chevron. */
@Composable
private fun NavRow(title: String, summary: String, onClick: () -> Unit, description: String? = null) {
    val c = LocalPalette.current
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val bg by animateColorAsState(
        targetValue = if (pressed) c.press else c.bg,
        animationSpec = motion(if (pressed) tween(0) else tween(RN_MS_COLOR, easing = IosEase)),
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
        if (description == null) {
            Text(title, modifier = Modifier.weight(1f), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp)
        } else {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp)
                Text(description, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            }
        }
        if (summary.isNotEmpty()) Text(
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

@Preview(name = "Light · killed banner", locale = "ko", widthDp = 390, heightDp = 900, showBackground = true)
@Preview(
    name = "Dark · killed banner", locale = "ko", widthDp = 390, heightDp = 900, showBackground = true,
    uiMode = Configuration.UI_MODE_NIGHT_YES or Configuration.UI_MODE_TYPE_NORMAL,
)
@Composable
private fun HomePreviewKilled() {
    HomeScreen(
        previewOn.copy(headline = HomeLogic.Headline.ORIGINAL, masterOn = false, killBanner = true),
        previewActions,
    )
}

@Preview(name = "Light · spatial tab", locale = "ko", widthDp = 390, heightDp = 1000, showBackground = true)
@Preview(
    name = "Dark · spatial tab", locale = "ko", widthDp = 390, heightDp = 1000, showBackground = true,
    uiMode = Configuration.UI_MODE_NIGHT_YES or Configuration.UI_MODE_TYPE_NORMAL,
)
@Composable
private fun HomePreviewSpatial() {
    HomeScreen(previewOn.copy(xtcOn = true, xtcPreset = HomeLogic.XtcPreset.CLEAR), previewActions, initialTab = 1)
}

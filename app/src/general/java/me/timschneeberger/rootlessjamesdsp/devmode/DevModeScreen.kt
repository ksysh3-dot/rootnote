package me.timschneeberger.rootlessjamesdsp.devmode

import android.content.res.Configuration
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberModalBottomSheetState
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
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidence
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidenceText
import me.timschneeberger.rootlessjamesdsp.pvb.DevGroup
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevShareCode
import me.timschneeberger.rootlessjamesdsp.pvb.DevSnapshot
import me.timschneeberger.rootlessjamesdsp.pvb.DevSpec
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevUnit
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarning
import java.util.Locale
import kotlin.math.roundToInt

/*
 * Developer-mode screen (Figma "개발자 모드 시안" 1-7, docs/DESIGN.md). Top bar, test sounds, a swipeable graph card
 * (harmonic bars / time graph / headroom gauge) whose page follows the group tabs, the slider cards of the group, the
 * settings rows, and a bottom bar (hold for the original, undo, share code). Dialogs: consent, warnings; sheets:
 * evidence, share code.
 */

@Immutable
data class DevDialog(val warning: DevWarning, val offerHide: Boolean, val tailMs: Int)

@Immutable
data class DevUiState(
    val values: FloatArray,
    val defaults: FloatArray,
    val vbAlgo: Int,
    val s1mOn: Boolean,
    val volumeLinkOn: Boolean,
    val measuredBadge: DevEvidenceText.MeasuredBadge,
    val thresholdMeasured: Boolean,
    val measuredOnName: String,
    val speakerFloorHz: Float,
    val gaugeVu: Boolean,
    val hiddenCount: Int,
    val canUndo: Boolean,
    val consentNeeded: Boolean,
    val serviceRunning: Boolean,
    val shareCode: String,
    val tab: Int = 0,
    val touched: String? = null,
    val testKind: DevTestKind? = null,
    val toneHz: Int = 55,
    val snapshot: DevSnapshot? = null,
    val active: Set<DevWarning> = emptySet(),
    val tailMs: Float? = null,
    val volumePct: Float = 0f,
    val abHolding: Boolean = false,
    val dialog: DevDialog? = null,
    val evidenceFor: String? = null,
    val shareOpen: Boolean = false,
    val sheetOpen: Boolean = false,
    val pasteText: String = "",
    val pasteResult: DevShareCode.Result? = null,
    val previewing: Boolean = false,
)

class DevActions(
    val onBack: () -> Unit,
    val onConsent: (Boolean) -> Unit,
    val onTab: (Int) -> Unit,
    val onValueStart: (DevSpec) -> Unit,
    val onValue: (DevSpec, Float) -> Unit,
    val onStep: (DevSpec, Int) -> Unit,
    val onToggle: (DevSpec, Boolean) -> Unit,
    val onUndo: () -> Unit,
    val onResetGroup: (DevGroup?) -> Unit,
    val onAbHold: (Boolean) -> Unit,
    val onTest: (DevTestKind?) -> Unit,
    val onEvidence: (DevSpec?) -> Unit,
    val onOpenUrl: (String) -> Unit,
    val onShareOpen: (Boolean) -> Unit,
    val onCopy: () -> Unit,
    val onSend: () -> Unit,
    val onPaste: (String) -> Unit,
    val onPreview: (Boolean) -> Unit,
    val onApply: () -> Unit,
    /** hide: "이 경고 다시 표시하지 않기" checked; action: the dialog's action button was used. */
    val onDialogClose: (hide: Boolean, action: Boolean) -> Unit,
    val onGaugeStyle: (Boolean) -> Unit,
    val onRestoreWarnings: () -> Unit,
    val onTurnOff: () -> Unit,
)

/** Rootnote palette plus the semantic tokens of docs/DESIGN.md 2.2 (res/values{,-night}/colors_rootnote.xml). */
@Immutable
data class DevPalette(
    val bg: Color, val band: Color, val press: Color, val divider: Color,
    val textPrimary: Color, val textSecondary: Color, val chevron: Color,
    val fill: Color, val accentText: Color,
    val chipBorder: Color, val chipText: Color, val chipSelectedBg: Color, val chipSelectedBorder: Color,
    val switchOff: Color, val sliderInactive: Color, val thumb: Color,
    val warnBg: Color, val warnText: Color, val warnDot: Color, val danger: Color, val dangerBg: Color,
    val researchBg: Color, val researchText: Color, val makerBg: Color, val makerText: Color,
    val measuredBg: Color, val measuredText: Color, val guessBg: Color, val guessText: Color,
    val dark: Boolean,
) {
    /** Text on rn_fill: white in light mode (5.3:1), deep teal in dark mode (white on #2BB0AA would be 2.6:1). */
    val onFill: Color get() = if (dark) Color(0xFF003734) else Color.White
}

@Composable
fun devPalette(dark: Boolean): DevPalette = DevPalette(
    bg = colorResource(R.color.rn_bg), band = colorResource(R.color.rn_band), press = colorResource(R.color.rn_press),
    divider = colorResource(R.color.rn_divider), textPrimary = colorResource(R.color.rn_text_primary),
    textSecondary = colorResource(R.color.rn_text_secondary), chevron = colorResource(R.color.rn_chevron),
    fill = colorResource(R.color.rn_fill), accentText = colorResource(R.color.rn_accent_text),
    chipBorder = colorResource(R.color.rn_chip_border), chipText = colorResource(R.color.rn_chip_text),
    chipSelectedBg = colorResource(R.color.rn_chip_selected_bg),
    chipSelectedBorder = colorResource(R.color.rn_chip_selected_border),
    switchOff = colorResource(R.color.rn_switch_off), sliderInactive = colorResource(R.color.rn_slider_inactive),
    thumb = colorResource(R.color.rn_thumb),
    warnBg = colorResource(R.color.rn_warn_bg), warnText = colorResource(R.color.rn_warn_text),
    warnDot = colorResource(R.color.rn_warn_dot), danger = colorResource(R.color.rn_danger),
    dangerBg = colorResource(R.color.rn_danger_bg),
    researchBg = colorResource(R.color.rn_badge_research_bg), researchText = colorResource(R.color.rn_badge_research_text),
    makerBg = colorResource(R.color.rn_badge_maker_bg), makerText = colorResource(R.color.rn_badge_maker_text),
    measuredBg = colorResource(R.color.rn_badge_measured_bg), measuredText = colorResource(R.color.rn_badge_measured_text),
    guessBg = colorResource(R.color.rn_badge_guess_bg), guessText = colorResource(R.color.rn_badge_guess_text),
    dark = dark,
)

internal val LocalDevPalette = staticCompositionLocalOf<DevPalette> { error("DevPalette not provided") }
internal val LocalDevReduceMotion = staticCompositionLocalOf { false }

/** docs/DESIGN.md 6: IosEase for positions/colours, OvershootEase when a thumb is released. */
internal val IosEase = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)
internal val OvershootEase = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)

@Composable
internal fun <T> motion(spec: FiniteAnimationSpec<T>): FiniteAnimationSpec<T> =
    if (LocalDevReduceMotion.current) snap() else spec

/** Orange of the experimental range (gradient "주황" of docs/DESIGN.md 2.3). */
internal val ExperimentalOrange = Color(0xFFE8892F)

@Composable
fun DevModeScreen(state: DevUiState, actions: DevActions, reduceMotion: Boolean) {
    val dark = (LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
    val c = devPalette(dark)
    val scheme = if (dark) darkColorScheme(primary = c.fill, background = c.bg, surface = c.bg, onBackground = c.textPrimary,
        onSurface = c.textPrimary, surfaceContainerHigh = c.bg, surfaceContainerLow = c.bg)
    else lightColorScheme(primary = c.fill, background = c.bg, surface = c.bg, onBackground = c.textPrimary,
        onSurface = c.textPrimary, surfaceContainerHigh = c.bg, surfaceContainerLow = c.bg)
    CompositionLocalProvider(LocalDevPalette provides c, LocalDevReduceMotion provides reduceMotion) {
        MaterialTheme(colorScheme = scheme) {
            DevContent(state, actions)
            if (state.consentNeeded) ConsentDialog(actions)
            state.dialog?.let { WarningDialog(it, actions) }
            state.evidenceFor?.let { id -> DevParams.byId(id)?.let { EvidenceSheet(it, state, actions) } }
            if (state.shareOpen) ShareSheet(state, actions)
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DevContent(state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    Column(Modifier.fillMaxSize().background(c.bg).statusBarsPadding().navigationBarsPadding()) {
        TopBar(actions)
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            TestSounds(state, actions)
            val pager = rememberPagerState(initialPage = state.tab, pageCount = { 3 })
            val tabNow by rememberUpdatedState(state.tab)
            LaunchedEffect(state.tab) {
                if (pager.currentPage != state.tab) pager.animateScrollToPage(state.tab)
            }
            LaunchedEffect(pager) {
                snapshotFlow { pager.settledPage }.collect { if (it != tabNow) actions.onTab(it) }
            }
            Box(
                Modifier
                    .padding(horizontal = 16.dp)
                    .fillMaxWidth()
                    .background(c.band, RoundedCornerShape(20.dp))
            ) {
                HorizontalPager(state = pager, modifier = Modifier.fillMaxWidth()) { page ->
                    Box(Modifier.fillMaxWidth().padding(16.dp)) {
                        when (page) {
                            0 -> HarmonicPage(state)
                            1 -> TimePage(state)
                            else -> GaugePage(state)
                        }
                    }
                }
            }
            PageDots(state.tab)
            GroupTabs(state.tab, actions)
            val group = DevGroup.values()[state.tab]
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 8.dp),
                horizontalArrangement = Arrangement.End,
            ) {
                TextAction(stringResource(R.string.dev_reset_group), onClick = { actions.onResetGroup(group) })
            }
            if (group == DevGroup.TIME) {
                if (state.s1mOn) Note(stringResource(R.string.dev_time_s1m_note))
                if (state.vbAlgo == me.timschneeberger.rootlessjamesdsp.pvb.PvbModels.GENTLE12)
                    Note(stringResource(R.string.dev_time_model_note))
            }
            for (spec in DevParams.group(group)) {
                val i = DevParams.ALL.indexOf(spec)
                if (spec.isSwitch) SwitchCard(spec, state.values[i] >= 0.5f, state, actions)
                else SliderCard(spec, state.values[i], state.defaults[i], state, actions)
            }
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().height(8.dp).background(c.band))
            SettingsSection(state, actions)
            Spacer(Modifier.height(16.dp))
        }
        BottomBar(state, actions)
    }
}

// ------------------------------------------------------------------------------------------------ top bar, chips

@Composable
private fun TopBar(actions: DevActions) {
    val c = LocalDevPalette.current
    Row(
        Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(start = 4.dp, end = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val back = stringResource(R.string.dev_back)
        Box(
            Modifier.size(48.dp).clickable(role = Role.Button, onClick = actions.onBack)
                .semantics { contentDescription = back },
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(24.dp)) {
                val s = size.width / 24f
                val p = Path().apply { moveTo(15f * s, 5f * s); lineTo(8f * s, 12f * s); lineTo(15f * s, 19f * s) }
                drawPath(p, c.textPrimary, style = Stroke(width = 2.2f * s, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
        Text(
            stringResource(R.string.dev_title), modifier = Modifier.padding(start = 4.dp).semantics { heading() },
            color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp,
        )
        Spacer(Modifier.width(8.dp))
        Box(Modifier.background(c.warnBg, RoundedCornerShape(5.dp)).padding(horizontal = 6.dp, vertical = 2.dp)) {
            Text(stringResource(R.string.dev_badge_noliability), color = c.warnText, fontSize = 11.sp, lineHeight = 16.sp,
                fontWeight = FontWeight.Medium)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TestSounds(state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 8.dp)) {
        Text(stringResource(R.string.dev_test_label), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
            modifier = Modifier.semantics { heading() })
        FlowRow(Modifier.fillMaxWidth().selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            val toneLabel = stringResource(R.string.dev_test_tone, state.toneHz)
            Chip(toneLabel, state.testKind == DevTestKind.TONE, stringResource(R.string.dev_test_tone_hint)) { actions.onTest(DevTestKind.TONE) }
            Chip(stringResource(R.string.dev_test_sweep), state.testKind == DevTestKind.SWEEP) { actions.onTest(DevTestKind.SWEEP) }
            Chip(stringResource(R.string.dev_test_kick), state.testKind == DevTestKind.KICK) { actions.onTest(DevTestKind.KICK) }
            Chip(stringResource(R.string.dev_test_bass_chord), state.testKind == DevTestKind.BASS_CHORD) { actions.onTest(DevTestKind.BASS_CHORD) }
            Chip(stringResource(R.string.dev_test_music), state.testKind == null) { actions.onTest(null) }
        }
        if (!state.serviceRunning) Text(stringResource(R.string.dev_test_off_note), color = c.warnText, fontSize = 13.sp,
            lineHeight = 18.sp, modifier = Modifier.padding(top = 4.dp))
    }
}

/** Pill chip (36 dp) in a 48 dp touch target; selected = teal tint, bold, a play triangle (not an emoji). */
@Composable
private fun Chip(label: String, selected: Boolean, hint: String? = null, onClick: () -> Unit) {
    val c = LocalDevPalette.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.94f else 1f, motion(tween(120, easing = IosEase)), label = "chip")
    val bg by animateColorAsState(if (selected) c.chipSelectedBg else c.bg, motion(tween(300, easing = IosEase)), label = "chipBg")
    Box(
        Modifier.heightIn(min = 48.dp)
            .selectable(selected = selected, interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)
            .semantics { if (hint != null && selected) stateDescription = hint },
        contentAlignment = Alignment.Center,
    ) {
        Row(
            Modifier.graphicsLayer { scaleX = scale; scaleY = scale }.heightIn(min = 36.dp)
                .background(bg, CircleShape)
                .border(1.dp, if (selected) c.chipSelectedBorder else c.chipBorder, CircleShape)
                .padding(horizontal = 14.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Canvas(Modifier.size(10.dp)) {
                    val p = Path().apply { moveTo(0f, 0f); lineTo(size.width, size.height / 2f); lineTo(0f, size.height); close() }
                    drawPath(p, c.accentText)
                }
                Spacer(Modifier.width(6.dp))
            }
            Text(label, color = if (selected) c.accentText else c.chipText, fontSize = 14.sp, lineHeight = 20.sp,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium)
        }
    }
}

@Composable
private fun PageDots(page: Int) {
    val c = LocalDevPalette.current
    val label = stringResource(R.string.dev_a11y_page, page + 1)
    Row(
        Modifier.fillMaxWidth().padding(vertical = 8.dp).semantics(mergeDescendants = true) { contentDescription = label },
        horizontalArrangement = Arrangement.Center,
    ) {
        for (i in 0 until 3) {
            val w by animateDpAsState(if (i == page) 18.dp else 6.dp, motion(tween(350, easing = IosEase)), label = "dot")
            Box(Modifier.padding(horizontal = 3.dp).size(width = w, height = 6.dp)
                .background(if (i == page) c.fill else c.sliderInactive, CircleShape))
        }
    }
}

@Composable
private fun GroupTabs(tab: Int, actions: DevActions) {
    val c = LocalDevPalette.current
    val labels = listOf(R.string.dev_tab_band, R.string.dev_tab_time, R.string.dev_tab_size)
    Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp).selectableGroup()) {
        labels.forEachIndexed { i, res ->
            val selected = i == tab
            Column(
                Modifier.heightIn(min = 48.dp)
                    .selectable(selected = selected, role = Role.Tab, onClick = { actions.onTab(i) })
                    .padding(horizontal = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(stringResource(res), color = if (selected) c.textPrimary else c.textSecondary, fontSize = 16.sp,
                    lineHeight = 22.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                    modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
                Box(Modifier.height(3.dp).width(if (selected) 56.dp else 0.dp).background(c.fill, CircleShape))
            }
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(c.divider))
}

@Composable
private fun TextAction(label: String, bold: Boolean = false, color: Color? = null, onClick: () -> Unit) {
    val c = LocalDevPalette.current
    Box(
        Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = color ?: c.accentText, fontSize = 14.sp, lineHeight = 20.sp,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium)
    }
}

@Composable
private fun Note(text: String) {
    val c = LocalDevPalette.current
    Text(text, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp))
}

// ------------------------------------------------------------------------------------------------ values

/** The value as the card shows it (the roll-off as its absolute slope). */
@Composable
internal fun valueText(spec: DevSpec, v: Float, vbAlgo: Int): String {
    fun num(x: Float, decimals: Int) = String.format(Locale.ROOT, "%.${decimals}f", x).let { if (it == "-0" || it == "-0.0") it.drop(1) else it }
    fun signed(x: Float, decimals: Int = 0): String {
        val s = num(x, decimals)
        return when {
            x > 0.0001f -> "+$s"
            x < -0.0001f -> "−" + s.removePrefix("-")
            else -> s
        }
    }
    return when (spec.unit) {
        DevUnit.HZ -> stringResource(R.string.dev_unit_hz, num(v, 0))
        DevUnit.DB -> stringResource(R.string.dev_unit_db,
            if (spec === DevParams.VOL_MAX) num(v, if (v % 1f == 0f) 0 else 1) else signed(v, if (v % 1f == 0f) 0 else 1))
        DevUnit.DB_OCT -> stringResource(R.string.dev_unit_db_oct, num(DevParams.rolloffBase(vbAlgo) + v, 0))
        DevUnit.MS -> stringResource(R.string.dev_unit_ms, num(v, 0))
        DevUnit.PCT -> stringResource(R.string.dev_unit_pct, num(v, 0))
        DevUnit.DB_PER_PCT -> stringResource(R.string.dev_unit_db_per_pct, num(v, 2))
        DevUnit.SWITCH -> stringResource(if (v >= 0.5f) R.string.dev_on else R.string.dev_off)
    }
}

/** Recommended range of [spec] as offsets (the roll-off's recommendation is absolute, 12..30 dB/oct). */
internal fun recRange(spec: DevSpec, vbAlgo: Int): ClosedFloatingPointRange<Float> =
    if (spec === DevParams.ROLLOFF) {
        val b = DevParams.rolloffBase(vbAlgo)
        (DevParams.ROLLOFF_REC_MIN - b)..(DevParams.ROLLOFF_REC_MAX - b)
    } else spec.recMin..spec.recMax

internal fun sliderRange(spec: DevSpec, vbAlgo: Int): ClosedFloatingPointRange<Float> =
    if (spec === DevParams.ROLLOFF) DevParams.rolloffRange(vbAlgo) else spec.min..spec.max

@Composable
private fun cardBg(touched: Boolean): Color {
    val c = LocalDevPalette.current
    val bg by animateColorAsState(if (touched) c.chipSelectedBg else c.bg, motion(tween(300, easing = IosEase)), label = "card")
    return bg
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CardHeader(spec: DevSpec, state: DevUiState, actions: DevActions, value: String, nonDefault: Boolean,
                       experimental: Boolean, onTitle: () -> Unit) {
    val c = LocalDevPalette.current
    val texts = DevModeTexts.of(spec)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        FlowRow(Modifier.weight(1f), verticalArrangement = Arrangement.Center) {
            Box(Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onTitle), contentAlignment = Alignment.CenterStart) {
                Text(stringResource(texts.name), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
                    fontWeight = FontWeight.Bold, modifier = Modifier.padding(end = 6.dp))
            }
            for (tag in texts.evidence.map { it.tag }.distinct()) EvidenceBadge(tag, state) { actions.onEvidence(spec) }
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(value, color = if (nonDefault) c.accentText else c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
                fontWeight = FontWeight.Bold)
            if (experimental) Text(stringResource(R.string.dev_range_experimental), color = c.warnText, fontSize = 11.sp,
                lineHeight = 16.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
internal fun badgeLabel(tag: DevEvidence, state: DevUiState): String = when (tag) {
    DevEvidence.RESEARCH -> stringResource(R.string.dev_tag_research)
    DevEvidence.MAKER -> stringResource(R.string.dev_tag_maker)
    DevEvidence.MEASURED -> if (state.measuredBadge.here) stringResource(R.string.dev_tag_measured_here)
        else stringResource(R.string.dev_tag_measured_on, state.measuredBadge.deviceName)
    DevEvidence.ESTIMATE -> stringResource(R.string.dev_tag_estimate)
}

@Composable
internal fun BadgeChip(tag: DevEvidence, label: String) {
    val c = LocalDevPalette.current
    val (bg, fg) = when (tag) {
        DevEvidence.RESEARCH -> c.researchBg to c.researchText
        DevEvidence.MAKER -> c.makerBg to c.makerText
        DevEvidence.MEASURED -> c.measuredBg to c.measuredText
        DevEvidence.ESTIMATE -> c.guessBg to c.guessText
    }
    Box(Modifier.background(bg, RoundedCornerShape(5.dp)).padding(horizontal = 6.dp, vertical = 1.dp)) {
        Text(label, color = fg, fontSize = 11.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun EvidenceBadge(tag: DevEvidence, state: DevUiState, onClick: () -> Unit) {
    val label = badgeLabel(tag, state)
    val a11y = stringResource(R.string.dev_tag_a11y, label)
    Box(
        Modifier.sizeIn(minHeight = 48.dp, minWidth = 32.dp)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = a11y }
            .padding(horizontal = 2.dp),
        contentAlignment = Alignment.Center,
    ) { BadgeChip(tag, label) }
}

@Composable
private fun Details(spec: DevSpec) {
    val c = LocalDevPalette.current
    val t = DevModeTexts.of(spec)
    Column(Modifier.fillMaxWidth().padding(top = 2.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        t.up?.let {
            val line = if (spec.isSwitch) stringResource(R.string.dev_when_on, stringResource(it))
                else stringResource(R.string.dev_raise, stringResource(it))
            Text(line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        }
        t.down?.let { Text(stringResource(R.string.dev_lower, stringResource(it)), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp) }
        t.note?.let { Text(stringResource(R.string.dev_caution, stringResource(it)), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp) }
    }
}

@Composable
private fun SliderCard(spec: DevSpec, value: Float, default: Float, state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    val touched = state.touched == spec.id
    var expanded by remember { mutableStateOf(false) }
    val range = sliderRange(spec, state.vbAlgo)
    val rec = recRange(spec, state.vbAlgo)
    val experimental = value < rec.start - 1e-4f || value > rec.endInclusive + 1e-4f
    val text = valueText(spec, value, state.vbAlgo)
    val name = stringResource(DevModeTexts.of(spec).name)
    Column(
        Modifier.padding(horizontal = 8.dp, vertical = 2.dp).fillMaxWidth()
            .background(cardBg(touched), RoundedCornerShape(14.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        CardHeader(spec, state, actions, text, spec.indexOf(value) != spec.indexOf(default), experimental) { expanded = !expanded }
        Text(stringResource(DevModeTexts.of(spec).line), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        if (expanded) Details(spec)
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            StepButton(false, stringResource(R.string.dev_minus, name), enabled = value > range.start + 1e-4f) { actions.onStep(spec, -1) }
            ValueTrack(spec, value, default, range, rec, name, text, experimental, Modifier.weight(1f).padding(horizontal = 4.dp), actions)
            StepButton(true, stringResource(R.string.dev_plus, name), enabled = value < range.endInclusive - 1e-4f) { actions.onStep(spec, 1) }
        }
    }
}

/** 44 dp round button with a minus or plus, inside a 48 dp touch target. */
@Composable
private fun StepButton(plus: Boolean, label: String, enabled: Boolean, onClick: () -> Unit) {
    val c = LocalDevPalette.current
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.94f else 1f, motion(tween(120, easing = IosEase)), label = "step")
    Box(
        Modifier.size(48.dp)
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.size(44.dp).graphicsLayer { scaleX = scale; scaleY = scale }
            .background(if (pressed) c.press else c.bg, CircleShape).border(1.dp, c.chipBorder, CircleShape),
            contentAlignment = Alignment.Center) {
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

/**
 * Track: recommended range teal, experimental range orange, a dot at the default value, a white thumb (ring orange in
 * the experimental range). Drag or tap; one haptic tick per grid step; TalkBack: range info and set-progress.
 */
@Composable
private fun ValueTrack(
    spec: DevSpec, value: Float, default: Float, range: ClosedFloatingPointRange<Float>,
    rec: ClosedFloatingPointRange<Float>, name: String, valueText: String, experimental: Boolean,
    modifier: Modifier, actions: DevActions,
) {
    val c = LocalDevPalette.current
    val haptic = LocalHapticFeedback.current
    val thumbPx = with(LocalDensity.current) { 26.dp.toPx() }
    var widthPx by remember { mutableFloatStateOf(0f) }
    var dragX by remember { mutableFloatStateOf(0f) }
    var held by remember { mutableStateOf(false) }
    var lastIndex by remember { mutableIntStateOf(spec.indexOf(value)) }
    LaunchedEffect(value) { lastIndex = spec.indexOf(value) }
    val rangeNow by rememberUpdatedState(range)
    fun frac(v: Float) = ((v - range.start) / (range.endInclusive - range.start)).coerceIn(0f, 1f)
    fun valueAt(x: Float): Float {
        val usable = (widthPx - thumbPx).coerceAtLeast(1f)
        val f = ((x - thumbPx / 2f) / usable).coerceIn(0f, 1f)
        val r = rangeNow
        return spec.snap(r.start + f * (r.endInclusive - r.start)).coerceIn(r.start, r.endInclusive)
    }
    fun emit(v: Float) {
        val idx = spec.indexOf(v)
        if (idx == lastIndex) return
        lastIndex = idx
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        actions.onValue(spec, v)
    }
    val fraction by animateFloatAsState(frac(value), motion(spring(dampingRatio = 0.85f, stiffness = Spring.StiffnessMedium)), label = "pos")
    val thumbScale by animateFloatAsState(if (held) 1.15f else 1f,
        motion(if (held) tween(120, easing = IosEase) else tween(350, easing = OvershootEase)), label = "thumb")
    val dragState = rememberDraggableState { d -> dragX += d; emit(valueAt(dragX)) }
    val rangeLabel = stringResource(if (experimental) R.string.dev_range_experimental else R.string.dev_range_recommended)
    val stateText = stringResource(R.string.dev_slider_state, valueText, rangeLabel)
    val steps = ((range.endInclusive - range.start) / spec.step).roundToInt()
    Box(
        modifier.height(48.dp)
            .onSizeChanged { widthPx = it.width.toFloat() }
            .semantics(mergeDescendants = true) {
                contentDescription = name
                stateDescription = stateText
                progressBarRangeInfo = ProgressBarRangeInfo(value, range, (steps - 1).coerceAtLeast(0))
                setProgress { target ->
                    val v = spec.snap(target).coerceIn(range.start, range.endInclusive)
                    actions.onValueStart(spec); actions.onValue(spec, v); true
                }
            }
            .draggable(
                state = dragState, orientation = Orientation.Horizontal,
                onDragStarted = { start -> held = true; dragX = start.x; actions.onValueStart(spec); emit(valueAt(start.x)) },
                onDragStopped = { held = false },
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = { held = true; tryAwaitRelease(); held = false },
                    onTap = { pos -> actions.onValueStart(spec); emit(valueAt(pos.x)) },
                )
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val r = thumbPx / 2f
            val y = size.height / 2f
            val stroke = 6.dp.toPx()
            val start = r
            val end = size.width - r
            fun x(v: Float) = start + (end - start) * frac(v)
            val rs = x(rec.start.coerceIn(range.start, range.endInclusive))
            val re = x(rec.endInclusive.coerceIn(range.start, range.endInclusive))
            val orange = ExperimentalOrange.copy(alpha = 0.45f)
            val teal = c.fill.copy(alpha = 0.32f)
            if (rs > start + 0.5f) drawLine(orange, Offset(start, y), Offset(rs, y), strokeWidth = stroke, cap = StrokeCap.Round)
            if (re < end - 0.5f) drawLine(orange, Offset(re, y), Offset(end, y), strokeWidth = stroke, cap = StrokeCap.Round)
            drawLine(teal, Offset(rs, y), Offset(re, y), strokeWidth = stroke, cap = StrokeCap.Round)
            // default value: a small dot under the track
            drawCircle(c.textSecondary, radius = 2.5.dp.toPx(), center = Offset(x(default.coerceIn(range.start, range.endInclusive)), y + 12.dp.toPx()))
        }
        Box(
            Modifier.align(Alignment.CenterStart)
                .offset { IntOffset(((widthPx - thumbPx).coerceAtLeast(0f) * fraction).roundToInt(), 0) }
                .size(26.dp)
                .graphicsLayer { scaleX = thumbScale; scaleY = thumbScale }
                .shadow(3.dp, CircleShape)
                .background(c.thumb, CircleShape)
                .border(if (held) 3.dp else 2.dp, if (experimental) ExperimentalOrange else c.accentText, CircleShape)
        )
    }
}

@Composable
private fun SwitchCard(spec: DevSpec, on: Boolean, state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    val touched = state.touched == spec.id
    var expanded by remember { mutableStateOf(false) }
    Column(
        Modifier.padding(horizontal = 8.dp, vertical = 2.dp).fillMaxWidth()
            .background(cardBg(touched), RoundedCornerShape(14.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        CardHeader(spec, state, actions, valueText(spec, if (on) 1f else 0f, state.vbAlgo), on, false) { expanded = !expanded }
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp)
                .toggleable(value = on, role = Role.Switch, onValueChange = { actions.onToggle(spec, it) }),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(stringResource(DevModeTexts.of(spec).line), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
                modifier = Modifier.weight(1f).padding(end = 12.dp))
            DevSwitch(on)
        }
        if (expanded) Details(spec)
    }
}

/** 51 x 31 dp, thumb 27 dp at 2 / 22 dp (docs/DESIGN.md 5). Visual only: the row carries the semantics. */
@Composable
private fun DevSwitch(on: Boolean) {
    val c = LocalDevPalette.current
    val x by animateDpAsState(if (on) 22.dp else 2.dp, motion(tween(350, easing = IosEase)), label = "sw")
    val track by animateColorAsState(if (on) c.fill else c.switchOff, motion(tween(300, easing = IosEase)), label = "swTrack")
    Box(Modifier.size(width = 51.dp, height = 31.dp).background(track, CircleShape)) {
        Box(Modifier.offset(x = x, y = 2.dp).size(27.dp).shadow(3.dp, CircleShape).background(c.thumb, CircleShape))
    }
}

// ------------------------------------------------------------------------------------------------ settings, bottom bar

@Composable
private fun SettingsSection(state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    Column(Modifier.fillMaxWidth().padding(top = 12.dp)) {
        Text(stringResource(R.string.dev_settings_title), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
            modifier = Modifier.padding(horizontal = 16.dp).semantics { heading() })
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.dev_gauge_style), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
                modifier = Modifier.weight(1f))
            Row(Modifier.selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip(stringResource(R.string.dev_gauge_style_basic), !state.gaugeVu) { actions.onGaugeStyle(false) }
                Chip(stringResource(R.string.dev_gauge_style_vu), state.gaugeVu) { actions.onGaugeStyle(true) }
            }
        }
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (state.hiddenCount > 0) stringResource(R.string.dev_hidden_warnings, state.hiddenCount)
                else stringResource(R.string.dev_hidden_none),
                color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, modifier = Modifier.weight(1f),
            )
            if (state.hiddenCount > 0) TextAction(stringResource(R.string.dev_hidden_restore), bold = true, onClick = actions.onRestoreWarnings)
        }
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button) { actions.onResetGroup(null) }
            .padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.dev_reset_all), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp)
        }
        Column(Modifier.fillMaxWidth().heightIn(min = 72.dp).clickable(role = Role.Button, onClick = actions.onTurnOff)
            .padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.Center) {
            Text(stringResource(R.string.dev_turn_off), color = c.danger, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.dev_turn_off_summary), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        }
    }
}

@Composable
private fun BottomBar(state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    Box(Modifier.fillMaxWidth().height(1.dp).background(c.divider))
    Row(
        Modifier.fillMaxWidth().background(c.bg).padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val holdLabel = stringResource(if (state.abHolding) R.string.dev_ab_holding else R.string.dev_ab_hold)
        val holdA11y = stringResource(R.string.dev_ab_hold_a11y)
        val bg by animateColorAsState(if (state.abHolding) c.accentText else c.fill, motion(tween(120, easing = IosEase)), label = "ab")
        val holding by rememberUpdatedState(state.abHolding)
        Box(
            Modifier.weight(1f).heightIn(min = 52.dp).background(bg, CircleShape)
                .pointerInput(Unit) {
                    detectTapGestures(onPress = {
                        actions.onAbHold(true)
                        tryAwaitRelease()
                        actions.onAbHold(false)
                    })
                }
                .semantics {
                    role = Role.Button
                    stateDescription = holdA11y
                    // TalkBack cannot hold: a double tap switches the original on and off.
                    onClick { actions.onAbHold(!holding); true }
                },
            contentAlignment = Alignment.Center,
        ) {
            Text(holdLabel, color = if (state.abHolding && !c.dark) Color.White else c.onFill, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp))
        }
        IconAction(stringResource(R.string.dev_undo), enabled = state.canUndo, onClick = actions.onUndo) { col ->
            Canvas(Modifier.size(24.dp)) {
                val s = size.width / 24f
                val p = Path().apply {
                    moveTo(9f * s, 5f * s); lineTo(4.5f * s, 9.5f * s); lineTo(9f * s, 14f * s)
                    moveTo(4.5f * s, 9.5f * s); lineTo(14f * s, 9.5f * s)
                    cubicTo(18f * s, 9.5f * s, 20f * s, 12f * s, 20f * s, 14.75f * s)
                    cubicTo(20f * s, 17.5f * s, 18f * s, 20f * s, 14f * s, 20f * s); lineTo(10f * s, 20f * s)
                }
                drawPath(p, col, style = Stroke(width = 2f * s, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
        IconAction(stringResource(R.string.dev_share), enabled = true, onClick = { actions.onShareOpen(true) }) { col ->
            Canvas(Modifier.size(24.dp)) {
                val s = size.width / 24f
                val p = Path().apply {
                    moveTo(12f * s, 3f * s); lineTo(12f * s, 15f * s)
                    moveTo(7.5f * s, 7.5f * s); lineTo(12f * s, 3f * s); lineTo(16.5f * s, 7.5f * s)
                    moveTo(6f * s, 11f * s); lineTo(5f * s, 11f * s); lineTo(5f * s, 21f * s); lineTo(19f * s, 21f * s)
                    lineTo(19f * s, 11f * s); lineTo(18f * s, 11f * s)
                }
                drawPath(p, col, style = Stroke(width = 2f * s, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
    }
}

@Composable
private fun IconAction(label: String, enabled: Boolean, onClick: () -> Unit, icon: @Composable (Color) -> Unit) {
    val c = LocalDevPalette.current
    val col = if (enabled) c.textPrimary else c.chevron
    Column(
        Modifier.sizeIn(minWidth = 64.dp, minHeight = 52.dp).clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        icon(col)
        Text(label, color = col, fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
    }
}

// ------------------------------------------------------------------------------------------------ dialogs and sheets

@Composable
private fun ConsentDialog(actions: DevActions) {
    val c = LocalDevPalette.current
    AlertDialog(
        onDismissRequest = { actions.onConsent(false) },
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = { Text(stringResource(R.string.dev_consent_title), color = c.textPrimary, fontSize = 22.sp, lineHeight = 30.sp, fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                for (res in listOf(R.string.dev_consent_1, R.string.dev_consent_2, R.string.dev_consent_3, R.string.dev_consent_4)) {
                    Row {
                        Box(Modifier.padding(top = 8.dp, end = 10.dp).size(5.dp).background(c.fill, CircleShape))
                        Text(stringResource(res), color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                    }
                }
            }
        },
        dismissButton = { OutlineButton(stringResource(R.string.dev_consent_cancel)) { actions.onConsent(false) } },
        confirmButton = { FilledButton(stringResource(R.string.dev_consent_ok)) { actions.onConsent(true) } },
    )
}

@Composable
internal fun FilledButton(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    val c = LocalDevPalette.current
    Box(
        Modifier.heightIn(min = 48.dp).background(if (enabled) c.fill else c.switchOff, CircleShape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick).padding(horizontal = 20.dp),
        contentAlignment = Alignment.Center,
    ) { Text(label, color = if (enabled) c.onFill else c.textSecondary, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold) }
}

@Composable
internal fun OutlineButton(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    val c = LocalDevPalette.current
    Box(
        Modifier.heightIn(min = 48.dp).border(1.dp, c.chipBorder, CircleShape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick).padding(horizontal = 20.dp),
        contentAlignment = Alignment.Center,
    ) { Text(label, color = if (enabled) c.textPrimary else c.chevron, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold) }
}

@Composable
private fun WarningDialog(d: DevDialog, actions: DevActions) {
    val c = LocalDevPalette.current
    var hide by remember(d) { mutableStateOf(false) }
    val (title, body, action) = when (d.warning) {
        DevWarning.BUZZ_ZONE -> Triple(R.string.dev_warn_buzz_title, stringResource(R.string.dev_warn_buzz_body), R.string.dev_warn_action_buzz)
        DevWarning.TAIL -> Triple(R.string.dev_warn_tail_title, stringResource(R.string.dev_warn_tail_body, d.tailMs), R.string.dev_warn_action_tail)
        DevWarning.VOLUME_NO_LINK -> Triple(R.string.dev_warn_volume_title, stringResource(R.string.dev_warn_volume_body), R.string.dev_warn_action_volume)
        DevWarning.NEAR_CEILING -> Triple(R.string.dev_warn_ceiling_title, stringResource(R.string.dev_warn_ceiling_body), R.string.dev_warn_action_ceiling)
        DevWarning.UNMEASURED -> Triple(R.string.dev_warn_unmeasured_title, stringResource(R.string.dev_warn_unmeasured_body), null)
    }
    AlertDialog(
        onDismissRequest = { actions.onDialogClose(false, false) },
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(c.warnDot, CircleShape))
                Spacer(Modifier.width(10.dp))
                Text(stringResource(title), color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold)
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(body, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                if (d.offerHide) {
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .toggleable(value = hide, role = Role.Checkbox, onValueChange = { hide = it }),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(checked = hide, onCheckedChange = null,
                            colors = CheckboxDefaults.colors(checkedColor = c.fill, uncheckedColor = c.chevron, checkmarkColor = c.onFill))
                        Spacer(Modifier.width(8.dp))
                        Column {
                            Text(stringResource(R.string.dev_warn_hide), color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold)
                            Text(stringResource(R.string.dev_warn_hide_note), color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp)
                        }
                    }
                }
            }
        },
        dismissButton = if (action != null) {
            { TextAction(stringResource(action), bold = true) { actions.onDialogClose(hide, true) } }
        } else null,
        confirmButton = { FilledButton(stringResource(R.string.dev_warn_ok)) { actions.onDialogClose(hide, false) } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EvidenceSheet(spec: DevSpec, state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    val texts = DevModeTexts.of(spec)
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = { actions.onEvidence(null) },
        sheetState = sheet,
        containerColor = c.bg,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        dragHandle = { Box(Modifier.padding(vertical = 10.dp).size(width = 36.dp, height = 4.dp).background(c.chipBorder, CircleShape)) },
    ) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.dev_ev_title, stringResource(texts.name)), color = c.textPrimary, fontSize = 20.sp,
                lineHeight = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            val urls = ArrayList<String>()
            for (item in texts.evidence) {
                Column(Modifier.fillMaxWidth().background(c.band, RoundedCornerShape(14.dp)).padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    BadgeChip(item.tag, badgeLabel(item.tag, state))
                    Text(stringResource(item.sentence), color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                    if (item.tag == DevEvidence.MEASURED && state.measuredBadge.here)
                        Text(stringResource(R.string.dev_ev_measured_here_note), color = c.accentText, fontSize = 13.sp, lineHeight = 18.sp)
                    for (src in item.sources) {
                        val label = stringResource(src.label)
                        val url = src.url
                        if (url == null || url in urls) {
                            Text(label, color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp)
                        } else {
                            urls += url
                            // each published source: its name and "출처 열기" (opens the browser; 48 dp target)
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text(label, color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp, modifier = Modifier.weight(1f))
                                TextAction(stringResource(R.string.dev_ev_open_source), bold = true) { actions.onOpenUrl(url) }
                            }
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End)) {
                FilledButton(stringResource(R.string.dev_ev_close)) { actions.onEvidence(null) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ShareSheet(state: DevUiState, actions: DevActions) {
    val c = LocalDevPalette.current
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = { actions.onShareOpen(false) },
        sheetState = sheet,
        containerColor = c.bg,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        dragHandle = { Box(Modifier.padding(vertical = 10.dp).size(width = 36.dp, height = 4.dp).background(c.chipBorder, CircleShape)) },
    ) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.dev_share_title), color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp,
                fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            Column(Modifier.fillMaxWidth().background(c.band, RoundedCornerShape(14.dp)).padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(R.string.dev_share_mine), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
                SelectionContainer {
                    Text(state.shareCode, color = c.accentText, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace)
                }
                Text(stringResource(R.string.dev_share_note), color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlineButton(stringResource(R.string.dev_share_copy), onClick = actions.onCopy)
                OutlineButton(stringResource(R.string.dev_share_send), onClick = actions.onSend)
            }
            OutlinedTextField(
                value = state.pasteText,
                onValueChange = actions.onPaste,
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.dev_share_paste_label)) },
                placeholder = { Text(stringResource(R.string.dev_share_paste_hint)) },
                shape = RoundedCornerShape(14.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = c.fill, unfocusedBorderColor = c.chipBorder, focusedLabelColor = c.accentText,
                    unfocusedLabelColor = c.textSecondary, cursorColor = c.fill,
                    focusedTextColor = c.textPrimary, unfocusedTextColor = c.textPrimary,
                ),
            )
            val result = state.pasteResult
            if (result is DevShareCode.Result.Ok) {
                Text(stringResource(R.string.dev_share_ok, result.model, result.appVersion, result.moved), color = c.textPrimary,
                    fontSize = 14.sp, lineHeight = 20.sp)
                if (result.model != android.os.Build.MODEL && result.model.isNotEmpty())
                    Text(stringResource(R.string.dev_share_other_device, result.model), color = c.warnText, fontSize = 13.sp, lineHeight = 18.sp)
                if (state.previewing) Text(stringResource(R.string.dev_share_previewing), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            } else if (result is DevShareCode.Result.Error) {
                Text(stringResource(shareError(result.reason)), color = c.danger, fontSize = 14.sp, lineHeight = 20.sp)
            }
            val ok = result is DevShareCode.Result.Ok
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End)) {
                OutlineButton(stringResource(if (state.previewing) R.string.dev_share_preview_stop else R.string.dev_share_preview), enabled = ok) {
                    actions.onPreview(!state.previewing)
                }
                FilledButton(stringResource(R.string.dev_share_apply), enabled = ok, onClick = actions.onApply)
            }
        }
    }
}

private fun shareError(r: DevShareCode.Reason): Int = when (r) {
    DevShareCode.Reason.EMPTY -> R.string.dev_share_err_empty
    DevShareCode.Reason.NOT_A_CODE -> R.string.dev_share_err_not
    DevShareCode.Reason.UNKNOWN_VERSION -> R.string.dev_share_err_version
    DevShareCode.Reason.BAD_CHARACTERS -> R.string.dev_share_err_chars
    DevShareCode.Reason.BAD_LENGTH, DevShareCode.Reason.TOO_LONG -> R.string.dev_share_err_length
    DevShareCode.Reason.CHECKSUM -> R.string.dev_share_err_checksum
}

/** Inline note under each graph: orange pill with a dot for a warning (never hidden), a plain line otherwise. */
@Composable
internal fun InlineNote(text: String, warning: Boolean) {
    val c = LocalDevPalette.current
    Row(
        Modifier.padding(top = 10.dp)
            .background(if (warning) c.warnBg else Color.Transparent, CircleShape)
            .padding(horizontal = if (warning) 12.dp else 0.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (warning) {
            Box(Modifier.size(8.dp).background(c.warnDot, CircleShape))
            Spacer(Modifier.width(8.dp))
        }
        Text(text, color = if (warning) c.warnText else c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
            fontWeight = if (warning) FontWeight.Medium else FontWeight.Normal)
    }
}

internal fun dbText(v: Float): String = String.format(Locale.ROOT, "%.1f", v).let {
    if (v < -0.05f) "−" + it.removePrefix("-") else it.removePrefix("-")
}


package me.timschneeberger.rootlessjamesdsp.home

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.min
import kotlin.math.sin

/*
 * The welcome (WelcomeActivity): the first-run notice of the general build as three short pages, built like the
 * spatial story (SpatialStory.kt) and shaped after other apps' first screens:
 * - one message per page, each carried by one motion (Toss "why motion in finance");
 * - what the app does as a short list of rows with a symbol each, at most three (Apple's welcome sheet; Material's
 *   "top user benefits": no more than three);
 * - the honest limits and the consent kept inside the flow instead of a wall of text (Apple HIG: licensing details
 *   integrated in a balanced way; Samsung's start process: a disclaimer shown once, confirmed at the bottom);
 * - the looking area on top, the touching area at the bottom (One UI), with a full-width call to action: "다음" on
 *   the first pages, "다음에" / "확인하고 시작하기" on the last (Toss's bottom CTA and its button words: "~하기" for
 *   the one action asked, "다음에" instead of "취소").
 * Palette, type and motion are the home screen's (docs/DESIGN.md): teal for virtual bass and the main actions,
 * purple for spatial, iOS easing; with the system animations off every stage shows one still key frame. Pages
 * scroll, so text up to 200 % never clips; the stage keeps about 40 % of the page.
 */

@Immutable
data class WelcomeState(
    val reduceMotion: Boolean = false,
    /** Name of a measured phone ("Galaxy S26 Ultra"), or null: not measured, it starts with conservative values. */
    val measuredName: String? = null,
    /** The shell permissions are granted already (no setup screens follow). */
    val permissionsReady: Boolean = false,
    /** Android 14 and later: the capture consent is asked every time processing starts. */
    val consentEveryTime: Boolean = true,
    /** Android 15 and later: "화면 공유 보호 사용 중지" in the developer options keeps notifications visible. */
    val screenShareSetting: Boolean = false,
    /** The page it opens on: 0, or [WELCOME_LAST_PAGE] when the welcome was put off once already. */
    val initialPage: Int = 0,
)

class WelcomeActions(
    /** "확인하고 시작하기". */
    val onStart: () -> Unit,
    /** "다음에". */
    val onLater: () -> Unit,
    /** Back on the first page. */
    val onLeave: () -> Unit,
    val onPrivacy: () -> Unit,
    val onLicense: () -> Unit,
)

private val Ease = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)
private const val PAGES = 3
/** The last page (the consent); where the welcome opens when it was put off once already. */
const val WELCOME_LAST_PAGE = PAGES - 1

@Composable
fun WelcomeScreen(state: WelcomeState, actions: WelcomeActions) {
    val c = rootnotePalette()
    val pager = rememberPagerState(initialPage = state.initialPage.coerceIn(0, WELCOME_LAST_PAGE)) { PAGES }
    val scope = rememberCoroutineScope()
    val last = pager.currentPage == WELCOME_LAST_PAGE
    // Back turns the page back; on the first page it leaves (WelcomeActivity decides what that means).
    BackHandler {
        if (pager.currentPage > 0) scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } else actions.onLeave()
    }
    Column(
        Modifier
            .fillMaxSize()
            .background(c.bg)
            .safeDrawingPadding()
    ) {
        WelcomeTopBar(page = pager.currentPage, reduceMotion = state.reduceMotion, showSkip = !last) {
            scope.launch { pager.animateScrollToPage(WELCOME_LAST_PAGE) }
        }
        HorizontalPager(state = pager, modifier = Modifier.weight(1f).fillMaxWidth()) { page ->
            WelcomePage(page, state, active = page == pager.currentPage, actions)
        }
        WelcomeBottomBar(last, state.reduceMotion, actions) {
            scope.launch { pager.animateScrollToPage(pager.currentPage + 1) }
        }
    }
}

// ------------------------------------------------------------------------------------------------- top and bottom

/** The brand mark as the home screen's top bar writes it, the page dots, and "건너뛰기" (kept in place when hidden). */
@Composable
private fun WelcomeTopBar(page: Int, reduceMotion: Boolean, showSkip: Boolean, onSkip: () -> Unit) {
    val c = rootnotePalette()
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .padding(start = 16.dp, end = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(10.dp).background(c.fill, CircleShape))
        Spacer(Modifier.width(8.dp))
        Text(
            stringResource(R.string.app_brand_name),
            modifier = Modifier.weight(1f).semantics { heading() },
            color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold,
            letterSpacing = (-0.3).sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        Dots(page, reduceMotion)
        TextAction(stringResource(R.string.welcome_skip), visible = showSkip, onClick = onSkip)
    }
}

@Composable
private fun Dots(page: Int, reduceMotion: Boolean) {
    val c = rootnotePalette()
    val label = stringResource(R.string.welcome_pages_a11y, page + 1, PAGES)
    Row(
        Modifier
            .padding(horizontal = 8.dp)
            .semantics(mergeDescendants = true) { contentDescription = label },
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        for (i in 0 until PAGES) {
            val on = i == page
            val w by animateFloatAsState(if (on) 18f else 6f, tween(if (reduceMotion) 0 else 300, easing = Ease), label = "dot")
            Box(Modifier.size(width = w.dp, height = 6.dp).background(if (on) c.fill else c.divider, CircleShape))
        }
    }
}

/**
 * The bottom call to action, outside the pages so it never scrolls away: one full-width "다음", and on the last page
 * the consent line with "다음에" and "확인하고 시작하기". The change fades out and in (150 + 150 ms, like the home
 * screen's text changes).
 */
@Composable
private fun WelcomeBottomBar(last: Boolean, reduceMotion: Boolean, actions: WelcomeActions, onNext: () -> Unit) {
    val c = rootnotePalette()
    AnimatedContent(
        targetState = last,
        transitionSpec = {
            if (reduceMotion) EnterTransition.None togetherWith ExitTransition.None
            else fadeIn(tween(150, delayMillis = 150, easing = LinearEasing)) togetherWith fadeOut(tween(150, easing = LinearEasing))
        },
        contentAlignment = Alignment.BottomCenter,
        label = "cta",
    ) { isLast ->
        Column(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (isLast) {
                Text(stringResource(R.string.welcome_consent), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PillButton(stringResource(R.string.welcome_later), filled = false, Modifier.weight(1f), actions.onLater)
                    PillButton(stringResource(R.string.welcome_start), filled = true, Modifier.weight(2f), actions.onStart)
                }
            } else {
                PillButton(stringResource(R.string.welcome_next), filled = true, Modifier.fillMaxWidth(), onNext)
            }
        }
    }
}

@Composable
private fun PillButton(label: String, filled: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val c = rootnotePalette()
    Box(
        modifier
            .heightIn(min = 48.dp)
            .clip(CircleShape)
            .then(
                if (filled) Modifier.background(c.fill, CircleShape)
                else Modifier.border(1.dp, c.chipBorder, CircleShape)
            )
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            // text on the teal fill: the theme's onPrimary (white in light mode, deep teal in dark mode, where white on
            // #2BB0AA would be 2.6:1); devmode's onFill writes the same values
            color = if (filled) colorResource(R.color.rn_m3_onPrimary) else c.textPrimary,
            fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center,
        )
    }
}

/** A text action as the home screen's banner actions write it; [visible] false keeps its place, silent and inert. */
@Composable
private fun TextAction(label: String, visible: Boolean = true, onClick: () -> Unit) {
    val c = rootnotePalette()
    Box(
        Modifier
            .heightIn(min = 48.dp)
            .then(
                if (visible) Modifier.clickable(role = Role.Button, onClick = onClick)
                else Modifier.alpha(0f).clearAndSetSemantics { }
            )
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = c.accentText, fontSize = 14.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium)
    }
}

// ------------------------------------------------------------------------------------------------- pages

@Composable
private fun WelcomePage(page: Int, state: WelcomeState, active: Boolean, actions: WelcomeActions) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val stageH = maxHeight * 0.42f
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            WelcomeStage(page, state, active, Modifier.fillMaxWidth().height(stageH))
            Spacer(Modifier.height(4.dp))
            when (page) {
                0 -> Appear(state.reduceMotion) { HelloText(state) }
                1 -> KnowText()
                else -> ReadyText(state, actions)
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

/** The first page's words come in once, after the picture: a short rise and fade (350 ms, iOS easing). */
@Composable
private fun Appear(reduceMotion: Boolean, content: @Composable () -> Unit) {
    var shown by rememberSaveable { mutableStateOf(reduceMotion) }
    LaunchedEffect(Unit) { shown = true }
    val p by animateFloatAsState(
        if (shown) 1f else 0f, tween(if (reduceMotion) 0 else 350, delayMillis = if (reduceMotion) 0 else 150, easing = Ease),
        label = "appear",
    )
    Box(Modifier.graphicsLayer { alpha = p; translationY = (1f - p) * 12.dp.toPx() }) { content() }
}

@Composable
private fun Heading(text: String) {
    val c = rootnotePalette()
    Text(
        text, modifier = Modifier.semantics { heading() },
        color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun Body(text: String) {
    val c = rootnotePalette()
    Text(text, color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
}

/** 1: hello, and what the app does (two features and how it starts on this phone). */
@Composable
private fun HelloText(state: WelcomeState) {
    val c = rootnotePalette()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Heading(stringResource(R.string.welcome_hello_title))
        Body(stringResource(R.string.welcome_hello_body))
        Column {
            InfoRow(Glyph.BASS, c.fill, stringResource(R.string.home_tab_bass), stringResource(R.string.welcome_bass_body))
            InfoRow(Glyph.SPACE, c.xtcFill, stringResource(R.string.home_tab_spatial), stringResource(R.string.welcome_spatial_body))
            InfoRow(
                Glyph.PHONE, c.textSecondary, stringResource(R.string.welcome_device_title),
                state.measuredName?.let { stringResource(R.string.welcome_device_measured, it) }
                    ?: stringResource(R.string.welcome_device_unmeasured),
            )
        }
    }
}

/** 2: the honest limits, with the one fix there is (exclude apps) and the one warning that cannot be hidden. */
@Composable
private fun KnowText() {
    val c = rootnotePalette()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Heading(stringResource(R.string.welcome_know_title))
        Body(stringResource(R.string.welcome_know_body))
        Column {
            InfoRow(Glyph.FLASK, c.textSecondary, stringResource(R.string.welcome_know_experimental_title),
                stringResource(R.string.welcome_know_experimental_body))
            InfoRow(Glyph.CLOCK, c.fill, stringResource(R.string.welcome_know_delay_title),
                stringResource(R.string.welcome_know_delay_body))
            InfoRow(Glyph.SPEAKER, c.textSecondary, stringResource(R.string.welcome_know_speaker_title),
                stringResource(R.string.welcome_know_speaker_body))
            InfoRow(Glyph.APPS, c.textSecondary, stringResource(R.string.welcome_know_others_title),
                stringResource(R.string.welcome_know_others_body))
        }
        WarningPill(stringResource(R.string.welcome_know_volume))
    }
}

/** 3: what happens next on this phone (only the lines that apply to its Android version), privacy, licence. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ReadyText(state: WelcomeState, actions: WelcomeActions) {
    val c = rootnotePalette()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Heading(stringResource(R.string.welcome_ready_title))
        Body(stringResource(R.string.welcome_ready_body))
        Column {
            if (state.permissionsReady)
                InfoRow(Glyph.CHECK, c.fill, stringResource(R.string.welcome_ready_granted_title),
                    stringResource(R.string.welcome_ready_granted_body))
            else
                InfoRow(Glyph.KEY, c.fill, stringResource(R.string.welcome_ready_grant_title),
                    stringResource(R.string.welcome_ready_grant_body))
            InfoRow(
                Glyph.DIALOG, c.textSecondary, stringResource(R.string.welcome_ready_capture_title),
                stringResource(if (state.consentEveryTime) R.string.welcome_ready_capture_body_14 else R.string.welcome_ready_capture_body_old),
            )
            if (state.screenShareSetting)
                InfoRow(Glyph.TOGGLE, c.textSecondary, stringResource(R.string.welcome_ready_a15_title),
                    stringResource(R.string.welcome_ready_a15_body))
            InfoRow(Glyph.LOCK, c.textSecondary, stringResource(R.string.welcome_ready_privacy_title),
                stringResource(R.string.welcome_ready_privacy_body)) {
                FlowRow(Modifier.offset(x = (-12).dp)) {
                    TextAction(stringResource(R.string.welcome_ready_privacy_more), onClick = actions.onPrivacy)
                    TextAction(stringResource(R.string.welcome_ready_license), onClick = actions.onLicense)
                }
            }
        }
        Text(stringResource(R.string.welcome_ready_legal), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
    }
}

/**
 * A row: a 24 dp symbol (2 dp round strokes, docs/DESIGN.md 7), the title (16/22 bold) and its line (13/18), like
 * the home screen's navigation rows without the chevron. No dividers, no card. [extra] goes under the line (links).
 */
@Composable
private fun InfoRow(symbol: Glyph, tint: Color, title: String, body: String, extra: (@Composable () -> Unit)? = null) {
    val c = rootnotePalette()
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .then(if (extra == null) Modifier.semantics(mergeDescendants = true) { } else Modifier)
            .padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Canvas(Modifier.padding(top = 1.dp).size(24.dp)) { glyph(symbol, tint) }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            Text(body, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            extra?.invoke()
        }
    }
}

/** docs/DESIGN.md 5 "인라인 경고": a warning pill with an orange dot and one line; it cannot be dismissed. */
@Composable
private fun WarningPill(text: String) {
    Row(
        Modifier
            .padding(top = 4.dp)
            .background(colorResource(R.color.rn_warn_bg), CircleShape)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).background(colorResource(R.color.rn_warn_dot), CircleShape))
        Spacer(Modifier.width(8.dp))
        Text(text, color = colorResource(R.color.rn_warn_text), fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium)
    }
}

// ------------------------------------------------------------------------------------------------- the stage

/** Stage colours: teal = virtual bass and progress, purple = spatial. */
private class HeroColors(val bass: Color, val space: Color, val ink: Color, val soft: Color, val line: Color, val bg: Color)

private val KEY_FRAMES = floatArrayOf(0.8f, 0.5f, 0.9f)
private val PERIODS = intArrayOf(4200, 3600, 4200)

@Composable
private fun WelcomeStage(page: Int, state: WelcomeState, active: Boolean, modifier: Modifier) {
    val c = rootnotePalette()
    val colors = remember(c) { HeroColors(c.fill, c.xtcFill, c.textPrimary, c.textSecondary, c.chipBorder, c.bg) }
    // One clock per page (0..1, looping from the page's key frame); a still key frame with the animations off or
    // off-screen. Read only while drawing, so a frame never recomposes the page.
    val clock: State<Float> = if (state.reduceMotion || !active) {
        remember(page) { mutableFloatStateOf(KEY_FRAMES[page]) }
    } else {
        val inf = rememberInfiniteTransition(label = "welcome$page")
        inf.animateFloat(
            KEY_FRAMES[page], KEY_FRAMES[page] + 1f,
            infiniteRepeatable(tween(PERIODS[page], easing = LinearEasing), RepeatMode.Restart), label = "t$page",
        )
    }
    val description = stringResource(
        when (page) {
            0 -> R.string.welcome_hero_hello_a11y
            1 -> R.string.welcome_hero_delay_a11y
            else -> R.string.welcome_hero_ready_a11y
        }
    )
    val labels = when (page) {
        0 -> listOf(stringResource(R.string.home_tab_bass), stringResource(R.string.home_tab_spatial))
        1 -> listOf(stringResource(R.string.welcome_hero_original), stringResource(R.string.app_brand_name),
            stringResource(R.string.welcome_hero_delay))
        else -> listOf(stringResource(R.string.welcome_step_grant), stringResource(R.string.welcome_step_allow),
            stringResource(R.string.welcome_step_listen))
    }
    val measurer = rememberTextMeasurer()
    Box(modifier.clip(RoundedCornerShape(20.dp)).background(c.band)) {
        Canvas(Modifier.fillMaxSize().padding(16.dp).semantics { contentDescription = description }) {
            val t = clock.value % 1f
            when (page) {
                0 -> heroHello(t, colors, measurer, labels)
                1 -> heroDelay(t, colors, measurer, labels)
                else -> heroReady(t, colors, measurer, labels)
            }
        }
    }
}

private fun smooth(x: Float): Float { val v = x.coerceIn(0f, 1f); return v * v * (3f - 2f * v) }

/** A stage label (12/16 sp Medium, grows with the font size). [vAlign]: 0 = [at] is its top, 1 = its bottom. */
private fun DrawScope.label(measurer: TextMeasurer, text: String, color: Color, at: Offset, maxWidth: Float = size.width,
                            center: Boolean = false, vAlign: Float = 0f) {
    if (color.alpha <= 0.01f || text.isEmpty()) return
    val r = measurer.measure(
        text,
        TextStyle(fontSize = 12.sp, lineHeight = 16.sp, color = color, fontWeight = FontWeight.Medium,
            textAlign = if (center) TextAlign.Center else TextAlign.Start),
        maxLines = 2,
        constraints = Constraints(maxWidth = maxWidth.toInt().coerceAtLeast(1)),
    )
    val x = if (center) at.x - r.size.width / 2f else at.x
    val y = at.y - r.size.height * vAlign
    drawText(r, topLeft = Offset(x.coerceIn(0f, (size.width - r.size.width).coerceAtLeast(0f)), y.coerceAtLeast(0f)))
}

/**
 * 1 (hello): the phone from the front with a song playing. First only its small sound (short grey arcs); then the
 * bass it cannot play spreads from the bottom speaker in large teal rings; then purple arcs open the sound out to
 * both sides. Everything fades a little before the loop starts again.
 */
private fun DrawScope.heroHello(t: Float, col: HeroColors, measurer: TextMeasurer, labels: List<String>) {
    val unit = min(size.width / 10f, size.height / 7f)
    val cx = size.width / 2f
    val cy = size.height * 0.5f
    val pw = unit * 2.2f
    val ph = unit * 4.4f
    val top = cy - ph / 2f
    val bottom = cy + ph / 2f
    val end = 1f - smooth((t - 0.9f) / 0.1f)
    val bassIn = smooth((t - 0.2f) / 0.2f) * end
    val spaceIn = smooth((t - 0.48f) / 0.2f) * end
    val ear = Offset(cx, top + unit * 0.25f)
    val foot = Offset(cx, bottom)

    // bass: large slow rings from the bottom speaker
    if (bassIn > 0f) {
        for (k in 0 until 2) {
            val p = ((t * 2f) + k * 0.5f) % 1f
            drawCircle(col.bass.copy(alpha = bassIn * (1f - p) * 0.85f), unit * (0.6f + 2.8f * p), foot, style = Stroke(4.dp.toPx()))
        }
    }
    // spatial: purple arcs moving out to both sides
    if (spaceIn > 0f) {
        val reach = size.width / 2f - unit * 0.3f
        val from = pw / 2f + unit * 0.35f
        for (k in 0 until 3) {
            val p = ((t * 1.5f) + k / 3f) % 1f
            val r = from + (reach - from) * p * spaceIn
            val a = spaceIn * (1f - p) * 0.9f
            val stroke = Stroke(2.5.dp.toPx(), cap = StrokeCap.Round)
            drawArc(col.space.copy(alpha = a), -32f, 64f, false, Offset(cx - r, cy - r), Size(2 * r, 2 * r), style = stroke)
            drawArc(col.space.copy(alpha = a), 148f, 64f, false, Offset(cx - r, cy - r), Size(2 * r, 2 * r), style = stroke)
        }
    }
    // the small sound of the phone alone: short thin arcs, quieter once the bass is filled in
    val small = 1f - 0.6f * bassIn
    for (k in 0 until 3) {
        val p = ((t * 3f) + k / 3f) % 1f
        val r = unit * (0.25f + 0.55f * p)
        val a = (1f - p) * 0.75f * small
        val stroke = Stroke(1.5.dp.toPx(), cap = StrokeCap.Round)
        drawArc(col.soft.copy(alpha = a), 215f, 110f, false, Offset(ear.x - r, ear.y - r), Size(2 * r, 2 * r), style = stroke)
        drawArc(col.soft.copy(alpha = a), 35f, 110f, false, Offset(foot.x - r, foot.y - r), Size(2 * r, 2 * r), style = stroke)
    }
    // the phone, front view: body, screen, a small "now playing" level, earpiece slot and bottom speaker holes
    drawRoundRect(col.ink.copy(alpha = 0.88f), Offset(cx - pw / 2f, top), Size(pw, ph), CornerRadius(unit * 0.42f))
    drawRoundRect(
        col.bg.copy(alpha = 0.22f), Offset(cx - pw / 2f + unit * 0.14f, top + unit * 0.5f),
        Size(pw - unit * 0.28f, ph - unit * 0.95f), CornerRadius(unit * 0.22f),
    )
    for (i in 0 until 4) {
        val lv = 0.35f + 0.65f * (0.5f + 0.5f * sin(2f * PI.toFloat() * (t * 2f + i * 0.27f)))
        val h = unit * 0.9f * lv
        val x = cx + (i - 1.5f) * unit * 0.34f
        drawLine(col.bg.copy(alpha = 0.75f), Offset(x, cy + unit * 0.45f), Offset(x, cy + unit * 0.45f - h), unit * 0.14f, StrokeCap.Round)
    }
    drawLine(col.bg.copy(alpha = 0.6f), Offset(cx - unit * 0.3f, ear.y), Offset(cx + unit * 0.3f, ear.y), unit * 0.08f, StrokeCap.Round)
    for (i in -2..2) drawCircle(col.bg.copy(alpha = 0.6f), unit * 0.045f, Offset(cx + i * unit * 0.14f, bottom - unit * 0.2f))
    // what each colour is (never the colour alone)
    label(measurer, labels.getOrElse(0) { "" }, col.bass.copy(alpha = bassIn), Offset(0f, bottom), size.width / 3f, vAlign = 1f)
    val spaceText = labels.getOrElse(1) { "" }
    val w = measurer.measure(spaceText, TextStyle(fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium),
        maxLines = 2, constraints = Constraints(maxWidth = (size.width / 3f).toInt().coerceAtLeast(1))).size.width
    label(measurer, spaceText, col.space.copy(alpha = spaceIn), Offset(size.width - w, top), size.width / 3f)
}

/**
 * 2 (good to know): the original sound and the processed sound run side by side; the processed one follows about
 * 0.15 s later, marked between the two onsets. The waves repeat every loop, so the loop is seamless; the mark fades
 * at its ends.
 */
private fun DrawScope.heroDelay(t: Float, col: HeroColors, measurer: TextMeasurer, labels: List<String>) {
    val w = size.width
    val h = size.height
    val spacing = w * 0.46f
    val delay = w * 0.13f
    val laneA = h * 0.34f
    val laneB = h * 0.76f
    val amp = h * 0.11f
    val shift = w * 0.18f + t * spacing
    fun burst(x: Float): Float {
        val local = (((x - shift) % spacing) + spacing) % spacing
        val env = exp(-local / (spacing * 0.09f)) * smooth(local / (spacing * 0.015f))
        return env * sin(local / spacing * 2f * PI.toFloat() * 10f)
    }
    fun lane(y: Float, offset: Float, color: Color) {
        drawLine(col.line, Offset(0f, y), Offset(w, y), 1.dp.toPx())
        val p = Path()
        val n = 180
        for (i in 0..n) {
            val x = w * i / n
            val v = y - amp * burst(x - offset)
            if (i == 0) p.moveTo(x, v) else p.lineTo(x, v)
        }
        drawPath(p, color, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
    lane(laneA, 0f, col.ink.copy(alpha = 0.7f))
    lane(laneB, delay, col.bass)
    label(measurer, labels.getOrElse(0) { "" }, col.soft, Offset(0f, laneA - amp - 6.dp.toPx()), vAlign = 1f)
    label(measurer, labels.getOrElse(1) { "" }, col.bass, Offset(0f, laneB - amp - 6.dp.toPx()), vAlign = 1f)
    // the mark between the two onsets
    val a = smooth(t / 0.1f) * (1f - smooth((t - 0.85f) / 0.15f))
    if (a > 0f) {
        val xa = shift
        val xb = shift + delay
        val mid = (laneA + laneB) / 2f + amp * 0.2f
        val dash = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))
        drawLine(col.soft.copy(alpha = 0.8f * a), Offset(xa, laneA), Offset(xa, mid), 1.5.dp.toPx(), pathEffect = dash)
        drawLine(col.bass.copy(alpha = 0.8f * a), Offset(xb, mid), Offset(xb, laneB), 1.5.dp.toPx(), pathEffect = dash)
        drawLine(col.ink.copy(alpha = 0.8f * a), Offset(xa, mid), Offset(xb, mid), 2.dp.toPx(), StrokeCap.Round)
        val tick = 5.dp.toPx()
        drawLine(col.ink.copy(alpha = 0.8f * a), Offset(xa, mid - tick), Offset(xa, mid + tick), 2.dp.toPx(), StrokeCap.Round)
        drawLine(col.ink.copy(alpha = 0.8f * a), Offset(xb, mid - tick), Offset(xb, mid + tick), 2.dp.toPx(), StrokeCap.Round)
        label(measurer, labels.getOrElse(2) { "" }, col.ink.copy(alpha = a), Offset(xb + 6.dp.toPx(), mid), w / 3f, vAlign = 0.5f)
    }
}

/**
 * 3 (ready): three steps on a line, "권한 한 번" -> "켤 때 확인" -> "듣기". A dot travels from step to step and lights
 * each one it reaches; before the loop starts again the lights fade.
 */
private fun DrawScope.heroReady(t: Float, col: HeroColors, measurer: TextMeasurer, labels: List<String>) {
    val w = size.width
    val unit = min(w / 10f, size.height / 7f)
    val y = size.height * 0.38f
    val xs = floatArrayOf(w * 0.17f, w * 0.5f, w * 0.83f)
    val r = unit * 0.9f
    val p = when {
        t < 0.12f -> 0f
        t < 0.42f -> smooth((t - 0.12f) / 0.3f)
        t < 0.52f -> 1f
        t < 0.82f -> 1f + smooth((t - 0.52f) / 0.3f)
        else -> 2f
    }
    val end = 1f - smooth((t - 0.94f) / 0.06f)
    fun xAt(q: Float): Float = if (q <= 1f) xs[0] + (xs[1] - xs[0]) * q else xs[1] + (xs[2] - xs[1]) * (q - 1f)
    // the track and the part already travelled
    drawLine(col.line, Offset(xs[0], y), Offset(xs[2], y), 2.dp.toPx(), StrokeCap.Round)
    drawLine(col.bass.copy(alpha = end), Offset(xs[0], y), Offset(xAt(p), y), 3.dp.toPx(), StrokeCap.Round)
    val glyphs = listOf(Glyph.KEY, Glyph.DIALOG, Glyph.WAVES)
    for (i in 0 until 3) {
        val lit = (if (i == 0) 1f else smooth((p - (i - 0.15f)) / 0.15f) * end).coerceIn(0f, 1f)
        val center = Offset(xs[i], y)
        drawCircle(col.bg, r, center)
        drawCircle(col.bass.copy(alpha = 0.14f * lit), r, center)
        drawCircle(lerp(col.line, col.bass, lit), r, center, style = Stroke(2.dp.toPx()))
        val box = r * 1.15f
        glyph(glyphs[i], lerp(col.soft, col.bass, lit), Offset(center.x - box / 2f, center.y - box / 2f), box)
        label(
            measurer, labels.getOrElse(i) { "" }, lerp(col.soft, col.ink, lit),
            Offset(center.x, y + r + 8.dp.toPx()), w / 3f - 8.dp.toPx(), center = true,
        )
    }
    // the travelling dot (between the steps only)
    if (p > 0.02f && p < 1.98f && kotlin.math.abs(p - 1f) > 0.02f) drawCircle(col.bass, unit * 0.16f, Offset(xAt(p), y))
}

private fun lerp(a: Color, b: Color, f: Float) = Color(
    a.red + (b.red - a.red) * f, a.green + (b.green - a.green) * f, a.blue + (b.blue - a.blue) * f,
    a.alpha + (b.alpha - a.alpha) * f,
)

// ------------------------------------------------------------------------------------------------- symbols

/** Symbols drawn on a 24-unit grid with 2 dp round strokes (docs/DESIGN.md 7: no emoji, line icons). */
private enum class Glyph { BASS, SPACE, PHONE, FLASK, CLOCK, SPEAKER, APPS, KEY, CHECK, DIALOG, TOGGLE, LOCK, WAVES }

private fun DrawScope.glyph(g: Glyph, color: Color, origin: Offset = Offset.Zero, box: Float = size.minDimension) {
    val s = box / 24f
    val width = 2.dp.toPx()
    val st = Stroke(width = width, cap = StrokeCap.Round, join = StrokeJoin.Round)
    fun o(x: Float, y: Float) = Offset(origin.x + x * s, origin.y + y * s)
    fun line(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, o(x1, y1), o(x2, y2), width, StrokeCap.Round)
    fun poly(vararg pts: Float, close: Boolean = false) {
        val p = Path()
        val first = o(pts[0], pts[1])
        p.moveTo(first.x, first.y)
        var i = 2
        while (i + 1 < pts.size) {
            val q = o(pts[i], pts[i + 1])
            p.lineTo(q.x, q.y)
            i += 2
        }
        if (close) p.close()
        drawPath(p, color, style = st)
    }
    fun rrect(l: Float, t: Float, r: Float, b: Float, rad: Float) =
        drawRoundRect(color, o(l, t), Size((r - l) * s, (b - t) * s), CornerRadius(rad * s), style = st)
    fun ring(x: Float, y: Float, r: Float) = drawCircle(color, r * s, o(x, y), style = st)
    fun dot(x: Float, y: Float, r: Float) = drawCircle(color, r * s, o(x, y))
    fun arc(x: Float, y: Float, r: Float, start: Float, sweep: Float) =
        drawArc(color, start, sweep, false, o(x - r, y - r), Size(2 * r * s, 2 * r * s), style = st)
    when (g) {
        Glyph.BASS -> {
            val p = Path()
            for (i in 0..40) {
                val q = o(2f + 20f * i / 40f, 12f - 6f * sin(2f * PI.toFloat() * i / 40f))
                if (i == 0) p.moveTo(q.x, q.y) else p.lineTo(q.x, q.y)
            }
            drawPath(p, color, style = st)
        }
        Glyph.SPACE -> {
            dot(12f, 12f, 2f)
            arc(12f, 12f, 6f, 145f, 70f); arc(12f, 12f, 6f, -35f, 70f)
            arc(12f, 12f, 10f, 150f, 60f); arc(12f, 12f, 10f, -30f, 60f)
        }
        Glyph.PHONE -> { rrect(7f, 2f, 17f, 22f, 2.5f); line(10.5f, 18.5f, 13.5f, 18.5f) }
        Glyph.FLASK -> {
            line(9f, 3f, 15f, 3f)
            poly(10f, 3f, 10f, 9.5f, 4.5f, 19f, 5.5f, 21f, 18.5f, 21f, 19.5f, 19f, 14f, 9.5f, 14f, 3f)
            line(7f, 15f, 17f, 15f)
        }
        Glyph.CLOCK -> { ring(12f, 12f, 9f); poly(12f, 7f, 12f, 12f, 15.5f, 14f) }
        Glyph.SPEAKER -> {
            poly(4f, 9f, 8f, 9f, 13f, 5f, 13f, 19f, 8f, 15f, 4f, 15f, close = true)
            arc(13f, 12f, 4f, -45f, 90f); arc(13f, 12f, 7.5f, -45f, 90f)
        }
        Glyph.APPS -> { rrect(3f, 8f, 14f, 19f, 2.5f); rrect(10f, 3f, 21f, 14f, 2.5f) }
        Glyph.KEY -> { ring(8f, 16f, 4f); line(10.8f, 13.2f, 20f, 4f); line(16f, 8f, 18.5f, 10.5f); line(18.5f, 5.5f, 20.5f, 7.5f) }
        Glyph.CHECK -> { ring(12f, 12f, 9f); poly(8f, 12.5f, 11f, 15.5f, 16.5f, 9.5f) }
        Glyph.DIALOG -> { rrect(3f, 5f, 21f, 19f, 3f); line(7f, 10f, 17f, 10f); line(7f, 14f, 12f, 14f) }
        Glyph.TOGGLE -> { rrect(2f, 7f, 22f, 17f, 5f); dot(17f, 12f, 2.6f) }
        Glyph.LOCK -> {
            rrect(5f, 11f, 19f, 21f, 2.5f)
            line(8f, 11f, 8f, 8f); line(16f, 11f, 16f, 8f); arc(12f, 8f, 4f, 180f, 180f)
            dot(12f, 16f, 1.2f)
        }
        Glyph.WAVES -> {
            dot(5f, 12f, 1.6f)
            arc(5f, 12f, 5f, -40f, 80f); arc(5f, 12f, 10f, -35f, 70f); arc(5f, 12f, 15f, -30f, 60f)
        }
    }
}

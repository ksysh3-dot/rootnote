package me.timschneeberger.rootlessjamesdsp.home

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterExitState
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
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
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
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
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
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
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.keepWords
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.min
import kotlin.math.sin

/*
 * The welcome (WelcomeActivity): the first-run notice of the general build as seven full-screen pages, one message
 * each, shaped after other apps' first screens (Toss, Samsung Smart Switch):
 * 1 "반가워요!" alone in the middle with the app's mark drawn in motion; 2 virtual bass; 3 spatial; 4 the delay and
 * its fix; 5 what to know before turning it on; 6 setup; 7 "이제 시작해 볼까요?" — what starting does, privacy and
 * the licence, answered by "나중에" / "확인하고 시작하기" (Toss's bottom CTA: "~하기" for the one action asked).
 * Each page: a symbol, a large title of one or two lines, a short line, then its picture or its few rows; the
 * looking area on top, the touching area at the bottom (One UI); text and buttons share one 24 dp column. Each
 * picture plays once when its page is reached, then rests (Toss "why motion in finance": motion that answers the
 * swipe). Teal marks virtual bass and the main action, purple marks spatial; everything else is neutral. Palette,
 * type and motion are the home screen's (docs/DESIGN.md); with the system animations off every picture shows its
 * resting frame. Pages scroll, so text up to 200 % never clips; pictures keep one height (40 % of the screen).
 *
 * Spacing is grouped on the 4 dp grid rather than even: the head holds together (symbol 16, title 8, line), and
 * 24 dp separates it from what the page shows; a caption sits 12 dp under its picture. When a page is taller than
 * the screen (large fonts, small phones), a hairline under the top bar and over the buttons says the page goes on
 * (an iOS scroll edge); at the usual sizes nothing scrolls and no line shows.
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
    /** "나중에". */
    val onLater: () -> Unit,
    /** Back on the first page. */
    val onLeave: () -> Unit,
    val onPrivacy: () -> Unit,
    val onLicense: () -> Unit,
)

private val Ease = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)
/** docs/DESIGN.md 6 OvershootEase: a pressed button settles back with a slight bounce, like the home screen's chips. */
private val Overshoot = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)
private const val PAGES = 7
/** The last page (the consent); where the welcome opens when it was put off once already. */
const val WELCOME_LAST_PAGE = PAGES - 1

/** Pages: hello, virtual bass, spatial, the delay, good to know, setup, start (the consent). */
private const val P_HELLO = 0
private const val P_BASS = 1
private const val P_SPACE = 2
private const val P_DELAY = 3
private const val P_KNOW = 4
private const val P_SETUP = 5

@Composable
fun WelcomeScreen(state: WelcomeState, actions: WelcomeActions) {
    val c = rootnotePalette()
    val pager = rememberPagerState(initialPage = state.initialPage.coerceIn(0, WELCOME_LAST_PAGE)) { PAGES }
    val scope = rememberCoroutineScope()
    // One scroll position per page, held here so the bars can tell whether the page under them goes on (each under its
    // own key, so a restored state goes back to its own page).
    val scrolls = List(PAGES) { key(it) { rememberScrollState() } }
    val scroll = scrolls[pager.currentPage]
    // The answers appear only once the last page has settled, never in the middle of a swipe.
    val last = pager.settledPage == WELCOME_LAST_PAGE
    // Back turns the page back; on the first page it leaves (WelcomeActivity decides what that means).
    BackHandler {
        if (pager.currentPage > 0) scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } else actions.onLeave()
    }
    BoxWithConstraints(
        Modifier
            .fillMaxSize()
            .background(c.bg)
            .safeDrawingPadding()
    ) {
        val stageHeight = maxHeight * 0.4f
        Column(Modifier.fillMaxSize()) {
            WelcomeTopBar(page = pager.currentPage, reduceMotion = state.reduceMotion, showSkip = !last) {
                scope.launch { pager.animateScrollToPage(WELCOME_LAST_PAGE) }
            }
            ScrollEdge(visible = scroll.canScrollBackward, state.reduceMotion)
            HorizontalPager(state = pager, modifier = Modifier.weight(1f).fillMaxWidth()) { page ->
                WelcomePage(page, state, active = page == pager.settledPage, stageHeight, scrolls[page], actions)
            }
            ScrollEdge(visible = scroll.canScrollForward, state.reduceMotion)
            WelcomeBottomBar(last, state.reduceMotion, actions) {
                scope.launch { pager.animateScrollToPage(pager.currentPage + 1) }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------- top and bottom

/** Nothing but where you are and "건너뛰기" (kept in place, silent, on the last page): each page is one message. */
@Composable
private fun WelcomeTopBar(page: Int, reduceMotion: Boolean, showSkip: Boolean, onSkip: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .padding(start = 16.dp, end = 12.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Dots(page, reduceMotion)
        Spacer(Modifier.weight(1f))
        TextAction(stringResource(R.string.welcome_skip), visible = showSkip, onClick = onSkip)
    }
}

/**
 * A 1 dp rn_divider hairline that fades in (300 ms, the colour timing of docs/DESIGN.md 6) while the page under a
 * bar has more to show in that direction. Always laid out, so showing it never moves anything.
 */
@Composable
private fun ScrollEdge(visible: Boolean, reduceMotion: Boolean) {
    val c = rootnotePalette()
    val a by animateFloatAsState(if (visible) 1f else 0f, tween(if (reduceMotion) 0 else 300, easing = Ease), label = "edge")
    Box(Modifier.fillMaxWidth().height(1.dp).graphicsLayer { alpha = a }.background(c.divider))
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
            Box(Modifier.size(width = w.dp, height = 6.dp).background(if (on) c.fill else c.sliderInactive, CircleShape))
        }
    }
}

/**
 * The bottom call to action, outside the pages so it never scrolls away, in the same 24 dp column as the text: one
 * full-width "다음", and on the last page "나중에" and "확인하고 시작하기". The change fades out and in (150 + 150 ms,
 * like the home screen's text changes).
 */
@OptIn(ExperimentalAnimationApi::class)
@Composable
private fun WelcomeBottomBar(last: Boolean, reduceMotion: Boolean, actions: WelcomeActions, onNext: () -> Unit) {
    AnimatedContent(
        targetState = last,
        transitionSpec = {
            if (reduceMotion) EnterTransition.None togetherWith ExitTransition.None
            else fadeIn(tween(150, delayMillis = 150, easing = LinearEasing)) togetherWith fadeOut(tween(150, easing = LinearEasing))
        },
        contentAlignment = Alignment.BottomCenter,
        label = "cta",
    ) { isLast ->
        // Buttons answer only while fully shown: never while fading in or out (an invisible "확인하고 시작하기"
        // must not catch a quick second tap on "다음").
        val shown = transition.currentState == EnterExitState.Visible && transition.targetState == EnterExitState.Visible
        Column(
            Modifier.fillMaxWidth().padding(start = 24.dp, end = 24.dp, top = 8.dp, bottom = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (isLast) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PillButton(stringResource(R.string.welcome_later), filled = false, shown, reduceMotion, Modifier.weight(1f), actions.onLater)
                    PillButton(stringResource(R.string.welcome_start), filled = true, shown, reduceMotion, Modifier.weight(2f), actions.onStart)
                }
            } else {
                PillButton(stringResource(R.string.welcome_next), filled = true, shown, reduceMotion, Modifier.fillMaxWidth(), onNext)
            }
        }
    }
}

/**
 * [enabled] false only while the button fades in or out: it keeps its look, it just does not answer. Unlike the
 * family's buttons it also pads 12 dp vertically (a wrapped label at large font sizes grows the pill instead of
 * touching its edge). Pressed, it shrinks to 0.96 (docs/DESIGN.md 6 누름: 120 ms iOS easing, back with the overshoot,
 * as the home screen's chips do at 0.94; a wide button needs less to show it) instead of a ripple.
 */
@Composable
private fun PillButton(label: String, filled: Boolean, enabled: Boolean, reduceMotion: Boolean, modifier: Modifier,
                       onClick: () -> Unit) {
    val c = rootnotePalette()
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed && enabled) 0.96f else 1f,
        animationSpec = when {
            reduceMotion -> snap()
            pressed -> tween(120, easing = Ease)
            else -> tween(350, easing = Overshoot)
        },
        label = "press",
    )
    Box(
        modifier
            .graphicsLayer { scaleX = scale; scaleY = scale }
            .heightIn(min = 48.dp)
            .clip(CircleShape)
            .then(
                if (filled) Modifier.background(c.fill, CircleShape)
                else Modifier.border(1.dp, c.chipBorder, CircleShape)
            )
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            keepWords(label),
            // text on the teal fill: the theme's onPrimary (white in light mode, deep teal in dark mode, where white on
            // #2BB0AA would be 2.6:1); devmode's onFill writes the same values
            color = if (filled) c.onFill else c.textPrimary,
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

/**
 * One message per page, laid out like the first screens of Toss and Samsung's apps: a symbol, a large title of one
 * or two lines, a short line under it, then the picture (or the few rows that page needs) in the space below. The
 * first page is the greeting alone, centred.
 */
@Composable
private fun WelcomePage(page: Int, state: WelcomeState, active: Boolean, stageHeight: Dp, scroll: ScrollState,
                        actions: WelcomeActions) {
    val c = rootnotePalette()
    if (page == P_HELLO) {
        HelloPage(state, active, scroll)
        return
    }
    // The head, then [GAP] to what the page shows: a picture (with its caption [CAPTION] under it) or rows, whose own
    // 12 dp padding makes up the rest of the gap.
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(start = 24.dp, end = 24.dp, top = 24.dp, bottom = 16.dp),
    ) {
        val stage = Modifier.padding(top = GAP).fillMaxWidth().height(stageHeight)
        when (page) {
            P_BASS -> {
                PageHead(Glyph.BASS, c.fill, R.string.welcome_bass_title, stringResource(R.string.welcome_bass_body))
                WelcomeStage(page, state, active, stage)
                Note(
                    state.measuredName?.let { stringResource(R.string.welcome_device_measured, it) }
                        ?: stringResource(R.string.welcome_device_unmeasured),
                    Modifier.padding(top = CAPTION),
                )
            }
            P_SPACE -> {
                PageHead(Glyph.SPACE, c.xtcFill, R.string.welcome_spatial_title, stringResource(R.string.welcome_spatial_body))
                WelcomeStage(page, state, active, stage)
            }
            P_DELAY -> {
                PageHead(Glyph.CLOCK, c.textPrimary, R.string.welcome_know_delay_title, stringResource(R.string.welcome_know_delay_body))
                WelcomeStage(page, state, active, stage)
            }
            P_KNOW -> {
                PageHead(Glyph.INFO, c.textPrimary, R.string.welcome_know_title, stringResource(R.string.welcome_know_body))
                WarningPill(stringResource(R.string.welcome_know_volume), Modifier.padding(top = GAP))
                Column(Modifier.padding(top = GAP - ROW_PAD)) {
                    InfoRow(Glyph.FLASK, c.textSecondary, stringResource(R.string.welcome_know_experimental_title),
                        stringResource(R.string.welcome_know_experimental_body))
                    InfoRow(Glyph.SPEAKER, c.textSecondary, stringResource(R.string.welcome_know_speaker_title),
                        stringResource(R.string.welcome_know_speaker_body))
                    InfoRow(Glyph.APPS, c.textSecondary, stringResource(R.string.welcome_know_others_title),
                        stringResource(R.string.welcome_know_others_body))
                }
            }
            P_SETUP -> SetupPage(state)
            else -> StartPage(actions)
        }
    }
}

/**
 * 1: "반가워요!" alone in the middle, with the app's mark: a beamed arpeggio whose first note head is empty (the
 * fundamental the speaker cannot play) — the overtones arrive one by one and the empty head appears last, as if
 * heard. Nothing explains it here; the next pages do.
 */
@Composable
private fun HelloPage(state: WelcomeState, active: Boolean, scroll: ScrollState) {
    val c = rootnotePalette()
    // centred on the page, and still scrolls when large fonts make it taller than the page
    BoxWithConstraints(Modifier.fillMaxSize()) {
    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(scroll)
            .heightIn(min = maxHeight)
            .padding(horizontal = 24.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        // one entrance for the whole page: the greeting, then the line 300 ms after it, while the mark draws itself
        Appear(state.reduceMotion, delay = 150) {
            Text(
                keepWords(stringResource(R.string.welcome_hello_title)),
                modifier = Modifier.semantics { heading() },
                color = c.accentText, fontSize = 28.sp, lineHeight = 36.sp, fontWeight = FontWeight.Bold,
                letterSpacing = (-0.4).sp, textAlign = TextAlign.Center, style = breaks(heading = true),
            )
        }
        Spacer(Modifier.height(32.dp))
        WelcomeStage(P_HELLO, state, active, Modifier.size(200.dp), card = false)
        Spacer(Modifier.height(32.dp))
        Appear(state.reduceMotion, delay = 450) {
            Text(
                keepWords(stringResource(R.string.welcome_hello_body, stringResource(R.string.app_brand_name))),
                color = c.textSecondary, fontSize = 15.sp, lineHeight = 22.sp, textAlign = TextAlign.Center,
                // centred lines read best balanced
                style = breaks(heading = true),
            )
        }
        // the greeting sits a little above the middle, as on the screens it follows
        Spacer(Modifier.height(48.dp))
    }
    }
}

/** Space from a page's head to what it shows. */
private val GAP = 24.dp
/** Space from a picture to its caption. */
private val CAPTION = 12.dp
/** An [InfoRow]'s own top and bottom padding (part of [GAP] when rows follow the head). */
private val ROW_PAD = 12.dp

/**
 * Line breaking (Compose's presets): titles and centred lines balanced (LineBreak.Heading, which also keeps phrases
 * whole where the platform supports it), running text for readability (LineBreak.Paragraph).
 */
@Composable
private fun breaks(heading: Boolean): TextStyle =
    LocalTextStyle.current.copy(lineBreak = if (heading) LineBreak.Heading else LineBreak.Paragraph)

/**
 * The page's symbol (40 dp), its title (22/30 bold, one or two lines) and the line under it: symbol to title 16 dp,
 * title to line 8 dp. The symbol is moved left by its own inset, so its stroke, not its box, lines up with the
 * title's first letter.
 */
@Composable
private fun PageHead(symbol: Glyph, tint: Color, title: Int, body: String) {
    val c = rootnotePalette()
    Canvas(Modifier.offset(x = -symbol.opticalInset(40.dp)).size(40.dp)) { glyph(symbol, tint) }
    Spacer(Modifier.height(16.dp))
    Text(
        keepWords(stringResource(title)), modifier = Modifier.semantics { heading() },
        color = c.textPrimary, fontSize = 22.sp, lineHeight = 30.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp,
        style = breaks(heading = true),
    )
    Spacer(Modifier.height(8.dp))
    Text(keepWords(body), color = c.textSecondary, fontSize = 15.sp, lineHeight = 22.sp, style = breaks(heading = false))
}

@Composable
private fun Note(text: String, modifier: Modifier = Modifier) {
    val c = rootnotePalette()
    Text(keepWords(text), modifier, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, style = breaks(heading = false))
}

/** The first page's words come in once: a short rise and fade (350 ms, iOS easing) after [delay] ms. */
@Composable
private fun Appear(reduceMotion: Boolean, delay: Int, content: @Composable () -> Unit) {
    var shown by rememberSaveable { mutableStateOf(reduceMotion) }
    LaunchedEffect(Unit) { shown = true }
    val p by animateFloatAsState(
        if (shown) 1f else 0f, tween(if (reduceMotion) 0 else 350, delayMillis = if (reduceMotion) 0 else delay, easing = Ease),
        label = "appear",
    )
    Box(Modifier.graphicsLayer { alpha = p; translationY = (1f - p) * 12.dp.toPx() }) { content() }
}

/** 6: what happens next on this phone, only the lines that apply to its Android version. */
@Composable
private fun SetupPage(state: WelcomeState) {
    val c = rootnotePalette()
    PageHead(Glyph.KEY, c.textPrimary, R.string.welcome_ready_title, stringResource(R.string.welcome_ready_body))
    Column(Modifier.padding(top = GAP - ROW_PAD)) {
        if (state.permissionsReady)
            InfoRow(Glyph.CHECK, c.textSecondary, stringResource(R.string.welcome_ready_granted_title),
                stringResource(R.string.welcome_ready_granted_body))
        else
            InfoRow(Glyph.TERMINAL, c.textSecondary, stringResource(R.string.welcome_ready_grant_title),
                stringResource(R.string.welcome_ready_grant_body))
        InfoRow(
            Glyph.DIALOG, c.textSecondary, stringResource(R.string.welcome_ready_capture_title),
            stringResource(if (state.consentEveryTime) R.string.welcome_ready_capture_body_14 else R.string.welcome_ready_capture_body_old),
        )
        if (state.screenShareSetting)
            InfoRow(Glyph.TOGGLE, c.textSecondary, stringResource(R.string.welcome_ready_a15_title),
                stringResource(R.string.welcome_ready_a15_body))
    }
}

/**
 * 7: the decision, kept calm: what starting does (the consent itself, as the page's line), privacy with its details,
 * the licence. The two answers are the bottom buttons.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun StartPage(actions: WelcomeActions) {
    val c = rootnotePalette()
    PageHead(Glyph.CHECK, c.textPrimary, R.string.welcome_start_title, stringResource(R.string.welcome_consent))
    InfoRow(Glyph.LOCK, c.textSecondary, stringResource(R.string.welcome_ready_privacy_title),
        stringResource(R.string.welcome_ready_privacy_body), Modifier.padding(top = GAP - ROW_PAD)) {
        FlowRow(Modifier.offset(x = (-12).dp)) {
            TextAction(stringResource(R.string.welcome_ready_privacy_more), onClick = actions.onPrivacy)
            TextAction(stringResource(R.string.welcome_ready_license), onClick = actions.onLicense)
        }
    }
    Note(stringResource(R.string.welcome_ready_legal))
}

/**
 * A row: a 24 dp symbol (2 dp round strokes, docs/DESIGN.md 7), the title (16/22 bold, like the home screen's switch
 * rows and DESIGN.md's 행 제목) and its line (13/18). No dividers, no card. [extra] goes under the line (links).
 */
@Composable
private fun InfoRow(symbol: Glyph, tint: Color, title: String, body: String, modifier: Modifier = Modifier,
                    extra: (@Composable () -> Unit)? = null) {
    val c = rootnotePalette()
    Row(
        modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .then(if (extra == null) Modifier.semantics(mergeDescendants = true) { } else Modifier)
            .padding(vertical = ROW_PAD),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Canvas(Modifier.padding(top = 1.dp).size(24.dp)) { glyph(symbol, tint) }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(keepWords(title), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
                style = breaks(heading = true))
            Text(keepWords(body), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, style = breaks(heading = false))
            extra?.invoke()
        }
    }
}

/** docs/DESIGN.md 5 "인라인 경고": a warning pill with an orange dot and one line; it cannot be dismissed. */
@Composable
private fun WarningPill(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier
            .background(colorResource(R.color.rn_warn_bg), CircleShape)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).background(colorResource(R.color.rn_warn_dot), CircleShape))
        Spacer(Modifier.width(8.dp))
        Text(keepWords(text), color = colorResource(R.color.rn_warn_text), fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium,
            style = breaks(heading = false))
    }
}

// ------------------------------------------------------------------------------------------------- the stage

/** Stage colours: teal = virtual bass and progress, purple = spatial. */
private class HeroColors(val bass: Color, val space: Color, val ink: Color, val soft: Color, val line: Color, val bg: Color) {
    /** Dark mode: the phone is drawn in a muted grey instead of the text colour, so it never outshines the words. */
    val dark: Boolean = bg.luminance() < 0.5f
    val body: Color = if (dark) line else ink.copy(alpha = 0.88f)
    val screen: Color = if (dark) bg.copy(alpha = 0.6f) else bg.copy(alpha = 0.22f)
    val marks: Color = if (dark) soft else bg.copy(alpha = 0.75f)
}

/**
 * Per page with a picture (hello, bass, spatial, delay): the frame it rests on, and the length of a whole cycle. The
 * picture plays once, from the start to its resting frame, each time its page is reached (motion that answers the
 * swipe, then stillness). Off-screen, a page waits at its first frame, so a page swiped in never jumps backwards;
 * with the animations off it shows the resting frame.
 */
private val KEY_FRAMES = floatArrayOf(0.9f, 0.8f, 0.8f, 0.5f)
private val PERIODS = intArrayOf(3600, 4200, 4200, 3600)

@Composable
private fun WelcomeStage(page: Int, state: WelcomeState, active: Boolean, modifier: Modifier, card: Boolean = true) {
    val c = rootnotePalette()
    val colors = remember(c) { HeroColors(c.fill, c.xtcFill, c.textPrimary, c.textSecondary, c.chipBorder, c.bg) }
    // One clock per page, 0 -> its resting frame, played once when the page has settled. Pages swiped in wait at
    // their first frame, so nothing jumps backwards on screen; with the animations off every page shows its resting
    // frame. Read only while drawing, so a frame never recomposes the page.
    val anim = remember(page) { Animatable(if (state.reduceMotion) KEY_FRAMES[page] else 0f) }
    LaunchedEffect(page, active, state.reduceMotion) {
        when {
            state.reduceMotion -> anim.snapTo(KEY_FRAMES[page])
            active -> {
                anim.snapTo(0f)
                anim.animateTo(KEY_FRAMES[page], tween((PERIODS[page] * KEY_FRAMES[page]).toInt(), easing = LinearEasing))
            }
            else -> anim.snapTo(0f)
        }
    }
    val clock: State<Float> = anim.asState()
    val brand = stringResource(R.string.app_brand_name)
    val description = when (page) {
        P_HELLO -> stringResource(R.string.welcome_hero_logo_a11y, brand)
        P_BASS -> stringResource(R.string.welcome_hero_bass_a11y)
        P_SPACE -> stringResource(R.string.welcome_hero_space_a11y)
        else -> stringResource(R.string.welcome_hero_delay_a11y)
    }
    val labels = when (page) {
        P_DELAY -> listOf(stringResource(R.string.welcome_hero_original), stringResource(R.string.app_brand_name),
            stringResource(R.string.welcome_hero_delay))
        else -> listOf(stringResource(R.string.home_tab_bass), stringResource(R.string.home_tab_spatial))
    }
    val measurer = rememberTextMeasurer()
    Box(if (card) modifier.clip(RoundedCornerShape(20.dp)).background(c.band) else modifier) {
        Canvas(
            Modifier.fillMaxSize().padding(if (card) 16.dp else 0.dp).semantics { contentDescription = description }
        ) {
            val t = clock.value % 1f
            when (page) {
                P_HELLO -> heroLogo(t, colors)
                P_BASS -> heroHello(t, colors, measurer, labels, bass = true, space = false)
                P_SPACE -> heroSpace(t, colors, measurer, labels)
                else -> heroDelay(t, colors, measurer, labels)
            }
        }
    }
}

private fun smooth(x: Float): Float { val v = x.coerceIn(0f, 1f); return v * v * (3f - 2f * v) }

/** 12/16 Medium, scaled with the user's font size up to 1.3x (dp.toSp() takes the font scale back out). */
private fun DrawScope.labelStyle(): TextStyle {
    val k = min(fontScale, 1.3f)
    return TextStyle(fontSize = (12f * k).dp.toSp(), lineHeight = (16f * k).dp.toSp(), fontWeight = FontWeight.Medium)
}

/**
 * A stage label: 12/16 Medium that grows with the font size up to 1.3x, so it stays inside the picture at 200 % (the
 * text under the picture carries the meaning at full size, and the picture has its TalkBack description).
 * [vAlign]: 0 = [at] is its top, 1 = its bottom.
 */
private fun DrawScope.label(measurer: TextMeasurer, text: String, color: Color, at: Offset, maxWidth: Float = size.width,
                            center: Boolean = false, vAlign: Float = 0f) {
    if (color.alpha <= 0.01f || text.isEmpty()) return
    val r = measurer.measure(
        text,
        labelStyle().copy(color = color, textAlign = if (center) TextAlign.Center else TextAlign.Start),
        maxLines = 2,
        constraints = Constraints(maxWidth = maxWidth.toInt().coerceAtLeast(1)),
    )
    val x = if (center) at.x - r.size.width / 2f else at.x
    val y = at.y - r.size.height * vAlign
    drawText(r, topLeft = Offset(x.coerceIn(0f, (size.width - r.size.width).coerceAtLeast(0f)), y.coerceAtLeast(0f)))
}

/**
 * Virtual bass: the phone from the front with a song playing. First only its small sound (short grey arcs); then the
 * bass it cannot play spreads from the bottom speaker in large teal rings. ([space] adds purple side arcs; the
 * spatial page has its own top view, heroSpace.)
 */
private fun DrawScope.heroHello(t: Float, col: HeroColors, measurer: TextMeasurer, labels: List<String>,
                                 bass: Boolean = true, space: Boolean = true) {
    val unit = min(size.width / 10f, size.height / 7f)
    val cx = size.width / 2f
    val cy = size.height * 0.5f
    val pw = unit * 2.2f
    val ph = unit * 4.4f
    val top = cy - ph / 2f
    val bottom = cy + ph / 2f
    val end = 1f - smooth((t - 0.9f) / 0.1f)
    // with one feature only, it comes in after the small sound (0.3); with both, bass first and spatial after it
    val bassIn = if (!bass) 0f else smooth((t - (if (space) 0.2f else 0.3f)) / 0.2f) * end
    val spaceIn = if (!space) 0f else smooth((t - (if (bass) 0.48f else 0.3f)) / 0.2f) * end
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
    val small = 1f - 0.6f * maxOf(bassIn, spaceIn)
    for (k in 0 until 3) {
        val p = ((t * 3f) + k / 3f) % 1f
        val r = unit * (0.25f + 0.55f * p)
        val a = (1f - p) * 0.75f * small
        val stroke = Stroke(1.5.dp.toPx(), cap = StrokeCap.Round)
        drawArc(col.soft.copy(alpha = a), 215f, 110f, false, Offset(ear.x - r, ear.y - r), Size(2 * r, 2 * r), style = stroke)
        drawArc(col.soft.copy(alpha = a), 35f, 110f, false, Offset(foot.x - r, foot.y - r), Size(2 * r, 2 * r), style = stroke)
    }
    // the phone, front view: body, screen, a small "now playing" level, earpiece slot and bottom speaker holes
    drawRoundRect(col.body, Offset(cx - pw / 2f, top), Size(pw, ph), CornerRadius(unit * 0.42f))
    drawRoundRect(
        col.screen, Offset(cx - pw / 2f + unit * 0.14f, top + unit * 0.5f),
        Size(pw - unit * 0.28f, ph - unit * 0.95f), CornerRadius(unit * 0.22f),
    )
    for (i in 0 until 4) {
        val lv = 0.35f + 0.65f * (0.5f + 0.5f * sin(2f * PI.toFloat() * (t * 2f + i * 0.27f)))
        val h = unit * 0.9f * lv
        val x = cx + (i - 1.5f) * unit * 0.34f
        drawLine(col.marks, Offset(x, cy + unit * 0.45f), Offset(x, cy + unit * 0.45f - h), unit * 0.14f, StrokeCap.Round)
    }
    drawLine(col.marks, Offset(cx - unit * 0.3f, ear.y), Offset(cx + unit * 0.3f, ear.y), unit * 0.08f, StrokeCap.Round)
    for (i in -2..2) drawCircle(col.marks, unit * 0.045f, Offset(cx + i * unit * 0.14f, bottom - unit * 0.2f))
    // what each colour is (never the colour alone)
    label(measurer, labels.getOrElse(0) { "" }, col.bass.copy(alpha = bassIn), Offset(0f, bottom), size.width / 3f, vAlign = 1f)
    val spaceText = labels.getOrElse(1) { "" }
    val w = measurer.measure(spaceText, labelStyle(),
        maxLines = 2, constraints = Constraints(maxWidth = (size.width / 3f).toInt().coerceAtLeast(1))).size.width
    label(measurer, spaceText, col.space.copy(alpha = spaceIn), Offset(size.width - w, top), size.width / 3f)
}

/**
 * Spatial, seen from above, with the spatial story's geometry on purpose (SpatialStory.kt Stage, phone(), head()), so
 * the (i) story later shows the same phone and listener: the phone held sideways, the listener below it. At first
 * each speaker also reaches the far ear (the dashed crossing lines) and the sound sits on the phone; then the
 * crossing lines fade and the two sounds move out beside the ears.
 */
private fun DrawScope.heroSpace(t: Float, col: HeroColors, measurer: TextMeasurer, labels: List<String>) {
    val unit = min(size.width / 8.5f, size.height / 6.4f)
    val cx = size.width / 2f
    // the phone (top) to the bottom of the head is 5 units: centred in the picture
    val phoneY = (size.height - unit * 5f) / 2f + unit * 0.45f
    val pw = unit * 4.2f
    val ph = unit * 0.9f
    val spL = Offset(cx - pw / 2f + unit * 0.35f, phoneY)
    val spR = Offset(cx + pw / 2f - unit * 0.35f, phoneY)
    val headY = phoneY + unit * 3.6f
    val headR = unit * 0.95f
    val earL = Offset(cx - headR, headY)
    val earR = Offset(cx + headR, headY)
    val clear = smooth((t - 0.3f) / 0.35f)
    val dash = PathEffect.dashPathEffect(floatArrayOf(10f, 8f))
    // the leak to the far ear fades; the direct paths stay
    drawLine(col.space.copy(alpha = 0.55f * (1f - clear)), spL, earR, 2.dp.toPx(), pathEffect = dash)
    drawLine(col.space.copy(alpha = 0.55f * (1f - clear)), spR, earL, 2.dp.toPx(), pathEffect = dash)
    drawLine(col.space.copy(alpha = 0.8f), spL, earL, 2.dp.toPx(), StrokeCap.Round)
    drawLine(col.space.copy(alpha = 0.8f), spR, earR, 2.dp.toPx(), StrokeCap.Round)
    // the phone, held sideways: body, screen, two speakers
    drawRoundRect(col.body, Offset(cx - pw / 2f, phoneY - ph / 2f), Size(pw, ph), CornerRadius(ph * 0.35f))
    drawRoundRect(col.screen, Offset(cx - pw / 2f + unit * 0.6f, phoneY - ph / 2f + unit * 0.12f),
        Size(pw - unit * 1.2f, ph - unit * 0.24f), CornerRadius(ph * 0.2f))
    drawCircle(col.space, unit * 0.17f, spL)
    drawCircle(col.space, unit * 0.17f, spR)
    // the listener
    val center = Offset(cx, headY)
    drawCircle(col.bg, headR, center)
    drawCircle(col.ink.copy(alpha = 0.7f), headR, center, style = Stroke(2.dp.toPx()))
    drawRoundRect(col.ink.copy(alpha = 0.7f), Offset(earL.x - unit * 0.16f, headY - unit * 0.3f), Size(unit * 0.2f, unit * 0.6f), CornerRadius(unit * 0.1f))
    drawRoundRect(col.ink.copy(alpha = 0.7f), Offset(earR.x - unit * 0.04f, headY - unit * 0.3f), Size(unit * 0.2f, unit * 0.6f), CornerRadius(unit * 0.1f))
    // the two sounds: from the middle of the phone out beside the ears
    val y = phoneY + unit * 1.3f + (headY - unit * 0.6f - phoneY - unit * 1.3f) * clear
    val spread = unit * 0.35f + (headR + unit * 1.0f - unit * 0.35f) * clear
    drawCircle(col.space, unit * 0.2f, Offset(cx - spread, y))
    drawCircle(col.space, unit * 0.2f, Offset(cx + spread, y))
    label(measurer, labels.getOrElse(1) { "" }, col.space.copy(alpha = clear), Offset(cx + spread + unit * 0.4f, y), size.width / 3f, vAlign = 0.5f)
}

/**
 * The delay: the original sound and the processed sound run side by side; the processed one follows about
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
 * The app's mark (docs/DESIGN.md 7): a beamed arpeggio, four notes rising. The three overtones arrive one by one, the
 * beam joins them, and only then does the first, empty note head appear: the fundamental the small speaker cannot
 * play, which the ear still hears. It fades a little before the loop starts again.
 */
private fun DrawScope.heroLogo(t: Float, col: HeroColors) {
    val w = size.width
    val h = size.height
    val end = 1f - smooth((t - 0.92f) / 0.08f)
    val xs = floatArrayOf(0.2f, 0.42f, 0.64f, 0.86f).map { it * w }
    val ys = floatArrayOf(0.8f, 0.7f, 0.6f, 0.5f).map { it * h }
    val rx = w * 0.085f
    val ry = w * 0.062f
    val beamY0 = h * 0.2f
    val beamY1 = h * 0.12f
    fun beamAt(x: Float) = beamY0 + (beamY1 - beamY0) * (x - xs[0]) / (xs[3] - xs[0])
    val stroke = w * 0.035f
    fun head(i: Int, a: Float, hollow: Boolean, grow: Float) {
        if (a <= 0f) return
        val cx = xs[i] - rx * 0.35f
        val cy = ys[i]
        rotate(-20f, Offset(cx, cy)) {
            val tl = Offset(cx - rx * grow, cy - ry * grow)
            val sz = Size(2 * rx * grow, 2 * ry * grow)
            if (hollow) drawOval(col.bass.copy(alpha = a), tl, sz, style = Stroke(stroke * 0.8f))
            else drawOval(col.bass.copy(alpha = a), tl, sz)
        }
        // the stem, from the right of the head up to the beam
        val sx = cx + rx * 0.82f
        drawLine(col.bass.copy(alpha = a), Offset(sx, cy - ry * 0.3f), Offset(sx, beamAt(sx)), stroke * 0.6f, StrokeCap.Round)
    }
    // the overtones, one by one
    for (i in 1..3) {
        val a = smooth((t - (0.06f + 0.12f * (i - 1))) / 0.1f) * end
        head(i, a, hollow = false, grow = 0.7f + 0.3f * a)
    }
    // the beam joins the overtones, then reaches back to the fundamental's stem
    fun stemX(i: Int) = xs[i] - rx * 0.35f + rx * 0.82f
    val over = smooth((t - 0.42f) / 0.12f)
    if (over > 0f && end > 0f) {
        val xb = stemX(1) + (stemX(3) - stemX(1)) * over
        drawLine(col.bass.copy(alpha = end), Offset(stemX(1), beamAt(stemX(1))), Offset(xb, beamAt(xb)), stroke * 1.4f, StrokeCap.Round)
    }
    val back = smooth((t - 0.6f) / 0.12f)
    if (back > 0f && end > 0f) {
        val xa = stemX(1) - (stemX(1) - stemX(0)) * back
        drawLine(col.bass.copy(alpha = end), Offset(xa, beamAt(xa)), Offset(stemX(1), beamAt(stemX(1))), stroke * 1.4f, StrokeCap.Round)
    }
    // the fundamental: an empty head, heard though not played; a soft ring answers it
    val fund = smooth((t - 0.6f) / 0.14f) * end
    head(0, fund, hollow = true, grow = 1f)
    if (fund > 0f && t < 0.92f) {
        val p = ((t - 0.6f) / 0.32f).coerceIn(0f, 1f)
        val cx = xs[0] - rx * 0.35f
        drawCircle(col.bass.copy(alpha = 0.5f * (1f - p) * fund), rx * (1.2f + 1.6f * p), Offset(cx, ys[0]), style = Stroke(stroke * 0.4f))
    }
}

// ------------------------------------------------------------------------------------------------- symbols

/**
 * Symbols drawn on a 24-unit grid with 2 dp round strokes (docs/DESIGN.md 7: no emoji, line icons). [left]: where
 * the drawing starts on that grid (the centre of its leftmost stroke), for optical alignment with text.
 */
private enum class Glyph(val left: Float) {
    BASS(2f), SPACE(2f), FLASK(4.5f), CLOCK(3f), SPEAKER(4f), APPS(3f), KEY(4f), CHECK(3f), DIALOG(3f), TOGGLE(2f),
    LOCK(5f), INFO(3f), TERMINAL(3f);

    /** The empty space left of the drawn stroke at [box] size: the grid inset less half the 2 dp stroke. */
    fun opticalInset(box: Dp): Dp = (box * (left / 24f) - 1.dp).coerceAtLeast(0.dp)
}

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
        Glyph.INFO -> { ring(12f, 12f, 9f); dot(12f, 7.6f, 1.3f); line(12f, 11f, 12f, 16.5f) }
        Glyph.TERMINAL -> { rrect(3f, 4f, 21f, 20f, 3f); poly(7f, 9f, 10f, 12f, 7f, 15f); line(12.5f, 15f, 16.5f, 15f) }
    }
}

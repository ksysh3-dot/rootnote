package me.timschneeberger.rootlessjamesdsp.home

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.animation.core.Animatable
import me.timschneeberger.rootlessjamesdsp.ui.RN_MS_COLOR
import me.timschneeberger.rootlessjamesdsp.ui.RN_MS_MOVE
import me.timschneeberger.rootlessjamesdsp.ui.RN_STORY_ROUNDS
import me.timschneeberger.rootlessjamesdsp.ui.RnEase
import me.timschneeberger.rootlessjamesdsp.ui.PagerDot
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.State
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

/*
 * The spatial explanation as a landscape motion story (SpatialStoryActivity). Principles taken from Toss's
 * "why motion in finance" article: one message per scene carried by one motion, few assets (only shapes drawn here:
 * the phone, the head with its ears, sound arcs; two colours, teal for the left speaker and virtual bass, purple for
 * the right speaker and spatial), continuity (the same phone and head stay on stage from scene to scene), a light
 * tone. The text beside each scene says everything on its own; the motion only helps. With the system animations
 * off every scene shows one still key frame.
 *
 * Layout: progress dots and close on top; the stage (about 60 %) and the scene's heading and text (scrolls with
 * large fonts); previous / next at the bottom; swiping also turns the page. Motion tokens are the home screen's:
 * iOS easing and 300 ms colour changes. The scene clock is read only while drawing (no recomposition per frame).
 */

@Immutable
data class StoryState(
    val reduceMotion: Boolean,
    /** Rootnote is running: "들어 보기" can switch spatial on and off. */
    val canListen: Boolean,
    /** Spatial plays now (the user's setting, or the listening choice). */
    val listening: Boolean,
    val distanceCm: Int,
    val hatCm: Int,
)

private val Ease = RnEase
private const val SCENES = 10
/** The page with the honest limits and "직접 들어 보기". */
private const val LISTEN_PAGE = 8

@Composable
fun SpatialStory(state: StoryState, onListen: (Boolean) -> Unit, onClose: () -> Unit) {
    val c = rootnotePalette()
    val items = stringArrayResource(R.array.home_xtc_info)
    val pager = rememberPagerState { SCENES }
    val scope = rememberCoroutineScope()
    Column(
        Modifier
            .fillMaxSize()
            .background(c.bg)
            .safeDrawingPadding()
    ) {
        // top: progress and close
        Row(
            Modifier.fillMaxWidth().padding(start = 24.dp, end = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                stringResource(R.string.home_xtc_info_title),
                modifier = Modifier.weight(1f).semantics { heading() },
                color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                for (i in 0 until SCENES) PagerDot(pager, i, c.xtcFill, c.divider, state.reduceMotion)
            }
            Spacer(Modifier.width(8.dp))
            val closeLabel = stringResource(R.string.home_xtc_info_close)
            Box(
                Modifier.size(48.dp).clickable(role = Role.Button, onClick = onClose)
                    .semantics { contentDescription = closeLabel },
                contentAlignment = Alignment.Center,
            ) {
                Canvas(Modifier.size(18.dp)) {
                    val s = size.width
                    drawLine(c.textSecondary, Offset(0f, 0f), Offset(s, s), 2.dp.toPx(), StrokeCap.Round)
                    drawLine(c.textSecondary, Offset(s, 0f), Offset(0f, s), 2.dp.toPx(), StrokeCap.Round)
                }
            }
        }

        HorizontalPager(state = pager, modifier = Modifier.weight(1f).fillMaxWidth()) { page ->
            Row(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
                Box(
                    Modifier
                        .weight(0.6f)
                        .fillMaxHeight()
                        .padding(vertical = 8.dp)
                        .background(c.band, RoundedCornerShape(20.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Scene(page, state, active = page == pager.currentPage)
                }
                Column(
                    Modifier
                        .weight(0.4f)
                        .fillMaxHeight()
                        .padding(start = 20.dp, top = 8.dp, bottom = 8.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "${page + 1} / $SCENES",
                        color = c.xtcAccentText, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Bold,
                    )
                    Text(
                        items.getOrElse(2 * page) { "" },
                        modifier = Modifier.semantics { heading() },
                        color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold,
                    )
                    Text(items.getOrElse(2 * page + 1) { "" }, color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
                    if (page == LISTEN_PAGE) ListenControl(state, onListen)
                }
            }
        }

        // bottom: previous / next
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            val first = pager.currentPage == 0
            val last = pager.currentPage == SCENES - 1
            StoryButton(stringResource(R.string.story_prev), filled = false, enabled = !first) {
                scope.launch { pager.animateScrollToPage(pager.currentPage - 1) }
            }
            Spacer(Modifier.weight(1f))
            StoryButton(stringResource(if (last) R.string.story_done else R.string.story_next), filled = true, enabled = true) {
                if (last) onClose() else scope.launch { pager.animateScrollToPage(pager.currentPage + 1) }
            }
        }
    }
}

@Composable
private fun StoryButton(label: String, filled: Boolean, enabled: Boolean, onClick: () -> Unit) {
    val c = rootnotePalette()
    Box(
        Modifier
            .heightIn(min = 48.dp)
            .then(
                if (filled) Modifier.background(c.xtcFill, CircleShape)
                else Modifier.border(1.dp, if (enabled) c.chipBorder else c.divider, CircleShape)
            )
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 22.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            color = when {
                filled -> c.thumb
                enabled -> c.textPrimary
                else -> c.chevron
            },
            fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold,
        )
    }
}

/** "직접 들어 보기": spatial off / on while music plays; never stored (the activity clears it on leaving). */
@Composable
private fun ListenControl(state: StoryState, onListen: (Boolean) -> Unit) {
    val c = rootnotePalette()
    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            stringResource(R.string.story_listen_title),
            color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
        )
        if (!state.canListen) {
            Text(stringResource(R.string.story_listen_unavailable), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            return@Column
        }
        Row(
            Modifier.background(c.band, RoundedCornerShape(14.dp)).padding(4.dp).selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            for ((on, label) in listOf(false to R.string.story_listen_off, true to R.string.story_listen_on)) {
                val selected = state.listening == on
                val bg by animateColorAsState(
                    if (selected) c.bg else c.band, tween(if (state.reduceMotion) 0 else RN_MS_COLOR, easing = Ease), label = "listenBg",
                )
                Box(
                    Modifier
                        .heightIn(min = 48.dp)
                        .background(bg, RoundedCornerShape(10.dp))
                        .selectable(selected = selected, role = Role.RadioButton) { onListen(on) }
                        .padding(horizontal = 18.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        stringResource(label),
                        color = if (selected) c.xtcAccentText else c.textSecondary,
                        fontSize = 15.sp, lineHeight = 21.sp,
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                    )
                }
            }
        }
        Text(stringResource(R.string.story_listen_hint), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
    }
}

// ------------------------------------------------------------------------------------------------- the stage

/** Colours of the stage: teal = left speaker / virtual bass, purple = right speaker / spatial. */
private class StageColors(val left: Color, val right: Color, val ink: Color, val soft: Color, val line: Color, val bg: Color)

@Composable
private fun Scene(page: Int, state: StoryState, active: Boolean) {
    val c = rootnotePalette()
    val colors = remember(c) { StageColors(c.fill, c.xtcFill, c.textPrimary, c.textSecondary, c.chipBorder, c.bg) }
    val periods = intArrayOf(2600, 3000, 4200, 1, 4000, 2400, 1, 5000, 2600, 4000)
    // One clock per scene (0..1, playing a few rounds, starting at the scene's key frame so a page that becomes active does not
    // jump); a still key frame with the animations off or off-screen. Read only inside the Canvas (draw phase).
    val clock: State<Float> = if (state.reduceMotion || !active || periods[page] <= 1) {
        remember(page) { androidx.compose.runtime.mutableFloatStateOf(KEY_FRAMES[page]) }
    } else {
        // a few rounds, then the scene rests on its key frame: a loop nobody can stop is not for everyone
        val anim = remember(page) { Animatable(KEY_FRAMES[page]) }
        LaunchedEffect(page) {
            anim.snapTo(KEY_FRAMES[page])
            anim.animateTo(KEY_FRAMES[page] + RN_STORY_ROUNDS, tween(periods[page] * RN_STORY_ROUNDS.toInt(), easing = LinearEasing))
        }
        anim.asState()
    }
    val description = stringArrayResource(R.array.story_scene_a11y).getOrElse(page) { "" }
    val measurer = rememberTextMeasurer()
    val compareLabels = listOf(stringResource(R.string.story_compare_widen), stringResource(R.string.story_compare_spatial))
    when (page) {
        3 -> DistanceScene(state, colors, description)
        6 -> PresetScene(state, colors, description)
        else -> Canvas(Modifier.fillMaxSize().padding(12.dp).semantics { contentDescription = description }) {
            val t = clock.value % 1f
            when (page) {
                0 -> sceneLeak(t, colors)
                1 -> sceneCancel(t, colors)
                2 -> sceneOrigin(t, colors, measurer)
                4 -> sceneSweetSpot(t, colors)
                5 -> sceneBand(t, colors, measurer)
                7 -> scenePortrait(t, colors)
                9 -> sceneCompare(t, colors, measurer, compareLabels)
                else -> sceneLimits(t, colors)
            }
        }
    }
}

private val KEY_FRAMES = floatArrayOf(0.55f, 0.75f, 0.85f, 0f, 0.3f, 0.4f, 0f, 0.8f, 0.5f, 0.7f)

/** Stage geometry (top view): the phone across the top, the head below it, ears left and right. */
private class Stage(w: Float, h: Float, distanceScale: Float = 1f, headScale: Float = 1f) {
    val unit = min(w / 10f, h / 7f)
    val cx = w / 2f
    val phoneY = h * 0.18f
    val phoneW = unit * 4.2f
    val phoneH = unit * 0.9f
    val spL = Offset(cx - phoneW / 2f + unit * 0.35f, phoneY)
    val spR = Offset(cx + phoneW / 2f - unit * 0.35f, phoneY)
    val headY = phoneY + unit * 3.6f * distanceScale
    val headR = unit * 0.95f * headScale
    val earL = Offset(cx - headR, headY)
    val earR = Offset(cx + headR, headY)
}

private fun DrawScope.phone(s: Stage, col: StageColors, leftOn: Boolean = true, rightOn: Boolean = true, cx: Float = s.cx, y: Float = s.phoneY) {
    drawRoundRect(
        col.ink.copy(alpha = 0.85f), Offset(cx - s.phoneW / 2f, y - s.phoneH / 2f), Size(s.phoneW, s.phoneH),
        CornerRadius(s.phoneH * 0.35f),
    )
    drawRoundRect(
        col.bg.copy(alpha = 0.25f), Offset(cx - s.phoneW / 2f + s.unit * 0.6f, y - s.phoneH / 2f + s.unit * 0.12f),
        Size(s.phoneW - s.unit * 1.2f, s.phoneH - s.unit * 0.24f), CornerRadius(s.phoneH * 0.2f),
    )
    val dl = s.spL.x - s.cx
    drawCircle(if (leftOn) col.left else col.line, s.unit * 0.17f, Offset(cx + dl, y))
    drawCircle(if (rightOn) col.right else col.line, s.unit * 0.17f, Offset(cx - dl, y))
}

private fun DrawScope.head(s: Stage, col: StageColors, dx: Float = 0f) {
    val center = Offset(s.cx + dx, s.headY)
    drawCircle(col.bg, s.headR, center)
    drawCircle(col.ink.copy(alpha = 0.7f), s.headR, center, style = Stroke(2.dp.toPx()))
    // nose (facing the phone) and ears
    val nose = Path().apply {
        moveTo(center.x - s.unit * 0.18f, center.y - s.headR + 1f)
        lineTo(center.x, center.y - s.headR - s.unit * 0.28f)
        lineTo(center.x + s.unit * 0.18f, center.y - s.headR + 1f)
    }
    drawPath(nose, col.ink.copy(alpha = 0.7f), style = Stroke(2.dp.toPx()))
    drawRoundRect(col.ink.copy(alpha = 0.7f), Offset(center.x - s.headR - s.unit * 0.16f, center.y - s.unit * 0.3f),
        Size(s.unit * 0.2f, s.unit * 0.6f), CornerRadius(s.unit * 0.1f))
    drawRoundRect(col.ink.copy(alpha = 0.7f), Offset(center.x + s.headR - s.unit * 0.04f, center.y - s.unit * 0.3f),
        Size(s.unit * 0.2f, s.unit * 0.6f), CornerRadius(s.unit * 0.1f))
}

/** Expanding arcs from [from] toward the listener, [phase] 0..1. */
private fun DrawScope.waves(from: Offset, color: Color, phase: Float, maxR: Float, count: Int = 3, dashed: Boolean = false) {
    for (k in 0 until count) {
        val p = (phase + k.toFloat() / count) % 1f
        val r = maxR * p
        val a = (1f - p) * 0.9f
        drawArc(
            color.copy(alpha = a), startAngle = 20f, sweepAngle = 140f, useCenter = false,
            topLeft = Offset(from.x - r, from.y - r), size = Size(2 * r, 2 * r),
            style = Stroke(
                width = 2.5.dp.toPx(), cap = StrokeCap.Round,
                pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(10f, 8f)) else null,
            ),
        )
    }
}

private fun smooth(x: Float): Float { val v = x.coerceIn(0f, 1f); return v * v * (3f - 2f * v) }

/** 1: both speakers reach both ears; the image collapses into the middle of the phone. */
private fun DrawScope.sceneLeak(t: Float, col: StageColors) {
    val s = Stage(size.width, size.height)
    val reach = s.headY - s.phoneY + s.headR * 1.4f
    waves(s.spL, col.left, t, reach)
    waves(s.spR, col.right, (t + 0.5f) % 1f, reach)
    phone(s, col)
    head(s, col)
    // ear meters: both ears hear left and right almost equally
    val h = s.unit * 1.2f
    for ((ear, sign) in listOf(s.earL to -1f, s.earR to 1f)) {
        val x = ear.x + sign * s.unit * 0.75f
        val top = ear.y - h / 2f
        val fillL = 0.5f + 0.4f * sin(2 * PI.toFloat() * t)
        val fillR = 0.5f + 0.4f * sin(2 * PI.toFloat() * (t + 0.5f))
        drawRoundRect(col.line, Offset(x - s.unit * 0.22f, top), Size(s.unit * 0.18f, h), CornerRadius(4f))
        drawRoundRect(col.line, Offset(x + s.unit * 0.04f, top), Size(s.unit * 0.18f, h), CornerRadius(4f))
        drawRoundRect(col.left, Offset(x - s.unit * 0.22f, top + h * (1 - fillL)), Size(s.unit * 0.18f, h * fillL), CornerRadius(4f))
        drawRoundRect(col.right, Offset(x + s.unit * 0.04f, top + h * (1 - fillR)), Size(s.unit * 0.18f, h * fillR), CornerRadius(4f))
    }
    // the sound image: a wide dashed band that shrinks into a dot in the middle of the phone
    val shrink = smooth(t * 1.4f)
    val w = (s.phoneW * 1.6f) * (1f - shrink) + s.unit * 0.3f
    val y = s.phoneY + s.unit * 1.3f
    drawOval(
        col.ink.copy(alpha = 0.5f), Offset(s.cx - w / 2f, y - s.unit * 0.18f), Size(w, s.unit * 0.36f),
        style = Stroke(2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f))),
    )
    drawCircle(col.ink.copy(alpha = 0.3f + 0.6f * shrink), s.unit * 0.12f, Offset(s.cx, y))
}

/** 2: the leak to the right ear meets an inverted copy from the right speaker; the sum goes flat; echoes fade. */
private fun DrawScope.sceneCancel(t: Float, col: StageColors) {
    val s = Stage(size.width * 0.62f, size.height)
    phone(s, col)
    head(s, col)
    val dash = PathEffect.dashPathEffect(floatArrayOf(10f, 8f))
    drawLine(col.left.copy(alpha = 0.8f), s.spL, s.earR, 2.5.dp.toPx(), StrokeCap.Round)
    val inv = smooth((t - 0.15f) / 0.3f)
    drawLine(col.right.copy(alpha = 0.8f * inv), s.spR, s.earR, 2.5.dp.toPx(), StrokeCap.Round, pathEffect = dash)
    // echoes: each round weaker
    for (k in 1..4) {
        val a = smooth((t - 0.45f - 0.08f * k) / 0.1f) * (0.6f / k)
        drawCircle(col.right.copy(alpha = a), s.unit * (0.25f + 0.25f * k), s.earR, style = Stroke(1.5.dp.toPx()))
    }
    // inset at the right: leak, inverted copy, and their sum
    val x0 = size.width * 0.66f
    val w = size.width * 0.32f
    val rowH = size.height / 4f
    val amp = rowH * 0.32f
    val shift = t * 2f * PI.toFloat()
    fun wave(y: Float, a: Float, color: Color, dashed: Boolean) {
        val p = Path()
        for (i in 0..60) {
            val x = x0 + w * i / 60f
            val v = y - a * sin(i / 60f * 4f * PI.toFloat() - shift)
            if (i == 0) p.moveTo(x, v) else p.lineTo(x, v)
        }
        drawPath(p, color, style = Stroke(2.5.dp.toPx(), cap = StrokeCap.Round, pathEffect = if (dashed) dash else null))
    }
    wave(rowH * 0.8f, amp, col.left, false)
    wave(rowH * 1.9f, -amp * inv, col.right, true)
    drawLine(col.line, Offset(x0, rowH * 2.55f), Offset(x0 + w, rowH * 2.55f), 1.dp.toPx())
    wave(rowH * 3.2f, amp * (1f - inv), col.ink, false)
}

/** 3: Bell Labs 1960s -> RACE 2007 (two loudspeakers close together) -> the phone at the same angle. */
private fun DrawScope.sceneOrigin(t: Float, col: StageColors, measurer: androidx.compose.ui.text.TextMeasurer) {
    val s = Stage(size.width, size.height * 0.8f)
    val m = smooth((t - 0.35f) / 0.4f)          // 0 = loudspeakers far away, 1 = the phone
    val far = 2.4f
    val y = s.headY - (s.headY - s.phoneY) * (far + (1f - far) * m)
    val spread = (s.spR.x - s.cx) * (far + (1f - far) * m)
    // the same angle in both cases
    val arc = Path().apply { moveTo(s.cx - spread, y); lineTo(s.cx, s.headY - s.headR); lineTo(s.cx + spread, y) }
    drawPath(arc, col.ink.copy(alpha = 0.25f), style = Stroke(1.5.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))))
    if (m < 1f) {
        val box = Size(s.unit * 0.7f, s.unit * 1.0f)
        for ((sx, color) in listOf(-spread to col.left, spread to col.right)) {
            drawRoundRect(color.copy(alpha = 1f - m), Offset(s.cx + sx - box.width / 2f, y - box.height / 2f), box, CornerRadius(8f))
        }
    }
    if (m > 0f) {
        val ps = Stage(size.width, size.height * 0.8f)
        val alpha = m
        drawRoundRect(col.ink.copy(alpha = 0.85f * alpha), Offset(ps.cx - ps.phoneW / 2f, ps.phoneY - ps.phoneH / 2f),
            Size(ps.phoneW, ps.phoneH), CornerRadius(ps.phoneH * 0.35f))
        drawCircle(col.left.copy(alpha = alpha), ps.unit * 0.17f, ps.spL)
        drawCircle(col.right.copy(alpha = alpha), ps.unit * 0.17f, ps.spR)
    }
    head(s, col)
    // timeline
    val ty = size.height * 0.92f
    val labels = listOf("1960s Bell Labs", "2007 RACE", "Rootnote")
    drawLine(col.line, Offset(size.width * 0.1f, ty), Offset(size.width * 0.9f, ty), 2.dp.toPx())
    val now = t * 1.2f
    for ((i, label) in labels.withIndex()) {
        val x = size.width * (0.15f + 0.35f * i)
        val lit = now > i * 0.35f
        drawCircle(if (lit) col.right else col.line, 5.dp.toPx(), Offset(x, ty))
        val r = measurer.measure(label, TextStyle(fontSize = 11.dp.toSp(), color = if (lit) col.ink else col.soft))
        drawText(r, topLeft = Offset(x - r.size.width / 2f, ty - 10.dp.toPx() - r.size.height))
    }
}

/** 4: distance and head size (interactive): the delay follows the distance much more than the head size. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DistanceScene(state: StoryState, col: StageColors, description: String) {
    val c = rootnotePalette()
    var dist by rememberSaveable { mutableFloatStateOf(state.distanceCm.toFloat()) }
    var hat by rememberSaveable { mutableIntStateOf(state.hatCm) }
    val spacing = 15.5f
    val radius = 0.0875f * hat / 57f
    val theta = atan((spacing * 0.005f) / (dist * 0.01f))
    val delayMs = radius / 343f * (theta + sin(theta)) * 1000f
    val degrees = (2 * theta * 180f / PI.toFloat()).roundToInt()
    BoxWithConstraints(Modifier.fillMaxSize().padding(12.dp)) {
    val stageH = maxHeight * 0.62f
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Canvas(Modifier.height(stageH).fillMaxWidth().semantics { contentDescription = description }) {
            val s = Stage(size.width, size.height, distanceScale = dist / 40f * 0.75f, headScale = hat / 57f)
            val apex = Offset(s.cx, s.headY - s.headR)
            drawLine(col.left.copy(alpha = 0.7f), s.spL, apex, 2.dp.toPx())
            drawLine(col.right.copy(alpha = 0.7f), s.spR, apex, 2.dp.toPx())
            phone(s, col)
            head(s, col)
        }
        Text(
            stringResource(R.string.story_delay, dist.roundToInt(), degrees, String.format(java.util.Locale.ROOT, "%.2f", delayMs)),
            color = c.xtcAccentText, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold,
        )
        // distance: drag across the bar (25..60 cm)
        DragBar(
            value = (dist - 25f) / 35f,
            label = stringResource(R.string.home_xtc_distance),
            valueText = "${dist.roundToInt()} cm",
            fill = c.xtcFill, track = c.sliderInactive, thumb = c.thumb,
        ) { f -> dist = 25f + 35f * f }
        FlowRow(Modifier.selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((h, label) in listOf(54 to R.string.home_xtc_head_s, 57 to R.string.home_xtc_head_m, 60 to R.string.home_xtc_head_l)) {
                val sel = hat == h
                Box(
                    Modifier
                        .heightIn(min = 48.dp)
                        .background(if (sel) c.xtcChipSelectedBg else c.chipBg, CircleShape)
                        .border(1.dp, if (sel) c.xtcChipSelectedBorder else c.chipBorder, CircleShape)
                        .selectable(selected = sel, role = Role.RadioButton) { hat = h }
                        .padding(horizontal = 14.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(stringResource(label), color = if (sel) c.xtcChipSelectedText else c.chipText, fontSize = 14.sp, lineHeight = 20.sp)
                }
            }
        }
    }
    }
}

/** A plain drag bar (0..1) for the distance demo; tap or drag. */
@Composable
private fun DragBar(value: Float, label: String, valueText: String, fill: Color, track: Color, thumb: Color, onChange: (Float) -> Unit) {
    var width by remember { mutableFloatStateOf(1f) }
    var inset by remember { mutableFloatStateOf(0f) }
    fun at(x: Float) = ((x - inset) / (width - 2 * inset).coerceAtLeast(1f)).coerceIn(0f, 1f)
    Box(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .onSizeChanged { width = it.width.toFloat().coerceAtLeast(1f) }
            .pointerInput(Unit) {
                inset = 12.dp.toPx()
                detectTapGestures(onTap = { onChange(at(it.x)) })
            }
            .pointerInput(Unit) {
                detectHorizontalDragGestures { change, _ ->
                    change.consume()
                    onChange(at(change.position.x))
                }
            }
            .semantics(mergeDescendants = true) {
                contentDescription = label
                stateDescription = valueText
                progressBarRangeInfo = ProgressBarRangeInfo(value.coerceIn(0f, 1f), 0f..1f, steps = 34)
                setProgress { v -> onChange(v.coerceIn(0f, 1f)); true }
            },
        contentAlignment = Alignment.CenterStart,
    ) {
        Canvas(Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            val y = size.height / 2f
            val r = 12.dp.toPx()
            drawLine(track, Offset(r, y), Offset(size.width - r, y), 4.dp.toPx(), StrokeCap.Round)
            val x = r + (size.width - 2 * r) * value.coerceIn(0f, 1f)
            drawLine(fill, Offset(r, y), Offset(x, y), 4.dp.toPx(), StrokeCap.Round)
            drawCircle(Color.Black.copy(alpha = 0.12f), r + 1.dp.toPx(), Offset(x, y + 1.dp.toPx()))
            drawCircle(thumb, r, Offset(x, y))
        }
    }
}

/** 5: the best spot glows in front of the face; moving sideways misaligns the cancelling and the glow fades. */
private fun DrawScope.sceneSweetSpot(t: Float, col: StageColors) {
    val s = Stage(size.width, size.height)
    val dx = s.unit * 1.6f * sin(2 * PI.toFloat() * t)
    val off = abs(dx) / (s.unit * 1.6f)
    val glowC = Offset(s.cx, s.headY)
    drawCircle(
        Brush.radialGradient(listOf(col.right.copy(alpha = 0.35f), Color.Transparent), glowC, s.unit * 1.8f),
        s.unit * 1.8f, glowC,
    )
    val aligned = 1f - off
    val dash = PathEffect.dashPathEffect(floatArrayOf(10f, 8f))
    val earL = Offset(s.earL.x + dx, s.earL.y)
    val earR = Offset(s.earR.x + dx, s.earR.y)
    drawLine(col.left.copy(alpha = 0.3f + 0.6f * aligned), s.spL, earR, 2.dp.toPx(), pathEffect = if (aligned < 0.5f) dash else null)
    drawLine(col.right.copy(alpha = 0.3f + 0.6f * aligned), s.spR, earL, 2.dp.toPx(), pathEffect = if (aligned < 0.5f) dash else null)
    phone(s, col)
    head(s, col, dx)
    // "still sounds": two notes stay on the phone
    drawCircle(col.ink.copy(alpha = 0.6f), s.unit * 0.1f, Offset(s.cx - s.unit * 0.3f, s.phoneY + s.unit * 1.1f))
    drawCircle(col.ink.copy(alpha = 0.6f), s.unit * 0.1f, Offset(s.cx + s.unit * 0.3f, s.phoneY + s.unit * 1.1f))
}

/** 6: the frequency strip: teal below 400 Hz (virtual bass), purple 400 Hz-8 kHz (spatial); long and short waves. */
private fun DrawScope.sceneBand(t: Float, col: StageColors, measurer: androidx.compose.ui.text.TextMeasurer) {
    fun xOf(f: Float): Float {
        val lo = ln(20f); val hi = ln(20000f)
        return size.width * 0.06f + size.width * 0.88f * ((ln(f) - lo) / (hi - lo))
    }
    val y = size.height * 0.72f
    val h = size.height * 0.08f
    val grow = smooth(t * 2f)
    drawRoundRect(col.line, Offset(xOf(20f), y), Size(xOf(20000f) - xOf(20f), h), CornerRadius(h / 2f))
    drawRoundRect(col.left, Offset(xOf(20f), y), Size((xOf(400f) - xOf(20f)) * grow, h), CornerRadius(h / 2f))
    drawRoundRect(col.right, Offset(xOf(400f), y), Size((xOf(8000f) - xOf(400f)) * grow, h), CornerRadius(h / 2f))
    for ((f, label) in listOf(20f to "20 Hz", 400f to "400 Hz", 8000f to "8 kHz", 20000f to "20 kHz")) {
        val r = measurer.measure(label, TextStyle(fontSize = 11.dp.toSp(), color = col.soft))
        val x = (xOf(f) - r.size.width / 2f).coerceAtMost(size.width - r.size.width).coerceAtLeast(0f)
        drawText(r, topLeft = Offset(x, y + h + 6.dp.toPx()))
    }
    // a long bass wave over the teal part, short waves over the purple part
    val shift = t * 2f * PI.toFloat()
    fun wave(x0: Float, x1: Float, cycles: Float, color: Color, yMid: Float, amp: Float) {
        val p = Path()
        for (i in 0..80) {
            val x = x0 + (x1 - x0) * i / 80f
            val v = yMid - amp * sin(i / 80f * cycles * 2f * PI.toFloat() - shift)
            if (i == 0) p.moveTo(x, v) else p.lineTo(x, v)
        }
        drawPath(p, color, style = Stroke(3.dp.toPx(), cap = StrokeCap.Round))
    }
    wave(xOf(20f), xOf(400f), 0.75f, col.left, size.height * 0.38f, size.height * 0.18f)
    wave(xOf(400f), xOf(8000f), 6f, col.right, size.height * 0.38f, size.height * 0.08f)
}

/** 7: presets (interactive): the centre dot (vocals) and the side dots (instruments) spread differently. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PresetScene(state: StoryState, col: StageColors, description: String) {
    val c = rootnotePalette()
    var preset by rememberSaveable { mutableIntStateOf(1) }
    val spread by animateFloatAsState(
        when (preset) { 0 -> 0.55f; 1 -> 0.8f; else -> 1f }, tween(if (state.reduceMotion) 0 else RN_MS_MOVE, easing = Ease), label = "spread",
    )
    val tint by animateFloatAsState(
        when (preset) { 0 -> 0f; 1 -> 0.4f; else -> 0.6f }, tween(if (state.reduceMotion) 0 else RN_MS_MOVE, easing = Ease), label = "tint",
    )
    BoxWithConstraints(Modifier.fillMaxSize().padding(12.dp)) {
    val stageH = maxHeight * 0.7f
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Canvas(Modifier.height(stageH).fillMaxWidth().semantics { contentDescription = description }) {
            val s = Stage(size.width, size.height)
            phone(s, col)
            head(s, col)
            val y = s.phoneY + s.unit * 1.5f
            val maxDx = s.unit * 3.6f
            // side dots (instruments) spread out, the centre dot (vocals) stays; its colour changes in full mode
            for (sign in listOf(-1f, 1f)) {
                val x = s.cx + sign * maxDx * spread
                drawCircle((if (sign < 0) col.left else col.right).copy(alpha = 0.25f), s.unit * 0.42f, Offset(x, y))
                drawCircle(if (sign < 0) col.left else col.right, s.unit * 0.22f, Offset(x, y))
            }
            val centre = lerpColor(col.ink, col.right, tint)
            drawCircle(centre.copy(alpha = 0.2f), s.unit * 0.42f, Offset(s.cx, y))
            drawCircle(centre, s.unit * 0.22f, Offset(s.cx, y))
        }
        FlowRow(Modifier.selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((i, label) in listOf(R.string.home_xtc_chip_subtle, R.string.home_xtc_chip_balanced, R.string.home_xtc_chip_clear).withIndex()) {
                val sel = preset == i
                Box(
                    Modifier
                        .heightIn(min = 48.dp)
                        .background(if (sel) c.xtcChipSelectedBg else c.chipBg, CircleShape)
                        .border(1.dp, if (sel) c.xtcChipSelectedBorder else c.chipBorder, CircleShape)
                        .selectable(selected = sel, role = Role.RadioButton) { preset = i }
                        .padding(horizontal = 14.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(stringResource(label), color = if (sel) c.xtcChipSelectedText else c.chipText, fontSize = 14.sp, lineHeight = 20.sp)
                }
            }
        }
    }
    }
}

private fun lerpColor(a: Color, b: Color, f: Float) = Color(
    a.red + (b.red - a.red) * f, a.green + (b.green - a.green) * f, a.blue + (b.blue - a.blue) * f, a.alpha + (b.alpha - a.alpha) * f,
)

/** 8: the honest picture: the stage, with the effect breathing between off and on (the listening control is beside). */
private fun DrawScope.sceneLimits(t: Float, col: StageColors) {
    val s = Stage(size.width, size.height)
    val on = 0.5f - 0.5f * cos(2 * PI.toFloat() * t)
    val y = s.phoneY + s.unit * 1.5f
    val spread = s.unit * (0.6f + 3.0f * on)
    drawCircle(col.left, s.unit * 0.2f, Offset(s.cx - spread, y))
    drawCircle(col.right, s.unit * 0.2f, Offset(s.cx + spread, y))
    drawCircle(col.ink, s.unit * 0.2f, Offset(s.cx, y))
    phone(s, col)
    head(s, col)
    val fade = exp(-3f * (1f - on))
    drawCircle(
        Brush.radialGradient(listOf(col.right.copy(alpha = 0.25f * fade), Color.Transparent), Offset(s.cx, s.headY), s.unit * 2f),
        s.unit * 2f, Offset(s.cx, s.headY),
    )
}

/**
 * 8: held upright (seen from the front this time): the phone turns from sideways to upright, its two speakers end
 * up above each other, at the same distance from both ears (nothing to cancel); then the two-way split: a long
 * teal wave (bass) from the bottom speaker, short purple waves (highs) from the top one.
 */
private fun DrawScope.scenePortrait(t: Float, col: StageColors) {
    val unit = min(size.width / 10f, size.height / 7f)
    val cx = size.width / 2f
    // face (front view): head, ears at the sides
    val headC = Offset(cx, size.height * 0.36f)
    val headR = unit * 1.5f
    drawCircle(col.bg, headR, headC)
    drawCircle(col.ink.copy(alpha = 0.7f), headR, headC, style = Stroke(2.dp.toPx()))
    val earL = Offset(cx - headR, headC.y)
    val earR = Offset(cx + headR, headC.y)
    drawCircle(col.ink.copy(alpha = 0.7f), unit * 0.18f, earL)
    drawCircle(col.ink.copy(alpha = 0.7f), unit * 0.18f, earR)
    // the phone in front of the face, lower down, turning upright
    val turn = smooth(t / 0.3f)
    val angle = 90f * turn
    val pc = Offset(cx, size.height * 0.74f)
    val len = unit * 3.2f
    val wid = unit * 0.9f
    rotate(angle, pc) {
        drawRoundRect(col.ink.copy(alpha = 0.85f), Offset(pc.x - len / 2, pc.y - wid / 2), Size(len, wid), CornerRadius(wid * 0.35f))
    }
    val rad = Math.toRadians(angle.toDouble())
    val dx = (len / 2 - unit * 0.35f) * kotlin.math.cos(rad).toFloat()
    val dy = (len / 2 - unit * 0.35f) * kotlin.math.sin(rad).toFloat()
    val top = Offset(pc.x + dx, pc.y - dy)        // the earpiece ends up on top
    val bottom = Offset(pc.x - dx, pc.y + dy)
    drawCircle(col.right, unit * 0.17f, top)
    drawCircle(col.left, unit * 0.17f, bottom)
    // upright: both speakers the same distance from both ears
    val equal = smooth((t - 0.3f) / 0.15f) * (1f - smooth((t - 0.55f) / 0.1f))
    if (equal > 0f) {
        val dash = PathEffect.dashPathEffect(floatArrayOf(8f, 6f))
        for (sp in listOf(top, bottom)) for (ear in listOf(earL, earR))
            drawLine(col.soft.copy(alpha = 0.8f * equal), sp, ear, 1.5.dp.toPx(), pathEffect = dash)
    }
    // the two-way split: bass from the bottom, highs from the top
    val split = smooth((t - 0.6f) / 0.15f)
    if (split > 0f) {
        val phase = (t * 3f) % 1f
        for (k in 0 until 2) {
            val p = (phase + k * 0.5f) % 1f
            val r = unit * 2.6f * p
            drawCircle(col.left.copy(alpha = split * (1f - p) * 0.9f), r, bottom, style = Stroke(4.dp.toPx()))
        }
        for (k in 0 until 4) {
            val p = (phase * 2f + k * 0.25f) % 1f
            val r = unit * 1.6f * p
            drawCircle(col.right.copy(alpha = split * (1f - p) * 0.9f), r, top, style = Stroke(1.5.dp.toPx()))
        }
    }
}

/**
 * 10: side by side, gently. Left, a usual widener: the side sound is pushed outwards, but both speakers still reach
 * both ears (the leak lines stay) and a wobble hangs around the head. Right, spatial: the leak lines fade away and
 * the sound moves out beside the ears. Same phone, same head, same colours as the other scenes.
 */
private fun DrawScope.sceneCompare(t: Float, col: StageColors, measurer: androidx.compose.ui.text.TextMeasurer, labels: List<String>) {
    val half = size.width / 2f
    drawLine(col.line, Offset(half, size.height * 0.08f), Offset(half, size.height * 0.95f), 1.dp.toPx())
    val grow = smooth(t / 0.5f)
    for (side in 0..1) {
        val x0 = side * half
        val label = measurer.measure(
            labels.getOrElse(side) { "" },
            TextStyle(fontSize = 13.dp.toSp(), color = if (side == 0) col.soft else col.right, fontWeight = FontWeight.Bold),
        )
        drawText(label, topLeft = Offset(x0 + ((half - label.size.width) / 2f).coerceAtLeast(0f), 0f))
        val top = label.size.height + 6.dp.toPx()
        translate(left = x0, top = top) {
            val s = Stage(half, size.height - top)
            val dash = PathEffect.dashPathEffect(floatArrayOf(8f, 6f))
            if (side == 0) {
                // leak lines stay; the side sound is pushed outwards; a small wobble around the head
                drawLine(col.left.copy(alpha = 0.7f), s.spL, s.earR, 2.dp.toPx())
                drawLine(col.right.copy(alpha = 0.7f), s.spR, s.earL, 2.dp.toPx())
                val y = s.phoneY + s.unit * 1.4f
                val reach = s.unit * (0.6f + 1.4f * grow)
                drawLine(col.soft, Offset(s.cx - s.unit * 0.3f, y), Offset(s.cx - reach, y), 2.dp.toPx(), StrokeCap.Round)
                drawLine(col.soft, Offset(s.cx + s.unit * 0.3f, y), Offset(s.cx + reach, y), 2.dp.toPx(), StrokeCap.Round)
                val wob = Path()
                for (i in 0..40) {
                    val a = i / 40f * 2f * PI.toFloat()
                    val r = s.headR * 1.25f + s.unit * 0.08f * grow * sin(6f * a + t * 12f)
                    val px = s.cx + r * cos(a)
                    val py = s.headY + r * sin(a)
                    if (i == 0) wob.moveTo(px, py) else wob.lineTo(px, py)
                }
                drawPath(wob, col.soft.copy(alpha = 0.6f), style = Stroke(1.5.dp.toPx()))
                drawCircle(col.ink.copy(alpha = 0.6f), s.unit * 0.18f, Offset(s.cx - reach * 0.5f, y))
                drawCircle(col.ink.copy(alpha = 0.6f), s.unit * 0.18f, Offset(s.cx + reach * 0.5f, y))
            } else {
                // the leak lines fade out; the sound moves out beside the ears
                val fade = 1f - grow
                drawLine(col.left.copy(alpha = 0.7f * fade), s.spL, s.earR, 2.dp.toPx(), pathEffect = dash)
                drawLine(col.right.copy(alpha = 0.7f * fade), s.spR, s.earL, 2.dp.toPx(), pathEffect = dash)
                drawLine(col.left.copy(alpha = 0.8f), s.spL, s.earL, 2.dp.toPx())
                drawLine(col.right.copy(alpha = 0.8f), s.spR, s.earR, 2.dp.toPx())
                val out = s.headR + s.unit * (0.2f + 0.9f * grow)
                drawCircle(col.left, s.unit * 0.2f, Offset(s.cx - out, s.headY))
                drawCircle(col.right, s.unit * 0.2f, Offset(s.cx + out, s.headY))
            }
            phone(s, col)
            head(s, col)
        }
    }
}

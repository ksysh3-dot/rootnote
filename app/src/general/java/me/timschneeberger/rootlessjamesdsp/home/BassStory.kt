package me.timschneeberger.rootlessjamesdsp.home

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log2
import kotlin.math.max
import kotlin.math.sin

/*
 * The EQ explanation as a landscape motion story (BassStoryActivity), in the spatial story's format (SpatialStory.kt):
 * one message per scene carried by one motion, few shapes (the response chart, a speaker cone, level bars), the same
 * chart staying on stage from scene to scene, teal (the bass colour) as the accent. The text beside each scene says
 * everything on its own; the motion only helps. With the system animations off every scene shows one still key frame.
 *
 * Message: boosting the lowest EQ bands (32-125 Hz) adds little bass one can hear and costs rattle, buzz and the
 * phone's own protection; a little at 200-400 Hz plus cutting the treble peak does more.
 */

/** Third-octave bands, dB re the mean of 630-2000 Hz ("mids"). */
internal object PhoneResponse {
    val HZ = floatArrayOf(125f, 160f, 200f, 250f, 315f, 400f, 500f, 630f, 800f, 1000f, 1250f, 1600f, 2000f, 2500f,
        3150f, 4000f, 5000f, 6300f, 8000f, 10000f, 12500f)
    /** Galaxy S26 Ultra, our UMIK-1 measurement (30 cm, volume 60/150, Dolby Atmos off). */
    val S26U = floatArrayOf(-21.7f, -15.5f, -10.4f, -6.4f, -7.5f, -7.1f, -6.2f, -4.3f, -0.5f, -1.2f, 1.5f, 0.8f, 3.8f,
        9.2f, 9.6f, 9.4f, 14.2f, 11.8f, 6.4f, -3.1f, -13.5f)
    /**
     * Android phones, estimated (one reviewer's measurements moved into our frame by difference transfer,
     * docs/SPEAKER_ESTIMATES.md): 10th percentile, median, 90th percentile per band. Aggregate only, by data policy.
     */
    val P10 = floatArrayOf(-30.9f, -21.3f, -16.0f, -9.6f, -8.4f, -7.5f, -8.6f, -9.2f, -3.9f, -0.7f, -0.5f, -2.7f, -0.1f,
        4.0f, 5.2f, 3.9f, 8.1f, 6.9f, 2.0f, -11.6f, -15.3f)
    val P50 = floatArrayOf(-23.1f, -14.5f, -10.7f, -5.5f, -5.0f, -4.6f, -5.9f, -5.5f, -1.8f, 1.7f, 2.6f, 0.0f, 3.1f,
        9.2f, 12.6f, 11.2f, 14.1f, 12.4f, 6.2f, -5.0f, -8.9f)
    val P90 = floatArrayOf(-16.5f, -9.4f, -5.3f, -1.1f, 0.3f, -0.6f, -1.9f, -1.5f, 1.2f, 3.7f, 4.6f, 2.9f, 5.7f, 12.7f,
        16.3f, 15.2f, 19.0f, 17.8f, 11.2f, 0.9f, -1.8f)
    /** The median phone is 10 dB under its mids here. */
    const val MEDIAN_MINUS10_HZ = 206f
}

private val Ease = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)
private const val SCENES = 10
/** The page with "직접 들어 보기" (63 Hz +10 dB at a moment the listener is not told). */
private const val TRY_PAGE = 5
private val PERIODS = intArrayOf(4200, 4000, 3200, 4000, 3600, 2000, 3600, 3600, 5200, 4200)
private val KEY_FRAMES = floatArrayOf(0.9f, 0.55f, 0.3f, 0.45f, 0.6f, 0f, 0.5f, 0.5f, 0.95f, 0.9f)

/**
 * The listening trial of [TRY_PAGE], driven by BassStoryActivity: [phase] IDLE, PREP (the trial's base settings
 * settle), RUN (30 s; 63 Hz goes up 10 dB from [changeFrom] to [changeTo] s, not shown until DONE), DONE.
 */
@Immutable
data class TryUi(
    val canTry: Boolean = false,
    val volumeTooHigh: Boolean = false,
    val phase: Int = IDLE,
    val elapsed: Float = 0f,
    val lengthS: Float = 30f,
    val changeFrom: Float = 0f,
    val changeTo: Float = 0f,
    val tapAt: Float? = null,
    /** After a hit: 0 bass, 1 rattle, 2 not sure. */
    val kind: Int? = null,
    val restored: Boolean = false,
) {
    val hit: Boolean get() = tapAt != null && tapAt >= changeFrom && tapAt <= changeTo + 3f
    companion object { const val IDLE = 0; const val PREP = 1; const val RUN = 2; const val DONE = 3 }
}

class TryActions(val onStart: () -> Unit, val onTap: () -> Unit, val onKind: (Int) -> Unit, val onAgain: () -> Unit)

@Composable
fun BassStory(reduceMotion: Boolean, trial: TryUi, actions: TryActions, onClose: () -> Unit) {
    val c = rootnotePalette()
    val items = stringArrayResource(R.array.eq_story)
    val pager = rememberPagerState { SCENES }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().background(c.bg).safeDrawingPadding()) {
        Row(Modifier.fillMaxWidth().padding(start = 24.dp, end = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                stringResource(R.string.eq_info_title),
                modifier = Modifier.weight(1f).semantics { heading() },
                color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                for (i in 0 until SCENES) {
                    val on = i == pager.currentPage
                    val w by animateFloatAsState(if (on) 18f else 6f, tween(if (reduceMotion) 0 else 300, easing = Ease), label = "dot")
                    Box(Modifier.size(width = w.dp, height = 6.dp).background(if (on) c.fill else c.divider, CircleShape))
                }
            }
            Spacer(Modifier.width(8.dp))
            val closeLabel = stringResource(R.string.home_xtc_info_close)
            Box(
                Modifier.size(48.dp).clickable(role = Role.Button, onClick = onClose).semantics { contentDescription = closeLabel },
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
                    Modifier.weight(0.6f).fillMaxHeight().padding(vertical = 8.dp).background(c.band, RoundedCornerShape(20.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Scene(page, reduceMotion, active = page == pager.currentPage, trial = trial)
                }
                Column(
                    Modifier.weight(0.4f).fillMaxHeight().padding(start = 20.dp, top = 8.dp, bottom = 8.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("${page + 1} / $SCENES", color = c.accentText, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Bold)
                    Text(items.getOrElse(2 * page) { "" }, modifier = Modifier.semantics { heading() },
                        color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold)
                    Text(items.getOrElse(2 * page + 1) { "" }, color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
                    if (page == TRY_PAGE) TryControl(trial, actions)
                }
            }
        }

        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
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
        Modifier.heightIn(min = 48.dp)
            .then(if (filled) Modifier.background(c.fill, CircleShape) else Modifier.border(1.dp, if (enabled) c.chipBorder else c.divider, CircleShape))
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 22.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = when { filled -> c.onFill; enabled -> c.textPrimary; else -> c.chevron },
            fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold)
    }
}

// ------------------------------------------------------------------------------------------------- the stage

/** Colours of the stage: teal = the bass colour (and "plays"), grey = "hardly plays", orange = trouble. */
private class Ink(val accent: Color, val text: Color, val soft: Color, val grey: Color, val warn: Color, val bg: Color)

private val Orange = Color(0xFFE8892F)

@Composable
private fun Scene(page: Int, reduceMotion: Boolean, active: Boolean, trial: TryUi) {
    val c = rootnotePalette()
    val ink = remember(c) { Ink(c.fill, c.textPrimary, c.textSecondary, c.chevron, Orange, c.bg) }
    val clock: State<Float> = if (reduceMotion || !active) {
        remember(page) { mutableFloatStateOf(KEY_FRAMES[page]) }
    } else {
        val inf = rememberInfiniteTransition(label = "eq$page")
        inf.animateFloat(KEY_FRAMES[page], KEY_FRAMES[page] + 1f,
            infiniteRepeatable(tween(PERIODS[page], easing = LinearEasing), RepeatMode.Restart), label = "t$page")
    }
    val description = stringArrayResource(R.array.eq_story_a11y).getOrElse(page) { "" }
    val labels = stringArrayResource(R.array.eq_story_labels)
    val tm = rememberTextMeasurer()
    Canvas(Modifier.fillMaxSize().padding(12.dp).semantics { contentDescription = description }) {
        val t = clock.value % 1f
        when (page) {
            0 -> sceneResponse(t, ink, tm, labels)
            1 -> sceneCrank(t, ink, tm, labels)
            2 -> sceneCone(t, ink, tm, labels)
            3 -> sceneProtect(t, ink, tm, labels)
            4 -> sceneSkirt(t, ink, tm, labels)
            5 -> sceneTry(t, ink, trial)
            6 -> sceneLowMid(t, ink, tm, labels)
            7 -> sceneTreble(t, ink, tm, labels)
            8 -> sceneResults(t, ink, tm, labels)
            else -> sceneRecipe(t, ink, tm, labels)
        }
    }
}

private fun smooth(x: Float): Float { val v = x.coerceIn(0f, 1f); return v * v * (3f - 2f * v) }

/** 0 -> 1 over [a, b] of the loop, then held. */
private fun phase(t: Float, a: Float, b: Float) = smooth((t - a) / (b - a))

private fun DrawScope.text(tm: TextMeasurer, s: String, x: Float, y: Float, color: Color, size: Float = 12f,
                           bold: Boolean = false, align: Float = 0f) {
    val r = tm.measure(s, TextStyle(fontSize = size.sp, fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium))
    val left = (x - r.size.width * align).coerceIn(0f, max(0f, this.size.width - r.size.width))
    drawText(r, color = color, topLeft = Offset(left, y))
}

/** The response chart's frame: log 25 Hz-16 kHz across, +20..-35 dB down. */
private class Chart(w: Float, h: Float) {
    val left = w * 0.09f
    val right = w * 0.98f
    val top = h * 0.12f
    val bottom = h * 0.84f
    fun x(hz: Float) = left + (right - left) * (ln(hz / 25f) / ln(16000f / 25f))
    fun y(db: Float) = top + (bottom - top) * ((20f - db.coerceIn(-35f, 20f)) / 55f)
}

private fun bell(hz: Float, f0: Float, gainDb: Float, widthOct: Float): Float {
    val d = log2(hz / f0) / widthOct
    return gainDb * exp(-0.5f * d * d)
}

private fun DrawScope.zonesAndGrid(ch: Chart, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val x125 = ch.x(125f)
    val x10 = ch.x(PhoneResponse.MEDIAN_MINUS10_HZ)
    drawRect(ink.grey.copy(alpha = 0.30f), Offset(ch.left, ch.top), Size(x125 - ch.left, ch.bottom - ch.top))
    drawRect(ink.grey.copy(alpha = 0.16f), Offset(x125, ch.top), Size(x10 - x125, ch.bottom - ch.top))
    drawRect(ink.accent.copy(alpha = 0.10f), Offset(x10, ch.top), Size(ch.right - x10, ch.bottom - ch.top))
    text(tm, labels.getOrElse(0) { "" }, ch.left + 4.dp.toPx(), ch.top + 3.dp.toPx(), ink.soft, 11f)
    text(tm, labels.getOrElse(1) { "" }, x10 + 4.dp.toPx(), ch.top + 3.dp.toPx(), ink.accent, 11f, bold = true)
    for (db in intArrayOf(10, 0, -10, -20, -30)) {
        val y = ch.y(db.toFloat())
        drawLine(ink.grey.copy(alpha = if (db == 0) 0.8f else 0.3f), Offset(ch.left, y), Offset(ch.right, y),
            (if (db == 0) 1.2f else 0.8f).dp.toPx())
        text(tm, if (db > 0) "+$db" else "$db", ch.left - 4.dp.toPx(), y - 8.dp.toPx(), ink.soft, 10f, align = 1f)
    }
    drawLine(ink.grey, Offset(ch.left, ch.bottom), Offset(ch.right, ch.bottom), 1.dp.toPx())
    for ((hz, s) in listOf(31f to "31", 62f to "62", 125f to "125", 250f to "250", 500f to "500", 1000f to "1k",
        2000f to "2k", 4000f to "4k", 8000f to "8k")) {
        val x = ch.x(hz)
        drawLine(ink.grey, Offset(x, ch.bottom), Offset(x, ch.bottom + 3.dp.toPx()), 1.dp.toPx())
        text(tm, s, x, ch.bottom + 4.dp.toPx(), ink.soft, 10f, align = 0.5f)
    }
}

private fun DrawScope.curve(ch: Chart, db: (Int) -> Float, color: Color, width: Float, dashed: Boolean = false) {
    val p = Path()
    for (i in PhoneResponse.HZ.indices) {
        val x = ch.x(PhoneResponse.HZ[i]); val y = ch.y(db(i))
        if (i == 0) p.moveTo(x, y) else p.lineTo(x, y)
    }
    drawPath(p, color, style = Stroke(width, cap = StrokeCap.Round,
        pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(10f, 7f), 0f) else null))
}

private fun DrawScope.phoneBand(ch: Chart, ink: Ink) {
    val p = Path()
    PhoneResponse.HZ.forEachIndexed { i, f -> if (i == 0) p.moveTo(ch.x(f), ch.y(PhoneResponse.P90[i])) else p.lineTo(ch.x(f), ch.y(PhoneResponse.P90[i])) }
    for (i in PhoneResponse.HZ.indices.reversed()) p.lineTo(ch.x(PhoneResponse.HZ[i]), ch.y(PhoneResponse.P10[i]))
    p.close()
    drawPath(p, ink.accent.copy(alpha = 0.22f))
}

/** 1: the chart draws itself from the left: the phones' range, the median phone, our S26 Ultra (dashed). */
private fun DrawScope.sceneResponse(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val ch = Chart(size.width, size.height)
    zonesAndGrid(ch, ink, tm, labels)
    val reveal = phase(t, 0.05f, 0.7f)
    clipRect(right = ch.left + (ch.right - ch.left) * reveal) {
        phoneBand(ch, ink)
        curve(ch, { PhoneResponse.P50[it] }, ink.accent, 2.5f.dp.toPx())
        curve(ch, { PhoneResponse.S26U[it] }, ink.text, 1.5f.dp.toPx(), dashed = true)
    }
    // the -23 dB at 125 Hz, once drawn
    val a = phase(t, 0.7f, 0.8f)
    if (a > 0f) {
        val p = Offset(ch.x(125f), ch.y(PhoneResponse.P50[0]))
        drawCircle(ink.accent.copy(alpha = a), 4.dp.toPx(), p)
        text(tm, labels.getOrElse(2) { "" }, p.x + 6.dp.toPx(), p.y - 18.dp.toPx(), ink.text.copy(alpha = a), 11f, bold = true)
    }
}

/** 2: the lowest EQ bands go up 10 dB; the median phone's curve barely leaves the grey part. */
private fun DrawScope.sceneCrank(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val ch = Chart(size.width, size.height)
    zonesAndGrid(ch, ink, tm, labels)
    val up = phase(t, 0.1f, 0.55f) * (1f - phase(t, 0.9f, 1f))
    // EQ knobs on 31, 62, 125 Hz rising, on the 0 dB line
    for (hz in floatArrayOf(31f, 62f, 125f)) {
        val x = ch.x(hz)
        val y0 = ch.y(0f); val y1 = ch.y(10f * up)
        drawLine(ink.warn.copy(alpha = 0.5f), Offset(x, y0), Offset(x, y1), 3.dp.toPx(), StrokeCap.Round)
        drawCircle(ink.warn, 6.dp.toPx(), Offset(x, y1))
    }
    text(tm, labels.getOrElse(3) { "" }, ch.x(31f) - 4.dp.toPx(), ch.y(10f * up) - 22.dp.toPx(), ink.warn, 11f, bold = true)
    curve(ch, { PhoneResponse.P50[it] }, ink.accent.copy(alpha = 0.45f), 2f.dp.toPx())
    // a low shelf (+10 dB under 125 Hz, half at 200 Hz) on the median phone
    curve(ch, { i ->
        val f = PhoneResponse.HZ[i]
        PhoneResponse.P50[i] + 10f * up / (1f + (f / 160f).let { it * it * it * it })
    }, ink.accent, 2.5f.dp.toPx())
    val a = phase(t, 0.55f, 0.65f) * (1f - phase(t, 0.9f, 1f))
    if (a > 0f) text(tm, labels.getOrElse(4) { "" }, ch.x(140f), ch.y(-24f), ink.text.copy(alpha = a), 11f, bold = true)
}

/** 3: two cones side by side: 250 Hz moves a little, 63 Hz (same loudness) 16 times as far and hits its limit. */
private fun DrawScope.sceneCone(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val w = size.width; val h = size.height
    val limit = h * 0.16f
    fun cone(cx: Float, amp: Float, cycles: Int, label: String, sub: String) {
        val cy = h * 0.45f
        val raw = amp * sin(2f * PI.toFloat() * cycles * t)
        val hit = abs(raw) > limit
        val dx = raw.coerceIn(-limit, limit)
        // limit marks
        for (s in floatArrayOf(-1f, 1f)) {
            drawLine(ink.soft.copy(alpha = 0.6f), Offset(cx + s * limit, cy - h * 0.2f), Offset(cx + s * limit, cy + h * 0.2f),
                1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f), 0f))
        }
        // the cone seen from the side: a short trapezoid that moves left and right
        val p = Path().apply {
            moveTo(cx + dx - h * 0.02f, cy - h * 0.06f); lineTo(cx + dx + h * 0.05f, cy - h * 0.16f)
            lineTo(cx + dx + h * 0.05f, cy + h * 0.16f); lineTo(cx + dx - h * 0.02f, cy + h * 0.06f); close()
        }
        drawPath(p, if (hit) ink.warn else ink.accent)
        // the magnet stays put
        drawRoundRect(ink.text.copy(alpha = 0.7f), Offset(cx - h * 0.12f, cy - h * 0.05f), Size(h * 0.07f, h * 0.1f), CornerRadius(4f))
        if (hit) {
            // "드르르": short zigzags at the limit
            val zx = cx + (if (raw > 0) 1f else -1f) * (limit + h * 0.07f)
            val z = Path().apply {
                moveTo(zx, cy - h * 0.12f)
                for (k in 1..6) lineTo(zx + (if (k % 2 == 0) -1f else 1f) * h * 0.025f, cy - h * 0.12f + k * h * 0.04f)
            }
            drawPath(z, ink.warn, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
        }
        text(tm, label, cx, h * 0.72f, ink.text, 14f, bold = true, align = 0.5f)
        text(tm, sub, cx, h * 0.72f + 20.dp.toPx(), ink.soft, 11f, align = 0.5f)
    }
    cone(w * 0.28f, limit * 0.22f, 8, "250 Hz", labels.getOrElse(5) { "" })
    cone(w * 0.72f, limit * 0.22f * 16f, 2, "63 Hz", labels.getOrElse(6) { "" })
}

/** 4: voice, instruments and bass; when the bass passes the protection line, every bar is pushed down. */
private fun DrawScope.sceneProtect(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val w = size.width; val h = size.height
    val base = h * 0.8f
    val maxH = h * 0.62f
    val line = 0.62f
    val bass = 0.3f + 0.6f * (0.5f - 0.5f * kotlin.math.cos(2f * PI.toFloat() * t))
    val gain = if (bass > line) line / bass else 1f
    val bars = listOf(labels.getOrElse(7) { "" } to 0.55f, labels.getOrElse(8) { "" } to 0.48f, labels.getOrElse(9) { "" } to bass)
    val bw = w * 0.14f
    for ((i, b) in bars.withIndex()) {
        val (name, v) = b
        val x = w * (0.2f + 0.27f * i)
        val hh = maxH * v * gain
        val col = if (i == 2) (if (bass > line) ink.warn else ink.accent) else ink.text.copy(alpha = 0.55f)
        drawRoundRect(col, Offset(x - bw / 2, base - hh), Size(bw, hh), CornerRadius(8.dp.toPx()))
        text(tm, name, x, base + 6.dp.toPx(), ink.soft, 12f, align = 0.5f)
    }
    val ly = base - maxH * line
    drawLine(ink.warn, Offset(w * 0.08f, ly), Offset(w * 0.95f, ly), 1.5f.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 7f), 0f))
    text(tm, labels.getOrElse(10) { "" }, w * 0.08f, ly - 18.dp.toPx(), ink.warn, 11f, bold = true)
    if (gain < 0.97f) text(tm, labels.getOrElse(11) { "" }, w * 0.5f, h * 0.04f, ink.warn, 13f, bold = true, align = 0.5f)
}

/** Peaking EQ magnitude (dB) at [hz]: the analog prototype of the usual biquad, [q] its bandwidth. */
private fun peakDb(hz: Float, f0: Float, gainDb: Float, q: Float): Float {
    val a = Math.pow(10.0, gainDb / 40.0)
    val w = (hz / f0).toDouble()
    val re = 1 - w * w
    val num = re * re + (w * a / q) * (w * a / q)
    val den = re * re + (w / (a * q)) * (w / (a * q))
    return (10 * kotlin.math.log10(num / den)).toFloat()
}

/** 5: why it seemed to work: a wide 63 Hz band's skirt still lifts 150-300 Hz, where the speaker plays. */
private fun DrawScope.sceneSkirt(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val ch = Chart(size.width, size.height)
    zonesAndGrid(ch, ink, tm, labels)
    val g = 10f * phase(t, 0.08f, 0.45f) * (1f - phase(t, 0.9f, 1f))
    // the EQ band itself, drawn around the 0 dB line
    val p = Path()
    for (k in 0..140) {
        val f = 25f * Math.pow((16000.0 / 25.0), k / 140.0).toFloat()
        val x = ch.x(f); val y = ch.y(peakDb(f, 63f, g, 0.7f))
        if (k == 0) p.moveTo(x, y) else p.lineTo(x, y)
    }
    drawPath(p, ink.warn, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
    text(tm, labels.getOrElse(25) { "" }, ch.x(30f), ch.y(12f) - 4.dp.toPx(), ink.warn, 11f, bold = true)
    // the part of the skirt that lands where the speaker plays
    val a = phase(t, 0.45f, 0.6f) * (1f - phase(t, 0.9f, 1f))
    if (a > 0f) {
        val x0 = ch.x(PhoneResponse.MEDIAN_MINUS10_HZ); val x1 = ch.x(320f)
        drawRect(ink.accent.copy(alpha = 0.22f * a), Offset(x0, ch.y(4f)), Size(x1 - x0, ch.y(0f) - ch.y(4f)))
        text(tm, labels.getOrElse(26) { "" }, x0, ch.y(4f) - 18.dp.toPx(), ink.accent.copy(alpha = a), 12f, bold = true)
    }
    curve(ch, { PhoneResponse.P50[it] }, ink.accent.copy(alpha = 0.5f), 2f.dp.toPx())
}

/**
 * 6: the trial's time bar: it fills over the 30 s; a soft pulse asks to listen while it runs; at the end the real
 * 63 Hz +10 dB stretch (orange) and the tap (a line) are shown.
 */
private fun DrawScope.sceneTry(t: Float, ink: Ink, trial: TryUi) {
    val w = size.width; val h = size.height
    val left = w * 0.08f; val right = w * 0.92f
    val y = h * 0.62f; val bh = h * 0.07f
    fun x(s: Float) = left + (right - left) * (s / trial.lengthS).coerceIn(0f, 1f)
    // a speaker, pulsing gently while the trial runs
    val cx = w / 2f; val cy = h * 0.3f
    val pulse = if (trial.phase == TryUi.RUN) 0.5f + 0.5f * sin(2f * PI.toFloat() * t) else 0f
    drawCircle(ink.accent.copy(alpha = 0.12f + 0.12f * pulse), h * (0.14f + 0.03f * pulse), Offset(cx, cy))
    drawCircle(ink.accent, h * 0.07f, Offset(cx, cy))
    drawCircle(ink.bg, h * 0.03f, Offset(cx, cy))
    drawRoundRect(ink.grey.copy(alpha = 0.35f), Offset(left, y), Size(right - left, bh), CornerRadius(bh / 2))
    val fill = when (trial.phase) { TryUi.RUN -> trial.elapsed; TryUi.DONE -> trial.lengthS; else -> 0f }
    if (fill > 0f) drawRoundRect(ink.accent.copy(alpha = 0.55f), Offset(left, y), Size(x(fill) - left, bh), CornerRadius(bh / 2))
    if (trial.phase == TryUi.DONE) {
        drawRoundRect(ink.warn, Offset(x(trial.changeFrom), y - bh * 0.35f), Size(x(trial.changeTo) - x(trial.changeFrom), bh * 1.7f),
            CornerRadius(bh / 2))
    }
    trial.tapAt?.let { tap ->
        val xt = x(tap)
        drawLine(ink.text, Offset(xt, y - bh * 1.2f), Offset(xt, y + bh * 2.2f), 2.5f.dp.toPx(), StrokeCap.Round)
    }
}

/** "직접 들어 보기": start, tap when it changed, the answer, what was heard. */
@Composable
private fun TryControl(trial: TryUi, actions: TryActions) {
    val c = rootnotePalette()
    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.eq_try_title), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
        when (trial.phase) {
            TryUi.IDLE -> when {
                !trial.canTry -> TryNote(stringResource(R.string.eq_try_unavailable))
                trial.volumeTooHigh -> TryNote(stringResource(R.string.eq_try_volume))
                else -> {
                    TryNote(stringResource(R.string.eq_try_hint))
                    StoryButton(stringResource(R.string.eq_try_start), filled = true, enabled = true, onClick = actions.onStart)
                }
            }
            TryUi.PREP -> TryNote(stringResource(R.string.eq_try_prep))
            TryUi.RUN -> {
                Text(stringResource(R.string.eq_try_focus), color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
                val tap = trial.tapAt
                if (tap == null) StoryButton(stringResource(R.string.eq_try_tap), filled = true, enabled = true, onClick = actions.onTap)
                else TryNote(stringResource(R.string.eq_try_tapped, tap.toInt()))
                TryNote(stringResource(R.string.eq_try_left, (trial.lengthS - trial.elapsed).toInt().coerceAtLeast(0)))
            }
            else -> {
                val from = trial.changeFrom.toInt(); val to = trial.changeTo.toInt()
                val tap = trial.tapAt
                val result = when {
                    tap == null -> stringResource(R.string.eq_try_none, from, to)
                    trial.hit -> stringResource(R.string.eq_try_hit, tap.toInt(), from, to)
                    else -> stringResource(R.string.eq_try_miss, tap.toInt(), from, to)
                }
                Text(result, color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
                if (trial.hit) {
                    val kinds = listOf(R.string.eq_try_kind_bass, R.string.eq_try_kind_rattle, R.string.eq_try_kind_unsure)
                    if (trial.kind == null) {
                        for ((i, k) in kinds.withIndex()) StoryButton(stringResource(k), filled = false, enabled = true) { actions.onKind(i) }
                    } else {
                        val ans = listOf(R.string.eq_try_ans_bass, R.string.eq_try_ans_rattle, R.string.eq_try_ans_unsure)[trial.kind]
                        Text(stringResource(ans), color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
                    }
                }
                if (trial.restored) TryNote(stringResource(R.string.eq_try_restored))
                StoryButton(stringResource(R.string.eq_try_again), filled = false, enabled = true, onClick = actions.onAgain)
            }
        }
    }
}

@Composable
private fun TryNote(text: String) {
    val c = rootnotePalette()
    Text(text, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
}

/** 7: a small bump at 200-400 Hz, where the speaker still plays. */
private fun DrawScope.sceneLowMid(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val ch = Chart(size.width, size.height)
    zonesAndGrid(ch, ink, tm, labels)
    val x200 = ch.x(200f); val x400 = ch.x(400f)
    drawRect(ink.accent.copy(alpha = 0.16f), Offset(x200, ch.top), Size(x400 - x200, ch.bottom - ch.top))
    val g = 3f * phase(t, 0.1f, 0.5f) * (1f - phase(t, 0.88f, 1f))
    curve(ch, { PhoneResponse.P50[it] }, ink.accent.copy(alpha = 0.45f), 2f.dp.toPx())
    curve(ch, { i -> PhoneResponse.P50[i] + bell(PhoneResponse.HZ[i], 250f, g, 0.6f) }, ink.accent, 2.5f.dp.toPx())
    text(tm, labels.getOrElse(12) { "" }, (x200 + x400) / 2f, ch.y(8f), ink.accent, 12f, bold = true, align = 0.5f)
}

/** 8: the treble peak (2.5-6 kHz, 10 dB and more over the mids) cut by 3 dB; the bass then stands out more. */
private fun DrawScope.sceneTreble(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val ch = Chart(size.width, size.height)
    zonesAndGrid(ch, ink, tm, labels)
    val x0 = ch.x(2500f); val x1 = ch.x(6300f)
    drawRect(ink.warn.copy(alpha = 0.14f), Offset(x0, ch.top), Size(x1 - x0, ch.bottom - ch.top))
    val g = -3f * phase(t, 0.1f, 0.5f) * (1f - phase(t, 0.88f, 1f))
    curve(ch, { PhoneResponse.P50[it] }, ink.accent.copy(alpha = 0.45f), 2f.dp.toPx())
    curve(ch, { i -> PhoneResponse.P50[i] + bell(PhoneResponse.HZ[i], 4500f, g, 0.7f) }, ink.accent, 2.5f.dp.toPx())
    text(tm, labels.getOrElse(13) { "" }, (x0 + x1) / 2f, ch.y(19f), ink.warn, 12f, bold = true, align = 0.5f)
}

/** 9: four results appear one after another. */
private fun DrawScope.sceneResults(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val w = size.width; val h = size.height
    val cw = w * 0.45f; val chh = h * 0.4f
    for (i in 0 until 4) {
        val a = phase(t, 0.08f + 0.17f * i, 0.2f + 0.17f * i)
        if (a <= 0f) continue
        val x = if (i % 2 == 0) w * 0.03f else w * 0.52f
        val y = if (i < 2) h * 0.06f else h * 0.54f
        drawRoundRect(ink.bg.copy(alpha = a), Offset(x, y), Size(cw, chh), CornerRadius(16.dp.toPx()))
        text(tm, labels.getOrElse(14 + 2 * i) { "" }, x + 14.dp.toPx(), y + 12.dp.toPx(), ink.accent.copy(alpha = a), 22f, bold = true)
        text(tm, labels.getOrElse(15 + 2 * i) { "" }, x + 14.dp.toPx(), y + 46.dp.toPx(), ink.text.copy(alpha = a), 12f)
    }
}

/** 10: the recommended EQ shape: low cut, a little at 220 Hz, the treble peak cut. */
private fun DrawScope.sceneRecipe(t: Float, ink: Ink, tm: TextMeasurer, labels: Array<String>) {
    val w = size.width; val h = size.height
    val left = w * 0.06f; val right = w * 0.97f
    val mid = h * 0.5f
    val dbPx = h * 0.045f
    fun x(hz: Float) = left + (right - left) * (ln(hz / 25f) / ln(16000f / 25f))
    val a = phase(t, 0.05f, 0.6f)
    fun gain(f: Float): Float {
        val hp = -12f * (1f / (1f + (f / 110f).let { it * it * it * it }))
        return a * (hp + bell(f, 220f, 2.5f, 0.6f) + bell(f, 4500f, -3f, 0.7f))
    }
    drawLine(ink.grey.copy(alpha = 0.8f), Offset(left, mid), Offset(right, mid), 1.2f.dp.toPx())
    text(tm, "0 dB", left, mid - 18.dp.toPx(), ink.soft, 10f)
    val p = Path()
    for (k in 0..120) {
        val f = 25f * (16000f / 25f).let { Math.pow(it.toDouble(), k / 120.0).toFloat() }
        val px = x(f); val py = mid - gain(f).coerceAtLeast(-12f) * dbPx
        if (k == 0) p.moveTo(px, py) else p.lineTo(px, py)
    }
    drawPath(p, ink.accent, style = Stroke(3.dp.toPx(), cap = StrokeCap.Round))
    val b = phase(t, 0.6f, 0.75f)
    if (b > 0f) {
        text(tm, labels.getOrElse(22) { "" }, x(50f), mid + 6f * dbPx, ink.soft.copy(alpha = b), 12f, bold = true, align = 0.5f)
        text(tm, labels.getOrElse(23) { "" }, x(220f), mid - 2.5f * dbPx - 26.dp.toPx(), ink.accent.copy(alpha = b), 12f, bold = true, align = 0.5f)
        text(tm, labels.getOrElse(24) { "" }, x(4500f), mid + 3f * dbPx + 6.dp.toPx(), ink.accent.copy(alpha = b), 12f, bold = true, align = 0.5f)
    }
    for ((hz, s) in listOf(62f to "62", 125f to "125", 250f to "250", 1000f to "1k", 4000f to "4k")) {
        text(tm, s, x(hz), h * 0.88f, ink.soft, 10f, align = 0.5f)
    }
}

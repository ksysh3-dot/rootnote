package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.DevHighlight
import me.timschneeberger.rootlessjamesdsp.pvb.DevMath
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevSnapshot
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarning
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

/*
 * The three graph pages of the developer-mode screen (Figma "개발자 모드 시안" 1-3, docs/DESIGN.md 5): harmonic bars,
 * time graph and headroom gauge (style A; optional analog level meter). They draw the last meter snapshot, which the
 * activity reads about 25 times a second on the main thread (never the audio thread). Every graph has a TalkBack summary
 * and an inline note; colour never carries meaning alone (zone names, status words, labels).
 */

private val Orange = Color(0xFFE8892F)

/** Value of [spec id] in the current state (the slider, so the graph follows a value before the engine reports it). */
private fun DevUiState.value(spec: me.timschneeberger.rootlessjamesdsp.pvb.DevSpec): Float = values[DevParams.ALL.indexOf(spec)]

private fun DevUiState.highlight(): DevHighlight = touched?.let { DevParams.byId(it)?.highlight } ?: DevHighlight.NONE

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GraphHeader(title: String, sub: String) {
    val c = LocalDevPalette.current
    FlowRow(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.Center) {
        Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(end = 8.dp))
        Text(sub, color = c.textSecondary, fontSize = 13.sp, lineHeight = 22.sp)
    }
}

/** The inline note under a graph: an active warning first (always shown, hidden dialog or not), else [ok]. */
@Composable
private fun GraphNote(state: DevUiState, ok: String?) {
    val tail = state.tailMs?.roundToInt() ?: 0
    when (DevMath.inlineWarning(state.active)) {
        DevWarning.NEAR_CEILING -> InlineNote(stringResource(R.string.dev_note_ceiling), true)
        DevWarning.BUZZ_ZONE -> InlineNote(stringResource(R.string.dev_note_buzz), true)
        DevWarning.TAIL -> InlineNote(stringResource(R.string.dev_note_tail, tail), true)
        DevWarning.VOLUME_NO_LINK -> InlineNote(stringResource(R.string.dev_note_volume), true)
        else -> InlineNote(ok ?: stringResource(R.string.dev_note_idle), false)
    }
}

private fun DrawScope.label(tm: TextMeasurer, text: String, x: Float, y: Float, color: Color, size: Float = 11f,
                            bold: Boolean = false, align: Float = 0.5f) {
    val r = tm.measure(text, TextStyle(fontSize = size.sp, fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium))
    val left = (x - r.size.width * align).coerceIn(0f, max(0f, this.size.width - r.size.width))
    drawText(r, color = color, topLeft = Offset(left, y))
}

private val Dash = PathEffect.dashPathEffect(floatArrayOf(10f, 7f), 0f)

// ------------------------------------------------------------------------------------------------ harmonic bars

@Composable
internal fun HarmonicPage(state: DevUiState) {
    val c = LocalDevPalette.current
    val snap = state.snapshot
    val bars = snap?.let { DevMath.bars(it) } ?: emptyList()
    val summary = snap?.let { DevMath.harmonicSummary(it) }
    val tm = rememberTextMeasurer()
    val zoneCannot = stringResource(R.string.dev_zone_cannot)
    val zoneGood = stringResource(R.string.dev_zone_good)
    val zoneBuzz = stringResource(R.string.dev_zone_buzz)
    val a11y = if (summary != null) stringResource(R.string.dev_a11y_harm, summary.f0Hz, summary.count, summary.loudestHz,
        dbText(summary.headroomDb)) else stringResource(R.string.dev_a11y_harm_none)
    val hl = state.highlight()
    val boundary = state.value(DevParams.BOUNDARY)
    val outLo = state.value(DevParams.OUT_LO)
    val outHi = state.value(DevParams.OUT_HI)
    val floor = state.speakerFloorHz
    Column(Modifier.fillMaxWidth()) {
        GraphHeader(stringResource(R.string.dev_graph_harm),
            if (summary != null) stringResource(R.string.dev_graph_harm_sub, summary.f0Hz, summary.count)
            else stringResource(R.string.dev_graph_harm_none))
        Spacer(Modifier.height(8.dp))
        Canvas(Modifier.fillMaxWidth().height(176.dp).clearAndSetSemantics { contentDescription = a11y }) {
            val axisY = size.height - 22.dp.toPx()
            val top = 20.dp.toPx()
            val plotH = axisY - top
            fun x(hz: Float) = DevMath.graphX(hz) * size.width
            // zones: speaker cannot play (grey), heard well (teal), buzz risk 220-400 Hz (orange)
            val xf = x(floor)
            val x220 = x(DevMath.BUZZ_LO_HZ)
            val x400 = x(DevMath.BUZZ_HI_HZ)
            drawRect(c.chevron.copy(alpha = 0.18f), Offset(0f, 0f), Size(xf, axisY))
            drawRect(c.fill.copy(alpha = 0.12f), Offset(xf, 0f), Size(max(0f, x220 - xf), axisY))
            drawRect(Orange.copy(alpha = 0.16f), Offset(x220, 0f), Size(x400 - x220, axisY))
            label(tm, zoneCannot, 4.dp.toPx(), 3.dp.toPx(), c.textSecondary, align = 0f)
            label(tm, zoneGood, xf + 4.dp.toPx(), 3.dp.toPx(), c.accentText, align = 0f)
            label(tm, zoneBuzz, x220 + 4.dp.toPx(), 3.dp.toPx(), c.warnText, align = 0f)
            // output band and generator edge while their sliders are touched
            if (hl == DevHighlight.OUT_BAND) {
                drawRect(c.accentText, Offset(x(outLo), top - 4.dp.toPx()), Size(x(outHi) - x(outLo), plotH + 4.dp.toPx()),
                    style = Stroke(width = 2.dp.toPx(), pathEffect = Dash))
            }
            if (hl == DevHighlight.BOUNDARY) {
                val xb = x(boundary)
                drawLine(c.accentText, Offset(xb, top - 4.dp.toPx()), Offset(xb, axisY), strokeWidth = 2.dp.toPx(), pathEffect = Dash)
            }
            drawLine(c.chevron.copy(alpha = 0.6f), Offset(0f, axisY), Offset(size.width, axisY), strokeWidth = 1.dp.toPx())
            val barW = 14.dp.toPx()
            val tallest = bars.maxOfOrNull { DevMath.barHeight(it.db) } ?: 0f
            // ghost fundamental: dashed outline (the note the speaker cannot play)
            if (snap != null && snap.f0Hz > 0f && bars.isNotEmpty()) {
                val h = max(0.35f, tallest) * plotH
                val gx = x(snap.f0Hz)
                drawRoundRect(if (hl == DevHighlight.FUNDAMENTAL) c.accentText else c.textSecondary,
                    Offset(gx - barW / 2f, axisY - h), Size(barW, h), CornerRadius(4.dp.toPx()),
                    style = Stroke(width = (if (hl == DevHighlight.FUNDAMENTAL) 2.5f else 1.5f).dp.toPx(), pathEffect = Dash))
            }
            for (b in bars) {
                val h = max(2.dp.toPx(), DevMath.barHeight(b.db) * plotH)
                val bx = x(b.hz)
                drawRoundRect(c.fill, Offset(bx - barW / 2f, axisY - h), Size(barW, h), CornerRadius(4.dp.toPx()))
                val marked = when (hl) {
                    DevHighlight.H2 -> b.k == 2
                    DevHighlight.H3 -> b.k == 3
                    DevHighlight.H4 -> b.k == 4
                    DevHighlight.H5_UP -> b.k >= 5
                    DevHighlight.UPPER -> b.hz > DevMath.BUZZ_LO_HZ
                    DevHighlight.ALL_BARS, DevHighlight.LAYER -> true
                    else -> false
                }
                if (marked) {
                    val p = 4.dp.toPx()
                    drawRoundRect(c.textPrimary, Offset(bx - barW / 2f - p, axisY - h - p), Size(barW + 2 * p, h + p),
                        CornerRadius(7.dp.toPx()), style = Stroke(width = 2.dp.toPx()))
                }
            }
            // axis labels: fundamental, speaker floor, 220, 400 Hz (skipped where they would overlap)
            val labels = ArrayList<Pair<Float, String>>()
            if (snap != null && snap.f0Hz > 0f && bars.isNotEmpty()) labels += x(snap.f0Hz) to "${snap.f0Hz.roundToInt()}"
            labels += xf to "${floor.roundToInt()}"
            labels += x220 to "220"
            labels += x400 to "400 Hz"
            var lastRight = -1e9f
            for ((lx, t) in labels.sortedBy { it.first }) {
                if (lx - 18.dp.toPx() < lastRight) continue
                label(tm, t, lx, axisY + 4.dp.toPx(), c.textSecondary)
                lastRight = lx + 18.dp.toPx()
            }
        }
        GraphNote(state, summary?.let { stringResource(R.string.dev_note_ok_harm, it.count, dbText(it.headroomDb)) })
    }
}

// ------------------------------------------------------------------------------------------------ time graph

@Composable
internal fun TimePage(state: DevUiState) {
    val c = LocalDevPalette.current
    val snap = state.snapshot
    val tm = rememberTextMeasurer()
    val span = snap?.let { DevMath.tailSpan(it.ringDry, it.ringLayer) }
    val tailMs = state.tailMs?.roundToInt()
    val a11y = if (tailMs != null) stringResource(R.string.dev_a11y_time, tailMs) else stringResource(R.string.dev_a11y_time_none)
    val tailLabel = stringResource(R.string.dev_time_tail)
    val now = stringResource(R.string.dev_time_axis_now)
    val secLabels = (1..2).map { stringResource(R.string.dev_time_axis_s, it) }
    val hl = state.highlight()
    Column(Modifier.fillMaxWidth()) {
        GraphHeader(stringResource(R.string.dev_graph_time), stringResource(R.string.dev_graph_time_sub))
        Spacer(Modifier.height(8.dp))
        Canvas(Modifier.fillMaxWidth().height(176.dp).clearAndSetSemantics { contentDescription = a11y }) {
            val axisY = size.height - 22.dp.toPx()
            val top = 8.dp.toPx()
            fun y(db: Float) = top + (axisY - top) * (1f - ((db.coerceIn(-60f, 0f) + 60f) / 60f))
            drawLine(c.chevron.copy(alpha = 0.6f), Offset(0f, axisY), Offset(size.width, axisY), strokeWidth = 1.dp.toPx())
            if (snap == null) return@Canvas
            val n = min(snap.ringDry.size, snap.ringLayer.size)
            if (n < 2) return@Canvas
            fun x(i: Int) = size.width * i / (n - 1).toFloat()
            // tail: from the dry note end to the layer's end, filled under the layer curve, dashed frame
            if (span != null && span.end > span.start) {
                val tail = Path()
                tail.moveTo(x(span.start), axisY)
                for (i in span.start..span.end) tail.lineTo(x(i), y(snap.ringLayer[i]))
                tail.lineTo(x(span.end), axisY)
                tail.close()
                drawPath(tail, Orange.copy(alpha = 0.30f))
                val warn = DevWarning.TAIL in state.active
                drawRect(if (warn) c.warnText else c.accentText, Offset(x(span.start), top),
                    Size(max(2f, x(span.end) - x(span.start)), axisY - top), style = Stroke(width = 1.5f.dp.toPx(), pathEffect = Dash))
                label(tm, tailLabel, (x(span.start) + x(span.end)) / 2f, top + 4.dp.toPx(), c.warnText, bold = true)
            }
            fun curve(ring: FloatArray): Path {
                val p = Path()
                p.moveTo(x(0), y(ring[0]))
                for (i in 1 until n) p.lineTo(x(i), y(ring[i]))
                return p
            }
            drawPath(curve(snap.ringDry), c.chevron, style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round))
            val thick = hl == DevHighlight.ATTACK || hl == DevHighlight.RELEASE || hl == DevHighlight.LAYER
            drawPath(curve(snap.ringLayer), c.fill, style = Stroke(width = (if (thick) 3.5f else 2.5f).dp.toPx(), cap = StrokeCap.Round))
            // seconds before now
            val totalS = (n - 1) * snap.binMs / 1000f
            for (s in 1..2) {
                if (s > totalS) break
                val lx = size.width * (1f - s / totalS)
                drawLine(c.chevron.copy(alpha = 0.6f), Offset(lx, axisY), Offset(lx, axisY + 3.dp.toPx()), strokeWidth = 1.dp.toPx())
                label(tm, secLabels[s - 1], lx, axisY + 4.dp.toPx(), c.textSecondary)
            }
            label(tm, now, size.width, axisY + 4.dp.toPx(), c.textSecondary, align = 1f)
        }
        GraphNote(state, tailMs?.let { stringResource(R.string.dev_note_ok_time, it) })
    }
}

// ------------------------------------------------------------------------------------------------ headroom gauge

private fun gaugeColor(f: Float): Color = Color(0xFF000000.toInt() or DevMath.gaugeColorAt(f))

private val GaugeStops: Array<Pair<Float, Color>> =
    DevMath.GAUGE_STOP_POS.indices.map { DevMath.GAUGE_STOP_POS[it] to Color(0xFF000000.toInt() or DevMath.GAUGE_STOP_RGB[it]) }
        .toTypedArray()

/** Level re the threshold (dB), or null while there is no (bass) sound. */
private fun relDb(s: DevSnapshot?): Float? = s?.takeIf { it.totalBandDb > -100f }?.let { -it.headroomDb }

@Composable
private fun statusText(st: DevMath.GaugeStatus): String = stringResource(when (st) {
    DevMath.GaugeStatus.ROOM -> R.string.dev_gauge_room
    DevMath.GaugeStatus.TIGHT -> R.string.dev_gauge_tight
    DevMath.GaugeStatus.DANGER -> R.string.dev_gauge_danger
})

@Composable
internal fun GaugePage(state: DevUiState) {
    val snap = state.snapshot
    val rel = relDb(snap)
    val thresholdLabel = if (state.thresholdMeasured) stringResource(R.string.dev_threshold_measured)
        else stringResource(R.string.dev_threshold_estimate, state.measuredOnName)
    val status = rel?.let { DevMath.gaugeStatus(-it) }
    val dryPct = snap?.let { DevMath.sharePct(it.dryBandDb, it.thresholdDb) } ?: 0
    val layPct = snap?.let { DevMath.sharePct(it.layerBandDb, it.thresholdDb) } ?: 0
    val a11y = if (rel != null && status != null)
        stringResource(R.string.dev_a11y_gauge, dbText(-rel), statusText(status), dryPct, layPct, thresholdLabel)
        else stringResource(R.string.dev_a11y_gauge_none)
    Column(Modifier.fillMaxWidth()) {
        GraphHeader(stringResource(R.string.dev_graph_gauge),
            stringResource(R.string.dev_graph_gauge_sub, state.volumePct.roundToInt(), thresholdLabel))
        Spacer(Modifier.height(8.dp))
        Box(Modifier.fillMaxWidth().clearAndSetSemantics { contentDescription = a11y }) {
            if (state.gaugeVu) VuMeter(rel, status) else GaugeA(rel, status, state.highlight() == DevHighlight.THRESHOLD)
        }
        val caption = when {
            snap == null -> null
            state.volumeLinkOn -> stringResource(R.string.dev_gauge_caption, dryPct, layPct, dbText(-snap.volumeLinkReductionDb))
            else -> stringResource(R.string.dev_gauge_caption_nolink, dryPct, layPct)
        }
        val c = LocalDevPalette.current
        if (caption != null) Text(caption, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
            modifier = Modifier.padding(top = 10.dp))
        GraphNote(state, rel?.let {
            if (status == DevMath.GaugeStatus.ROOM) stringResource(R.string.dev_note_ok_gauge_room, dbText(-it))
            else stringResource(R.string.dev_note_ok_gauge, dbText(-it))
        })
    }
}

/** Style A: big number + "dB 여유" + status pill, thin gradient track, level dot, protection-threshold notch. */
@Composable
private fun GaugeA(rel: Float?, status: DevMath.GaugeStatus?, emphasiseThreshold: Boolean) {
    val c = LocalDevPalette.current
    val tm = rememberTextMeasurer()
    val target = rel?.let { DevMath.gaugeFraction(it) } ?: 0f
    val f by animateFloatAsState(target, motion(tween(120, easing = LinearEasing)), label = "gauge")
    val thresholdText = stringResource(R.string.dev_gauge_threshold)
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            if (rel == null) {
                Text(stringResource(R.string.dev_gauge_waiting), color = c.textSecondary, fontSize = 15.sp, lineHeight = 21.sp,
                    modifier = Modifier.weight(1f).padding(vertical = 18.dp))
            } else {
                val headroom = -rel
                val shown = if (headroom > 24f) "24+" else dbText(headroom)
                Row(Modifier.weight(1f), verticalAlignment = Alignment.Bottom) {
                    Text(shown, color = c.textPrimary, fontSize = 56.sp, lineHeight = 62.sp, fontWeight = FontWeight.Bold,
                        letterSpacing = (-1).sp)
                    Text(stringResource(R.string.dev_gauge_unit), color = c.textSecondary, fontSize = 16.sp, lineHeight = 22.sp,
                        modifier = Modifier.padding(start = 8.dp, bottom = 10.dp))
                }
                if (status != null) StatusPill(status)
            }
        }
        Canvas(Modifier.fillMaxWidth().height(52.dp)) {
            val dotR = 11.dp.toPx()
            val trackH = 8.dp.toPx()
            val left = dotR
            val right = size.width - dotR
            val w = right - left
            val cy = dotR + 2.dp.toPx()
            val brush = Brush.horizontalGradient(*GaugeStops, startX = left, endX = right)
            // track: the gradient at 30 %; fill: the same gradient (same span) at 100 %, clipped at the level
            drawRoundRect(brush, Offset(left, cy - trackH / 2f), Size(w, trackH), CornerRadius(trackH / 2f), alpha = 0.3f)
            val lx = left + w * f
            if (rel != null) clipRect(left = 0f, top = 0f, right = lx, bottom = size.height) {
                drawRoundRect(brush, Offset(left, cy - trackH / 2f), Size(w, trackH), CornerRadius(trackH / 2f))
            }
            // protection threshold: dark notch + label
            val tx = left + w * DevMath.thresholdFraction
            drawLine(c.textPrimary, Offset(tx, cy - 11.dp.toPx()), Offset(tx, cy + 11.dp.toPx()),
                strokeWidth = (if (emphasiseThreshold) 3.5f else 2.5f).dp.toPx(), cap = StrokeCap.Round)
            label(tm, thresholdText, tx, cy + 14.dp.toPx(), c.textPrimary, size = 12f, bold = true)
            if (rel != null) {
                // level dot: 22 dp white with a 5 dp ring in the track colour at the level
                drawCircle(Color.White, radius = dotR, center = Offset(lx, cy))
                drawCircle(gaugeColor(f), radius = dotR - 2.5f.dp.toPx(), center = Offset(lx, cy), style = Stroke(width = 5.dp.toPx()))
            }
        }
    }
}

@Composable
private fun StatusPill(status: DevMath.GaugeStatus) {
    val c = LocalDevPalette.current
    val (bg, fg) = when (status) {
        DevMath.GaugeStatus.ROOM -> c.chipSelectedBg to c.accentText
        DevMath.GaugeStatus.TIGHT -> c.warnBg to c.warnText
        DevMath.GaugeStatus.DANGER -> c.dangerBg to c.danger
    }
    Box(Modifier.background(bg, CircleShape).padding(horizontal = 12.dp, vertical = 5.dp)) {
        Text(statusText(status), color = fg, fontSize = 14.sp, lineHeight = 20.sp, fontWeight = FontWeight.Bold)
    }
}

private val VuBezel = Color(0xFF2A2622)
private val VuFaceTop = Color(0xFFFBF1D6)
private val VuFaceBottom = Color(0xFFEBD9A8)
private val VuInk = Color(0xFF2A2622)
private val VuRed = Color(0xFFB3261E)

/**
 * Optional style: an analog VU-style needle meter. Ivory face in a dark bezel, black scale -12 .. +2 dB re the
 * protection threshold (0 = threshold), red arc 0..+2, thin needle over +-56 degrees with about 300 ms smoothing, a
 * small status lamp with its word. Same colours in both themes (it is a physical object).
 */
@Composable
private fun VuMeter(rel: Float?, status: DevMath.GaugeStatus?) {
    val tm = rememberTextMeasurer()
    val target = DevMath.vuFraction(rel ?: (DevMath.VU_MIN_DB - 6f))
    val f by animateFloatAsState(target, motion(tween(300, easing = LinearOutSlowInEasing)), label = "needle")
    val caption = stringResource(R.string.dev_vu_caption)
    val word = status?.let { statusText(it) } ?: ""
    Box(Modifier.fillMaxWidth().background(VuBezel, RoundedCornerShape(20.dp)).padding(12.dp)) {
        Canvas(Modifier.fillMaxWidth().height(170.dp)) {
            val face = Brush.verticalGradient(listOf(VuFaceTop, VuFaceBottom))
            drawRoundRect(face, Offset.Zero, size, CornerRadius(14.dp.toPx()))
            val r = min(size.height * 0.92f, size.width * 0.42f)
            val pivot = Offset(size.width / 2f, size.height + r * 0.18f)
            val maxDeg = 56f
            fun angle(fr: Float) = Math.toRadians((-maxDeg + 2 * maxDeg * fr).toDouble())
            fun at(fr: Float, radius: Float): Offset {
                val a = angle(fr)
                return Offset(pivot.x + radius * sin(a).toFloat(), pivot.y - radius * cos(a).toFloat())
            }
            // red arc 0..+2
            val f0 = DevMath.vuFraction(0f)
            val f2 = DevMath.vuFraction(DevMath.VU_MAX_DB)
            val arcR = r - 3.dp.toPx()
            drawArc(VuRed, startAngle = (-90f - maxDeg + 2 * maxDeg * f0), sweepAngle = 2 * maxDeg * (f2 - f0), useCenter = false,
                topLeft = Offset(pivot.x - arcR, pivot.y - arcR), size = Size(2 * arcR, 2 * arcR),
                style = Stroke(width = 5.dp.toPx()))
            // black arc and ticks
            val f12 = DevMath.vuFraction(DevMath.VU_MIN_DB)
            drawArc(VuInk, startAngle = (-90f - maxDeg + 2 * maxDeg * f12), sweepAngle = 2 * maxDeg * (f0 - f12), useCenter = false,
                topLeft = Offset(pivot.x - r, pivot.y - r), size = Size(2 * r, 2 * r), style = Stroke(width = 1.5f.dp.toPx()))
            var db = DevMath.VU_MIN_DB
            while (db <= DevMath.VU_MAX_DB + 0.01f) {
                val fr = DevMath.vuFraction(db)
                val major = db.roundToInt() in listOf(-12, -9, -6, -3, 0, 2)
                val len = (if (major) 10f else 5f).dp.toPx()
                drawLine(if (db > 0.01f || db.roundToInt() == 0) VuRed else VuInk, at(fr, r), at(fr, r + len),
                    strokeWidth = (if (major) 2f else 1f).dp.toPx())
                if (major) {
                    val p = at(fr, r + len + 14.dp.toPx())
                    val t = if (db > 0.01f) "+${db.roundToInt()}" else if (db < -0.01f) "−${(-db).roundToInt()}" else "0"
                    label(tm, t, p.x, p.y - 9.dp.toPx(), if (db >= -0.01f) VuRed else VuInk, size = 13f, bold = true)
                }
                db += 1f
            }
            label(tm, caption, size.width / 2f, pivot.y - r * 0.55f, VuInk, size = 13f, bold = true)
            // needle (clipped to the face)
            clipRect(0f, 0f, size.width, size.height) {
                drawLine(VuInk, pivot, at(f, r + 8.dp.toPx()), strokeWidth = 1.6f.dp.toPx(), cap = StrokeCap.Round)
            }
            // status lamp + word
            if (status != null) {
                val lamp = when (status) {
                    DevMath.GaugeStatus.ROOM -> gaugeColor(0f)
                    DevMath.GaugeStatus.TIGHT -> gaugeColor(0.72f)
                    DevMath.GaugeStatus.DANGER -> gaugeColor(1f)
                }
                val lx = size.width - 16.dp.toPx()
                val ly = size.height - 16.dp.toPx()
                drawCircle(lamp, radius = 5.dp.toPx(), center = Offset(lx, ly))
                val m = tm.measure(word, TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Bold))
                drawText(m, color = VuInk, topLeft = Offset(lx - 10.dp.toPx() - m.size.width, ly - m.size.height / 2f))
            }
        }
    }
}

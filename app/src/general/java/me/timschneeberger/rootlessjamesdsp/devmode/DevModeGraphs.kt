package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
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
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.material3.TextButton
import androidx.compose.material3.Checkbox
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.input.pointer.pointerInput
import me.timschneeberger.rootlessjamesdsp.pvb.PvbDevMeter
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
import me.timschneeberger.rootlessjamesdsp.ui.RnMotion
import me.timschneeberger.rootlessjamesdsp.ui.rn

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
    val notes = snap?.let { DevMath.trackBars(it).size } ?: 0
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
            if (summary != null && notes > 1) stringResource(R.string.dev_graph_harm_sub_more, summary.f0Hz, summary.count, notes - 1)
            else if (summary != null) stringResource(R.string.dev_graph_harm_sub, summary.f0Hz, summary.count)
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
            // thin bars so two or three bass notes held together fit side by side; quieter notes drawn lighter, first
            val barW = 6.dp.toPx()
            val tracks = snap?.let { DevMath.trackBars(it) } ?: emptyList()
            val tallest = tracks.flatMap { it.second }.maxOfOrNull { DevMath.barHeight(it.db) } ?: 0f
            for ((i, t) in tracks.withIndex().reversed()) {
                val (f0, tb) = t
                val main = i == 0
                // ghost fundamental: dashed outline (the note the speaker cannot play)
                val h = max(0.35f, tallest) * (if (main) 1f else 0.8f) * plotH
                val gx = x(f0)
                val ghostHl = main && hl == DevHighlight.FUNDAMENTAL
                drawRoundRect((if (ghostHl) c.accentText else c.textSecondary).copy(alpha = if (main) 1f else 0.55f),
                    Offset(gx - barW / 2f, axisY - h), Size(barW, h), CornerRadius(3.dp.toPx()),
                    style = Stroke(width = (if (ghostHl) 2f else 1.2f).dp.toPx(), pathEffect = Dash))
                for (b in tb) {
                    val bh = max(2.dp.toPx(), DevMath.barHeight(b.db) * plotH)
                    val bx = x(b.hz)
                    drawRoundRect(if (main) c.fill else c.fill.copy(alpha = 0.45f), Offset(bx - barW / 2f, axisY - bh),
                        Size(barW, bh), CornerRadius(3.dp.toPx()))
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
                        val p = 3.dp.toPx()
                        drawRoundRect(c.textPrimary, Offset(bx - barW / 2f - p, axisY - bh - p), Size(barW + 2 * p, bh + p),
                            CornerRadius(5.dp.toPx()), style = Stroke(width = 1.5f.dp.toPx()))
                    }
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
    var frozen by remember { mutableStateOf<DevSnapshot?>(null) }
    var fraction by remember { mutableStateOf(1f) }
    var showRequest by remember { mutableStateOf(false) }
    val latestSnapshot by rememberUpdatedState(state.snapshot)
    val snap = frozen ?: state.snapshot
    val tm = rememberTextMeasurer()
    val green = Color(0xFF70B77E)
    val n = snap?.ringLayer?.size ?: 0
    val index = (fraction * (n - 1).coerceAtLeast(0)).roundToInt()
    fun stage(i: Int, field: Int): Float = snap?.stages?.getOrNull(i * PvbDevMeter.STAGE_FIELDS + field) ?: -120f
    val available = snap?.stages?.size == PvbDevMeter.STAGE_FIELDS * n && n > 0
    val span = snap?.let { DevMath.tailSpan(it.ringDry, it.ringLayer) }
    val ageMs = if (snap != null) (n - 1 - index) * snap.binMs else 0f
    Column(Modifier.fillMaxWidth()) {
        GraphHeader("배음이 줄어드는 단계", if (frozen == null) "실시간 · 누르거나 길게 눌러 정지" else "화면 정지 · 음악은 계속 재생")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = showRequest, onCheckedChange = { showRequest = it })
            Text("제한 전 요청 배음", color = c.textSecondary, fontSize = 12.sp)
            if (frozen != null) TextButton(onClick = { frozen = null; fraction = 1f }) { Text("실시간") }
            else TextButton(onClick = { frozen = latestSnapshot; fraction = 1f }) { Text("화면 정지") }
        }
        Text("회색: 공통 입력 저역   연초록: 합성기 입력 저역", color = c.textSecondary, fontSize = 12.sp)
        Text("틸 실선: 실제 배음 · 점선: 요청 배음 / 최종 리미터 전", color = c.textSecondary, fontSize = 12.sp)
        Canvas(Modifier.fillMaxWidth().height(220.dp)
            .pointerInput(frozen) {
                detectTapGestures(onTap = { p -> if (frozen == null) frozen = latestSnapshot; fraction = (p.x / size.width).coerceIn(0f, 1f) },
                    onLongPress = { p -> if (frozen == null) frozen = latestSnapshot; fraction = (p.x / size.width).coerceIn(0f, 1f) })
            }
            .pointerInput(frozen) { detectDragGestures { change, _ ->
                if (frozen != null) { change.consume(); fraction = (change.position.x / size.width).coerceIn(0f, 1f) }
            } }
            .clearAndSetSemantics { contentDescription = "공통 입력, 합성기 입력, 제한 전후 배음의 고정 dBFS 시간 그래프. 화면 정지 후 수치를 읽을 수 있습니다." }) {
            val left = 34.dp.toPx(); val right = size.width - 4.dp.toPx()
            val top = 8.dp.toPx(); val bottom = size.height - 46.dp.toPx()
            fun x(i: Int) = left + (right - left) * i / (n - 1).coerceAtLeast(1)
            fun y(v: Float) = bottom - (bottom - top) * ((v.coerceIn(-100f, 0f) + 100f) / 100f)
            for (db in listOf(0, -20, -40, -60, -80, -100)) {
                drawLine(c.chevron.copy(alpha = .25f), Offset(left, y(db.toFloat())), Offset(right, y(db.toFloat())), 1f)
                label(tm, "$db", left - 5.dp.toPx(), y(db.toFloat()) - 6.dp.toPx(), c.textSecondary, align = 1f)
            }
            if (snap == null || n < 2 || !available) return@Canvas
            fun curve(field: Int, actual: Boolean = false): Path {
                val p = Path()
                for (i in 0 until n) { val value = if (actual) snap.ringLayer[i] else stage(i, field)
                    if (i == 0) p.moveTo(x(i), y(value)) else p.lineTo(x(i), y(value)) }
                return p
            }
            drawPath(curve(0), c.chevron, style = Stroke(2.dp.toPx()))
            drawPath(curve(1), green, style = Stroke(2.dp.toPx()))
            if (showRequest) drawPath(curve(2), c.fill.copy(alpha = .55f), style = Stroke(1.5f.dp.toPx(), pathEffect = Dash))
            drawPath(curve(0, true), c.fill, style = Stroke(2.5f.dp.toPx()))
            // Event lane: actual no-track observations / fit guard / dedicated layer reduction.
            val lane = bottom + 6.dp.toPx()
            for (i in 1 until n) {
                val reason = stage(i, 4).toInt().coerceAtLeast(0)
                if (stage(i, 6) == -1f && stage(i - 1, 6) > 0f) label(tm, "×", x(i), lane, c.textSecondary)
                if (stage(i, 6) > 0f && stage(i - 1, 6) == -1f) label(tm, "○", x(i), lane, green)
                if ((reason and 8) != 0) drawLine(c.textSecondary, Offset(x(i - 1), lane + 7.dp.toPx()), Offset(x(i), lane + 7.dp.toPx()), 3.dp.toPx(), pathEffect = Dash)
                if (stage(i, 8) > .5f) drawLine(Orange, Offset(x(i - 1), lane + 13.dp.toPx()), Offset(x(i), lane + 13.dp.toPx()), 3.dp.toPx())
            }
            if (span != null && span.end > span.start) {
                val yy = bottom + 24.dp.toPx()
                drawLine(Orange, Offset(x(span.start), yy), Offset(x(span.end), yy), 2.dp.toPx())
                for (i in listOf(span.start, span.end)) drawLine(Orange, Offset(x(i), yy - 5.dp.toPx()), Offset(x(i), yy + 2.dp.toPx()), 2.dp.toPx())
            }
            if (frozen != null) drawLine(c.textPrimary, Offset(x(index), top), Offset(x(index), bottom + 28.dp.toPx()), 1.5f.dp.toPx())
            label(tm, "${((n - 1) * snap.binMs / 1000f).let { "%.2f".format(it) }}초 전", left, size.height - 15.dp.toPx(), c.textSecondary, align = 0f)
            label(tm, "현재", right, size.height - 15.dp.toPx(), c.textSecondary, align = 1f)
        }
        Text("× 유효 트랙 없음 관측 → ○ 재관측 · 빗금: 맞춤 제한 사유 · 주황: 배음층 제한", color = c.textSecondary, fontSize = 11.sp)
        if (frozen != null && available) {
            val reason = stage(index, 4).toInt().coerceAtLeast(0)
            val names = listOf(1 to "절대 크기", 2 to "상대 크기", 4 to "피크 없음", 8 to "모델 맞춤", 16 to "격자", 32 to "트랙 누락", 64 to "용량", 128 to "배음 가중치", 256 to "비유한 값", 512 to "종속 배음")
                .filter { (bit, _) -> (reason and bit) != 0 }.joinToString(" · ") { it.second }
            fun db(v: Float) = if (v <= -100f) "−100 이하" else "%.1f".format(v)
            Text("선택: %.0f ms 전 · 원본 시점에 정렬한 %.0f ms bin".format(ageMs, snap!!.binMs), color = c.textPrimary, fontSize = 12.sp)
            Text("공통 입력 ${db(stage(index, 0))} / 합성기 입력 ${db(stage(index, 1))} dBFS\n요청 ${db(stage(index, 2))} / 실제 ${db(snap.ringLayer[index])} dBFS", color = c.textPrimary, fontSize = 13.sp)
            val trackState = when (stage(index, 6).toInt()) { 1 -> "새 트랙"; 2 -> "트랙 관측 유지"; 3 -> "트랙 유지 추정"; -1 -> "유효 트랙 없음"; else -> "관측 대기" }
            Text("추적 상태: $trackState", color = c.textPrimary, fontSize = 12.sp)
            val f0 = stage(index, 3)
            Text(if (f0 > 0f) "f₀ %.1f Hz · 맞춤 잔차 %.1f dB".format(f0, stage(index, 5)) else "f₀: 해당 합성 프레임의 유효 트랙 없음/관측 대기", color = c.textPrimary, fontSize = 13.sp)
            Text("배음층 제한 %.1f dB / 최종 리미터 최대 감쇄 %.1f dB".format(stage(index, 8).coerceAtLeast(0f), stage(index, 7).coerceAtLeast(0f)), color = c.textPrimary, fontSize = 13.sp)
            Text("관측 사유: ${names.ifEmpty { "사유 비트 없음" }} · 신뢰도 확률이 아님", color = c.textSecondary, fontSize = 12.sp)
            if (span != null) Text("꼬리 판정 기준: 합성기 입력 종료 ${(span.start * snap.binMs).roundToInt()} ms → 실제 배음 종료 ${(span.end * snap.binMs).roundToInt()} ms (화면 왼쪽 기준)${if (span.ongoing) " · 아직 진행 중" else ""}", color = c.warnText, fontSize = 12.sp)
        } else if (frozen == null) GraphNote(state, null)
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
    val f by animateFloatAsState(target, rn(RnMotion.clock(120)), label = "gauge")
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
 * protection threshold (0 = threshold), red arc 0..+2, thin needle over +-56 degrees with a damped spring (RnMotion.Apple.needle), a
 * small status lamp with its word. Same colours in both themes (it is a physical object).
 */
@Composable
private fun VuMeter(rel: Float?, status: DevMath.GaugeStatus?) {
    val tm = rememberTextMeasurer()
    val target = DevMath.vuFraction(rel ?: (DevMath.VU_MIN_DB - 6f))
    val f by animateFloatAsState(target, rn(RnMotion.Apple.needle()), label = "needle")
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

package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.SpeakerProbe
import kotlin.math.ln
import kotlin.math.roundToInt

/** What "스피커 확인 (마이크)" shows (reference only; nothing is applied). */
@Immutable
data class ProbeView(
    val running: Boolean,
    val noMic: Boolean = false,
    val nowHz: Double? = null,
    val nowRelDb: Double? = null,
    val nowRatioDb: Double? = null,
    val bins: List<SpeakerProbe.Bin> = emptyList(),
    val floorHz: Double? = null,
    val clipped: Boolean = false,
) {
    companion object {
        fun of(p: SpeakerProbe, running: Boolean) = ProbeView(
            running = running,
            nowHz = p.nowHz.takeIf { !it.isNaN() },
            nowRelDb = p.nowRelDb.takeIf { !it.isNaN() },
            nowRatioDb = p.nowRatioDb.takeIf { !it.isNaN() },
            bins = p.bins(),
            floorHz = p.floorHz(),
            clipped = p.clipped,
        )
    }
}

@Composable
private fun verdictText(v: SpeakerProbe.Verdict): String = stringResource(when (v) {
    SpeakerProbe.Verdict.PLAYS -> R.string.dev_probe_plays
    SpeakerProbe.Verdict.WEAK -> R.string.dev_probe_weak
    SpeakerProbe.Verdict.BUZZ -> R.string.dev_probe_buzz
})

/**
 * The microphone's view of the probe sweep, under the test sounds: a band card (radius 14, as the evidence sheet's
 * cards) with the live line, one bar per 1/6 octave (40-500 Hz; height = fundamental re the loudest bar, teal = plays,
 * grey = weak, orange = buzz only; dashed line at -10 dB), the reference floor and the caveat.
 */
@Composable
internal fun ProbePanel(v: ProbeView) {
    val c = LocalDevPalette.current
    Column(
        Modifier.padding(top = 8.dp).fillMaxWidth().background(c.band, RoundedCornerShape(14.dp)).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(stringResource(R.string.dev_probe_title), color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp,
            fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
        if (v.noMic) {
            InlineNote(stringResource(R.string.dev_probe_nomic), warning = true)
            return@Column
        }
        val hz = v.nowHz
        val rel = v.nowRelDb
        val ratio = v.nowRatioDb
        if (v.running && hz != null && rel != null && ratio != null) {
            Text(stringResource(R.string.dev_probe_now, hz.roundToInt(), dbText(rel.toFloat()), dbText(ratio.toFloat()),
                verdictText(SpeakerProbe.verdict(rel, ratio))), color = c.textPrimary, fontSize = 13.sp, lineHeight = 18.sp)
        } else if (v.running) {
            Text(stringResource(R.string.dev_probe_wait), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        }
        val floorText = v.floorHz?.let { stringResource(R.string.dev_probe_floor, SpeakerProbe.roundHz(it)) }
            ?: stringResource(R.string.dev_probe_floor_none)
        ProbeBars(v, floorText)
        Text(floorText, color = c.accentText, fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold)
        if (v.clipped) InlineNote(stringResource(R.string.dev_probe_clipped), warning = true)
        Text(stringResource(R.string.dev_probe_note), color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp)
    }
}

@Composable
private fun ProbeBars(v: ProbeView, description: String) {
    val c = LocalDevPalette.current
    val lo = SpeakerProbe.LO_HZ
    val hi = SpeakerProbe.HI_HZ
    val labels = listOf(50, 100, 200, 400)
    val tm = androidx.compose.ui.text.rememberTextMeasurer()
    val labelStyle = androidx.compose.ui.text.TextStyle(color = c.textSecondary, fontSize = 11.sp)
    Canvas(Modifier.fillMaxWidth().height(120.dp).semantics { contentDescription = description }) {
        val axisY = size.height - 16.dp.toPx()
        fun x(f: Double) = (ln(f / lo) / ln(hi / lo)).toFloat() * size.width
        fun y(db: Double) = axisY * (-db / 30.0).coerceIn(0.0, 1.0).toFloat()
        val w = size.width / 26f
        for (b in v.bins) {
            val col = when (b.verdict) {
                SpeakerProbe.Verdict.PLAYS -> c.fill
                SpeakerProbe.Verdict.WEAK -> c.chevron
                SpeakerProbe.Verdict.BUZZ -> ExperimentalOrange
            }
            val top = y(b.relDb)
            drawRect(col, Offset(x(b.hz) - w / 2, top), Size(w * 0.8f, (axisY - top).coerceAtLeast(2.dp.toPx())))
        }
        // -10 dB: below it a bin counts as weak
        val y10 = y(SpeakerProbe.WEAK_DB)
        drawLine(c.textSecondary, Offset(0f, y10), Offset(size.width, y10), 1.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx())))
        v.floorHz?.let { f -> drawLine(c.accentText, Offset(x(f) - w / 2, 0f), Offset(x(f) - w / 2, axisY), 2.dp.toPx()) }
        v.nowHz?.takeIf { v.running }?.let { f -> drawCircle(c.accentText, 3.dp.toPx(), Offset(x(f), axisY + 4.dp.toPx())) }
        drawLine(c.chevron.copy(alpha = 0.6f), Offset(0f, axisY), Offset(size.width, axisY), 1.dp.toPx())
        for (l in labels) {
            val r = tm.measure("$l", labelStyle)
            drawText(r, topLeft = Offset((x(l.toDouble()) - r.size.width / 2f).coerceIn(0f, size.width - r.size.width), axisY + 3.dp.toPx()))
        }
    }
}

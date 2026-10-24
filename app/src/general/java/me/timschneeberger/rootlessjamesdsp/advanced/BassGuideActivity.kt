package me.timschneeberger.rootlessjamesdsp.advanced

import android.content.Context
import android.content.Intent
import android.os.Bundle
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.ui.RnBadge
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnEndSpace
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import kotlin.math.ln
import kotlin.math.max

/**
 * "저음, 왕창 올려도 될까요?": why a big low-bass EQ boost does not pay on a phone speaker, with the speaker response of
 * Android phones drawn. Opened from the advanced screen (Rootnote's tone section and the JamesDSP equalizer).
 *
 * The curves: our own Galaxy S26 Ultra measurement (UMIK-1), and the 10th-90th percentile band and median of about 90
 * Android phones measured by one reviewer, moved into our frame by difference transfer (docs/SPEAKER_ESTIMATES.md).
 * Aggregate values only: no per-model curve is kept in the app or the repository (data policy).
 */
class BassGuideActivity : RnActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setRnContent {
            RnPage(stringResource(R.string.guide_title), onBack = this@BassGuideActivity::finish) { BassGuide() }
        }
    }

    companion object {
        fun intent(context: Context): Intent = Intent(context, BassGuideActivity::class.java)
    }
}

/** Third-octave bands, dB re the mean of 630-2000 Hz ("mids"). */
internal object PhoneResponse {
    val HZ = floatArrayOf(125f, 160f, 200f, 250f, 315f, 400f, 500f, 630f, 800f, 1000f, 1250f, 1600f, 2000f, 2500f,
        3150f, 4000f, 5000f, 6300f, 8000f, 10000f, 12500f)
    /** Galaxy S26 Ultra, our UMIK-1 measurement (30 cm, volume 60/150, Dolby Atmos off). */
    val S26U = floatArrayOf(-21.7f, -15.5f, -10.4f, -6.4f, -7.5f, -7.1f, -6.2f, -4.3f, -0.5f, -1.2f, 1.5f, 0.8f, 3.8f,
        9.2f, 9.6f, 9.4f, 14.2f, 11.8f, 6.4f, -3.1f, -13.5f)
    /** Android phones (estimated, aggregate): 10th percentile, median, 90th percentile per band. */
    val P10 = floatArrayOf(-30.9f, -21.3f, -16.0f, -9.6f, -8.4f, -7.5f, -8.6f, -9.2f, -3.9f, -0.7f, -0.5f, -2.7f, -0.1f,
        4.0f, 5.2f, 3.9f, 8.1f, 6.9f, 2.0f, -11.6f, -15.3f)
    val P50 = floatArrayOf(-23.1f, -14.5f, -10.7f, -5.5f, -5.0f, -4.6f, -5.9f, -5.5f, -1.8f, 1.7f, 2.6f, 0.0f, 3.1f,
        9.2f, 12.6f, 11.2f, 14.1f, 12.4f, 6.2f, -5.0f, -8.9f)
    val P90 = floatArrayOf(-16.5f, -9.4f, -5.3f, -1.1f, 0.3f, -0.6f, -1.9f, -1.5f, 1.2f, 3.7f, 4.6f, 2.9f, 5.7f, 12.7f,
        16.3f, 15.2f, 19.0f, 17.8f, 11.2f, 0.9f, -1.8f)
    /** Median phone: 10 dB under the mids here. */
    const val MEDIAN_MINUS10_HZ = 206f

    const val LO_HZ = 25f
    const val HI_HZ = 16000f
    const val TOP_DB = 20f
    const val BOTTOM_DB = -35f

    fun x(hz: Float): Float = (ln(hz / LO_HZ) / ln(HI_HZ / LO_HZ))
    fun y(db: Float): Float = (TOP_DB - db.coerceIn(BOTTOM_DB, TOP_DB)) / (TOP_DB - BOTTOM_DB)
}

@Composable
private fun BassGuide() {
    val c = LocalRn.current
    Text(stringResource(R.string.guide_answer_title), color = c.textPrimary, fontSize = 17.sp, lineHeight = 24.sp,
        fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp).semantics { heading() })
    Text(stringResource(R.string.guide_answer), color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))

    ResponseCard()

    RnBand()
    RnSectionTitle(stringResource(R.string.guide_why_title))
    Point(stringResource(R.string.guide_why_1), listOf(R.string.guide_tag_research, R.string.guide_tag_measured))
    Point(stringResource(R.string.guide_why_2), listOf(R.string.guide_tag_research, R.string.guide_tag_maker))
    Point(stringResource(R.string.guide_why_3), listOf(R.string.guide_tag_maker, R.string.guide_tag_measured))

    RnBand()
    RnSectionTitle(stringResource(R.string.guide_ours_title))
    Point(stringResource(R.string.guide_ours_1), listOf(R.string.guide_tag_measured))
    Point(stringResource(R.string.guide_ours_2), listOf(R.string.guide_tag_blind))
    Point(stringResource(R.string.guide_ours_3), listOf(R.string.guide_tag_blind))
    Point(stringResource(R.string.guide_ours_4), listOf(R.string.guide_tag_blind))
    Point(stringResource(R.string.guide_ours_5), listOf(R.string.guide_tag_measured))

    RnBand()
    RnSectionTitle(stringResource(R.string.guide_do_title))
    Point(stringResource(R.string.guide_do_1), emptyList())
    Point(stringResource(R.string.guide_do_2), emptyList())
    Point(stringResource(R.string.guide_do_3), emptyList())
    Point(stringResource(R.string.guide_do_4), emptyList())

    RnBand()
    RnSectionTitle(stringResource(R.string.guide_web_title))
    RnParagraph(stringResource(R.string.guide_web))
    RnParagraph(stringResource(R.string.guide_sources))
    RnEndSpace()
}

/** One point: a dot, the text, and its evidence tags (docs/DESIGN.md 5 근거 표시). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Point(text: String, tags: List<Int>) {
    val c = LocalRn.current
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp)) {
        Box(Modifier.padding(top = 8.dp, end = 10.dp).size(5.dp).background(c.textSecondary, RoundedCornerShape(3.dp)))
        Column(Modifier.weight(1f)) {
            Text(text, color = c.textPrimary, fontSize = 14.sp, lineHeight = 21.sp)
            if (tags.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    for (t in tags) RnBadge(stringResource(t), c.chipBg, c.textSecondary)
                }
            }
        }
    }
}

/** The picture card (rn_band, radius 20, 16 inside): Android phone speakers' response, log frequency axis. */
@Composable
private fun ResponseCard() {
    val c = LocalRn.current
    val tm = rememberTextMeasurer()
    val a11y = stringResource(R.string.guide_graph_a11y)
    val cannot = stringResource(R.string.guide_zone_cannot)
    val plays = stringResource(R.string.guide_zone_plays)
    val noData = stringResource(R.string.guide_zone_nodata)
    val mids = stringResource(R.string.guide_mids)
    val grey = c.chevron
    Column(
        Modifier.padding(horizontal = 16.dp, vertical = 8.dp).fillMaxWidth()
            .background(c.band, RoundedCornerShape(20.dp)).padding(16.dp),
    ) {
        Text(stringResource(R.string.guide_graph_title), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
            fontWeight = FontWeight.Bold)
        Text(stringResource(R.string.guide_graph_sub), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        Spacer(Modifier.height(10.dp))
        Canvas(Modifier.fillMaxWidth().height(220.dp).clearAndSetSemantics { contentDescription = a11y }) {
            val left = 30.dp.toPx()
            val top = 18.dp.toPx()
            val axisY = size.height - 20.dp.toPx()
            val w = size.width - left
            val h = axisY - top
            fun px(hz: Float) = left + PhoneResponse.x(hz) * w
            fun py(db: Float) = top + PhoneResponse.y(db) * h
            val x125 = px(PhoneResponse.HZ.first())
            val x10 = px(PhoneResponse.MEDIAN_MINUS10_HZ)
            // zones: no data below 125 Hz, "hardly plays" up to the median phone's -10 dB point, "plays" above
            drawRect(grey.copy(alpha = 0.35f), Offset(left, top), Size(x125 - left, h))
            drawRect(grey.copy(alpha = 0.18f), Offset(x125, top), Size(x10 - x125, h))
            drawRect(c.fill.copy(alpha = 0.12f), Offset(x10, top), Size(left + w - x10, h))
            label(tm, cannot, left + 4.dp.toPx(), top + 3.dp.toPx(), c.textSecondary, align = 0f)
            label(tm, noData, left + 4.dp.toPx(), py(-30f) - 16.dp.toPx(), c.textSecondary, align = 0f)
            label(tm, plays, x10 + 4.dp.toPx(), top + 3.dp.toPx(), c.accentText, align = 0f)
            // dB grid
            for (db in intArrayOf(10, 0, -10, -20, -30)) {
                val y = py(db.toFloat())
                drawLine(grey.copy(alpha = if (db == 0) 0.7f else 0.3f), Offset(left, y), Offset(left + w, y),
                    strokeWidth = (if (db == 0) 1.2f else 1f).dp.toPx())
                label(tm, if (db > 0) "+$db" else "$db", left - 4.dp.toPx(), y - 7.dp.toPx(), c.textSecondary, align = 1f, clamp = false)
            }
            label(tm, mids, left + w, py(0f) - 16.dp.toPx(), c.textSecondary, align = 1f)
            // the 10th-90th percentile band of the phones, the median, our S26 Ultra
            val band = Path().apply {
                PhoneResponse.HZ.forEachIndexed { i, f -> if (i == 0) moveTo(px(f), py(PhoneResponse.P90[i])) else lineTo(px(f), py(PhoneResponse.P90[i])) }
                for (i in PhoneResponse.HZ.indices.reversed()) lineTo(px(PhoneResponse.HZ[i]), py(PhoneResponse.P10[i]))
                close()
            }
            drawPath(band, c.fill.copy(alpha = 0.22f))
            curve(PhoneResponse.P50, ::px, ::py, c.fill, 2.5f.dp.toPx(), null)
            curve(PhoneResponse.S26U, ::px, ::py, c.textPrimary, 1.6f.dp.toPx(), PathEffect.dashPathEffect(floatArrayOf(10f, 7f), 0f))
            // the bands of a common phone EQ (31-16k), as ticks on the axis
            drawLine(grey.copy(alpha = 0.6f), Offset(left, axisY), Offset(left + w, axisY), strokeWidth = 1.dp.toPx())
            for ((hz, t) in listOf(31f to "31", 62f to "62", 125f to "125", 250f to "250", 500f to "500", 1000f to "1k",
                2000f to "2k", 4000f to "4k", 8000f to "8k")) {
                val x = px(hz)
                drawLine(grey, Offset(x, axisY), Offset(x, axisY + 4.dp.toPx()), strokeWidth = 1.dp.toPx())
                label(tm, t, x, axisY + 5.dp.toPx(), c.textSecondary)
            }
            label(tm, "Hz", left + w, axisY + 5.dp.toPx(), c.textSecondary, align = 1f)
        }
        Spacer(Modifier.height(10.dp))
        Legend(c.fill, false, stringResource(R.string.guide_legend_median))
        Legend(c.fill.copy(alpha = 0.22f), true, stringResource(R.string.guide_legend_band))
        Legend(c.textPrimary, false, stringResource(R.string.guide_legend_s26u), dashed = true)
        Spacer(Modifier.height(6.dp))
        Text(stringResource(R.string.guide_graph_note), color = c.textSecondary, fontSize = 12.sp, lineHeight = 17.sp)
    }
}

@Composable
private fun Legend(color: Color, area: Boolean, text: String, dashed: Boolean = false) {
    val c = LocalRn.current
    Row(Modifier.padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Canvas(Modifier.width(22.dp).height(12.dp)) {
            if (area) drawRect(color, Offset(0f, 0f), size)
            else drawLine(color, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), strokeWidth = 2.dp.toPx(),
                pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(8f, 5f), 0f) else null)
        }
        Spacer(Modifier.width(8.dp))
        Text(text, color = c.textSecondary, fontSize = 12.sp, lineHeight = 17.sp)
    }
}

private fun DrawScope.curve(db: FloatArray, px: (Float) -> Float, py: (Float) -> Float, color: Color, width: Float,
                            effect: PathEffect?) {
    val p = Path()
    PhoneResponse.HZ.forEachIndexed { i, f -> if (i == 0) p.moveTo(px(f), py(db[i])) else p.lineTo(px(f), py(db[i])) }
    drawPath(p, color, style = Stroke(width = width, pathEffect = effect))
}

private fun DrawScope.label(tm: TextMeasurer, text: String, x: Float, y: Float, color: Color, align: Float = 0.5f,
                            clamp: Boolean = true) {
    val r = tm.measure(text, TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Medium))
    var l = x - r.size.width * align
    if (clamp) l = l.coerceIn(0f, max(0f, size.width - r.size.width))
    drawText(r, color = color, topLeft = Offset(l, y))
}

package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.MicSpectrum
import kotlin.math.ln

/** What "마이크 스펙트럼" shows: third-octave levels of the phone microphone, in dB SPL or dB re full scale. */
@Immutable
data class MicSpecView(
    val running: Boolean,
    val noMic: Boolean = false,
    /** "폰 마이크 보정": the declared response taken off (and dB SPL where the sensitivity applies). */
    val corrected: Boolean = true,
    /** Recording UNPROCESSED (the declared sensitivity applies only there). */
    val raw: Boolean = false,
    val declaredSens: Double? = null,
    val declaredResponse: Boolean = false,
    /** One level per [MicSpectrum.CENTERS] band; empty until the first frame. */
    val levels: List<Double> = emptyList(),
    /** [levels] are dB SPL (else dB re full scale). */
    val spl: Boolean = false,
    val total: Double? = null,
    val clipped: Boolean = false,
)

/**
 * The phone microphone's spectrum under the test sounds: a band card like the probe's with the live level, the
 * correction switch, one bar per third octave (25 Hz-16 kHz) and what the numbers mean.
 */
@Composable
internal fun MicSpecPanel(v: MicSpecView, onCorr: (Boolean) -> Unit) {
    val c = LocalDevPalette.current
    Column(
        Modifier.padding(top = 8.dp).fillMaxWidth().background(c.band, RoundedCornerShape(14.dp)).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(stringResource(R.string.dev_micspec_title), color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp,
            fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
        if (v.noMic) {
            InlineNote(stringResource(R.string.dev_probe_nomic), warning = true)
            return@Column
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.dev_micspec_corr), color = c.textPrimary, fontSize = 14.sp, lineHeight = 20.sp,
                modifier = Modifier.weight(1f))
            Switch(checked = v.corrected, onCheckedChange = onCorr)
        }
        val unit = if (v.spl) "dB SPL" else "dBFS"
        val total = v.total
        if (total != null) {
            Text(stringResource(R.string.dev_micspec_total, dbText(total.toFloat()), unit), color = c.accentText,
                fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold)
        } else if (v.running) {
            Text(stringResource(R.string.dev_probe_wait), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        }
        MicSpecBars(v, unit)
        Text(stringResource(when {
            !v.corrected -> R.string.dev_micspec_note_off
            v.spl -> R.string.dev_micspec_note_spl
            v.declaredResponse && !v.raw -> R.string.dev_micspec_note_voice
            v.declaredResponse -> R.string.dev_micspec_note_shape
            else -> R.string.dev_micspec_note_none
        }), color = c.textSecondary, fontSize = 12.sp, lineHeight = 16.sp)
        if (v.clipped) InlineNote(stringResource(R.string.dev_probe_clipped), warning = true)
    }
}

@Composable
private fun MicSpecBars(v: MicSpecView, unit: String) {
    val c = LocalDevPalette.current
    val lo = 20.0
    val hi = 20000.0
    // the scale: 10-100 dB SPL, or -110 to -20 dB re full scale
    val top = if (v.spl) 100.0 else -20.0
    val span = 90.0
    val tm = androidx.compose.ui.text.rememberTextMeasurer()
    val labelStyle = androidx.compose.ui.text.TextStyle(color = c.textSecondary, fontSize = 11.sp)
    Canvas(Modifier.fillMaxWidth().height(150.dp).semantics { contentDescription = unit }) {
        val left = 28.dp.toPx()
        val axisY = size.height - 16.dp.toPx()
        val w = size.width - left
        fun x(f: Double) = left + (ln(f / lo) / ln(hi / lo)).toFloat() * w
        fun y(db: Double) = (axisY * ((top - db) / span).coerceIn(0.0, 1.0)).toFloat()
        val bw = w / 32f
        for (g in 0..3) {
            val db = top - g * 30.0
            val gy = y(db)
            drawLine(c.chevron.copy(alpha = 0.25f), Offset(left, gy), Offset(size.width, gy), 1.dp.toPx())
            val r = tm.measure(String.format(java.util.Locale.ROOT, "%.0f", db), labelStyle)
            drawText(r, topLeft = Offset(0f, (gy - r.size.height / 2f).coerceIn(0f, axisY - r.size.height)))
        }
        v.levels.forEachIndexed { i, db ->
            if (!db.isFinite()) return@forEachIndexed
            val t = y(db)
            drawRect(c.fill, Offset(x(MicSpectrum.CENTERS[i]) - bw / 2, t), Size(bw * 0.8f, (axisY - t).coerceAtLeast(2.dp.toPx())))
        }
        drawLine(c.chevron.copy(alpha = 0.6f), Offset(left, axisY), Offset(size.width, axisY), 1.dp.toPx())
        for ((f, l) in listOf(50.0 to "50", 100.0 to "100", 500.0 to "500", 1000.0 to "1k", 5000.0 to "5k", 10000.0 to "10k")) {
            val r = tm.measure(l, labelStyle)
            drawText(r, topLeft = Offset((x(f) - r.size.width / 2f).coerceIn(left, size.width - r.size.width), axisY + 3.dp.toPx()))
        }
    }
}

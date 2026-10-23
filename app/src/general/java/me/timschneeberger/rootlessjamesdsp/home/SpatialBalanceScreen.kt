package me.timschneeberger.rootlessjamesdsp.home

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.SpatialBalance
import kotlin.math.roundToInt

/*
 * "좌우 맞추기" (SpatialBalanceActivity), landscape: the stage on the left (the phone from above with the sound as a
 * dot that follows the balance), the step on the right. Palette and motion as the spatial tab: purple accents, iOS
 * easing, 300 ms; with the animations off the dot jumps.
 */

enum class BalanceStep { INTRO, MEASURING, RESULT, EAR_LO, EAR_HI, DONE, FAILED }
enum class MeasurePhase { QUIET, LEFT, RIGHT }
enum class BalanceFailure { NO_MIC, TOO_QUIET }

@Immutable
data class BalanceUi(
    val step: BalanceStep = BalanceStep.INTRO,
    val loDb: Float = 0f,
    val hiDb: Float = 0f,
    val ready: Boolean = true,
    val reduceMotion: Boolean = false,
    val progress: Float = 0f,
    val measuring: MeasurePhase = MeasurePhase.QUIET,
    val result: SpatialBalance.Result? = null,
    val failure: BalanceFailure = BalanceFailure.NO_MIC,
    /** How the values were set: "", "ear", "mic", "mic+ear". */
    val source: String = "",
)

class BalanceActions(
    val onAuto: () -> Unit,
    val onEar: () -> Unit,
    val onEarValue: (Float) -> Unit,
    val onEarNext: () -> Unit,
    /**
     * "귀로 확인하기" / "귀로 맞추기" from a result: the by-ear steps start at a sound result (else at the stored values).
     * Stores nothing; a measured value is only stored by the by-ear "저장".
     */
    val onRefine: (SpatialBalance.Result) -> Unit,
    val onSave: () -> Unit,
    val onReset: () -> Unit,
    val onClose: () -> Unit,
)

private val Ease = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)

/** "왼쪽 +1.5 dB" style: which speaker is louder by how much (the correction lowers that side). */
@Composable
private fun sideText(db: Float): String = when {
    db > 0f -> stringResource(R.string.balance_side_left, "%.1f".format(db))
    db < 0f -> stringResource(R.string.balance_side_right, "%.1f".format(-db))
    else -> stringResource(R.string.balance_side_even)
}

@Composable
fun SpatialBalanceScreen(ui: BalanceUi, actions: BalanceActions) {
    val c = rootnotePalette()
    Column(Modifier.fillMaxSize().background(c.bg).safeDrawingPadding()) {
        Row(Modifier.fillMaxWidth().padding(start = 24.dp, end = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                stringResource(R.string.balance_title),
                modifier = Modifier.weight(1f).semantics { heading() },
                color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            val closeLabel = stringResource(R.string.home_xtc_info_close)
            Box(
                Modifier.size(48.dp).clickable(role = Role.Button, onClick = actions.onClose)
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
        Row(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
            Box(
                Modifier.weight(0.5f).fillMaxHeight().background(c.band, RoundedCornerShape(20.dp)),
                contentAlignment = Alignment.Center,
            ) {
                val value = when (ui.step) {
                    BalanceStep.EAR_HI -> ui.hiDb
                    BalanceStep.EAR_LO -> ui.loDb
                    else -> (ui.loDb + ui.hiDb) / 2f
                }
                BalanceStage(value, ui)
            }
            Column(
                Modifier.weight(0.5f).fillMaxHeight().padding(start = 20.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                StepContent(ui, actions)
            }
        }
    }
}

/** The phone from above, a head below it, and the sound as a dot between the speakers that follows the balance. */
@Composable
private fun BalanceStage(valueDb: Float, ui: BalanceUi) {
    val c = rootnotePalette()
    val pos by animateFloatAsState(
        (valueDb / 6f).coerceIn(-1f, 1f), tween(if (ui.reduceMotion) 0 else 300, easing = Ease), label = "dot",
    )
    val playingLeft = ui.step == BalanceStep.MEASURING && ui.measuring == MeasurePhase.LEFT
    val playingRight = ui.step == BalanceStep.MEASURING && ui.measuring == MeasurePhase.RIGHT
    Canvas(Modifier.fillMaxSize().padding(16.dp)) {
        val unit = minOf(size.width / 8f, size.height / 6f)
        val cx = size.width / 2f
        val phoneY = size.height * 0.25f
        val pw = unit * 4.2f
        val ph = unit * 0.9f
        drawRoundRect(c.textPrimary.copy(alpha = 0.85f), Offset(cx - pw / 2, phoneY - ph / 2), Size(pw, ph), CornerRadius(ph * 0.35f))
        val sl = Offset(cx - pw / 2 + unit * 0.35f, phoneY)
        val sr = Offset(cx + pw / 2 - unit * 0.35f, phoneY)
        drawCircle(if (playingLeft) c.xtcFill else c.fill, unit * (if (playingLeft) 0.24f else 0.17f), sl)
        drawCircle(if (playingRight) c.xtcFill else c.fill, unit * (if (playingRight) 0.24f else 0.17f), sr)
        val headY = phoneY + unit * 3.2f
        val headR = unit * 0.95f
        drawCircle(c.bg, headR, Offset(cx, headY))
        drawCircle(c.textPrimary.copy(alpha = 0.7f), headR, Offset(cx, headY), style = Stroke(2.dp.toPx()))
        // the sound between the speakers; centre mark
        val y = phoneY + unit * 1.4f
        drawLine(c.divider, Offset(sl.x, y), Offset(sr.x, y), 2.dp.toPx(), StrokeCap.Round)
        drawLine(c.chevron, Offset(cx, y - unit * 0.25f), Offset(cx, y + unit * 0.25f), 2.dp.toPx(), StrokeCap.Round)
        if (ui.step != BalanceStep.MEASURING) {
            // the dot follows the slider: right = the correction moves the sound right
            val x = cx + pos * (sr.x - sl.x) / 2f
            drawCircle(c.xtcFill.copy(alpha = 0.25f), unit * 0.42f, Offset(x, y))
            drawCircle(c.xtcFill, unit * 0.22f, Offset(x, y))
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun StepContent(ui: BalanceUi, actions: BalanceActions) {
    val c = rootnotePalette()
    @Composable fun title(t: String) = Text(t, modifier = Modifier.semantics { heading() }, color = c.textPrimary,
        fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold)
    @Composable fun body(t: String) = Text(t, color = c.textPrimary, fontSize = 15.sp, lineHeight = 22.sp)
    @Composable fun note(t: String) = Text(t, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
    when (ui.step) {
        BalanceStep.INTRO -> {
            title(stringResource(R.string.balance_intro_title))
            body(stringResource(R.string.balance_intro_body))
            if (ui.loDb != 0f || ui.hiDb != 0f)
                note(stringResource(R.string.balance_current, sideText(ui.loDb), sideText(ui.hiDb)))
            if (!ui.ready) note(stringResource(R.string.balance_not_ready))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ActionButton(stringResource(R.string.balance_auto), filled = true, enabled = ui.ready, onClick = actions.onAuto)
                ActionButton(stringResource(R.string.balance_ear), filled = false, enabled = ui.ready, onClick = actions.onEar)
            }
            note(stringResource(R.string.balance_auto_note))
            if (ui.loDb != 0f || ui.hiDb != 0f)
                ActionButton(stringResource(R.string.balance_reset), filled = false, enabled = true, onClick = actions.onReset)
        }
        BalanceStep.MEASURING -> {
            title(stringResource(R.string.balance_measuring_title))
            body(stringResource(when (ui.measuring) {
                MeasurePhase.QUIET -> R.string.balance_measuring_quiet
                MeasurePhase.LEFT -> R.string.balance_measuring_left
                MeasurePhase.RIGHT -> R.string.balance_measuring_right
            }))
            ProgressLine(ui.progress, ui.reduceMotion)
            note(stringResource(R.string.balance_measuring_note))
        }
        BalanceStep.RESULT -> {
            val r = ui.result ?: return
            title(stringResource(R.string.balance_result_title))
            // a sound recording is still an estimate for this grip (the microphones' paths are assumed mirror-like, and
            // a mixed pair can pass): it only places the by-ear slider, the listener saves; an unsound one is not used
            if (r.reliable) body(stringResource(R.string.balance_result_body, sideText(r.loDb), sideText(r.hiDb)))
            note(stringResource(when {
                r.reliable -> R.string.balance_result_estimate
                !r.distinctMics -> R.string.balance_result_one_mic
                else -> R.string.balance_result_unsteady
            }))
            ActionButton(stringResource(if (r.reliable) R.string.balance_check_ear else R.string.balance_ear),
                filled = true, enabled = true) { actions.onRefine(r) }
        }
        BalanceStep.EAR_LO, BalanceStep.EAR_HI -> {
            val lo = ui.step == BalanceStep.EAR_LO
            title(stringResource(if (lo) R.string.balance_ear_lo_title else R.string.balance_ear_hi_title))
            body(stringResource(R.string.balance_ear_body))
            val v = if (lo) ui.loDb else ui.hiDb
            BalanceSlider(v, stringResource(R.string.balance_slider_label), sideText(v), actions.onEarValue)
            Row(Modifier.fillMaxWidth()) {
                note(stringResource(R.string.balance_slider_left))
                Box(Modifier.weight(1f))
                note(stringResource(R.string.balance_slider_right))
            }
            ActionButton(
                stringResource(if (lo) R.string.balance_next else R.string.balance_save), filled = true, enabled = true,
                onClick = actions.onEarNext,
            )
        }
        BalanceStep.DONE -> {
            title(stringResource(R.string.balance_done_title))
            body(stringResource(R.string.balance_done_body, sideText(ui.loDb), sideText(ui.hiDb)))
            ActionButton(stringResource(R.string.story_done), filled = true, enabled = true, onClick = actions.onClose)
        }
        BalanceStep.FAILED -> {
            title(stringResource(R.string.balance_failed_title))
            body(stringResource(if (ui.failure == BalanceFailure.NO_MIC) R.string.balance_failed_mic else R.string.balance_failed_quiet))
            ActionButton(stringResource(R.string.balance_ear), filled = true, enabled = ui.ready, onClick = actions.onEar)
        }
    }
}

@Composable
private fun ProgressLine(progress: Float, reduce: Boolean) {
    val c = rootnotePalette()
    val p by animateFloatAsState(progress, tween(if (reduce) 0 else 300), label = "progress")
    Canvas(Modifier.fillMaxWidth().heightIn(min = 8.dp)) {
        val y = size.height / 2f
        drawLine(c.sliderInactive, Offset(0f, y), Offset(size.width, y), 6.dp.toPx(), StrokeCap.Round)
        drawLine(c.xtcFill, Offset(0f, y), Offset(size.width * p, y), 6.dp.toPx(), StrokeCap.Round)
    }
}

/** -6..+6 dB in half steps; right = the sound moves right. Tap, drag, or TalkBack set-progress. */
@Composable
private fun BalanceSlider(value: Float, label: String, valueText: String, onChange: (Float) -> Unit) {
    val c = rootnotePalette()
    var width by remember { mutableFloatStateOf(1f) }
    var inset by remember { mutableFloatStateOf(0f) }
    fun at(x: Float): Float {
        val f = ((x - inset) / (width - 2 * inset).coerceAtLeast(1f)).coerceIn(0f, 1f)
        return ((f * 24f).roundToInt() - 12) / 2f
    }
    Box(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .onSizeChanged { width = it.width.toFloat().coerceAtLeast(1f) }
            .pointerInput(Unit) {
                inset = 14.dp.toPx()
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
                progressBarRangeInfo = ProgressBarRangeInfo(value, -6f..6f, steps = 23)
                setProgress { v -> onChange((v * 2f).roundToInt() / 2f); true }
            },
    ) {
        Canvas(Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            val y = size.height / 2f
            val r = 14.dp.toPx()
            drawLine(c.sliderInactive, Offset(r, y), Offset(size.width - r, y), 4.dp.toPx(), StrokeCap.Round)
            val mid = size.width / 2f
            drawLine(c.chevron, Offset(mid, y - 10.dp.toPx()), Offset(mid, y + 10.dp.toPx()), 2.dp.toPx(), StrokeCap.Round)
            val x = r + (size.width - 2 * r) * ((value + 6f) / 12f)
            drawLine(c.xtcFill, Offset(mid, y), Offset(x, y), 4.dp.toPx(), StrokeCap.Round)
            drawCircle(Color.Black.copy(alpha = 0.12f), r + 1.dp.toPx(), Offset(x, y + 1.dp.toPx()))
            drawCircle(c.thumb, r, Offset(x, y))
        }
    }
}

@Composable
private fun ActionButton(label: String, filled: Boolean, enabled: Boolean, onClick: () -> Unit) {
    val c = rootnotePalette()
    Box(
        Modifier
            .heightIn(min = 48.dp)
            .then(
                if (filled) Modifier.background(if (enabled) c.xtcFill else c.switchOff, CircleShape)
                else Modifier.border(1.dp, if (enabled) c.chipBorder else c.divider, CircleShape)
            )
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            color = when { filled && enabled -> c.thumb; enabled -> c.textPrimary; else -> c.chevron },
            fontSize = 15.sp, lineHeight = 21.sp, fontWeight = FontWeight.Bold,
        )
    }
}

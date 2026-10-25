package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.BassFitSession
import me.timschneeberger.rootlessjamesdsp.pvb.BreakupStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.CheckRound
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.FitConditions
import me.timschneeberger.rootlessjamesdsp.pvb.FitPrompt
import me.timschneeberger.rootlessjamesdsp.pvb.FitScope
import me.timschneeberger.rootlessjamesdsp.pvb.FitResult
import me.timschneeberger.rootlessjamesdsp.pvb.FloorStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.NoiseGate
import me.timschneeberger.rootlessjamesdsp.pvb.SpeakerProbe
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnButtonRow
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceRow
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.RnDivider
import me.timschneeberger.rootlessjamesdsp.ui.RnEase
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnNote
import me.timschneeberger.rootlessjamesdsp.ui.RnOutlineButton
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnTextAction
import me.timschneeberger.rootlessjamesdsp.ui.rnMotion
import java.util.Locale
import kotlin.math.roundToInt

/*
 * "저음 맞추기" (BassFitActivity), built from the shared page kit (ui/RnRows.kt): RnPage with the answers in a fixed
 * bottom bar (thumb reach, and they never scroll away during a question), section titles, paragraphs, notes and
 * pill buttons as the other detail pages write them. Drawn here only what the kit has no piece for: the two turns of
 * a step-1 question, the A/B/X play pads and the progress line of the room check.
 */

enum class FitScreen { INTRO, ROOM, ROOM_WARN, TEST, RESULT, CHECK, SAVE, DONE, VALIDATE, VAL_NEXT }
enum class FitPause { VOLUME, ROUTE, ENGINE }

@Immutable
data class FitUi(
    val screen: FitScreen = FitScreen.INTRO,
    val ready: Boolean = true,
    val lastRecord: String? = null,
    val canRestore: Boolean = false,
    /** "소음 보정": step 1's bursts corrected for the room's noise ([NoiseMasking]). */
    val noiseCorr: Boolean = false,
    // room check
    val roomPhase: Int = 0,
    val progress: Float = 0f,
    val verdict: NoiseGate.Verdict? = null,
    val noisy: Boolean = false,
    /** The microphone's reference floor from the probe sweep (reference only, never applied). */
    val micFloorHz: Double? = null,
    val micClipped: Boolean = false,
    /** The microphone's harmonic distortion of the probe sweep ("63 Hz −12 · ..."), reference only. */
    val micThd: String? = null,
    val micThd100: Double? = null,
    // questions
    val step: Int = 0,
    val prompt: FitPrompt? = null,
    /** "1" / "2" (a step-1 turn sounding), "A", "B", "X", "C" (a clip playing), null. */
    val playing: String? = null,
    /** Clips heard to the end in this question. */
    val heard: Set<String> = emptySet(),
    val answerable: Boolean = false,
    val disturbed: Boolean = false,
    val paused: FitPause? = null,
    val volumeText: String = "",
    val seedText: String = "",
    // result
    val result: FitResult? = null,
    val current: FloatArray? = null,
    val proposed: FloatArray? = null,
    val changes: Boolean = false,
    val vbAlgo: Int = 0,
    // music check and save
    val checkNumber: Int = 0,
    val checkTrials: Int = 0,
    val checkSide: Int = 1,
    /** -1: not compared. */
    val checkNew: Int = 0,
    val checkOld: Int = 0,
    val checkSame: Int = 0,
    // validation mode
    val validating: Boolean = false,
    val valScope: FitScope = FitScope.FLOOR,
    val valConds: Set<Int> = FitConditions.ALL.indices.toSet(),
    val valRepeats: Int = 3,
    val valTotal: Int = 0,
    val valIndex: Int = 0,
    val logLines: Int = 0,
    /** UMIK-1 sound playing for this condition index; 0 pink noise, 1 probe sweep. */
    val umikPlaying: Int? = null,
    val umikPhase: Int = 0,
    /** Microphone floor per condition index from the last UMIK-1 sound (-1 = none found). */
    val umikFloors: Map<Int, Double> = emptyMap(),
    /** "마이크 맞추기": 0 the room, 1 the noise being recorded; null idle. */
    val micCalPhase: Int? = null,
    val micCalRoomDone: Boolean = false,
    /** One summary line per recording source of the last step. */
    val micCalLines: List<String> = emptyList(),
    val micCalRows: Int = 0,
    /** What the phone declares about its microphone (validation screen). */
    val micDeclared: String = "",
)

class FitActions(
    val onBack: () -> Unit,
    val onStart: () -> Unit,
    val onShapeOnly: () -> Unit,
    val onNoiseCorr: (Boolean) -> Unit,
    val onRestore: () -> Unit,
    val onRoomRetry: () -> Unit,
    val onRoomProceed: () -> Unit,
    val onFloor: (FloorStaircase.Choice) -> Unit,
    val onReplay: () -> Unit,
    val onPlay: (String) -> Unit,
    /** null: "잘 모르겠어요" (counted as wrong). */
    val onAbx: (Boolean?) -> Unit,
    val onPrefer: (BassFitSession.Pick) -> Unit,
    val onBreakup: (BreakupStaircase.Answer) -> Unit,
    val onShape: (Boolean) -> Unit,
    val onCheckStart: () -> Unit,
    val onCheckSkip: () -> Unit,
    val onCheckSide: (Int) -> Unit,
    val onCheckAnswer: (CheckRound.Answer) -> Unit,
    val onSave: () -> Unit,
    val onClose: () -> Unit,
    val onValidate: () -> Unit,
    val onValScope: (FitScope) -> Unit,
    val onValCondition: (Int, Boolean) -> Unit,
    val onValRepeats: (Int) -> Unit,
    val onValStart: () -> Unit,
    val onValNext: () -> Unit,
    val onValStop: () -> Unit,
    val onUmik: (Int) -> Unit,
    val onLogCopy: () -> Unit,
    val onLogSend: () -> Unit,
    val onLogClear: () -> Unit,
    val onMicCalRoom: () -> Unit,
    val onMicCalNoise: () -> Unit,
    val onMicCalSend: () -> Unit,
    val onMicCalClear: () -> Unit,
    val onValBack: () -> Unit,
)

@Composable
fun BassFitScreen(ui: FitUi, actions: FitActions) {
    val back = when {
        ui.screen == FitScreen.VALIDATE -> actions.onValBack
        ui.validating -> actions.onValStop          // back ends the block, not the screen
        else -> actions.onBack
    }
    val title = stringResource(if (ui.validating || ui.screen == FitScreen.VALIDATE) R.string.fit_val_title else R.string.fit_title)
    RnPage(title, onBack = back, bottomBar = { BottomAnswers(ui, actions) }) {
        ui.paused?.let { p ->
            RnNote(when (p) {
                FitPause.VOLUME -> stringResource(R.string.fit_pause_volume, ui.volumeText)
                FitPause.ROUTE -> stringResource(R.string.fit_pause_route)
                FitPause.ENGINE -> stringResource(R.string.fit_pause_engine)
            }, warning = true, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        }
        when (ui.screen) {
            FitScreen.INTRO -> Intro(ui, actions)
            FitScreen.ROOM -> Room(ui)
            FitScreen.ROOM_WARN -> RoomWarn(ui)
            FitScreen.TEST -> Question(ui, actions)
            FitScreen.RESULT -> Result(ui)
            FitScreen.CHECK -> Check(ui, actions)
            FitScreen.SAVE -> Save(ui)
            FitScreen.DONE -> Done()
            FitScreen.VALIDATE -> Validate(ui, actions)
            FitScreen.VAL_NEXT -> {
                Title(stringResource(R.string.fit_val_next_title, ui.valIndex, ui.valTotal))
                Body(stringResource(R.string.fit_val_next_body))
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ text roles

/** Page heading of a step: 20/26 Bold (the kit's dialog and sheet titles), 16 dp margin. */
@Composable
private fun Title(text: String) {
    val c = LocalRn.current
    Text(text, color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold,
        modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 4.dp).semantics { heading() })
}

/** Body 15/21 primary, 16 dp margin (the consent and warning dialogs' body). */
@Composable
private fun Body(text: String) {
    val c = LocalRn.current
    Text(text, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp))
}

/** A bullet line: 5 dp dot in the fill colour and 15/21 text (the developer-mode consent list). */
@Composable
private fun Bullet(text: String) {
    val c = LocalRn.current
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 5.dp)) {
        Box(Modifier.padding(top = 8.dp, end = 10.dp).size(5.dp).background(c.fill, CircleShape))
        Text(text, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
    }
}

// ------------------------------------------------------------------------------------------------ intro, room

@Composable
private fun Intro(ui: FitUi, actions: FitActions) {
    Title(stringResource(R.string.fit_intro_title))
    Body(stringResource(R.string.fit_intro_body))
    Bullet(stringResource(R.string.fit_intro_1))
    Bullet(stringResource(R.string.fit_intro_2))
    Bullet(stringResource(R.string.fit_intro_3))
    if (!ui.ready) RnNote(stringResource(R.string.fit_not_ready), warning = true)
    RnSwitchRow(stringResource(R.string.fit_noise_corr), checked = ui.noiseCorr, onCheckedChange = actions.onNoiseCorr,
        line = stringResource(R.string.fit_noise_corr_line))
    ui.lastRecord?.let {
        RnSectionTitle(stringResource(R.string.fit_last_title))
        RnParagraph(it)
    }
}

@Composable
private fun Room(ui: FitUi) {
    Title(stringResource(R.string.fit_room_title))
    Body(stringResource(when (ui.roomPhase) {
        0 -> R.string.fit_room_quiet
        1 -> R.string.fit_room_ref
        2 -> R.string.fit_room_probe
        else -> R.string.fit_room_judge
    }))
    ProgressLine(ui.progress)
    RnParagraph(stringResource(R.string.fit_room_note))
}

@Composable
private fun RoomWarn(ui: FitUi) {
    val v = ui.verdict
    val noMic = v == null || NoiseGate.Reason.NO_MIC in v.reasons
    Title(stringResource(if (noMic) R.string.fit_nomic_title else R.string.fit_noisy_title))
    Body(stringResource(if (noMic) R.string.fit_nomic_body else R.string.fit_noisy_body))
    if (v != null && !noMic) {
        if (NoiseGate.Reason.SNR_LOW in v.reasons) RnNote(stringResource(R.string.fit_noisy_band, v.worstBandHz.roundToInt(),
            v.worstSnrDb.roundToInt(), NoiseGate.MIN_SNR_DB.roundToInt()), warning = true)
        if (NoiseGate.Reason.ROOM_UNSTEADY in v.reasons) RnNote(stringResource(R.string.fit_noisy_jump, v.jumpDb.roundToInt(),
            NoiseGate.MAX_JUMP_DB.roundToInt()), warning = true)
    }
}

/** 6 dp line, inactive track and fill (the "좌우 맞추기" measuring line, in the bass colour). */
@Composable
private fun ProgressLine(progress: Float) {
    val c = LocalRn.current
    val p by animateFloatAsState(progress, rnMotion(tween(300, easing = RnEase)), label = "progress")
    Canvas(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp).height(8.dp)) {
        val y = size.height / 2f
        drawLine(c.sliderInactive, Offset(0f, y), Offset(size.width, y), 6.dp.toPx(), StrokeCap.Round)
        drawLine(c.fill, Offset(0f, y), Offset(size.width * p.coerceIn(0f, 1f), y), 6.dp.toPx(), StrokeCap.Round)
    }
}

// ------------------------------------------------------------------------------------------------ questions

@Composable
private fun stepLabel(ui: FitUi): String = stringResource(when (val p = ui.prompt) {
    is FitPrompt.Abx -> if (p.purpose == FitPrompt.Purpose.EDGE) R.string.fit_step_1b else R.string.fit_step_2
    is FitPrompt.Prefer -> when (p.purpose) {
        FitPrompt.Purpose.EDGE -> R.string.fit_step_1b
        FitPrompt.Purpose.SHAPE -> R.string.fit_step_4
        else -> R.string.fit_step_2
    }
    is FitPrompt.Buzz -> R.string.fit_step_3
    is FitPrompt.ShapeOffer -> R.string.fit_step_4
    else -> R.string.fit_step_1
})

@Composable
private fun Question(ui: FitUi, actions: FitActions) {
    val p = ui.prompt ?: return
    val number = when (p) {
        is FitPrompt.Floor -> p.number
        is FitPrompt.Abx -> p.number
        is FitPrompt.Prefer -> p.number
        is FitPrompt.Buzz -> p.number
        else -> 0
    }
    if (ui.validating) RnSectionTitle(stringResource(R.string.fit_val_run, ui.valIndex, ui.valTotal))
    RnSectionTitle(stepLabel(ui) + if (number > 0) "  ·  " + (if (p is FitPrompt.Abx)
        stringResource(R.string.fit_question_of, number, p.maxTrials) else stringResource(R.string.fit_question, number)) else "")
    when (p) {
        is FitPrompt.Floor -> {
            Title(stringResource(R.string.fit_floor_title))
            Stage {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                    Turn(1, ui.playing == "1")
                    Turn(2, ui.playing == "2")
                }
                Box(Modifier.fillMaxWidth().padding(top = 4.dp), contentAlignment = Alignment.Center) {
                    RnTextAction(stringResource(R.string.fit_replay), bold = true,
                        enabled = ui.answerable && ui.paused == null, onClick = actions.onReplay)
                }
            }
            Body(stringResource(R.string.fit_floor_body))
            Body(stringResource(if (p.reference) R.string.fit_floor_part_ref else R.string.fit_floor_part_low))
            if (ui.disturbed) RnNote(stringResource(R.string.fit_disturbed), warning = true,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        }
        is FitPrompt.Abx -> {
            Title(stringResource(R.string.fit_abx_title))
            Stage {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (l in listOf("A", "B", "X")) PlayPad(l, l, ui, actions)
                }
            }
            Body(stringResource(if (p.purpose == FitPrompt.Purpose.EDGE) R.string.fit_abx_edge else R.string.fit_abx_layer))
            RnParagraph(stringResource(R.string.fit_abx_body))
        }
        is FitPrompt.Prefer -> {
            Title(stringResource(R.string.fit_prefer_title))
            Stage {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (l in listOf("A", "B")) PlayPad(l, l, ui, actions)
                }
            }
            RnParagraph(stringResource(R.string.fit_prefer_body))
        }
        is FitPrompt.Buzz -> {
            Title(stringResource(R.string.fit_buzz_title))
            Stage {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PlayPad("C", stringResource(R.string.fit_clip_label), ui, actions)
                    PlayPad("R", stringResource(R.string.fit_buzz_ref_label), ui, actions)
                }
            }
            RnParagraph(stringResource(R.string.fit_buzz_body))
        }
        is FitPrompt.ShapeOffer -> {
            Title(stringResource(R.string.fit_shape_title))
            Body(stringResource(R.string.fit_shape_body))
        }
        is FitPrompt.Done -> Unit
    }
}

/** The question's panel: band colour, radius 20, 16 dp inside (the developer mode's graph card). */
@Composable
private fun Stage(content: @Composable ColumnScope.() -> Unit) {
    val c = LocalRn.current
    Column(
        Modifier.padding(horizontal = 16.dp, vertical = 8.dp).fillMaxWidth().background(c.band, RoundedCornerShape(20.dp))
            .padding(16.dp),
        content = content,
    )
}

/** One turn of a step-1 question: a 72 dp circle with its number, filled while that turn sounds. */
@Composable
private fun Turn(n: Int, lit: Boolean) {
    val c = LocalRn.current
    val bg by animateColorAsState(if (lit) c.fill else c.bg, rnMotion(tween(120, easing = RnEase)), label = "turn")
    val label = stringResource(R.string.fit_interval_a11y, n)
    val playing = stringResource(R.string.fit_playing)
    Column(horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.semantics(mergeDescendants = true) { contentDescription = label; if (lit) stateDescription = playing }) {
        Box(Modifier.size(72.dp).background(bg, CircleShape).border(2.dp, if (lit) c.fill else c.chipBorder, CircleShape),
            contentAlignment = Alignment.Center) {
            Text("$n", color = if (lit) c.onFill else c.textSecondary, fontSize = 26.sp, lineHeight = 32.sp, fontWeight = FontWeight.Bold)
        }
        Text(stringResource(R.string.fit_interval, n), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
            modifier = Modifier.padding(top = 6.dp))
    }
}

/** A clip to play: radius 14, 88 dp high; playing = the selected chip colours; "heard" once played to the end. */
@Composable
private fun RowScope.PlayPad(id: String, label: String, ui: FitUi, actions: FitActions) {
    val c = LocalRn.current
    val playing = ui.playing == id
    val bg by animateColorAsState(if (playing) c.chipSelectedBg else c.bg, rnMotion(tween(300, easing = RnEase)), label = "pad")
    val a11y = stringResource(R.string.fit_play_a11y, label)
    val stateText = stringResource(when {
        playing -> R.string.fit_playing
        id in ui.heard -> R.string.fit_heard
        else -> R.string.fit_tap_to_play
    })
    val enabled = ui.paused == null
    Column(
        Modifier.weight(1f).heightIn(min = 88.dp).background(bg, RoundedCornerShape(14.dp))
            .border(if (playing) 2.dp else 1.dp, if (playing) c.chipSelectedBorder else c.chipBorder, RoundedCornerShape(14.dp))
            .clickable(enabled = enabled, role = Role.Button) { actions.onPlay(id) }
            .semantics { contentDescription = a11y; stateDescription = stateText; selected = playing }
            .padding(vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(label, color = if (playing) c.accentText else c.textPrimary, fontSize = if (label.length == 1) 28.sp else 20.sp,
            lineHeight = 34.sp, fontWeight = FontWeight.Bold)
        Text(stateText, color = if (playing) c.accentText else c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
    }
}

// ------------------------------------------------------------------------------------------------ result, check, save

private fun signed(v: Double, decimals: Int = 0): String {
    val s = String.format(Locale.ROOT, "%.${decimals}f", kotlin.math.abs(v))
    return when { v > 0.05 -> "+$s"; v < -0.05 -> "−$s"; else -> s }
}

@Composable
private fun Result(ui: FitUi) {
    val r = ui.result ?: return
    Title(stringResource(R.string.fit_result_title))
    val keep = stringResource(R.string.fit_r_keep)
    val unsure = stringResource(R.string.fit_r_unsure)
    if (!r.shapeOnly) {
    RnNavRow(stringResource(R.string.fit_r_floor), onClick = null, chevron = false, value = when {
        r.floor != null -> stringResource(R.string.fit_hz, r.floor.speakerFloorHz.roundToInt())
        r.floorHz != null -> unsure
        else -> stringResource(R.string.fit_r_not_found)
    })
    r.noiseCorrectionDb?.let { RnNavRow(stringResource(R.string.fit_noise_corr), onClick = null, chevron = false,
        line = stringResource(if (r.noiseSensFromPhone) R.string.fit_r_noise_line_phone else R.string.fit_r_noise_line_guess), value = stringResource(R.string.fit_db, BassFitActivity.signed(it))) }
    MicFloor(ui, r)
    if (r.floor != null && r.edgeHz != null) RnNavRow(stringResource(R.string.fit_r_edge), onClick = null, chevron = false,
        line = if (r.edgeHz > r.floor.boundaryHz + 1) stringResource(R.string.fit_r_edge_raised) else null,
        value = stringResource(R.string.fit_hz, r.edgeHz.roundToInt()))
    RnDivider()
    RnNavRow(stringResource(R.string.fit_r_layer), onClick = null, chevron = false, value = when (r.layerAudible) {
        true -> stringResource(R.string.fit_r_layer_yes)
        false -> stringResource(R.string.fit_r_layer_no)
        null -> keep
    })
    if (r.layerAudible == true) RnNavRow(stringResource(R.string.fit_r_strength), onClick = null, chevron = false,
        value = if (r.preferredDb != null && r.strengthConsistent) stringResource(R.string.fit_db, signed(r.preferredDb.toDouble())) else unsure)
    RnNavRow(stringResource(R.string.fit_r_limit), onClick = null, chevron = false, value = when {
        r.limitDb == null -> stringResource(R.string.fit_r_not_found)
        !r.limitReliable -> unsure
        r.breakupDb == null -> stringResource(R.string.fit_r_limit_none)
        else -> stringResource(R.string.fit_db, signed(r.limitDb))
    })
    if (r.breakupKind != null && r.breakupDb != null && r.limitReliable && r.limitDb != null && r.limitDb < 12.0) RnNavRow(stringResource(R.string.fit_r_kind), onClick = null, chevron = false,
        value = stringResource(if (r.breakupKind == BreakupStaircase.Answer.RATTLE) R.string.fit_r_kind_rattle else R.string.fit_r_kind_buzz))
    if (r.breakupCatchRattles + r.breakupCatchBuzzes > 0) RnNote(stringResource(R.string.fit_r_catch_broke), warning = true)
    }
    RnNavRow(stringResource(R.string.fit_r_shape), onClick = null, chevron = false, value = when {
        !r.shapeTried -> stringResource(R.string.fit_r_skipped)
        r.shape == null -> unsure
        else -> stringResource(R.string.fit_r_shape_value, signed(r.shape.rolloffDbOct), signed(r.shape.lowOrderDb))
    })
    if (ui.noisy) RnNote(stringResource(R.string.fit_r_noisy), warning = true)
    RnParagraph(stringResource(R.string.fit_r_conditions, ui.volumeText, ui.seedText))
    RnBand()
    val cur = ui.current
    val next = ui.proposed
    if (!ui.changes || cur == null || next == null) {
        RnNote(stringResource(R.string.fit_nothing))
        return
    }
    RnSectionTitle(stringResource(R.string.fit_changes_title))
    DevParams.ALL.forEachIndexed { i, spec ->
        if (spec.indexOf(cur[i]) != spec.indexOf(next[i])) {
            RnNavRow(stringResource(DevModeTexts.of(spec).name), onClick = null, chevron = false,
                value = stringResource(R.string.fit_change, valueText(spec, cur[i], ui.vbAlgo), valueText(spec, next[i], ui.vbAlgo)),
                valueColor = LocalRn.current.accentText)
        }
    }
}

/** The microphone's reference floor next to the ear's, and a note when they are more than 1/3 octave apart. */
@Composable
private fun MicFloor(ui: FitUi, r: FitResult) {
    val mic = ui.micFloorHz
    RnNavRow(stringResource(R.string.fit_r_mic_floor), line = stringResource(R.string.fit_r_mic_line), onClick = null, chevron = false,
        value = mic?.let { stringResource(R.string.fit_hz, SpeakerProbe.roundHz(it)) } ?: stringResource(R.string.fit_r_mic_none))
    ui.micThd?.let { RnNavRow(stringResource(R.string.fit_r_mic_thd), line = it + " dB", onClick = null, chevron = false) }
    val ear = r.floor?.speakerFloorHz ?: return
    if (mic == null) return
    val apart = kotlin.math.log2(ear / mic)
    if (apart < -1.0 / 3) RnNote(stringResource(R.string.fit_r_mic_lower))
    else if (apart > 1.0 / 3) RnNote(stringResource(R.string.fit_r_mic_higher))
}

@Composable
private fun Check(ui: FitUi, actions: FitActions) {
    val c = LocalRn.current
    RnSectionTitle(stringResource(R.string.fit_check_round, ui.checkNumber, ui.checkTrials))
    Title(stringResource(R.string.fit_check_title))
    Stage {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (side in 1..2) {
                val on = ui.checkSide == side
                val bg by animateColorAsState(if (on) c.chipSelectedBg else c.bg, rnMotion(tween(300, easing = RnEase)), label = "side")
                val label = stringResource(if (side == 1) R.string.fit_check_one else R.string.fit_check_two)
                val now = stringResource(R.string.fit_check_now, label)
                Box(
                    Modifier.weight(1f).heightIn(min = 88.dp).background(bg, RoundedCornerShape(14.dp))
                        .border(if (on) 2.dp else 1.dp, if (on) c.chipSelectedBorder else c.chipBorder, RoundedCornerShape(14.dp))
                        .clickable(enabled = ui.paused == null, role = Role.Tab) { actions.onCheckSide(side) }
                        .semantics { selected = on; if (on) stateDescription = now },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(label, color = if (on) c.accentText else c.textPrimary, fontSize = 22.sp, lineHeight = 28.sp,
                        fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                }
            }
        }
    }
    RnParagraph(stringResource(R.string.fit_check_body))
}

@Composable
private fun Save(ui: FitUi) {
    Title(stringResource(R.string.fit_save_title))
    if (ui.checkNew < 0) Body(stringResource(R.string.fit_save_unchecked))
    else {
        Body(stringResource(R.string.fit_save_counts, ui.checkTrials, ui.checkNew))
        RnParagraph(stringResource(when {
            ui.checkNew > ui.checkOld -> R.string.fit_save_new
            ui.checkOld > ui.checkNew -> R.string.fit_save_old
            else -> R.string.fit_save_same
        }))
    }
}

@Composable
private fun Done() {
    Title(stringResource(R.string.fit_saved_title))
    Body(stringResource(R.string.fit_saved_body))
}

// ------------------------------------------------------------------------------------------------ validation

@Composable
private fun conditionLabel(i: Int): String = FitConditions.ALL[i]?.let { stringResource(R.string.fit_val_cond_hp, it.roundToInt()) }
    ?: stringResource(R.string.fit_val_cond_real)

/**
 * Validation mode: one step repeated under hidden virtual speakers (the engine's high-pass), the UMIK-1 sounds per
 * condition, and the log (copy, send, clear). Kit rows only: choice rows, switch rows, navigation rows.
 */
@Composable
private fun Validate(ui: FitUi, actions: FitActions) {
    var confirmClear by remember { mutableStateOf(false) }
    Title(stringResource(R.string.fit_val_title))
    Body(stringResource(R.string.fit_val_body))
    if (!ui.ready) RnNote(stringResource(R.string.fit_not_ready), warning = true)

    RnSectionTitle(stringResource(R.string.fit_val_ear))
    RnChoiceRow(stringResource(R.string.fit_val_step), listOf(
        RnChoice(FitScope.FLOOR, stringResource(R.string.fit_val_step_floor)),
        RnChoice(FitScope.BREAKUP, stringResource(R.string.fit_val_step_breakup)),
    ), ui.valScope, actions.onValScope)
    RnChoiceRow(stringResource(R.string.fit_val_repeats), listOf(1, 2, 3, 5).map {
        RnChoice(it, stringResource(R.string.fit_val_repeats_n, it))
    }, ui.valRepeats, actions.onValRepeats)
    RnSwitchRow(stringResource(R.string.fit_noise_corr), checked = ui.noiseCorr, onCheckedChange = actions.onNoiseCorr,
        line = stringResource(R.string.fit_noise_corr_line))
    for (i in FitConditions.ALL.indices) {
        RnSwitchRow(conditionLabel(i), checked = i in ui.valConds, onCheckedChange = { on -> actions.onValCondition(i, on) })
    }
    val runs = ui.valConds.size * ui.valRepeats
    RnParagraph(stringResource(R.string.fit_val_ear_note, runs))

    RnBand()
    RnSectionTitle(stringResource(R.string.fit_val_umik))
    RnParagraph(stringResource(R.string.fit_val_umik_note))
    for (i in FitConditions.ALL.indices) {
        val playing = ui.umikPlaying == i
        val floor = ui.umikFloors[i]
        RnNavRow(conditionLabel(i), chevron = false, enabled = ui.ready || playing,
            line = when {
                playing && ui.umikPhase == 0 -> stringResource(R.string.fit_val_umik_pink)
                playing -> stringResource(R.string.fit_val_umik_sweep)
                floor != null -> if (floor > 0) stringResource(R.string.fit_val_umik_floor, SpeakerProbe.roundHz(floor))
                    else stringResource(R.string.fit_r_mic_none)
                else -> null
            },
            value = stringResource(if (playing) R.string.fit_val_umik_stop else R.string.fit_val_umik_play),
            valueColor = LocalRn.current.accentText,
            onClick = { actions.onUmik(i) })
    }

    RnBand()
    RnSectionTitle(stringResource(R.string.fit_mcal_title))
    RnParagraph(stringResource(R.string.fit_mcal_note))
    if (ui.micDeclared.isNotEmpty()) RnParagraph(ui.micDeclared)
    val busy = ui.micCalPhase != null
    RnNavRow(stringResource(R.string.fit_mcal_room), chevron = false, enabled = !busy,
        line = if (ui.micCalPhase == 0) stringResource(R.string.fit_mcal_recording) else null,
        value = stringResource(if (ui.micCalRoomDone) R.string.fit_mcal_again else R.string.fit_mcal_start),
        valueColor = LocalRn.current.accentText, onClick = actions.onMicCalRoom)
    RnNavRow(stringResource(R.string.fit_mcal_noise), chevron = false, enabled = !busy && ui.micCalRoomDone,
        line = if (ui.micCalPhase == 1) stringResource(R.string.fit_mcal_recording) else null,
        value = stringResource(R.string.fit_mcal_start),
        valueColor = LocalRn.current.accentText, onClick = actions.onMicCalNoise)
    for (l in ui.micCalLines) RnParagraph(l)
    if (ui.micCalRows > 0) {
        RnParagraph(stringResource(R.string.fit_mcal_rows, ui.micCalRows))
        RnButtonRow {
            RnOutlineButton(stringResource(R.string.fit_val_log_clear), Modifier.weight(1f), enabled = !busy, onClick = actions.onMicCalClear)
            RnOutlineButton(stringResource(R.string.fit_val_log_send), Modifier.weight(1f), onClick = actions.onMicCalSend)
        }
    }

    RnBand()
    RnSectionTitle(stringResource(R.string.fit_val_log_title))
    RnParagraph(stringResource(R.string.fit_val_log_lines, ui.logLines))
    if (ui.logLines > 0) {
        RnButtonRow {
            RnOutlineButton(stringResource(R.string.fit_val_log_clear), Modifier.weight(1f)) { confirmClear = true }
            RnOutlineButton(stringResource(R.string.fit_val_log_copy), Modifier.weight(1f), onClick = actions.onLogCopy)
            RnOutlineButton(stringResource(R.string.fit_val_log_send), Modifier.weight(1f), onClick = actions.onLogSend)
        }
    }
    if (confirmClear) RnDialog(
        title = stringResource(R.string.fit_val_log_clear_title), text = stringResource(R.string.fit_val_log_clear_body, ui.logLines),
        confirmLabel = stringResource(R.string.fit_val_log_clear), onConfirm = { confirmClear = false; actions.onLogClear() },
        dismissLabel = stringResource(android.R.string.cancel), onDismiss = { confirmClear = false },
    )
}

// ------------------------------------------------------------------------------------------------ answers (bottom bar)

@Composable
private fun BottomAnswers(ui: FitUi, actions: FitActions) {
    val c = LocalRn.current
    val on = ui.answerable && ui.paused == null
    if (ui.screen == FitScreen.ROOM) return          // nothing to answer while the room is measured
    Box(Modifier.fillMaxWidth().height(1.dp).background(c.divider))
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        when (ui.screen) {
            FitScreen.INTRO -> {
                RnButtonRow { RnFilledButton(stringResource(R.string.fit_start), Modifier.weight(1f), enabled = ui.ready, onClick = actions.onStart) }
                RnButtonRow { RnOutlineButton(stringResource(R.string.fit_shape_only), Modifier.weight(1f), enabled = ui.ready, onClick = actions.onShapeOnly) }
                RnButtonRow {
                    if (ui.canRestore) RnOutlineButton(stringResource(R.string.fit_restore), Modifier.weight(1f), onClick = actions.onRestore)
                    RnOutlineButton(stringResource(R.string.fit_val_open), Modifier.weight(1f), onClick = actions.onValidate)
                }
            }
            FitScreen.VALIDATE -> RnButtonRow {
                RnFilledButton(stringResource(R.string.fit_val_start), Modifier.weight(1f),
                    enabled = ui.ready && ui.valConds.isNotEmpty() && ui.umikPlaying == null, onClick = actions.onValStart)
            }
            FitScreen.VAL_NEXT -> RnButtonRow {
                RnOutlineButton(stringResource(R.string.fit_val_stop), Modifier.weight(1f), onClick = actions.onValStop)
                RnFilledButton(stringResource(R.string.fit_val_next), Modifier.weight(1f), onClick = actions.onValNext)
            }
            FitScreen.ROOM -> Unit
            FitScreen.ROOM_WARN -> {
                RnButtonRow { RnFilledButton(stringResource(R.string.fit_retry_quiet), Modifier.weight(1f), onClick = actions.onRoomRetry) }
                RnButtonRow { RnOutlineButton(stringResource(R.string.fit_proceed), Modifier.weight(1f), onClick = actions.onRoomProceed) }
            }
            FitScreen.TEST -> when (ui.prompt) {
                is FitPrompt.Floor -> {
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_floor_first), Modifier.weight(1f), enabled = on) { actions.onFloor(FloorStaircase.Choice.FIRST) }
                        RnOutlineButton(stringResource(R.string.fit_floor_second), Modifier.weight(1f), enabled = on) { actions.onFloor(FloorStaircase.Choice.SECOND) }
                    }
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_floor_neither), Modifier.weight(1f), enabled = on) { actions.onFloor(FloorStaircase.Choice.NEITHER) }
                        RnOutlineButton(stringResource(R.string.fit_floor_buzz), Modifier.weight(1f), enabled = on) { actions.onFloor(FloorStaircase.Choice.BUZZ_ONLY) }
                    }
                }
                is FitPrompt.Abx -> {
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_abx_is_a), Modifier.weight(1f), enabled = on) { actions.onAbx(true) }
                        RnOutlineButton(stringResource(R.string.fit_abx_is_b), Modifier.weight(1f), enabled = on) { actions.onAbx(false) }
                    }
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_abx_unsure), Modifier.weight(1f), enabled = on) { actions.onAbx(null) }
                    }
                }
                is FitPrompt.Prefer -> {
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_prefer_a), Modifier.weight(1f), enabled = on) { actions.onPrefer(BassFitSession.Pick.A) }
                        RnOutlineButton(stringResource(R.string.fit_prefer_b), Modifier.weight(1f), enabled = on) { actions.onPrefer(BassFitSession.Pick.B) }
                    }
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.fit_prefer_same), Modifier.weight(1f), enabled = on) { actions.onPrefer(BassFitSession.Pick.SAME) }
                    }
                }
                is FitPrompt.Buzz -> RnButtonRow {
                    RnOutlineButton(stringResource(R.string.fit_buzz_clean), Modifier.weight(1f), enabled = on) { actions.onBreakup(BreakupStaircase.Answer.CLEAN) }
                    RnOutlineButton(stringResource(R.string.fit_buzz_rattle), Modifier.weight(1f), enabled = on) { actions.onBreakup(BreakupStaircase.Answer.RATTLE) }
                    RnOutlineButton(stringResource(R.string.fit_buzz_buzz), Modifier.weight(1f), enabled = on) { actions.onBreakup(BreakupStaircase.Answer.BUZZ) }
                }
                is FitPrompt.ShapeOffer -> {
                    RnButtonRow { RnFilledButton(stringResource(R.string.fit_shape_take), Modifier.weight(1f)) { actions.onShape(true) } }
                    RnButtonRow { RnOutlineButton(stringResource(R.string.fit_shape_skip), Modifier.weight(1f)) { actions.onShape(false) } }
                }
                else -> Unit
            }
            FitScreen.RESULT -> if (ui.changes) {
                RnButtonRow { RnFilledButton(stringResource(R.string.fit_check_start), Modifier.weight(1f), onClick = actions.onCheckStart) }
                RnButtonRow {
                    RnOutlineButton(stringResource(R.string.fit_discard), Modifier.weight(1f), onClick = actions.onClose)
                    RnOutlineButton(stringResource(R.string.fit_check_skip), Modifier.weight(1f), onClick = actions.onCheckSkip)
                }
            } else RnButtonRow { RnFilledButton(stringResource(R.string.fit_close), Modifier.weight(1f), onClick = actions.onClose) }
            FitScreen.CHECK -> {
                val ok = ui.paused == null
                RnButtonRow {
                    RnOutlineButton(stringResource(R.string.fit_check_first), Modifier.weight(1f), enabled = ok) { actions.onCheckAnswer(CheckRound.Answer.FIRST) }
                    RnOutlineButton(stringResource(R.string.fit_check_second), Modifier.weight(1f), enabled = ok) { actions.onCheckAnswer(CheckRound.Answer.SECOND) }
                }
                RnButtonRow {
                    RnOutlineButton(stringResource(R.string.fit_check_same), Modifier.weight(1f), enabled = ok) { actions.onCheckAnswer(CheckRound.Answer.SAME) }
                }
            }
            FitScreen.SAVE -> {
                RnButtonRow { RnFilledButton(stringResource(R.string.fit_save), Modifier.weight(1f), onClick = actions.onSave) }
                RnButtonRow { RnOutlineButton(stringResource(R.string.fit_discard), Modifier.weight(1f), onClick = actions.onClose) }
            }
            FitScreen.DONE -> RnButtonRow { RnFilledButton(stringResource(R.string.fit_close), Modifier.weight(1f), onClick = actions.onClose) }
        }
    }
}

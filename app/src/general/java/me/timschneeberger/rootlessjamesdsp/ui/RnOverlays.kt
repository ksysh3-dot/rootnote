package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/*
 * Dialogs and sheets (docs/DESIGN.md 4/5: 대화상자 radius 28, 시트 top radius 28 with a 36×4 handle), written as the
 * developer mode writes them: page-coloured container, title 20/26 Bold (a heading), body 15/21, filled and outline
 * pill buttons or text actions.
 */

/** One option of a choice sheet: [label] with an optional [line] under it. */
data class RnChoice<T>(val value: T, val label: String, val line: String? = null)

/** A simple message dialog. [dismissLabel] null: one button only. */
@Composable
fun RnDialog(
    title: String,
    text: String,
    confirmLabel: String = stringResource(android.R.string.ok),
    onConfirm: () -> Unit,
    dismissLabel: String? = null,
    onDismiss: () -> Unit = onConfirm,
    neutralLabel: String? = null,
    onNeutral: () -> Unit = {},
    dismissible: Boolean = true,
    content: (@Composable ColumnScope.() -> Unit)? = null,
) {
    val c = LocalRn.current
    AlertDialog(
        onDismissRequest = { if (dismissible) onDismiss() },
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = { RnDialogTitle(title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (text.isNotEmpty()) Text(text, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                content?.invoke(this)
            }
        },
        dismissButton = if (dismissLabel != null || neutralLabel != null) {
            {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (neutralLabel != null) RnTextAction(neutralLabel, onClick = onNeutral)
                    if (dismissLabel != null) RnTextAction(dismissLabel, onClick = onDismiss)
                }
            }
        } else null,
        confirmButton = { RnFilledButton(confirmLabel, onClick = onConfirm) },
    )
}

@Composable
fun RnDialogTitle(title: String) {
    val c = LocalRn.current
    Text(title, color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold,
        modifier = Modifier.semantics { heading() })
}

/** A bottom sheet with the kit's look; [content] is laid out in a column with 24 dp side margins. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RnSheet(onDismiss: () -> Unit, title: String? = null, content: @Composable ColumnScope.() -> Unit) {
    val c = LocalRn.current
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheet,
        containerColor = c.bg,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        dragHandle = { Box(Modifier.padding(vertical = 10.dp).size(width = 36.dp, height = 4.dp).background(c.chipBorder, CircleShape)) },
    ) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(bottom = 16.dp)) {
            if (title != null) Box(Modifier.padding(start = 24.dp, end = 24.dp, bottom = 8.dp)) { RnDialogTitle(title) }
            content()
        }
    }
}

/**
 * A row whose value is one of a few choices (a ListPreference): title, the chosen label on the right, a chevron.
 * Tapping opens [RnChoiceSheet].
 */
@Composable
fun <T> RnChoiceRow(
    title: String,
    choices: List<RnChoice<T>>,
    selected: T?,
    onSelect: (T) -> Unit,
    line: String? = null,
    enabled: Boolean = true,
    valueInLine: Boolean = false,
) {
    var open by remember { mutableStateOf(false) }
    val current = choices.firstOrNull { it.value == selected }
    RnNavRow(
        title = title,
        line = if (valueInLine) listOfNotNull(current?.label, line).joinToString("\n") else line,
        value = if (valueInLine) null else current?.label,
        enabled = enabled,
        onClick = { open = true },
    )
    if (open) RnChoiceSheet(title, choices, selected, onDismiss = { open = false }) { onSelect(it); open = false }
}

/** Radio list in a sheet: rows min 56, the chosen one in the accent colour with a check (role RadioButton). */
@Composable
fun <T> RnChoiceSheet(title: String, choices: List<RnChoice<T>>, selected: T?, onDismiss: () -> Unit, onSelect: (T) -> Unit) {
    val c = LocalRn.current
    RnSheet(onDismiss, title) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).selectableGroup()) {
            for (ch in choices) {
                val on = ch.value == selected
                Row(
                    Modifier.fillMaxWidth().selectable(selected = on, role = Role.RadioButton) { onSelect(ch.value) }
                        .heightIn(min = 56.dp).padding(horizontal = 24.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(ch.label, color = if (on) c.accentText else c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
                            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal)
                        if (!ch.line.isNullOrEmpty()) Text(ch.line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
                    }
                    Spacer(Modifier.width(12.dp))
                    Box(Modifier.size(24.dp)) { if (on) RnCheckMark() }
                }
            }
        }
    }
}

/** A 24 dp check in the accent colour (2 dp round strokes); [color] and [side] for a check on a filled mark. */
@Composable
fun RnCheckMark(color: Color? = null, side: Dp = 24.dp) {
    val c = LocalRn.current
    val tint = color ?: c.accentText
    Canvas(Modifier.size(side)) {
        val s = size.width / 24f
        val st = Stroke(2.2f * s, cap = StrokeCap.Round)
        val p = androidx.compose.ui.graphics.Path().apply { moveTo(5f * s, 12.5f * s); lineTo(10f * s, 17.5f * s); lineTo(19f * s, 7f * s) }
        drawPath(p, tint, style = st)
    }
}

/**
 * A text input dialog (the legacy "값 편집" and name prompts): an outlined field with a hint, an optional unit
 * suffix, numeric keyboard when [number]; [validate] returns an error to show under the field, or null to accept.
 */
@Composable
fun RnInputDialog(
    title: String,
    initial: String,
    onDone: (String) -> Unit,
    onDismiss: () -> Unit,
    hint: String? = null,
    suffix: String? = null,
    number: Boolean = false,
    message: String? = null,
    validate: (String) -> String? = { null },
) {
    val c = LocalRn.current
    var text by remember { mutableStateOf(initial) }
    var error by remember { mutableStateOf<String?>(null) }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
    fun submit() {
        val e = validate(text.trim())
        if (e == null) onDone(text.trim()) else error = e
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = { RnDialogTitle(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!message.isNullOrEmpty()) Text(message, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                OutlinedTextField(
                    value = text, onValueChange = { text = it; error = null },
                    modifier = Modifier.fillMaxWidth().focusRequester(focus),
                    label = hint?.let { { Text(it) } },
                    suffix = suffix?.let { { Text(it, color = c.textSecondary) } },
                    singleLine = !(!number && initial.contains('\n')),
                    isError = error != null,
                    supportingText = error?.let { { Text(it) } },
                    keyboardOptions = if (number) KeyboardOptions(keyboardType = KeyboardType.Decimal) else KeyboardOptions.Default,
                    shape = RoundedCornerShape(14.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = c.fill, unfocusedBorderColor = c.chipBorder, cursorColor = c.fill,
                        focusedLabelColor = c.accentText, focusedTextColor = c.textPrimary, unfocusedTextColor = c.textPrimary,
                    ),
                )
            }
        },
        dismissButton = { RnTextAction(stringResource(android.R.string.cancel), onClick = onDismiss) },
        confirmButton = { RnFilledButton(stringResource(android.R.string.ok), onClick = ::submit) },
    )
}

/** Multiple choice (checkbox rows) in a dialog; confirm is enabled when something is picked (unless [allowNone]). */
@Composable
fun <T> RnMultiChoiceDialog(
    title: String,
    choices: List<RnChoice<T>>,
    confirmLabel: String,
    onConfirm: (List<T>) -> Unit,
    onDismiss: () -> Unit,
    initial: Set<T> = emptySet(),
    allowNone: Boolean = false,
) {
    val c = LocalRn.current
    val picked = remember { mutableStateListOf<T>().apply { addAll(initial) } }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = { RnDialogTitle(title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                for (ch in choices) {
                    val on = ch.value in picked
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .toggleable(value = on, role = Role.Checkbox) { if (it) picked.add(ch.value) else picked.remove(ch.value) },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(checked = on, onCheckedChange = null,
                            colors = CheckboxDefaults.colors(checkedColor = c.fill, uncheckedColor = c.chevron, checkmarkColor = c.onFill))
                        Spacer(Modifier.width(8.dp))
                        Column {
                            Text(ch.label, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
                            if (!ch.line.isNullOrEmpty()) Text(ch.line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
                        }
                    }
                }
            }
        },
        dismissButton = { RnTextAction(stringResource(android.R.string.cancel), onClick = onDismiss) },
        confirmButton = {
            RnFilledButton(confirmLabel, enabled = allowNone || picked.isNotEmpty()) { onConfirm(picked.toList()) }
        },
    )
}

/** A progress dialog: title, an indeterminate (or [progress] 0..1) bar, an optional cancel. */
@Composable
fun RnProgressDialog(title: String, progress: Float? = null, line: String? = null, onCancel: (() -> Unit)? = null) {
    val c = LocalRn.current
    AlertDialog(
        onDismissRequest = {},
        containerColor = c.bg,
        shape = RoundedCornerShape(28.dp),
        title = { RnDialogTitle(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (progress == null) LinearProgressIndicator(Modifier.fillMaxWidth(), color = c.fill, trackColor = c.sliderInactive)
                else LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth(), color = c.fill, trackColor = c.sliderInactive)
                if (!line.isNullOrEmpty()) Text(line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            }
        },
        confirmButton = { if (onCancel != null) RnTextAction(stringResource(android.R.string.cancel), onClick = onCancel) },
    )
}


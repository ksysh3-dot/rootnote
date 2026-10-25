package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.R

/*
 * Page frame and rows (docs/DESIGN.md 1, 4, 5): SEED structure — section title, rows, an 8 dp band between groups,
 * no cards around row groups; rows tint on press (120 ms), switches move with IosEase. Written as the home screen's
 * NavRow/SwitchRow/IosSwitch and the developer mode's top bar, buttons and notes.
 */

// ------------------------------------------------------------------------------------------------ page frame

/**
 * A detail page: the top bar, then [content] in a vertical scroll, then an optional fixed [bottomBar]. Pads for the
 * status and navigation bars (the activity is edge-to-edge).
 */
@Composable
fun RnPage(
    title: String,
    onBack: (() -> Unit)?,
    actions: @Composable RowScope.() -> Unit = {},
    bottomBar: (@Composable () -> Unit)? = null,
    scroll: Boolean = true,
    content: @Composable ColumnScope.() -> Unit,
) {
    val c = LocalRn.current
    Column(Modifier.fillMaxSize().background(c.bg).statusBarsPadding().navigationBarsPadding()) {
        RnTopBar(title, onBack, actions)
        Column(
            Modifier.weight(1f).fillMaxWidth().then(if (scroll) Modifier.verticalScroll(rememberScrollState()) else Modifier),
            content = content,
        )
        bottomBar?.invoke()
    }
}

/** Back chevron in a 48 dp target, the title (20/26 Bold, heading), trailing 48 dp actions (DevMode TopBar). */
@Composable
fun RnTopBar(title: String, onBack: (() -> Unit)?, actions: @Composable RowScope.() -> Unit = {}) {
    val c = LocalRn.current
    Row(
        Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(start = if (onBack != null) 4.dp else 16.dp, end = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            val back = stringResource(R.string.dev_back)
            val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
            Box(
                Modifier.size(48.dp).clickable(role = Role.Button, onClick = onBack).semantics { contentDescription = back },
                contentAlignment = Alignment.Center,
            ) {
                Canvas(Modifier.size(24.dp).graphicsLayer { scaleX = if (rtl) -1f else 1f }) {
                    val s = size.width / 24f
                    val p = Path().apply { moveTo(15f * s, 5f * s); lineTo(8f * s, 12f * s); lineTo(15f * s, 19f * s) }
                    drawPath(p, c.textPrimary, style = Stroke(width = 2.2f * s, cap = StrokeCap.Round, join = StrokeJoin.Round))
                }
            }
        }
        Text(
            title, modifier = Modifier.weight(1f).padding(start = 4.dp, end = 8.dp).semantics { heading() },
            color = c.textPrimary, fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp,
        )
        actions()
    }
}

/** A 48 dp icon action for the top or bottom bar; [icon] draws in the given colour (2 dp round strokes). */
@Composable
fun RnIconAction(label: String, enabled: Boolean = true, onClick: () -> Unit, icon: @Composable (Color) -> Unit) {
    val c = LocalRn.current
    Box(
        Modifier.size(48.dp).clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) { icon(if (enabled) c.textPrimary else c.chevron) }
}

/** The 8 dp grey band between groups (docs/DESIGN.md 4). */
@Composable
fun RnBand() {
    Box(Modifier.fillMaxWidth().height(8.dp).background(LocalRn.current.band))
}

/** A 1 dp divider between rows of one group, inset 16 dp. */
@Composable
fun RnDivider() {
    Box(Modifier.padding(horizontal = 16.dp).fillMaxWidth().height(1.dp).background(LocalRn.current.divider))
}

/**
 * Section title: 13/18 secondary, a heading, 16 dp side margin (DevMode's section labels). With [onInfo], an (i) at
 * the right end in a 48 dp target opens the section's long explanation (the home screen's spatial (i)).
 */
@Composable
fun RnSectionTitle(text: String, onInfo: (() -> Unit)? = null, infoLabel: String = "") {
    val c = LocalRn.current
    if (onInfo == null) {
        Text(
            text, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium,
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 4.dp).semantics { heading() },
        )
        return
    }
    Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp, top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(
            text, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f).semantics { heading() },
        )
        Box(
            Modifier.size(48.dp).clickable(role = Role.Button, onClick = onInfo).semantics { contentDescription = infoLabel },
            contentAlignment = Alignment.Center,
        ) {
            Box(Modifier.size(22.dp).border(1.5.dp, c.accentText, CircleShape), contentAlignment = Alignment.Center) {
                Text("i", color = c.accentText, fontSize = 13.sp, lineHeight = 13.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ rows

/** The row background: page colour, tinted rn_press while pressed (120 ms). */
@Composable
private fun pressTint(interaction: MutableInteractionSource, enabled: Boolean): Color {
    val c = LocalRn.current
    val pressed by interaction.collectIsPressedAsState()
    val bg by animateColorAsState(if (pressed && enabled) c.press else c.bg, rnMotion(if (pressed && enabled) tween(0) else tween(RN_MS_COLOR, easing = RnEase)), label = "press")
    return bg
}

/** Title 16/22 and an optional line 13/18 (the home screen's row text). */
@Composable
private fun RowText(title: String, line: String?, enabled: Boolean, modifier: Modifier, bold: Boolean = false) {
    val c = LocalRn.current
    Column(modifier.alpha(if (enabled) 1f else 0.4f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal)
        if (!line.isNullOrEmpty()) Text(line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
    }
}

/**
 * A row that goes somewhere or opens something: title, optional line, a value on the right (13/18 secondary) and a
 * chevron ([chevron] false for a row that acts in place). Min 56 dp, 16/12 padding, press tint.
 */
@Composable
fun RnNavRow(
    title: String,
    line: String? = null,
    value: String? = null,
    enabled: Boolean = true,
    chevron: Boolean = true,
    valueColor: Color? = null,
    onClick: (() -> Unit)?,
) {
    val c = LocalRn.current
    val interaction = remember { MutableInteractionSource() }
    Row(
        Modifier.fillMaxWidth().background(pressTint(interaction, enabled && onClick != null))
            .then(if (onClick != null) Modifier.clickable(interaction, null, enabled = enabled, role = Role.Button, onClick = onClick)
                else Modifier.semantics(mergeDescendants = true) {})
            .heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        RowText(title, line, enabled, Modifier.weight(1f))
        if (!value.isNullOrEmpty()) Text(
            value, modifier = Modifier.weight(1f, fill = false).alpha(if (enabled) 1f else 0.4f),
            color = valueColor ?: c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, textAlign = TextAlign.End,
        )
        if (chevron && onClick != null) RnChevron(enabled)
    }
}

/** 18 dp chevron, mirrored in RTL. */
@Composable
fun RnChevron(enabled: Boolean = true) {
    val c = LocalRn.current
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    Canvas(Modifier.size(18.dp).alpha(if (enabled) 1f else 0.4f).graphicsLayer { scaleX = if (rtl) -1f else 1f }) {
        val s = size.width / 24f
        val p = Path().apply { moveTo(9f * s, 6f * s); lineTo(15f * s, 12f * s); lineTo(9f * s, 18f * s) }
        drawPath(p, c.chevron, style = Stroke(width = 2f * s * 1.2f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
}

/**
 * A row that toggles a switch: the whole row is the switch (role Switch, with its state). Min 72 dp with a line,
 * 56 without; [line] can change with the state (summaryOn / summaryOff).
 */
@Composable
fun RnSwitchRow(
    title: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    line: String? = null,
    enabled: Boolean = true,
    bold: Boolean = false,
    icon: Painter? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    Row(
        Modifier.fillMaxWidth().background(pressTint(interaction, enabled))
            .toggleable(value = checked, interactionSource = interaction, indication = null, enabled = enabled,
                role = Role.Switch, onValueChange = onCheckedChange)
            .heightIn(min = if (line.isNullOrEmpty()) 56.dp else 72.dp).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (icon != null) RowIcon(icon, enabled)
        RowText(title, line, enabled, Modifier.weight(1f), bold)
        Box(Modifier.alpha(if (enabled) 1f else 0.4f)) { RnSwitch(checked) }
    }
}

/** A 24 dp row icon in the secondary colour (the module icons of the advanced screen). Decorative. */
@Composable
private fun RowIcon(icon: Painter, enabled: Boolean) {
    Icon(icon, contentDescription = null, tint = LocalRn.current.textSecondary,
        modifier = Modifier.size(24.dp).alpha(if (enabled) 1f else 0.4f))
}

/**
 * The title of a group that has no switch of its own (the advanced screen's "출력 제어"): 16/22 Bold like a bold
 * switch row's title, a heading, min 56 dp, with an optional icon.
 */
@Composable
fun RnGroupTitle(title: String, icon: Painter? = null, enabled: Boolean = true) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 12.dp).semantics { heading() },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (icon != null) RowIcon(icon, enabled)
        RowText(title, null, enabled, Modifier.weight(1f), bold = true)
    }
}

/** 51×31, thumb 27 at 2/22, on = fill, off = rn_switch_off (docs/DESIGN.md 5). Visual only. */
@Composable
fun RnSwitch(checked: Boolean) {
    val c = LocalRn.current
    // thumb and track end together; the thumb moves in the draw phase (no layout pass per frame)
    val x by animateDpAsState(if (checked) 22.dp else 2.dp, rnMotion(tween(RN_MS_MOVE, easing = RnEase)), label = "swX")
    val track by animateColorAsState(if (checked) c.fill else c.switchOff, rnMotion(tween(RN_MS_MOVE, easing = RnEase)), label = "swT")
    Box(Modifier.size(width = 51.dp, height = 31.dp).background(track, CircleShape)) {
        Box(Modifier.offset(y = 2.dp).size(27.dp).graphicsLayer { translationX = x.toPx() }.shadow(3.dp, CircleShape).background(c.thumb, CircleShape))
    }
}

// ------------------------------------------------------------------------------------------------ text, notes, buttons

/** Body text inside a page (15/21), 16 dp side margin. */
@Composable
fun RnParagraph(text: String, modifier: Modifier = Modifier, color: Color? = null) {
    val c = LocalRn.current
    Text(text, color = color ?: c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
        modifier = modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp))
}

/**
 * An information note: an "i" in a circle and the text (13/18), on the band colour, radius 14 (docs/DESIGN.md 4).
 * [warning] uses the warning colours (rn_warn_*) and an orange dot instead (인라인 경고: cannot be dismissed).
 */
@Composable
fun RnNote(text: String, warning: Boolean = false, modifier: Modifier = Modifier, onClick: (() -> Unit)? = null) {
    val c = LocalRn.current
    val bg = if (warning) colorResource(R.color.rn_warn_bg) else c.band
    val fg = if (warning) colorResource(R.color.rn_warn_text) else c.textSecondary
    val dot = colorResource(R.color.rn_warn_dot)
    Row(
        modifier.padding(horizontal = 16.dp, vertical = 8.dp).fillMaxWidth()
            .background(bg, RoundedCornerShape(14.dp))
            .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (warning) Box(Modifier.padding(top = 5.dp).size(8.dp).background(dot, CircleShape))
        else Canvas(Modifier.padding(top = 1.dp).size(16.dp)) {
            val s = size.width / 24f
            drawCircle(fg, 9f * s, style = Stroke(2f * s * 1.4f))
            drawCircle(fg, 1.4f * s, Offset(12f * s, 7.6f * s))
            drawLine(fg, Offset(12f * s, 11f * s), Offset(12f * s, 16.5f * s), 2f * s * 1.4f, StrokeCap.Round)
        }
        Text(text, color = fg, fontSize = 13.sp, lineHeight = 18.sp, modifier = Modifier.weight(1f),
            fontWeight = if (warning) FontWeight.Medium else FontWeight.Normal)
    }
}

/** A text button (14/20 accent, Medium or Bold) in a 48 dp target (home banner actions, DevMode TextAction). */
@Composable
fun RnTextAction(label: String, bold: Boolean = false, color: Color? = null, enabled: Boolean = true, onClick: () -> Unit) {
    val c = LocalRn.current
    Box(
        Modifier.heightIn(min = 48.dp).clickable(enabled = enabled, role = Role.Button, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = (color ?: c.accentText).copy(alpha = if (enabled) 1f else 0.4f), fontSize = 14.sp,
            lineHeight = 20.sp, fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium)
    }
}

/** Pressed controls shrink to [to] over 120 ms and settle back with a spring (docs/DESIGN.md 6 누름). */
@Composable
fun pressScale(interaction: MutableInteractionSource, enabled: Boolean, to: Float = 0.96f): Float {
    val pressed by interaction.collectIsPressedAsState()
    val reduce = LocalRnReduceMotion.current
    val s by animateFloatAsState(
        if (pressed && enabled) to else 1f,
        when {
            reduce -> androidx.compose.animation.core.snap()
            pressed -> tween(120, easing = RnEase)
            else -> rnRelease()
        },
        label = "pressScale",
    )
    return s
}

/** Main button: pill, fill colour, 15/21 Bold onFill text, min 48 (docs/DESIGN.md 5 주 버튼). */
@Composable
fun RnFilledButton(label: String, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    val c = LocalRn.current
    val interaction = remember { MutableInteractionSource() }
    val scale = pressScale(interaction, enabled)
    Box(
        modifier.graphicsLayer { scaleX = scale; scaleY = scale }.heightIn(min = 48.dp)
            .background(if (enabled) c.fill else c.switchOff, CircleShape)
            .clickable(interaction, null, enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = if (enabled) c.onFill else c.textSecondary, fontSize = 15.sp, lineHeight = 21.sp,
            fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
    }
}

/** Secondary button: pill with a 1 dp outline (docs/DESIGN.md 5 보조 버튼). */
@Composable
fun RnOutlineButton(label: String, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    val c = LocalRn.current
    val interaction = remember { MutableInteractionSource() }
    val scale = pressScale(interaction, enabled)
    Box(
        modifier.graphicsLayer { scaleX = scale; scaleY = scale }.heightIn(min = 48.dp)
            .border(1.dp, c.chipBorder, CircleShape)
            .clickable(interaction, null, enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = if (enabled) c.textPrimary else c.chevron, fontSize = 15.sp, lineHeight = 21.sp,
            fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
    }
}

/** A row of buttons at the end of a block, 16 dp margin, 8 dp apart. */
@Composable
fun RnButtonRow(content: @Composable RowScope.() -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

/** An empty list: a message in the middle of the page (13/18 secondary) with an optional action. */
@Composable
fun RnEmpty(text: String, top: Dp = 64.dp, action: (@Composable () -> Unit)? = null) {
    val c = LocalRn.current
    Column(
        Modifier.fillMaxWidth().padding(start = 32.dp, end = 32.dp, top = top, bottom = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(text, color = c.textSecondary, fontSize = 15.sp, lineHeight = 21.sp, textAlign = TextAlign.Center)
        action?.invoke()
    }
}

/** Spacer at the end of a page so the last row is not under the navigation bar gesture area. */
@Composable
fun RnEndSpace(height: Dp = 24.dp) = Spacer(Modifier.height(height))

/** A small rounded badge (radius 5, 11/16 Medium; docs/DESIGN.md 5 근거 표시). */
@Composable
fun RnBadge(text: String, bg: Color, fg: Color) {
    Box(Modifier.background(bg, RoundedCornerShape(5.dp)).padding(horizontal = 6.dp, vertical = 1.dp)) {
        Text(text, color = fg, fontSize = 11.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
    }
}

/** Horizontal space helper. */
@Composable
fun RowScope.RnGap(w: Dp) = Spacer(Modifier.width(w))

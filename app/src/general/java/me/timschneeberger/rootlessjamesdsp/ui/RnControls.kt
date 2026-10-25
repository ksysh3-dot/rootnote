package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.runtime.State
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.background
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.unit.dp

/*
 * The small controls every screen of the general build shares, so none of them re-draws a press, a tint or a switch of
 * its own (docs/DESIGN.md 6): the press scale, the press tint and the switch.
 */

/**
 * A control being pressed shrinks to [to] (the press starts on the first frame: Seed d3 on the pressed-scale curve) and,
 * let go of, returns with a spring that carries the speed over ([RnMotion.Apple.thumb]), so a new press while it is
 * still coming back takes over where it is. Read the value while drawing (graphicsLayer), not while composing.
 */
@Composable
fun pressScale(pressed: Boolean, to: Float = 0.96f): State<Float> =
    animateFloatAsState(
        if (pressed) to else 1f,
        rn(if (pressed) RnMotion.Seed.pressIn() else RnMotion.Apple.thumb()),
        label = "pressScale",
    )

/** [pressScale] for a control with an [interaction] source that may be [enabled]. */
@Composable
fun pressScale(interaction: MutableInteractionSource, enabled: Boolean, to: Float = 0.96f): State<Float> {
    val pressed by interaction.collectIsPressedAsState()
    return pressScale(pressed && enabled, to)
}

/** A background that takes the press colour at once on touch-down and gives it back in Seed d3 (docs/DESIGN.md 6 누름). */
@Composable
fun rnPressTint(pressed: Boolean, rest: Color, press: Color): Color {
    val tint by animateColorAsState(
        if (pressed) press else rest,
        rn(if (pressed) RnMotion.instant() else RnMotion.Seed.color()),
        label = "pressTint",
    )
    return tint
}

/** [rnPressTint] for a row with an [interaction] source that may be [enabled]. */
@Composable
fun rnPressTint(interaction: MutableInteractionSource, enabled: Boolean, rest: Color, press: Color): Color {
    val pressed by interaction.collectIsPressedAsState()
    return rnPressTint(pressed && enabled, rest, press)
}

/**
 * The switch (docs/DESIGN.md 5): a 51x31 track, a 27 dp thumb at 2 / 22 dp. One progress value moves with a spring
 * ([RnMotion.Apple.thumb]) and both the thumb's place and the track's colour are taken from it while drawing, so the
 * two end together and nothing is recomposed per frame. Visual only: the row carries the switch semantics.
 */
@Composable
fun RnSwitchVisual(checked: Boolean, on: Color, off: Color, thumb: Color) {
    val t = animateFloatAsState(if (checked) 1f else 0f, rn(RnMotion.Apple.thumb()), label = "switch")
    Box(
        Modifier.size(width = 51.dp, height = 31.dp).drawBehind {
            drawRoundRect(lerp(off, on, t.value.coerceIn(0f, 1f)), cornerRadius = CornerRadius(size.height / 2f))
        }
    ) {
        Box(
            Modifier.offset(y = 2.dp).size(27.dp)
                .graphicsLayer { translationX = (2.dp + 20.dp * t.value).toPx() }
                .shadow(3.dp, CircleShape)
                .background(thumb, CircleShape)
        )
    }
}

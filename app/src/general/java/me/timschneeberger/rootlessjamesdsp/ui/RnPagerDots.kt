package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.pager.PagerState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.dp
import kotlin.math.abs

/** How many rounds a story scene plays before it rests on its key frame. */
const val RN_STORY_ROUNDS = 3f

/**
 * One page dot that follows the pager's position while it is swiped (6 dp wide, 18 dp at its own page, its colour
 * between [inactive] and [active]): the dots move with the finger instead of after it. The position is read only while
 * laying out and drawing, so a swipe recomposes nothing. With the animations off the dot jumps to the settled page.
 */
@Composable
fun PagerDot(pager: PagerState, index: Int, active: Color, inactive: Color, modifier: Modifier = Modifier) {
    val reduce = LocalRnReduceMotion.current
    fun near(): Float =
        if (reduce) (if (pager.currentPage == index) 1f else 0f)
        else (1f - abs(pager.currentPage + pager.currentPageOffsetFraction - index)).coerceIn(0f, 1f)
    Box(
        modifier
            .layout { _, _ ->
                val w = (6.dp.toPx() + 12.dp.toPx() * near()).toInt()
                val h = 6.dp.roundToPx()
                layout(w, h) {}
            }
            .drawBehind {
                drawRoundRect(lerp(inactive, active, near()), cornerRadius = CornerRadius(size.height / 2f))
            }
    )
}

/** The page dots of a pager: [count] [PagerDot]s with 6 dp between them. The one dot row of the general build. */
@Composable
fun RnPagerDots(pager: PagerState, count: Int, active: Color, inactive: Color, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        for (i in 0 until count) PagerDot(pager, i, active, inactive)
    }
}

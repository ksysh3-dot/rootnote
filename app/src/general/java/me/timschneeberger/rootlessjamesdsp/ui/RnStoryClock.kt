package me.timschneeberger.rootlessjamesdsp.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember

/**
 * The clock of an explanatory picture (the welcome, the two stories): it plays once, from 0 to its resting frame [rest],
 * when the picture's page has settled, then stands still (motion that answers a swipe, then stillness: it costs no
 * battery and a person who wants to look again taps the picture, see [replay]). A page that is not the current one
 * waits at 0, so a page swiped in never jumps backwards. With the animations off it shows the resting frame at once.
 * The value is read while drawing only, so a frame never recomposes the page. docs/DESIGN.md 6 ("그림 시계").
 */
class RnStoryClock internal constructor(val value: State<Float>, private val ticks: androidx.compose.runtime.MutableIntState) {
    /** Plays the picture again from its first frame. */
    fun replay() { ticks.intValue++ }
}

/** [cycleMs] is the length of one whole cycle (0..1); the clock runs 0 -> [rest] in `cycleMs * rest`. */
@Composable
fun rememberRnStoryClock(key: Any, active: Boolean, rest: Float, cycleMs: Int): RnStoryClock {
    val reduce = LocalRnReduceMotion.current
    val anim = remember(key) { Animatable(if (reduce) rest else 0f) }
    val ticks = remember(key) { mutableIntStateOf(0) }
    LaunchedEffect(key, active, reduce, ticks.intValue) {
        when {
            reduce -> anim.snapTo(rest)
            active -> {
                anim.snapTo(0f)
                anim.animateTo(rest, RnMotion.clock((cycleMs * rest).toInt().coerceAtLeast(1)))
            }
            else -> anim.snapTo(0f)
        }
    }
    return remember(anim, ticks) { RnStoryClock(anim.asState(), ticks) }
}

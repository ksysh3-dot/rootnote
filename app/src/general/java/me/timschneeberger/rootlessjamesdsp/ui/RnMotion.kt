package me.timschneeberger.rootlessjamesdsp.ui

import android.content.Context
import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.SpringSpec
import androidx.compose.animation.core.TweenSpec
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedContentScope
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/*
 * The one place the general build's motion is defined (docs/DESIGN.md 6, tools/check_motion.py).
 *
 *   - The finger holds the value  -> Apple: it follows at once while dragged (snap), and after it is let go a spring
 *     takes over the current value and speed.
 *   - The system changes a state  -> Seed: a fixed time and curve (Seed Design motion tokens).
 *
 * Screen files never call tween(, spring( or CubicBezierEasing( themselves; they name the kind of change instead
 * (RnMotion.Seed.color(), RnMotion.Apple.thumb()) and pass it through [rn], so one switch (the system's "remove
 * animations") makes every motion instant.
 */
object RnMotion {
    /** Seed durations d3 / d4 / d6. Nothing the person triggers by tapping runs longer than [D6]. */
    const val D3 = 150
    const val D4 = 200
    const val D6 = 300

    /** Seed Design motion tokens: a state changed by the system (colour, text, tab, dialog, page). */
    object Seed {
        /** $timing-function.easing: the functional micro motions (a tap, a focus, a colour). */
        val Easing = CubicBezierEasing(0.35f, 0f, 0.35f, 1f)

        /** $timing-function.enter: dialogs, sheets and pages coming in. */
        val Enter = CubicBezierEasing(0f, 0f, 0.15f, 1f)

        /** $timing-function.exit: dialogs, sheets and pages going away. */
        val Exit = CubicBezierEasing(0.35f, 0f, 1f, 1f)

        /** A colour (or an opacity) changing with a tap: d3. */
        fun <T> color(): TweenSpec<T> = tween(RnMotion.D3, easing = Easing)

        /** A size or position changing with a tap or a tab: [ms] (default d6), optionally after [delayMs]. */
        fun <T> move(ms: Int = RnMotion.D6, delayMs: Int = 0): TweenSpec<T> = tween(ms, delayMs, Easing)

        /** The start of a press: d3 on the pressed-scale curve. */
        fun <T> pressIn(): TweenSpec<T> = tween(RnMotion.D3, easing = Enter)

        /** Coming in (dialog, sheet, page, appearing text): at most [D6]. */
        fun <T> enter(ms: Int = RnMotion.D6, delayMs: Int = 0): TweenSpec<T> = tween(ms, delayMs, Enter)

        /** Going away (a dismissal): d4. */
        fun <T> exit(ms: Int = RnMotion.D4): TweenSpec<T> = tween(ms, easing = Exit)
    }

    /** Apple-style springs, for what a finger holds or has just let go of (they carry the current speed over). */
    object Apple {
        /** A position that settles without bouncing (damping 1.0, response about 0.4 s). */
        fun <T> settle(): SpringSpec<T> = spring(dampingRatio = 1f, stiffness = 247f)

        /** Press release, switch thumb, slider thumb scale (damping 1.0, response about 0.3 s). */
        fun <T> thumb(): SpringSpec<T> = spring(dampingRatio = 1f, stiffness = 439f)

        /** A needle or gauge following a live value (damping 0.7): it swings a little and never restarts per sample. */
        fun <T> needle(): SpringSpec<T> = spring(dampingRatio = 0.7f, stiffness = 200f)

        /** A let-go that carries speed (damping 0.8): reserved for sheets and pagers. */
        fun <T> fling(): SpringSpec<T> = spring(dampingRatio = 0.8f, stiffness = 439f)
    }

    /**
     * Two contents at one place swapping (a text that changes, a tab): both fade for [ms] and the size follows with the
     * same time and curve, so there is never a moment with nothing shown and nothing below it shakes.
     */
    fun crossFade(ms: Int): ContentTransform = ContentTransform(
        targetContentEnter = fadeIn(Seed.move(ms)),
        initialContentExit = fadeOut(Seed.move(ms)),
        sizeTransform = SizeTransform(clip = false) { _, _ -> Seed.move(ms) },
    )

    /** What a finger holds is not animated while it holds it. */
    fun <T> instant(): FiniteAnimationSpec<T> = snap()

    /** The constant-speed clock of a looping illustration (not an interface motion). */
    fun <T> clock(ms: Int): TweenSpec<T> = tween(ms, easing = LinearEasing)
}

/** True when the system animations are off: every motion snaps (docs/DESIGN.md 8). */
val LocalRnReduceMotion = staticCompositionLocalOf { false }

/** [spec], or an instant change when the system animations are off. The only way a screen uses a motion spec. */
@Composable
fun <T> rn(spec: FiniteAnimationSpec<T>): FiniteAnimationSpec<T> = if (LocalRnReduceMotion.current) snap() else spec

/** The system "animator duration scale" is 0 (accessibility: remove animations). The only place it is read. */
fun animationsOff(context: Context): Boolean = try {
    Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
} catch (_: Exception) { false }

/**
 * Provides [LocalRnReduceMotion] to [content] and keeps it current while the setting changes, so no screen or activity
 * reads the setting itself. Every top-level screen of the general build (and [RnTheme]) wraps itself in this.
 */
@Composable
fun ProvideRnMotion(content: @Composable () -> Unit) {
    val context = LocalContext.current
    var off by remember { mutableStateOf(animationsOff(context)) }
    DisposableEffect(context) {
        val resolver = context.contentResolver
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { off = animationsOff(context) }
        }
        try {
            resolver.registerContentObserver(Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, observer)
        } catch (_: Exception) { }
        off = animationsOff(context)
        onDispose { try { resolver.unregisterContentObserver(observer) } catch (_: Exception) { } }
    }
    CompositionLocalProvider(LocalRnReduceMotion provides off, content = content)
}

/** A content that swaps for another at one place: [RnMotion.crossFade] over [ms] (d3 for text, d4 for a tab), or at once. */
@Composable
fun <S> RnSwap(
    targetState: S,
    modifier: Modifier = Modifier,
    ms: Int = RnMotion.D3,
    contentAlignment: Alignment = Alignment.TopStart,
    label: String = "swap",
    content: @Composable AnimatedContentScope.(S) -> Unit,
) {
    val reduce = LocalRnReduceMotion.current
    AnimatedContent(
        targetState = targetState,
        modifier = modifier,
        transitionSpec = {
            if (reduce) ContentTransform(EnterTransition.None, ExitTransition.None, sizeTransform = null)
            else RnMotion.crossFade(ms)
        },
        contentAlignment = contentAlignment,
        label = label,
        content = content,
    )
}

package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * JamesDSP and PVB in one chain (2026-10-22): captured audio -> JamesDSP effects -> PVB (EQ v1.1, virtual bass,
 * limiter) -> output. PVB stays last because its limiter is the final speaker protection.
 *
 * Plain Kotlin (no Android types), so the host tests check the same decisions the service, the JamesDSP engine and
 * the DSP screen make:
 * - [route]: which engine(s) process a block;
 * - [sealed] / [allowed] / [output]: which JamesDSP modules are forced off while PVB processes. Sealing only changes
 *   what is sent to the native JamesDSP engine; the user's saved JamesDSP settings are never written, so they apply
 *   again as soon as PVB stops processing;
 * - [shortToFloat] / [floatToShort]: 16-bit capture runs the chain in float, so JamesDSP boosts above 0 dBFS reach
 *   the PVB limiter instead of being clipped between the two engines.
 *
 * Headroom: no extra gain stage. The whole chain is float (JamesDSP's float path does not clip and its own output
 * limiter is neutral while sealed), and PVB already applies its output gain (default -5 dB, general build at most
 * -3 dB) before its look-ahead limiter. Host measurement (tools/pvb-harness/test_jdsp_chain.py): JamesDSP +6 dB low
 * shelf and compressor in front of the PVB defaults stay below -1 dBTP, with 0.3 dB or less mean limiter gain
 * reduction per block.
 */
object JdspChain {
    /** Which engines process a block, in this order. */
    enum class Route(val jdsp: Boolean, val pvb: Boolean) {
        /** PVB not in the signal path: JamesDSP alone, exactly as before the chain existed. */
        JDSP_ONLY(true, false),
        /** PVB alone (no JamesDSP effect on, or a research mode): bit-identical to before the chain existed. */
        PVB_ONLY(false, true),
        /** JamesDSP effects first, then PVB. */
        JDSP_THEN_PVB(true, true),
    }

    /** What happens to a JamesDSP module while PVB processes. */
    enum class Policy {
        /** Forced off (output control: neutral) and shown locked. */
        SEALED,
        /** Applied before PVB, with a note on its card. */
        INFO,
        /** Applied before PVB without a note. */
        ALLOWED,
    }

    /** The JamesDSP effect modules (each has its own enable switch; the output control has none, see [output]). */
    enum class Module(val policy: Policy) {
        BASS(Policy.SEALED),         // dynamic bass boost: PVB EQ and virtual bass own the low end
        TUBE(Policy.SEALED),         // analog modelling: adds harmonics in front of the virtual bass detector
        COMPRESSOR(Policy.INFO),     // changes the levels the virtual bass reacts to
        EQ(Policy.INFO),             // adds to PVB EQ; large low boosts drive the PVB limiter
        PEQ(Policy.INFO),
        GEQ(Policy.INFO),
        CONVOLVER(Policy.ALLOWED),
        DDC(Policy.ALLOWED),
        LIVEPROG(Policy.ALLOWED),
        CROSSFEED(Policy.ALLOWED),   // mostly for headphones
        STEREO_WIDE(Policy.ALLOWED), // mostly for headphones
        REVERB(Policy.ALLOWED),
    }

    /**
     * JamesDSP limiter threshold while sealed, dB. Its limiter has no look-ahead: gain = threshold / max(threshold,
     * peak), so with +24 dB every sample below 15.8 (full scale 1.0) passes with a gain of exactly 1. PVB's
     * look-ahead limiter after it is the only limiter that acts.
     */
    const val NEUTRAL_LIMITER_DB = 24f

    /** JamesDSP output control: limiter threshold and release, post gain. */
    data class Output(val thresholdDb: Float, val releaseMs: Float, val postGainDb: Float)

    /** PVB is in the signal path (same condition as PvbController.isActive). */
    fun pvbInPath(s: PvbSettings, abActive: Boolean): Boolean = s.enabled || s.matchOnDisable || abActive

    /**
     * PVB processes audibly (its EQ, virtual bass and limiter are heard): on, and on a route it is allowed to process.
     * Matched bypass ("match loudness when off") and a route bypass (headphones with "speaker only") do not seal.
     */
    fun sealed(s: PvbSettings, speaker: Boolean): Boolean = s.enabled && (!s.speakerOnly || speaker)

    /** The module may run in JamesDSP: the user enabled it and it is not sealed. */
    fun allowed(m: Module, enabled: Boolean, sealed: Boolean): Boolean =
        enabled && !(sealed && m.policy == Policy.SEALED)

    /** At least one enabled module still runs with this seal state ("JamesDSP on" for the chain). */
    fun hasEffects(enabled: Set<Module>, sealed: Boolean): Boolean = enabled.any { allowed(it, true, sealed) }

    /** Output control sent to JamesDSP: the user's values, or 0 dB and a neutral limiter while sealed. */
    fun output(user: Output, sealed: Boolean): Output =
        if (sealed) Output(NEUTRAL_LIMITER_DB, user.releaseMs, 0f) else user

    /**
     * Route of one block. [research]: blind comparison, measurement or buzz diagnostics; their trims and recordings
     * assume the PVB engine alone, so JamesDSP stays out of the path while they run (as before the chain existed).
     */
    fun route(pvbInPath: Boolean, research: Boolean, jdspEffects: Boolean): Route = when {
        !pvbInPath -> Route.JDSP_ONLY
        research || !jdspEffects -> Route.PVB_ONLY
        else -> Route.JDSP_THEN_PVB
    }

    /** 16-bit to float, the same scale as the PVB engine's own 16-bit path (1 / 32768). */
    fun shortToFloat(src: ShortArray, dst: FloatArray, n: Int) {
        for (i in 0 until n) dst[i] = src[i] * (1f / 32768f)
    }

    /** Float to 16-bit, rounded to nearest (ties to even) and clamped, as the PVB engine's own 16-bit path. */
    fun floatToShort(src: FloatArray, dst: ShortArray, n: Int) {
        for (i in 0 until n) {
            val v = src[i] * 32768f
            dst[i] = when {
                v.isNaN() -> 0
                v >= 32767f -> 32767
                v <= -32768f -> -32768
                else -> Math.rint(v.toDouble()).toInt().toShort()
            }
        }
    }

    /** Short label of a route for logs. */
    fun label(r: Route): String = when (r) {
        Route.JDSP_ONLY -> "jamesdsp"
        Route.PVB_ONLY -> "pvb"
        Route.JDSP_THEN_PVB -> "jamesdsp>pvb"
    }
}

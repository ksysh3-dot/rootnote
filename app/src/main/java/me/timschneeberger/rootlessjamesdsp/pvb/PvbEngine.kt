package me.timschneeberger.rootlessjamesdsp.pvb

/** Index of each value in the parameter array (same order as pvb::Param in pvb_engine.h). */
object PvbParam {
    const val ENABLED = 0
    const val HP_HZ = 1
    const val LOW_HZ = 2
    const val LOW_DB = 3
    const val LOW_Q = 4
    const val HI_HZ = 5
    const val HI_DB = 6
    const val HI_Q = 7
    const val OUT_DB = 8
    const val CEIL_DB = 9
    const val REL_MS = 10
    const val RAMP_MS = 11
    const val DYN_ON = 12
    const val DYN_REF_DB = 13
    const val DYN_DOWN_RATIO = 14
    const val DYN_DOWN_MAX_DB = 15
    const val DYN_UP_RATIO = 16
    const val DYN_UP_MAX_DB = 17
    const val HS_HZ = 18
    const val HS_DB = 19
    /** Final output gate after the dry/wet mix (blind-comparison mute and headroom), dB; <= -90 = silent. */
    const val GATE_DB = 20
    /** Condition tag (integer) for [PvbEngine.openMs]. */
    const val TAG = 21
    /** Virtual bass (experimental): 1 = the algorithm [VB_ALGO] is in the path, with its latency. */
    const val VB_ON = 22
    /** Legacy IDs0-5 retained; Alpha2 reference=4, P1=6, D2=7, J2=8, oscillator=9, corrected=10. */
    const val VB_ALGO = 23
    /** Layer level re the 'faithful' level, dB; <= -90 silences the layer but keeps the algorithm and its latency. */
    const val VB_LEVEL_DB = 24
    const val FLAT = 25
    const val MATCH_HOLD = 26
    const val MATCH_SEED_DB = 27
    const val DIAGNOSTIC_SOLO = 28
    /** Experimental layer options (1 = on, default off; ignored while virtual bass is off). See pvb_layer_condition.h. */
    const val X_SMOOTH = 29   // 층 출렁임 완화 (cut only)
    const val X_RISE = 30     // 급상승 완화 (cut only)
    const val X_S1M = 31      // 배음별 단일 포락선 (S1m, P1 only, layer -2 dB)
    const val X_DENSE = 32    // 복합음 감응 세기 (up to -6 dB)
    /**
     * Developer mode ("개발자 모드", general build; see pvb_engine.h). DEV_ON = 0: every D_* value is ignored (output
     * bit-identical to the engine without them); every D_* at its default is bit-identical as well. DEV_ON also caps
     * the limiter ceiling at -1 dBTP. DEV_METER only switches the display meters ([PvbEngine.copyDevMeters]) on.
     */
    const val DEV_ON = 33
    const val DEV_METER = 34
    const val D_BOUNDARY_HZ = 35
    const val D_OUT_LO_HZ = 36
    const val D_OUT_HI_HZ = 37
    const val D_H2_DB = 38
    const val D_H3_DB = 39
    const val D_H4_DB = 40
    const val D_H5_DB = 41
    const val D_ROLLOFF_DB_OCT = 42
    const val D_SUST_DB = 43
    const val D_PERC_DB = 44
    const val D_ATTACK_MS = 45
    const val D_RELEASE_MS = 46
    /** Crosstalk cancellation ("공간감", pvb_xtc.h): XTC_MODE 0 = off (bit-identical), 1 = centre safe, 2 = full. */
    const val XTC_MODE = 47
    const val XTC_STRENGTH_DB = 48
    const val XTC_DIST_CM = 49
    const val XTC_HAT_CM = 50
    const val XTC_SPACING_CM = 51
    const val XTC_LO_HZ = 52
    const val XTC_HI_HZ = 53
    /** Speaker balance after the canceller (left louder by this, dB): 400-1500 Hz and 1.5-8 kHz. */
    const val XTC_BAL_LO_DB = 54
    const val XTC_BAL_HI_DB = 55
    const val COUNT = 56
}

/** Index of each value in the meter array (same order as pvb::Meter in pvb_engine.h). */
object PvbMeter {
    const val IN_PEAK_DB = 0
    const val OUT_PEAK_DB = 1
    const val LIM_GR_DB = 2
    const val LOW_DB_NOW = 3
    const val MIX = 4
    const val LOAD_PCT = 5
    const val SAMPLE_RATE = 6
    const val LATENCY = 7
    const val BLOCKS = 8
    const val NAN_EVENTS = 9
    const val EST_LEVEL_DB = 10
    const val EST_GR_DB = 11
    const val DYN_DB = 12
    const val DYN_LEVEL_DB = 13
    /** Virtual bass in the signal path: 0 = none; otherwise native algorithm ID + 1. */
    const val VB = 14
    const val MATCH_DB = 15
    /** Rule-based observations only; these do not control the sound. */
    const val VB_SCENE = 16
    const val VB_UNKNOWN_FRAMES = 17
    const val VB_STEADY_FRAMES = 18
    const val VB_TRANSIENT_FRAMES = 19
    const val VB_COMPLEX_FRAMES = 20
    const val VB_UPPER_BLEND = 21
    const val VB_UPPER_TARGET = 22
    const val VB_UPPER_TRANSITIONS = 23
    const val DIAGNOSTIC_SOLO_BLEND = 24
    const val DIAGNOSTIC_SOLO_EXTRA_GR_DB = 25
    /** Share of audio time since the last read in blocks where the limiter took off more than 0.5 dB, %. */
    const val LIM_ACTIVE_PCT = 26
    const val COUNT = 27
}

/** Developer-mode meter layout (same order as pvb::DevMeter in pvb_engine.h), then [RING] (dry, layer) pairs. */
object PvbDevMeter {
    const val F0 = 0
    const val H2_DB = 1          // k = 2..8 at H2_DB + k - 2
    const val DRY_BAND_DB = 8
    const val LAYER_BAND_DB = 9
    const val RING_COUNT = 10
    const val RING_BIN_MS = 11
    const val GAIN = 12
    const val BOUNDARY_HZ = 13
    const val OUT_LO_HZ = 14
    const val OUT_HI_HZ = 15
    const val FIELDS = 16
    const val RING = 512
    const val SIZE = FIELDS + 2 * RING
}

/** Index of each value in the analysis info array (same order as pvb::AnaInfo in pvb_analysis.h). */
object PvbAnaInfo {
    const val FRESH = 0
    const val LIM_GR_DB = 1
    const val EST_GR_DB = 2
    const val LOW_DB_NOW = 3
    const val MIX = 4
    const val OUT_DB = 5
    const val SAMPLE_RATE = 6
    const val DYN_DB = 7
    const val COUNT = 8

    /** Frequency of point [i] of [n] on the analysis grid (log-spaced, 20 Hz to 20 kHz). */
    fun pointHz(i: Int, n: Int): Float =
        (20.0 * Math.pow(1000.0, if (n > 1) i.toDouble() / (n - 1) else 0.0)).toFloat()
}

/**
 * Owner of one native engine instance. Processing calls come from the audio thread; parameter and meter
 * calls may come from any thread (the native side never blocks the audio thread).
 *
 * Lifetime: every call that uses the native handle holds a reference for the duration of the call
 * ([acquire]/[release], a lock-free counter). [close] drops the owner's reference; the native engine is freed by
 * whichever thread releases the last reference, so it is never freed while a processing or UI call still uses it
 * and no call ever waits for another. After close, processing passes audio through and the other calls do nothing.
 */
class PvbEngine(sampleRate: Int) : AutoCloseable {
    private val handle: Long = PvbNative.create(sampleRate)
    /** Immutable requested controls for opt-in diagnostics. Native ramp/application may lag this snapshot. */
    @Volatile var diagnosticParams: FloatArray? = null
        private set

    /** 1 = the owner's reference (until [close]); +1 for each call in flight; 0 = freed. */
    private val refs = java.util.concurrent.atomic.AtomicInteger(if (handle != 0L) 1 else 0)
    private val closed = java.util.concurrent.atomic.AtomicBoolean(false)

    init {
        check(
            PvbNative.paramCount() == PvbParam.COUNT && PvbNative.meterCount() == PvbMeter.COUNT &&
                PvbNative.anaInfoCount() == PvbAnaInfo.COUNT
        ) {
            "libpvbengine does not match PvbEngine.kt (params ${PvbNative.paramCount()}, meters " +
                "${PvbNative.meterCount()}, analysis info ${PvbNative.anaInfoCount()})"
        }
    }

    /** Takes a reference if the engine is still alive; false once it is closed (or freed). */
    private fun acquire(): Boolean {
        if (closed.get()) return false
        while (true) {
            val r = refs.get()
            if (r <= 0) return false
            if (refs.compareAndSet(r, r + 1)) return true
        }
    }

    private fun release() {
        if (refs.decrementAndGet() == 0) PvbNative.destroy(handle)
    }

    private inline fun <T> use(otherwise: T, block: (Long) -> T): T {
        if (!acquire()) return otherwise
        try {
            return block(handle)
        } finally {
            release()
        }
    }

    val isValid: Boolean
        get() = !closed.get() && refs.get() > 0

    val latencyFrames: Int
        get() = use(0) { PvbNative.latency(it) }

    fun setSampleRate(sampleRate: Int) = use(Unit) { PvbNative.setSampleRate(it, sampleRate) }

    fun setParams(values: FloatArray) {
        require(values.size == PvbParam.COUNT) { "expected ${PvbParam.COUNT} values, got ${values.size}" }
        use(Unit) { PvbNative.setParams(it, values) }
        diagnosticParams = values.copyOf()
    }

    /** Clears the engine memory and fades in; call when the engine re-enters the signal path. */
    fun reset() = use(Unit) { PvbNative.reset(it) }

    /** Interleaved stereo; [length] is the number of samples (not frames). Passes audio through once closed. */
    fun processFloat(input: FloatArray, output: FloatArray, length: Int = input.size) {
        if (!acquire()) {
            PvbNative.processFloat(0L, input, output, length)
            return
        }
        try {
            PvbNative.processFloat(handle, input, output, length)
        } finally {
            release()
        }
    }

    /** Interleaved stereo 16-bit; [length] is the number of samples (not frames). Passes audio through once closed. */
    fun processShort(input: ShortArray, output: ShortArray, length: Int = input.size) {
        if (!acquire()) {
            PvbNative.processShort(0L, input, output, length)
            return
        }
        try {
            PvbNative.processShort(handle, input, output, length)
        } finally {
            release()
        }
    }

    /** Audio owner only, immediately before/after process; no meter resets. */
    fun setDiagnosticCapture(enabled: Boolean) = use(Unit) { PvbNative.setDiagnosticCapture(it, enabled) }
    fun copyDiagnostic(layer: FloatArray, full: FloatArray, trace: FloatArray, samples: Int): Boolean = use(false) {
        PvbNative.copyDiagnostic(it, layer, full, trace, samples)
    }
    fun copyHarmonicTrace(out: FloatArray): Int = use(-1) { PvbNative.copyHarmonicTrace(it, out) }

    /** Developer-mode meters into [out] (size [PvbDevMeter.SIZE]); any thread but the audio thread. */
    fun copyDevMeters(out: FloatArray): Boolean = use(false) { PvbNative.copyDevMeters(it, out) == PvbDevMeter.SIZE }

    /** Fills [out] (size [PvbMeter.COUNT]); peak meters restart after each call. */
    fun readMeters(out: FloatArray): Boolean = use(false) {
        PvbNative.readMeters(it, out)
        true
    }

    /**
     * Milliseconds of audio processed with parameter tag [tag] while it was audible (output gate open, processed,
     * not silent); -1 if another tag is active or the engine is closed. See [PvbParam.TAG].
     */
    fun openMs(tag: Int): Int = use(-1) { PvbNative.openMs(it, tag) }

    /** Measured match gain, or NaN before any usable audio has been measured. */
    fun matchDb(): Float = use(Float.NaN) { PvbNative.matchDb(it) }

    /**
     * Live spectrum analysis of the latest audio (any thread but the audio thread). The four arrays must
     * have the same size (2..1024 points, log-spaced 20 Hz to 20 kHz, see [PvbAnaInfo.pointHz]); NaN marks
     * points with nothing to show. [dtSeconds] < 0 measures the display smoothing time with the clock.
     * Returns false when the engine is closed or the arrays do not fit.
     */
    fun analyze(
        inDb: FloatArray, outDb: FloatArray, diffDb: FloatArray, eqDb: FloatArray, info: FloatArray,
        dtSeconds: Double = -1.0,
    ): Boolean = use(false) { PvbNative.analyze(it, inDb, outDb, diffDb, eqDb, info, dtSeconds) > 0 }

    /** Drops the owner's reference; the native engine is freed when the last call using it returns. */
    override fun close() {
        if (closed.compareAndSet(false, true) && handle != 0L) release()
    }

    companion object {
        /** EQ v1.1 as tested in the blind listening rounds, plus the output limiter. */
        fun defaultParams(): FloatArray = floatArrayOf(
            1f,      // enabled
            100f,    // high-pass, Hz (LR4)
            220f, 3f, 1f,      // low-mid bell: Hz, dB, Q
            4500f, -3f, 0.6f,  // treble bell: Hz, dB, Q
            -5f,     // output gain, dB
            -1f,     // limiter ceiling, dBTP
            60f,     // limiter release, ms
            20f,     // glide time, ms
            0f,      // dynamic low-mid off
            -30f,    // dynamic reference level (as the phone limiter sees it), dBFS
            0.5f, 0f,      // above the reference: ratio, max dB taken back (0 = off)
            0.19f, 2f,     // below the reference: ratio, max dB added
            2500f, 0f,     // treble tilt: high shelf corner, gain (0 = off)
            0f,      // final output gate, dB (0 = open)
            0f,      // condition tag (blind comparison)
            0f, 0f, 0f,    // virtual bass: off, hpv, 0 dB
            0f, 0f, -6f,   // flat bypass off (controller selects it), match running, initial estimate
            0f,           // generated-layer diagnostic monitor off
            0f, 0f, 0f, 0f,   // experimental layer options off: smooth, rise, S1m, dense
            0f, 0f,           // developer mode off, its meters off
            190f, 150f, 600f, // generator input edge, output band (the model's own values)
            0f, 0f, 0f, 0f,   // harmonic offsets k = 2, 3, 4, 5+
            0f,               // upper roll-off offset, dB/oct
            0f, 0f,           // sustained / percussive path, dB
            32f / 3f, 32f,    // attack (2 hops), release (6 hops), ms
            0f, -6f, 40f, 57f, // crosstalk cancellation off; gentle, 40 cm, standard head (hat 57 cm)
            15.5f, 400f, 8000f, // speaker spacing, feedback band
            0f, 0f,             // speaker balance (speakers taken as equal)
        )
    }
}


package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.sin

/**
 * Developer-mode test sounds, generated in the app (no files): they replace the captured music in the service's audio
 * loop, so they go through the same engine and the same speaker path ([DevTestSound.render], called by
 * RootlessAudioProcessorService). Pure Kotlin; deterministic; no allocation while rendering.
 *
 * Levels: peaks about -10 dBFS (tone and sweep -12 dBFS), so the engine's limiter is not what the user hears.
 */
enum class DevTestKind {
    TONE, SWEEP, KICK, BASS_CHORD,
    /** Spatial "좌우 맞추기" (SpatialBalance): band noise in both channels, 400-1500 Hz / 1.5-8 kHz, -24 dBFS RMS. */
    XTC_BAND_LO, XTC_BAND_HI,
    /** Spatial self-measurement: a log sweep 300 Hz-10 kHz in one channel only (3 s, then 1.5 s silence), -18 dBFS. */
    XTC_SWEEP_L, XTC_SWEEP_R,
    /**
     * "저음 맞추기" (BassFitSession): [FIT_SILENCE] keeps the music out between questions; [FIT_REF] the room check's
     * reference, band noise 56-560 Hz at -22 dBFS RMS; [FIT_IFC_1] / [FIT_IFC_2] / [FIT_IFC_0] one two-interval trial,
     * a tone burst at the requested frequency in the first, the second or neither interval (then silence);
     * [FIT_LOW] a 3.6 s sustained bass line (41-73 Hz) under a soft chord, [FIT_MID] 3.6 s of notes 4-27 % above the
     * requested frequency (the generator edge), both then silence.
     */
    FIT_SILENCE, FIT_REF, FIT_IFC_1, FIT_IFC_2, FIT_IFC_0, FIT_LOW, FIT_MID,
}

class DevTestSignal {
    private var kind: DevTestKind? = null
    private var toneHz = 55.0
    private var t = 0L            // frames since the sound started
    private var sr = 48000
    private val phase = DoubleArray(4)

    /** Restarts with [kind] (null = silence). */
    fun set(kind: DevTestKind?, toneHz: Double) {
        this.kind = kind
        this.toneHz = toneHz
        t = 0
        phase.fill(0.0)
        rng = 0x2545F4914F6CDD1DL
        designBand()
    }

    private val left get() = kind != DevTestKind.XTC_SWEEP_R
    private val right get() = kind != DevTestKind.XTC_SWEEP_L

    /** Fills [frames] stereo frames of [out] (interleaved, from index 0) at [sampleRate]. */
    fun render(out: FloatArray, frames: Int, sampleRate: Int) {
        if (sampleRate != sr) { sr = sampleRate.coerceIn(8000, 192000); t = 0; designBand() }
        val l = left
        val r = right
        for (n in 0 until frames) {
            val v = next().toFloat()
            out[2 * n] = if (l) v else 0f
            out[2 * n + 1] = if (r) v else 0f
        }
    }

    fun renderShort(out: ShortArray, frames: Int, sampleRate: Int) {
        if (sampleRate != sr) { sr = sampleRate.coerceIn(8000, 192000); t = 0; designBand() }
        val l = left
        val r = right
        for (n in 0 until frames) {
            val v = (next() * 32767.0).coerceIn(-32768.0, 32767.0).toInt().toShort()
            out[2 * n] = if (l) v else 0
            out[2 * n + 1] = if (r) v else 0
        }
    }

    // ---- spatial calibration signals: band noise (xorshift white noise through a 4-pole band-pass) and sweeps
    private var rng = 0x2545F4914F6CDD1DL
    private val bq = DoubleArray(4 * 5)      // two high-pass + two low-pass biquads: b0 b1 b2 a1 a2
    private val bz = DoubleArray(4 * 2)
    private var bandGain = 1.0

    private fun designBand() {
        val (lo, hi) = when (kind) {
            DevTestKind.XTC_BAND_LO -> 400.0 to 1500.0
            DevTestKind.XTC_BAND_HI -> 1500.0 to 8000.0
            DevTestKind.FIT_REF -> 56.0 to 560.0
            else -> return
        }
        for (i in 0 until 4) {
            val hp = i < 2
            val f0 = if (hp) lo else hi
            val w = 2 * PI * f0 / sr
            val al = sin(w) / (2 * 0.7071067811865476)
            val cw = cos(w)
            val a0 = 1 + al
            val o = 5 * i
            if (hp) { bq[o] = (1 + cw) / 2 / a0; bq[o + 1] = -(1 + cw) / a0; bq[o + 2] = (1 + cw) / 2 / a0 }
            else { bq[o] = (1 - cw) / 2 / a0; bq[o + 1] = (1 - cw) / a0; bq[o + 2] = (1 - cw) / 2 / a0 }
            bq[o + 3] = -2 * cw / a0
            bq[o + 4] = (1 - al) / a0
        }
        bz.fill(0.0)
        // white noise of RMS 1 keeps sqrt(band / (sr / 2)) of its power in the band
        bandGain = (if (kind == DevTestKind.FIT_REF) FIT_REF_RMS else BAND_RMS) / kotlin.math.sqrt((hi - lo) / (sr / 2.0))
    }

    private fun white(): Double {
        rng = rng xor (rng shl 13); rng = rng xor (rng ushr 7); rng = rng xor (rng shl 17)
        // uniform in [-1, 1): RMS 1/sqrt(3)
        return ((rng ushr 11).toDouble() / (1L shl 53).toDouble() * 2.0 - 1.0) * 1.7320508075688772
    }

    private fun band(): Double {
        var x = white()
        for (i in 0 until 4) {
            val o = 5 * i
            val z = 2 * i
            val y = bq[o] * x + bz[z]
            bz[z] = bq[o + 1] * x - bq[o + 3] * y + bz[z + 1]
            bz[z + 1] = bq[o + 2] * x - bq[o + 4] * y
            x = y
        }
        return x * bandGain
    }

    private fun xtcSweep(time: Double): Double {
        val x = time % XTC_SWEEP_PERIOD
        if (x >= XTC_SWEEP_S) return 0.0
        val k = ln(XTC_SWEEP_HI / XTC_SWEEP_LO)
        val ph = 2 * PI * XTC_SWEEP_LO * XTC_SWEEP_S / k * (exp(k * x / XTC_SWEEP_S) - 1)
        val fade = minOf(1.0, x / 0.02, (XTC_SWEEP_S - x) / 0.02)
        return XTC_SWEEP_AMP * fade * sin(ph)
    }

    /** One mono sample. */
    fun next(): Double {
        val time = t.toDouble() / sr
        t++
        return when (kind) {
            null -> 0.0
            DevTestKind.TONE -> tone(time)
            DevTestKind.SWEEP -> sweep(time)
            DevTestKind.KICK -> kick(time)
            DevTestKind.BASS_CHORD -> bassChord(time)
            DevTestKind.XTC_BAND_LO, DevTestKind.XTC_BAND_HI, DevTestKind.FIT_REF -> band()
            DevTestKind.XTC_SWEEP_L, DevTestKind.XTC_SWEEP_R -> xtcSweep(time)
            DevTestKind.FIT_SILENCE, DevTestKind.FIT_IFC_0 -> 0.0
            DevTestKind.FIT_IFC_1 -> ifcTone(time, IFC_LEAD_S)
            DevTestKind.FIT_IFC_2 -> ifcTone(time, IFC_LEAD_S + IFC_LEN_S + IFC_GAP_S)
            DevTestKind.FIT_LOW -> fitLow(time)
            DevTestKind.FIT_MID -> fitMid(time)
        }
    }

    /** Raised-cosine edges of [fade] s on a note of [len] s at x s into it (0 outside). */
    private fun noteEnv(x: Double, len: Double, fade: Double): Double = when {
        x < 0 || x >= len -> 0.0
        x < fade -> 0.5 - 0.5 * cos(PI * x / fade)
        x > len - fade -> 0.5 - 0.5 * cos(PI * (len - x) / fade)
        else -> 1.0
    }

    // Two-interval trial: one burst of [IFC_LEN_S] starting at [start], 40 ms raised-cosine edges (no click to hear).
    private fun ifcTone(time: Double, start: Double): Double {
        val env = noteEnv(time - start, IFC_LEN_S, 0.04)
        return if (env == 0.0) 0.0 else FIT_TONE_AMP * env * sin(advance(0, toneHz))
    }

    // E1 A1 D2 G1, 0.9 s each, bass with a little second harmonic under a soft chord (Em Am Dm G); once, then silence.
    private fun fitLow(time: Double): Double {
        if (time >= CLIP_S) return 0.0
        val i = (time / FIT_NOTE_S).toInt().coerceIn(0, 3)
        val x = time - i * FIT_NOTE_S
        if (x < 1.0 / sr) { phase[0] = 0.0 }
        val env = noteEnv(x, FIT_NOTE_S, 0.03)
        val bass = FIT_BASS_AMP * env * (sin(advance(0, FIT_LOW_NOTES[i])) + 0.3 * sin(2 * phase[0]))
        var chord = 0.0
        for (j in 0 until 3) chord += sin(advance(1 + j, FIT_CHORDS[i][j]))
        return bass + CHORD_AMP * env * chord
    }

    // Four notes 4-27 % above the requested frequency (the band between the generator edge and 1.3 times it).
    private fun fitMid(time: Double): Double {
        if (time >= CLIP_S) return 0.0
        val i = (time / FIT_NOTE_S).toInt().coerceIn(0, 3)
        val x = time - i * FIT_NOTE_S
        if (x < 1.0 / sr) { phase[0] = 0.0 }
        val env = noteEnv(x, FIT_NOTE_S, 0.03)
        return FIT_BASS_AMP * env * (sin(advance(0, toneHz * FIT_MID_RATIOS[i])) + 0.25 * sin(2 * phase[0]))
    }

    private fun advance(i: Int, hz: Double): Double {
        phase[i] += 2 * PI * hz / sr
        if (phase[i] > 2 * PI) phase[i] -= 2 * PI
        return phase[i]
    }

    /** Raised-cosine gate: [on] seconds out of each [period], 20 ms fades. */
    private fun gate(time: Double, on: Double, period: Double, fade: Double = 0.02): Double {
        val x = time % period
        return when {
            x >= on -> 0.0
            x < fade -> 0.5 - 0.5 * cos(PI * x / fade)
            x > on - fade -> 0.5 - 0.5 * cos(PI * (on - x) / fade)
            else -> 1.0
        }
    }

    // Single bass tone (40 / 55 / 80 Hz): 2 s on, 0.6 s off, so both the steady harmonics and the tail show.
    private fun tone(time: Double): Double = TONE_AMP * gate(time, 2.0, 2.6) * sin(advance(0, toneHz))

    // Slow logarithmic sweep 30 -> 200 Hz in 8 s, 0.5 s pause, repeat.
    private fun sweep(time: Double): Double {
        val x = time % SWEEP_PERIOD
        if (x >= SWEEP_S) { phase[0] = 0.0; return 0.0 }
        val f = SWEEP_LO * exp(ln(SWEEP_HI / SWEEP_LO) * x / SWEEP_S)
        return TONE_AMP * gate(time, SWEEP_S, SWEEP_PERIOD) * sin(advance(0, f))
    }

    // Kick every 0.5 s: pitch 150 -> 50 Hz (30 ms), decay 180 ms, 0.45 s long.
    private fun kick(time: Double): Double {
        val x = time % 0.5
        if (x < 1.0 / sr) phase[0] = 0.0
        if (x >= 0.45) return 0.0
        val f = 50.0 + 100.0 * exp(-x / 0.03)
        val env = exp(-x / 0.18) * (if (x < 0.002) x / 0.002 else 1.0) * (if (x > 0.42) (0.45 - x) / 0.03 else 1.0)
        return KICK_AMP * env * sin(advance(0, f))
    }

    // Bass line (A1 F1 C2 G1, a plucked note every 0.5 s) under a soft chord (Am F C G), 2 s per bar.
    private fun bassChord(time: Double): Double {
        val bar = ((time / 2.0).toInt()) % 4
        val inNote = time % 0.5
        val bassEnv = exp(-inNote / 0.35) * (if (inNote < 0.005) inNote / 0.005 else 1.0) *
            (if (inNote > 0.48) (0.5 - inNote) / 0.02 else 1.0)
        val bass = BASS_AMP * bassEnv * (sin(advance(0, BASS[bar])) + 0.25 * sin(2 * phase[0]))
        val inBar = time % 2.0
        val pad = gate(inBar, 2.0, 2.0, 0.08)
        var chord = 0.0
        for (j in 0 until 3) chord += sin(advance(1 + j, CHORDS[bar][j]))
        return bass + CHORD_AMP * pad * chord
    }

    companion object {
        const val TONE_AMP = 0.25          // -12 dBFS
        const val BAND_RMS = 0.063         // -24 dBFS RMS band noise
        const val XTC_SWEEP_AMP = 0.125    // -18 dBFS
        const val XTC_SWEEP_LO = 300.0
        const val XTC_SWEEP_HI = 10000.0
        const val XTC_SWEEP_S = 3.0
        const val XTC_SWEEP_PERIOD = 4.5
        const val KICK_AMP = 0.32
        const val BASS_AMP = 0.24
        const val CHORD_AMP = 0.035
        const val SWEEP_LO = 30.0
        const val SWEEP_HI = 200.0
        const val SWEEP_S = 8.0
        const val SWEEP_PERIOD = 8.5
        val TONE_CHOICES = doubleArrayOf(40.0, 55.0, 80.0)
        // "저음 맞추기"
        const val FIT_REF_RMS = 0.08       // -22 dBFS RMS band noise
        const val FIT_TONE_AMP = 0.18      // -15 dBFS peak
        const val FIT_BASS_AMP = 0.2
        /** Two-interval trial: interval 1 at [IFC_LEAD_S], interval 2 [IFC_LEN_S] + [IFC_GAP_S] later. */
        const val IFC_LEAD_S = 0.3
        const val IFC_LEN_S = 0.5
        const val IFC_GAP_S = 0.5
        const val IFC_END_S = IFC_LEAD_S + 2 * IFC_LEN_S + IFC_GAP_S
        const val FIT_NOTE_S = 0.9
        const val CLIP_S = 4 * FIT_NOTE_S
        private val FIT_LOW_NOTES = doubleArrayOf(41.2, 55.0, 73.42, 49.0)
        private val FIT_CHORDS = arrayOf(
            doubleArrayOf(164.81, 196.0, 246.94), doubleArrayOf(220.0, 261.63, 329.63),
            doubleArrayOf(146.83, 174.61, 220.0), doubleArrayOf(196.0, 246.94, 293.66),
        )
        private val FIT_MID_RATIOS = doubleArrayOf(1.04, 1.11, 1.19, 1.27)
        private val BASS = doubleArrayOf(55.0, 43.65, 65.41, 49.0)
        private val CHORDS = arrayOf(
            doubleArrayOf(220.0, 261.63, 329.63), doubleArrayOf(174.61, 220.0, 261.63),
            doubleArrayOf(261.63, 329.63, 392.0), doubleArrayOf(196.0, 246.94, 293.66),
        )
    }
}

/**
 * The test sound playing now (developer-mode screen -> audio thread). [request] is read once per block by the audio
 * thread ([render]); the screen calls [stop] whenever it leaves (onStop), so a test sound never outlives the screen.
 */
object DevTestSound {
    data class Request(val kind: DevTestKind, val toneHz: Double, val serial: Int)

    @Volatile var request: Request? = null
        private set
    private var serial = 0
    private val signal = DevTestSignal()
    private var playingSerial = -1

    val playing: Boolean get() = request != null

    fun start(kind: DevTestKind, toneHz: Double = 55.0) {
        request = Request(kind, toneHz, ++serial)
    }

    fun stop() {
        request = null
    }

    /** Audio thread: replaces [frames] captured frames with the test sound. False (buffer untouched) when none plays. */
    fun render(buffer: FloatArray, frames: Int, sampleRate: Int): Boolean {
        val r = sync() ?: return false
        signal.render(buffer, frames, sampleRate)
        return r
    }

    fun render(buffer: ShortArray, frames: Int, sampleRate: Int): Boolean {
        val r = sync() ?: return false
        signal.renderShort(buffer, frames, sampleRate)
        return r
    }

    private fun sync(): Boolean? {
        val r = request ?: run { playingSerial = -1; return null }
        if (r.serial != playingSerial) {
            signal.set(r.kind, r.toneHz)
            playingSerial = r.serial
        }
        return true
    }
}

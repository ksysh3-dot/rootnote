package me.timschneeberger.rootlessjamesdsp.devmode

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.BassFitSession
import me.timschneeberger.rootlessjamesdsp.pvb.BassFitSettings
import me.timschneeberger.rootlessjamesdsp.pvb.CheckRound
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSignal
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
import me.timschneeberger.rootlessjamesdsp.pvb.FitLatency
import me.timschneeberger.rootlessjamesdsp.pvb.FitMaterial
import me.timschneeberger.rootlessjamesdsp.pvb.FitPrompt
import me.timschneeberger.rootlessjamesdsp.pvb.FitResult
import me.timschneeberger.rootlessjamesdsp.pvb.FitVariant
import me.timschneeberger.rootlessjamesdsp.pvb.FloorStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.NoiseGate
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import java.security.SecureRandom
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * "저음 맞추기" (bass fit, docs/BASS_FIT_PLAN.md), developer mode. The questions come from [BassFitSession]; this
 * screen plays them, listens to the room and keeps the conditions fixed:
 *
 * - Room check (strict): 3 s of the room, then the reference ([DevTestKind.FIT_REF]) through the phone microphone;
 *   [NoiseGate.judge]. Failing (or no microphone): "주변이 시끄러워서 …" with [조용한 곳에서 다시] [그래도 진행];
 *   proceeding marks the result noisy. The same recording gives the latency ([FitLatency]).
 * - Step 1 trials: the microphone keeps recording; the silent interval of each trial is checked against the room
 *   ([NoiseGate.disturbed]) and a disturbed trial is played again without counting.
 * - Fixed volume and route: a volume change, another output or the engine stopping pauses the test (the sound
 *   stops); it goes on, repeating the current question, when they are back.
 * - Everything plays through the engine with JamesDSP held out ([PvbRuntime.calibrating]) and the test settings as
 *   the engine's temporary override ([BassFitSettings]); between questions [DevTestKind.FIT_SILENCE] keeps the music
 *   out. The final check plays the listener's music with JamesDSP back in.
 * - A new seed every run ([SecureRandom]): the order of the questions and the A/B/X sides differ each time; the seed
 *   is shown with the result (시험 코드) so a run can be replayed.
 *
 * Nothing is stored before "새 설정 저장": it writes the developer values ([FitResult.applyTo]) and keeps the values
 * before it, so "맞추기 전으로 되돌리기" can put them back. Leaving the screen stops everything and stores nothing.
 */
class BassFitActivity : RnActivity() {
    private lateinit var prefs: SharedPreferences
    private lateinit var flags: SharedPreferences
    private val main = Handler(Looper.getMainLooper())
    private var ui by mutableStateOf(FitUi())

    private var session: BassFitSession? = null
    private var check: CheckRound? = null
    private var mic: FitMic? = null
    /** Changes whenever what plays changes: a scheduled step of an older sound sees a stale token and does nothing. */
    private var token = 0
    private var latencyS = FitLatency.TYPICAL_S
    private var roomBands: DoubleArray? = null
    private var startVolume = -1
    private var oldSettings: PvbSettings? = null
    private var newSettings: PvbSettings? = null
    private var newValues: FloatArray? = null

    private val statusListener: () -> Unit = { main.post { checkPause() } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!PvbBuild.general) { finish(); return }
        prefs = getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        flags = PvbGeneral.flags(this)
        ui = introState()
        setRnContent { BassFitScreen(ui, actions) }
    }

    override fun onStart() {
        super.onStart()
        if (!::prefs.isInitialized) return
        PvbRuntime.addStatusListener(statusListener)
        ui = ui.copy(ready = engineReady())
    }

    override fun onStop() {
        if (::prefs.isInitialized) {
            PvbRuntime.removeStatusListener(statusListener)
            stopAll()
            // a run can't go on after leaving: nothing was stored, start again from the beginning
            if (ui.screen != FitScreen.INTRO && ui.screen != FitScreen.DONE) ui = introState()
        }
        super.onStop()
    }

    // ------------------------------------------------------------------------------------------------ helpers

    private fun engineReady(): Boolean {
        val st = PvbRuntime.status
        return BaseAudioProcessorService.activeServices > 0 && st.processing && st.speaker && !PvbRuntime.abActive
    }

    private fun stored(): PvbSettings = PvbSettings.load(prefs)

    private fun introState(): FitUi = FitUi(
        ready = engineReady(),
        lastRecord = flags.getString(KEY_FIT_RECORD, null),
        canRestore = flags.getString(KEY_FIT_BEFORE, null) != null,
    )

    /** Ends what plays and records; the stored settings and JamesDSP play again. Stores nothing. */
    private fun stopAll() {
        token++
        DevTestSound.stop()
        PvbRuntime.setDevOverride(null)
        PvbRuntime.calibrating = false
        mic?.stop()
        mic = null
    }

    /** Silence (keeps the music out) with the settings of [v]. */
    private fun hold(v: FitVariant) {
        PvbRuntime.calibrating = true
        PvbRuntime.setDevOverride(BassFitSettings.of(stored(), v))
        DevTestSound.start(DevTestKind.FIT_SILENCE)
    }

    private fun later(delayS: Double, block: () -> Unit) {
        val t = token
        main.postDelayed({ if (t == token && !isFinishing) block() }, (delayS * 1000).toLong())
    }

    private fun volumeText(): String {
        val st = PvbRuntime.status
        return getString(R.string.fit_volume, startVolume.coerceAtLeast(0), st.volumeMax)
    }

    // ------------------------------------------------------------------------------------------------ pause

    private fun pauseReason(): FitPause? {
        val st = PvbRuntime.status
        return when {
            BaseAudioProcessorService.activeServices <= 0 || !st.processing || PvbRuntime.abActive -> FitPause.ENGINE
            !st.speaker -> FitPause.ROUTE
            startVolume >= 0 && st.volumeIndex != startVolume -> FitPause.VOLUME
            else -> null
        }
    }

    private fun checkPause() {
        if (ui.screen == FitScreen.INTRO || ui.screen == FitScreen.DONE) { ui = ui.copy(ready = engineReady()); return }
        if (ui.screen != FitScreen.ROOM && ui.screen != FitScreen.TEST && ui.screen != FitScreen.CHECK) return
        val reason = pauseReason()
        if (reason == ui.paused) return
        if (reason != null) {
            token++
            if (ui.screen == FitScreen.CHECK) PvbRuntime.setDevOverride(oldSettings) else DevTestSound.start(DevTestKind.FIT_SILENCE)
            ui = ui.copy(paused = reason, playing = null, volumeText = volumeText())
        } else {
            ui = ui.copy(paused = null)
            when (ui.screen) {
                FitScreen.ROOM -> roomCheck()
                FitScreen.TEST -> present()           // the current question again
                FitScreen.CHECK -> playCheckSide(ui.checkSide)
                else -> Unit
            }
        }
    }

    // ------------------------------------------------------------------------------------------------ start, room

    private fun start() {
        if (!engineReady()) { ui = ui.copy(ready = false); return }
        stopAll()
        val st = PvbRuntime.status
        startVolume = st.volumeIndex
        val seed = SecureRandom().nextLong()
        session = BassFitSession(seed, stored().vbLevelDb.toDouble())
        latencyS = FitLatency.TYPICAL_S
        roomBands = null
        ui = FitUi(screen = FitScreen.ROOM, seedText = seedText(seed), volumeText = volumeText())
        hold(FitVariant.RAW)
        mic = if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
            FitMic.open(getSystemService(AudioManager::class.java)) else null
        if (mic == null) {
            ui = ui.copy(screen = FitScreen.ROOM_WARN, verdict = NoiseGate.judge(null, null, FS.toDouble()))
            return
        }
        roomCheck()
    }

    /** 0.5 s settle, 3 s of the room, 2.7 s of the reference; then judge (off the main thread). */
    private fun roomCheck() {
        val m = mic ?: return
        token++
        hold(FitVariant.RAW)
        ui = ui.copy(screen = FitScreen.ROOM, roomPhase = 0, progress = 0f)
        var roomFrom = 0L
        var refFrom = 0L
        later(0.5) { roomFrom = m.frames; ui = ui.copy(progress = 0.05f) }
        for (k in 1..5) later(0.5 + 0.6 * k) { ui = ui.copy(progress = 0.05f + 0.09f * k) }
        later(3.6) {
            DevTestSound.start(DevTestKind.FIT_REF)
            refFrom = m.frames
            ui = ui.copy(roomPhase = 1, progress = 0.55f)
        }
        for (k in 1..4) later(3.6 + 0.6 * k) { ui = ui.copy(progress = 0.55f + 0.09f * k) }
        later(6.4) {
            DevTestSound.start(DevTestKind.FIT_SILENCE)
            ui = ui.copy(roomPhase = 2, progress = 1f)
            val t = token
            Thread({
                val fs = FS.toDouble()
                val room = m.copy(roomFrom, (3.0 * fs).toInt())
                val around = m.copy(refFrom - (0.5 * fs).toLong(), (2.6 * fs).toInt())
                val onset = around?.let { FitLatency.onsetFrame(it, fs, (0.5 * fs).toInt()) }
                val lat = onset?.let { (it - 0.5 * fs) / fs } ?: FitLatency.TYPICAL_S
                val sig = m.copy(refFrom + ((lat + 0.4) * fs).toLong(), (1.8 * fs).toInt())
                val verdict = NoiseGate.judge(room, sig, fs)
                val bands = room?.let { NoiseGate.bandLevels(it, fs, NoiseGate.TEST_BANDS) }
                main.post {
                    if (t != token || isFinishing) return@post
                    latencyS = lat
                    roomBands = bands
                    if (verdict.pass) {
                        ui = ui.copy(verdict = verdict)
                        beginTest()
                    } else ui = ui.copy(screen = FitScreen.ROOM_WARN, verdict = verdict)
                }
            }, "bass-fit-room").start()
        }
    }

    private fun beginTest() {
        ui = ui.copy(screen = FitScreen.TEST)
        present()
    }

    // ------------------------------------------------------------------------------------------------ questions

    /** Shows the session's current question; step 1 trials and break-up clips play by themselves. */
    private fun present() {
        val s = session ?: return
        token++
        val p = s.prompt
        if (p is FitPrompt.Done) { finishTest(); return }
        ui = ui.copy(step = s.step, prompt = p, heard = emptySet(), playing = null, answerable = false)
        when (p) {
            is FitPrompt.Floor -> { hold(FitVariant.RAW); later(0.4) { playTrial(p) } }
            is FitPrompt.Buzz -> { hold(p.variant); later(0.3) { playClip("C") } }
            is FitPrompt.Abx -> hold(p.a)
            is FitPrompt.Prefer -> hold(p.a)
            else -> DevTestSound.start(DevTestKind.FIT_SILENCE)
        }
    }

    private fun playTrial(p: FitPrompt.Floor) {
        token++
        hold(FitVariant.RAW)
        val trial = p.trial
        val kind = when (trial) {
            is FloorStaircase.Trial.Catch -> DevTestKind.FIT_IFC_0
            is FloorStaircase.Trial.Tone -> if (trial.inFirst) DevTestKind.FIT_IFC_1 else DevTestKind.FIT_IFC_2
        }
        val hz = (trial as? FloorStaircase.Trial.Tone)?.hz ?: 100.0
        val mark = mic?.frames
        DevTestSound.start(kind, hz)
        ui = ui.copy(playing = null, answerable = false, disturbed = false)
        val i1 = DevTestSignal.IFC_LEAD_S
        val i2 = i1 + DevTestSignal.IFC_LEN_S + DevTestSignal.IFC_GAP_S
        val len = DevTestSignal.IFC_LEN_S
        later(latencyS + i1) { ui = ui.copy(playing = "1") }
        later(latencyS + i1 + len) { ui = ui.copy(playing = null) }
        later(latencyS + i2) { ui = ui.copy(playing = "2") }
        later(latencyS + i2 + len) { ui = ui.copy(playing = null) }
        later(latencyS + DevTestSignal.IFC_END_S + 0.2) {
            DevTestSound.start(DevTestKind.FIT_SILENCE)
            val silent = when (trial) {
                is FloorStaircase.Trial.Catch -> listOf(i1, i2)
                is FloorStaircase.Trial.Tone -> listOf(if (trial.inFirst) i2 else i1)
            }
            if (mark != null && disturbed(mark, silent)) {
                // a noise in the silent interval: the trial doesn't count, play it again
                ui = ui.copy(disturbed = true)
                later(1.2) { playTrial(p) }
            } else ui = ui.copy(answerable = true, heard = setOf("T"))
        }
    }

    private fun disturbed(mark: Long, starts: List<Double>): Boolean {
        val m = mic ?: return false
        val bands = roomBands ?: return false
        val fs = FS.toDouble()
        return starts.any { st ->
            val from = mark + ((latencyS + st + 0.08) * fs).toLong()
            val w = m.copy(from, ((DevTestSignal.IFC_LEN_S - 0.16) * fs).toInt()) ?: return@any false
            NoiseGate.disturbed(w, fs, bands)
        }
    }

    /** A, B, X or C (the break-up clip): the clip from the start with that side's settings. */
    private fun playClip(label: String) {
        val p = ui.prompt ?: return
        val (variant, material, toneHz) = when (p) {
            is FitPrompt.Abx -> Triple(when (label) { "A" -> p.a; "B" -> p.b; else -> if (p.xIsA) p.a else p.b }, p.material, p.toneHz)
            is FitPrompt.Prefer -> Triple(if (label == "A") p.a else p.b, p.material, p.toneHz)
            is FitPrompt.Buzz -> Triple(p.variant, FitMaterial.LOW, 0.0)
            else -> return
        }
        token++
        hold(variant)
        ui = ui.copy(playing = label)
        // the engine takes the new settings first (its parameter ramps), then the clip starts from its beginning
        later(0.2) {
            DevTestSound.start(if (material == FitMaterial.MID) DevTestKind.FIT_MID else DevTestKind.FIT_LOW, toneHz)
            later(DevTestSignal.CLIP_S + latencyS) {
                DevTestSound.start(DevTestKind.FIT_SILENCE)
                val heard = ui.heard + label
                ui = ui.copy(playing = null, heard = heard, answerable = answerable(p, heard))
            }
        }
    }

    private fun answerable(p: FitPrompt, heard: Set<String>): Boolean = when (p) {
        is FitPrompt.Abx -> "X" in heard
        is FitPrompt.Prefer -> "A" in heard && "B" in heard
        is FitPrompt.Buzz -> "C" in heard
        else -> true
    }

    private fun answered(block: (BassFitSession) -> Unit) {
        val s = session ?: return
        if (!ui.answerable || ui.paused != null) return
        block(s)
        present()
    }

    // ------------------------------------------------------------------------------------------------ result, check, save

    private fun finishTest() {
        val s = session ?: return
        token++
        DevTestSound.stop()
        PvbRuntime.setDevOverride(null)
        PvbRuntime.calibrating = false
        mic?.stop(); mic = null
        val r = s.result
        val cur = DevParams.read(stored())
        val next = r.applyTo(cur)
        newValues = next
        ui = ui.copy(screen = FitScreen.RESULT, result = r, prompt = null, playing = null, paused = null,
            current = cur, proposed = next, changes = (cur.indices).any { DevParams.ALL[it].indexOf(cur[it]) != DevParams.ALL[it].indexOf(next[it]) },
            vbAlgo = stored().vbAlgo)
    }

    private fun startCheck() {
        val s = session ?: return
        val values = newValues ?: return
        val st = stored()
        oldSettings = st
        newSettings = DevParams.apply(st, values).copy(devOn = true)
        check = CheckRound(s.seed xor CHECK_SALT)
        ui = ui.copy(screen = FitScreen.CHECK, checkNumber = 1, checkTrials = check!!.trials, checkSide = 1)
        PvbRuntime.calibrating = false
        DevTestSound.stop()                 // the listener's own music
        playCheckSide(1)
    }

    private fun playCheckSide(side: Int) {
        val c = check ?: return
        val playNew = (side == 1) == c.newIsFirst
        PvbRuntime.setDevOverride(if (playNew) newSettings else oldSettings)
        ui = ui.copy(checkSide = side)
    }

    private fun answerCheck(a: CheckRound.Answer) {
        val c = check ?: return
        if (ui.paused != null) return
        c.answer(a)
        if (c.done) {
            PvbRuntime.setDevOverride(null)
            ui = ui.copy(screen = FitScreen.SAVE, checkNew = c.newPicked, checkOld = c.oldPicked, checkSame = c.same)
        } else {
            ui = ui.copy(checkNumber = c.number + 1)
            playCheckSide(1)
        }
    }

    private fun skipCheck() {
        PvbRuntime.setDevOverride(null)
        ui = ui.copy(screen = FitScreen.SAVE, checkNew = -1)
    }

    private fun save() {
        val values = newValues ?: return
        val r = ui.result ?: return
        val before = DevParams.read(stored())
        val e = prefs.edit()
        DevParams.write(values, { k, v -> e.putFloat(k, v) }, { k, v -> e.putBoolean(k, v) })
        e.apply()
        val f = flags.edit().putString(KEY_FIT_BEFORE, before.joinToString(",")).putString(KEY_FIT_RECORD, record(r))
        r.floor?.let { f.putFloat(KEY_FIT_FLOOR_HZ, it.speakerFloorHz.toFloat()) }
        f.apply()
        stopAll()
        ui = ui.copy(screen = FitScreen.DONE)
    }

    private fun restoreBefore() {
        val raw = flags.getString(KEY_FIT_BEFORE, null) ?: return
        val v = raw.split(",").mapNotNull { it.trim().toFloatOrNull() }
        // values saved by an older version are shorter: the values added since keep their current value
        val cur = DevParams.read(stored())
        val values = FloatArray(cur.size) { if (it < v.size) v[it] else cur[it] }
        val e = prefs.edit()
        DevParams.write(values, { k, x -> e.putFloat(k, x) }, { k, x -> e.putBoolean(k, x) })
        e.apply()
        flags.edit().remove(KEY_FIT_BEFORE).remove(KEY_FIT_RECORD).remove(KEY_FIT_FLOOR_HZ).apply()
        Toast.makeText(this, R.string.fit_restored, Toast.LENGTH_SHORT).show()
        ui = introState()
    }

    /** One line kept with the result (shown on the intro next time). */
    private fun record(r: FitResult): String {
        val date = SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())
        val floor = r.floor?.let { getString(R.string.fit_hz, it.speakerFloorHz.toInt()) } ?: getString(R.string.fit_r_keep)
        val strength = newValues?.let { getString(R.string.fit_db, signed(it[DevParams.ALL.indexOf(DevParams.STRENGTH)].toDouble())) }
            ?: getString(R.string.fit_r_keep)
        return getString(R.string.fit_record, date, floor, strength, ui.volumeText, ui.seedText) +
            if (ui.noisy) " · " + getString(R.string.fit_record_noisy) else ""
    }

    // ------------------------------------------------------------------------------------------------ actions

    private val actions = FitActions(
        onBack = { finish() },
        onStart = { start() },
        onRestore = { restoreBefore() },
        onRoomRetry = { stopAll(); ui = introState() },
        onRoomProceed = { ui = ui.copy(noisy = true); if (mic == null) hold(FitVariant.RAW); beginTest() },
        onFloor = { c -> answered { it.answerFloor(c) } },
        onReplay = {
            when (val p = ui.prompt) {
                is FitPrompt.Floor -> if (ui.paused == null) playTrial(p)
                is FitPrompt.Buzz -> if (ui.paused == null) playClip("C")
                else -> Unit
            }
        },
        onPlay = { label -> if (ui.paused == null) playClip(label) },
        onAbx = { xIsA -> answered { it.answerAbx(xIsA) } },
        onPrefer = { pick -> answered { it.answerPrefer(pick) } },
        onBuzz = { buzz -> answered { it.answerBuzz(buzz) } },
        onShape = { take -> session?.let { it.shapeChoice(take); present() } },
        onCheckStart = { startCheck() },
        onCheckSkip = { skipCheck() },
        onCheckSide = { side -> if (ui.paused == null) playCheckSide(side) },
        onCheckAnswer = { a -> answerCheck(a) },
        onSave = { save() },
        onClose = { finish() },
    )

    companion object {
        const val FS = 48000
        /** Developer values before the last saved fit (comma-separated, DevParams.ALL order). */
        const val KEY_FIT_BEFORE = "bass_fit_before"
        /** One line describing the last saved fit. */
        const val KEY_FIT_RECORD = "bass_fit_record"
        /** Speaker floor found by the last saved fit (Hz): the developer-mode graphs draw it instead of the profile's. */
        const val KEY_FIT_FLOOR_HZ = "bass_fit_floor_hz"
        private const val CHECK_SALT = 0x5EED_C0DE_L

        fun seedText(seed: Long): String = String.format(Locale.ROOT, "%08X", (seed ushr 32) xor (seed and 0xFFFFFFFFL))

        fun signed(v: Double): String = when {
            v > 0.05 -> "+" + String.format(Locale.ROOT, "%.0f", v)
            v < -0.05 -> "−" + String.format(Locale.ROOT, "%.0f", -v)
            else -> "0"
        }
    }
}

/**
 * The phone microphone, recorded continuously into a 12 s ring (mono, 48 kHz float) on its own thread. [frames] counts
 * the frames recorded so far; [copy] gives a stretch back while it is still in the ring. UNPROCESSED where the phone
 * offers it (no noise suppression or gain control), else VOICE_RECOGNITION (both keep the ratios the room check uses).
 */
internal class FitMic private constructor(private val rec: AudioRecord) {
    private val ring = FloatArray(BassFitActivity.FS * RING_S)
    @Volatile var frames = 0L; private set
    @Volatile private var running = true

    init { Thread({ loop() }, "bass-fit-mic").start() }

    private fun loop() {
        val buf = FloatArray(BassFitActivity.FS / 100)
        try {
            rec.startRecording()
            while (running) {
                val n = rec.read(buf, 0, buf.size, AudioRecord.READ_BLOCKING)
                if (n < 0) break
                val w = frames
                for (i in 0 until n) ring[((w + i) % ring.size).toInt()] = buf[i]
                frames = w + n
            }
        } catch (_: Exception) {
        } finally {
            try { rec.stop() } catch (_: Exception) {}
            rec.release()
        }
    }

    /** [n] frames from [from], or null when they are not recorded yet or already overwritten. */
    fun copy(from: Long, n: Int): FloatArray? {
        val now = frames
        if (n <= 0 || from < 0 || from + n > now || from < now - ring.size) return null
        return FloatArray(n) { ring[((from + it) % ring.size).toInt()] }
    }

    fun stop() {
        running = false
        try { rec.stop() } catch (_: Exception) {}   // unblocks a read in progress
    }

    companion object {
        private const val RING_S = 12

        fun open(am: AudioManager?): FitMic? {
            val fs = BassFitActivity.FS
            val source = if (am?.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true")
                MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
            val minBuf = AudioRecord.getMinBufferSize(fs, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_FLOAT)
            val rec = try {
                @Suppress("MissingPermission")
                AudioRecord(source, fs, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_FLOAT, maxOf(minBuf, fs / 2))
            } catch (_: Exception) { null }
            if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) { rec?.release(); return null }
            return FitMic(rec)
        }
    }
}

package me.timschneeberger.rootlessjamesdsp.devmode

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.widget.Toast
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidenceText
import me.timschneeberger.rootlessjamesdsp.pvb.DevMath
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevShareCode
import me.timschneeberger.rootlessjamesdsp.pvb.DevSnapshot
import me.timschneeberger.rootlessjamesdsp.pvb.DevSpec
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarning
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarningStore
import me.timschneeberger.rootlessjamesdsp.pvb.DevWarningTracker
import me.timschneeberger.rootlessjamesdsp.pvb.DeviceProfile
import me.timschneeberger.rootlessjamesdsp.pvb.DeviceProfiles
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbDevMeter
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbMeter
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService

/**
 * Developer mode of the general build ("개발자 모드", docs/DEVMODE_COPY.md, Figma "개발자 모드 시안").
 *
 * Entry: About -> 개발자/연구 -> 개발자 모드, or the row in the PVB settings, both only after the hidden unlock. The first
 * entry asks for consent (stored in pvb_flags); consenting turns developer mode on (pvb_dev_on). Values are written to
 * pvb_settings like every other PVB setting; the controller pushes them to the engine (P_DEV_ON, P_D_*).
 *
 * While the screen is visible: the engine's developer-mode meters run (P_DEV_METER) and are read about 25 times a second
 * on the main thread (never on the audio thread). Leaving the screen stops the test sound, the meters, the A/B hold and
 * any share-code preview.
 */
class DevModeActivity : BaseActivity() {
    private lateinit var prefs: SharedPreferences
    private lateinit var flags: SharedPreferences
    private lateinit var profile: DeviceProfile
    private var measuredOn: DeviceProfile? = null
    private lateinit var tracker: DevWarningTracker
    private val main = Handler(Looper.getMainLooper())

    private var ui by mutableStateOf<DevUiState?>(null)
    private var reduceMotion by mutableStateOf(false)
    private val undo = ArrayDeque<FloatArray>()
    private val meterBuf = FloatArray(PvbDevMeter.SIZE)
    private val engineMeters = FloatArray(PvbMeter.COUNT)
    private var polling = false
    private var touchedClear: Runnable? = null

    private val store = object : DevWarningStore {
        override fun count(w: DevWarning) = flags.getInt("dev_warn_count_${w.name}", 0)
        override fun setCount(w: DevWarning, n: Int) { flags.edit().putInt("dev_warn_count_${w.name}", n).apply() }
        override fun hidden(w: DevWarning) = flags.getBoolean("dev_warn_hidden_${w.name}", false)
        override fun setHidden(w: DevWarning, hidden: Boolean) { flags.edit().putBoolean("dev_warn_hidden_${w.name}", hidden).apply() }
    }

    private val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ -> reloadValues() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!PvbBuild.general) { finish(); return }
        prefs = getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        flags = PvbGeneral.flags(this)
        profile = PvbGeneral.profile(this)
        measuredOn = loadMeasuredOnProfile()
        tracker = DevWarningTracker(store)

        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }

        val consent = flags.getBoolean(PvbGeneral.KEY_DEV_CONSENT, false)
        if (consent && !prefs.getBoolean(DevParams.KEY_DEV_ON, false)) prefs.edit().putBoolean(DevParams.KEY_DEV_ON, true).apply()
        ui = buildState(consentNeeded = !consent)
        if (consent) maybeUnmeasured()
        setContent { ui?.let { DevModeScreen(it, actions, reduceMotion) } }
    }

    override fun onStart() {
        super.onStart()
        if (!::prefs.isInitialized) return
        prefs.registerOnSharedPreferenceChangeListener(prefListener)
        reduceMotion = animationsOff()
        reloadValues()
        PvbRuntime.setDevMeter(true)
        polling = true
        main.post(poll)
    }

    override fun onStop() {
        if (::prefs.isInitialized) {
            prefs.unregisterOnSharedPreferenceChangeListener(prefListener)
            polling = false
            main.removeCallbacks(poll)
            // Nothing of the screen outlives it: test sound, meters, A/B hold, preview.
            DevTestSound.stop()
            PvbRuntime.setDevMeter(false)
            PvbRuntime.setDevOverride(null)
            update { it.copy(testKind = null, abHolding = false, previewing = false) }
        }
        super.onStop()
    }

    // ------------------------------------------------------------------------------------------------ state

    private fun update(f: (DevUiState) -> DevUiState) { ui = ui?.let(f) }

    private fun settings(): PvbSettings = PvbSettings.load(prefs)

    private fun profileDefaults(): FloatArray = DevParams.defaults(profile.settings)

    private fun loadMeasuredOnProfile(): DeviceProfile? = try {
        assets.open("${DeviceProfiles.ASSET_DIR}/${DevEvidenceText.MEASURED_ON_ID}.json").bufferedReader()
            .use { DeviceProfiles.parse(it.readText()) }
    } catch (e: Exception) {
        null
    }

    private fun buildState(consentNeeded: Boolean): DevUiState {
        val s = settings()
        val badge = DevEvidenceText.measuredBadge(profile, measuredOn)
        return DevUiState(
            values = DevParams.read(s),
            defaults = profileDefaults(),
            vbAlgo = s.vbAlgo,
            s1mOn = s.xS1m,
            volumeLinkOn = s.vbVolLink,
            measuredBadge = badge,
            thresholdMeasured = DevEvidenceText.thresholdMeasured(profile),
            measuredOnName = badge.deviceName,
            speakerFloorHz = profile.speakerFloorHz,
            gaugeVu = flags.getBoolean(PvbGeneral.KEY_DEV_GAUGE_VU, false),
            hiddenCount = tracker.hiddenTypes().size,
            canUndo = undo.isNotEmpty(),
            consentNeeded = consentNeeded,
            serviceRunning = BaseAudioProcessorService.activeServices > 0,
            shareCode = shareCode(DevParams.read(s)),
        )
    }

    private fun reloadValues() {
        val s = settings()
        val values = DevParams.read(s)
        update {
            it.copy(values = values, vbAlgo = s.vbAlgo, s1mOn = s.xS1m, volumeLinkOn = s.vbVolLink,
                canUndo = undo.isNotEmpty(), hiddenCount = tracker.hiddenTypes().size, shareCode = shareCode(values))
        }
    }

    private fun shareCode(values: FloatArray): String =
        DevShareCode.encode(android.os.Build.MODEL ?: "", BuildConfig.VERSION_NAME, values, profileDefaults())

    private fun animationsOff(): Boolean = try {
        Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    } catch (e: Exception) {
        false
    }

    private fun maybeUnmeasured() {
        if (tracker.unmeasuredOnEntry(profile.measured))
            update { it.copy(dialog = DevDialog(DevWarning.UNMEASURED, offerHide = false, tailMs = 0)) }
    }

    // ------------------------------------------------------------------------------------------------ meters

    private val poll = object : Runnable {
        override fun run() {
            if (!polling) return
            readMeters()
            main.postDelayed(this, POLL_MS)
        }
    }

    private fun readMeters() {
        val engine = PvbRuntime.engine
        val running = BaseAudioProcessorService.activeServices > 0
        if (engine == null || !engine.copyDevMeters(meterBuf)) {
            update { it.copy(snapshot = null, serviceRunning = running) }
            return
        }
        engine.readMeters(engineMeters)
        val st = PvbRuntime.status
        val s = settings()
        val volPct = VolumeLevelLink.volumePct(st.volumeIndex, st.volumeMax)
        val snap = DevSnapshot.fromMeters(
            meterBuf,
            outPeakDb = engineMeters[PvbMeter.OUT_PEAK_DB],
            limiterGrDb = engineMeters[PvbMeter.LIM_GR_DB],
            ceilingDb = minOf(s.ceilDb, -1f),
            volumePct = volPct,
            volumeLink = s.vbVolLink,
            volumeLinkReductionDb = st.vbVolReductionDb,
            thresholdDb = profile.protectThresholdDb(volPct),
        )
        val active = DevMath.evaluate(snap)
        val tail = DevMath.tailMs(snap.ringDry, snap.ringLayer, snap.binMs)
        val current = ui ?: return
        val show = if (current.consentNeeded) null
            else tracker.update(active, SystemClock.elapsedRealtime(), dialogOpen = current.dialog != null || current.sheetOpen)
        update {
            it.copy(snapshot = snap, active = active, tailMs = tail, volumePct = volPct, serviceRunning = running,
                dialog = it.dialog ?: show?.let { w -> DevDialog(w, tracker.offerHide(w), Math.round(tail ?: 0f)) })
        }
    }

    // ------------------------------------------------------------------------------------------------ writing

    private fun write(spec: DevSpec, value: Float) {
        val v = spec.snap(value)
        val e = prefs.edit()
        if (spec.isSwitch) e.putBoolean(spec.key, v >= 0.5f) else e.putFloat(spec.key, v)
        e.apply()
        update {
            val values = it.values.copyOf().also { a -> a[DevParams.ALL.indexOf(spec)] = v }
            it.copy(values = values, shareCode = shareCode(values))
        }
    }

    private fun writeAll(values: FloatArray) {
        val e = prefs.edit()
        DevParams.write(values, { k, v -> e.putFloat(k, v) }, { k, v -> e.putBoolean(k, v) })
        e.apply()
        update { it.copy(values = values.copyOf(), shareCode = shareCode(values)) }
    }

    private fun pushUndo() {
        val cur = ui?.values ?: return
        if (undo.lastOrNull()?.contentEquals(cur) == true) return
        undo.addLast(cur.copyOf())
        while (undo.size > MAX_UNDO) undo.removeFirst()
        update { it.copy(canUndo = true) }
    }

    private fun touch(spec: DevSpec?) {
        touchedClear?.let { main.removeCallbacks(it) }
        update { it.copy(touched = spec?.id) }
        if (spec != null) {
            val r = Runnable { update { it.copy(touched = null) } }
            touchedClear = r
            main.postDelayed(r, TOUCH_HOLD_MS)
        }
    }

    private fun toast(res: Int) = Toast.makeText(this, res, Toast.LENGTH_SHORT).show()

    // ------------------------------------------------------------------------------------------------ actions

    private val actions = DevActions(
        onBack = { finish() },
        onConsent = { ok ->
            if (!ok) finish() else {
                flags.edit().putBoolean(PvbGeneral.KEY_DEV_CONSENT, true).apply()
                prefs.edit().putBoolean(DevParams.KEY_DEV_ON, true).apply()
                update { it.copy(consentNeeded = false) }
                maybeUnmeasured()
            }
        },
        onTab = { tab -> update { it.copy(tab = tab) } },
        onValueStart = { spec -> pushUndo(); touch(spec) },
        onValue = { spec, v -> write(spec, v); touch(spec) },
        onStep = { spec, dir ->
            pushUndo()
            val cur = ui?.values?.get(DevParams.ALL.indexOf(spec)) ?: spec.default
            val range = rangeOf(spec)
            val next = (cur + dir * spec.step).coerceIn(range.start, range.endInclusive)
            write(spec, next)
            touch(spec)
        },
        onToggle = { spec, on -> pushUndo(); write(spec, if (on) 1f else 0f); touch(spec) },
        onUndo = {
            val prev = undo.removeLastOrNull()
            if (prev == null) toast(R.string.dev_undo_empty) else writeAll(prev)
            update { it.copy(canUndo = undo.isNotEmpty()) }
        },
        onResetGroup = { group ->
            val cur = ui?.values
            if (cur != null) {
                pushUndo()
                writeAll(DevParams.reset(cur, profileDefaults(), group))
                toast(R.string.dev_reset_done)
            }
        },
        onAbHold = { held ->
            if (held) PvbRuntime.setDevOverride(DevParams.apply(settings(), profileDefaults()))
            else PvbRuntime.setDevOverride(null)
            update { it.copy(abHolding = held, previewing = false) }
        },
        onTest = { kind ->
            val cur = ui
            when {
                cur == null -> Unit
                kind == null -> { DevTestSound.stop(); update { it.copy(testKind = null) } }
                kind == DevTestKind.TONE && cur.testKind == DevTestKind.TONE -> {
                    val next = TONES[(TONES.indexOf(cur.toneHz) + 1) % TONES.size]
                    DevTestSound.start(kind, next.toDouble())
                    update { it.copy(toneHz = next) }
                }
                kind == cur.testKind -> { DevTestSound.stop(); update { it.copy(testKind = null) } }
                else -> { DevTestSound.start(kind, cur.toneHz.toDouble()); update { it.copy(testKind = kind) } }
            }
        },
        onEvidence = { spec -> update { it.copy(evidenceFor = spec?.id, sheetOpen = spec != null || it.shareOpen) } },
        onOpenUrl = { url -> PvbGeneral.openUrl(this, url) },
        onShareOpen = { open ->
            if (!open) PvbRuntime.setDevOverride(null)
            update { it.copy(shareOpen = open, sheetOpen = open || it.evidenceFor != null, previewing = if (open) it.previewing else false) }
        },
        onCopy = {
            val code = ui?.shareCode ?: ""
            (getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager)
                ?.setPrimaryClip(ClipData.newPlainText(getString(R.string.dev_share_title), code))
            toast(R.string.dev_share_copied)
        },
        onSend = {
            val code = ui?.shareCode ?: ""
            try {
                startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_TEXT, code), getString(R.string.dev_share_title)))
            } catch (e: Exception) {
                toast(R.string.no_activity_found)
            }
        },
        onPaste = { text ->
            val r = if (text.isBlank()) null else DevShareCode.decode(text, profileDefaults())
            update { it.copy(pasteText = text, pasteResult = r) }
        },
        onPreview = { on ->
            val r = ui?.pasteResult as? DevShareCode.Result.Ok
            if (on && r != null) PvbRuntime.setDevOverride(DevParams.apply(settings(), r.values))
            else PvbRuntime.setDevOverride(null)
            update { it.copy(previewing = on && r != null) }
        },
        onApply = {
            val r = ui?.pasteResult as? DevShareCode.Result.Ok
            if (r != null) {
                PvbRuntime.setDevOverride(null)
                pushUndo()
                writeAll(r.values)
                toast(R.string.dev_share_applied)
                update { it.copy(previewing = false, shareOpen = false, sheetOpen = it.evidenceFor != null, pasteText = "", pasteResult = null) }
            }
        },
        onDialogClose = { hide, action ->
            val d = ui?.dialog
            if (d != null) {
                if (hide) tracker.hide(d.warning)
                if (action) runWarningAction(d.warning)
            }
            update { it.copy(dialog = null, hiddenCount = tracker.hiddenTypes().size) }
        },
        onGaugeStyle = { vu ->
            flags.edit().putBoolean(PvbGeneral.KEY_DEV_GAUGE_VU, vu).apply()
            update { it.copy(gaugeVu = vu) }
        },
        onRestoreWarnings = {
            tracker.restoreAll()
            toast(R.string.dev_hidden_restored)
            update { it.copy(hiddenCount = 0) }
        },
        onTurnOff = {
            writeAll(profileDefaults())
            prefs.edit().putBoolean(DevParams.KEY_DEV_ON, false).apply()
            finish()
        },
    )

    /** The slider range of [spec] for the current model (the roll-off offset depends on it). */
    private fun rangeOf(spec: DevSpec): ClosedFloatingPointRange<Float> =
        if (spec === DevParams.ROLLOFF) DevParams.rolloffRange(ui?.vbAlgo ?: 0) else spec.min..spec.max

    private fun runWarningAction(w: DevWarning) {
        when (w) {
            DevWarning.BUZZ_ZONE, DevWarning.NEAR_CEILING -> {
                pushUndo()
                val cur = ui?.values?.get(DevParams.ALL.indexOf(DevParams.STRENGTH)) ?: DevParams.STRENGTH.default
                write(DevParams.STRENGTH, (cur - 2f).coerceAtLeast(0f))
            }
            DevWarning.TAIL -> {
                pushUndo()
                write(DevParams.RELEASE, DevParams.RELEASE.default)
            }
            DevWarning.VOLUME_NO_LINK -> prefs.edit().putBoolean(PvbSettings.KEY_VB_VOL_LINK, true).apply()
            DevWarning.UNMEASURED -> Unit
        }
    }

    companion object {
        private const val POLL_MS = 40L
        private const val MAX_UNDO = 50
        private const val TOUCH_HOLD_MS = 1500L
        val TONES = listOf(40, 55, 80)
    }
}

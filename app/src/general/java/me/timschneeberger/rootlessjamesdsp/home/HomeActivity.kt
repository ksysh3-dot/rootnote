package me.timschneeberger.rootlessjamesdsp.home

import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.media.AudioManager
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.HapticFeedbackConstants
import androidx.activity.compose.setContent
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.content.getSystemService
import androidx.core.view.WindowCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.activity.MainActivity
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity
import me.timschneeberger.rootlessjamesdsp.pvb.FirstRun
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore
import me.timschneeberger.rootlessjamesdsp.pvb.HomeLogic
import me.timschneeberger.rootlessjamesdsp.pvb.KillWatch
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbMeter
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.service.RootAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.service.RootlessAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.setup.RnRootSetup
import me.timschneeberger.rootlessjamesdsp.utils.isRoot
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.utils.extensions.AssetManagerExtensions.installPrivateAssets
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.registerLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.unregisterLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasProjectMediaAppOp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission
import timber.log.Timber

/**
 * Launch screen of the general build (Rootnote). The DSP screen (advanced/RnAdvancedActivity) is reached through "Advanced
 * settings"; the s26u build keeps MainActivity as its launcher and never contains this class.
 *
 * The master row is the general build's processing switch: on = PVB processing (pvb_enable) and virtual bass
 * (pvb_vb_enable) on, with the audio service running; off = pvb_enable off (the service keeps running, so turning
 * it back on is instant). The first-run notice (the welcome screen, WelcomeActivity) gates it exactly as it gates the
 * service (FirstRun / PvbBuild); the welcome carries the virtual-bass warning and confirming it turns virtual bass on,
 * so the switch never asks again.
 *
 * First week (FirstWeek): a row to the app exclusion list (video and games play without the delay), and a banner when
 * the system killed the capture service (KillWatch) that leads to the battery step.
 *
 * Start-up mirrors MainActivity for the rootless build: private assets, onboarding when permissions are missing,
 * first-run and unmeasured-phone notices, the Android 15 notice, and the capture prompt when processing is
 * expected but the service is not running.
 */
class HomeActivity : BaseActivity() {
    private lateinit var prefs: SharedPreferences
    private lateinit var mediaProjectionManager: MediaProjectionManager
    private lateinit var captureLauncher: ActivityResultLauncher<Intent>

    private var uiState by mutableStateOf<HomeUiState?>(null)
    private var reduceMotion by mutableStateOf(false)

    /** "Custom" tapped on this screen: stays selected until a preset chip is tapped. */
    private var customPinned = false
    /** The user turned processing on and the service is being started (capture prompt, service start). */
    private var startPending = false
    private val clearPending = Runnable { startPending = false; refresh() }

    // Kept as fields: SharedPreferences holds its listeners weakly.
    private val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ -> refresh() }
    private val statusListener: () -> Unit = { refresh() }
    private val serviceReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            startPending = false
            refresh()
        }
    }

    /** "누르는 동안 가상 저음 빼고 듣기" is held: its override is cleared when the screen stops. */
    private var holdingWithoutVb = false

    private val actions = HomeActions(
        onMaster = { on -> onMasterChanged(on) },
        onLevel = { level ->
            prefs.edit().putFloat(PvbSettings.KEY_VB_STRENGTH_DB, level.toFloat()).apply()
        },
        onChip = { chip -> onChipTapped(chip) },
        onLink = { on -> prefs.edit().putBoolean(PvbSettings.KEY_VB_VOL_LINK, on).apply() },
        // temporary: the user's settings as played, layer silent (same model and latency); never stored
        onHoldWithoutVb = { held ->
            holdingWithoutVb = held
            PvbRuntime.setDevOverride(if (held) PvbSettings.load(prefs).copy(vbLevelDb = PvbSettings.VB_LEVEL_OFF) else null)
        },
        onAdvanced = { startActivity(me.timschneeberger.rootlessjamesdsp.advanced.RnAdvancedActivity.intent(this)) },
        onAbout = {
            startActivity(me.timschneeberger.rootlessjamesdsp.settings.RnSettingsActivity.intent(this,
                me.timschneeberger.rootlessjamesdsp.settings.RnSettingsActivity.Route.ABOUT))
        },
        onExclusions = { startActivity(me.timschneeberger.rootlessjamesdsp.exclusions.RnExclusionsActivity.intent(this)) },
        onKillBattery = {
            startActivity(Intent(this, OnboardingActivity::class.java).putExtra(OnboardingActivity.EXTRA_BATTERY_SETUP, true))
        },
        onKillDismiss = {
            FirstWeekStore.onBannerDismissed(this)
            refresh()
        },
        onXtc = { on ->
            if (on) {
                val last = try { prefs.getString(PvbSettings.KEY_XTC_LAST_MODE, null)?.toIntOrNull() } catch (_: ClassCastException) { null }
                val mode = HomeLogic.xtcResumeMode(last)
                if (mode != null) prefs.edit().putString(PvbSettings.KEY_XTC_MODE, mode.toString()).apply()
                else writeXtcPreset(HomeLogic.XtcPreset.BALANCED)
            } else {
                prefs.edit()
                    .putString(PvbSettings.KEY_XTC_LAST_MODE, PvbSettings.load(prefs).xtcMode.toString())
                    .putString(PvbSettings.KEY_XTC_MODE, PvbSettings.XTC_OFF.toString())
                    .apply()
            }
        },
        onXtcPreset = { preset -> if (preset != HomeLogic.XtcPreset.CUSTOM) writeXtcPreset(preset) },
        onXtcDistance = { step ->
            prefs.edit().putFloat(PvbSettings.KEY_XTC_DISTANCE, HomeLogic.xtcDistanceCm(step).toFloat()).apply()
        },
        onXtcHead = { hat -> prefs.edit().putString(PvbSettings.KEY_XTC_HEAD, hat.toString()).apply() },
        onSpatialInfo = { startActivity(Intent(this, SpatialStoryActivity::class.java)) },
        onXtcBalance = { startActivity(Intent(this, SpatialBalanceActivity::class.java)) },
    )

    /** Spatial preset: mode + strength, as the list values of the advanced settings ("-6", "-4.5", "-3"). */
    private fun writeXtcPreset(preset: HomeLogic.XtcPreset) {
        val db = preset.strengthDb
        val text = if (db == Math.round(db).toFloat()) Math.round(db).toString() else db.toString()
        prefs.edit()
            .putString(PvbSettings.KEY_XTC_MODE, preset.mode.toString())
            .putString(PvbSettings.KEY_XTC_STRENGTH, text)
            .apply()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        mediaProjectionManager = getSystemService<MediaProjectionManager>()!!

        // The window behind the screen (and the status bar area) has the screen's colour.
        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }

        val firstBoot = prefsVar.get<Boolean>(R.string.key_first_boot)
        assets.installPrivateAssets(this, force = firstBoot)

        captureLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                app.mediaProjectionStartIntent = result.data
                RootlessAudioProcessorService.start(this, result.data)
                armPendingTimeout()
            } else {
                startPending = false
            }
            refresh()
        }

        // Permissions missing: the setup screens first, like MainActivity. On the first launch the welcome
        // (WelcomeActivity) comes before them and starts them itself after the answer.
        // Root build (Magisk module): no capture permissions to set up; DUMP (finding the apps' audio sessions) is
        // granted with su, and the Rootnote module must be the installed JamesDSP effect.
        if (isRoot()) RnRootSetup.check(this)
        else if (!hasDumpPermission() || !hasRecordPermission()) {
            Timber.i("Launching onboarding (first boot: $firstBoot)")
            if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed))
                startActivity(WelcomeActivity.thenSetup(this, fixPerms = !firstBoot))
            else
                startActivity(Intent(this, OnboardingActivity::class.java).apply {
                    putExtra(OnboardingActivity.EXTRA_FIX_PERMS, !firstBoot)
                })
            finish()
            return
        }

        reduceMotion = animationsOff()
        refresh()
        setContent {
            uiState?.let { HomeScreen(it, actions, reduceMotion) }
        }

        // Not confirmed yet: the welcome over the home screen ("확인하고 시작하기" starts processing right away), unless
        // it was put off in this process; then it comes when processing is switched on.
        if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed)) {
            if (!PvbGeneral.welcomeLater)
                PvbGeneral.showFirstRunNotice(this, onConfirmed = {
                    PvbGeneral.maybeShowUnmeasuredNotice(this)
                    refresh()
                    ensureRunning()
                })
        } else
            PvbGeneral.maybeShowUnmeasuredNotice(this)

        if (showAndroid15Alert()) return

        // Back from onboarding, or processing expected but the service is not running: ask for capture now
        // (MainActivity does the same whenever its service is not running).
        val running = BaseAudioProcessorService.activeServices > 0
        if (intent.getBooleanExtra(MainActivity.EXTRA_FORCE_SHOW_CAPTURE_PROMPT, false) ||
            (!running && PvbSettings.load(prefs).enabled)) {
            startPending = true
            requestCapturePermission()
            refresh()
        }
    }

    override fun onStart() {
        super.onStart()
        if (!::prefs.isInitialized) return
        prefs.registerOnSharedPreferenceChangeListener(prefListener)
        PvbRuntime.addStatusListener(statusListener)
        registerLocalReceiver(serviceReceiver, IntentFilter(Constants.ACTION_SERVICE_STARTED).apply {
            addAction(Constants.ACTION_SERVICE_STOPPED)
        })
        refresh()
    }

    override fun onResume() {
        super.onResume()
        reduceMotion = animationsOff()
        refresh()
        mainHandler.removeCallbacks(pressurePoll)
        mainHandler.postDelayed(pressurePoll, 1000L)
    }

    override fun onPause() {
        mainHandler.removeCallbacks(pressurePoll)
        super.onPause()
    }

    override fun onStop() {
        if (holdingWithoutVb) { holdingWithoutVb = false; PvbRuntime.setDevOverride(null) }
        if (::prefs.isInitialized) {
            prefs.unregisterOnSharedPreferenceChangeListener(prefListener)
            PvbRuntime.removeStatusListener(statusListener)
            try {
                unregisterLocalReceiver(serviceReceiver)
            } catch (e: Exception) {
                Timber.d(e)
            }
        }
        super.onStop()
    }

    override fun onDestroy() {
        window?.decorView?.removeCallbacks(clearPending)
        super.onDestroy()
    }

    // ------------------------------------------------------------------------------------------------ state

    private fun refresh() {
        if (!::prefs.isInitialized) return
        val s = PvbSettings.load(prefs)
        val running = BaseAudioProcessorService.activeServices > 0
        val status = PvbRuntime.status
        val audio = getSystemService<AudioManager>()
        // The controller's published volume while it runs; otherwise the same AudioManager values it reads.
        val (index, max) = if (running && status.volumeMax > 0) status.volumeIndex to status.volumeMax
            else (audio?.getStreamVolume(AudioManager.STREAM_MUSIC) ?: -1) to (audio?.getStreamMaxVolume(AudioManager.STREAM_MUSIC) ?: 0)
        val caps = PvbBuild.caps
        val profile = PvbGeneral.profile(this)
        val shownRunning = running || startPending
        // A capture service that died without stopping (One UI battery management): banner until dismissed/recovered.
        val kill = FirstWeekStore.check(this, running)
        uiState = HomeUiState(
            headline = HomeLogic.headline(s, shownRunning),
            masterOn = HomeLogic.masterOn(s, shownRunning),
            measuredDeviceName = if (profile.measured) profile.name else null,
            level = HomeLogic.sliderValue(s.vbLevelDb, caps),
            levelMax = HomeLogic.sliderMax(caps),
            chip = HomeLogic.selectedChip(HomeLogic.modelKey(s.vbAlgo), s.vbLevelDb, customPinned),
            linkOn = s.vbVolLink,
            linkLine = HomeLogic.linkLine(s, index, max),
            killBanner = KillWatch.showBanner(PvbBuild.general, kill, shownRunning, s.enabled),
            xtcOn = s.xtcMode != PvbSettings.XTC_OFF,
            processingOn = HomeLogic.headline(s, shownRunning) != HomeLogic.Headline.ORIGINAL,
            xtcDistanceCm = s.xtcDistanceCm.toInt(),
            xtcPreset = HomeLogic.xtcPreset(s.xtcMode, s.xtcStrengthDb),
            xtcDistanceStep = HomeLogic.xtcDistanceStep(s.xtcDistanceCm),
            xtcDistanceSteps = HomeLogic.xtcDistanceSteps(),
            xtcHatCm = s.xtcHatCm.toInt(),
            xtcBalLoDb = s.xtcBalLoDb,
            xtcBalHiDb = s.xtcBalHiDb,
            limiterPressure = limiterPressure,
        )
    }

    // Limiter pressure (HomeLogic.limiterPressure): the engine's meters once a second while this screen is in front.
    // Reading the meters also restarts the peak meters and runs the phone limiter estimate for 3 s (display cost only).
    private var limiterPressure = false
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val meterBuf = FloatArray(PvbMeter.COUNT)
    private val pressurePoll = object : Runnable {
        override fun run() {
            val s = if (::prefs.isInitialized) PvbSettings.load(prefs) else null
            val running = BaseAudioProcessorService.activeServices > 0
            val engine = PvbRuntime.engine
            val pct = if (running && engine != null && engine.readMeters(meterBuf)) meterBuf[PvbMeter.LIM_ACTIVE_PCT] else 0f
            val vbPlaying = s != null && running && s.enabled && s.vbOn && PvbRuntime.status.processing
            val next = HomeLogic.limiterPressure(limiterPressure, vbPlaying, pct)
            if (next != limiterPressure) { limiterPressure = next; refresh() }
            mainHandler.postDelayed(this, 1000L)
        }
    }

    private fun animationsOff(): Boolean = try {
        Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    } catch (e: Exception) {
        false
    }

    // ------------------------------------------------------------------------------------------------ actions

    private fun onMasterChanged(on: Boolean) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
            window.decorView.performHapticFeedback(
                if (on) HapticFeedbackConstants.CONFIRM else HapticFeedbackConstants.REJECT
            )
        if (on) turnOn() else turnOff()
    }

    private fun turnOn() {
        // Nothing runs before the first-run notice was confirmed (confirming turns pvb_enable on).
        if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed)) {
            PvbGeneral.showFirstRunNotice(this, onConfirmed = {
                PvbGeneral.maybeShowUnmeasuredNotice(this)
                turnOn()
            })
            return
        }
        // The confirmed first-run notice is the virtual-bass consent (it carries the warning): no second dialog.
        prefs.edit()
            .putBoolean(PvbSettings.KEY_VB_ON, true)
            .putBoolean(PvbSettings.KEY_ENABLE, true)
            .apply()
        ensureRunning()
    }

    private fun turnOff() {
        // The service keeps running (no new capture prompt when turning back on); PVB passes the sound through.
        startPending = false
        prefs.edit().putBoolean(PvbSettings.KEY_ENABLE, false).apply()
        FirstWeekStore.onUserTurnedOff(this)
        refresh()
    }

    private fun ensureRunning() {
        if (BaseAudioProcessorService.activeServices == 0) {
            startPending = true
            requestCapturePermission()
        }
        refresh()
    }

    private fun onChipTapped(chip: HomeLogic.Chip) {
        val write = HomeLogic.presetWrite(chip, PvbBuild.caps)
        if (write == null) {
            customPinned = true
            refresh()
            return
        }
        customPinned = false
        // Only the model and the level, like the preset list of the advanced screen.
        prefs.edit()
            .putString(PvbSettings.KEY_VB_ALGO, write.first)
            .putFloat(PvbSettings.KEY_VB_STRENGTH_DB, write.second)
            .apply()
        refresh()
    }

    // ------------------------------------------------------------------------------------------------ service

    private fun requestCapturePermission() {
        if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed)) {
            startPending = false
            PvbGeneral.showFirstRunNotice(this, onConfirmed = {
                PvbGeneral.maybeShowUnmeasuredNotice(this)
                startPending = true
                requestCapturePermission()
                refresh()
            })
            refresh()
            return
        }
        if (isRoot()) {
            // the audio effect does the work; the service attaches it to the apps' sessions
            RootAudioProcessorService.startServiceEnhanced(this)
            armPendingTimeout()
            return
        }
        if (app.mediaProjectionStartIntent != null && !SdkCheck.isVanillaIceCream) {
            RootlessAudioProcessorService.start(this, app.mediaProjectionStartIntent)
            armPendingTimeout()
            return
        }
        try {
            captureLauncher.launch(mediaProjectionManager.createScreenCaptureIntent())
        } catch (ex: ActivityNotFoundException) {
            startPending = false
            toast(getString(R.string.error_projection_api_missing))
            Timber.e(ex)
            refresh()
        }
    }

    /** The service reports its start by broadcast; if it never does, stop showing "on". */
    private fun armPendingTimeout() {
        window.decorView.removeCallbacks(clearPending)
        window.decorView.postDelayed(clearPending, 5000L)
    }

    /** MainActivity's Android 15 keyguard notice. Returns true when it sent the user to the setup screens. */
    private fun showAndroid15Alert(): Boolean {
        if (!SdkCheck.isVanillaIceCream) return false

        if (!hasProjectMediaAppOp()) {
            MaterialAlertDialogBuilder(this)
                .setTitle(R.string.android_15_screenshare_warning_title)
                .setMessage(R.string.android_15_screenshare_keyguard_warning)
                .setCancelable(false)
                .setPositiveButton(R.string.continue_action) { _, _ ->
                    startActivity(Intent(this, OnboardingActivity::class.java).apply {
                        putExtra(OnboardingActivity.EXTRA_FIX_PERMS, false)
                    })
                    finish()
                }
                .show()
            return true
        }

        // The information part (notifications hidden while capturing, "Disable screen share protections") is in
        // the first-run notice, so the home screen does not show it as a second dialog.
        return false
    }
}

package me.timschneeberger.rootlessjamesdsp.advanced

import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.HapticFeedbackConstants
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.getSystemService
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.MainActivity
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity
import me.timschneeberger.rootlessjamesdsp.home.WelcomeActivity
import me.timschneeberger.rootlessjamesdsp.interop.JamesDspWrapper
import me.timschneeberger.rootlessjamesdsp.model.ProcessorMessage
import me.timschneeberger.rootlessjamesdsp.model.preset.Preset
import me.timschneeberger.rootlessjamesdsp.pvb.FirstRun
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.service.RootAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.service.RootlessAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.utils.isRoot
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.RoutingObserver
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.utils.extensions.AssetManagerExtensions.installPrivateAssets
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.broadcastPresetLoadEvent
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.registerLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.restoreDspSettings
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.sendLocalBroadcast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.unregisterLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasProjectMediaAppOp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission
import me.timschneeberger.rootlessjamesdsp.utils.storage.StorageUtils
import org.koin.android.ext.android.inject
import timber.log.Timber
import java.io.File
import kotlin.math.roundToInt

/**
 * "고급 설정" of the general build in Compose (replaces MainActivity and its DspFragment there; the s26u build keeps
 * them). Same keys, files and behaviours as the legacy screen (inventory in the plan): the audio service switch (the
 * legacy power button), the PVB status, the PVB settings with their build caps and derived rows, the JamesDSP modules
 * with their seal notes, presets, the revert, excluded apps and settings, and files opened with the app
 * (MainActivity forwards its VIEW intents here).
 *
 * The activity owns what a page cannot: the capture prompt and the service, the document picker of the file
 * libraries, and the broadcasts. Pages read the ticks below: [presetTick] (files replaced on disk), [statusTick]
 * (PvbRuntime published a status), [resumeTick] (back from another screen), [sampleRate] (the engine's processing
 * rate for the convolver line).
 */
class RnAdvancedActivity : RnActivity() {

    /** The capture service runs. */
    var serviceOn by mutableStateOf(false)
        private set
    /** Processing was switched on and the service is being started (capture prompt, service start). */
    var startPending by mutableStateOf(false)
        private set
    /** The screen is started (the status text refreshes only then). */
    var started by mutableStateOf(false)
        private set
    var presetTick by mutableIntStateOf(0)
        private set
    var statusTick by mutableIntStateOf(0)
        private set
    var resumeTick by mutableIntStateOf(0)
        private set
    /** The processing rate the engine last reported (Hz), 0 before any report. */
    var sampleRate by mutableIntStateOf(0)
        private set
    /** A file opened with the app, waiting for "import only" / "import and use" ([handleFileIntent]). */
    var pendingImport by mutableStateOf<PendingImport?>(null)
    /** An error to show in a dialog (title, text). */
    var alert by mutableStateOf<Pair<String, String>?>(null)

    data class PendingImport(val uri: Uri, val name: String, val title: Int, val subDir: String,
                             val namespace: String?, val keyRes: Int?, val enableKeyRes: Int?)

    /** The current output device (the upstream device profiles row). */
    val routingObserver: RoutingObserver by inject()

    private lateinit var mediaProjectionManager: MediaProjectionManager
    private lateinit var captureLauncher: ActivityResultLauncher<Intent>
    private lateinit var importLauncher: ActivityResultLauncher<Array<String>>
    private var onImportPicked: ((Uri) -> Unit)? = null
    private val clearPending = Runnable { startPending = false; refreshService() }

    private val serviceReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                Constants.ACTION_SERVICE_STARTED, Constants.ACTION_SERVICE_STOPPED -> {
                    startPending = false
                    refreshService()
                }
                Constants.ACTION_PRESET_LOADED -> {
                    persistDefaults()  // the legacy screen re-created its preferences, storing these again
                    presetTick++
                }
                Constants.ACTION_REPORT_SAMPLE_RATE ->
                    sampleRate = intent.getFloatExtra(Constants.EXTRA_SAMPLE_RATE, 0f).roundToInt()
            }
        }
    }

    /** The engine's messages (MainActivity showed them as snackbars). */
    private val processorMessageReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (ProcessorMessage.Type.fromInt(intent.getIntExtra(ProcessorMessage.TYPE, 0))) {
                ProcessorMessage.Type.VdcParseError -> toast(getString(R.string.message_vdc_corrupt))
                ProcessorMessage.Type.ConvolverParseError -> when (ProcessorMessage.ConvolverErrorCode.fromInt(
                    intent.getIntExtra(ProcessorMessage.Param.ConvolverErrorCode.name, 0))) {
                    ProcessorMessage.ConvolverErrorCode.Corrupted -> R.string.message_irs_corrupt
                    ProcessorMessage.ConvolverErrorCode.AdvParamsInvalid -> R.string.message_convolver_advimp_invalid
                    else -> null
                }?.let { toast(getString(it)) }
                ProcessorMessage.Type.LiveprogResult -> {
                    val ret = intent.getIntExtra(ProcessorMessage.Param.LiveprogResultCode.name, 1)
                    if (ret <= 0) toast(getString(R.string.message_liveprog_compile_fail) +
                        " (${JamesDspWrapper.eelErrorCodeToString(ret)})")
                }
                else -> {}
            }
        }
    }

    private val statusListener: () -> Unit = { statusTick++ }
    private var receiversRegistered = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        mediaProjectionManager = getSystemService<MediaProjectionManager>()!!

        captureLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == RESULT_OK) {
                app.mediaProjectionStartIntent = result.data
                RootlessAudioProcessorService.start(this, result.data)
                armPendingTimeout()
            } else startPending = false
            refreshService()
        }
        importLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            val then = onImportPicked
            onImportPicked = null
            if (uri != null) then?.invoke(uri)
        }

        val firstBoot = prefsVar.get<Boolean>(R.string.key_first_boot)
        assets.installPrivateAssets(this, force = firstBoot)

        // Permissions missing: the setup screens first, like MainActivity and the home screen.
        if (!hasDumpPermission() || !hasRecordPermission()) {
            if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed))
                startActivity(WelcomeActivity.thenSetup(this, fixPerms = !firstBoot))
            else
                startActivity(Intent(this, OnboardingActivity::class.java).putExtra(OnboardingActivity.EXTRA_FIX_PERMS, !firstBoot))
            finish()
            return
        }

        // The PVB settings as the legacy fragment left them on open: model migration, then the general build's caps
        // written back where a stored value is outside what a slider can show (the engine plays the clamped value).
        val pvb = getSharedPreferences(PvbSettings.PREFS_NAME, MODE_PRIVATE)
        PvbSettings.migrateVirtualBassModel(pvb)
        PvbAdvanced.writeBackCaps(pvb)

        persistDefaults()

        // Registered for the whole life of the screen (MainActivity did the same): a preset loaded while another
        // screen is on top still reloads this one.
        registerLocalReceiver(serviceReceiver, IntentFilter(Constants.ACTION_SERVICE_STARTED).apply {
            addAction(Constants.ACTION_SERVICE_STOPPED)
            addAction(Constants.ACTION_PRESET_LOADED)
            addAction(Constants.ACTION_REPORT_SAMPLE_RATE)
        })
        registerLocalReceiver(processorMessageReceiver, IntentFilter(Constants.ACTION_PROCESSOR_MESSAGE))
        receiversRegistered = true

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = returnToHome()
        })

        refreshService()
        setRnContent { AdvancedScreen(this) }

        sendLocalBroadcast(Intent(Constants.ACTION_PREFERENCES_UPDATED))

        if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed)) {
            if (!PvbGeneral.welcomeLater)
                PvbGeneral.showFirstRunNotice(this, onConfirmed = { PvbGeneral.maybeShowUnmeasuredNotice(this) })
        } else
            PvbGeneral.maybeShowUnmeasuredNotice(this)

        if (showAndroid15Alert()) return

        // Redirected from the setup screens: ask for capture right away (MainActivity did the same).
        if (intent.getBooleanExtra(MainActivity.EXTRA_FORCE_SHOW_CAPTURE_PROMPT, false) && !serviceOn) {
            startPending = true
            requestCapturePermission()
        }

        if (intent?.action == Intent.ACTION_VIEW) intent.data?.let { handleFileIntent(it) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.action == Intent.ACTION_VIEW) intent.data?.let { handleFileIntent(it) }
    }

    override fun onStart() {
        super.onStart()
        started = true
        PvbRuntime.addStatusListener(statusListener)
        refreshService()
    }

    override fun onResume() {
        super.onResume()
        prefsVar.set(R.string.key_is_activity_active, true)
        resumeTick++
        refreshService()
    }

    override fun onPause() {
        prefsVar.set(R.string.key_is_activity_active, false)
        super.onPause()
    }

    override fun onStop() {
        started = false
        PvbRuntime.removeStatusListener(statusListener)
        super.onStop()
    }

    override fun onDestroy() {
        window?.decorView?.removeCallbacks(clearPending)
        if (receiversRegistered) {
            unregisterLocalReceiver(serviceReceiver)
            unregisterLocalReceiver(processorMessageReceiver)
        }
        super.onDestroy()
    }

    /**
     * Opening the legacy screen stored some defaults that the engine's own defaults differ from (ListPreference and
     * EditTextPreference store their default; sliders stored non-zero defaults): crossfeed "5" and reverb "15" among
     * them. Written once per missing key, so the engine plays what this screen shows, as before.
     */
    @Suppress("DEPRECATION")
    private fun persistDefaults() {
        fun file(name: String, vararg values: Pair<Int, Any>) {
            val prefs = getSharedPreferences(name, MODE_MULTI_PROCESS)
            val edit = prefs.edit()
            var changed = false
            for ((keyRes, v) in values) {
                val key = getString(keyRes)
                if (prefs.contains(key)) continue
                when (v) {
                    is Float -> edit.putFloat(key, v)
                    is String -> edit.putString(key, v)
                }
                changed = true
            }
            if (changed) edit.apply()
        }
        file(Constants.PREF_OUTPUT, R.string.key_limiter_threshold to -0.1f, R.string.key_limiter_release to 60f)
        file(Constants.PREF_COMPANDER, R.string.key_compander_timeconstant to 0.22f, R.string.key_compander_tftransforms to "0")
        file(Constants.PREF_BASS, R.string.key_bass_max_gain to 5f)
        file(Constants.PREF_EQ, R.string.key_eq_filter_type to "0", R.string.key_eq_interpolation to "0")
        file(Constants.PREF_DDC, R.string.key_ddc_file to "")
        file(Constants.PREF_CONVOLVER, R.string.key_convolver_file to "", R.string.key_convolver_mode to "0",
            R.string.key_convolver_adv_imp to Constants.DEFAULT_CONVOLVER_ADVIMP)
        file(Constants.PREF_LIVEPROG, R.string.key_liveprog_file to "")
        file(Constants.PREF_TUBE, R.string.key_tube_drive to 2f)
        file(Constants.PREF_STEREOWIDE, R.string.key_stereowide_mode to 60f)
        file(Constants.PREF_CROSSFEED, R.string.key_crossfeed_mode to "5")
        file(Constants.PREF_REVERB, R.string.key_reverb_preset to "15")
    }

    // ------------------------------------------------------------------------------------------------ navigation

    /** Leaves for the home screen, opening it first when this screen was opened on its own. */
    fun returnToHome() {
        if (isTaskRoot) startActivity(PvbGeneral.homeIntent(this))
        finish()
    }

    fun launchSafely(block: () -> Unit) {
        try { block() } catch (_: ActivityNotFoundException) { toast(R.string.no_activity_found) }
    }

    /** Opens the document picker; [then] gets the picked file. */
    fun pickFile(then: (Uri) -> Unit) {
        onImportPicked = then
        try {
            importLauncher.launch(arrayOf("*/*"))
        } catch (ex: Exception) {
            onImportPicked = null
            Timber.i(ex)
            toast(R.string.no_activity_found)
        }
    }

    /** "기본값으로 초기화": every dsp_* file is deleted (pvb_settings stays) and the screen reloads. */
    fun revert() = restoreDspSettings()

    // ------------------------------------------------------------------------------------------------ service

    private fun refreshService() {
        serviceOn = BaseAudioProcessorService.activeServices > 0
    }

    /** The legacy power button: on asks for capture (first-run notice first), off stops the service. */
    fun setService(on: Boolean) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
            window.decorView.performHapticFeedback(if (on) HapticFeedbackConstants.CONFIRM else HapticFeedbackConstants.REJECT)
        if (on) {
            startPending = true
            requestCapturePermission()
        } else {
            startPending = false
            if (isRoot()) RootAudioProcessorService.stopService(this) else RootlessAudioProcessorService.stop(this)
        }
        refreshService()
    }

    private fun requestCapturePermission() {
        if (FirstRun.mustShowNotice(PvbBuild.general, PvbBuild.firstRunConfirmed)) {
            startPending = false
            PvbGeneral.showFirstRunNotice(this, onConfirmed = {
                PvbGeneral.maybeShowUnmeasuredNotice(this)
                startPending = true
                requestCapturePermission()
            })
            return
        }
        if (isRoot()) {
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
        }
    }

    /** The service reports its start by broadcast; if it never does, stop showing "starting". */
    private fun armPendingTimeout() {
        window.decorView.removeCallbacks(clearPending)
        window.decorView.postDelayed(clearPending, 5000L)
    }

    /** MainActivity's Android 15 notice. Returns true when it sent the user to the setup screens. */
    private fun showAndroid15Alert(): Boolean {
        if (!SdkCheck.isVanillaIceCream || hasProjectMediaAppOp()) return false
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.android_15_screenshare_warning_title)
            .setMessage(R.string.android_15_screenshare_keyguard_warning)
            .setCancelable(false)
            .setPositiveButton(R.string.continue_action) { _, _ ->
                startActivity(Intent(this, OnboardingActivity::class.java).putExtra(OnboardingActivity.EXTRA_FIX_PERMS, false))
                finish()
            }
            .show()
        return true
    }

    // ------------------------------------------------------------------------------------------------ opened files

    /** A file opened with the app (MainActivity.handleFileIntent): presets, Liveprog scripts, VDC and impulse responses. */
    private fun handleFileIntent(uri: Uri) {
        val name = StorageUtils.queryName(this, uri)
        if (name == null) {
            toast(getString(R.string.intent_import_error_file_uri))
            return
        }
        pendingImport = when {
            name.endsWith(".tar") -> {
                val valid = StorageUtils.openInputStreamSafe(this, uri)?.use { Preset.validate(it) } ?: true
                if (!valid) {
                    alert = getString(R.string.filelibrary_corrupted_title) to getString(R.string.filelibrary_corrupted)
                    return
                }
                PendingImport(uri, name, R.string.intent_import_preset, "Presets", null, null, null)
            }
            name.endsWith(".eel") -> PendingImport(uri, name, R.string.intent_import_liveprog, "Liveprog",
                Constants.PREF_LIVEPROG, R.string.key_liveprog_file, R.string.key_liveprog_enable)
            name.endsWith(".vdc") -> PendingImport(uri, name, R.string.intent_import_vdc, "DDC",
                Constants.PREF_DDC, R.string.key_ddc_file, R.string.key_ddc_enable)
            name.endsWith(".irs") || name.endsWith(".wav") -> PendingImport(uri, name, R.string.intent_import_irs, "Convolver",
                Constants.PREF_CONVOLVER, R.string.key_convolver_file, R.string.key_convolver_enable)
            else -> null
        }
    }

    /** The answer to [pendingImport]: [use] false = "가져오기만", true = "가져오기 및 활성화". */
    fun finishImport(p: PendingImport, use: Boolean) {
        pendingImport = null
        val file = StorageUtils.importFile(this, File(getExternalFilesDir(null), p.subDir).absolutePath, p.uri)
        if (file == null) {
            Timber.w("Failed to import file '${p.uri}'")
            toast(getString(R.string.intent_import_fail, p.name))
            return
        }
        if (!use) {
            toast(getString(R.string.intent_import_success, p.name))
            return
        }
        CoroutineScope(Dispatchers.Default).launch {
            delay(250L)
            if (p.name.endsWith(".tar")) {
                try {
                    StorageUtils.openInputStreamSafe(this@RnAdvancedActivity, p.uri)?.use { Preset.load(this@RnAdvancedActivity, it) }
                } catch (ex: Exception) {
                    withContext(Dispatchers.Main) {
                        alert = getString(R.string.filelibrary_corrupted_title) to (ex.localizedMessage ?: "")
                    }
                }
            } else if (p.namespace != null && p.keyRes != null && p.enableKeyRes != null) {
                @Suppress("DEPRECATION")
                getSharedPreferences(p.namespace, MODE_MULTI_PROCESS).edit()
                    .putBoolean(getString(p.enableKeyRes), true)
                    .putString(getString(p.keyRes), file.absolutePath)
                    .apply()
            }
            delay(250L)
            broadcastPresetLoadEvent()
            withContext(Dispatchers.Main) { toast(getString(R.string.intent_import_select_success, p.name)) }
        }
    }

    companion object {
        fun intent(context: Context): Intent = Intent(context, RnAdvancedActivity::class.java)

    }
}

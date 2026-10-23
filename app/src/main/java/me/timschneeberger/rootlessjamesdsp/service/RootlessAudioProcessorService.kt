package me.timschneeberger.rootlessjamesdsp.service

import android.annotation.SuppressLint
import android.app.Activity
import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioPlaybackConfiguration
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.AudioTimestamp
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.Process
import androidx.annotation.RequiresApi
import androidx.core.content.getSystemService
import androidx.core.math.MathUtils.clamp
import androidx.lifecycle.Observer
import androidx.lifecycle.asLiveData
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.flavor.CrashlyticsImpl
import me.timschneeberger.rootlessjamesdsp.interop.JamesDspLocalEngine
import me.timschneeberger.rootlessjamesdsp.interop.ProcessorMessageHandler
import me.timschneeberger.rootlessjamesdsp.model.IEffectSession
import me.timschneeberger.rootlessjamesdsp.model.preference.AudioEncoding
import me.timschneeberger.rootlessjamesdsp.model.room.AppBlocklistDatabase
import me.timschneeberger.rootlessjamesdsp.model.room.AppBlocklistRepository
import me.timschneeberger.rootlessjamesdsp.model.room.BlockedApp
import me.timschneeberger.rootlessjamesdsp.model.rootless.SessionRecordingPolicyEntry
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain
import me.timschneeberger.rootlessjamesdsp.pvb.PvbController
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbEngine
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevelWatcher
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzRing
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzDiagnostics
import me.timschneeberger.rootlessjamesdsp.session.rootless.OnRootlessSessionChangeListener
import me.timschneeberger.rootlessjamesdsp.session.rootless.RootlessSessionDatabase
import me.timschneeberger.rootlessjamesdsp.session.rootless.RootlessSessionManager
import me.timschneeberger.rootlessjamesdsp.session.rootless.SessionRecordingPolicyManager
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.Constants.ACTION_PREFERENCES_UPDATED
import me.timschneeberger.rootlessjamesdsp.utils.Constants.ACTION_SAMPLE_RATE_UPDATED
import me.timschneeberger.rootlessjamesdsp.utils.Constants.ACTION_SERVICE_HARD_REBOOT_CORE
import me.timschneeberger.rootlessjamesdsp.utils.Constants.ACTION_SERVICE_RELOAD_LIVEPROG
import me.timschneeberger.rootlessjamesdsp.utils.Constants.ACTION_SERVICE_SOFT_REBOOT_CORE
import me.timschneeberger.rootlessjamesdsp.utils.extensions.CompatExtensions.getParcelableAs
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.registerLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.sendLocalBroadcast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.unregisterLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission
import me.timschneeberger.rootlessjamesdsp.utils.notifications.Notifications
import me.timschneeberger.rootlessjamesdsp.utils.notifications.ServiceNotificationHelper
import me.timschneeberger.rootlessjamesdsp.utils.preferences.Preferences
import me.timschneeberger.rootlessjamesdsp.utils.sdkAbove
import org.koin.android.ext.android.inject
import timber.log.Timber
import java.io.IOException
import java.util.concurrent.locks.LockSupport
import org.json.JSONObject


@RequiresApi(Build.VERSION_CODES.Q)
class RootlessAudioProcessorService : BaseAudioProcessorService() {
    // System services
    private lateinit var mediaProjectionManager: MediaProjectionManager
    private lateinit var notificationManager: NotificationManager
    private lateinit var audioManager: AudioManager

    // Media projection token
    private var mediaProjection: MediaProjection? = null
    private var mediaProjectionStartIntent: Intent? = null

    // Processing
    @Volatile
    private var recreateRecorderRequested = false
    private lateinit var engine: JamesDspLocalEngine
    // PVB speaker engine; while the PVB card is on it is the last stage of the processing loop, after any JamesDSP
    // effects (JdspChain)
    private lateinit var pvbEngine: PvbEngine
    private lateinit var pvbController: PvbController
    // Alpha 3.1 per-song level memory (reads media sessions through sessionManager)
    private lateinit var trackLevelWatcher: TrackLevelWatcher
    private lateinit var buzzDiagnostics: BuzzDiagnostics
    @Volatile private var diagnosticGain = 1f
    private val mainHandler = Handler(Looper.getMainLooper())

    // Audio thread lifecycle (all fields below: main thread only). One AudioWorker per generation; a stopped
    // generation whose thread has not ended yet stays in `lingering`, and nothing it may still use (engines, a new
    // generation) is freed or started until a watcher thread has seen it end.
    private var worker: AudioWorker? = null
    private var lingering: AudioWorker? = null
    private var startWhenStopped = false
    private var closeEnginesWhenStopped = false
    private var enginesClosed = false
    private val isRunning: Boolean
        get() = worker != null || lingering != null

    // Session management
    private lateinit var sessionManager: RootlessSessionManager
    private var sessionLossRetryCount = 0
    @Volatile
    private var notificationSessions: Array<IEffectSession> = emptyArray()

    // Idle detection (read by the audio thread)
    @Volatile
    private var isProcessorIdle = false
    @Volatile
    private var suspendOnIdle = false
    // Deep sleep (battery, off by default): seconds of paused output before the capture stops too ("0" = off)
    @Volatile
    private var deepSleepSetting = "0"
    // Silence before the output rests, in seconds ("2" / "5" / "10")
    @Volatile
    private var holdSetting = "2"
    // Set by a playback change: the audio thread looks for music often for a short while (see AudioWorker.run)
    @Volatile
    private var playbackChanged = false

    // Deep sleep: any playback change (a player starting) wakes the audio thread to check for music
    private val playbackCallback = object : AudioManager.AudioPlaybackCallback() {
        override fun onPlaybackConfigChanged(configs: MutableList<AudioPlaybackConfiguration>?) {
            playbackChanged = true
            worker?.wake()
        }
    }

    /** Shows or clears "deep sleep" in the status notification (called from the audio thread). */
    private fun showDeepSleep(on: Boolean) {
        mainHandler.post {
            ServiceNotificationHelper.powerState = if (on) getString(R.string.powersave_deep_active) else ""
            if (!isServiceDisposing) ServiceNotificationHelper.pushServiceNotification(this, notificationSessions)
        }
    }

    // Exclude restricted apps flag
    private var excludeRestrictedSessions = false

    // Termination flag
    @Volatile
    private var isServiceDisposing = false

    // Shared preferences
    private val preferences: Preferences.App by inject()
    private val preferencesVar: Preferences.Var by inject()

    // Room databases
    private val applicationScope = CoroutineScope(SupervisorJob())
    private val blockedAppDatabase by lazy { AppBlocklistDatabase.getDatabase(this, applicationScope) }
    private val blockedAppRepository by lazy { AppBlocklistRepository(blockedAppDatabase.appBlocklistDao()) }
    private val blockedApps by lazy { blockedAppRepository.blocklist.asLiveData() }
    private val blockedAppObserver = Observer<List<BlockedApp>?> {
        Timber.d("blockedAppObserver: Database changed; ignored=${!isRunning}")
        if(isRunning)
            recreateRecorderRequested = true
    }

    override fun onCreate() {
        super.onCreate()
        // General build: a previous instance that never stopped was killed (FirstWeek / KillWatch).
        me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore.onServiceCreated(this)

        // Get reference to system services
        audioManager = getSystemService<AudioManager>()!!
        mediaProjectionManager = getSystemService<MediaProjectionManager>()!!
        notificationManager = getSystemService<NotificationManager>()!!

        // Setup session manager
        sessionManager = RootlessSessionManager(this)
        sessionManager.sessionDatabase.setOnSessionLossListener(onSessionLossListener)
        sessionManager.sessionDatabase.setOnAppProblemListener(onAppProblemListener)
        sessionManager.sessionDatabase.registerOnSessionChangeListener(onSessionChangeListener)
        sessionManager.sessionPolicyDatabase.registerOnRestrictedSessionChangeListener(onSessionPolicyChangeListener)

        // Setup core engine
        engine = JamesDspLocalEngine(this, ProcessorMessageHandler())
        engine.syncWithPreferences()

        // Setup PVB engine and its control layer
        pvbEngine = PvbEngine(48000)
        pvbController = PvbController(this, pvbEngine)
        // JamesDSP -> PVB chain: seal the overlapping JamesDSP modules while PVB processes (never written to prefs)
        pvbController.onSealChanged = { sealed -> engine.pvbSeal = sealed }
        pvbController.start()
        trackLevelWatcher = TrackLevelWatcher(this, sessionManager)
        // Per-song memory reads track titles: it does not exist in the general build (RECORD_FEATURES = false).
        if (BuildConfig.RECORD_FEATURES) trackLevelWatcher.start()
        buzzDiagnostics = BuzzDiagnostics(this, pvbEngine,
            changed = { updateBuzzNotification() },
            gain = { gain -> diagnosticGain = gain; worker?.setDiagnosticGain(gain) },
            ioSnapshot = { (worker?.diagnosticIo() ?: JSONObject().put("worker_running", false))
                .put("source_session_packages", org.json.JSONArray(notificationSessions.map { it.packageName ?: "uid:${it.uid}" })) },
            result = { message -> ServiceNotificationHelper.pushBuzzResult(this, message) })
        updateBuzzNotification()

        // Setup general-purpose broadcast receiver
        val filter = IntentFilter()
        filter.addAction(ACTION_PREFERENCES_UPDATED)
        filter.addAction(ACTION_SAMPLE_RATE_UPDATED)
        filter.addAction(ACTION_SERVICE_RELOAD_LIVEPROG)
        filter.addAction(ACTION_SERVICE_HARD_REBOOT_CORE)
        filter.addAction(ACTION_SERVICE_SOFT_REBOOT_CORE)
        registerLocalReceiver(broadcastReceiver, filter)

        // Setup shared preferences
        preferences.registerOnSharedPreferenceChangeListener(preferencesListener)
        loadFromPreferences(getString(R.string.key_powersave_suspend))
        loadFromPreferences(getString(R.string.key_powersave_deep))
        loadFromPreferences(getString(R.string.key_powersave_hold))
        audioManager.registerAudioPlaybackCallback(playbackCallback, Handler(Looper.getMainLooper()))
        loadFromPreferences(getString(R.string.key_session_exclude_restricted))

        // Setup database observer
        blockedApps.observeForever(blockedAppObserver)

        notificationManager.cancel(Notifications.ID_SERVICE_STARTUP)

        // No need to recreate in this stage
        recreateRecorderRequested = false

        // Launch foreground service
        startForeground(
            Notifications.ID_SERVICE_STATUS,
            ServiceNotificationHelper.createServiceNotification(this, arrayOf()),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
        )
    }

    override fun onStartCommand(intent: Intent, flags: Int, startId: Int): Int {

        Timber.d("onStartCommand")

        // Buzz diagnostics (recordings) do not exist in the general build.
        if (!BuildConfig.RECORD_FEATURES &&
            intent.action in setOf(ACTION_BUZZ_TOGGLE, ACTION_BUZZ_SOLO, ACTION_BUZZ_CAPTURE)) return START_NOT_STICKY

        // Handle intent action
        when (intent.action) {
            null -> {
                Timber.wtf("onStartCommand: intent.action is null")
            }
            ACTION_START -> {
                Timber.d("Starting service")
            }
            ACTION_STOP -> {
                Timber.d("Stopping service")
                me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore.onUserStopped(this)
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_BUZZ_TOGGLE -> {
                if (worker != null) buzzDiagnostics.toggle()
                else if (!isServiceDisposing) stopSelf()
                return START_NOT_STICKY
            }
            ACTION_BUZZ_SOLO -> {
                if (worker != null && buzzDiagnostics.armed && !buzzDiagnostics.busy) {
                    val on = pvbEngine.diagnosticParams?.get(PvbParam.DIAGNOSTIC_SOLO) == 1f
                    pvbController.setDiagnosticSolo(!on)
                    updateBuzzNotification()
                } else if (worker == null && !isServiceDisposing) stopSelf()
                return START_NOT_STICKY
            }
            ACTION_BUZZ_CAPTURE -> {
                if (worker != null) {
                    if (!buzzDiagnostics.trigger()) ServiceNotificationHelper.pushBuzzResult(this,
                        "진단을 먼저 켜고, 현재 기록이 끝난 뒤 다시 눌러 주세요. 블라인드 비교·측정 중에는 사용할 수 없습니다.")
                } else if (!isServiceDisposing) stopSelf()
                return START_NOT_STICKY
            }
        }

        if (isRunning) {
            return START_NOT_STICKY
        }

        // Cancel outdated notifications
        notificationManager.cancel(Notifications.ID_SERVICE_SESSION_LOSS)
        notificationManager.cancel(Notifications.ID_SERVICE_APPCOMPAT)

        // Setup media projection
        mediaProjectionStartIntent = intent.extras?.getParcelableAs(EXTRA_MEDIA_PROJECTION_DATA)

        mediaProjection = try {
            mediaProjectionManager.getMediaProjection(
                Activity.RESULT_OK,
                mediaProjectionStartIntent!!
            )
        }
        catch (ex: Exception) {
            Timber.e("Failed to acquire media projection")
            sendLocalBroadcast(Intent(Constants.ACTION_DISCARD_AUTHORIZATION))
            Timber.e(ex)
            null
        }

        mediaProjection?.registerCallback(projectionCallback, Handler(Looper.getMainLooper()))

        if (mediaProjection != null) {
            startRecording()
            me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore.onCaptureStarted(this)
            sendLocalBroadcast(Intent(Constants.ACTION_SERVICE_STARTED))
        } else {
            Timber.w("Failed to capture audio")
            stopSelf()
        }

        return START_REDELIVER_INTENT
    }

    override fun onDestroy() {
        isServiceDisposing = true
        me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore.onServiceDestroyed(this)
        startWhenStopped = false
        buzzDiagnostics.close()

        // Stop recording; release the engines only once the audio thread has really ended
        trackLevelWatcher.stop()
        pvbController.onSealChanged = null  // the JamesDSP engine is being closed: no re-sync on the way out
        pvbController.stop()
        if (stopRecording()) closeEngines() else closeEnginesWhenStopped = true

        // Stop foreground service
        stopForeground(STOP_FOREGROUND_REMOVE)

        // Notify app about service termination
        sendLocalBroadcast(Intent(Constants.ACTION_SERVICE_STOPPED))

        // Unregister database observer
        blockedApps.removeObserver(blockedAppObserver)

        // Unregister receivers and release resources
        unregisterLocalReceiver(broadcastReceiver)
        mediaProjection?.unregisterCallback(projectionCallback)
        mediaProjection = null

        sessionManager.sessionPolicyDatabase.unregisterOnRestrictedSessionChangeListener(onSessionPolicyChangeListener)
        sessionManager.sessionDatabase.unregisterOnSessionChangeListener(onSessionChangeListener)
        sessionManager.destroy()

        preferences.unregisterOnSharedPreferenceChangeListener(preferencesListener)
        try { audioManager.unregisterAudioPlaybackCallback(playbackCallback) } catch (_: Exception) {}
        notificationManager.cancel(Notifications.ID_SERVICE_STATUS)

        stopSelf()
        super.onDestroy()
    }

    // Preferences listener
    private val preferencesListener = SharedPreferences.OnSharedPreferenceChangeListener {
            _, key ->
        loadFromPreferences(key)
    }

    // Projection termination callback. The capture session is gone: always clean up and stop (the audio thread,
    // the muted source sessions and the notification); only the way the user is told depends on the screen.
    private val projectionCallback = object: MediaProjection.Callback() {
        override fun onStop() {
            if(isServiceDisposing) {
                // Planned shutdown
                return
            }

            Timber.w("Capture permission revoked. Stopping service.")

            sendLocalBroadcast(Intent(Constants.ACTION_DISCARD_AUTHORIZATION))

            // A toast would be disruptive while the app's own screen is in front (it shows the state itself)
            if(!preferencesVar.get<Boolean>(R.string.key_is_activity_active))
                this@RootlessAudioProcessorService.toast(getString(R.string.capture_permission_revoked_toast))

            notificationManager.cancel(Notifications.ID_SERVICE_STATUS)
            stopSelf()
        }
    }

    // General purpose broadcast receiver
    private val broadcastReceiver: BroadcastReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                ACTION_SAMPLE_RATE_UPDATED -> engine.syncWithPreferences(arrayOf(Constants.PREF_CONVOLVER))
                ACTION_PREFERENCES_UPDATED -> engine.syncWithPreferences()
                ACTION_SERVICE_RELOAD_LIVEPROG -> engine.syncWithPreferences(arrayOf(Constants.PREF_LIVEPROG))
                ACTION_SERVICE_HARD_REBOOT_CORE -> restartRecording()
                ACTION_SERVICE_SOFT_REBOOT_CORE -> requestAudioRecordRecreation()
            }
        }
    }

    // Session loss listener
    private val onSessionLossListener = object: RootlessSessionDatabase.OnSessionLossListener {
        override fun onSessionLost(sid: Int) {
            // Push notification if enabled
            if(!preferences.get<Boolean>(R.string.key_session_loss_ignore)) {
                // Check if retry count exceeded
                if(sessionLossRetryCount < SESSION_LOSS_MAX_RETRIES) {
                    // Retry
                    sessionLossRetryCount++
                    Timber.d("Session lost. Retry count: $sessionLossRetryCount/$SESSION_LOSS_MAX_RETRIES")
                    sessionManager.pollOnce(false)
                    restartRecording()
                    return
                }
                else {
                    sessionLossRetryCount = 0
                    Timber.d("Giving up on saving session. User interaction required.")
                }

                // Request users attention
                notificationManager.cancel(Notifications.ID_SERVICE_STATUS)
                ServiceNotificationHelper.pushSessionLossNotification(this@RootlessAudioProcessorService, mediaProjectionStartIntent)
                this@RootlessAudioProcessorService.toast(getString(R.string.session_control_loss_toast), false)
                Timber.w("Terminating service due to session loss")
                stopSelf()
            }
        }
    }

    // Session change listener
    private val onSessionChangeListener = object : OnRootlessSessionChangeListener {
        override fun onSessionChanged(sessionList: HashMap<Int, IEffectSession>) {
            isProcessorIdle = sessionList.size == 0
            Timber.d("onSessionChanged: isProcessorIdle=$isProcessorIdle")
            worker?.wake()

            notificationSessions = sessionList.values.toTypedArray()

            ServiceNotificationHelper.pushServiceNotification(
                this@RootlessAudioProcessorService,
                notificationSessions
            )
        }
    }

    // App problem listener
    private val onAppProblemListener = object : RootlessSessionDatabase.OnAppProblemListener {
        override fun onAppProblemDetected(uid: Int) {
            // Push notification if enabled
            if(!preferences.get<Boolean>(R.string.key_session_app_problem_ignore)) {
                // Request users attention
                notificationManager.cancel(Notifications.ID_SERVICE_STATUS)

                // Determine if we should redirect instantly, or push a non-intrusive notification
                if(preferencesVar.get<Boolean>(R.string.key_is_activity_active) ||
                    preferencesVar.get<Boolean>(R.string.key_is_app_compat_activity_active)) {
                    startActivity(
                        ServiceNotificationHelper.createAppTroubleshootIntent(
                            this@RootlessAudioProcessorService,
                            mediaProjectionStartIntent,
                            uid,
                            directLaunch = true
                        )
                    )
                    notificationManager.cancel(Notifications.ID_SERVICE_APPCOMPAT)
                }
                else
                    ServiceNotificationHelper.pushAppIssueNotification(this@RootlessAudioProcessorService, mediaProjectionStartIntent, uid)

                this@RootlessAudioProcessorService.toast(getString(R.string.session_app_compat_toast), false)
                Timber.w("Terminating service due to app incompatibility; redirect user to troubleshooting options")
                stopSelf()
            }
        }
    }

    // Session policy change listener
    private val onSessionPolicyChangeListener = object : SessionRecordingPolicyManager.OnSessionRecordingPolicyChangeListener {
        override fun onSessionRecordingPolicyChanged(sessionList: HashMap<String, SessionRecordingPolicyEntry>, isMinorUpdate: Boolean) {
            if(!this@RootlessAudioProcessorService.excludeRestrictedSessions) {
                Timber.d("onRestrictedSessionChanged: blocked; excludeRestrictedSessions disabled")
                return
            }

            if(!isMinorUpdate) {
                Timber.d("onRestrictedSessionChanged: major update detected; requesting soft-reboot")
                requestAudioRecordRecreation()
            }
            else {
                Timber.d("onRestrictedSessionChanged: minor update detected")
            }
        }
    }

    private fun loadFromPreferences(key: String?){
        when (key) {
            getString(R.string.key_powersave_suspend) -> {
                suspendOnIdle = preferences.get<Boolean>(R.string.key_powersave_suspend)
                Timber.d("Suspend on idle set to $suspendOnIdle")
                worker?.wake()
            }
            getString(R.string.key_powersave_deep) -> {
                deepSleepSetting = preferences.get<String>(R.string.key_powersave_deep)
                Timber.d("Deep sleep set to $deepSleepSetting")
                worker?.wake()
            }
            getString(R.string.key_powersave_hold) -> {
                holdSetting = preferences.get<String>(R.string.key_powersave_hold)
                Timber.d("Output rest after ${holdSetting}s of silence")
            }
            getString(R.string.key_session_exclude_restricted) -> {
                excludeRestrictedSessions = preferences.get<Boolean>(R.string.key_session_exclude_restricted)
                Timber.d("Exclude restricted set to $excludeRestrictedSessions")

                requestAudioRecordRecreation()
            }
        }
    }

    // Request recreation of the AudioRecord object to update AudioPlaybackRecordingConfiguration
    fun requestAudioRecordRecreation() {
        if(isServiceDisposing) {
            Timber.e("recreateAudioRecorder: service already disposing")
            return
        }

        recreateRecorderRequested = true
    }

    // Start recording thread
    @SuppressLint("BinaryOperationInTimber")
    private fun startRecording() {
        if (worker != null) return
        if (lingering != null) {
            // the previous generation has not ended yet: start when it has
            startWhenStopped = true
            return
        }
        if (isServiceDisposing) return

        // Sanity check
        if (!hasRecordPermission()) {
            Timber.e("Record audio permission missing. Can't record")
            stopSelf()
            return
        }

        // Load preferences
        val encoding = AudioEncoding.fromInt(
            preferences.get<String>(R.string.key_audioformat_encoding).toIntOrNull() ?: 1
        )
        val bufferSize = preferences.get<Float>(R.string.key_audioformat_buffersize).toInt().coerceAtLeast(64)
        val bufferSizeBytes = when (encoding) {
            AudioEncoding.PcmFloat -> bufferSize * Float.SIZE_BYTES
            else -> bufferSize * Short.SIZE_BYTES
        }
        val encodingFormat = when (encoding) {
            AudioEncoding.PcmShort -> AudioFormat.ENCODING_PCM_16BIT
            else -> AudioFormat.ENCODING_PCM_FLOAT
        }
        val sampleRate = clamp(determineSamplingRate(), 44100, 48000)

        Timber.i("Sample rate: $sampleRate; Encoding: ${encoding.name}; " +
                "Buffer size: $bufferSize; Buffer size (bytes): $bufferSizeBytes ; " +
                "HAL buffer size (bytes): ${determineBufferSize()}")

        // Create recorder and track
        val recorder: AudioRecord
        val track: AudioTrack
        try {
            recorder = buildAudioRecord(encodingFormat, sampleRate, bufferSizeBytes)
        }
        catch(ex: Exception) {
            Timber.e("Failed to create initial audio record")
            Timber.e(ex)
            stopSelf()
            return
        }
        try {
            track = buildAudioTrack(encodingFormat, sampleRate, bufferSizeBytes)
        }
        catch(ex: Exception) {
            Timber.e("Failed to create initial audio track")
            Timber.e(ex)
            recorder.release()
            stopSelf()
            return
        }

        if(engine.sampleRate.toInt() != sampleRate) {
            Timber.d("Sampling rate changed to ${sampleRate}Hz")
            engine.sampleRate = sampleRate.toFloat()
        }
        pvbEngine.setSampleRate(sampleRate)
        pvbController.attachTrack(track)

        val w = AudioWorker(encoding, encodingFormat, sampleRate, bufferSize, bufferSizeBytes, recorder, track)
        worker = w
        buzzDiagnostics.attach(sampleRate)
        w.thread.start()
    }

    /**
     * Stops the running audio generation: asks its thread to end, unblocks its blocking read/write, and waits up to
     * [STOP_JOIN_MS] (main thread, bounded). Returns true when no audio thread of this service is alive any more.
     * Otherwise the generation is kept in [lingering]; a watcher thread waits for it without limit and then runs
     * whatever was deferred (closing the engines or starting the next generation).
     */
    private fun stopRecording(): Boolean {
        val w = worker ?: return lingering == null
        buzzDiagnostics.detach("audio_worker_stopped")
        worker = null
        w.requestStop()
        try {
            w.thread.join(STOP_JOIN_MS)
        } catch (e: InterruptedException) {
            Thread.currentThread().interrupt()
        }
        if (!w.thread.isAlive) return lingering == null

        Timber.w("Audio thread did not end within $STOP_JOIN_MS ms; waiting for it in the background")
        lingering = w
        Thread({
            while (w.thread.isAlive) {
                try {
                    w.thread.join()
                } catch (ignored: InterruptedException) {
                }
            }
            mainHandler.post { onLingeringEnded(w) }
        }, "pvb-audio-reaper").start()
        return false
    }

    private fun onLingeringEnded(w: AudioWorker) {
        if (lingering !== w) return
        lingering = null
        Timber.d("Lingering audio thread has ended")
        if (closeEnginesWhenStopped) {
            closeEnginesWhenStopped = false
            closeEngines()
        } else if (startWhenStopped && !isServiceDisposing) {
            startWhenStopped = false
            startRecording()
        }
    }

    /** Frees the native engines. Only called when no audio thread can use them any more. */
    private fun closeEngines() {
        if (enginesClosed) return
        enginesClosed = true
        engine.close()
        pvbEngine.close()
    }

    private fun updateBuzzNotification() {
        if (!buzzDiagnostics.armed) pvbController.setDiagnosticSolo(false)
        val solo = pvbEngine.diagnosticParams?.get(PvbParam.DIAGNOSTIC_SOLO) == 1f
        ServiceNotificationHelper.buzzArmed = buzzDiagnostics.armed
        ServiceNotificationHelper.buzzBusy = buzzDiagnostics.busy
        ServiceNotificationHelper.buzzState = buzzDiagnostics.stateText + if (solo) " · 생성 저음만 듣는 중" else ""
        ServiceNotificationHelper.buzzServiceActive = !isServiceDisposing
        ServiceNotificationHelper.pushBuzzControl(this)
        if (!isServiceDisposing) ServiceNotificationHelper.pushServiceNotification(this, notificationSessions)
    }

    // Hard restart recording thread
    fun restartRecording() {
        if(isServiceDisposing) {
            Timber.e("restartRecording: service already disposing")
            return
        }

        recreateRecorderRequested = false
        if (stopRecording()) startRecording() else startWhenStopped = true
    }

    /**
     * One generation of the capture -> process -> playback loop. The recorder and the track belong to this
     * generation's thread: only that thread reads, writes, recreates and releases them. Other threads may only call
     * [requestStop], which stops/pauses them under [ioLock] to unblock a blocking read or write.
     */
    private inner class AudioWorker(
        private val encoding: AudioEncoding,
        private val encodingFormat: Int,
        private val sampleRate: Int,
        private val bufferSize: Int,
        private val bufferSizeBytes: Int,
        initialRecorder: AudioRecord,
        initialTrack: AudioTrack,
    ) : Runnable {
        @Volatile
        var stopRequested = false
            private set
        private val ioLock = Any()
        @Volatile
        private var recorder: AudioRecord = initialRecorder
        @Volatile
        private var track: AudioTrack = initialTrack
        private var writeFailures = 0
        @Volatile private var writtenSamples = 0L
        @Volatile private var readProblems = 0L
        @Volatile private var writeProblems = 0L
        @Volatile private var lastReadCode = 0
        @Volatile private var lastWriteCode = 0
        @Volatile private var trackGeneration = 0
        @Volatile private var lastGainResult = AudioTrack.SUCCESS
        val thread = Thread(this, "pvb-audio")
        // Battery: output paused after a long silence (audio thread only; see SilenceGate)
        private val silenceGate = SilenceGate.forRate(sampleRate)
        private var outputPaused = false
        /** Deep sleep: the capture is stopped too (the output was already paused by the silence gate). */
        private var deepSleeping = false
        /** Set when deep sleep ends: run the engines over a little silence first (see [run]). */
        private var flushPending = false
        /** Deep sleep: short waits left after a playback change (a starting player is counted as music a little later). */
        private var deepFastPolls = 0
        /** Last time (elapsedRealtimeNanos) the paused loop asked whether music plays: at most once a second. */
        private var lastMusicCheckNs = 0L

        /** Any thread: ends an idle wait early (sessions or the power-save setting changed). */
        fun wake() = LockSupport.unpark(thread)

        fun setDiagnosticGain(gain: Float) {
            try { lastGainResult = track.setVolume(gain) }
            catch (_: Exception) { lastGainResult = AudioTrack.ERROR_INVALID_OPERATION }
        }

        /** Main thread. These are approximate I/O observations, never an acoustic playback timestamp. */
        fun diagnosticIo(): JSONObject {
            val obj = JSONObject().put("worker_running", !stopRequested).put("sample_rate_hz", sampleRate)
                .put("encoding", encoding.toString()).put("buffer_samples", bufferSize)
                .put("track_generation", trackGeneration).put("written_samples_this_track", writtenSamples)
                .put("read_problem_count", readProblems).put("write_problem_count", writeProblems)
                .put("last_read_problem_code", lastReadCode).put("last_write_problem_code", lastWriteCode)
                .put("diagnostic_track_gain_requested", diagnosticGain)
                .put("last_diagnostic_gain_result", lastGainResult)
            try {
                val t = track
                val head = t.playbackHeadPosition.toLong() and 0xffffffffL
                obj.put("track_playback_head_frames_unsigned32", head)
                    .put("track_queued_frames_estimate", maxOf(0L, writtenSamples / 2 - head))
                    .put("track_underrun_count", t.underrunCount)
                val stamp = AudioTimestamp()
                if (t.getTimestamp(stamp)) obj.put("track_timestamp_frame", stamp.framePosition)
                    .put("track_timestamp_monotonic_ns", stamp.nanoTime)
            } catch (_: Exception) { obj.put("track_observation_unavailable", true) }
            return obj
        }

        /** Any thread: asks the audio thread to end and unblocks its I/O. Never releases anything itself. */
        fun requestStop() {
            synchronized(ioLock) {
                stopRequested = true
                try { recorder.stop() } catch (ignored: Exception) {}
                try { track.pause() } catch (ignored: Exception) {}
                try { track.flush() } catch (ignored: Exception) {}
            }
            thread.interrupt()
        }

        private fun requestServiceStop() {
            mainHandler.post {
                if (worker === this) {
                    Timber.w("Audio thread gave up; stopping service")
                    stopSelf()
                }
            }
        }

        override fun run() {
            try {
                // Rebuilding the processing pipeline must not overwrite the current
                // session-aware notification with a false "idle" state.
                ServiceNotificationHelper.pushServiceNotification(
                    applicationContext,
                    notificationSessions,
                )
                loop()
            } catch (e: Exception) {
                if (!stopRequested) {
                    Timber.e("Exception in audio thread raised")
                    Timber.e(e)
                    requestServiceStop()
                }
            } finally {
                buzzDiagnostics.audioDiscontinuity("audio_worker_ended")
                if (deepSleeping) { deepSleeping = false; showDeepSleep(false) }
                synchronized(ioLock) { stopRequested = true }
                try { recorder.stop() } catch (ignored: Exception) {}
                try { track.stop() } catch (ignored: Exception) {}
                try { recorder.release() } catch (ignored: Exception) {}
                try { track.release() } catch (ignored: Exception) {}
            }
        }

        /** Interruptible pause; false = the thread was interrupted (stop). */
        private fun pause(ms: Long): Boolean = try {
            Thread.sleep(ms)
            true
        } catch (e: InterruptedException) {
            false
        }

        private fun replaceRecorder(): Boolean {
            buzzDiagnostics.audioDiscontinuity("recorder_recreated")
            synchronized(ioLock) {
                if (stopRequested) return false
                try { recorder.stop() } catch (ignored: Exception) {}
                try { recorder.release() } catch (ignored: Exception) {}
                if (mediaProjection == null) {
                    Timber.e("Media projection handle is null, stopping service")
                    requestServiceStop()
                    return false
                }
                recorder = try {
                    buildAudioRecord(encodingFormat, sampleRate, bufferSizeBytes)
                } catch (e: Exception) {
                    Timber.e("Failed to recreate the audio record")
                    Timber.e(e)
                    requestServiceStop()
                    return false
                }
            }
            Timber.d("Recorder recreated")
            return true
        }

        private fun replaceTrack(): Boolean {
            buzzDiagnostics.audioDiscontinuity("track_recreated")
            val newTrack: AudioTrack
            synchronized(ioLock) {
                if (stopRequested) return false
                try { track.pause() } catch (ignored: Exception) {}
                try { track.release() } catch (ignored: Exception) {}
                newTrack = try {
                    buildAudioTrack(encodingFormat, sampleRate, bufferSizeBytes)
                } catch (e: Exception) {
                    Timber.e("Failed to recreate the audio track")
                    Timber.e(e)
                    requestServiceStop()
                    return false
                }
                track = newTrack
                ++trackGeneration
                writtenSamples = 0
                silenceGate.reset()
                outputPaused = false
                try { newTrack.setVolume(diagnosticGain) } catch (_: Exception) {}
            }
            Timber.d("Track recreated")
            pvbController.attachTrack(newTrack)
            return true
        }

        /** Restarts the track paused by the silence gate; a track that cannot play is rebuilt. False = stop. */
        private fun resumeOutput(): Boolean {
            outputPaused = false
            if (playTrack()) {
                Timber.d("Output resumed")
                return true
            }
            if (stopRequested || !replaceTrack()) return false
            if (playTrack()) return true
            if (!stopRequested) requestServiceStop()
            return false
        }

        private fun playTrack(): Boolean {
            synchronized(ioLock) {
                if (stopRequested) return false
                try {
                    track.play()
                } catch (e: Exception) {
                    Timber.w(e, "Could not start the output track")
                    return false
                }
            }
            return true
        }

        /** A failed or empty read: retry after a short pause, recreate the recorder after many in a row. */
        private fun onReadProblem(code: Int, failures: Int): Boolean {
            ++readProblems; lastReadCode = code
            buzzDiagnostics.audioDiscontinuity("capture_read_gap")
            if (code == AudioRecord.ERROR_DEAD_OBJECT || failures >= MAX_IO_FAILURES) {
                Timber.w("AudioRecord.read returned $code ($failures in a row); recreating the recorder")
                return replaceRecorder()
            }
            return pause(IO_RETRY_MS)
        }

        /** Handles a failed write of one block; the rest of that block is dropped. */
        private fun onWriteProblem(code: Int): Boolean {
            ++writeProblems; lastWriteCode = code
            buzzDiagnostics.audioDiscontinuity("playback_write_gap")
            if (code == AudioTrack.ERROR_DEAD_OBJECT || ++writeFailures >= MAX_IO_FAILURES) {
                Timber.w("AudioTrack.write returned $code; recreating the track")
                writeFailures = 0
                return replaceTrack()
            }
            return pause(IO_RETRY_MS)
        }

        /** Writes [n] samples, continuing after partial writes; false = stop (or the track could not be rebuilt). */
        private fun writeAll(buf: FloatArray, n: Int): Boolean {
            val r = PcmPump.writeAll(n, MAX_EMPTY_WRITES, { stopRequested }) { off, len ->
                track.write(buf, off, len, AudioTrack.WRITE_BLOCKING).also { if (it > 0) writtenSamples += it }
            }
            if (r < 0) return onWriteProblem(r)
            if (r == n) writeFailures = 0
            else if (r >= 0 && !stopRequested) {
                ++writeProblems; lastWriteCode = 0; buzzDiagnostics.audioDiscontinuity("playback_partial_drop")
            }
            return !stopRequested
        }

        private fun writeAll(buf: ShortArray, n: Int): Boolean {
            val r = PcmPump.writeAll(n, MAX_EMPTY_WRITES, { stopRequested }) { off, len ->
                track.write(buf, off, len, AudioTrack.WRITE_BLOCKING).also { if (it > 0) writtenSamples += it }
            }
            if (r < 0) return onWriteProblem(r)
            if (r == n) writeFailures = 0
            else if (r >= 0 && !stopRequested) {
                ++writeProblems; lastWriteCode = 0; buzzDiagnostics.audioDiscontinuity("playback_partial_drop")
            }
            return !stopRequested
        }

        // TODO Move all audio-related code to C++
        private fun loop() {
            val isShort = encoding == AudioEncoding.PcmShort
            val floatBuffer = FloatArray(if (isShort) 0 else bufferSize)
            val diagnosticLayer = FloatArray(bufferSize)
            val diagnosticFull = FloatArray(bufferSize)
            val diagnosticTrace = FloatArray(BuzzRing.DETAIL_FIELDS)
            val harmonicTrace = FloatArray(me.timschneeberger.rootlessjamesdsp.pvb.HarmonicHistory.ROWS * me.timschneeberger.rootlessjamesdsp.pvb.HarmonicHistory.FIELDS)
            val floatOutBuffer = FloatArray(if (isShort) 0 else bufferSize)
            // JamesDSP -> PVB chain: JamesDSP output (float) and, for 16-bit capture, the float input/output
            val chainA = FloatArray(bufferSize)
            val chainB = FloatArray(if (isShort) bufferSize else 0)
            val shortBuffer = ShortArray(if (isShort) bufferSize else 0)
            val shortOutBuffer = ShortArray(if (isShort) bufferSize else 0)
            var carry = 0            // 0 or 1: a sample of an incomplete stereo frame kept from the last read
            var readFailures = 0
            var pvbWasActive = false
            var lastRoute: JdspChain.Route? = null
            var historySuspended = false

            /** Runs the engines of [route] over [frames] frames of silence and drops the output (deep sleep). */
            fun processSilence(route: JdspChain.Route, frames: Int) {
                var left = frames * 2
                while (left > 0) {
                    val n = minOf(left, bufferSize and 1.inv())
                    if (n <= 0) return
                    if (isShort) {
                        java.util.Arrays.fill(shortBuffer, 0, n, 0.toShort())
                        when (route) {
                            JdspChain.Route.JDSP_ONLY -> engine.processInt16(shortBuffer, shortOutBuffer, 0, n)
                            JdspChain.Route.PVB_ONLY -> pvbEngine.processShort(shortBuffer, shortOutBuffer, n)
                            JdspChain.Route.JDSP_THEN_PVB -> {
                                JdspChain.shortToFloat(shortBuffer, chainB, n)
                                engine.processFloat(chainB, chainA, 0, n)
                                pvbEngine.processFloat(chainA, chainB, n)
                            }
                        }
                    } else {
                        java.util.Arrays.fill(floatBuffer, 0, n, 0f)
                        when (route) {
                            JdspChain.Route.JDSP_ONLY -> engine.processFloat(floatBuffer, floatOutBuffer, 0, n)
                            JdspChain.Route.PVB_ONLY -> pvbEngine.processFloat(floatBuffer, floatOutBuffer, n)
                            JdspChain.Route.JDSP_THEN_PVB -> {
                                engine.processFloat(floatBuffer, chainA, 0, n)
                                pvbEngine.processFloat(chainA, floatOutBuffer, n)
                            }
                        }
                    }
                    left -= n
                }
            }

            while (!stopRequested) {
                if(recreateRecorderRequested) {
                    recreateRecorderRequested = false
                    Timber.d("Recreating recorder without stopping thread...")
                    if (!replaceRecorder()) return
                    carry = 0
                }

                // Suspend core while idle (not while a developer-mode test sound plays: it needs the loop running)
                if(isProcessorIdle && suspendOnIdle && !me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound.playing) {
                    if (!historySuspended) buzzDiagnostics.audioDiscontinuity("capture_suspended_idle")
                    historySuspended = true
                    synchronized(ioLock) {
                        if (stopRequested) return
                        if(recorder.state == AudioRecord.STATE_INITIALIZED &&
                            recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING)
                            recorder.stop()
                        if(track.state == AudioTrack.STATE_INITIALIZED &&
                            track.playState != AudioTrack.PLAYSTATE_STOPPED) {
                            track.stop()
                            // AudioTrack resets its playback head after stop/resume.
                            writtenSamples = 0; ++trackGeneration
                        }
                    }
                    // PVB holds audio from before the pause in its delay lines; start clean on resume
                    pvbWasActive = false
                    carry = 0
                    silenceGate.reset()
                    outputPaused = false
                    if (deepSleeping) showDeepSleep(false)
                    deepSleeping = false
                    flushPending = false
                    // Wait for a session (onSessionChanged wakes this thread) instead of polling every 50 ms; the
                    // timeout still notices a developer-mode test sound.
                    LockSupport.parkNanos(IDLE_WAIT_NS)
                    // parkNanos keeps the interrupt flag (sleep threw): an interrupt ends the loop as before
                    if (stopRequested || Thread.interrupted()) return
                    continue
                }
                historySuspended = false

                // Deep sleep: the capture stays stopped while nothing plays music (a playback change wakes this
                // thread at once; the timeout notices a research mode or a test sound). It ends when music plays,
                // or when deep sleep stops being allowed; then the capture restarts below and the output resumes on
                // the first sound, as after a normal pause.
                if (deepSleeping) {
                    val researchNow = PvbRuntime.abActive || PvbRuntime.measuring || buzzDiagnostics.armed
                    val stay = suspendOnIdle && SilenceGate.deepFrames(deepSleepSetting, sampleRate) > 0 && !researchNow &&
                        !me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound.playing && !audioManager.isMusicActive
                    if (stay) {
                        synchronized(ioLock) {
                            if (stopRequested) return
                            // a recorder rebuilt meanwhile is not started; one started elsewhere is stopped again
                            if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING)
                                try { recorder.stop() } catch (ignored: Exception) {}
                        }
                        // A playback change may come before the player counts as active: look again every 50 ms
                        // for half a second, so a starting song loses only about 0.1 s; otherwise wait long.
                        if (playbackChanged) {
                            playbackChanged = false
                            deepFastPolls = DEEP_FAST_POLLS
                        }
                        val wait = if (deepFastPolls > 0) { deepFastPolls--; DEEP_FAST_WAIT_NS } else DEEP_WAIT_NS
                        LockSupport.parkNanos(wait)
                        if (stopRequested || Thread.interrupted()) return
                        continue
                    }
                    deepFastPolls = 0
                    showDeepSleep(false)
                    deepSleeping = false
                    silenceGate.rearm()
                    flushPending = true
                    buzzDiagnostics.audioDiscontinuity("capture_resumed_deep_sleep")
                    Timber.d("Deep sleep ended: capture restarts")
                }

                // Resume recorder and track if suspended (never after a stop request: requestStop stopped them)
                synchronized(ioLock) {
                    if (stopRequested) return
                    if(recorder.recordingState == AudioRecord.RECORDSTATE_STOPPED)
                        recorder.startRecording()
                    if(!outputPaused && track.playState != AudioTrack.PLAYSTATE_PLAYING)
                        track.play()
                }

                // Route of this block: JamesDSP alone (PVB not in the path), PVB alone (no JamesDSP effect on, or a
                // research mode: blind comparison, measurement, buzz diagnostics, speaker calibration), or JamesDSP
                // effects -> PVB.
                val research = PvbRuntime.abActive || PvbRuntime.measuring || PvbRuntime.calibrating || buzzDiagnostics.armed
                val route = JdspChain.route(
                    pvbInPath = pvbController.isActive,
                    research = research,
                    jdspEffects = engine.hasEffects,
                )
                val pvbActive = route.pvb
                // PVB engine re-entering the signal path, or JamesDSP joining/leaving in front of it (its delay and
                // level change): drop PVB's stale audio and fade in
                if(pvbActive && (!pvbWasActive || route != lastRoute))
                    pvbEngine.reset()
                if (route != lastRoute) Timber.d("Processing route: ${JdspChain.label(route)}")
                pvbWasActive = pvbActive
                lastRoute = route
                // Back from deep sleep: the engines did not run while the capture was stopped, so a setting changed
                // meanwhile (a switch, a glide, a reset fade) would land on the next sound. Let it finish on half a
                // second of silence now; the output is still paused, so nothing of this is played.
                if (flushPending) {
                    flushPending = false
                    processSilence(route, sampleRate / 2)
                }

                // Read; only the samples actually read are processed and played (never the rest of an old block)
                val got = if (isShort)
                    recorder.read(shortBuffer, carry, bufferSize - carry, AudioRecord.READ_BLOCKING)
                else
                    recorder.read(floatBuffer, carry, bufferSize - carry, AudioRecord.READ_BLOCKING)
                if (stopRequested) return
                if (got <= 0) {
                    // 0: stopped or interrupted; < 0: an error code
                    readFailures++
                    if (!onReadProblem(got, readFailures)) return
                    if (got == AudioRecord.ERROR_DEAD_OBJECT || readFailures >= MAX_IO_FAILURES) {
                        readFailures = 0
                        carry = 0
                    }
                    continue
                }
                readFailures = 0

                // Whole stereo frames only; an odd trailing sample waits for the next read
                val total = carry + got
                val samples = PcmPump.wholeFrames(carry, got)
                if (samples > 0) {
                    // Developer mode (general build): a test sound replaces the captured music, so it takes the same
                    // engine and speaker path. Nothing changes while none plays.
                    if (isShort) me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound.render(shortBuffer, samples / 2, sampleRate)
                    else me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound.render(floatBuffer, samples / 2, sampleRate)
                    val inputSilent = if (isShort) SilenceGate.isSilent(shortBuffer, samples) else SilenceGate.isSilent(floatBuffer, samples)
                    val diagnosticRing = buzzDiagnostics.ring
                    val detailed = diagnosticRing?.detailed == true && !diagnosticRing.frozen
                    pvbEngine.setDiagnosticCapture(detailed && pvbActive)
                    if (isShort) {
                        when (route) {
                            JdspChain.Route.JDSP_ONLY -> engine.processInt16(shortBuffer, shortOutBuffer, 0, samples)
                            JdspChain.Route.PVB_ONLY -> pvbEngine.processShort(shortBuffer, shortOutBuffer, samples)
                            JdspChain.Route.JDSP_THEN_PVB -> {
                                // in float, so JamesDSP boosts above full scale reach the PVB limiter unclipped
                                JdspChain.shortToFloat(shortBuffer, chainB, samples)
                                engine.processFloat(chainB, chainA, 0, samples)
                                pvbEngine.processFloat(chainA, chainB, samples)
                                JdspChain.floatToShort(chainB, shortOutBuffer, samples)
                            }
                        }
                        val haveDetail = detailed && pvbActive && pvbEngine.copyDiagnostic(diagnosticLayer, diagnosticFull, diagnosticTrace, samples)
                        val harmonicRows = if (haveDetail) pvbEngine.copyHarmonicTrace(harmonicTrace) else -1
                        diagnosticRing?.recordShort(shortBuffer, shortOutBuffer, samples,
                            pvbEngine.diagnosticParams, if (pvbActive) pvbEngine.latencyFrames else -1,
                            buzzDiagnostics.observedAlgo, buzzDiagnostics.observedBlend, pvbActive,
                            if (haveDetail) diagnosticLayer else null, if (haveDetail) diagnosticFull else null,
                            if (haveDetail) diagnosticTrace else null, android.os.SystemClock.elapsedRealtimeNanos(),
                            if (harmonicRows >= 0) harmonicTrace else null, harmonicRows)
                    } else {
                        when (route) {
                            JdspChain.Route.JDSP_ONLY -> engine.processFloat(floatBuffer, floatOutBuffer, 0, samples)
                            JdspChain.Route.PVB_ONLY -> pvbEngine.processFloat(floatBuffer, floatOutBuffer, samples)
                            JdspChain.Route.JDSP_THEN_PVB -> {
                                engine.processFloat(floatBuffer, chainA, 0, samples)
                                pvbEngine.processFloat(chainA, floatOutBuffer, samples)
                            }
                        }
                        val haveDetail = detailed && pvbActive && pvbEngine.copyDiagnostic(diagnosticLayer, diagnosticFull, diagnosticTrace, samples)
                        val harmonicRows = if (haveDetail) pvbEngine.copyHarmonicTrace(harmonicTrace) else -1
                        diagnosticRing?.recordFloat(floatBuffer, floatOutBuffer, samples,
                            pvbEngine.diagnosticParams, if (pvbActive) pvbEngine.latencyFrames else -1,
                            buzzDiagnostics.observedAlgo, buzzDiagnostics.observedBlend, pvbActive,
                            if (haveDetail) diagnosticLayer else null, if (haveDetail) diagnosticFull else null,
                            if (haveDetail) diagnosticTrace else null, android.os.SystemClock.elapsedRealtimeNanos(),
                            if (harmonicRows >= 0) harmonicTrace else null, harmonicRows)
                    }
                    // Long silence: the output rests (track paused) while the engines go on processing the silent
                    // input, so settings, switches and fades still happen in the silence and the sound returns
                    // exactly as it would have. Never in a research mode or with a test sound; follows the
                    // power-save setting like the idle suspension.
                    val pauseAllowed = suspendOnIdle && !research && !me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound.playing
                    val outputSilent = if (isShort) SilenceGate.isSilent(shortOutBuffer, samples)
                        else SilenceGate.isSilent(floatOutBuffer, samples)
                    val silent = inputSilent && outputSilent
                    silenceGate.holdFrames = SilenceGate.holdFrames(holdSetting, sampleRate)
                    if (silenceGate.skip(silent, pauseAllowed, samples / 2)) {
                        // Paused long enough (deep sleep on, no music playing anywhere): stop the capture as well.
                        // Music that is not captured (an excluded app) keeps it awake; ask at most once a second.
                        var goDeep = false
                        if (silenceGate.deepDue(SilenceGate.deepFrames(deepSleepSetting, sampleRate))) {
                            val now = android.os.SystemClock.elapsedRealtimeNanos()
                            if (now - lastMusicCheckNs >= MUSIC_CHECK_NS) {
                                lastMusicCheckNs = now
                                goDeep = !audioManager.isMusicActive
                            }
                        }
                        if (goDeep) {
                            synchronized(ioLock) {
                                if (stopRequested) return
                                try { recorder.stop() } catch (ignored: Exception) {}
                            }
                            deepSleeping = true
                            playbackChanged = false
                            showDeepSleep(true)
                            buzzDiagnostics.audioDiscontinuity("capture_stopped_deep_sleep")
                            Timber.d("Deep sleep: capture stopped")
                        }
                    } else {
                        if (outputPaused && !resumeOutput()) return
                        if (!(if (isShort) writeAll(shortOutBuffer, samples) else writeAll(floatOutBuffer, samples))) return
                        if (silenceGate.afterBlock(silent, samples / 2, pauseAllowed)) {
                            // Pause (not stop): the little silence still queued plays first when it resumes.
                            synchronized(ioLock) {
                                if (stopRequested) return
                                try { track.pause() } catch (ignored: Exception) {}
                            }
                            outputPaused = true
                            buzzDiagnostics.audioDiscontinuity("output_paused_silence")
                            Timber.d("Output paused: silence")
                        }
                    }
                }
                carry = if (isShort) PcmPump.keepCarry(shortBuffer, total, samples)
                else PcmPump.keepCarry(floatBuffer, total, samples)
                if (deepSleeping) carry = 0   // the capture restarts later: a kept half frame would not fit
            }
        }
    }

    private fun buildAudioTrack(encoding: Int, sampleRate: Int, bufferSizeBytes: Int): AudioTrack {
        val attributesBuilder = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_UNKNOWN)
            .setContentType(AudioAttributes.CONTENT_TYPE_UNKNOWN)
            .setFlags(0)

        sdkAbove(Build.VERSION_CODES.Q) {
            attributesBuilder.setAllowedCapturePolicy(AudioAttributes.ALLOW_CAPTURE_BY_NONE)
        }

        val format = AudioFormat.Builder()
            .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
            .setEncoding(encoding)
            .setSampleRate(sampleRate)
            .build()

        val frameSizeInBytes: Int = if (encoding == AudioFormat.ENCODING_PCM_16BIT) {
            2 /* channels */ * 2 /* bytes */
        } else {
            2 /* channels */ * 4 /* bytes */
        }

        val bufferSize = if (((bufferSizeBytes % frameSizeInBytes) != 0 || bufferSizeBytes < 1)) {
            Timber.e("Invalid audio buffer size $bufferSizeBytes")
            128 * (bufferSizeBytes / 128)
        }
        else bufferSizeBytes

        Timber.d("Using buffer size $bufferSize")

        return AudioTrack.Builder()
            .setAudioFormat(format)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setAudioAttributes(attributesBuilder.build())
            .setBufferSizeInBytes(bufferSize)
            .build()
    }

    @SuppressLint("MissingPermission")
    private fun buildAudioRecord(encoding: Int, sampleRate: Int, bufferSizeBytes: Int): AudioRecord {
        if (!hasRecordPermission()) {
            Timber.e("buildAudioRecord: RECORD_AUDIO not granted")
            throw RuntimeException("RECORD_AUDIO not granted")
        }

        val format = AudioFormat.Builder()
            .setEncoding(encoding)
            .setSampleRate(sampleRate)
            .setChannelMask(AudioFormat.CHANNEL_IN_STEREO)
            .build()

        val configBuilder = AudioPlaybackCaptureConfiguration.Builder(mediaProjection!!)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .addMatchingUsage(AudioAttributes.USAGE_GAME)
            .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)

        val excluded = (if(excludeRestrictedSessions)
            sessionManager.sessionPolicyDatabase.getRestrictedUids().toList()
        else {
            sessionManager.pollOnce(false)
            emptyList()
        }).toMutableList()

        blockedApps.value?.map { it.uid }?.let {
            excluded += it
        }
        excluded += Process.myUid()

        excluded.forEach { configBuilder.excludeUid(it) }
        sessionManager.sessionDatabase.setExcludedUids(excluded.toTypedArray())
        sessionManager.pollOnce(false)

        Timber.d("buildAudioRecord: Excluded UIDs: ${excluded.joinToString("; ")}")

        return AudioRecord.Builder()
            .setAudioFormat(format)
            .setBufferSizeInBytes(bufferSizeBytes)
            .setAudioPlaybackCaptureConfig(configBuilder.build())
            .build()
    }

    // Determine HAL sampling rate
    private fun determineSamplingRate(): Int {
        val sampleRateStr: String? = audioManager.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE)
        val srate = sampleRateStr?.let { str -> Integer.parseInt(str).takeUnless { it == 0 } } ?: 48000
        Timber.i("Real HAL sampling rate is $srate")
        return srate
    }

    // Determine HAL buffer size
    private fun determineBufferSize(): Int {
        val framesPerBuffer: String? = audioManager.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER)
        return framesPerBuffer?.let { str -> Integer.parseInt(str).takeUnless { it == 0 } } ?: 256
    }

    companion object {
        const val SESSION_LOSS_MAX_RETRIES = 1

        /** How long the main thread waits for the audio thread to end before handing that wait to a watcher. */
        private const val STOP_JOIN_MS = 500L
        /** Failed or empty reads/writes in a row before the recorder/track is recreated. */
        private const val MAX_IO_FAILURES = 50
        private const val IO_RETRY_MS = 10L
        /** Longest idle wait (no session) before the loop looks again; session changes wake it at once. */
        private const val IDLE_WAIT_NS = 250_000_000L
        /** Deep sleep: longest wait between checks (a playback change wakes the thread at once). */
        private const val DEEP_WAIT_NS = 2_000_000_000L
        /** Deep sleep: after a playback change, 10 checks 50 ms apart before the long wait again. */
        private const val DEEP_FAST_POLLS = 10
        private const val DEEP_FAST_WAIT_NS = 50_000_000L
        /** While paused: how often to ask whether music plays (a binder call) once deep sleep is due. */
        private const val MUSIC_CHECK_NS = 1_000_000_000L
        /** Zero-length blocking writes (track paused or interrupted) before the rest of a block is dropped. */
        private const val MAX_EMPTY_WRITES = 3

        const val ACTION_START = BuildConfig.APPLICATION_ID + ".rootless.service.START"
        const val ACTION_STOP = BuildConfig.APPLICATION_ID + ".rootless.service.STOP"
        const val ACTION_BUZZ_TOGGLE = BuildConfig.APPLICATION_ID + ".rootless.service.BUZZ_TOGGLE"
        const val ACTION_BUZZ_SOLO = BuildConfig.APPLICATION_ID + ".rootless.service.BUZZ_SOLO"
        const val ACTION_BUZZ_CAPTURE = BuildConfig.APPLICATION_ID + ".rootless.service.BUZZ_CAPTURE"
        const val EXTRA_MEDIA_PROJECTION_DATA = "mediaProjectionData"
        const val EXTRA_APP_UID = "uid"
        const val EXTRA_APP_COMPAT_INTERNAL_CALL = "appCompatInternalCall"

        fun start(context: Context, data: Intent?) {
            // General build: nothing is processed before the first-run notice was confirmed (every start path:
            // power button, tile, boot, power broadcast).
            if (!me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild.processingAllowed) {
                Timber.w("Not starting: first-run notice not confirmed")
                return
            }
            try {
                context.startForegroundService(ServiceNotificationHelper.createStartIntent(context, data))
            }
            catch(ex: Exception) {
                CrashlyticsImpl.recordException(ex)
            }
        }

        fun stop(context: Context) {
            try {
                context.startForegroundService(ServiceNotificationHelper.createStopIntent(context))
            }
            catch(ex: Exception) {
                CrashlyticsImpl.recordException(ex)
            }
        }
    }
}


package me.timschneeberger.rootlessjamesdsp.service

import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BuzzReportsActivity
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzMicRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzMicrophone
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.utils.notifications.Notifications
import me.timschneeberger.rootlessjamesdsp.utils.notifications.ServiceNotificationHelper

/** Started only by the visible diagnostic Activity, after explicit user action and permission. */
class BuzzMicrophoneService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private var mic: BuzzMicrophone? = null
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        // General build: no microphone recording at all (the service is also removed from its manifest).
        if (!me.timschneeberger.rootlessjamesdsp.BuildConfig.RECORD_FEATURES) { stopSelf(); return START_NOT_STICKY }
        val notification = NotificationCompat.Builder(this, Notifications.CHANNEL_BUZZ_REPORT)
            .setSmallIcon(R.drawable.ic_tune_vertical_variant_24dp)
            .setContentTitle("버즈 진단 · 마이크 켜짐")
            .setContentText("실제 스피커 소리의 최근 5초를 보관 중 · 버즈 버튼으로 저장")
            .setContentIntent(PendingIntent.getActivity(this, 107, Intent(this, BuzzReportsActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .addAction(R.drawable.ic_close_24dp, "마이크 끄기", PendingIntent.getService(this, 108,
                Intent(this, BuzzMicrophoneService::class.java).setAction(ACTION_STOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .setOngoing(true).setSilent(true).setOnlyAlertOnce(true).build()
        try {
            if (Build.VERSION.SDK_INT >= 30) startForeground(Notifications.ID_BUZZ_MIC, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            else startForeground(Notifications.ID_BUZZ_MIC, notification)
            if (mic == null) {
                check(PvbRuntime.engine != null && ServiceNotificationHelper.buzzArmed && !PvbRuntime.abActive && !PvbRuntime.measuring)
                val existing = BuzzMicRuntime.capture
                check(existing == null || !existing.running)
                val capture = BuzzMicrophone(this)
                mic = capture; BuzzMicRuntime.capture = capture; capture.start()
                main.postDelayed(checkStatus, 250)
            }
        } catch (e: Exception) {
            ServiceNotificationHelper.pushBuzzResult(this, "마이크를 시작하지 못했습니다: ${e.javaClass.simpleName}. 앱 화면에서 마이크 권한과 진단 상태를 확인해 주세요.")
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private val checkStatus = object : Runnable {
        override fun run() {
            if (mic?.running != true || PvbRuntime.engine == null || !ServiceNotificationHelper.buzzArmed || PvbRuntime.abActive || PvbRuntime.measuring) {
                if (mic?.running != true) ServiceNotificationHelper.pushBuzzResult(this@BuzzMicrophoneService,
                    "마이크 기록이 종료되었습니다. 기록 목록과 앱의 마이크 권한을 확인해 주세요.")
                stopSelf()
            } else main.postDelayed(this, 250)
        }
    }

    override fun onDestroy() {
        main.removeCallbacks(checkStatus)
        mic?.stop()
        if (BuzzMicRuntime.capture === mic) BuzzMicRuntime.capture = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "pvb.buzz.MIC_STOP"
    }
}

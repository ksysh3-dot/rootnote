package me.timschneeberger.rootlessjamesdsp.activity

import android.app.Activity
import android.Manifest
import android.content.pm.PackageManager
import android.app.AlertDialog
import android.content.ClipData
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Switch
import android.widget.Toast
import androidx.core.content.FileProvider
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.BuzzMicRuntime
import me.timschneeberger.rootlessjamesdsp.service.BuzzMicrophoneService
import me.timschneeberger.rootlessjamesdsp.service.RootlessAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.utils.notifications.ServiceNotificationHelper
import java.io.File
import java.util.Locale

/** A distinct provider component avoids merging with the app's existing FileProvider declaration. */
class BuzzFileProvider : FileProvider()

/** Local reports only. Sharing always opens the system chooser; no automatic submission. */
class BuzzReportsActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); render() }
    override fun onResume() { super.onResume(); render() }

    private fun startMicrophone() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 702); return
        }
        try {
            // startService from this visible activity, not startForegroundService: the service promotes itself, and
            // when that fails (permission, type restrictions) it can stop without the system killing the app for
            // a missing startForeground() (release audit S8).
            startService(Intent(this, BuzzMicrophoneService::class.java))
            window.decorView.postDelayed({ if (!isFinishing && !isDestroyed) render() }, 300L)
        } catch (_: Exception) { Toast.makeText(this, "앱 화면에서 마이크 권한과 진단 상태를 확인해 주세요.", Toast.LENGTH_LONG).show() }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 702 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) startMicrophone()
    }

    private fun render() {
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = (16 * resources.displayMetrics.density).toInt()
            setPadding(pad, pad, pad, pad)
        }
        fun text(value: String, size: Float = 15f) {
            column.addView(TextView(this).apply { this.text = value; textSize = size; setPadding(0, 12, 0, 12) })
        }
        fun button(label: String, enabled: Boolean = true, click: () -> Unit) {
            column.addView(Button(this).apply { text = label; isEnabled = enabled; setOnClickListener { click() } })
        }
        text("버즈 진단·리포트", 22f)
        text("진단을 켜면 최근 5초의 입력·처리 파형을 메모리에만 보관합니다. 버즈를 들은 뒤 ‘버즈 기록·뮤트’를 누르면 앞 5초와 뒤 3초를 ZIP으로 저장하고 재생을 잠시 뮤트합니다. 이미 들린 소리는 되돌려 뮤트할 수 없습니다.\n\n‘스피커 소리도 기록’을 별도로 켜면 마이크 파형도 같은 ZIP에 담습니다. 마이크에는 주변 말소리도 들어갈 수 있습니다. 자동 전송하지 않으며 공유할 때 음악·선택한 마이크 녹음도 포함됩니다. 처리 출력 WAV에는 뮤트 전 소리가 남지만, 실제 마이크의 뮤트 후 구간은 조용해집니다.")
        text("상세 진단: 앞 5초·뒤 3초의 생성 저음(generated.wav)과 전체 믹스(full_mix.wav)를 따로 보관합니다. JSON에는 처리 블록별 레벨·리미터 감쇄·모델 상태·적용 설정·처리 시간을 포함합니다. 일반 재생 중에도 분리 파일이 저장됩니다.")
        text(ServiceNotificationHelper.buzzState)
        val running = PvbRuntime.engine != null
        val prefs = getSharedPreferences("pvb_buzz", MODE_PRIVATE)
        val muteRequested = prefs.getBoolean("mute_on_report", true)
        column.addView(Switch(this).apply {
            text = "기록할 때 재생 잠시 뮤트\n끄면 마이크의 후구간도 들린 그대로 기록"
            isChecked = muteRequested
            isEnabled = !ServiceNotificationHelper.buzzBusy
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean("mute_on_report", checked).apply()
                ServiceNotificationHelper.pushBuzzControl(this@BuzzReportsActivity)
                render()
            }
        })
        fun action(value: String) {
            if (!running) return
            try {
                startService(Intent(this, RootlessAudioProcessorService::class.java).setAction(value))
                column.postDelayed({ if (!isFinishing && !isDestroyed) render() }, 250L)
            } catch (_: Exception) { Toast.makeText(this, "서비스 상태를 확인해 주세요.", Toast.LENGTH_LONG).show() }
        }
        if (!running) text("앱의 전원 버튼으로 오디오 서비스를 먼저 켜 주세요.")
        button(if (ServiceNotificationHelper.buzzArmed) "진단 끄기" else "진단 켜기", running) {
            action(RootlessAudioProcessorService.ACTION_BUZZ_TOGGLE)
        }
        button(if (muteRequested) "버즈 기록·뮤트" else "버즈 기록 · 재생 유지", running && ServiceNotificationHelper.buzzArmed && !ServiceNotificationHelper.buzzBusy) {
            action(RootlessAudioProcessorService.ACTION_BUZZ_CAPTURE)
        }
        val solo = PvbRuntime.engine?.diagnosticParams?.get(PvbParam.DIAGNOSTIC_SOLO) == 1f
        column.addView(Switch(this).apply {
            text = "생성된 가상 저음만 듣기 · 진단용"
            isChecked = solo
            isEnabled = running && ServiceNotificationHelper.buzzArmed && !ServiceNotificationHelper.buzzBusy &&
                PvbRuntime.status.processing && PvbRuntime.status.vbOn && !PvbRuntime.abActive && !PvbRuntime.measuring
            setOnCheckedChangeListener { _, _ -> action(RootlessAudioProcessorService.ACTION_BUZZ_SOLO) }
        })
        text("원음·분석·가상 저음 생성·전체 믹스 처리는 계속 유지하고 생성 성분만 들려줍니다. 음량을 자동으로 키우지 않으며 전환에는 약 0.1초가 걸립니다. 배음만 들을 때 거친 음색 자체가 오류를 뜻하지는 않습니다. 실제 스피커의 반응은 전체 음악을 들을 때와 다를 수 있습니다.\n\n이 상태의 처리 출력 WAV에는 생성 저음만 저장됩니다. 전환 전 5초도 함께 남을 수 있으니, 단독 구간을 기록하려면 전환 후 5초 이상 기다려 주세요. 진단 끄기·서비스 재시작·비교/측정 시 일반 재생으로 복귀합니다.")
        val micRunning = BuzzMicRuntime.capture?.running == true
        button(if (micRunning) "스피커 마이크 기록 끄기" else "스피커 소리도 기록 · 마이크 켜기",
            micRunning || (running && ServiceNotificationHelper.buzzArmed && !ServiceNotificationHelper.buzzBusy)) {
            if (micRunning) {
                stopService(Intent(this, BuzzMicrophoneService::class.java))
                column.postDelayed({ if (!isFinishing && !isDestroyed) render() }, 250L)
            } else startMicrophone()
        }
        button("목록 새로고침") { render() }
        val files = File(filesDir, "buzz_reports").listFiles()?.filter { it.isFile && it.extension in listOf("zip", "part") }
            ?.sortedByDescending { it.lastModified() }.orEmpty()
        text("저장된 리포트 ${files.size}개 · 한도 100 MB\n공간이 차면 새 기록을 저장하지 않습니다. 필요 없는 리포트는 직접 삭제해 주세요.")
        for (file in files) {
            text("${file.name}\n${String.format(Locale.US, "%.2f", file.length() / 1048576.0)} MB" +
                if (file.extension == "part") " · 저장이 끝나지 않은 파일" else "")
            button("공유 / 다른 위치에 저장", file.extension == "zip") {
                try {
                    val uri = FileProvider.getUriForFile(this, BuildConfig.APPLICATION_ID + ".buzz_provider", file)
                    val send = Intent(Intent.ACTION_SEND).setType("application/zip")
                        .putExtra(Intent.EXTRA_STREAM, uri)
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    send.clipData = ClipData.newRawUri("버즈 리포트", uri)
                    startActivity(Intent.createChooser(send, "버즈 리포트 공유"))
                } catch (_: Exception) { Toast.makeText(this, "리포트를 공유할 앱을 확인해 주세요.", Toast.LENGTH_LONG).show() }
            }
            button("이 리포트 삭제") {
                AlertDialog.Builder(this).setMessage("${file.name} 파일을 삭제할까요?")
                    .setNegativeButton("취소", null).setPositiveButton("삭제") { _, _ ->
                        if (!file.delete()) Toast.makeText(this, "삭제하지 못했습니다.", Toast.LENGTH_SHORT).show()
                        render()
                    }.show()
            }
        }
        setContentView(ScrollView(this).apply { addView(column) })
    }
}

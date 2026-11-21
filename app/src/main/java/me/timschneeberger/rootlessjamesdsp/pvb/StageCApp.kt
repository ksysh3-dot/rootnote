package me.timschneeberger.rootlessjamesdsp.pvb

import me.timschneeberger.rootlessjamesdsp.BuildConfig
import android.content.Context
import android.content.Intent
import android.content.ClipData
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.core.content.FileProvider
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Bass mode preparation. All preparation runs on service main, with the audio worker joined. */
object StageCApp {
    const val TELEMETRY = "pvb_s91_telemetry"
    internal val fileLock = Any()
    private fun prefs(c: Context) = c.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
    fun prepare(c: Context, engine: PvbEngine, rate: Int) {
        val mode = PvbSettings.load(prefs(c)).stageCId
        check(engine.prepareBass(mode, rate)) { "COMBO preparation failed" }
    }

    /** Existing developer entry, shared by both flavors. It never enables engine tuning implicitly. */
    fun showDeveloperMenu(c: Context) {
        val p = prefs(c)
        val telemetry = p.getBoolean(TELEMETRY, false)
        val halRate = (c.getSystemService(Context.AUDIO_SERVICE) as AudioManager)
            .getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE) ?: "?"
        val devLog = BuildConfig.RECORD_FEATURES && p.getBoolean(DevDetailLog.PREF, false)
        val items = mutableListOf("계측 파일: " + if (telemetry) "켬" else "끔 (기본)", "계측 파일 모두 내보내기")
        if (BuildConfig.RECORD_FEATURES) items += "상세 디버그 기록 (5 ms): " + if (devLog) "켬" else "끔 (기본)"
        if (PvbBuild.general) items += "기존 개발자 설정"
        MaterialAlertDialogBuilder(c).setTitle("개발자 메뉴 · 출력 $halRate Hz")
            .setItems(items.toTypedArray()) { _, index ->
                when (index) {
                    0 -> p.edit().putBoolean(TELEMETRY, !telemetry).apply()
                    1 -> export(c)
                    2 -> if (BuildConfig.RECORD_FEATURES) {
                        p.edit().putBoolean(DevDetailLog.PREF, !devLog).apply()
                        Toast.makeText(c, "상세 디버그 기록 " + (if (devLog) "끔" else "켬") +
                            " · 오디오 처리를 껐다 켜면 적용됩니다", Toast.LENGTH_LONG).show()
                    } else PvbGeneral.openLegacyDevMode(c)
                }
            }.setNeutralButton("로그 위치") { _, _ ->
                MaterialAlertDialogBuilder(c).setTitle("계측 파일")
                    .setMessage(File(c.filesDir, "s91_telemetry").absolutePath +
                        "\n5초마다 JSONL 기록. 계측을 끄거나 모드를 바꾸면 마지막 기록을 저장합니다." +
                        "\n과거 모드 기록도 모두 내보내기에 포함됩니다." +
                        (if (BuildConfig.RECORD_FEATURES) "\n\n상세 디버그 기록: " + File(c.filesDir, DevDetailLog.DIR).absolutePath +
                        "\n5 ms 칸마다 입력·요청·실제 배음·추적 상태·사유·제한량 (JSONL, 오디오 없음)." +
                        " 15분마다 새 파일, 합계 300 MB를 넘으면 오래된 것부터 지웁니다. 내보내기에 포함됩니다." else ""))
                    .setPositiveButton(android.R.string.ok, null).show()
            }.setNegativeButton(android.R.string.cancel, null).show()
    }

    private fun export(context: Context) {
        val c = context
        Thread({
            try {
                val dir = File(c.filesDir, "s91_telemetry")
                val out = File(c.filesDir, "s91_telemetry_export/s91-" + System.currentTimeMillis() + ".zip")
                synchronized(fileLock) {
                    val files = dir.listFiles()?.filter { it.extension == "jsonl" }.orEmpty() +
                        (if (BuildConfig.RECORD_FEATURES) File(c.filesDir, DevDetailLog.DIR).listFiles()?.filter { it.extension == "jsonl" }.orEmpty() else emptyList())
                    check(files.isNotEmpty()) { "계측 파일이 없습니다. 개발자 메뉴에서 계측을 켜고 재생해 주세요." }
                    out.parentFile!!.mkdirs()
                    ZipOutputStream(out.outputStream()).use { zip ->
                        for (f in files) {
                            zip.putNextEntry(ZipEntry(f.name))
                            f.inputStream().use { it.copyTo(zip) }
                            zip.closeEntry()
                        }
                    }
                }
                Handler(Looper.getMainLooper()).post {
                    try {
                        val uri = FileProvider.getUriForFile(c, c.packageName + ".buzz_provider", out)
                        c.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("application/zip")
                            .putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            .apply { clipData = ClipData.newRawUri("s91", uri) }, "s91 계측 파일 내보내기"))
                    } catch (e: Exception) {
                        Toast.makeText(c, "계측 파일 공유 실패: " + (e.message ?: e.javaClass.simpleName), Toast.LENGTH_LONG).show()
                    }
                }
            } catch (e: Exception) {
                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(c, e.message ?: "계측 파일 내보내기 실패", Toast.LENGTH_LONG).show()
                }
            }
        }, "s91-export").start()
    }
}

package me.timschneeberger.rootlessjamesdsp.pvb

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
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** s91 personal test only. All preparation runs on service main, with the audio worker joined. */
object StageCApp {
    const val WORKER = "pvb_s91_worker"
    const val TELEMETRY = "pvb_s91_telemetry"
    internal val fileLock = Any()
    private fun prefs(c: Context) = c.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
    fun prepare(c: Context, engine: PvbEngine, rate: Int) {
        val p = prefs(c)
        val requested = PvbSettings.load(p).stageCId
        // The separator and conductor models are 48 kHz only: elsewhere their clock and pitch axis are wrong.
        val mode = if (rate != 48000 && requested >= 2) 0 else requested
        if (mode != requested) Toast.makeText(c, "출력이 $rate Hz라 분리형·지휘형을 쓸 수 없습니다. 48 kHz에서만 동작합니다.",
            Toast.LENGTH_LONG).show()
        val asset = when (mode) { 2 -> "T3a16_96.bin"; 3 -> "E60KD.bin"; 4 -> "stable_ab_1218.bin"; else -> null }
        val data = asset?.let { c.assets.open(it).use { f -> f.readBytes() } }
        if (data != null) {
            val expected = when (mode) {
                2 -> "e7be71d65f05c7a84527e1c58a71edde05012a86034069c933288a597051906d"
                3 -> "8fd3284cd08c101754fff524988e5987ea7e3cf897b494c44ce845e900c80310"
                else -> "70f4a90c34568f46d4677e4799397991a2cb2f6577988fb3ea704332330c9b98"
            }
            check(data.size == if (mode == 3) 425640 else 531208)
            check(MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) } == expected)
        }
        check(engine.prepareStageC(mode, data, mode == 3 && p.getBoolean(WORKER, false),
            p.getBoolean(TELEMETRY, false), rate)) { "s91 model preparation failed" }
    }

    /** Existing developer entry, shared by both flavors. It never enables engine tuning implicitly. */
    fun showDeveloperMenu(c: Context) {
        val p = prefs(c)
        val telemetry = p.getBoolean(TELEMETRY, false)
        val worker = p.getBoolean(WORKER, false)
        val halRate = (c.getSystemService(Context.AUDIO_SERVICE) as AudioManager)
            .getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE) ?: "?"
        val items = mutableListOf("epoch6 안정 비교 선택", "지휘형 작업 스레드: " + if (worker) "켬" else "끔 (기본)",
            "시험 계측 파일: " + if (telemetry) "켬" else "끔 (기본)", "계측 파일 모두 내보내기")
        if (PvbBuild.general) items += "기존 개발자 설정"
        MaterialAlertDialogBuilder(c).setTitle("s91 개인 시험 · 개발자 메뉴 · 출력 $halRate Hz")
            .setItems(items.toTypedArray()) { _, index ->
                when (index) {
                    0 -> p.edit().putString(PvbSettings.KEY_BASS_MODE, "stable").apply()
                    1 -> p.edit().putBoolean(WORKER, !worker).apply()
                    2 -> p.edit().putBoolean(TELEMETRY, !telemetry).apply()
                    3 -> export(c)
                    4 -> PvbGeneral.openLegacyDevMode(c)
                }
            }.setNeutralButton("로그 위치") { _, _ ->
                MaterialAlertDialogBuilder(c).setTitle("계측 파일")
                    .setMessage(File(c.filesDir, "s91_telemetry").absolutePath +
                        "\n5초마다 JSONL 기록. 계측을 끄거나 모드를 바꾸면 마지막 기록을 저장합니다." +
                        "\n과거 모드 기록도 모두 내보내기에 포함됩니다.")
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
                    val files = dir.listFiles()?.filter { it.extension == "jsonl" }.orEmpty()
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

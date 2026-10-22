package me.timschneeberger.rootlessjamesdsp.pvb

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.media.AudioManager
import android.view.View
import android.util.AttributeSet
import android.util.TypedValue
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

/**
 * Card for the in-app measurement ([PvbMeasure]): volume steps, the phone's compressor and the plan for the
 * output-headroom blind comparison. The last result is kept and can be copied as JSON.
 */
class PvbMeasureCard @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val title = TextView(context)
    private val intro = TextView(context)
    private val startBtn = Button(context)
    private val progress = TextView(context)
    private val resultText = TextView(context)
    private val copyBtn = Button(context)
    private var running: PvbMeasure? = null
    private var last: JSONObject? = null

    init {
        orientation = VERTICAL
        val pad = dp(16)
        setPadding(pad, dp(14), pad, dp(14))

        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        title.setTypeface(title.typeface, Typeface.BOLD)
        title.text = "측정 (폰 마이크) · 비교 시험용, 실시간 볼륨 보정에는 미적용"
        addView(title)

        intro.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        intro.setLineSpacing(0f, 1.15f)
        intro.setPadding(0, dp(6), 0, dp(8))
        intro.text = "스피커로 분홍 잡음(쉬 소리)을 내고 폰 마이크로 받아서, 볼륨 단계마다 실제로 몇 dB 커지는지, " +
            "볼륨을 올리면 저음이 깎이는지, 폰이 큰 소리를 얼마나 누르는지 잽니다. 약 1분 걸리고, 볼륨이 1단계부터 " +
            "끝까지 올라가며 소리가 꽤 커집니다(끝나면 원래 볼륨으로 돌아갑니다).\n" +
            "음악을 멈추고, 조용한 곳에서 폰을 화면이 위로 오게 평평한 곳에 두고, 측정하는 동안 건드리지 마세요. " +
            "출력 여유 블라인드 비교는 이 측정 결과로 볼륨과 출력을 맞춥니다. 볼륨 연동 보정(실험)은 이 측정을 쓰지 않고 " +
            "안드로이드가 알려 주는 볼륨 곡선을 씁니다. 측정 중 이어폰·블루투스로 바뀌면 바로 멈추고 볼륨을 되돌립니다."
        addView(intro)

        startBtn.text = "측정 시작"
        startBtn.setOnClickListener { if (running == null) start() else running?.cancel() }
        addView(startBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        progress.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
        progress.setPadding(0, dp(6), 0, 0)
        addView(progress)

        resultText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
        resultText.setLineSpacing(0f, 1.15f)
        resultText.setPadding(0, dp(8), 0, 0)
        resultText.typeface = Typeface.MONOSPACE
        addView(resultText)

        copyBtn.text = "결과 복사 (JSON)"
        copyBtn.visibility = GONE
        copyBtn.setOnClickListener { copy() }
        addView(copyBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        PvbMeasure.restoreIfInterrupted(context)
        PvbMeasure.load(context)?.let { show(it) }
    }

    private fun currentIndex(): Int =
        context.getSystemService(AudioManager::class.java).getStreamVolume(AudioManager.STREAM_MUSIC)

    private fun start() {
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            progress.text = "녹음 권한이 없습니다. 앱 설정에서 마이크 권한을 허용해 주세요."
            return
        }
        val am = context.getSystemService(AudioManager::class.java)
        val external = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).firstOrNull { it.type in PvbMeasure.EXTERNAL_OUTPUTS }
        if (external != null) {
            progress.text = "이어폰이나 블루투스가 연결돼 있습니다. 끊고 내장 스피커로 측정하세요."
            return
        }
        if (PvbRuntime.abActive) {
            progress.text = "블라인드 비교가 끝난 뒤에 측정하세요."
            return
        }
        resultText.text = ""
        copyBtn.visibility = GONE
        startBtn.text = "중단"
        val m = PvbMeasure(context,
            onProgress = { progress.text = it },
            onDone = { result, error ->
                running = null
                startBtn.text = "측정 시작"
                if (result != null) {
                    progress.text = error ?: "끝났습니다."
                    show(result)
                } else {
                    progress.text = error ?: "측정 실패"
                }
            })
        running = m
        m.start()
    }

    private fun show(result: JSONObject) {
        last = result
        resultText.text = PvbMeasure.summary(result, currentIndex())
        copyBtn.visibility = VISIBLE
    }

    private fun copy() {
        val r = last ?: return
        val cm = context.getSystemService(ClipboardManager::class.java) ?: return
        cm.setPrimaryClip(ClipData.newPlainText("PVB 측정", r.toString(1)))
        copyBtn.text = "복사했습니다"
        postDelayed({ copyBtn.text = "결과 복사 (JSON)" }, 1500)
    }

    override fun onWindowVisibilityChanged(visibility: Int) {
        super.onWindowVisibilityChanged(visibility)
        if (visibility != View.VISIBLE) running?.cancel()   // the microphone goes silent in the background
    }

    override fun onDetachedFromWindow() {
        running?.cancel()   // the runner restores the volume itself
        super.onDetachedFromWindow()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

}

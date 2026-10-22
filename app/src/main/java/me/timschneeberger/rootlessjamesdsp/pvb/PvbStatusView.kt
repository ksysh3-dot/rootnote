package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.content.ClipData
import android.content.ClipboardManager
import android.graphics.Typeface
import android.os.Build
import android.os.SystemClock
import android.util.AttributeSet
import android.util.TypedValue
import android.widget.LinearLayout
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import org.json.JSONObject
import java.util.Locale

/**
 * Live status card of the PVB engine: what is processing, the applied low-mid gain, the volume reading and
 * the meters. Refreshes twice a second while it is on screen.
 */
class PvbStatusView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val title = TextView(context)
    private val body = TextView(context)
    private val researchCopy = Button(context)
    private val meters = FloatArray(PvbMeter.COUNT)
    private var attached = false
    private var lastBlocks = -1f
    private var lastBlockChangeMs = 0L

    private val refresh = object : Runnable {
        override fun run() {
            render()
            if (attached) postDelayed(this, REFRESH_MS)
        }
    }

    init {
        orientation = VERTICAL
        val pad = dp(16)
        setPadding(pad, dp(14), pad, dp(14))
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        title.setTypeface(title.typeface, Typeface.BOLD)
        // s26u: "PVB 스피커 보정" as before; general: the brand name (no internal PVB name).
        title.text = if (PvbBuild.general) context.getString(me.timschneeberger.rootlessjamesdsp.R.string.app_brand_name)
            else "PVB 스피커 보정"
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        body.setLineSpacing(0f, 1.15f)
        body.setPadding(0, dp(6), 0, 0)
        addView(title)
        addView(body)
        researchCopy.text = "저음 연구 기록 복사"
        researchCopy.visibility = GONE
        researchCopy.setOnClickListener { copyResearch() }
        addView(researchCopy)
        // Buzz diagnostics (recordings) exist only in the s26u build.
        if (PvbBuild.recordFeatures) addView(Button(context).apply {
            text = "버즈 진단·저장된 리포트"
            setOnClickListener {
                context.startActivity(android.content.Intent(context,
                    me.timschneeberger.rootlessjamesdsp.activity.BuzzReportsActivity::class.java))
            }
        })
        render()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        attached = true
        removeCallbacks(refresh)
        post(refresh)
    }

    override fun onDetachedFromWindow() {
        attached = false
        removeCallbacks(refresh)
        super.onDetachedFromWindow()
    }

    private fun render() {
        val engine = PvbRuntime.engine
        if (engine == null) {
            researchCopy.visibility = GONE
            body.text = "서비스가 꺼져 있습니다. 위의 전원 버튼으로 켜면 상태가 여기에 표시됩니다."
            return
        }
        val s = PvbRuntime.status
        if (PvbRuntime.abHidden) {
            researchCopy.visibility = GONE
            body.text = "블라인드 비교 중입니다. 어떤 설정이 재생되는지 드러나지 않게 상태를 숨깁니다."
            return
        }
        val haveMeters = engine.readMeters(meters)
        val research = PvbBuild.researchUi
        // The S26U speaker/limiter model applies only on the S26U (general build: measured profile only).
        val phoneModel = PvbGeneral.phoneModelCurves(context)
        researchCopy.visibility = if (research && haveMeters && s.vbOn && !s.matchedBypass &&
            PvbModels.fromId(s.vbAlgo) != null) VISIBLE else GONE
        val lines = ArrayList<String>()
        if (PvbGeneral.unmeasured(context))
            lines += context.getString(me.timschneeberger.rootlessjamesdsp.R.string.unmeasured_status)
        val back = PvbRuntime.abReturnVolume
        if (PvbRuntime.abActive && back >= 0) {
            lines += "블라인드 비교 뒤라 출력을 ${PvbAbConditions.HEADROOM_DB.toInt()} dB 낮춰 두었습니다. 볼륨을 " +
                "${PvbRuntime.volumeLabel(back, s.volumeMax)}로 내리면 원래 출력으로 돌아갑니다 " +
                "(지금 ${PvbRuntime.volumeLabel(s.volumeIndex, s.volumeMax)})."
        }

        // The service stops reading audio while nothing plays, so the block counter stands still.
        val now = SystemClock.elapsedRealtime()
        if (haveMeters) {
            val blocks = meters[PvbMeter.BLOCKS]
            if (blocks != lastBlocks) {
                if (lastBlocks >= 0f) lastBlockChangeMs = now  // first reading is only a baseline
                lastBlocks = blocks
            }
        }
        val flowing = haveMeters && lastBlockChangeMs > 0L && now - lastBlockChangeMs < IDLE_AFTER_MS

        lines += when {
            s.matchedBypass -> "상태: 보정 꺼짐 · 음량 맞춘 원음 · ${s.routeName}"
            !s.enabled && !s.usingPvb -> "상태: PVB 꺼짐 (원래 JamesDSP 처리 사용)"
            !s.processing -> "상태: 우회 · ${s.routeName}${if (s.routeKnown) "" else " (추정)"} (내장 스피커가 아님)"
            flowing -> "상태: 처리 중 · ${s.routeName}"
            else -> "상태: 대기 중 · ${s.routeName} (지금 잡히는 소리가 없음)"
        }

        if (s.matchedBypass) {
            val measured = engine.matchDb()
            val db = if (haveMeters) meters[PvbMeter.MATCH_DB] else measured
            lines += "음량 맞춤 ${signed(db)} dB" + if (measured.isFinite()) " (최근 재생 기준 추정)" else " (초기 추정·음악 재생 후 갱신)"
        }

        val applied = if (flowing) meters[PvbMeter.LOW_DB_NOW] else s.targetLowDb
        if (s.processing) lines += if (s.volLink) {
            "저중역 보정: ${signed(applied)} dB (볼륨 연동: 기준보다 ${fmt(s.dropDb)} dB ${if (s.dropDb >= 0f) "작음" else "큼"})"
        } else {
            "저중역 보정: ${signed(applied)} dB (볼륨 연동 꺼짐)"
        }

        if (s.processing && s.dynRefDb.isFinite()) {
            val now = if (haveMeters) meters[PvbMeter.DYN_DB] else 0f
            val level = if (haveMeters && meters[PvbMeter.DYN_LEVEL_DB] > -119f) meters[PvbMeter.DYN_LEVEL_DB] else Float.NaN
            lines += "조용한 구간 저음 추가: ${signed(now)} dB · 기준 ${fmt(s.dynRefDb)} dB (지금 레벨 ${fmt(level)} dB)"
        }
        if (s.vbOn && !s.matchedBypass) {
            val vb = if (haveMeters) meters[PvbMeter.VB].toInt() else 0
            // General build without the research tools: no internal alpha names or model codenames.
            val vbLabel = if (PvbBuild.general) "가상 저음" else "가상 저음 (알파 3)"
            val modelName = if (research) "${PvbSettings.vbAlgoName(vb - 1)} · " else ""
            lines += when {
                vb in 1..11 ->
                    "$vbLabel: ${modelName}레벨 ${signed(s.vbLevelDb)} dB" +
                        (if (s.vbVolLink) " · 볼륨 연동 −${fmt(s.vbVolReductionDb)} dB → 적용 ${signed(s.vbAppliedLevelDb)} dB" else "")
                else -> "$vbLabel: 켜져 있지만 지금은 쓰지 않음 (우회 중이거나 이 샘플레이트에서 지원 안 됨)"
            }
            if (research && flowing && vb == 1 + PvbSettings.VB_GENTLE) {
                lines += "구간 분석: ${sceneName(meters[PvbMeter.VB_SCENE].toInt())} · 소리에 미적용"
            }
            if (research && flowing && vb == 1 + PvbSettings.VB_GENTLE_ADAPTIVE) {
                val weight = (meters[PvbMeter.VB_UPPER_BLEND] * 100).toInt()
                lines += "고차배음 더 억제 설정: ${weight}% · 적응형 시험"
            }
        }
        if (research) lines += "볼륨: ${s.volumeIndex}/${s.volumeMax} 단계 · 약 ${fmt(s.volumeDb)} dB, 기준 ${fmt(s.referenceDb)} dB"
        if (research) lines += if (s.volumeDbSource == "system") {
            "  (폰이 알려 준 볼륨 곡선 사용)"
        } else {
            "  (기본 곡선으로 추정. 폰이 알려 준 값 ${fmt(s.volumeSysDb)} dB는 볼륨마다 거의 같아서 안 씀)"
        }

        if (flowing) {
            lines += "피크: 입력 ${fmt(meters[PvbMeter.IN_PEAK_DB])} → 출력 ${fmt(meters[PvbMeter.OUT_PEAK_DB])} dBFS · 앱 리미터 감쇠 ${fmt(meters[PvbMeter.LIM_GR_DB])} dB"
            if (research && phoneModel)
                lines += "폰이 저음 대역(250 Hz)을 누르는 양: 약 ${fmt(meters[PvbMeter.EST_GR_DB])} dB (측정 기반 추정)"
            val rate = meters[PvbMeter.SAMPLE_RATE]
            val latencyMs = if (rate > 0f) meters[PvbMeter.LATENCY] * 1000f / rate else 0f
            if (research) lines += "처리 부하: ${fmt(meters[PvbMeter.LOAD_PCT], 2)}% · ${fmt(rate / 1000f)} kHz · 엔진 지연 ${fmt(latencyMs)} ms"
        } else if (haveMeters && s.enabled && s.processing) {
            lines += "피크·부하: 음악이 재생되면 표시"
        }
        if (haveMeters && meters[PvbMeter.NAN_EVENTS] > 0f) {
            lines += "잘못된 샘플 처리: ${meters[PvbMeter.NAN_EVENTS].toInt()}회"
        }

        val recent = PvbRuntime.recentSettings()
        if (research && recent.isNotEmpty()) {
            lines += "볼륨 관련 시스템 설정 변화 (진단용):"
            recent.take(4).forEach { lines += "  $it" }
        }
        body.text = lines.joinToString("\n")
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun copyResearch() {
        if (PvbRuntime.abHidden) return
        val engine = PvbRuntime.engine ?: return
        val snapshot = FloatArray(PvbMeter.COUNT)
        if (!engine.readMeters(snapshot)) return
        val s = PvbRuntime.status
        val scene = snapshot[PvbMeter.VB_SCENE].toInt()
        val counts = JSONObject()
        listOf("unknown", "steady", "transient", "complex").forEachIndexed { i, name ->
            counts.put(name, snapshot[PvbMeter.VB_UNKNOWN_FRAMES + i].toLong())
        }
        val report = JSONObject()
            .put("schema", 2)
            .put("type", "pvb_vb_research")
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("app_version_code", BuildConfig.VERSION_CODE)
            .put("exported_at_unix_ms", System.currentTimeMillis())
            .put("device", Build.MODEL)
            .put("soc", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else "unknown")
            .put("android_sdk", Build.VERSION.SDK_INT)
            .put("requested_algorithm", s.vbAlgo)
            .put("active_algorithm", snapshot[PvbMeter.VB].toInt() - 1)
            .put("requested_layer_level_db", s.vbLevelDb)
            .put("vb_volume_link", s.vbVolLink)
            .put("vb_volume_reduction_db", s.vbVolReductionDb)
            .put("applied_layer_level_db", s.vbAppliedLevelDb)
            .put("sample_rate", snapshot[PvbMeter.SAMPLE_RATE].toInt())
            .put("engine_latency_frames", snapshot[PvbMeter.LATENCY].toInt())
            .put("volume_index", s.volumeIndex)
            .put("volume_max", s.volumeMax)
            .put("route", s.routeName)
            .put("scene", scene)
            .put("scene_label", sceneName(scene))
            .put("scene_frames", counts)
            .put("analysis_hop_core_samples", 16)
            .put("analysis_core_sample_rate", 3000)
            .put("counts_since_algorithm_reset", true)
            .put("trained_selector", false)
            .put("automatic_audio_switching_applied", snapshot[PvbMeter.VB].toInt() == 1 + PvbSettings.VB_GENTLE_ADAPTIVE && s.processing && !s.matchedBypass)
            .put("strong_budget_weight", snapshot[PvbMeter.VB_UPPER_BLEND])
            .put("strong_budget_target", snapshot[PvbMeter.VB_UPPER_TARGET].toInt())
            .put("budget_transitions", snapshot[PvbMeter.VB_UPPER_TRANSITIONS].toLong())
            .put("policy_version", 2)
            .put("note", "Rule-based experimental harmonic-budget selection only in algorithm 5; " +
                "not pitch labels, buzz detection, learned quality scores or a listening result. " +
                "Both budgets share analysis and oscillator phases. Counters reset with algorithm/rate.")
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("PVB 저음 연구", report.toString(2)))
        Toast.makeText(context, "저음 연구 기록을 복사했습니다", Toast.LENGTH_SHORT).show()
    }

    companion object {
        private const val REFRESH_MS = 500L
        private const val IDLE_AFTER_MS = 1200L

        private fun sceneName(scene: Int): String = when (scene) {
            1 -> "지속음 처리 후보"
            2 -> "짧은 타격음 처리 후보"
            3 -> "보수적 처리 후보"
            else -> "판단 보류"
        }

        private fun fmt(v: Float, digits: Int = 1): String =
            if (v.isFinite()) String.format(Locale.US, "%.${digits}f", v) else "–"

        private fun signed(v: Float): String =
            if (v.isFinite()) String.format(Locale.US, "%+.1f", v) else "–"
    }
}


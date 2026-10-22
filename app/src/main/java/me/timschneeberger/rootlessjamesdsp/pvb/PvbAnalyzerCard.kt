package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.graphics.Typeface
import android.util.AttributeSet
import android.util.TypedValue
import android.widget.LinearLayout
import android.widget.TextView

/** The "실시간 분석" card on the DSP screen: title, the analysis display, a one-line readout and a short key. */
class PvbAnalyzerCard @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val title = TextView(context)
    private val analyzer = PvbAnalyzerView(context)
    private val readout = TextView(context)
    private val key = TextView(context)

    init {
        orientation = VERTICAL
        val pad = dp(16)
        setPadding(pad, dp(14), pad, dp(14))

        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        title.setTypeface(title.typeface, Typeface.BOLD)
        title.text = "실시간 분석"
        addView(title)

        val lp = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        lp.topMargin = dp(10)
        addView(analyzer, lp)

        readout.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        readout.typeface = Typeface.MONOSPACE
        readout.setLines(2)  // fixed height: the text changes several times a second
        readout.setPadding(0, dp(8), 0, 0)
        readout.text = "분석 대기 중"
        addView(readout)

        key.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
        key.setLineSpacing(0f, 1.15f)
        key.setPadding(0, dp(6), 0, 0)
        key.alpha = 0.75f
        key.text = "왼쪽 눈금은 스펙트럼(1/12옥타브, 1 kHz 기준 +3 dB/옥타브 기울기), 오른쪽 눈금은 EQ입니다. " +
            "실측 변화는 출력 − 입력(출력 레벨 제외)이라 리미터가 걸리면 EQ 곡선 아래로 내려갑니다. " +
            "스피커 반영은 볼륨 60 실측 응답을 더한 추정입니다. 범례를 누르면 선을 켜고 끕니다."
        addView(key)

        analyzer.readoutListener = { readout.text = it }
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
}

package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.graphics.Typeface
import android.util.AttributeSet
import android.util.TypedValue
import android.widget.LinearLayout
import android.widget.Button
import android.widget.TextView

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
    private val status = PvbStatusText(context)
    private var attached = false

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
        researchCopy.setOnClickListener { PvbStatusText.copyResearch(context) }
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
        val r = status.render("서비스가 꺼져 있습니다. 위의 전원 버튼으로 켜면 상태가 여기에 표시됩니다.")
        researchCopy.visibility = if (r.canCopyResearch) VISIBLE else GONE
        body.text = r.text
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    companion object {
        private const val REFRESH_MS = 500L
    }
}

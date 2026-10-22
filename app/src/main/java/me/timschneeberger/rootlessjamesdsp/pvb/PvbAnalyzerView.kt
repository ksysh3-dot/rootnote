package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.AttributeSet
import android.util.TypedValue
import android.view.MotionEvent
import android.view.View
import java.util.Locale
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Live analysis display (design: "실시간 분석"): input and output spectra, the EQ curve the engine is using
 * right now, the measured change (output - input), an optional speaker overlay and a 6 s limiter strip.
 *
 * The native analysis runs on a worker thread, 30 times a second, and only while this view is on screen.
 * The display itself is a dark instrument screen in both app themes.
 */
class PvbAnalyzerView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    /** Called on the UI thread with a one-line summary (low-mid gain, limiter values), at most 4 times a second. */
    var readoutListener: ((String) -> Unit)? = null

    // ------------------------------------------------------------------------------------------ data
    private val freqs = FloatArray(POINTS) { PvbAnaInfo.pointHz(it, POINTS) }
    private val tilt = FloatArray(POINTS) { (TILT_DB_PER_OCT * ln(freqs[it] / 1000f) / LN2) }
    private val speaker = FloatArray(POINTS) { speakerDb(freqs[it]) }

    private val lock = Any()
    private val fIn = FloatArray(POINTS)
    private val fOut = FloatArray(POINTS)
    private val fDiff = FloatArray(POINTS)
    private val fEq = FloatArray(POINTS)
    private val fInfo = FloatArray(PvbAnaInfo.COUNT)
    private val grApp = FloatArray(HISTORY)
    private val grPhone = FloatArray(HISTORY)
    private var histPos = 0
    private var hasData = false
    private var everFresh = false
    private var engineMissing = true
    private var lastFreshMs = 0L
    private var lastComputeMs = 0L
    private var lastHistMs = 0L
    private var histAccMs = 0f
    private var curLim = 0f
    private var limHold = 0f
    private var estHold = 0f
    private var lastReadout = ""
    private var lastReadoutMs = 0L

    private val show = BooleanArray(LEGEND.size)
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    // ------------------------------------------------------------------------------------------ threads
    /** One worker per attach, with its own buffers, so a late call from an old worker cannot mix in. */
    private inner class Work {
        val thread = HandlerThread("pvb-analysis").apply { start() }
        val handler = Handler(thread.looper)
        val bIn = FloatArray(POINTS)
        val bOut = FloatArray(POINTS)
        val bDiff = FloatArray(POINTS)
        val bEq = FloatArray(POINTS)
        val bInfo = FloatArray(PvbAnaInfo.COUNT)
        @Volatile
        var busy = false
        val compute = Runnable { computeOn(this) }
    }

    @Volatile
    private var work: Work? = null
    private var attached = false
    private val tmpRect = Rect()

    private val uiTick = object : Runnable {
        override fun run() {
            if (!attached) return
            val visible = isShown && windowVisibility == VISIBLE && getGlobalVisibleRect(tmpRect)
            val w = work
            if (visible && w != null && !w.busy) {
                w.busy = true
                w.handler.post(w.compute)
            }
            postDelayed(this, if (visible) FRAME_MS else OFFSCREEN_MS)
        }
    }

    private fun computeOn(w: Work) {
        val e = PvbRuntime.engine
        val ok = e != null && e.analyze(w.bIn, w.bOut, w.bDiff, w.bEq, w.bInfo)
        val now = SystemClock.uptimeMillis()
        var text: String? = null
        synchronized(lock) {
            if (w !== work) {
                w.busy = false
                return
            }
            engineMissing = e == null
            if (ok) {
                System.arraycopy(w.bIn, 0, fIn, 0, POINTS)
                System.arraycopy(w.bOut, 0, fOut, 0, POINTS)
                System.arraycopy(w.bDiff, 0, fDiff, 0, POINTS)
                System.arraycopy(w.bEq, 0, fEq, 0, POINTS)
                System.arraycopy(w.bInfo, 0, fInfo, 0, PvbAnaInfo.COUNT)
                hasData = true
                val fresh = w.bInfo[PvbAnaInfo.FRESH] >= 0.5f
                if (fresh) {
                    everFresh = true
                    lastFreshMs = now
                    // gain reduction of the newest audio block; it stands until the next block arrives
                    curLim = w.bInfo[PvbAnaInfo.LIM_GR_DB] * w.bInfo[PvbAnaInfo.MIX]
                }
                val est = w.bInfo[PvbAnaInfo.EST_GR_DB]
                val live = everFresh && now - lastFreshMs < IDLE_AFTER_MS
                if (live) {
                    val dt = (now - lastComputeMs).coerceIn(0L, 200L) / 1000f
                    limHold = max(if (fresh) curLim else 0f, limHold - HOLD_FALL_DB_PER_S * dt)
                    estHold = max(est, estHold - HOLD_FALL_DB_PER_S * dt)
                    // the strip moves with the clock: one column per SLOT_MS, whatever the block size
                    histAccMs += (now - lastHistMs).coerceIn(0L, 6000L).toFloat()
                    var pushed = 0
                    while (histAccMs >= SLOT_MS && pushed < HISTORY) {
                        grApp[histPos] = curLim
                        grPhone[histPos] = est
                        histPos = (histPos + 1) % HISTORY
                        histAccMs -= SLOT_MS
                        pushed++
                    }
                    if (pushed == HISTORY) histAccMs = 0f
                }
                lastHistMs = now
            }
            lastComputeMs = now
            text = readoutText(now)
        }
        w.busy = false
        text?.let { t -> post { readoutListener?.invoke(t) } }
        postInvalidateOnAnimation()
    }

    // ------------------------------------------------------------------------------------------ drawing tools
    private val density = resources.displayMetrics.density
    private fun dp(v: Float) = v * density
    private fun sp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, v, resources.displayMetrics)

    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = C_BG }
    private val gridPaint = Paint().apply { color = C_GRID; strokeWidth = dp(1f) }
    private val gridMinorPaint = Paint().apply { color = C_GRID; alpha = 110; strokeWidth = dp(1f) }
    private val zeroPaint = Paint().apply { color = C_GRID_STRONG; strokeWidth = dp(1f) }
    private val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = C_TEXT; textSize = sp(10.5f); typeface = Typeface.MONOSPACE
    }
    private val eqLabelPaint = Paint(labelPaint).apply { color = C_EQ; alpha = 190 }
    private val notePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = C_TEXT; textSize = sp(11f) }
    private val overlayPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFE7E1EC.toInt(); textSize = sp(13f); textAlign = Paint.Align.CENTER
    }
    private val legendPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFE7E1EC.toInt(); textSize = sp(12.5f) }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND
    }
    private val dashSpk = DashPathEffect(floatArrayOf(dp(6f), dp(4f)), 0f)
    private val dotDiff = DashPathEffect(floatArrayOf(dp(0.5f), dp(3.5f)), 0f)
    private val dashEqOff = DashPathEffect(floatArrayOf(dp(8f), dp(5f)), 0f)
    private val legendDash = DashPathEffect(floatArrayOf(dp(4f), dp(3f)), 0f)
    private val path = Path()
    private val fillPath = Path()
    private val plot = RectF()
    private val strip = RectF()
    private val legendRects = Array(LEGEND.size) { RectF() }
    private var legendTop = 0f
    private var legendRows = 1
    private var pressed = -1

    init {
        for (i in LEGEND.indices) show[i] = prefs.getBoolean("ana_show_${LEGEND[i].key}", LEGEND[i].default)
        contentDescription = "실시간 분석: 입력과 출력 스펙트럼, EQ 곡선, 리미터 감쇠"
        isClickable = true
    }

    // ------------------------------------------------------------------------------------------ lifecycle
    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        attached = true
        work?.thread?.quitSafely()
        work = Work()
        removeCallbacks(uiTick)
        post(uiTick)
    }

    override fun onDetachedFromWindow() {
        attached = false
        removeCallbacks(uiTick)
        val w = work
        work = null
        w?.thread?.quitSafely()
        super.onDetachedFromWindow()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        val plotH = w * PLOT_RATIO
        legendRows = layoutLegend(w.toFloat(), 0f, apply = false)
        val h = plotH + dp(6f) + legendRows * dp(LEGEND_ROW_DP) + dp(6f) + dp(STRIP_DP)
        setMeasuredDimension(w, h.roundToInt())
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        val plotH = w * PLOT_RATIO
        plot.set(dp(34f), dp(24f), w - dp(32f), plotH - dp(20f))
        legendTop = plotH + dp(6f)
        legendRows = layoutLegend(w.toFloat(), legendTop, apply = true)
        val stripTop = legendTop + legendRows * dp(LEGEND_ROW_DP) + dp(6f)
        strip.set(0f, stripTop, w.toFloat(), stripTop + dp(STRIP_DP))
    }

    /** Places the legend items in rows from [top] (only counts when [apply] is false); returns the row count. */
    private fun layoutLegend(width: Float, top: Float, apply: Boolean): Int {
        val pad = dp(10f)
        val gap = dp(6f)
        var x = 0f
        var row = 0
        for (i in LEGEND.indices) {
            val w = dp(16f) + dp(6f) + legendPaint.measureText(LEGEND[i].label) + 2 * pad
            if (x > 0f && x + w > width) {
                row++
                x = 0f
            }
            val y = top + row * dp(LEGEND_ROW_DP)
            if (apply) legendRects[i].set(x, y + dp(2f), x + w, y + dp(LEGEND_ROW_DP) - dp(2f))
            x += w + gap
        }
        return row + 1
    }

    // ------------------------------------------------------------------------------------------ touch (legend)
    override fun onTouchEvent(event: MotionEvent): Boolean {
        val hit = legendRects.indexOfFirst { it.contains(event.x, event.y) }
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                pressed = hit
                if (hit < 0) return false
                invalidate()
                return true
            }
            MotionEvent.ACTION_UP -> {
                if (pressed >= 0 && hit == pressed) {
                    show[hit] = !show[hit]
                    prefs.edit().putBoolean("ana_show_${LEGEND[hit].key}", show[hit]).apply()
                    performClick()
                }
                pressed = -1
                invalidate()
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                pressed = -1
                invalidate()
            }
        }
        return pressed >= 0
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    // ------------------------------------------------------------------------------------------ draw
    private fun xOf(f: Float) = plot.left + (ln(f / F_MIN) / LN_SPAN) * plot.width()
    private fun ySpec(v: Float) = plot.top + (SPEC_TOP - v) / (SPEC_TOP - SPEC_BOT) * plot.height()
    private fun yEq(v: Float) = plot.top + (EQ_TOP - v) / (EQ_TOP - EQ_BOT) * plot.height()
    private fun clampY(y: Float) = min(plot.bottom + dp(2f), max(plot.top - dp(2f), y))

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val r = dp(14f)
        canvas.drawRoundRect(0f, 0f, width.toFloat(), legendTop - dp(4f), r, r, bgPaint)
        canvas.drawRoundRect(strip, r, r, bgPaint)
        drawGrid(canvas)

        if (PvbRuntime.abHidden) {
            // Blind comparison: the curves would give the condition away.
            drawOverlay(canvas, "블라인드 비교 중", "어떤 설정인지 드러나지 않게 분석 화면을 숨깁니다")
            synchronized(lock) { drawLegend(canvas) }
            return
        }

        val now = SystemClock.uptimeMillis()
        val pvbOn = PvbRuntime.status.enabled
        synchronized(lock) {
            val live = everFresh && now - lastFreshMs < IDLE_AFTER_MS
            val mix = if (hasData) fInfo[PvbAnaInfo.MIX] else 1f
            canvas.save()
            canvas.clipRect(plot.left, plot.top - dp(3f), plot.right, plot.bottom + dp(3f))
            if (hasData && everFresh) {
                if (show[L_IN]) drawSpectrum(canvas, fIn, C_IN, fillAlpha = 105, lineWidth = 1.2f)
                if (show[L_OUT]) drawSpectrum(canvas, fOut, C_OUT, fillAlpha = 30, lineWidth = 1.6f)
                // The S26 Ultra speaker response is drawn only where it applies (general build: S26U profile).
                if (show[L_SPK] && PvbGeneral.phoneModelCurves(context)) drawSpeaker(canvas)
                if (show[L_DIFF]) drawEqLine(canvas, fDiff, C_DIFF, 2.2f, dotDiff, 255)
            }
            if (hasData && show[L_EQ]) {
                val alpha = (90 + 165 * mix).roundToInt().coerceIn(0, 255)
                drawEqLine(canvas, fEq, C_EQ, 2.4f, if (mix < 0.5f) dashEqOff else null, alpha)
            }
            canvas.restore()

            when {
                engineMissing -> drawOverlay(canvas, "서비스가 꺼져 있습니다", "아래 전원 버튼으로 켜면 분석이 시작됩니다")
                !pvbOn -> drawOverlay(canvas, "PVB 꺼짐", "원래 JamesDSP가 처리하는 동안은 분석하지 않습니다")
                live && silent() -> drawOverlay(canvas, "소리 없음", "재생이 일시정지되었거나 무음 구간입니다")
                !live -> drawOverlay(canvas, "대기 중", if (everFresh) "재생이 멈춰 마지막 모습을 보여 주는 중" else "음악을 재생하면 그래프가 움직입니다")
                mix < 0.5f && show[L_EQ] -> {
                    eqLabelPaint.textAlign = Paint.Align.RIGHT
                    canvas.drawText("PVB 꺼짐 · 점선은 켤 때의 곡선", plot.right - dp(6f), plot.bottom - dp(8f), eqLabelPaint)
                    eqLabelPaint.textAlign = Paint.Align.LEFT
                }
            }

            drawLegend(canvas)
            drawStrip(canvas)
        }
    }

    /** True when the input spectrum is at the floor everywhere (paused player still feeding zeros). Under [lock]. */
    private fun silent(): Boolean {
        for (v in fIn) if (!v.isNaN() && v > SILENT_DB) return false
        return true
    }

    private fun drawGrid(canvas: Canvas) {
        for (f in MINOR_HZ) {
            val x = xOf(f)
            canvas.drawLine(x, plot.top, x, plot.bottom, gridMinorPaint)
        }
        for (f in MAJOR_HZ) {
            val x = xOf(f)
            canvas.drawLine(x, plot.top, x, plot.bottom, gridPaint)
        }
        for (k in 0..4) {
            val y = plot.top + k * plot.height() / 4f
            canvas.drawLine(plot.left, y, plot.right, y, if (k == 2) zeroPaint else gridPaint)
        }
        // frequency labels, skipping any that would collide
        labelPaint.textAlign = Paint.Align.CENTER
        var lastRight = -1e9f
        val baseY = plot.bottom + dp(14f)
        for (i in MAJOR_HZ.indices) {
            val label = MAJOR_LABELS[i]
            val w = labelPaint.measureText(label)
            val x = min(plot.right - w / 2f, max(plot.left + w / 2f, xOf(MAJOR_HZ[i])))
            if (x - w / 2f < lastRight + dp(5f)) continue
            canvas.drawText(label, x, baseY, labelPaint)
            lastRight = x + w / 2f
        }
        // level labels: spectrum on the left, EQ on the right (same grid lines)
        val fm = labelPaint.fontMetrics
        val mid = -(fm.ascent + fm.descent) / 2f
        for (k in 0..4) {
            val y = plot.top + k * plot.height() / 4f + mid
            labelPaint.textAlign = Paint.Align.RIGHT
            canvas.drawText((SPEC_TOP - k * 24f).roundToInt().toString(), plot.left - dp(5f), y, labelPaint)
            val e = (EQ_TOP - k * 6f).roundToInt()
            eqLabelPaint.textAlign = Paint.Align.LEFT
            canvas.drawText(if (e > 0) "+$e" else "$e", plot.right + dp(5f), y, eqLabelPaint)
        }
        notePaint.textAlign = Paint.Align.LEFT
        canvas.drawText("스펙트럼 dB", dp(10f), dp(15f), notePaint)
        notePaint.textAlign = Paint.Align.RIGHT
        canvas.drawText("EQ dB", width - dp(10f), dp(15f), notePaint)
    }

    private fun drawSpectrum(canvas: Canvas, v: FloatArray, color: Int, fillAlpha: Int, lineWidth: Float) {
        path.reset()
        fillPath.reset()
        var started = false
        var lastX = 0f
        for (i in 0 until POINTS) {
            val d = v[i]
            if (d.isNaN()) continue
            val x = xOf(freqs[i])
            val y = clampY(ySpec(d + tilt[i]))
            if (!started) {
                path.moveTo(x, y)
                fillPath.moveTo(x, plot.bottom)
                fillPath.lineTo(x, y)
                started = true
            } else {
                path.lineTo(x, y)
                fillPath.lineTo(x, y)
            }
            lastX = x
        }
        if (!started) return
        fillPath.lineTo(lastX, plot.bottom)
        fillPath.close()
        fillPaint.color = color
        fillPaint.alpha = fillAlpha
        canvas.drawPath(fillPath, fillPaint)
        linePaint.color = color
        linePaint.alpha = 255
        linePaint.strokeWidth = dp(lineWidth)
        linePaint.pathEffect = null
        canvas.drawPath(path, linePaint)
    }

    private fun drawSpeaker(canvas: Canvas) {
        path.reset()
        var pen = false
        for (i in 0 until POINTS) {
            val s = speaker[i]
            val d = fOut[i]
            if (s.isNaN() || d.isNaN()) {
                pen = false
                continue
            }
            val x = xOf(freqs[i])
            val y = clampY(ySpec(d + s + tilt[i]))
            if (!pen) path.moveTo(x, y) else path.lineTo(x, y)
            pen = true
        }
        linePaint.color = C_SPK
        linePaint.alpha = 255
        linePaint.strokeWidth = dp(1.6f)
        linePaint.pathEffect = dashSpk
        canvas.drawPath(path, linePaint)
        linePaint.pathEffect = null
    }

    private fun drawEqLine(canvas: Canvas, v: FloatArray, color: Int, w: Float, effect: DashPathEffect?, alpha: Int) {
        path.reset()
        var pen = false
        for (i in 0 until POINTS) {
            val d = v[i]
            if (d.isNaN()) {
                pen = false
                continue
            }
            val x = xOf(freqs[i])
            val y = clampY(yEq(d))
            if (!pen) path.moveTo(x, y) else path.lineTo(x, y)
            pen = true
        }
        linePaint.color = color
        linePaint.alpha = alpha
        linePaint.strokeWidth = dp(w)
        linePaint.pathEffect = effect
        canvas.drawPath(path, linePaint)
        linePaint.pathEffect = null
        linePaint.alpha = 255
    }

    private fun drawOverlay(canvas: Canvas, title: String, sub: String) {
        val cx = (plot.left + plot.right) / 2f
        val cy = (plot.top + plot.bottom) / 2f
        val boxW = min(plot.width() - dp(16f), max(overlayPaint.measureText(sub), overlayPaint.measureText(title)) + dp(28f))
        fillPaint.color = C_BG
        fillPaint.alpha = 215
        canvas.drawRoundRect(cx - boxW / 2f, cy - dp(28f), cx + boxW / 2f, cy + dp(26f), dp(10f), dp(10f), fillPaint)
        overlayPaint.isFakeBoldText = true
        canvas.drawText(title, cx, cy - dp(6f), overlayPaint)
        overlayPaint.isFakeBoldText = false
        overlayPaint.alpha = 190
        overlayPaint.textSize = sp(11.5f)
        canvas.drawText(sub, cx, cy + dp(14f), overlayPaint)
        overlayPaint.textSize = sp(13f)
        overlayPaint.alpha = 255
    }

    private fun drawLegend(canvas: Canvas) {
        val fm = legendPaint.fontMetrics
        for (i in LEGEND.indices) {
            val item = LEGEND[i]
            val rect = legendRects[i]
            val on = show[i]
            fillPaint.color = if (i == pressed) C_GRID_STRONG else C_BG
            fillPaint.alpha = if (on) 255 else 140
            canvas.drawRoundRect(rect, rect.height() / 2f, rect.height() / 2f, fillPaint)
            val sx = rect.left + dp(10f)
            val cy = rect.centerY()
            linePaint.color = item.color
            linePaint.alpha = if (on) 255 else 80
            linePaint.strokeWidth = dp(if (item.style == STYLE_FILL) 8f else 3f)
            linePaint.strokeCap = if (item.style == STYLE_FILL) Paint.Cap.SQUARE else Paint.Cap.ROUND
            linePaint.pathEffect = when (item.style) {
                STYLE_DASH -> legendDash
                STYLE_DOT -> dotDiff
                else -> null
            }
            canvas.drawLine(sx + dp(2f), cy, sx + dp(14f), cy, linePaint)
            linePaint.pathEffect = null
            linePaint.strokeCap = Paint.Cap.ROUND
            linePaint.alpha = 255
            legendPaint.alpha = if (on) 255 else 110
            legendPaint.textAlign = Paint.Align.LEFT
            canvas.drawText(item.label, sx + dp(22f), cy - (fm.ascent + fm.descent) / 2f, legendPaint)
        }
        legendPaint.alpha = 255
    }

    private fun drawStrip(canvas: Canvas) {
        val top = strip.top + dp(22f)
        val bottom = strip.bottom - dp(7f)
        val left = strip.left + dp(10f)
        val right = strip.right - dp(36f)
        fun yOf(d: Float) = top + (min(max(d, 0f), STRIP_MAX_DB) / STRIP_MAX_DB) * (bottom - top)
        for (d in floatArrayOf(0f, 6f, 12f)) canvas.drawLine(left, yOf(d), right, yOf(d), gridPaint)
        labelPaint.textAlign = Paint.Align.LEFT
        val fm = labelPaint.fontMetrics
        val mid = -(fm.ascent + fm.descent) / 2f
        canvas.drawText("0", right + dp(5f), yOf(0f) + mid, labelPaint)
        canvas.drawText("6", right + dp(5f), yOf(6f) + mid, labelPaint)
        canvas.drawText("12dB", right + dp(5f), yOf(12f) + mid, labelPaint)
        notePaint.textAlign = Paint.Align.LEFT
        canvas.drawText("리미터 감쇠 · 최근 6초", left, strip.top + dp(15f), notePaint)
        notePaint.textAlign = Paint.Align.RIGHT
        notePaint.color = C_LIM
        canvas.drawText("— 폰 저음 눌림", strip.right - dp(10f), strip.top + dp(15f), notePaint)
        val phoneW = notePaint.measureText("— 폰 저음 눌림")
        notePaint.color = C_OUT
        canvas.drawText("■ 앱", strip.right - dp(18f) - phoneW, strip.top + dp(15f), notePaint)
        notePaint.color = C_TEXT

        val step = (right - left) / HISTORY
        fillPaint.color = C_OUT
        fillPaint.alpha = 255
        for (i in 0 until HISTORY) {
            val v = grApp[(histPos + i) % HISTORY]
            if (v > 0.05f) {
                val x = left + i * step
                canvas.drawRect(x, top, x + max(step, dp(1f)), yOf(v), fillPaint)
            }
        }
        path.reset()
        for (i in 0 until HISTORY) {
            val x = left + i * step
            val y = yOf(grPhone[(histPos + i) % HISTORY])
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        linePaint.color = C_LIM
        linePaint.alpha = 255
        linePaint.strokeWidth = dp(1.5f)
        linePaint.pathEffect = null
        canvas.drawPath(path, linePaint)
    }

    /** The one-line summary for the card, or null when it has not changed or was sent too recently. Under [lock]. */
    private fun readoutText(now: Long): String? {
        if (now - lastReadoutMs < READOUT_MS) return null
        val live = everFresh && now - lastFreshMs < IDLE_AFTER_MS
        val text = if (PvbRuntime.abHidden) {
            "블라인드 비교 중"
        } else if (!hasData) {
            "분석 대기 중"
        } else if (!PvbRuntime.status.enabled) {
            "PVB 꺼짐 (원래 JamesDSP 처리 중)"
        } else {
            val mix = fInfo[PvbAnaInfo.MIX]
            val low = if (mix < 0.5f) "꺼짐" else signed(fInfo[PvbAnaInfo.LOW_DB_NOW]) + " dB"
            val lim = if (live) minus(limHold) + " dB" else "–"
            val est = if (live) minus(estHold) + " dB" else "–"
            val dyn = fInfo[PvbAnaInfo.DYN_DB]
            val dynText = if (dyn != 0f && mix >= 0.5f) " (조용한 구간 ${signed(dyn)})" else ""
            "저중역 보정 $low$dynText · 앱 리미터 $lim · 폰 저음 눌림(추정) $est"
        }
        lastReadoutMs = now
        if (text == lastReadout) return null
        lastReadout = text
        return text
    }

    // ------------------------------------------------------------------------------------------ constants
    private class LegendItem(val key: String, val label: String, val color: Int, val style: Int, val default: Boolean)

    companion object {
        const val POINTS = 240
        private const val FRAME_MS = 33L
        private const val OFFSCREEN_MS = 250L
        private const val SILENT_DB = -130f
        private const val IDLE_AFTER_MS = 1200L
        private const val READOUT_MS = 250L
        private const val HISTORY = 180          // strip columns
        private const val SLOT_MS = 6000f / HISTORY  // 6 s across the strip
        private const val HOLD_FALL_DB_PER_S = 10f
        private const val PLOT_RATIO = 0.64f
        private const val LEGEND_ROW_DP = 34f
        private const val STRIP_DP = 74f
        private const val STRIP_MAX_DB = 12f
        private const val SPEC_TOP = 0f
        private const val SPEC_BOT = -96f
        private const val EQ_TOP = 12f
        private const val EQ_BOT = -12f
        private const val TILT_DB_PER_OCT = 3f
        private const val F_MIN = 20f
        private val LN_SPAN = ln(1000f)
        private val LN2 = ln(2f)
        private const val PREFS = "pvb_ui"

        private const val C_BG = 0xFF131218.toInt()
        private const val C_GRID = 0xFF2A2833.toInt()
        private const val C_GRID_STRONG = 0xFF3A3746.toInt()
        private const val C_TEXT = 0xFF8D879B.toInt()
        private const val C_IN = 0xFF77728A.toInt()
        private const val C_OUT = 0xFFC3B1FF.toInt()
        private const val C_EQ = 0xFFF4A93B.toInt()
        private const val C_DIFF = 0xFF7EE2B0.toInt()
        private const val C_SPK = 0xFF7CC8F5.toInt()
        private const val C_LIM = 0xFFFF8A6B.toInt()

        private const val STYLE_LINE = 0
        private const val STYLE_FILL = 1
        private const val STYLE_DASH = 2
        private const val STYLE_DOT = 3
        private const val L_IN = 0
        private const val L_OUT = 1
        private const val L_EQ = 2
        private const val L_DIFF = 3
        private const val L_SPK = 4
        private val LEGEND = arrayOf(
            LegendItem("in", "입력", C_IN, STYLE_FILL, true),
            LegendItem("out", "출력", C_OUT, STYLE_LINE, true),
            LegendItem("eq", "EQ 곡선", C_EQ, STYLE_LINE, true),
            LegendItem("diff", "실측 변화", C_DIFF, STYLE_DOT, true),
            LegendItem("spk", "스피커 반영", C_SPK, STYLE_DASH, false),
        )

        private val MAJOR_HZ = floatArrayOf(20f, 50f, 100f, 200f, 500f, 1000f, 2000f, 5000f, 10000f, 20000f)
        private val MAJOR_LABELS = arrayOf("20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k")
        private val MINOR_HZ = floatArrayOf(
            30f, 40f, 60f, 70f, 80f, 90f, 300f, 400f, 600f, 700f, 800f, 900f,
            3000f, 4000f, 6000f, 7000f, 8000f, 9000f,
        )

        // S26 Ultra speaker response at volume 60 (gated, UMIK-calibrated, 1 kHz = 0 dB), measured 2026-10.
        private val SPK_HZ = floatArrayOf(
            40f, 48f, 58f, 69f, 83f, 99f, 119f, 143f, 171f, 205f, 246f, 295f, 353f, 424f, 508f, 609f, 731f,
            876f, 1050f, 1260f, 1510f, 1811f, 2172f, 2604f, 3122f, 3744f, 4489f, 5383f, 6455f, 7740f, 9280f,
            11128f, 13343f, 16000f,
        )
        private val SPK_DB = floatArrayOf(
            -35.1f, -34.4f, -32.7f, -30.1f, -26.8f, -23.7f, -20.9f, -18.9f, -17.1f, -13.7f, -9.6f, -6.5f, -3.9f,
            -3.0f, -4.8f, -1.8f, 0.5f, 2.9f, 0.6f, 4.5f, 4.8f, 3.8f, 8.3f, 12.5f, 12.8f, 11.0f, 14.4f, 16.5f,
            12.7f, 8.4f, 0.0f, -6.1f, -9.2f, -7.4f,
        )

        /** Speaker response at [f] (log-frequency interpolation), NaN outside the measured range. */
        fun speakerDb(f: Float): Float {
            if (f < SPK_HZ.first() || f > SPK_HZ.last()) return Float.NaN
            for (i in 1 until SPK_HZ.size) {
                if (f <= SPK_HZ[i]) {
                    val t = ln(f / SPK_HZ[i - 1]) / ln(SPK_HZ[i] / SPK_HZ[i - 1])
                    return SPK_DB[i - 1] + t * (SPK_DB[i] - SPK_DB[i - 1])
                }
            }
            return SPK_DB.last()
        }

        private fun signed(v: Float): String {
            val r = (v * 10f).roundToInt() / 10f
            return String.format(Locale.US, "%+.1f", if (abs(r) < 0.05f) 0f else r)
        }

        private fun minus(gr: Float): String {
            val r = (gr * 10f).roundToInt() / 10f
            return if (r < 0.05f) "0.0" else String.format(Locale.US, "−%.1f", r)
        }
    }
}

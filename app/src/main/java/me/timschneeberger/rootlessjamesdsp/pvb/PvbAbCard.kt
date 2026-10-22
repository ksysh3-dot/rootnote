package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Typeface
import android.media.AudioManager
import android.os.SystemClock
import android.util.AttributeSet
import android.util.TypedValue
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.random.Random

/**
 * In-app blind comparison on the live path: the music the user is playing goes through condition A or B,
 * switched instantly; which setting is A is hidden until the end. Each run has [TRIALS] trials with a fresh
 * random assignment. Results are kept in the app (last 30 runs) and can be copied as JSON.
 */
class PvbAbCard @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val pairs = PvbAbConditions.PAIRS
    private val prefs = context.getSharedPreferences(PvbRuntime.AB_PREFS, Context.MODE_PRIVATE)

    private val title = TextView(context)
    private val intro = TextView(context)
    private val spinner = Spinner(context)
    private val volumeNote = TextView(context)
    private val startBtn = Button(context)
    private val trialBox = LinearLayout(context)
    private val progress = TextView(context)
    private val nowPlaying = TextView(context)
    private val aBtn = Button(context)
    private val bBtn = Button(context)
    private val preferA = Button(context)
    private val preferB = Button(context)
    private val same = Button(context)
    private val annoyA = CheckBox(context)
    private val annoyB = CheckBox(context)
    private val stopBtn = Button(context)
    private val resultText = TextView(context)
    private val copyBtn = Button(context)
    private val returnBox = LinearLayout(context)
    private val returnHint = TextView(context)
    private val returnBtn = Button(context)

    private class Trial(val aIsFirst: Boolean) {
        var choice = ""             // "A", "B" or "="
        var annoyA = false
        var annoyB = false
        var switches = 0
        var startedMs = 0L
        var seconds = 0.0
        var heardA = false
        var heardB = false
    }

    private var pairIndex = 0
    private var trials = ArrayList<Trial>()
    private var current = -1
    private var playing = 0             // 0 = silent (between trials), 1 = A, 2 = B
    private var inGap = false
    private var seq = 0                 // invalidates delayed steps of an earlier trial or run
    private var lastCond: PvbRuntime.AbCondition? = null
    private var lastJson = ""
    private var startVolume = 0
    private var runFirst: PvbRuntime.AbCondition? = null
    private var runSecond: PvbRuntime.AbCondition? = null
    private var runTrims = floatArrayOf(0f, 0f)
    private var runVolume: Map<String, Int>? = null      // stage comparison: volume index per condition id
    private var runPlan: PvbMeasureMath.StagePlan? = null
    private var pendingRestore = -1   // stage run ended: volume still to be put back (done at once if a run starts)
    private var runSeq = 0            // invalidates the run monitor of an earlier run
    private val audio = context.getSystemService(AudioManager::class.java)

    /** Any change of the output device ends a run: the trial in progress is not recorded. */
    private val routeListener: () -> Unit = {
        if (current >= 0) {
            stop(aborted = true)
            resultText.text = "출력 장치가 바뀌어 비교를 중단했습니다. 진행 중이던 회차는 기록하지 않습니다.\n" + resultText.text
        }
    }

    init {
        orientation = VERTICAL
        val pad = dp(16)
        setPadding(pad, dp(14), pad, dp(14))

        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        title.setTypeface(title.typeface, Typeface.BOLD)
        title.text = "블라인드 비교"
        addView(title)

        intro.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        intro.setLineSpacing(0f, 1.15f)
        intro.setPadding(0, dp(6), 0, dp(8))
        intro.text = "지금 재생 중인 곡에서 두 설정을 A와 B로 바꿔 들으며 고릅니다. 회차마다 A와 B가 무작위로 " +
            "바뀌고, 어떤 설정이었는지는 끝난 뒤에 공개됩니다. 회차 사이에는 소리를 잠깐 끊어서 앞 회차와 " +
            "비교할 수 없게 합니다. 음량은 폰 모델로 맞춘 값이라 곡에 따라 조금 차이가 남을 수 있습니다. " +
            "비교하는 동안에는 상태와 분석 화면을 숨기고, 화면을 돌리거나 나가면 중단됩니다."
        addView(intro)

        spinner.adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, pairs.map { it.label })
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                pairIndex = position
                updateNote()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        addView(spinner, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        volumeNote.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        volumeNote.setLineSpacing(0f, 1.15f)
        volumeNote.setPadding(0, dp(6), 0, dp(4))
        volumeNote.setTypeface(volumeNote.typeface, Typeface.BOLD)
        updateNote()
        addView(volumeNote)

        startBtn.text = "시작 ($TRIALS 회)"
        startBtn.setOnClickListener { if (isVbPair()) confirmVb { start() } else start() }
        addView(startBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // ---- trial box
        trialBox.orientation = VERTICAL
        trialBox.visibility = GONE
        progress.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
        progress.setTypeface(progress.typeface, Typeface.BOLD)
        trialBox.addView(progress)
        nowPlaying.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        nowPlaying.setPadding(0, dp(2), 0, dp(4))
        trialBox.addView(nowPlaying)
        trialBox.addView(row(aBtn, bBtn))
        aBtn.text = "A 듣기"
        bBtn.text = "B 듣기"
        aBtn.setOnClickListener { play(true) }
        bBtn.setOnClickListener { play(false) }

        val ask = TextView(context)
        ask.text = "어느 쪽이 더 좋습니까?"
        ask.setPadding(0, dp(8), 0, 0)
        trialBox.addView(ask)
        preferA.text = "A"
        preferB.text = "B"
        same.text = "구분 안 됨"
        preferA.setOnClickListener { answer("A") }
        preferB.setOnClickListener { answer("B") }
        same.setOnClickListener { answer("=") }
        trialBox.addView(row(preferA, preferB, same))
        annoyA.text = "A에 거슬리는 소리 (비프음, 떨림, 찌그러짐)"
        annoyB.text = "B에 거슬리는 소리 (비프음, 떨림, 찌그러짐)"
        trialBox.addView(annoyA)
        trialBox.addView(annoyB)
        stopBtn.text = "중단"
        stopBtn.setOnClickListener { if (current >= 0) stop(aborted = true) }
        trialBox.addView(stopBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(trialBox, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // ---- after a run: own settings 10 dB quieter until the volume is back where it was
        returnBox.orientation = VERTICAL
        returnBox.visibility = GONE
        returnHint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        returnHint.setPadding(0, dp(8), 0, 0)
        returnBox.addView(returnHint)
        returnBtn.text = "볼륨 그대로 원래 출력으로 (10 dB 커집니다)"
        returnBtn.setOnClickListener { finishReturn() }
        returnBox.addView(returnBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(returnBox, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // ---- results
        resultText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        resultText.setLineSpacing(0f, 1.15f)
        resultText.setPadding(0, dp(8), 0, 0)
        resultText.typeface = Typeface.MONOSPACE
        addView(resultText)
        copyBtn.text = "결과 복사 (JSON)"
        copyBtn.visibility = GONE
        copyBtn.setOnClickListener { copyResults() }
        addView(copyBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // Alpha 3.3: the virtual bass comparisons with a verdict per trial, symptoms and export (own screen).
        val liveBtn = Button(context)
        liveBtn.text = "실청 블라인드 비교 (가상 저음, 회차별 판정 저장·내보내기)"
        liveBtn.setOnClickListener {
            if (current >= 0) return@setOnClickListener   // finish or stop this card's run first
            context.startActivity(android.content.Intent(context, me.timschneeberger.rootlessjamesdsp.activity.LiveAbActivity::class.java))
        }
        addView(liveBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        if (PvbRuntime.abReturnVolume >= 0) showReturn()   // a run ended while this screen was away

        val last = prefs.getString(KEY_RESULTS, null)
        if (last != null) {
            try {
                val arr = JSONArray(last)
                resultText.text = "저장된 결과 ${arr.length()}건. 마지막: " + arr.getJSONObject(arr.length() - 1).optString("summary")
                lastJson = arr.toString(1)
                copyBtn.visibility = if (arr.length() > 0) VISIBLE else GONE
            } catch (ignored: Exception) {
            }
        }
    }

    private fun row(vararg views: View): LinearLayout {
        val r = LinearLayout(context)
        r.orientation = HORIZONTAL
        for (v in views) r.addView(v, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        return r
    }

    private fun pair() = pairs[pairIndex]

    private fun conditionFor(aSide: Boolean): PvbRuntime.AbCondition {
        val t = trials[current]
        val first = aSide == t.aIsFirst
        return if (first) runFirst!! else runSecond!!
    }

    /** A pair that plays a virtual bass condition (experimental). */
    private fun isVbPair(p: PvbAbConditions.Pair = pair()) = p.second.condition.apply(PvbSettings()).vbOn

    private fun updateNote() {
        val vbNote = if (isVbPair()) "\n가상 저음은 실험 기능입니다. 두 쪽 모두 같은 지연" +
            (if (pair().second.condition.apply(PvbSettings()).vbAlgo != PvbSettings.VB_BANKSTOWN) "(약 0.15초)" else "(없음)") +
            "으로 재생하므로 지연으로는 구분되지 않습니다. 윙윙거림·잡음이 들리면 '거슬리는 소리'에 표시하세요." else ""
        volumeNote.text = (if (pair().stage) {
            "이 비교는 앱이 볼륨을 직접 바꿉니다. 평소 듣는 볼륨으로 맞춘 뒤 시작하고, 비교하는 동안 볼륨 버튼은 누르지 마세요. " +
                "한쪽은 지금 출력·지금 볼륨, 다른 쪽은 출력을 낮추고 볼륨을 올려 같은 크기로 맞춘 것입니다(아래 측정 결과로 계산). " +
                "A·B를 바꿀 때마다 소리가 잠깐 끊깁니다. 끝나면 볼륨을 시작할 때로 되돌립니다."
        } else {
            "비교하는 동안 두 쪽 모두 ${PvbAbConditions.HEADROOM_DB.toInt()} dB 작게 내보냅니다(폰의 압축을 거의 " +
                "받지 않아야 음량을 맞출 수 있습니다). 처음 들을 때 평소 크기로 들릴 때까지 볼륨을 올리세요(150 기준 20~30). 끝난 뒤에도 " +
                "원래 설정이 10 dB 낮게 나오다가, 볼륨을 시작할 때 크기로 내리면 원래 출력으로 돌아갑니다."
        }) + vbNote + (pair().unavailableReason?.let { "\n$it" } ?: "")
    }

    /** The virtual bass warning (same text as in the settings), once, before the first comparison that plays it. */
    private fun confirmVb(then: () -> Unit) {
        if (prefs.getBoolean(KEY_VB_WARNING_OK, false)) {
            then()
            return
        }
        android.app.AlertDialog.Builder(context)
            .setTitle(context.getString(me.timschneeberger.rootlessjamesdsp.R.string.pvb_vb_warning_title))
            .setMessage(context.getString(me.timschneeberger.rootlessjamesdsp.R.string.pvb_vb_warning))
            .setPositiveButton(context.getString(me.timschneeberger.rootlessjamesdsp.R.string.pvb_vb_warning_ok)) { _, _ ->
                prefs.edit().putBoolean(KEY_VB_WARNING_OK, true).apply()
                then()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    /** Sets up the two conditions of this run; null = ready, otherwise the reason it cannot start. */
    private fun prepareRun(): String? {
        val p = pair()
        p.unavailableReason?.let { return it }
        runVolume = null
        runPlan = null
        if (!p.stage) {
            runFirst = p.first.condition
            runSecond = p.second.condition
            runTrims = floatArrayOf(p.first.trimDb, p.second.trimDb)
            return null
        }
        if (PvbRuntime.abReturnVolume >= 0) {
            return "앞 비교 뒤라 볼륨이 올라가 있습니다. 볼륨을 ${PvbRuntime.abReturnVolume}단계로 내린 뒤 시작하세요."
        }
        val m = PvbMeasure.load(context) ?: return "먼저 아래 '측정'을 해 주세요. 볼륨 단계와 폰 압축을 재야 이 비교의 크기를 맞출 수 있습니다."
        val base = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        // only a plan whose microphone check passed at this very volume (and on the speaker) may run
        val checked = PvbMeasure.checkedStagePlan(m, base)
        val plan = checked.plan ?: return checked.reason
        val x = plan.outDropDb.toFloat()
        // no common headroom here: the comparison is about the level the phone's compressor sees
        runFirst = PvbRuntime.AbCondition("now", "EQ v1.1 기준 출력", 0f, 0f) { PvbAbConditions.v11(it) }
        runSecond = PvbRuntime.AbCondition("stage", "출력 −${"%.1f".format(Locale.US, x)} dB, 볼륨 +${plan.steps}단계", -x, 0f) {
            PvbAbConditions.v11(it)
        }
        runTrims = floatArrayOf(0f, -x)
        runVolume = mapOf("now" to base, "stage" to base + plan.steps)
        runPlan = plan
        return null
    }

    /** Sets the volume for a stage condition; false if the phone did not take it (do-not-disturb, fixed volume). */
    private fun setVolumeFor(cond: PvbRuntime.AbCondition?): Boolean {
        val idx = runVolume?.get(cond?.id ?: return true) ?: return true
        return setIndex(idx)
    }

    private fun setIndex(idx: Int): Boolean = try {
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, idx, 0)
        audio.getStreamVolume(AudioManager.STREAM_MUSIC) == idx
    } catch (ignored: Exception) {
        false
    }

    private fun start() {
        if (pendingRestore >= 0) {
            if (!setIndex(pendingRestore)) {
                resultText.text = "앞 비교의 볼륨(${pendingRestore}단계)을 되돌리지 못했습니다. 볼륨을 직접 맞춘 뒤 시작하세요."
                return
            }
            pendingRestore = -1
        }
        if (PvbRuntime.measuring) {
            resultText.text = "측정이 끝난 뒤에 시작하세요."
            return
        }
        if (PvbRuntime.engine == null) {
            resultText.text = "서비스가 꺼져 있습니다. 전원 버튼으로 켜고 음악을 재생한 뒤 시작하세요."
            return
        }
        if (!PvbRuntime.status.speaker) {
            resultText.text = "지금 출력이 내장 스피커가 아닙니다 (${PvbRuntime.status.routeName}). 내장 스피커로 재생할 때만 비교할 수 있습니다."
            return
        }
        prepareRun()?.let {
            resultText.text = it
            return
        }
        trials = ArrayList(List(TRIALS) { Trial(Random.nextBoolean()) })
        current = 0
        lastCond = null
        // still raised from the last headroom run: keep the level from before that run
        startVolume = if (PvbRuntime.abReturnVolume >= 0) PvbRuntime.abReturnVolume
        else audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        PvbRuntime.cancelReturnWait()
        prefs.edit().putInt(PvbRuntime.AB_KEY_START_VOLUME, startVolume).apply()   // in case the app is killed
        returnBox.visibility = GONE
        spinner.isEnabled = false
        startBtn.visibility = GONE
        trialBox.visibility = VISIBLE
        resultText.text = ""
        copyBtn.visibility = GONE
        PvbRuntime.setAb(true, null, muted = true)   // fade the user's own sound out before the first trial
        val rs = ++runSeq
        postDelayed({ monitorRun(rs) }, MONITOR_MS)
        beginTrial()
    }

    /**
     * Runs while a comparison runs. The output-headroom comparison must play each side at the volume the app set for
     * it: if the volume changes while a side is audible (the user pressed a volume key), the run stops.
     */
    private fun monitorRun(rs: Int) {
        if (rs != runSeq || current < 0) return
        val plan = runVolume
        val cond = lastCond
        if (plan != null && cond != null && playing != 0 && !PvbRuntime.abMuted) {
            val want = plan[cond.id]
            val now = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
            if (want != null && now != want) {
                stop(aborted = true)
                resultText.text = "볼륨이 바뀌어 비교를 중단했습니다(앱이 맞춘 ${want}단계, 지금 ${now}단계). " +
                    "이 비교 중에는 볼륨 버튼을 누르지 마세요.\n" + resultText.text
                return
            }
        }
        postDelayed({ monitorRun(rs) }, MONITOR_MS)
    }

    /**
     * Marks a side as heard only when the engine reports this exact state (tag) as audible for [HEARD_MS]: output
     * gate open, processed (not bypassed) and the music not silent. Pressing the button alone is not enough.
     */
    private fun watchHeard(t: Trial, aSide: Boolean, token: Int) {
        val tag = PvbRuntime.abTag
        val started = SystemClock.elapsedRealtime()
        var hinted = false
        fun poll() {
            if (token != seq || current < 0 || trials[current] !== t) return
            val ms = PvbRuntime.engine?.openMs(tag) ?: -1
            if (ms >= HEARD_MS) {
                heard(t, aSide)
                return
            }
            if (!hinted && SystemClock.elapsedRealtime() - started > SILENT_HINT_MS) {
                hinted = true
                nowPlaying.text = "지금 재생: ${if (aSide) "A" else "B"} · 소리가 들어오지 않습니다. 음악이 재생 중인지 확인하세요."
            }
            postDelayed({ poll() }, HEARD_POLL_MS)
        }
        poll()
    }

    /** Silence first, then the listener starts A or B himself, so a trial never starts by switching from the last one. */
    private fun beginTrial() {
        val t = trials[current]
        t.startedMs = SystemClock.elapsedRealtime()
        annoyA.isChecked = false
        annoyB.isChecked = false
        progress.text = "${current + 1} / $TRIALS 회차 · ${pair().label}"
        playing = 0
        inGap = true
        nowPlaying.text = "잠시 쉽니다…"
        setButtons()
        val token = ++seq
        postDelayed({
            if (token != seq || current < 0) return@postDelayed
            inGap = false
            nowPlaying.text = "A나 B를 눌러 들으세요"
            setButtons()
        }, GAP_MS)
    }

    private fun play(aSide: Boolean) {
        if (current < 0 || inGap) return
        val t = trials[current]
        val side = if (aSide) 1 else 2
        val cond = conditionFor(aSide)
        val wasPlaying = playing != 0 && !PvbRuntime.abMuted
        lastCond = cond
        playing = side
        if (runVolume != null) {
            // Stage comparison: the volume changes with the condition. Fade out, change volume and setting while
            // silent, fade in; the same short gap in both directions.
            if (wasPlaying) {
                t.switches++
                PvbRuntime.setAb(true, PvbRuntime.abCondition, muted = true)
            }
            val token = ++seq
            postDelayed({
                if (token != seq || current < 0) return@postDelayed
                if (!setVolumeFor(cond)) {
                    stop(aborted = true)
                    resultText.text = "폰이 볼륨 변경을 받지 않아 중단했습니다(방해 금지 모드나 볼륨 고정 확인). " + resultText.text
                    return@postDelayed
                }
                PvbRuntime.setAb(true, cond, muted = true)
                postDelayed({
                    if (token == seq && current >= 0) {
                        PvbRuntime.setAb(true, cond, muted = false)
                        watchHeard(t, aSide, token)
                    }
                }, SETTLE_MS)
            }, if (wasPlaying) FADE_WAIT_MS else 0L)
        } else if (PvbRuntime.abMuted) {
            // From silence: the engine takes the new setting at once while muted (no glide), then it fades in.
            // Also when the other side was pressed a moment ago and has not faded in yet.
            PvbRuntime.setAb(true, cond, muted = true)
            val token = ++seq
            postDelayed({
                if (token == seq && current >= 0) {
                    PvbRuntime.setAb(true, cond, muted = false)
                    watchHeard(t, aSide, token)
                }
            }, SETTLE_MS)
        } else {
            t.switches++
            val token = ++seq
            PvbRuntime.setAb(true, cond, muted = false)
            watchHeard(t, aSide, token)
        }
        showPlaying(t, aSide)
        setButtons()
    }

    private fun heard(t: Trial, aSide: Boolean) {
        if (aSide) t.heardA = true else t.heardB = true
        if (current >= 0 && trials[current] === t) {
            showPlaying(t, aSide)
            setButtons()
        }
    }

    private fun showPlaying(t: Trial, aSide: Boolean) {
        val both = t.heardA && t.heardB
        nowPlaying.text = "지금 재생: ${if (aSide) "A" else "B"}" + (if (both) "" else " · 다른 쪽도 들어 본 뒤 고를 수 있습니다") +
            (if (PvbRuntime.status.speaker) "" else "\n출력이 내장 스피커가 아닙니다. 이 비교는 의미가 없으니 중단하세요.")
    }

    private fun setButtons() {
        val t = if (current in 0 until TRIALS) trials[current] else null
        val open = t != null && !inGap
        aBtn.isEnabled = open && playing != 1
        bBtn.isEnabled = open && playing != 2
        val both = t != null && !inGap && t.heardA && t.heardB
        preferA.isEnabled = both
        preferB.isEnabled = both
        same.isEnabled = both
    }

    private fun answer(choice: String) {
        if (current < 0 || inGap) return
        val t = trials[current]
        if (!(t.heardA && t.heardB)) return
        t.choice = choice
        t.annoyA = annoyA.isChecked
        t.annoyB = annoyB.isChecked
        t.seconds = (SystemClock.elapsedRealtime() - t.startedMs) / 1000.0
        current++
        PvbRuntime.setAb(true, lastCond, muted = true)   // fade out what was playing; nothing switches audibly
        if (current >= TRIALS) stop(aborted = false) else beginTrial()
    }

    private fun stop(aborted: Boolean, immediate: Boolean = false) {
        val done = trials.take(if (aborted) current.coerceAtLeast(0) else TRIALS).filter { it.choice.isNotEmpty() }
        current = -1
        playing = 0
        inGap = false
        ++runSeq
        val token = ++seq
        if (runVolume != null) {
            // stage comparison: the app changed the volume, so it puts it back - and checks that the phone took it
            // before the output goes back to normal
            val back = startVolume
            if (immediate) {
                if (setIndex(back)) PvbRuntime.setAb(false, null) else PvbRuntime.waitForVolumeReturn(back)
            } else {
                PvbRuntime.setAb(true, lastCond, muted = true)
                pendingRestore = back
                postDelayed({
                    if (token != seq) return@postDelayed
                    pendingRestore = -1
                    if (setIndex(back)) {
                        postDelayed({ if (token == seq) PvbRuntime.setAb(false, null) }, SETTLE_MS)
                    } else {
                        // keep the output 10 dB down until the user brings the volume back himself
                        PvbRuntime.waitForVolumeReturn(back)
                        showReturn()
                        resultText.text = "볼륨을 ${back}단계로 되돌리지 못했습니다. 직접 내려 주세요. 그때까지 출력을 " +
                            "${PvbAbConditions.HEADROOM_DB.toInt()} dB 낮춰 둡니다.\n" + resultText.text
                    }
                }, FADE_WAIT_MS)
            }
        } else if (audio.getStreamVolume(AudioManager.STREAM_MUSIC) <= startVolume) {
            // volume not raised (or already back down): straight back to the user's own settings
            if (immediate) {
                PvbRuntime.setAb(false, null)
            } else {
                PvbRuntime.setAb(true, lastCond, muted = true)
                postDelayed({ if (token == seq) PvbRuntime.setAb(false, null) }, END_PAUSE_MS)
            }
        } else {
            // the volume was turned up for this run: own settings 10 dB quieter until it is back down
            PvbRuntime.waitForVolumeReturn(startVolume)
            if (!immediate) showReturn()
        }
        trialBox.visibility = GONE
        startBtn.visibility = VISIBLE
        spinner.isEnabled = true
        if (done.isEmpty()) {
            resultText.text = if (aborted) "중단했습니다. 기록할 회차가 없습니다." else ""
            return
        }
        report(done, aborted)
    }

    private fun showReturn() {
        returnBox.visibility = VISIBLE
        pollReturn(++seq)
    }

    /** Only updates the text; the controller brings the sound back when the volume goes down. */
    private fun pollReturn(token: Int) {
        if (token != seq) return
        val back = PvbRuntime.abReturnVolume
        if (back < 0) {
            returnBox.visibility = GONE
            return
        }
        val max = PvbRuntime.status.volumeMax
        returnHint.text = "비교가 끝났습니다. 지금은 원래 설정을 ${PvbAbConditions.HEADROOM_DB.toInt()} dB 낮춰 내보내고 있어서, " +
            "올린 볼륨에서도 비교할 때와 같은 크기입니다. 볼륨을 시작할 때인 ${PvbRuntime.volumeLabel(back, max)}로 내리면 " +
            "원래 출력으로 돌아갑니다. 지금 ${PvbRuntime.volumeLabel(PvbRuntime.status.volumeIndex, max)}."
        postDelayed({ pollReturn(token) }, RETURN_POLL_MS)
    }

    private fun finishReturn() {
        ++seq
        returnBox.visibility = GONE
        if (PvbRuntime.abReturnVolume >= 0) PvbRuntime.endAb()
    }

    private fun report(done: List<Trial>, aborted: Boolean) {
        val p = pair()
        val f = runFirst ?: return
        val g = runSecond ?: return
        var first = 0
        var second = 0
        var ties = 0
        var annoyFirst = 0
        var annoySecond = 0
        val lines = ArrayList<String>()
        val arr = JSONArray()
        done.forEachIndexed { i, t ->
            val aLabel = if (t.aIsFirst) f.label else g.label
            val bLabel = if (t.aIsFirst) g.label else f.label
            val winner = when (t.choice) {
                "A" -> aLabel
                "B" -> bLabel
                else -> "구분 안 됨"
            }
            when (winner) {
                f.label -> first++
                g.label -> second++
                else -> ties++
            }
            if (t.annoyA) { if (t.aIsFirst) annoyFirst++ else annoySecond++ }
            if (t.annoyB) { if (t.aIsFirst) annoySecond++ else annoyFirst++ }
            lines += "${i + 1}. A=$aLabel, B=$bLabel → $winner" +
                (if (t.annoyA || t.annoyB) " (거슬림: ${listOfNotNull(if (t.annoyA) "A" else null, if (t.annoyB) "B" else null).joinToString()})" else "")
            arr.put(JSONObject().apply {
                put("a", if (t.aIsFirst) f.id else g.id)
                put("b", if (t.aIsFirst) g.id else f.id)
                put("choice", t.choice)
                put("annoy_a", t.annoyA)
                put("annoy_b", t.annoyB)
                put("switches", t.switches)
                put("seconds", t.seconds)
            })
        }
        val n = first + second
        val pval = signTestP(first, n)
        val summary = "${f.label} $first : ${g.label} $second (구분 안 됨 $ties), p=${String.format(Locale.US, "%.2f", pval)}; " +
            "거슬림 ${f.label} $annoyFirst, ${g.label} $annoySecond"
        val header = (if (aborted) "중단됨 · " else "") + "결과 (${done.size}회)\n" + summary +
            "\np는 우연히 이만큼 한쪽으로 쏠릴 확률입니다. 0.05보다 작으면 차이가 있다고 볼 만합니다."
        resultText.text = header + "\n\n" + lines.joinToString("\n")

        val run = JSONObject().apply {
            put("time", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date()))
            put("pair", p.id)
            put("first", f.id)
            put("second", g.id)
            put("headroom_db", if (p.stage) 0.0 else PvbAbConditions.HEADROOM_DB.toDouble())
            put("trims_db", JSONObject().apply {
                put(f.id, runTrims[0].toDouble())
                put(g.id, runTrims[1].toDouble())
            })
            put("volume_index_start", startVolume)
            put("volume_index_end", audio.getStreamVolume(AudioManager.STREAM_MUSIC))
            runPlan?.let {
                put("stage", JSONObject().apply {
                    put("volume_steps", it.steps)
                    put("volume_gain_db", it.volumeGainDb)
                    put("out_drop_db", it.outDropDb)
                    put("phone_loss_db", it.phoneLossDb)
                })
            }
            put("aborted", aborted)
            put("summary", summary)
            put("trials", arr)
        }
        val all = try {
            JSONArray(prefs.getString(KEY_RESULTS, "[]"))
        } catch (ignored: Exception) {
            JSONArray()
        }
        all.put(run)
        while (all.length() > 30) all.remove(0)
        prefs.edit().putString(KEY_RESULTS, all.toString()).apply()
        lastJson = all.toString(1)
        copyBtn.visibility = VISIBLE
    }

    private fun copyResults() {
        val cm = context.getSystemService(ClipboardManager::class.java) ?: return
        cm.setPrimaryClip(ClipData.newPlainText("PVB 블라인드 비교", lastJson))
        copyBtn.text = "복사했습니다"
        postDelayed({ copyBtn.text = "결과 복사 (JSON)" }, 1500)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        PvbRuntime.addRouteListener(routeListener)
    }

    override fun onDetachedFromWindow() {
        PvbRuntime.removeRouteListener(routeListener)
        // never leave a condition applied when the screen goes away; after a run the own settings stay 10 dB
        // quieter until the volume is back down (the controller watches it), so leaving cannot make it suddenly loud
        if (pendingRestore >= 0) {
            val back = pendingRestore
            pendingRestore = -1
            if (setIndex(back)) {
                if (PvbRuntime.abActive && PvbRuntime.abReturnVolume < 0) PvbRuntime.setAb(false, null)
            } else {
                PvbRuntime.waitForVolumeReturn(back)
            }
        }
        if (current >= 0) stop(aborted = true, immediate = true)
        else if (PvbRuntime.abActive && PvbRuntime.abReturnVolume < 0) PvbRuntime.setAb(false, null)
        ++seq
        super.onDetachedFromWindow()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    companion object {
        private const val TRIALS = 8
        private const val GAP_MS = 1500L        // silence between trials (also before the first)
        private const val SETTLE_MS = 250L      // new setting lands while muted (> one audio block), then fade-in
        private const val END_PAUSE_MS = 400L
        // Fade-out (150 ms) must have reached the speaker before the volume changes: parameters are taken at the
        // start of a processing block and the output track holds about one more block (85 ms at the default
        // 8192-sample buffer, 170 ms at 16384): 150 + 2 x 170 + margin.
        private const val FADE_WAIT_MS = 700L
        private const val RETURN_POLL_MS = 500L
        private const val MONITOR_MS = 300L
        /** A side counts as heard after this much audible audio with exactly that setting (engine-reported). */
        private const val HEARD_MS = 400
        private const val HEARD_POLL_MS = 100L
        private const val SILENT_HINT_MS = 2500L
        private const val KEY_RESULTS = "results"
        private const val KEY_VB_WARNING_OK = "vb_warning_ok"

        /** Two-sided sign test: probability of a split at least this uneven with no real difference. */
        fun signTestP(k: Int, n: Int): Double {
            if (n == 0) return 1.0
            val m = minOf(k, n - k)
            var tail = 0.0
            var c = 1.0  // C(n, 0)
            for (i in 0..m) {
                if (i > 0) c = c * (n - i + 1) / i
                tail += c
            }
            return minOf(1.0, 2.0 * tail / Math.pow(2.0, n.toDouble()))
        }
    }
}

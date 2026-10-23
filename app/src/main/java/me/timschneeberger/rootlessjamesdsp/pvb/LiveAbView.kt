package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Typeface
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.BatteryManager
import android.os.SystemClock
import android.text.InputType
import android.util.TypedValue
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipDrawable
import com.google.android.material.chip.ChipGroup
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.activity.LiveAbResultsActivity
import me.timschneeberger.rootlessjamesdsp.service.NotificationListenerService
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.random.Random

/**
 * Alpha 3.3 "실청 블라인드 비교": the user's own music through the real engine, switched blindly between the conditions
 * of one predefined comparison ([LiveAbComparisons]). Each trial shuffles the letters (seeded, [LiveAbShuffle]); the
 * mapping is revealed only after the verdict is saved. Uses the same engine path as the existing comparison card
 * ([PvbRuntime.setAb]: condition, loudness trim, common headroom, mute between trials) and the same return-to-normal
 * rule afterwards. Leaving the screen ends the comparison; a trial that was not saved is not recorded.
 */
class LiveAbView(context: Context) : LinearLayout(context) {
    private val comparisons = LiveAbComparisons.ALL
    private val prefs = context.getSharedPreferences(PvbRuntime.AB_PREFS, Context.MODE_PRIVATE)
    private val audio = context.getSystemService(AudioManager::class.java)
    private val store = openStore(context)

    private val spinner = Spinner(context)
    private val description = TextView(context)
    private val startBtn = Button(context)
    private val resultsBtn = Button(context)
    private val message = TextView(context)

    private val sessionBox = LinearLayout(context)
    private val progress = TextView(context)
    private val nowPlaying = TextView(context)
    private val sideButtons = List(3) { Button(context) }
    private val verdictGroup = ChipGroup(context)
    private val verdictChips = ArrayList<Chip>()
    private val symptomGroup = ChipGroup(context)
    private val symptomChips = ArrayList<Chip>()
    private val note = EditText(context)
    private val saveBtn = Button(context)
    private val reveal = TextView(context)
    private val nextBtn = Button(context)
    private val endBtn = Button(context)

    private val returnBox = LinearLayout(context)
    private val returnHint = TextView(context)
    private val returnBtn = Button(context)

    // ---- session state
    private var cmpIndex = 0
    private var running = false
    private var cmp: LiveAbComparisons.Comparison = comparisons[0]
    private var base = PvbSettings()
    private var conds: List<PvbRuntime.AbCondition> = emptyList()
    private var seed = 0L
    private var trialNo = 0
    private var mapping = IntArray(0)       // letter index -> condition index
    private var heard = BooleanArray(0)
    private var playing = -1                // letter index, -1 = silent
    private var inGap = false
    private var revealed = false
    private var verdict: String? = null
    private var switches = 0
    private var trialStartMs = 0L
    private var lastCond: PvbRuntime.AbCondition? = null
    private var startVolume = 0
    private var savedThisRun = 0
    private var seq = 0                     // invalidates delayed steps of an earlier trial or run

    private val routeListener: () -> Unit = {
        if (running) end("출력 장치가 바뀌어 비교를 끝냈습니다. 저장하지 않은 회차는 기록하지 않습니다.")
    }

    /** Someone else ended the comparison (the existing card's screen going away, for example): stop cleanly. */
    private val abListener: () -> Unit = {
        post { if (running && !PvbRuntime.abActive) end("다른 화면에서 비교가 끝나 이 비교도 끝냈습니다. 저장하지 않은 회차는 기록하지 않습니다.", engineAlreadyFree = true) }
    }

    init {
        orientation = VERTICAL
        val pad = dp(16)
        setPadding(pad, dp(12), pad, dp(24))

        addView(text("내 음악을 실제 엔진으로 들으면서 두(또는 세) 설정을 A·B(·C)로 바꿔 듣고, 회차마다 판정을 저장합니다. " +
            "회차마다 글자가 새로 섞이고, 어느 쪽이 무엇이었는지는 저장한 뒤에 공개됩니다. 음악을 먼저 내장 스피커로 재생해 두세요. " +
            "곡 제목을 기록하려면 알림 접근 권한이 필요합니다(곡별 세기 기억과 같은 권한). 화면을 나가면 비교가 끝납니다.", 13f))

        spinner.adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, comparisons.map { it.label })
        cmpIndex = comparisons.indexOfFirst { it.id == prefs.getString(KEY_LAST, null) }.coerceAtLeast(0)
        spinner.setSelection(cmpIndex)
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                cmpIndex = position
                prefs.edit().putString(KEY_LAST, comparisons[position].id).apply()
                updateDescription()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        addView(spinner, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        description.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        description.setLineSpacing(0f, 1.15f)
        description.setPadding(0, dp(6), 0, dp(6))
        addView(description)

        startBtn.text = "비교 시작"
        startBtn.setOnClickListener { confirmVb { start() } }
        addView(startBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        resultsBtn.setOnClickListener { context.startActivity(Intent(context, LiveAbResultsActivity::class.java)) }
        addView(resultsBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // ---- session
        sessionBox.orientation = VERTICAL
        sessionBox.visibility = GONE
        progress.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        progress.setTypeface(progress.typeface, Typeface.BOLD)
        progress.setPadding(0, dp(8), 0, 0)
        sessionBox.addView(progress)
        nowPlaying.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
        nowPlaying.setPadding(0, dp(2), 0, dp(6))
        sessionBox.addView(nowPlaying)
        val sides = LinearLayout(context).apply { orientation = HORIZONTAL }
        sideButtons.forEachIndexed { i, b ->
            b.text = LiveAbShuffle.LETTERS[i]
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f)
            b.minHeight = dp(96)
            b.setOnClickListener { play(i) }
            sides.addView(b, LayoutParams(0, dp(104), 1f).apply { setMargins(dp(3), 0, dp(3), 0) })
        }
        sessionBox.addView(sides, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        sessionBox.addView(label("판정"))
        verdictGroup.isSingleSelection = true
        for ((value, title) in listOf("A" to "A 나음", "B" to "B 나음", "C" to "C 나음", LiveAbRecord.SAME to "차이 모름")) {
            val c = chip(title)
            c.tag = value
            c.setOnCheckedChangeListener { _, _ -> onVerdictChanged() }
            verdictChips += c
            verdictGroup.addView(c)
        }
        sessionBox.addView(verdictGroup)
        sessionBox.addView(label("들린 증상 (선택, 여러 개)"))
        for (s in LiveAbRecord.CHIPS) {
            val c = chip(s)
            c.tag = s
            symptomChips += c
            symptomGroup.addView(c)
        }
        sessionBox.addView(symptomGroup)
        note.hint = "메모 (선택)"
        note.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        note.maxLines = 4
        sessionBox.addView(note, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        saveBtn.text = "판정 저장하고 공개"
        saveBtn.setOnClickListener { save() }
        sessionBox.addView(saveBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        reveal.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
        reveal.setTypeface(reveal.typeface, Typeface.BOLD)
        reveal.setLineSpacing(0f, 1.15f)
        reveal.setPadding(0, dp(6), 0, dp(6))
        reveal.visibility = GONE
        sessionBox.addView(reveal)
        nextBtn.text = "다음 회차"
        nextBtn.visibility = GONE
        nextBtn.setOnClickListener { if (running && revealed) beginTrial() }
        sessionBox.addView(nextBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        endBtn.text = "비교 끝내기"
        endBtn.setOnClickListener { if (running) end(null) }
        sessionBox.addView(endBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(sessionBox, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        // ---- after a run with headroom: own settings 10 dB quieter until the volume is back down
        returnBox.orientation = VERTICAL
        returnBox.visibility = GONE
        returnHint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        returnHint.setPadding(0, dp(8), 0, 0)
        returnBox.addView(returnHint)
        returnBtn.text = "볼륨 그대로 원래 출력으로 (10 dB 커집니다)"
        returnBtn.setOnClickListener {
            ++seq
            returnBox.visibility = GONE
            if (PvbRuntime.abReturnVolume >= 0) PvbRuntime.endAb()
        }
        returnBox.addView(returnBtn, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(returnBox, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        message.setLineSpacing(0f, 1.15f)
        message.setPadding(0, dp(8), 0, 0)
        addView(message)

        updateDescription()
        refreshResultsButton()
        if (PvbRuntime.abReturnVolume >= 0) showReturn()
    }

    // ------------------------------------------------------------------------------------------ views

    private fun text(s: String, sp: Float) = TextView(context).apply {
        text = s
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
        setLineSpacing(0f, 1.15f)
        setPadding(0, 0, 0, dp(8))
    }

    private fun label(s: String) = TextView(context).apply {
        text = s
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(10), 0, 0)
    }

    private fun chip(title: String) = Chip(context).apply {
        setChipDrawable(ChipDrawable.createFromAttributes(context, null, 0,
            com.google.android.material.R.style.Widget_Material3_Chip_Filter))
        id = View.generateViewId()
        text = title
        isCheckable = true
        isCheckedIconVisible = true
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun refreshResultsButton() {
        resultsBtn.text = "저장된 판정 보기 · 내보내기 (${store.load().size}건)"
    }

    private fun updateDescription() {
        val c = comparisons[cmpIndex]
        val user = PvbSettings.load(context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE))
        val volume = if (c.headroomDb > 0f) "\n비교하는 동안 모든 쪽을 ${c.headroomDb.toInt()} dB 작게 내보냅니다(기존 블라인드 비교와 같음). " +
            "처음 들을 때 평소 크기가 될 때까지 볼륨을 올리세요. 끝난 뒤에는 볼륨을 시작할 때로 내리면 원래 출력으로 돌아갑니다."
        else "\n이 비교는 출력을 낮추지 않습니다. 볼륨은 평소대로 두세요."
        description.text = c.description + "\n조건: " + c.sides.joinToString(" / ") { it.label(user) } + volume
    }

    /** The virtual bass warning, once (same flag as the existing comparison card). */
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

    // ------------------------------------------------------------------------------------------ run

    private fun start() {
        if (running) return
        val c = comparisons[cmpIndex]
        val why = when {
            PvbRuntime.measuring -> "측정이 끝난 뒤에 시작하세요."
            PvbRuntime.engine == null -> "서비스가 꺼져 있습니다. 앱의 전원 버튼으로 켜고 음악을 재생한 뒤 시작하세요."
            !PvbRuntime.status.speaker -> "지금 출력이 내장 스피커가 아닙니다 (${PvbRuntime.status.routeName}). 내장 스피커로 재생할 때만 비교할 수 있습니다."
            PvbRuntime.abActive && PvbRuntime.abReturnVolume < 0 -> "다른 블라인드 비교가 진행 중입니다. 그 비교를 끝낸 뒤 시작하세요."
            c.headroomDb <= 0f && PvbRuntime.abReturnVolume >= 0 ->
                "앞 비교 뒤라 볼륨이 올라가 있습니다. 볼륨을 ${PvbRuntime.abReturnVolume}단계로 내린 뒤 시작하세요(이 비교는 평소 볼륨으로 듣습니다)."
            else -> null
        }
        if (why != null) {
            message.text = why
            return
        }
        cmp = c
        base = PvbSettings.load(context.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE))
        conds = cmp.sides.map { cmp.condition(it, base) }
        seed = Random.nextLong()
        trialNo = 0
        savedThisRun = 0
        lastCond = null
        // still raised from an earlier headroom run: keep the level from before that run
        startVolume = if (PvbRuntime.abReturnVolume >= 0) PvbRuntime.abReturnVolume else audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        PvbRuntime.cancelReturnWait()
        if (cmp.headroomDb > 0f) prefs.edit().putInt(PvbRuntime.AB_KEY_START_VOLUME, startVolume).apply()   // app killed
        else prefs.edit().remove(PvbRuntime.AB_KEY_START_VOLUME).apply()
        running = true
        returnBox.visibility = GONE
        spinner.isEnabled = false
        startBtn.visibility = GONE
        sessionBox.visibility = VISIBLE
        message.text = ""
        for (i in sideButtons.indices) sideButtons[i].visibility = if (i < conds.size) VISIBLE else GONE
        verdictChips.forEach { it.visibility = if (it.tag == "C" && conds.size < 3) GONE else VISIBLE }
        PvbRuntime.setAb(true, null, muted = true)   // fade the user's own sound out before the first trial
        beginTrial()
    }

    /** Silence first; the listener then starts a side himself, so a trial never begins by switching from the last one. */
    private fun beginTrial() {
        trialNo++
        mapping = LiveAbShuffle.permutation(seed, trialNo, conds.size)
        heard = BooleanArray(conds.size)
        playing = -1
        switches = 0
        revealed = false
        verdict = null
        verdictGroup.clearCheck()
        symptomChips.forEach { it.isChecked = false }
        note.setText("")
        reveal.visibility = GONE
        nextBtn.visibility = GONE
        if (!PvbRuntime.abMuted) PvbRuntime.setAb(true, lastCond, muted = true)
        trialStartMs = SystemClock.elapsedRealtime()
        progress.text = "$trialNo 회차 · ${cmp.label}" + (if (savedThisRun > 0) " · 이번에 저장 $savedThisRun" else "")
        inGap = true
        nowPlaying.text = "잠시 쉽니다…"
        setControls()
        val token = ++seq
        postDelayed({
            if (token != seq || !running) return@postDelayed
            inGap = false
            nowPlaying.text = "${letters()} 중 하나를 눌러 들으세요"
            setControls()
        }, GAP_MS)
    }

    private fun letters() = LiveAbShuffle.LETTERS.take(conds.size).joinToString("·")

    private fun play(letter: Int) {
        if (!running || inGap || revealed || letter >= conds.size) return
        val cond = conds[mapping[letter]]
        lastCond = cond
        playing = letter
        val token = ++seq
        if (PvbRuntime.abMuted) {
            // From silence: the engine takes the new setting at once while muted (no glide), then it fades in.
            PvbRuntime.setAb(true, cond, muted = true)
            postDelayed({
                if (token == seq && running) {
                    PvbRuntime.setAb(true, cond, muted = false)
                    watchHeard(letter, token)
                }
            }, SETTLE_MS)
        } else {
            switches++
            PvbRuntime.setAb(true, cond, muted = false)
            watchHeard(letter, token)
        }
        showPlaying()
        setControls()
    }

    /** A side counts as heard only when the engine reports this exact state as audible for [HEARD_MS]. */
    private fun watchHeard(letter: Int, token: Int) {
        val tag = PvbRuntime.abTag
        val started = SystemClock.elapsedRealtime()
        var hinted = false
        fun poll() {
            if (token != seq || !running) return
            val ms = PvbRuntime.engine?.openMs(tag) ?: -1
            if (ms >= HEARD_MS) {
                heard[letter] = true
                showPlaying()
                setControls()
                return
            }
            if (!hinted && SystemClock.elapsedRealtime() - started > SILENT_HINT_MS) {
                hinted = true
                nowPlaying.text = "지금 재생: ${LiveAbShuffle.LETTERS[letter]} · 소리가 들어오지 않습니다. 음악이 재생 중인지 확인하세요."
            }
            postDelayed({ poll() }, HEARD_POLL_MS)
        }
        poll()
    }

    private fun showPlaying() {
        if (playing < 0) return
        val missing = LiveAbShuffle.LETTERS.take(conds.size).filterIndexed { i, _ -> !heard[i] }
        nowPlaying.text = "지금 재생: ${LiveAbShuffle.LETTERS[playing]}" +
            (if (missing.isEmpty()) "" else " · 아직 안 들은 쪽: ${missing.joinToString("·")}") +
            (if (PvbRuntime.status.speaker) "" else "\n출력이 내장 스피커가 아닙니다. 이 비교는 의미가 없으니 끝내세요.")
    }

    private fun onVerdictChanged() {
        verdict = verdictChips.firstOrNull { it.isChecked }?.tag as? String
        setControls()
    }

    private fun setControls() {
        val open = running && !inGap && !revealed
        sideButtons.forEachIndexed { i, b ->
            b.isEnabled = open
            b.text = if (i == playing && open) "▶ ${LiveAbShuffle.LETTERS[i]}" else LiveAbShuffle.LETTERS[i]
            b.setTypeface(null, if (i == playing && open) Typeface.BOLD else Typeface.NORMAL)
        }
        verdictChips.forEach { it.isEnabled = open }
        symptomChips.forEach { it.isEnabled = open }
        note.isEnabled = open
        val allHeard = heard.isNotEmpty() && heard.all { it }
        saveBtn.isEnabled = open && allHeard && verdict != null
        saveBtn.text = when {
            !open -> "판정 저장하고 공개"
            !allHeard -> "모든 쪽을 들은 뒤 저장할 수 있습니다"
            verdict == null -> "판정을 고르세요"
            else -> "판정 저장하고 공개"
        }
    }

    private fun save() {
        if (!running || revealed || inGap) return
        val v = verdict ?: return
        if (!heard.all { it } || !LiveAbRecord.verdictValid(v, conds.size)) return
        val r = buildRecord(v)
        if (!store.add(r)) {
            message.text = "판정을 저장하지 못했습니다(저장 공간 확인). 다시 눌러 보세요."
            return
        }
        savedThisRun++
        revealed = true
        ++seq
        PvbRuntime.setAb(true, lastCond, muted = true)   // fade out: the next trial starts from silence
        playing = -1
        val w = r.winner()
        reveal.text = "공개 · " + r.sides.joinToString(", ") { "${it.letter} = ${it.label}" } + "\n" +
            (if (w == null) "판정: 차이 모름" else "고른 쪽: ${w.letter} = ${w.label}") +
            (if (r.chips.isEmpty()) "" else "\n증상: ${r.chips.joinToString(", ")}")
        reveal.visibility = VISIBLE
        nextBtn.visibility = VISIBLE
        nowPlaying.text = "저장했습니다. 다음 회차를 누르면 글자를 새로 섞습니다."
        progress.text = "$trialNo 회차 · ${cmp.label} · 이번에 저장 $savedThisRun"
        setControls()
        refreshResultsButton()
    }

    private fun buildRecord(v: String): LiveAbRecord {
        val now = System.currentTimeMillis()
        val index = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val sides = (0 until conds.size).map { letter ->
            val ci = mapping[letter]
            val side = cmp.sides[ci]
            val s = side.apply(base)
            LiveAbSide(
                letter = LiveAbShuffle.LETTERS[letter],
                id = side.id,
                label = conds[ci].label,
                algo = s.vbAlgo,
                levelDb = s.vbLevelDb,
                effectiveLevelDb = VolumeLevelLink.levelFor(s, index, max),
                volLink = s.vbVolLink,
                trimDb = side.trimDb,
                trimMeasured = side.trimMeasured,
            )
        }
        val t = currentTrack()
        return LiveAbRecord(
            id = "$now-${java.lang.Long.toHexString(seed).takeLast(6)}-$trialNo",
            timeMs = now,
            timeLocal = SimpleDateFormat("yyyy-MM-dd HH:mm:ssXXX", Locale.US).format(Date(now)),
            comparisonId = cmp.id,
            comparisonLabel = cmp.label,
            seed = seed,
            trial = trialNo,
            sides = sides,
            verdict = v,
            chips = symptomChips.filter { it.isChecked }.map { it.tag as String },
            note = note.text?.toString()?.trim() ?: "",
            track = t?.let { LiveAbTrack(it.packageName, it.title, it.artist, it.album) },
            volumeIndex = index,
            volumeMax = max,
            volumePct = VolumeLevelLink.volumePct(index, max),
            vbSliderDb = base.vbLevelDb,
            vbUserEffectiveDb = VolumeLevelLink.levelFor(base, index, max),
            vbUserVolLink = base.vbVolLink,
            headroomDb = cmp.headroomDb,
            switches = switches,
            listenSeconds = (SystemClock.elapsedRealtime() - trialStartMs) / 1000.0,
            batteryPct = battery(),
            // with the source commit, so a record can be traced to the exact engine it played (review question 74)
            appVersion = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) @${BuildConfig.COMMIT_SHA}",
            route = PvbRuntime.status.routeName,
        )
    }

    private fun battery(): Int = try {
        val v = context.getSystemService(BatteryManager::class.java)?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        if (v != null && v in 0..100) v else -1
    } catch (_: Exception) { -1 }

    /** The playing song as alpha 3.1 sees it ([TrackKeys.select]); needs notification access, otherwise null. */
    private fun currentTrack(): TrackInfo? = try {
        val msm = context.getSystemService(MediaSessionManager::class.java)
        val controllers = msm?.getActiveSessions(ComponentName(context, NotificationListenerService::class.java)) ?: emptyList()
        val players = controllers.map { snapshot(it) }
        TrackKeys.select(players, null) ?: players.firstOrNull { TrackKeys.of(it.track) != null }?.track
    } catch (_: Exception) {
        null   // no notification access (SecurityException) or a dead session
    }

    private fun snapshot(c: MediaController): PlayerSnapshot = try {
        val state = c.playbackState?.state ?: PlaybackState.STATE_NONE
        val md = c.metadata
        fun text(key: String): String? = md?.getText(key)?.toString()?.takeIf { it.isNotBlank() }
        PlayerSnapshot(
            track = if (md != null) TrackInfo(c.packageName,
                text(MediaMetadata.METADATA_KEY_ARTIST) ?: text(MediaMetadata.METADATA_KEY_ALBUM_ARTIST),
                text(MediaMetadata.METADATA_KEY_TITLE) ?: text(MediaMetadata.METADATA_KEY_DISPLAY_TITLE),
                text(MediaMetadata.METADATA_KEY_ALBUM)) else null,
            playing = state == PlaybackState.STATE_PLAYING || state == PlaybackState.STATE_BUFFERING,
            paused = state == PlaybackState.STATE_PAUSED,
        )
    } catch (_: Exception) {
        PlayerSnapshot(null, playing = false, paused = false)
    }

    /**
     * Ends the run. Same rule as the existing card: with the common headroom and the volume turned up, the user's own
     * settings stay that much quieter until the volume is back down (the controller watches it); otherwise a short
     * fade back to the user's own settings. [immediate]: the screen is going away, no delayed steps.
     */
    private fun end(reason: String?, immediate: Boolean = false, engineAlreadyFree: Boolean = false) {
        if (!running) return
        running = false
        playing = -1
        inGap = false
        val token = ++seq
        if (!engineAlreadyFree) {
            val raised = audio.getStreamVolume(AudioManager.STREAM_MUSIC) > startVolume
            if (cmp.headroomDb > 0f && raised) {
                PvbRuntime.waitForVolumeReturn(startVolume)
                if (!immediate) showReturn()
            } else if (immediate) {
                PvbRuntime.setAb(false, null)
            } else {
                PvbRuntime.setAb(true, lastCond, muted = true)
                postDelayed({ if (token == seq && !running) PvbRuntime.setAb(false, null) }, END_PAUSE_MS)
            }
        }
        if (immediate) return
        sessionBox.visibility = GONE
        startBtn.visibility = VISIBLE
        spinner.isEnabled = true
        message.text = (reason?.let { "$it\n" } ?: "") + "비교를 끝냈습니다. 이번에 저장한 회차: $savedThisRun"
        refreshResultsButton()
    }

    private fun showReturn() {
        returnBox.visibility = VISIBLE
        pollReturn(++seq)
    }

    private fun pollReturn(token: Int) {
        if (token != seq) return
        val back = PvbRuntime.abReturnVolume
        if (back < 0) {
            returnBox.visibility = GONE
            return
        }
        val max = PvbRuntime.status.volumeMax
        returnHint.text = "지금은 원래 설정을 ${PvbAbConditions.HEADROOM_DB.toInt()} dB 낮춰 내보내고 있습니다. 볼륨을 시작할 때인 " +
            "${PvbRuntime.volumeLabel(back, max)}로 내리면 원래 출력으로 돌아갑니다. 지금 ${PvbRuntime.volumeLabel(PvbRuntime.status.volumeIndex, max)}."
        postDelayed({ pollReturn(token) }, RETURN_POLL_MS)
    }

    fun onScreenResumed() {
        if (!running) {
            refreshResultsButton()
            updateDescription()
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        PvbRuntime.addRouteListener(routeListener)
        PvbRuntime.addAbListener(abListener)
    }

    override fun onDetachedFromWindow() {
        PvbRuntime.removeRouteListener(routeListener)
        PvbRuntime.removeAbListener(abListener)
        // never leave a condition applied when the screen goes away
        if (running) end(null, immediate = true)
        ++seq
        super.onDetachedFromWindow()
    }

    companion object {
        private const val KEY_LAST = "live_last_comparison"
        private const val KEY_VB_WARNING_OK = "vb_warning_ok"   // shared with PvbAbCard
        private const val GAP_MS = 1500L
        private const val SETTLE_MS = 250L
        private const val END_PAUSE_MS = 400L
        private const val RETURN_POLL_MS = 500L
        private const val HEARD_MS = 400
        private const val HEARD_POLL_MS = 100L
        private const val SILENT_HINT_MS = 2500L

        fun openStore(context: Context) = LiveAbStore(File(context.applicationContext.filesDir, "live_ab/trials.json"))
    }
}

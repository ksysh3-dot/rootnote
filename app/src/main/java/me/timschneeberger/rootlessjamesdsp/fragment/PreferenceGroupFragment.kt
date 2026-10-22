package me.timschneeberger.rootlessjamesdsp.fragment

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.media.AudioManager
import android.os.Bundle
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.RelativeSizeSpan
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.annotation.XmlRes
import androidx.appcompat.app.AlertDialog
import androidx.preference.Preference
import androidx.preference.ListPreference
import androidx.preference.Preference.SummaryProvider
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.PreferenceScreen
import androidx.preference.SwitchPreferenceCompat
import androidx.recyclerview.widget.RecyclerView
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.GraphicEqualizerActivity
import me.timschneeberger.rootlessjamesdsp.activity.LiveprogEditorActivity
import me.timschneeberger.rootlessjamesdsp.activity.ParametricEqualizerActivity
import me.timschneeberger.rootlessjamesdsp.activity.TrackLevelsActivity
import me.timschneeberger.rootlessjamesdsp.activity.LiveAbActivity
import me.timschneeberger.rootlessjamesdsp.activity.LiveprogParamsActivity
import me.timschneeberger.rootlessjamesdsp.adapter.RoundedRipplePreferenceGroupAdapter
import me.timschneeberger.rootlessjamesdsp.liveprog.EelParser
import me.timschneeberger.rootlessjamesdsp.preference.CompanderPreference
import me.timschneeberger.rootlessjamesdsp.preference.EqualizerPreference
import me.timschneeberger.rootlessjamesdsp.preference.FileLibraryPreference
import me.timschneeberger.rootlessjamesdsp.preference.MaterialSeekbarPreference
import me.timschneeberger.rootlessjamesdsp.preference.SwitchPreferenceGroup
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevels
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink
import me.timschneeberger.rootlessjamesdsp.utils.AudioSampleRateDetector
import me.timschneeberger.rootlessjamesdsp.utils.ConvolverSampleRateFiles
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.registerLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.sendLocalBroadcast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.unregisterLocalReceiver
import me.timschneeberger.rootlessjamesdsp.utils.preferences.Preferences
import org.koin.core.component.KoinComponent
import org.koin.core.component.inject
import timber.log.Timber
import java.io.File
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt


class PreferenceGroupFragment : PreferenceFragmentCompat(), KoinComponent {
    private val prefsApp: Preferences.App by inject()
    private val eelParser = EelParser()
    private var recyclerView: RecyclerView? = null
    private var reportedProcessingSampleRate: Int? = null
    private var convolverStatusUpdater: (() -> Unit)? = null
    // Held strongly: SharedPreferences keeps its listeners in a weak map.
    private var pvbModeListener: SharedPreferences.OnSharedPreferenceChangeListener? = null
    private var pvbXtcListener: SharedPreferences.OnSharedPreferenceChangeListener? = null
    // Alpha 3.1: keeps the slider/model in step with a recalled song and shows the per-song indicator.
    private var pvbTrackListener: SharedPreferences.OnSharedPreferenceChangeListener? = null
    private var pvbTrackIndicator: (() -> Unit)? = null
    // Alpha 3.2: "볼륨 연동 세기" live summary (refreshed by the controller's status updates and setting changes).
    private var pvbVolLinkListener: SharedPreferences.OnSharedPreferenceChangeListener? = null
    private var pvbVolLinkIndicator: (() -> Unit)? = null

    private val listener =
        SharedPreferences.OnSharedPreferenceChangeListener { _, _ ->
            requireContext().sendLocalBroadcast(Intent(Constants.ACTION_PREFERENCES_UPDATED))
            convolverStatusUpdater?.invoke()
        }

    private val listenerApp =
        SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            when(key) {
                context?.resources?.getString(R.string.key_appearance_show_icons) -> updateIconState()
            }
        }

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when(intent?.action) {
                Constants.ACTION_PRESET_LOADED -> {
                    val id = this@PreferenceGroupFragment.id
                    Timber.d("Reloading group fragment for ${this@PreferenceGroupFragment.preferenceManager.sharedPreferencesName}")
                    (requireParentFragment() as DspFragment).restartFragment(id, cloneInstance(this@PreferenceGroupFragment))
                }
                Constants.ACTION_REPORT_SAMPLE_RATE -> {
                    reportedProcessingSampleRate = intent
                        .getFloatExtra(Constants.EXTRA_SAMPLE_RATE, 0f)
                        .roundToInt()
                    convolverStatusUpdater?.invoke()
                }
            }
        }
    }

    private fun updateIconState() {
        if(preferenceScreen.preferenceCount > 0) {
            (preferenceScreen.getPreference(0) as? SwitchPreferenceGroup?)
                ?.setIsIconVisible(prefsApp.get<Boolean>(R.string.key_appearance_show_icons))
        }
    }

    override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
        val args = requireArguments()
        preferenceManager.sharedPreferencesName = args.getString(BUNDLE_PREF_NAME)
        @Suppress("DEPRECATION")
        preferenceManager.sharedPreferencesMode = Context.MODE_MULTI_PROCESS
        if (args.getInt(BUNDLE_XML_RES) == R.xml.dsp_pvb_preferences) {
            preferenceManager.sharedPreferences?.let { PvbSettings.migrateVirtualBassModel(it) }
        }
        addPreferencesFromResource(args.getInt(BUNDLE_XML_RES))

        requireContext().registerLocalReceiver(receiver, IntentFilter().apply {
            addAction(Constants.ACTION_PRESET_LOADED)
            addAction(Constants.ACTION_REPORT_SAMPLE_RATE)
        })

        when(args.getInt(BUNDLE_XML_RES)) {
            R.xml.dsp_pvb_preferences -> setupPvbVirtualBass()
            R.xml.dsp_convolver_preferences -> setupConvolverSampleRateFiles()
            R.xml.dsp_compander_preferences -> {
                findPreference<MaterialSeekbarPreference>(getString(R.string.key_compander_granularity))?.valueLabelOverride =
                    fun(it: Float): String {
                        return when(it.roundToInt()) {
                            0 -> getString(R.string.compander_granularity_very_low)
                            1 -> getString(R.string.compander_granularity_low)
                            2 -> getString(R.string.compander_granularity_medium)
                            3 -> getString(R.string.compander_granularity_high)
                            4 -> getString(R.string.compander_granularity_extreme)
                            else -> it.roundToInt().toString()
                        }
                    }
            }
            R.xml.dsp_stereowide_preferences -> {
                findPreference<MaterialSeekbarPreference>(getString(R.string.key_stereowide_mode))?.valueLabelOverride =
                    fun(it: Float): String {
                        return if (it in 49.0..51.0)
                            getString(R.string.stereowide_level_none)
                        else if(it >= 60)
                            getString(R.string.stereowide_level_very_wide)
                        else if(it >= 51)
                            getString(R.string.stereowide_level_wide)
                        else if(it <= 40)
                            getString(R.string.stereowide_level_very_narrow)
                        else if(it <= 49)
                            getString(R.string.stereowide_level_narrow)
                        else
                            it.toString()
                    }
            }
            R.xml.dsp_liveprog_preferences -> {
                val liveprogParams = findPreference<Preference>(getString(R.string.key_liveprog_params))
                val liveprogEdit = findPreference<Preference>(getString(R.string.key_liveprog_edit))
                val liveprogFile = findPreference<FileLibraryPreference>(getString(R.string.key_liveprog_file))

                fun updateLiveprog(newValue: String) {
                    eelParser.load(FileLibraryPreference.createFullPathCompat(requireContext(), newValue))
                    val count = eelParser.properties.size
                    val filePresent = eelParser.contents != null
                    val uiUpdate = {
                        liveprogEdit?.isEnabled = filePresent

                        liveprogParams?.isEnabled = count > 0

                        try {
                            liveprogParams?.summary = if (count > 0)
                                resources.getQuantityString(R.plurals.custom_parameters, count, count)
                            else
                                getString(R.string.liveprog_additional_params_not_supported)
                        }
                        catch(ex: IllegalStateException) {
                            /* Because this lambda is executed async, it is possible that it is called
                               while the fragment is destroyed, leading to accessing a detached context */
                            Timber.d(ex)
                        }
                    }

                    if (recyclerView == null)
                        // Recycler view doesn't exist yet, directly setup the preference
                        uiUpdate()
                    else
                        // Recycler view does exist, queue on UI thread
                        recyclerView!!.post(uiUpdate)
                }

                liveprogFile?.summaryProvider = SummaryProvider<FileLibraryPreference> {
                    updateLiveprog(it.value)
                    if(it.value == null || it.value.isBlank() || !eelParser.isFileLoaded) {
                        getString(R.string.liveprog_no_script_selected)
                    }
                    else
                        eelParser.description
                }

                FileLibraryPreference.createFullPathNullCompat(requireContext(), liveprogFile?.value)?.let {
                    updateLiveprog(it)
                }

                liveprogFile?.setOnPreferenceChangeListener { _, newValue ->
                    updateLiveprog(newValue as String)
                    true
                }

                liveprogParams?.setOnPreferenceClickListener {
                    val intent = Intent(requireContext(), LiveprogParamsActivity::class.java)
                    intent.putExtra(LiveprogParamsActivity.EXTRA_TARGET_FILE, FileLibraryPreference.createFullPathNullCompat(requireContext(), liveprogFile?.value))
                    startActivity(intent)
                    true
                }

                liveprogEdit?.setOnPreferenceClickListener {
                    val intent = Intent(requireContext(), LiveprogEditorActivity::class.java)
                    intent.putExtra(LiveprogEditorActivity.EXTRA_TARGET_FILE, FileLibraryPreference.createFullPathNullCompat(requireContext(), liveprogFile?.value))
                    startActivity(intent)
                    true
                }
            }
            R.xml.dsp_graphiceq_preferences -> {
                findPreference<Preference>(getString(R.string.key_geq_nodes))?.setOnPreferenceClickListener {
                    val intent = Intent(requireContext(), GraphicEqualizerActivity::class.java)
                    startActivity(intent)
                    true
                }
            }
            R.xml.dsp_parametriceq_preferences -> {
                findPreference<Preference>(getString(R.string.key_peq_bands))?.setOnPreferenceClickListener {
                    val intent = Intent(requireContext(), ParametricEqualizerActivity::class.java)
                    startActivity(intent)
                    true
                }
            }
        }

        updateIconState()

        preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(listener)
        prefsApp.registerOnSharedPreferenceChangeListener(listenerApp)
    }

    private val KEY_DEV_MODE_ROW = "pvb_dev_mode"

    /** Keys shown only with the research tools (general build: after the hidden unlock; s26u: always). */
    private val pvbResearchKeys = setOf(
        PvbSettings.KEY_VB_ALGO, PvbSettings.KEY_LOW_Q, PvbSettings.KEY_HI_Q, PvbSettings.KEY_HS_DB, PvbSettings.KEY_HS_HZ,
        PvbSettings.KEY_VOL_REF_PCT, PvbSettings.KEY_VOL_SLOPE, PvbSettings.KEY_VOL_CAP_DB, PvbSettings.KEY_VOL_MAX_DB,
        PvbSettings.KEY_DYN_ON, PvbSettings.KEY_DYN_UP_MAX_DB, PvbSettings.KEY_DYN_REF_DB,
        PvbSettings.KEY_VB_VOL_REF_PCT, PvbSettings.KEY_VB_VOL_SLOPE, PvbSettings.KEY_VB_VOL_MAX_DB,
    )

    private fun pvbResearchVisible(p: Preference): Boolean = PvbBuild.researchUi || p.key !in pvbResearchKeys

    /**
     * Build differences of the PVB card. s26u: nothing changes. General: the record-storing entries (per-song
     * memory, live blind comparison) are removed, and the sliders get the safe caps (the settings are clamped to
     * the same caps when read, PvbSettings.load).
     */
    private fun adaptPvbForBuild() {
        val group = findPreference<SwitchPreferenceGroup>(PvbSettings.KEY_ENABLE) ?: return
        if (!PvbBuild.recordFeatures) {
            listOf(PvbSettings.KEY_VB_TRACK_MEMORY, PvbSettings.KEY_VB_TRACK_LIST, PvbSettings.KEY_VB_LIVE_AB).forEach { key ->
                findPreference<Preference>(key)?.let { group.removePreference(it) }
            }
        }
        val caps = PvbBuild.caps ?: return
        fun bar(key: String) = findPreference<MaterialSeekbarPreference>(key)
        bar(PvbSettings.KEY_OUT_DB)?.setMax(caps.outDbMax)
        bar(PvbSettings.KEY_CEIL_DB)?.setMax(caps.ceilDbMax)
        bar(PvbSettings.KEY_LOW_DB)?.setMax(caps.lowDbMax)
        bar(PvbSettings.KEY_LOW_Q)?.setMax(caps.lowQMax)
        bar(PvbSettings.KEY_HP_HZ)?.setMin(caps.hpHzMin)
        bar(PvbSettings.KEY_RELEASE_MS)?.setMin(caps.releaseMsMin)
        bar(PvbSettings.KEY_VB_STRENGTH_DB)?.setMax(caps.vbLevelMax)
        // Bring stored values that a slider can no longer show into range (also what the engine plays).
        val prefs = preferenceManager.sharedPreferences ?: return
        val s = PvbSettings.load(prefs)
        mapOf(PvbSettings.KEY_OUT_DB to s.outDb, PvbSettings.KEY_CEIL_DB to s.ceilDb, PvbSettings.KEY_LOW_DB to s.lowDb,
            PvbSettings.KEY_LOW_Q to s.lowQ, PvbSettings.KEY_HP_HZ to s.hpHz, PvbSettings.KEY_RELEASE_MS to s.releaseMs,
            PvbSettings.KEY_VB_STRENGTH_DB to s.vbLevelDb).forEach { (key, v) ->
            bar(key)?.let { if (it.getValue() != v) it.setValue(v) }
        }
    }

    /**
     * Crosstalk cancellation ("공간감"): the preset row is derived from mode + strength and never stored (like the
     * virtual bass mode); strength, distance and head size are shown only while it is on.
     */
    private fun setupPvbXtc() {
        val mode = findPreference<ListPreference>(PvbSettings.KEY_XTC_MODE) ?: return
        val strength = findPreference<ListPreference>(PvbSettings.KEY_XTC_STRENGTH)
        val details = listOfNotNull(strength, findPreference<Preference>(PvbSettings.KEY_XTC_DISTANCE),
            findPreference<Preference>(PvbSettings.KEY_XTC_HEAD), findPreference<Preference>(PvbSettings.KEY_XTC_PORTRAIT))
        val splitRows = listOfNotNull(findPreference<Preference>(PvbSettings.KEY_XTC_PORTRAIT_LOW),
            findPreference<Preference>(PvbSettings.KEY_XTC_PORTRAIT_TEST))
        // "Which one is the bottom speaker?": the left channel alone for 3 s through the normal path (DevTestSound).
        findPreference<Preference>(PvbSettings.KEY_XTC_PORTRAIT_TEST)?.setOnPreferenceClickListener {
            val ctx = requireContext()
            val ok = me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService.activeServices > 0 &&
                me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime.status.processing
            if (!ok) {
                android.widget.Toast.makeText(ctx, R.string.pvb_xtc_portrait_test_off, android.widget.Toast.LENGTH_LONG).show()
            } else {
                val sound = me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
                sound.start(me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind.XTC_SWEEP_L)
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ sound.stop() }, 3300L)
            }
            true
        }
        val preset = findPreference<ListPreference>(PvbSettings.KEY_XTC_PRESET)
        // preset key -> (mode, strength); "custom" writes nothing
        val presets = linkedMapOf(
            "off" to (PvbSettings.XTC_OFF to "-6"),
            "subtle" to (PvbSettings.XTC_CENTRE to "-6"),
            "balanced" to (PvbSettings.XTC_FULL to "-4.5"),
            "clear" to (PvbSettings.XTC_FULL to "-3"),
        )
        preset?.apply {
            entries = arrayOf(getString(R.string.pvb_xtc_off), getString(R.string.pvb_xtc_preset_subtle),
                getString(R.string.pvb_xtc_preset_balanced), getString(R.string.pvb_xtc_preset_clear),
                getString(R.string.pvb_xtc_preset_custom))
            entryValues = arrayOf("off", "subtle", "balanced", "clear", "custom")
            summaryProvider = SummaryProvider<ListPreference> { it.entry ?: "" }
        }
        fun refresh() {
            val prefs = preferenceManager.sharedPreferences ?: return
            val s = PvbSettings.load(prefs)
            details.forEach { it.isVisible = s.xtcMode != PvbSettings.XTC_OFF }
            splitRows.forEach { it.isVisible = s.xtcMode != PvbSettings.XTC_OFF && s.xtcPortrait == PvbSettings.XTC_PORTRAIT_SPLIT }
            preset?.value = presets.entries.firstOrNull { (_, v) ->
                v.first == s.xtcMode && (s.xtcMode == PvbSettings.XTC_OFF || v.second.toFloat() == s.xtcStrengthDb)
            }?.key ?: "custom"
        }
        refresh()
        preset?.setOnPreferenceChangeListener { _, newValue ->
            val v = presets[newValue] ?: return@setOnPreferenceChangeListener false
            mode.value = v.first.toString()
            if (v.first != PvbSettings.XTC_OFF) strength?.value = v.second
            refresh()
            false  // derived, never stored
        }
        pvbXtcListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == PvbSettings.KEY_XTC_MODE || key == PvbSettings.KEY_XTC_STRENGTH || key == PvbSettings.KEY_XTC_PORTRAIT) refresh()
        }.also { preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(it) }
    }

    /** Virtual bass is experimental: turning it on only takes effect after the warning is confirmed. */
    private fun setupPvbVirtualBass() {
        adaptPvbForBuild()
        val algo = findPreference<ListPreference>(PvbSettings.KEY_VB_ALGO)?.apply {
            entries = PvbModels.models.map { it.title }.toTypedArray()
            entryValues = PvbModels.models.map { it.key }.toTypedArray()
            summaryProvider = SummaryProvider<ListPreference> { pref ->
                val model = PvbModels.fromKey(pref.value)
                "${model.title} · 약 0.15초 지연\n${model.description}"
            }
        }
        val level = findPreference<MaterialSeekbarPreference>(PvbSettings.KEY_VB_STRENGTH_DB)?.apply {
            valueLabelOverride = { v -> PvbSettings.clampLevel(v).roundToInt().let { if (it > 0) "+$it dB" else "$it dB" } }
        }
        findPreference<ListPreference>(PvbSettings.KEY_VB_MODE)?.let { mode ->
            fun item(title: String, description: String): CharSequence = SpannableStringBuilder(title).apply {
                val start = length
                append("\n").append(description)
                setSpan(RelativeSizeSpan(0.8f), start, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if (PvbBuild.general) {
                // General build: plain names from resources (English/Korean), no model codenames; "custom" is
                // only listed with the research tools (the model list is visible then).
                fun title(key: String) = when (key) {
                    PvbModels.PRESET_FULLNESS -> getString(R.string.vb_preset_fullness_title)
                    PvbModels.PRESET_DEEP -> getString(R.string.vb_preset_deep_title)
                    else -> getString(R.string.vb_preset_custom_title)
                }
                fun desc(key: String) = when (key) {
                    PvbModels.PRESET_FULLNESS -> getString(R.string.vb_preset_fullness_desc)
                    PvbModels.PRESET_DEEP -> getString(R.string.vb_preset_deep_desc)
                    else -> getString(R.string.vb_preset_custom_desc)
                }
                val keys = PvbModels.presets.map { it.key } +
                    (if (PvbBuild.researchUi) listOf(PvbModels.PRESET_CUSTOM) else emptyList())
                mode.entries = keys.map { item(title(it), desc(it)) }.toTypedArray()
                mode.entryValues = keys.toTypedArray()
                mode.summaryProvider = SummaryProvider<ListPreference> { pref ->
                    val key = pref.value ?: PvbModels.PRESET_CUSTOM
                    "${title(key)}\n${desc(key)}\n${getString(R.string.vb_mode_note)}"
                }
            } else {
                mode.entries = (PvbModels.presets.map { item(it.title, it.description) } +
                    item(PvbModels.CUSTOM_TITLE, PvbModels.CUSTOM_DESCRIPTION)).toTypedArray()
                mode.entryValues = (PvbModels.presets.map { it.key } + PvbModels.PRESET_CUSTOM).toTypedArray()
                mode.summaryProvider = SummaryProvider<ListPreference> { pref ->
                    val preset = PvbModels.presets.firstOrNull { it.key == pref.value }
                    (if (preset != null) "${preset.title}\n${preset.description}"
                    else "${PvbModels.CUSTOM_TITLE}\n${PvbModels.CUSTOM_DESCRIPTION}") +
                        "\n모드는 아래의 모델과 크기만 정합니다. 새로운 처리가 아니며 EQ·출력 등 다른 설정은 그대로입니다."
                }
            }
            fun refresh() {
                val prefs = preferenceManager.sharedPreferences ?: return
                val s = PvbSettings.load(prefs)
                mode.value = PvbModels.presetFor(PvbModels.fromId(s.vbAlgo)?.key, s.vbLevelDb)?.key ?: PvbModels.PRESET_CUSTOM
            }
            refresh()
            mode.setOnPreferenceChangeListener { _, newValue ->
                val preset = PvbModels.presets.firstOrNull { it.key == newValue }
                    ?: return@setOnPreferenceChangeListener false  // 사용자 지정: nothing to write
                // Only the model and the level; the engine ramps the level and fades a model switch.
                algo?.value = preset.modelKey
                level?.setValue(preset.levelDb)
                refresh()
                false  // the mode itself is derived, never stored
            }
            pvbModeListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
                if (key == PvbSettings.KEY_VB_ALGO || key == PvbSettings.KEY_VB_STRENGTH_DB) refresh()
            }.also { preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(it) }
        }
        setupPvbXtc()
        if (PvbBuild.recordFeatures) setupPvbTrackMemory(algo, level)  // general: per-song memory does not exist
        setupPvbVolumeLink()
        findPreference<Preference>(PvbSettings.KEY_VB_LIVE_AB)?.setOnPreferenceClickListener {
            startActivity(Intent(requireContext(), LiveAbActivity::class.java))
            true
        }
        // "실험 기능": feedback goes to GitHub Issues (a browser; nothing is sent by the app).
        // Developer mode (general build, after the hidden unlock): opens the developer-mode screen.
        findPreference<Preference>(KEY_DEV_MODE_ROW)?.let { row ->
            row.isVisible = me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral.devModeAvailable
            row.setOnPreferenceClickListener {
                me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral.openDevMode(requireContext())
                true
            }
        }
        findPreference<Preference>(PvbSettings.KEY_X_FEEDBACK)?.setOnPreferenceClickListener {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(FEEDBACK_URL)))
            } catch (_: Exception) {
                requireContext().toast(R.string.no_activity_found)
            }
            true
        }
        val sw = findPreference<SwitchPreferenceCompat>(PvbSettings.KEY_VB_ON) ?: return
        sw.setOnPreferenceChangeListener { _, newValue ->
            if (newValue != true) return@setOnPreferenceChangeListener true
            // General build: the confirmed first-run notice already carries this warning (one consent, FirstRun).
            if (PvbBuild.general && PvbBuild.firstRunConfirmed) return@setOnPreferenceChangeListener true
            AlertDialog.Builder(requireContext())
                .setTitle(R.string.pvb_vb_warning_title)
                .setMessage(R.string.pvb_vb_warning)
                .setPositiveButton(R.string.pvb_vb_warning_ok) { _, _ -> sw.isChecked = true }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
            false  // stays off until confirmed (cancel, back or tapping outside keep it off)
        }
    }

    /**
     * Alpha 3.1 "곡별 세기 기억": the switch (its summary is the live indicator), the list screen, and the slider and
     * model list following a song's recalled setting (TrackLevels writes the same keys the slider does).
     */
    private fun setupPvbTrackMemory(algo: ListPreference?, level: MaterialSeekbarPreference?) {
        val ctx = requireContext().applicationContext
        val levels = TrackLevels.get(ctx)
        val memory = findPreference<SwitchPreferenceCompat>(PvbSettings.KEY_VB_TRACK_MEMORY)
        val list = findPreference<Preference>(PvbSettings.KEY_VB_TRACK_LIST)

        fun db(v: Float) = PvbSettings.clampLevel(v).roundToInt().let { if (it > 0) "+$it dB" else "$it dB" }
        fun update() {
            if (!isAdded) return
            val i = levels.indicator(ctx)
            memory?.summary = when {
                !i.enabled -> getString(R.string.pvb_vb_track_memory_off)
                !i.access -> getString(R.string.pvb_vb_track_memory_no_access)
                !i.watching -> getString(R.string.pvb_vb_track_memory_no_service, db(i.defaultDb))
                i.track == null -> getString(R.string.pvb_vb_track_memory_no_track, db(i.defaultDb))
                else -> {
                    val t = i.track
                    val name = listOfNotNull(t?.title?.trim(), t?.artist?.trim()?.takeIf { it.isNotEmpty() }).joinToString(" — ")
                    if (i.usingSaved) getString(R.string.pvb_vb_track_memory_saved, name, db(i.levelDb), db(i.defaultDb))
                    else getString(R.string.pvb_vb_track_memory_default, name, db(i.levelDb))
                }
            }
            val count = levels.entries().size
            list?.summary = if (count == 0) getString(R.string.pvb_vb_track_list_empty)
                else getString(R.string.pvb_vb_track_list_summary, count)
        }

        memory?.setOnPreferenceChangeListener { _, newValue ->
            if (newValue == true && !TrackLevels.hasNotificationAccess(ctx)) showNotificationAccessDialog()
            true
        }
        list?.setOnPreferenceClickListener {
            startActivity(Intent(requireContext(), TrackLevelsActivity::class.java))
            true
        }

        pvbTrackListener = SharedPreferences.OnSharedPreferenceChangeListener { prefs, key ->
            // A recalled song writes these keys from outside the widgets; bring the widgets along. Writing the
            // same value back is not a change, so this never loops.
            when (key) {
                PvbSettings.KEY_VB_STRENGTH_DB -> level?.let {
                    val v = PvbSettings.load(prefs).vbLevelDb
                    if (it.getValue() != v) it.setValue(v)
                }
                PvbSettings.KEY_VB_ALGO -> algo?.let {
                    val k = PvbModels.fromKey(prefs.getString(PvbSettings.KEY_VB_ALGO, null)).key
                    if (it.value != k) it.value = k
                }
            }
        }.also { preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(it) }
        pvbTrackIndicator = { update() }.also { levels.addListener(it) }
        update()
    }

    /**
     * Alpha 3.2 "볼륨 연동 세기": the switch summary shows what the volume takes off now and the strength that plays
     * (same computation as PvbController), and its three sliders are shown only while it is on.
     */
    private fun setupPvbVolumeLink() {
        val link = findPreference<SwitchPreferenceCompat>(PvbSettings.KEY_VB_VOL_LINK) ?: return
        val keys = setOf(PvbSettings.KEY_VB_VOL_REF_PCT, PvbSettings.KEY_VB_VOL_SLOPE, PvbSettings.KEY_VB_VOL_MAX_DB)
        val group = findPreference<SwitchPreferenceGroup>(PvbSettings.KEY_ENABLE)
        val audio = requireContext().applicationContext.getSystemService(AudioManager::class.java)

        fun num(v: Float, digits: Int = 1): String {   // 8 -> "8", 1.33 -> "1.3", 0.25 -> "0.25" (2 digits)
            val t = String.format(Locale.US, "%.${digits}f", v)
            return if ('.' in t) t.trimEnd('0').trimEnd('.') else t
        }
        fun signedDb(v: Float): String = when {
            abs(v) < 0.05f -> "0 dB"
            v > 0 -> "+${num(v)} dB"
            else -> "−${num(-v)} dB"
        }
        fun update() {
            if (!isAdded) return
            val prefs = preferenceManager.sharedPreferences ?: return
            val s = PvbSettings.load(prefs)
            group?.updateChildrenVisibility()
            if (!s.vbVolLink) {
                link.summary = getString(R.string.pvb_vb_vol_link_off)
                return
            }
            // Same index and maximum the controller reads; unknown -> 0% (no reduction).
            val index = try { audio?.getStreamVolume(AudioManager.STREAM_MUSIC) ?: 0 } catch (_: Exception) { 0 }
            val max = try { audio?.getStreamMaxVolume(AudioManager.STREAM_MUSIC)?.coerceAtLeast(2) ?: 0 } catch (_: Exception) { 0 }
            val pct = VolumeLevelLink.volumePct(index, max).roundToInt().toString()
            val reduction = VolumeLevelLink.reductionFor(s, index, max)
            val applied = VolumeLevelLink.levelFor(s, index, max)
            val ref = num(s.vbVolRefPct, 0)
            val slope = num(s.vbVolSlope, 2)
            val maxDb = num(s.vbVolMaxDb)
            link.summary = if (reduction >= 0.05f)
                getString(R.string.pvb_vb_vol_link_on, pct, signedDb(-reduction), signedDb(applied), ref, slope, maxDb)
            else getString(R.string.pvb_vb_vol_link_on_none, pct, signedDb(applied), ref, slope, maxDb)
        }

        // 0.05 dB steps (the XML attribute only takes integers)
        findPreference<MaterialSeekbarPreference>(PvbSettings.KEY_VB_VOL_SLOPE)?.setSeekBarIncrement(0.05f)
        group?.childFilter = { p ->
            pvbResearchVisible(p) &&
                (p.key !in keys || (preferenceManager.sharedPreferences?.let { PvbSettings.load(it).vbVolLink } ?: false))
        }
        pvbVolLinkListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == PvbSettings.KEY_VB_VOL_LINK || key == PvbSettings.KEY_VB_STRENGTH_DB || key in keys) update()
        }.also { preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(it) }
        pvbVolLinkIndicator = { update() }.also { PvbRuntime.addStatusListener(it) }
        update()
    }

    private fun showNotificationAccessDialog() {
        AlertDialog.Builder(requireContext())
            .setTitle(R.string.pvb_vb_track_memory_access_title)
            .setMessage(R.string.pvb_vb_track_memory_access_message)
            .setPositiveButton(R.string.pvb_vb_track_memory_access_open) { _, _ ->
                try {
                    startActivity(TrackLevels.notificationAccessIntent(requireContext()))
                } catch (_: Exception) {
                    requireContext().toast(R.string.no_activity_found)
                }
            }
            .setNegativeButton(R.string.pvb_vb_track_memory_access_later, null)
            .show()
    }

    override fun onResume() {
        super.onResume()
        pvbTrackIndicator?.invoke()   // back from the notification access screen
        pvbVolLinkIndicator?.invoke() // the volume may have changed meanwhile
    }

    private fun setupConvolverSampleRateFiles() {
        val assignmentPreference = findPreference<Preference>(
            getString(R.string.key_convolver_sample_rate_files)
        ) ?: return
        val filePreference = findPreference<FileLibraryPreference>(
            getString(R.string.key_convolver_file)
        ) ?: return
        val processingPreference = findPreference<Preference>(
            getString(R.string.key_convolver_processing_rate)
        ) ?: return
        val sharedPreferences = preferenceManager.sharedPreferences ?: return
        val assignmentKey = getString(R.string.key_convolver_sample_rate_files)

        fun assignments() = ConvolverSampleRateFiles.decode(
            sharedPreferences.getString(assignmentKey, "").orEmpty()
        )

        fun processingRate(): Int = reportedProcessingSampleRate
            ?: (requireActivity().application as MainApplication).engineSampleRate.roundToInt()

        fun selectedImpulseResponse(rate: Int): String {
            if (!sharedPreferences.getBoolean(getString(R.string.key_convolver_enable), false)) {
                return getString(R.string.convolver_sample_rate_disabled)
            }

            val fallbackFile = filePreference.value.orEmpty()
            val mappedFile = ConvolverSampleRateFiles.resolve(
                sharedPreferences.getString(assignmentKey, "").orEmpty(),
                rate,
                fallbackFile,
            )
            val selectedFile = mappedFile.takeIf {
                File(FileLibraryPreference.createFullPathCompat(requireContext(), it)).isFile
            } ?: fallbackFile
            return selectedFile.takeIf(String::isNotBlank)
                ?.let { File(it).nameWithoutExtension }
                ?: getString(R.string.convolver_sample_rate_no_file)
        }

        fun updateSummary() {
            val count = assignments().size
            val rate = processingRate()
            processingPreference.summary = if (rate > 0) {
                getString(
                    R.string.convolver_processing_rate_status,
                    ConvolverSampleRateFiles.formatKilohertz(rate),
                    selectedImpulseResponse(rate),
                )
            } else {
                getString(R.string.convolver_sample_rate_processing_inactive)
            }
            val assignmentsSummary = if (count == 0)
                getString(R.string.convolver_sample_rate_files_summary)
            else
                getString(R.string.convolver_sample_rate_files_count, count)
            assignmentPreference.summary = assignmentsSummary
        }

        convolverStatusUpdater = ::updateSummary

        assignmentPreference.setOnPreferenceClickListener {
            filePreference.refresh()
            val assignedFiles = assignments()
            val detectedRates = AudioSampleRateDetector.getOutputSampleRates(
                requireContext(),
            )
            val sampleRates = (detectedRates + assignedFiles.keys)
                .filter(ConvolverSampleRateFiles::isSupportedSampleRate)
                .distinct()
                .sorted()
            val rateLabels = sampleRates.map { rate ->
                val fileName = assignedFiles[rate]
                    ?.let { File(it).nameWithoutExtension }
                    ?: getString(R.string.convolver_sample_rate_unassigned)
                getString(
                    R.string.convolver_sample_rate_label,
                    ConvolverSampleRateFiles.formatKilohertz(rate),
                    fileName,
                )
            }.toTypedArray()

            AlertDialog.Builder(requireContext())
                .setTitle(R.string.convolver_sample_rate_files)
                .setItems(rateLabels) { _, rateIndex ->
                    val rate = sampleRates[rateIndex]
                    val choices = arrayOf(getString(R.string.convolver_sample_rate_use_default)) +
                        filePreference.entries.map(CharSequence::toString)

                    AlertDialog.Builder(requireContext())
                        .setTitle(
                            getString(
                                R.string.convolver_sample_rate_select_file,
                                ConvolverSampleRateFiles.formatKilohertz(rate),
                            )
                        )
                        .setItems(choices) { _, fileIndex ->
                            val updatedAssignments = assignments().toMutableMap()
                            if (fileIndex == 0) {
                                updatedAssignments.remove(rate)
                            } else {
                                updatedAssignments[rate] =
                                    filePreference.entryValues[fileIndex - 1].toString()
                            }
                            sharedPreferences.edit()
                                .putString(
                                    assignmentKey,
                                    ConvolverSampleRateFiles.encode(updatedAssignments),
                                )
                                .apply()
                            updateSummary()
                        }
                        .setNegativeButton(android.R.string.cancel, null)
                        .show()
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
            true
        }

        updateSummary()
    }

    override fun onCreateRecyclerView(
        inflater: LayoutInflater,
        parent: ViewGroup,
        savedInstanceState: Bundle?,
    ): RecyclerView {
        return super.onCreateRecyclerView(inflater, parent, savedInstanceState).apply {
            itemAnimator = null // Fix to prevent RecyclerView crash if group is toggled rapidly
            isNestedScrollingEnabled = false

            this@PreferenceGroupFragment.recyclerView = this
        }
    }

    override fun onCreateAdapter(preferenceScreen: PreferenceScreen): RecyclerView.Adapter<*> {
        return RoundedRipplePreferenceGroupAdapter(preferenceScreen)
    }

    override fun onDestroy() {
        convolverStatusUpdater = null
        super.onDestroy()
        requireContext().unregisterLocalReceiver(receiver)
        prefsApp.unregisterOnSharedPreferenceChangeListener(listener)
        preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(listener)
        pvbModeListener?.let { preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(it) }
        pvbModeListener = null
        pvbXtcListener?.let { preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(it) }
        pvbXtcListener = null
        pvbTrackListener?.let { preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(it) }
        pvbTrackListener = null
        pvbTrackIndicator?.let { TrackLevels.removeListener(it) }
        pvbTrackIndicator = null
        pvbVolLinkListener?.let { preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(it) }
        pvbVolLinkListener = null
        pvbVolLinkIndicator?.let { PvbRuntime.removeStatusListener(it) }
        pvbVolLinkIndicator = null
    }

    @Suppress("DEPRECATION")
    override fun onDisplayPreferenceDialog(preference: Preference) {
        when (preference) {
            is EqualizerPreference -> {
                val dialogFragment = EqualizerDialogFragment.newInstance(preference.key)
                dialogFragment.setTargetFragment(this, 0)
                dialogFragment.show(parentFragmentManager, null)
            }
            is CompanderPreference -> {
                val dialogFragment = CompanderDialogFragment.newInstance(preference.key)
                dialogFragment.setTargetFragment(this, 0)
                dialogFragment.show(parentFragmentManager, null)
            }
            is FileLibraryPreference -> {
                val dialogFragment = FileLibraryDialogFragment.newInstance(preference.key)
                dialogFragment.setTargetFragment(this, 0)
                dialogFragment.show(parentFragmentManager, null)
            }
            else -> super.onDisplayPreferenceDialog(preference)
        }
    }

    companion object {
        private const val BUNDLE_PREF_NAME = "preferencesName"
        private const val BUNDLE_XML_RES = "preferencesXmlRes"
        private const val FEEDBACK_URL = "https://github.com/ksysh3-dot/rootnote/issues"

        fun newInstance(preferencesName: String?, @XmlRes preferencesXmlRes: Int): PreferenceGroupFragment {
            return PreferenceGroupFragment().apply {
                arguments = Bundle().apply {
                    putString(BUNDLE_PREF_NAME, preferencesName)
                    putInt(BUNDLE_XML_RES, preferencesXmlRes)
                }
            }
        }

        fun cloneInstance(fragment: PreferenceGroupFragment): PreferenceGroupFragment {
            return fragment.requireArguments().let { args ->
                 newInstance(args.getString(BUNDLE_PREF_NAME), args.getInt(BUNDLE_XML_RES))
            }
        }
    }
}

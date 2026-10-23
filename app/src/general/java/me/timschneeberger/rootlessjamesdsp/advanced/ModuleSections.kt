package me.timschneeberger.rootlessjamesdsp.advanced

import android.content.Intent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.GraphicEqualizerActivity
import me.timschneeberger.rootlessjamesdsp.activity.LiveprogEditorActivity
import me.timschneeberger.rootlessjamesdsp.activity.LiveprogParamsActivity
import me.timschneeberger.rootlessjamesdsp.activity.ParametricEqualizerActivity
import me.timschneeberger.rootlessjamesdsp.liveprog.EelParser
import me.timschneeberger.rootlessjamesdsp.model.GraphicEqNodeList
import me.timschneeberger.rootlessjamesdsp.model.ParametricEqBandList
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnInputDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnPrefsFile
import me.timschneeberger.rootlessjamesdsp.utils.AudioSampleRateDetector
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.ConvolverSampleRateFiles
import java.io.File
import kotlin.math.roundToInt

/*
 * The JamesDSP modules of the advanced screen in the legacy order (DspFragment), one namespace each, with the same
 * keys, defaults and ranges as their preference XML. Slider steps are the legacy increments where the XML set one;
 * the free sliders got a step for the ± buttons and drag (the value input still takes any value in range).
 */

/** The seal of a module while PVB processes ([sealed]): locked for SEALED modules and the output, a note for INFO ones. */
private fun sealOf(policy: JdspChain.Policy?, sealed: Boolean): Seal = when {
    !sealed -> Seal.NONE
    policy == null || policy == JdspChain.Policy.SEALED -> Seal.LOCKED
    policy == JdspChain.Policy.INFO -> Seal.INFO
    else -> Seal.NONE
}

@Composable
fun JamesDspModules(host: RnAdvancedActivity, sealed: Boolean, showIcons: Boolean) {
    val brand = stringResource(R.string.app_brand_name)
    val lockedNote = stringResource(R.string.pvb_jamesdsp_sealed, brand)
    val eqNote = stringResource(R.string.pvb_jamesdsp_eq_info, brand)
    val k = { id: Int -> host.getString(id) }

    // 출력 제어: no switch of its own; sealed = 0 dB post gain and a neutral limiter
    val output = rememberDspFile(Constants.PREF_OUTPUT, host)
    DspModule(stringResource(R.string.output_control_header), R.drawable.ic_twotone_volume_up_24dp, showIcons, output, null,
        sealOf(null, sealed), stringResource(R.string.pvb_jamesdsp_output_sealed, brand)) {
        PrefSlider(output, k(R.string.key_limiter_threshold), stringResource(R.string.output_limiter_threshold), -0.1f,
            -60f..-0.1f, 0.1f, "dB", 2)
        PrefSlider(output, k(R.string.key_limiter_release), stringResource(R.string.output_limiter_release), 60f,
            1.5f..500f, 0.5f, "ms", 2)
        PrefSlider(output, k(R.string.key_output_postgain), stringResource(R.string.output_control_postgain), 0f,
            -15f..15f, 0.1f, "dB", 2)
    }

    // 다이나믹 레인지 컴팬더
    val compander = rememberDspFile(Constants.PREF_COMPANDER, host)
    var companderEdit by remember { mutableStateOf(false) }
    DspModule(stringResource(R.string.compander_enable), R.drawable.ic_baseline_arrow_collapse_24dp, showIcons, compander,
        k(R.string.key_compander_enable), sealOf(JdspChain.Policy.INFO, sealed),
        stringResource(R.string.pvb_jamesdsp_compressor_info, brand)) {
        PrefSlider(compander, k(R.string.key_compander_timeconstant), stringResource(R.string.compander_timeconstant), 0.22f,
            0.06f..0.3f, 0.01f, "s", 2)
        val granularity = listOf(R.string.compander_granularity_very_low, R.string.compander_granularity_low,
            R.string.compander_granularity_medium, R.string.compander_granularity_high, R.string.compander_granularity_extreme)
            .map { stringResource(it) }
        PrefSlider(compander, k(R.string.key_compander_granularity), stringResource(R.string.compander_granularity), 0f,
            0f..4f, 1f, "", 0, strictStep = true, label = { v -> granularity.getOrElse(v.roundToInt()) { v.roundToInt().toString() } })
        PrefChoice(compander, k(R.string.key_compander_tftransforms), stringResource(R.string.compander_tftransforms), "0",
            R.array.compander_tf_transforms, R.array.compander_tf_transforms_values)
        val responseKey = k(R.string.key_compander_response)
        val response = compander.string(responseKey, COMPANDER_DEFAULT)
        val title = stringResource(R.string.rn_adv_compander_edit)
        RnNavRow(title, enabled = !LocalSealed.current) { companderEdit = true }
        CurvePreview(title, { companderEdit = true }) { CompanderPreview(response, it) }
        if (companderEdit) CompanderEditorDialog(host, compander, responseKey, COMPANDER_DEFAULT) { companderEdit = false }
    }

    // 다이나믹 베이스 부스트 (sealed)
    val bass = rememberDspFile(Constants.PREF_BASS, host)
    DspModule(stringResource(R.string.bass_enable), R.drawable.ic_twotone_speaker_24dp, showIcons, bass,
        k(R.string.key_bass_enable), sealOf(JdspChain.Policy.SEALED, sealed), lockedNote) {
        PrefSlider(bass, k(R.string.key_bass_max_gain), stringResource(R.string.bass_max_gain), 5f, 3f..15f, 0.5f, "dB", 2)
    }

    // 멀티 모달 이퀄라이저
    val eq = rememberDspFile(Constants.PREF_EQ, host)
    var eqEdit by remember { mutableStateOf(false) }
    DspModule(stringResource(R.string.eq_enable), R.drawable.ic_baseline_equalizer_24dp, showIcons, eq,
        k(R.string.key_eq_enable), sealOf(JdspChain.Policy.INFO, sealed), eqNote) {
        val typeKey = k(R.string.key_eq_filter_type)
        PrefChoice(eq, typeKey, stringResource(R.string.eq_filter_type), "0", R.array.eq_filter_types, R.array.eq_filter_types_values)
        PrefChoice(eq, k(R.string.key_eq_interpolation), stringResource(R.string.eq_interpolator), "0",
            R.array.eq_interpolators, R.array.eq_interpolators_values)
        val bandsKey = k(R.string.key_eq_bands)
        val bands = eq.string(bandsKey, Constants.DEFAULT_EQ)
        val type = eq.string(typeKey, "0").toIntOrNull() ?: 0
        val title = stringResource(R.string.rn_adv_eq_edit)
        RnNavRow(title, enabled = !LocalSealed.current) { eqEdit = true }
        CurvePreview(title, { eqEdit = true }) { EqPreview(bands, type, it) }
        if (eqEdit) EqEditorDialog(host, eq, bandsKey, Constants.DEFAULT_EQ, type) { eqEdit = false }
    }

    // Parametric equalizer: its editor stays a screen of its own
    val peq = rememberDspFile(Constants.PREF_PEQ, host)
    DspModule(stringResource(R.string.peq_enable), R.drawable.ic_baseline_equalizer_24dp, showIcons, peq,
        k(R.string.key_peq_enable), sealOf(JdspChain.Policy.INFO, sealed), eqNote) {
        val value = peq.string(k(R.string.key_peq_bands), Constants.DEFAULT_PEQ)
        val count = remember(value) { ParametricEqBandList().apply { deserialize(value) }.size }
        val preamp = peq.float(k(R.string.key_peq_preamp), 0f)
        val open = { host.launchSafely { host.startActivity(Intent(host, ParametricEqualizerActivity::class.java)) } }
        val title = stringResource(R.string.peq_bands)
        RnNavRow(title, pluralStringResource(R.plurals.peq_bands_count, count, count), onClick = open)
        CurvePreview(title, open) { PeqPreview(value, preamp, it) }
    }

    // 임의 응답 이퀄라이저 (GEQ): its editor (and AutoEQ) stays a screen of its own
    val geq = rememberDspFile(Constants.PREF_GEQ, host)
    DspModule(stringResource(R.string.geq_enable), R.drawable.ic_baseline_chart_timeline_variant_24dp, showIcons, geq,
        k(R.string.key_geq_enable), sealOf(JdspChain.Policy.INFO, sealed), eqNote) {
        val value = geq.string(k(R.string.key_geq_nodes), Constants.DEFAULT_GEQ)
        val count = remember(value) { GraphicEqNodeList().apply { deserialize(value) }.size }
        val open = { host.launchSafely { host.startActivity(Intent(host, GraphicEqualizerActivity::class.java)) } }
        val title = stringResource(R.string.geq_nodes)
        RnNavRow(title, pluralStringResource(R.plurals.nodes, count, count), onClick = open)
        CurvePreview(title, open) { GeqPreview(value, it) }
    }

    // 주파수 응답 보정 (ViPER-DDC)
    val ddc = rememberDspFile(Constants.PREF_DDC, host)
    DspModule(stringResource(R.string.ddc_enable), R.drawable.ic_baseline_sine_wave_24dp, showIcons, ddc,
        k(R.string.key_ddc_enable), Seal.NONE, null) {
        FileRowWithLibrary(host, ddc, k(R.string.key_ddc_file), stringResource(R.string.ddc_file), LibraryType.DDC)
    }

    // 컨볼버
    val convolver = rememberDspFile(Constants.PREF_CONVOLVER, host)
    DspModule(stringResource(R.string.convolver_enable), R.drawable.ic_baseline_waveform_24dp, showIcons, convolver,
        k(R.string.key_convolver_enable), Seal.NONE, null) {
        ConvolverRows(host, convolver)
    }

    // 실시간 프로그래밍 DSP
    val liveprog = rememberDspFile(Constants.PREF_LIVEPROG, host)
    DspModule(stringResource(R.string.liveprog_enable), R.drawable.ic_baseline_code_tags_24dp, showIcons, liveprog,
        k(R.string.key_liveprog_enable), Seal.NONE, null) {
        LiveprogRows(host, liveprog)
    }

    // 아날로그 모델링 (sealed)
    val tube = rememberDspFile(Constants.PREF_TUBE, host)
    DspModule(stringResource(R.string.tube_enable), R.drawable.ic_baseline_led_outline_24dp, showIcons, tube,
        k(R.string.key_tube_enable), sealOf(JdspChain.Policy.SEALED, sealed), lockedNote) {
        PrefSlider(tube, k(R.string.key_tube_drive), stringResource(R.string.tube_drive), 2f, -3f..12f, 0.5f, "dB", 2)
    }

    // 음장 넓이
    val wide = rememberDspFile(Constants.PREF_STEREOWIDE, host)
    DspModule(stringResource(R.string.stereowide_enable), R.drawable.ic_baseline_cone_24dp, showIcons, wide,
        k(R.string.key_stereowide_enable), Seal.NONE, null) {
        val none = stringResource(R.string.stereowide_level_none)
        val veryWide = stringResource(R.string.stereowide_level_very_wide)
        val wideL = stringResource(R.string.stereowide_level_wide)
        val veryNarrow = stringResource(R.string.stereowide_level_very_narrow)
        val narrow = stringResource(R.string.stereowide_level_narrow)
        PrefSlider(wide, k(R.string.key_stereowide_mode), stringResource(R.string.stereowide_level), 60f, 30f..75f, 1f, "", 2,
            label = { v ->
                when {
                    v in 49f..51f -> none
                    v >= 60f -> veryWide
                    v >= 51f -> wideL
                    v <= 40f -> veryNarrow
                    v <= 49f -> narrow
                    else -> v.toString()
                }
            })
    }

    // 크로스피드
    val crossfeed = rememberDspFile(Constants.PREF_CROSSFEED, host)
    DspModule(stringResource(R.string.crossfeed_enable), R.drawable.ic_baseline_image_filter_tilt_shift_24dp, showIcons, crossfeed,
        k(R.string.key_crossfeed_enable), Seal.NONE, null) {
        PrefChoice(crossfeed, k(R.string.key_crossfeed_mode), stringResource(R.string.crossfeed_preset), "5",
            R.array.crossfeed_modes, R.array.crossfeed_modes_values)
    }

    // 가상 공간 효과
    val reverb = rememberDspFile(Constants.PREF_REVERB, host)
    DspModule(stringResource(R.string.reverb_enable), R.drawable.ic_baseline_cube_outline_24dp, showIcons, reverb,
        k(R.string.key_reverb_enable), Seal.NONE, null) {
        PrefChoice(reverb, k(R.string.key_reverb_preset), stringResource(R.string.reverb_room_type), "15",
            R.array.reverb_presets, R.array.reverb_presets_values)
    }
}

private const val COMPANDER_DEFAULT = "95.0;200.0;400.0;800.0;1600.0;3400.0;7500.0;0;0;0;0;0;0;0"

/** A module's file row: the chosen file's name (or none) and the library sheet. */
@Composable
private fun FileRowWithLibrary(host: RnAdvancedActivity, file: RnPrefsFile, key: String, title: String, type: LibraryType,
                               line: String? = null) {
    var open by remember { mutableStateOf(false) }
    val value = file.string(key, "")
    RnNavRow(title, line ?: (FileLibrary.displayName(value) ?: stringResource(
        if (type == LibraryType.LIVEPROG) R.string.liveprog_no_script_selected else R.string.filelibrary_no_file_selected)),
        enabled = !LocalSealed.current) { open = true }
    if (open) FileLibrarySheet(host, type, title, value, onSelect = { file.put(key, it) }, onDismiss = { open = false })
}

/**
 * Convolver: the impulse response, the per-sample-rate files (legacy setupConvolverSampleRateFiles: pick a rate, then a
 * file or "use default"), the current processing line, the optimisation mode and the advanced waveform text.
 */
@Composable
private fun ConvolverRows(host: RnAdvancedActivity, f: RnPrefsFile) {
    val context = LocalContext.current
    val k = { id: Int -> host.getString(id) }
    val fileKey = k(R.string.key_convolver_file)
    val mapKey = k(R.string.key_convolver_sample_rate_files)
    FileRowWithLibrary(host, f, fileKey, stringResource(R.string.convolver_impulse), LibraryType.CONVOLVER)

    val assignments = ConvolverSampleRateFiles.decode(f.string(mapKey, ""))
    var pickRate by remember { mutableStateOf<List<Int>?>(null) }
    var pickFileFor by remember { mutableStateOf<Int?>(null) }
    RnNavRow(stringResource(R.string.convolver_sample_rate_files),
        if (assignments.isEmpty()) stringResource(R.string.convolver_sample_rate_files_summary)
        else stringResource(R.string.convolver_sample_rate_files_count, assignments.size)) {
        pickRate = (AudioSampleRateDetector.getOutputSampleRates(context) + assignments.keys)
            .filter(ConvolverSampleRateFiles::isSupportedSampleRate).distinct().sorted()
    }

    // 현재 처리: the engine's reported rate, else the app's last known one
    val rate = host.sampleRate.takeIf { it > 0 } ?: (host.application as MainApplication).engineSampleRate.roundToInt()
    val enabled = f.bool(k(R.string.key_convolver_enable), false)
    val fallback = f.string(fileKey, "")
    val processing = if (rate > 0) {
        val chosen = if (!enabled) stringResource(R.string.convolver_sample_rate_disabled) else {
            val mapped = ConvolverSampleRateFiles.resolve(f.string(mapKey, ""), rate, fallback)
            val file = mapped.takeIf { File(FileLibrary.fullPath(context, it)).isFile } ?: fallback
            file.takeIf(String::isNotBlank)?.let { File(it).nameWithoutExtension } ?: stringResource(R.string.convolver_sample_rate_no_file)
        }
        stringResource(R.string.convolver_processing_rate_status, ConvolverSampleRateFiles.formatKilohertz(rate), chosen)
    } else stringResource(R.string.convolver_sample_rate_processing_inactive)
    RnNavRow(stringResource(R.string.convolver_processing_rate), processing, onClick = null)

    PrefChoice(f, k(R.string.key_convolver_mode), stringResource(R.string.convolver_convolution_mode), "0",
        R.array.convolver_convolution_mode, R.array.convolver_convolution_mode_values)

    val advKey = k(R.string.key_convolver_adv_imp)
    var editAdv by remember { mutableStateOf(false) }
    val adv = f.string(advKey, Constants.DEFAULT_CONVOLVER_ADVIMP)
    RnNavRow(stringResource(R.string.convolver_advanced_editing), adv, enabled = !LocalSealed.current) { editAdv = true }
    if (editAdv) RnInputDialog(stringResource(R.string.convolver_advanced_editing), adv,
        onDone = { f.put(advKey, it); editAdv = false }, onDismiss = { editAdv = false })

    val unassigned = stringResource(R.string.convolver_sample_rate_unassigned)
    pickRate?.let { rates ->
        RnChoiceSheet(stringResource(R.string.convolver_sample_rate_files),
            rates.map { r ->
                RnChoice(r, context.getString(R.string.convolver_sample_rate_label, ConvolverSampleRateFiles.formatKilohertz(r),
                    assignments[r]?.let { File(it).nameWithoutExtension } ?: unassigned))
            }, selected = null, onDismiss = { pickRate = null }) { r -> pickRate = null; pickFileFor = r }
    }
    pickFileFor?.let { r ->
        val files = remember { FileLibrary.list(context, LibraryType.CONVOLVER) }
        val choices = listOf(RnChoice("", stringResource(R.string.convolver_sample_rate_use_default))) +
            files.map { RnChoice(it.path, it.name) }
        RnChoiceSheet(stringResource(R.string.convolver_sample_rate_select_file, ConvolverSampleRateFiles.formatKilohertz(r)),
            choices, selected = assignments[r], onDismiss = { pickFileFor = null }) { path ->
            pickFileFor = null
            val updated = ConvolverSampleRateFiles.decode(f.string(mapKey, "")).toMutableMap()
            if (path.isEmpty()) updated.remove(r) else updated[r] = path
            f.put(mapKey, ConvolverSampleRateFiles.encode(updated))
        }
    }
}

/** Liveprog: the script (its description as the line), its parameters screen and the built-in editor. */
@Composable
private fun LiveprogRows(host: RnAdvancedActivity, f: RnPrefsFile) {
    val context = LocalContext.current
    val key = host.getString(R.string.key_liveprog_file)
    val value = f.string(key, "")
    val full = FileLibrary.fullPath(context, value)
    // re-read when the file changes, on return from the editors, and after a preset load
    val script = remember(value, host.resumeTick, host.presetTick) {
        EelParser().apply { if (value.isNotBlank()) load(full) }
    }
    val described = if (value.isBlank() || !script.isFileLoaded) stringResource(R.string.liveprog_no_script_selected)
        else script.description ?: FileLibrary.displayName(value)
    FileRowWithLibrary(host, f, key, stringResource(R.string.liveprog_file), LibraryType.LIVEPROG, line = described)
    val count = script.properties.size
    RnNavRow(stringResource(R.string.liveprog_additional_params),
        if (count > 0) pluralStringResource(R.plurals.custom_parameters, count, count)
        else stringResource(R.string.liveprog_additional_params_not_supported),
        enabled = count > 0 && !LocalSealed.current) {
        host.launchSafely {
            host.startActivity(Intent(host, LiveprogParamsActivity::class.java)
                .putExtra(LiveprogParamsActivity.EXTRA_TARGET_FILE, full))
        }
    }
    RnNavRow(stringResource(R.string.liveprog_edit_header), stringResource(R.string.liveprog_edit),
        enabled = script.contents != null && !LocalSealed.current) {
        host.launchSafely {
            host.startActivity(Intent(host, LiveprogEditorActivity::class.java)
                .putExtra(LiveprogEditorActivity.EXTRA_TARGET_FILE, full))
        }
    }
}

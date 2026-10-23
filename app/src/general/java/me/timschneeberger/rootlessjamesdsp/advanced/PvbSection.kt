package me.timschneeberger.rootlessjamesdsp.advanced

import android.content.Context
import android.content.SharedPreferences
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestKind
import me.timschneeberger.rootlessjamesdsp.pvb.DevTestSound
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings.Companion as P
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink
import me.timschneeberger.rootlessjamesdsp.service.BaseAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceRow
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnDivider
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.ui.RnPrefsFile
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

/** The PVB card's logic that lived in PreferenceGroupFragment (setupPvbVirtualBass and its helpers). */
object PvbAdvanced {
    /** Shown only with the research tools (general build: after the hidden unlock in 앱 정보). */
    val researchKeys = setOf(
        P.KEY_VB_ALGO, P.KEY_LOW_Q, P.KEY_HI_Q, P.KEY_HS_DB, P.KEY_HS_HZ,
        P.KEY_VOL_REF_PCT, P.KEY_VOL_SLOPE, P.KEY_VOL_CAP_DB, P.KEY_VOL_MAX_DB,
        P.KEY_DYN_ON, P.KEY_DYN_UP_MAX_DB, P.KEY_DYN_REF_DB,
        P.KEY_VB_VOL_REF_PCT, P.KEY_VB_VOL_SLOPE, P.KEY_VB_VOL_MAX_DB,
    )

    /** "공간감 프리셋": preset key -> (mode, strength list value); "custom" writes nothing. */
    val xtcPresets = linkedMapOf(
        "off" to (P.XTC_OFF to "-6"),
        "subtle" to (P.XTC_CENTRE to "-6"),
        "balanced" to (P.XTC_FULL to "-4.5"),
        "clear" to (P.XTC_FULL to "-3"),
    )

    fun xtcPreset(s: PvbSettings): String = xtcPresets.entries.firstOrNull { (_, v) ->
        v.first == s.xtcMode && (s.xtcMode == P.XTC_OFF || v.second.toFloat() == s.xtcStrengthDb)
    }?.key ?: "custom"

    /**
     * Stored values that the general build's sliders can no longer show are written back clamped (adaptPvbForBuild);
     * the engine already plays the clamped values (PvbSettings.load).
     */
    fun writeBackCaps(prefs: SharedPreferences) {
        PvbBuild.caps ?: return
        val s = PvbSettings.load(prefs)
        val edit = prefs.edit()
        var changed = false
        mapOf(P.KEY_OUT_DB to s.outDb, P.KEY_CEIL_DB to s.ceilDb, P.KEY_LOW_DB to s.lowDb, P.KEY_LOW_Q to s.lowQ,
            P.KEY_HP_HZ to s.hpHz, P.KEY_RELEASE_MS to s.releaseMs, P.KEY_VB_STRENGTH_DB to s.vbLevelDb).forEach { (key, v) ->
            val stored = prefs.all[key] as? Float ?: return@forEach  // absent: the slider shows the default
            if (stored != v) { edit.putFloat(key, v); changed = true }
        }
        if (changed) edit.apply()
    }

    private fun num(v: Float, digits: Int = 1): String {   // 8 -> "8", 1.33 -> "1.3", 0.25 -> "0.25" (2 digits)
        val t = String.format(Locale.US, "%.${digits}f", v)
        return if ('.' in t) t.trimEnd('0').trimEnd('.') else t
    }

    private fun signedDb(v: Float): String = when {
        abs(v) < 0.05f -> "0 dB"
        v > 0 -> "+${num(v)} dB"
        else -> "−${num(-v)} dB"
    }

    /** "볼륨 연동 세기" line: what the volume takes off now and the strength that plays (PvbController's computation). */
    fun vbVolLinkLine(context: Context, s: PvbSettings): String {
        if (!s.vbVolLink) return context.getString(R.string.pvb_vb_vol_link_off)
        val audio = context.applicationContext.getSystemService(AudioManager::class.java)
        val index = try { audio?.getStreamVolume(AudioManager.STREAM_MUSIC) ?: 0 } catch (_: Exception) { 0 }
        val max = try { audio?.getStreamMaxVolume(AudioManager.STREAM_MUSIC)?.coerceAtLeast(2) ?: 0 } catch (_: Exception) { 0 }
        val pct = VolumeLevelLink.volumePct(index, max).roundToInt().toString()
        val reduction = VolumeLevelLink.reductionFor(s, index, max)
        val applied = VolumeLevelLink.levelFor(s, index, max)
        val ref = num(s.vbVolRefPct, 0)
        val slope = num(s.vbVolSlope, 2)
        val maxDb = num(s.vbVolMaxDb)
        return if (reduction >= 0.05f)
            context.getString(R.string.pvb_vb_vol_link_on, pct, signedDb(-reduction), signedDb(applied), ref, slope, maxDb)
        else context.getString(R.string.pvb_vb_vol_link_on_none, pct, signedDb(applied), ref, slope, maxDb)
    }

    /** "어느 쪽이 아래 스피커인지 확인": the left channel alone for 3 s through the normal path, while processing. */
    fun portraitTest(context: Context) {
        val ok = BaseAudioProcessorService.activeServices > 0 && PvbRuntime.status.processing
        if (!ok) {
            Toast.makeText(context, R.string.pvb_xtc_portrait_test_off, Toast.LENGTH_LONG).show()
            return
        }
        DevTestSound.start(DevTestKind.XTC_SWEEP_L)
        Handler(Looper.getMainLooper()).postDelayed({ DevTestSound.stop() }, 3300L)
    }
}

/**
 * The PVB settings (legacy dsp_pvb_preferences + setupPvbVirtualBass): the master switch "스피커 보정" and, while it
 * is on, speaker-only, developer mode, spatial, tone, output, the volume rows, virtual bass and the experimental
 * options; "끌 때 음량 맞춤" is always shown. Values are written straight to pvb_settings (the controller listens to
 * that file; no broadcast). Derived rows (공간감 프리셋, 가상 저음 모드) are computed and never stored.
 */
@Composable
fun PvbSection(host: RnAdvancedActivity, showIcons: Boolean) {
    val context = LocalContext.current
    val p = rememberPvbFile()
    host.resumeTick                       // the research unlock happens in 앱 정보: re-read on return
    host.statusTick                       // the volume-link line follows the controller's status
    val research = PvbBuild.researchUi
    val caps = PvbBuild.caps
    val s = p.read { PvbSettings.load(it) }
    val enabled = p.bool(P.KEY_ENABLE, true)
    var vbWarning by remember { mutableStateOf(false) }

    RnSwitchRow(stringResource(R.string.pvb_enable), enabled, { p.put(P.KEY_ENABLE, it) }, bold = true,
        icon = if (showIcons) painterResource(R.drawable.ic_twotone_speaker_24dp) else null)

    if (enabled) {
        PrefSwitch(p, P.KEY_SPEAKER_ONLY, stringResource(R.string.pvb_speaker_only), true,
            line = stringResource(R.string.pvb_speaker_only_summary))
        if (PvbGeneral.devModeAvailable)
            RnNavRow(stringResource(R.string.pvb_dev_mode), stringResource(R.string.pvb_dev_mode_summary)) {
                PvbGeneral.openDevMode(context)
            }

        // 공간감
        RnSectionTitle(stringResource(R.string.home_xtc_title))
        val presetLabels = listOf(R.string.pvb_xtc_off, R.string.pvb_xtc_preset_subtle, R.string.pvb_xtc_preset_balanced,
            R.string.pvb_xtc_preset_clear, R.string.pvb_xtc_preset_custom).map { stringResource(it) }
        val presetKeys = listOf("off", "subtle", "balanced", "clear", "custom")
        RnChoiceRow(stringResource(R.string.pvb_xtc_preset), presetKeys.mapIndexed { i, k -> RnChoice(k, presetLabels[i]) },
            PvbAdvanced.xtcPreset(s), { key ->
                val v = PvbAdvanced.xtcPresets[key] ?: return@RnChoiceRow
                val edit = p.prefs.edit().putString(P.KEY_XTC_MODE, v.first.toString())
                if (v.first != P.XTC_OFF) edit.putString(P.KEY_XTC_STRENGTH, v.second)
                edit.apply()
            })
        PrefChoice(p, P.KEY_XTC_MODE, stringResource(R.string.pvb_xtc_mode), "0",
            R.array.pvb_xtc_mode_entries, R.array.pvb_xtc_mode_values)
        if (s.xtcMode != P.XTC_OFF) {
            PrefChoice(p, P.KEY_XTC_STRENGTH, stringResource(R.string.pvb_xtc_strength), "-6",
                R.array.pvb_xtc_strength_entries, R.array.pvb_xtc_strength_values)
            PrefSlider(p, P.KEY_XTC_DISTANCE, stringResource(R.string.pvb_xtc_distance), 40f, 25f..60f, 1f, "cm", 0,
                strictStep = true)
            PrefChoice(p, P.KEY_XTC_PORTRAIT, stringResource(R.string.pvb_xtc_portrait), "0",
                R.array.pvb_xtc_portrait_entries, R.array.pvb_xtc_portrait_values)
            if (s.xtcPortrait == P.XTC_PORTRAIT_SPLIT) {
                PrefChoice(p, P.KEY_XTC_PORTRAIT_LOW, stringResource(R.string.pvb_xtc_portrait_low), "R",
                    R.array.pvb_xtc_portrait_low_entries, R.array.pvb_xtc_portrait_low_values)
                RnNavRow(stringResource(R.string.pvb_xtc_portrait_test), stringResource(R.string.pvb_xtc_portrait_test_summary),
                    chevron = false) { PvbAdvanced.portraitTest(context) }
            }
            PrefChoice(p, P.KEY_XTC_HEAD, stringResource(R.string.pvb_xtc_head), "57",
                R.array.pvb_xtc_head_entries, R.array.pvb_xtc_head_values)
        }

        // 음색 보정 (the general build's caps narrow some ranges)
        RnSectionTitle(stringResource(R.string.rn_adv_section_tone))
        PrefSlider(p, P.KEY_LOW_DB, stringResource(R.string.pvb_low_db), 3f, -6f..(caps?.lowDbMax ?: 9f), 0.5f, "dB", 1)
        PrefSlider(p, P.KEY_LOW_HZ, stringResource(R.string.pvb_low_hz), 220f, 150f..350f, 5f, "Hz", 0)
        if (research) PrefSlider(p, P.KEY_LOW_Q, stringResource(R.string.pvb_low_q), 1f, 0.4f..(caps?.lowQMax ?: 3f), 0.05f, "", 2)
        PrefSlider(p, P.KEY_HP_HZ, stringResource(R.string.pvb_hp_hz), 100f, (caps?.hpHzMin ?: 40f)..200f, 5f, "Hz", 0)
        PrefSlider(p, P.KEY_HI_DB, stringResource(R.string.pvb_hi_db), -3f, -9f..3f, 0.5f, "dB", 1)
        PrefSlider(p, P.KEY_HI_HZ, stringResource(R.string.pvb_hi_hz), 4500f, 2000f..8000f, 100f, "Hz", 0)
        if (research) {
            PrefSlider(p, P.KEY_HI_Q, stringResource(R.string.pvb_hi_q), 0.6f, 0.3f..2f, 0.05f, "", 2)
            PrefSlider(p, P.KEY_HS_DB, stringResource(R.string.pvb_hs_db), 0f, -9f..0f, 0.5f, "dB", 1)
            PrefSlider(p, P.KEY_HS_HZ, stringResource(R.string.pvb_hs_hz), 2500f, 1500f..6000f, 100f, "Hz", 0)
        }

        // 출력과 리미터
        RnSectionTitle(stringResource(R.string.rn_adv_section_output))
        PrefSlider(p, P.KEY_OUT_DB, stringResource(R.string.pvb_out_db), -5f, -20f..(caps?.outDbMax ?: 0f), 0.5f, "dB", 1)
        PrefSlider(p, P.KEY_CEIL_DB, stringResource(R.string.pvb_ceil_db), -1f, -6f..(caps?.ceilDbMax ?: 0f), 0.1f, "dBTP", 1)
        PrefSlider(p, P.KEY_RELEASE_MS, stringResource(R.string.pvb_release_ms), 60f, (caps?.releaseMsMin ?: 10f)..500f, 5f, "ms", 0)

        // 볼륨에 따른 저중역
        RnSectionTitle(stringResource(R.string.rn_adv_section_volume))
        PrefSwitch(p, P.KEY_VOL_LINK, stringResource(R.string.pvb_vol_link), false, line = stringResource(R.string.pvb_vol_link_summary))
        if (research) {
            PrefSlider(p, P.KEY_VOL_REF_PCT, stringResource(R.string.pvb_vol_ref_pct), 40f, 10f..100f, 1f, "%", 0)
            PrefSlider(p, P.KEY_VOL_SLOPE, stringResource(R.string.pvb_vol_slope), 0.19f, 0f..0.5f, 0.01f, "dB", 2)
            PrefSlider(p, P.KEY_VOL_CAP_DB, stringResource(R.string.pvb_vol_cap_db), 6f, 3f..9f, 0.5f, "dB", 1)
            PrefSlider(p, P.KEY_VOL_MAX_DB, stringResource(R.string.pvb_vol_max_db), 1f, -3f..3f, 0.5f, "dB", 1)
            PrefSwitch(p, P.KEY_DYN_ON, stringResource(R.string.pvb_dyn_enable), false, line = stringResource(R.string.pvb_dyn_enable_summary))
            PrefSlider(p, P.KEY_DYN_UP_MAX_DB, stringResource(R.string.pvb_dyn_up_max_db), 2f, 0f..4f, 0.5f, "dB", 1)
            PrefSlider(p, P.KEY_DYN_REF_DB, stringResource(R.string.pvb_dyn_ref_db), -30f, -40f..-10f, 1f, "dB", 0)
        }

        // 가상 저음 (the rows below depend on its switch, as the legacy android:dependency did)
        RnSectionTitle(stringResource(R.string.home_tab_bass))
        val vbOn = p.bool(P.KEY_VB_ON, false)
        PrefSwitch(p, P.KEY_VB_ON, stringResource(R.string.pvb_vb_enable), false, line = stringResource(R.string.pvb_vb_enable_summary),
            onChange = { on ->
                // General build: the confirmed first-run notice already carries this warning (one consent).
                if (!on || (PvbBuild.general && PvbBuild.firstRunConfirmed)) {
                    p.put(P.KEY_VB_ON, on)
                } else {
                    vbWarning = true  // stays off until the warning is confirmed
                }
            })
        VbModeRow(p, s, research, vbOn)
        if (research) {
            val model = PvbModels.fromKey(p.string(P.KEY_VB_ALGO, PvbModels.DEFAULT_KEY))
            RnChoiceRow(stringResource(R.string.pvb_vb_algo), PvbModels.models.map { RnChoice(it.key, it.title, it.description) },
                model.key, { p.put(P.KEY_VB_ALGO, it) }, line = "${model.title} · 약 0.15초 지연\n${model.description}",
                enabled = vbOn)
        }
        PrefSlider(p, P.KEY_VB_STRENGTH_DB, stringResource(R.string.pvb_vb_level), P.VB_LEVEL_DEFAULT,
            P.VB_LEVEL_MIN..(caps?.vbLevelMax ?: P.VB_LEVEL_MAX), 1f, "dB", 0, enabled = vbOn, strictStep = true,
            label = { v -> P.clampLevel(v).roundToInt().let { if (it > 0) "+$it dB" else "$it dB" } })
        PrefSwitch(p, P.KEY_VB_VOL_LINK, stringResource(R.string.pvb_vb_vol_link), false,
            line = PvbAdvanced.vbVolLinkLine(context, s), enabled = vbOn)
        if (research && s.vbVolLink) {
            PrefSlider(p, P.KEY_VB_VOL_REF_PCT, stringResource(R.string.pvb_vb_vol_ref_pct), 40f, 20f..70f, 1f, "%", 0,
                line = stringResource(R.string.pvb_vb_vol_ref_pct_summary), enabled = vbOn, strictStep = true)
            PrefSlider(p, P.KEY_VB_VOL_SLOPE, stringResource(R.string.pvb_vb_vol_slope), 0.2f, 0.1f..0.5f, 0.05f, "dB", 2,
                line = stringResource(R.string.pvb_vb_vol_slope_summary), enabled = vbOn, strictStep = true)
            PrefSlider(p, P.KEY_VB_VOL_MAX_DB, stringResource(R.string.pvb_vb_vol_max_db), 12f, 3f..12f, 1f, "dB", 0,
                line = stringResource(R.string.pvb_vb_vol_max_db_summary), enabled = vbOn, strictStep = true)
        }

        // 실험 기능
        RnSectionTitle(stringResource(R.string.pvb_x_header))
        RnParagraph(stringResource(R.string.pvb_x_header_summary))
        PrefSwitch(p, P.KEY_X_SMOOTH, stringResource(R.string.pvb_x_smooth), false, stringResource(R.string.pvb_x_smooth_summary), enabled = vbOn)
        PrefSwitch(p, P.KEY_X_RISE, stringResource(R.string.pvb_x_rise), false, stringResource(R.string.pvb_x_rise_summary), enabled = vbOn)
        PrefSwitch(p, P.KEY_X_S1M, stringResource(R.string.pvb_x_s1m), false, stringResource(R.string.pvb_x_s1m_summary), enabled = vbOn)
        PrefSwitch(p, P.KEY_X_DENSE, stringResource(R.string.pvb_x_dense), false, stringResource(R.string.pvb_x_dense_summary), enabled = vbOn)
        RnNavRow(stringResource(R.string.pvb_x_feedback), stringResource(R.string.pvb_x_feedback_summary)) {
            PvbGeneral.openUrl(context, FEEDBACK_URL)
        }
        RnDivider()
    }
    PrefSwitch(p, P.KEY_MATCH_ON_DISABLE, stringResource(R.string.pvb_match_on_disable), true,
        line = stringResource(R.string.pvb_match_on_disable_summary))

    if (vbWarning) RnDialog(
        stringResource(R.string.pvb_vb_warning_title), stringResource(R.string.pvb_vb_warning),
        confirmLabel = stringResource(R.string.pvb_vb_warning_ok),
        onConfirm = { vbWarning = false; p.put(P.KEY_VB_ON, true) },
        dismissLabel = stringResource(android.R.string.cancel), onDismiss = { vbWarning = false },
    )
}

/** "모드": derived from the model and the level; choosing one writes only those two (the preset is never stored). */
@Composable
private fun VbModeRow(p: RnPrefsFile, s: PvbSettings, research: Boolean, vbOn: Boolean) {
    fun titleRes(key: String) = when (key) {
        PvbModels.PRESET_FULLNESS -> R.string.vb_preset_fullness_title
        PvbModels.PRESET_DEEP -> R.string.vb_preset_deep_title
        else -> R.string.vb_preset_custom_title
    }
    fun descRes(key: String) = when (key) {
        PvbModels.PRESET_FULLNESS -> R.string.vb_preset_fullness_desc
        PvbModels.PRESET_DEEP -> R.string.vb_preset_deep_desc
        else -> R.string.vb_preset_custom_desc
    }
    // "사용자 지정" is listed only with the research tools (the model list is visible then)
    val keys = PvbModels.presets.map { it.key } + if (research) listOf(PvbModels.PRESET_CUSTOM) else emptyList()
    val choices = keys.map { RnChoice(it, stringResource(titleRes(it)), stringResource(descRes(it))) }
    val current = PvbModels.presetFor(PvbModels.fromId(s.vbAlgo)?.key, s.vbLevelDb)?.key ?: PvbModels.PRESET_CUSTOM
    RnChoiceRow(
        stringResource(R.string.pvb_vb_mode), choices, current,
        { key ->
            val preset = PvbModels.presets.firstOrNull { it.key == key } ?: return@RnChoiceRow  // 사용자 지정: nothing to write
            p.prefs.edit().putString(P.KEY_VB_ALGO, preset.modelKey).putFloat(P.KEY_VB_STRENGTH_DB, preset.levelDb).apply()
        },
        line = "${stringResource(titleRes(current))}\n${stringResource(descRes(current))}\n${stringResource(R.string.vb_mode_note)}",
        enabled = vbOn,
    )
}

@Composable
private fun rememberPvbFile(): RnPrefsFile =
    me.timschneeberger.rootlessjamesdsp.ui.rememberPrefsFile(PvbSettings.PREFS_NAME, dsp = false)

private const val FEEDBACK_URL = "https://github.com/ksysh3-dot/rootnote/issues"

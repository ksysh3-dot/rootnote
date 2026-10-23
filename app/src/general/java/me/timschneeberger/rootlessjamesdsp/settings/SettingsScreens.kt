package me.timschneeberger.rootlessjamesdsp.settings

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.util.Patterns
import android.view.ContextThemeWrapper
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import androidx.core.text.HtmlCompat
import com.google.android.material.color.MaterialColors
import com.hippo.unifile.UniFile
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity
import me.timschneeberger.rootlessjamesdsp.api.AutoEqClient
import me.timschneeberger.rootlessjamesdsp.backup.BackupCreatorJob
import me.timschneeberger.rootlessjamesdsp.backup.BackupRestoreService
import me.timschneeberger.rootlessjamesdsp.delegates.ThemingDelegate
import me.timschneeberger.rootlessjamesdsp.home.appThemeChoice
import me.timschneeberger.rootlessjamesdsp.interop.BenchmarkManager
import me.timschneeberger.rootlessjamesdsp.model.preference.AppTheme
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceRow
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnEndSpace
import me.timschneeberger.rootlessjamesdsp.ui.RnInputDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnNote
import me.timschneeberger.rootlessjamesdsp.ui.RnNumberInput
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnSliderRow
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.pressScale
import me.timschneeberger.rootlessjamesdsp.ui.rememberAppPrefs
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.extensions.AssetManagerExtensions.installPrivateAssets
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.sendLocalBroadcast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasProjectMediaAppOp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.isDynamicColorAvailable
import java.util.Locale

/*
 * The settings pages (RnSettingsActivity.Route), built from the shared kit (ui/) after the legacy Preference XML:
 * same rows in the same order, the same keys in the same files ("application"), the same side effects. Rows that the
 * general build never showed (root-only categories, Google Play, crash reports) are left out.
 */

@Composable
fun SettingsPage(route: RnSettingsActivity.Route, host: RnSettingsActivity) {
    when (route) {
        RnSettingsActivity.Route.ROOT -> RootPage(host)
        RnSettingsActivity.Route.APPEARANCE -> AppearancePage(host)
        RnSettingsActivity.Route.AUDIO -> AudioPage(host)
        RnSettingsActivity.Route.PROFILES -> ProfilesPage(host)
        RnSettingsActivity.Route.TROUBLESHOOT -> TroubleshootPage(host)
        RnSettingsActivity.Route.LIMITATIONS -> LimitationsPage(host)
        RnSettingsActivity.Route.BACKUP -> BackupPage(host)
        RnSettingsActivity.Route.MISC -> MiscPage(host)
        RnSettingsActivity.Route.ABOUT -> AboutPage(host)
    }
}

/** Choices from a string array and its values array (a legacy ListPreference). */
@Composable
private fun choices(entries: Int, values: Int): List<RnChoice<String>> {
    val e = stringArrayResource(entries)
    val v = stringArrayResource(values)
    return e.indices.map { RnChoice(v[it], e[it]) }
}

// ------------------------------------------------------------------------------------------------ root

@Composable
private fun RootPage(host: RnSettingsActivity) {
    RnPage(stringResource(R.string.title_activity_settings), onBack = host::finish) {
        RnNavRow(stringResource(R.string.appearance_section_header), stringResource(R.string.appearance_summary)) { host.open(RnSettingsActivity.Route.APPEARANCE) }
        RnNavRow(stringResource(R.string.audio_format_header), stringResource(R.string.audio_format_summary)) { host.open(RnSettingsActivity.Route.AUDIO) }
        RnNavRow(stringResource(R.string.profiles_section_header), stringResource(R.string.profiles_summary)) { host.open(RnSettingsActivity.Route.PROFILES) }
        RnNavRow(stringResource(R.string.troubleshooting), stringResource(R.string.troubleshooting_summary)) { host.open(RnSettingsActivity.Route.TROUBLESHOOT) }
        RnNavRow(stringResource(R.string.backup_settings), stringResource(R.string.backup_settings_summary)) { host.open(RnSettingsActivity.Route.BACKUP) }
        RnNavRow(stringResource(R.string.misc_settings), stringResource(R.string.misc_settings_summary)) { host.open(RnSettingsActivity.Route.MISC) }
        RnBand()
        RnNavRow(stringResource(R.string.about_settings), stringResource(R.string.about_settings_summary)) { host.open(RnSettingsActivity.Route.ABOUT) }
        RnEndSpace()
    }
}

// ------------------------------------------------------------------------------------------------ appearance

@Composable
private fun AppearancePage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val kMode = stringResource(R.string.key_appearance_theme_mode)
    val kBlack = stringResource(R.string.key_appearance_pure_black)
    val kIcons = stringResource(R.string.key_appearance_show_icons)
    val kNav = stringResource(R.string.key_appearance_nav_hide)
    val mode = app.string(kMode, stringResource(R.string.default_appearance_theme_mode))
    RnPage(stringResource(R.string.appearance_section_header), onBack = host::finish) {
        RnSectionTitle(stringResource(R.string.appearance_title))
        RnChoiceRow(stringResource(R.string.appearance_theme_mode), choices(R.array.theme_modes, R.array.theme_modes_values), mode,
            onSelect = { app.put(kMode, it) })
        ThemePicker(host)
        // pure black only means something in dark mode (hidden when dark mode is off, as before)
        if (mode != "1") RnSwitchRow(stringResource(R.string.appearance_pure_black_mode),
            app.bool(kBlack, false), { app.put(kBlack, it) })
        RnSwitchRow(stringResource(R.string.appearance_show_icons), app.bool(kIcons, true), { app.put(kIcons, it) })
        RnBand()
        RnSectionTitle(stringResource(R.string.appearance_navigation_title))
        RnSwitchRow(stringResource(R.string.appearance_nav_hide), app.bool(kNav, false), { app.put(kNav, it) })
        RnEndSpace()
    }
}

/** The colours a theme preview draws: page, bar, container, primary (read from that theme, like ThemesPreferenceAdapter). */
private data class ThemeSwatch(val theme: AppTheme, val surface: Color, val bar: Color, val container: Color, val primary: Color)

private fun swatch(context: Context, theme: AppTheme, black: Boolean): ThemeSwatch {
    var ctx: Context = context
    for (id in ThemingDelegate.getThemeResIds(theme, black)) ctx = ContextThemeWrapper(ctx, id)
    fun c(attr: Int, fb: Int) = Color(MaterialColors.getColor(ctx, attr, fb))
    return ThemeSwatch(
        theme,
        surface = c(com.google.android.material.R.attr.colorSurface, 0xFFFFFFFF.toInt()),
        bar = c(com.google.android.material.R.attr.colorOnSurface, 0xFF1A1C20.toInt()).copy(alpha = 0.85f),
        container = c(com.google.android.material.R.attr.colorSecondaryContainer, 0xFFE3E6E8.toInt()),
        primary = c(com.google.android.material.R.attr.colorPrimary, 0xFF0B7A7A.toInt()),
    )
}

/**
 * The app theme picker: a horizontal row of small previews (radius 14), the chosen one outlined in its own primary
 * colour and named in bold. Picking one recreates every open screen (BaseActivity), as before.
 */
@Composable
private fun ThemePicker(host: RnSettingsActivity) {
    val c = LocalRn.current
    val app = rememberAppPrefs()
    val key = stringResource(R.string.key_appearance_app_theme)
    val context = LocalContext.current
    val (current, black) = remember(context) { appThemeChoice(context) }
    val list = remember(context) {
        AppTheme.choices(general = true, dynamicAvailable = isDynamicColorAvailable).map { swatch(host, it, black) }
    }
    val selectedText = stringResource(R.string.rn_selected)
    Column(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        Text(stringResource(R.string.appearance_app_theme), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
            modifier = Modifier.padding(horizontal = 16.dp))
        Row(
            Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 10.dp)
                .selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            for (s in list) {
                val on = s.theme == current
                val interaction = remember { MutableInteractionSource() }
                val scale = pressScale(interaction, true)
                val label = stringResource(s.theme.titleResId ?: R.string.theme_default)
                Column(
                    Modifier.width(92.dp)
                        .selectable(selected = on, interactionSource = interaction, indication = null, role = Role.RadioButton) {
                            if (!on) app.put(key, s.theme.name)
                        }
                        .semantics { if (on) stateDescription = selectedText }
                        .padding(4.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Box(
                        Modifier.graphicsLayer { scaleX = scale; scaleY = scale }.size(width = 84.dp, height = 132.dp)
                            .border(if (on) 3.dp else 1.dp, if (on) s.primary else c.chipBorder, RoundedCornerShape(14.dp))
                            .padding(if (on) 3.dp else 1.dp)
                            .background(s.surface, RoundedCornerShape(12.dp))
                            .padding(8.dp),
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Box(Modifier.size(width = 44.dp, height = 8.dp).background(s.bar, CircleShape))
                            Box(Modifier.fillMaxWidth().height(48.dp).background(s.container, RoundedCornerShape(8.dp)))
                            Box(Modifier.size(width = 52.dp, height = 6.dp).background(s.bar.copy(alpha = 0.35f), CircleShape))
                        }
                        Row(Modifier.align(Alignment.BottomStart), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(14.dp).background(s.primary, CircleShape))
                            Spacer(Modifier.width(6.dp))
                            Box(Modifier.size(width = 34.dp, height = 10.dp).background(s.primary.copy(alpha = 0.35f), CircleShape))
                        }
                    }
                    Text(label, color = if (on) c.textPrimary else c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
                        fontWeight = if (on) FontWeight.Bold else FontWeight.Normal, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(top = 6.dp))
                }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ audio processing

@Composable
private fun AudioPage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val kEnc = stringResource(R.string.key_audioformat_encoding)
    val kBuf = stringResource(R.string.key_audioformat_buffersize)
    val defBuf = host.resources.getInteger(R.integer.default_audioformat_buffersize).toFloat()
    val unit = stringResource(R.string.audio_format_buffer_size_unit)
    var benchmark by remember { mutableStateOf(BenchmarkManager.hasBenchmarksCached()) }
    var editBuffer by remember { mutableStateOf(false) }
    fun hardReboot() = host.sendLocalBroadcast(Intent(Constants.ACTION_SERVICE_HARD_REBOOT_CORE))
    fun setBuffer(v: Float) {
        if (v <= 1024f) host.toast(R.string.audio_format_buffer_size_warning_low_value, false)
        app.put(kBuf, v)
        hardReboot()
    }
    fun runBenchmark() = BenchmarkManager.runBenchmarks(host) {
        CoroutineScope(Dispatchers.Main).launch { benchmark = BenchmarkManager.hasBenchmarksCached() }
    }
    RnPage(stringResource(R.string.audio_format_header), onBack = host::finish) {
        RnSectionTitle(stringResource(R.string.audio_format_section_header))
        RnChoiceRow(stringResource(R.string.audio_format_encoding),
            choices(R.array.audio_format_encodings, R.array.audio_format_encodings_values),
            app.string(kEnc, stringResource(R.string.default_audioformat_encoding)),
            onSelect = { app.put(kEnc, it); hardReboot() })
        val buf = app.float(kBuf, defBuf)
        RnSliderRow(
            title = stringResource(R.string.audio_format_buffer_size), value = buf, range = 128f..16384f, step = 128f,
            valueText = { "${it.toInt()}$unit" }, onChange = ::setBuffer, default = defBuf, onEdit = { editBuffer = true },
        )
        RnBand()
        RnSectionTitle(stringResource(R.string.audio_format_optimization_header))
        RnSwitchRow(stringResource(R.string.audio_format_optimization_benchmark), benchmark, {
            if (it) runBenchmark() else { BenchmarkManager.clearBenchmarks(); benchmark = false }
        }, line = stringResource(R.string.audio_format_optimization_benchmark_summary))
        RnNavRow(stringResource(R.string.audio_format_optimization_refresh), enabled = benchmark, chevron = false) { runBenchmark() }
        RnEndSpace()
    }
    if (editBuffer) RnNumberInput(stringResource(R.string.audio_format_buffer_size), app.float(kBuf, defBuf), 128f..16384f, 128f,
        unit.trim(), onDone = { setBuffer(it); editBuffer = false }, onDismiss = { editBuffer = false })
}

// ------------------------------------------------------------------------------------------------ device profiles

@Composable
private fun ProfilesPage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val key = stringResource(R.string.key_device_profiles_enable)
    var info by remember { mutableStateOf(false) }
    val on = app.bool(key, false)
    RnPage(stringResource(R.string.profiles_section_header), onBack = host::finish) {
        RnSwitchRow(stringResource(R.string.profiles_enable), on, { app.put(key, it) },
            line = stringResource(if (on) R.string.profiles_enable_summary_on else R.string.profiles_enable_summary_off))
        RnNavRow(stringResource(R.string.profiles_info_title), stringResource(R.string.profiles_info), chevron = false) { info = true }
        RnNote(stringResource(R.string.profiles_manage_hint))
        RnEndSpace()
    }
    if (info) RnDialog(stringResource(R.string.profiles_info_title), stringResource(R.string.profiles_info_content), onConfirm = { info = false })
}

// ------------------------------------------------------------------------------------------------ troubleshooting

@Composable
private fun TroubleshootPage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val kSuspend = stringResource(R.string.key_powersave_suspend)
    val kHold = stringResource(R.string.key_powersave_hold)
    val kDeep = stringResource(R.string.key_powersave_deep)
    val kMethod = stringResource(R.string.key_session_detection_method)
    val kPoll = stringResource(R.string.key_session_continuous_polling)
    val kRate = stringResource(R.string.key_session_continuous_polling_rate)
    val kLoss = stringResource(R.string.key_session_loss_ignore)
    val kProblem = stringResource(R.string.key_session_app_problem_ignore)
    val kRestricted = stringResource(R.string.key_session_exclude_restricted)
    var lossWarning by remember { mutableStateOf(false) }
    var editRate by remember { mutableStateOf(false) }
    val suspend = app.bool(kSuspend, true)
    val poll = app.bool(kPoll, false)
    RnPage(stringResource(R.string.troubleshooting), onBack = host::finish) {
        RnSectionTitle(stringResource(R.string.troubleshooting_docs))
        RnNavRow(stringResource(R.string.troubleshooting_view_limitations), stringResource(R.string.troubleshooting_view_limitations_summary)) {
            host.open(RnSettingsActivity.Route.LIMITATIONS)
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.troubleshooting_actions))
        RnNavRow(stringResource(R.string.troubleshooting_notification_access), stringResource(R.string.troubleshooting_notification_access_summary)) {
            host.openNotificationAccess()
        }
        RnNavRow(stringResource(R.string.troubleshooting_dump), stringResource(R.string.troubleshooting_dump_summary), chevron = false) {
            host.shareDump()
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.powersave))
        RnSwitchRow(stringResource(R.string.powersave_suspend), suspend, { app.put(kSuspend, it) },
            line = stringResource(if (suspend) R.string.powersave_suspend_on else R.string.powersave_suspend_off))
        val holdChoices = choices(R.array.powersave_hold_entries, R.array.powersave_hold_values)
        val hold = app.string(kHold, stringResource(R.string.default_powersave_hold))
        RnChoiceRow(stringResource(R.string.powersave_hold), holdChoices, hold, onSelect = { app.put(kHold, it) },
            line = String.format(stringResource(R.string.powersave_hold_summary), holdChoices.firstOrNull { it.value == hold }?.label ?: hold),
            enabled = suspend, valueInLine = false)
        val deepChoices = choices(R.array.powersave_deep_entries, R.array.powersave_deep_values)
        val deep = app.string(kDeep, stringResource(R.string.default_powersave_deep))
        RnChoiceRow(stringResource(R.string.powersave_deep), deepChoices, deep, onSelect = { app.put(kDeep, it) },
            line = String.format(stringResource(R.string.powersave_deep_summary), deepChoices.firstOrNull { it.value == deep }?.label ?: deep),
            enabled = suspend)
        RnBand()
        RnSectionTitle(stringResource(R.string.session_detection_header))
        RnChoiceRow(stringResource(R.string.session_detection_method),
            choices(R.array.session_detection_methods, R.array.session_detection_methods_values),
            app.string(kMethod, stringResource(R.string.default_session_detection_method)), onSelect = { app.put(kMethod, it) },
            valueInLine = true)
        RnSwitchRow(stringResource(R.string.session_continuous_polling), poll, { app.put(kPoll, it) },
            line = stringResource(if (poll) R.string.session_continuous_polling_on else R.string.session_continuous_polling_off))
        RnNavRow(stringResource(R.string.session_continuous_polling_rate),
            app.string(kRate, stringResource(R.string.default_session_continuous_polling_rate)), enabled = poll, chevron = false) {
            editRate = true
        }
        val loss = app.bool(kLoss, false)
        RnSwitchRow(stringResource(R.string.session_loss_ignore), loss, {
            app.put(kLoss, it)
            if (it) lossWarning = true
        }, line = stringResource(if (loss) R.string.session_loss_ignore_on else R.string.session_loss_ignore_off))
        val problem = app.bool(kProblem, false)
        // the legacy row reuses the session-loss summaries
        RnSwitchRow(stringResource(R.string.session_app_problem_ignore), problem, { app.put(kProblem, it) },
            line = stringResource(if (problem) R.string.session_loss_ignore_on else R.string.session_loss_ignore_off))
        val restricted = app.bool(kRestricted, true)
        RnSwitchRow(stringResource(R.string.session_exclude_restricted), restricted, { app.put(kRestricted, it) },
            line = stringResource(if (restricted) R.string.session_exclude_restricted_on else R.string.session_exclude_restricted_off))
        RnEndSpace()
    }
    if (lossWarning) RnDialog(stringResource(R.string.warning), stringResource(R.string.session_loss_ignore_warning),
        onConfirm = { lossWarning = false })
    if (editRate) RnInputDialog(
        title = stringResource(R.string.session_continuous_polling_rate),
        initial = app.string(kRate, stringResource(R.string.default_session_continuous_polling_rate)),
        number = true, suffix = "ms",
        validate = { if (it.toIntOrNull()?.takeIf { v -> v > 0 } == null) host.getString(R.string.slider_dialog_format_error) else null },
        onDone = { app.put(kRate, it); editRate = false }, onDismiss = { editRate = false },
    )
}

/** "기술적 한계": the six cards of the upstream onboarding, as notes. */
@Composable
private fun LimitationsPage(host: RnSettingsActivity) {
    val items = listOf(
        R.string.limit_session_control_conflict_title to R.string.limit_session_control_conflict,
        R.string.limit_unsupported_apps_title to R.string.limit_unsupported_apps,
        R.string.limit_hw_accel_title to R.string.limit_hw_accel,
        R.string.limit_detect_delay_title to R.string.limit_detect_delay,
        R.string.limit_latency_title to R.string.limit_latency,
        R.string.limit_tested_devices_title to R.string.limit_tested_devices,
    )
    val c = LocalRn.current
    RnPage(stringResource(R.string.troubleshooting_view_limitations), onBack = host::finish) {
        for ((t, b) in items) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(t), color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
                val body = HtmlCompat.fromHtml(stringResource(b), HtmlCompat.FROM_HTML_MODE_COMPACT).toString().trim()
                Text(body, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            }
        }
        RnEndSpace()
    }
}

// ------------------------------------------------------------------------------------------------ backup

@Composable
private fun BackupPage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val kFreq = stringResource(R.string.key_backup_frequency)
    val kLoc = stringResource(R.string.key_backup_location)
    val kMax = stringResource(R.string.key_backup_maximum)
    // as before: a location without a kept write permission is forgotten, and automatic backups switch off with it
    remember(host) {
        val loc = app.prefs.getString(kLoc, "") ?: ""
        val kept = host.contentResolver.persistedUriPermissions.any { it.uri == loc.toUri() && it.isWritePermission }
        if (!kept && loc.isNotEmpty()) app.put(kLoc, "")
        if ((app.prefs.getString(kLoc, "") ?: "").isBlank()) app.put(kFreq, host.getString(R.string.default_backup_frequency))
        true
    }
    host.backupLocationTick
    val loc = app.string(kLoc, "")
    val locText = if (loc.isBlank()) stringResource(R.string.value_not_set)
        else (UniFile.fromUri(host, loc.toUri())?.filePath ?: loc) + "/automatic"
    RnPage(stringResource(R.string.backup_settings), onBack = host::finish) {
        RnSectionTitle(stringResource(R.string.backup_manual_backup))
        RnNavRow(stringResource(R.string.backup_create), stringResource(R.string.backup_create_summary), chevron = false) { host.createBackup() }
        RnNavRow(stringResource(R.string.backup_restore), stringResource(R.string.backup_restore_summary), chevron = false) { host.loadBackup() }
        RnBand()
        RnSectionTitle(stringResource(R.string.backup_automatic_backup))
        RnChoiceRow(stringResource(R.string.backup_frequency), choices(R.array.backup_frequency, R.array.backup_frequency_values),
            app.string(kFreq, stringResource(R.string.default_backup_frequency)), onSelect = { v ->
                app.put(kFreq, v)
                val hours = v.toIntOrNull() ?: 0
                BackupCreatorJob.setupTask(host, hours)
                if (hours > 0 && app.prefs.getString(kLoc, "").isNullOrBlank()) host.pickBackupLocation()
            })
        RnNavRow(stringResource(R.string.backup_location), locText) { host.pickBackupLocation() }
        RnChoiceRow(stringResource(R.string.backup_maximum), choices(R.array.backup_maximum, R.array.backup_maximum),
            app.string(kMax, stringResource(R.string.default_backup_maximum)), onSelect = { app.put(kMax, it) })
        RnNote(stringResource(R.string.backup_compat_info))
        RnEndSpace()
    }
    host.restoreUri?.let { uri ->
        RnChoiceSheet(
            stringResource(R.string.backup_restore_mode_title),
            listOf(RnChoice(false, stringResource(R.string.backup_restore_mode_clean)),
                RnChoice(true, stringResource(R.string.backup_restore_mode_dirty))),
            selected = null, onDismiss = { host.restoreUri = null },
        ) { dirty ->
            BackupRestoreService.start(host, uri, dirty)
            host.restoreUri = null
        }
    }
}

// ------------------------------------------------------------------------------------------------ misc

@Composable
private fun MiscPage(host: RnSettingsActivity) {
    val app = rememberAppPrefs()
    val kRecents = stringResource(R.string.key_exclude_app_from_recents)
    val kAuto = stringResource(R.string.key_autostart_prompt_at_boot)
    val kUrl = stringResource(R.string.key_network_autoeq_api_url)
    val defUrl = stringResource(R.string.default_network_autoeq_api_url)
    var repaired by remember { mutableStateOf(false) }
    var editUrl by remember { mutableStateOf(false) }
    var urlFailure by remember { mutableStateOf<String?>(null) }
    host.resumeTick
    val skipPrompt = host.hasProjectMediaAppOp()
    val autoStart = skipPrompt && Settings.canDrawOverlays(host)
    val ok = colorResource(R.color.rn_badge_measured_text)
    val warn = colorResource(R.color.rn_warn_text)
    RnPage(stringResource(R.string.misc_settings), onBack = host::finish) {
        RnSectionTitle(stringResource(R.string.app_behavior))
        val recents = app.bool(kRecents, false)
        RnSwitchRow(stringResource(R.string.exclude_app_from_recents), recents, { app.put(kRecents, it) },
            line = stringResource(if (recents) R.string.exclude_app_from_recents_on else R.string.exclude_app_from_recents_off))
        val auto = app.bool(kAuto, true)
        RnSwitchRow(
            stringResource(if (autoStart) R.string.autostart_service_at_boot else R.string.autostart_prompt_at_boot), auto,
            { app.put(kAuto, it) },
            line = stringResource(when {
                autoStart && auto -> R.string.autostart_service_at_boot_on
                autoStart -> R.string.autostart_service_at_boot_off
                auto -> R.string.autostart_prompt_at_boot_on
                else -> R.string.autostart_prompt_at_boot_off
            }),
        )
        RnBand()
        RnSectionTitle(stringResource(R.string.assets))
        RnNavRow(stringResource(R.string.troubleshooting_repair_assets), stringResource(R.string.troubleshooting_repair_assets_summary), chevron = false) {
            host.assets.installPrivateAssets(host, force = true)
            repaired = true
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.misc_permission_header))
        RnNavRow(stringResource(R.string.misc_permission_skip_prompt),
            value = stringResource(if (skipPrompt) R.string.permission_allowed else R.string.permission_not_allowed),
            valueColor = if (skipPrompt) ok else warn, onClick = null)
        RnNavRow(stringResource(R.string.misc_permission_auto_start),
            value = stringResource(if (autoStart) R.string.permission_allowed else R.string.permission_not_allowed),
            valueColor = if (autoStart) ok else warn, onClick = null)
        if (!skipPrompt || !autoStart) RnNavRow(stringResource(R.string.misc_permission_restart_setup),
            stringResource(R.string.misc_permission_restart_setup_summary)) {
            host.startActivity(Intent(host, OnboardingActivity::class.java).putExtra(OnboardingActivity.EXTRA_ROOTLESS_REDO_ADB_SETUP, true))
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.network_services))
        RnNavRow(stringResource(R.string.network_autoeq_api_url), app.string(kUrl, defUrl), chevron = false) { editUrl = true }
        RnEndSpace()
    }
    if (repaired) RnDialog(stringResource(R.string.success), stringResource(R.string.troubleshooting_repair_assets_success),
        onConfirm = { repaired = false })
    if (editUrl) RnInputDialog(
        title = stringResource(R.string.network_autoeq_api_url), initial = app.string(kUrl, defUrl),
        validate = { if (!Patterns.WEB_URL.matcher(it.lowercase(Locale.ROOT)).matches()) host.getString(R.string.network_invalid_url) else null },
        onDone = { url ->
            editUrl = false
            try {
                // as before: the URL is kept at once, then tested; a failed test offers the default back
                val client = AutoEqClient(host, 5, url)
                app.put(kUrl, url)
                host.toast(R.string.network_autoeq_conntest_running)
                client.queryProfiles("conntest",
                    onResponse = { _, _ -> host.toast(R.string.network_autoeq_conntest_done, false) },
                    onFailure = { error -> urlFailure = error })
            } catch (_: IllegalArgumentException) {
                host.toast(R.string.network_invalid_url)
            }
        },
        onDismiss = { editUrl = false },
    )
    urlFailure?.let { error ->
        RnDialog(stringResource(R.string.network_autoeq_conntest_fail), stringResource(R.string.network_autoeq_conntest_fail_summary, error),
            confirmLabel = stringResource(R.string.yes), onConfirm = { app.put(kUrl, defUrl); urlFailure = null },
            dismissLabel = stringResource(R.string.no), onDismiss = { urlFailure = null })
    }
}

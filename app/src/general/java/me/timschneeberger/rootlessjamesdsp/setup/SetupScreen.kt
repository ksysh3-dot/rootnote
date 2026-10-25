package me.timschneeberger.rootlessjamesdsp.setup

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.booleanResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.LocalRnReduceMotion
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnButtonRow
import me.timschneeberger.rootlessjamesdsp.ui.RnCheckMark
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnEndSpace
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnOutlineButton
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.rememberAppPrefs
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.ui.RnMotion
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition

/**
 * The setup steps (see [RnSetupActivity]): one page at a time, sliding left or right; the top bar's back goes to the
 * previous step or leaves; the bottom button goes on ("다음", or "마침" on the last step). The method page has no
 * bottom button: choosing a method goes on.
 */
@Composable
fun SetupScreen(host: RnSetupActivity) {
    host.resumeTick                       // installed / exempt states are re-read on return
    val page = host.page
    val title = stringResource(when (page) {
        RnSetupActivity.PAGE_METHOD_SELECT -> R.string.onboarding_methods_title
        RnSetupActivity.PAGE_ADB_SETUP ->
            if (host.method == RnSetupActivity.Method.Adb) R.string.onboarding_adb_adb_title else R.string.onboarding_adb_shizuku_title
        RnSetupActivity.PAGE_RUNTIME_PERMISSIONS -> R.string.onboarding_perm_title
        else -> R.string.firstweek_battery_title
    })
    val reduce = LocalRnReduceMotion.current
    RnPage(
        title, onBack = host::back, scroll = false,
        bottomBar = {
            if (page != RnSetupActivity.PAGE_METHOD_SELECT) RnButtonRow {
                RnFilledButton(stringResource(if (host.isLastPage) R.string.onboarding_finish else R.string.onboarding_next),
                    Modifier.weight(1f), onClick = host::next)
            }
        },
    ) {
        AnimatedContent(
            targetState = page,
            transitionSpec = {
                val dir = if (host.forward) 1 else -1
                if (reduce) EnterTransition.None togetherWith ExitTransition.None
                else (slideInHorizontally(RnMotion.Seed.enter()) { it / 4 * dir } + fadeIn(RnMotion.Seed.enter(250))) togetherWith
                    (slideOutHorizontally(RnMotion.Seed.exit()) { -it / 4 * dir } + fadeOut(RnMotion.Seed.exit()))
            },
            label = "setupPage",
        ) { shown ->
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
                when (shown) {
                    RnSetupActivity.PAGE_METHOD_SELECT -> MethodPage(host)
                    RnSetupActivity.PAGE_ADB_SETUP -> AdbPage(host)
                    RnSetupActivity.PAGE_RUNTIME_PERMISSIONS -> PermissionsPage()
                    else -> BatteryPage(host)
                }
                RnEndSpace()
            }
        }
    }

    host.alert?.let { (t, m) -> RnDialog(stringResource(t), stringResource(m), onConfirm = { host.alert = null }) }
    if (host.shizukuSources) RnDialog(
        stringResource(R.string.firstweek_shizuku_sources_title), stringResource(R.string.firstweek_shizuku_sources),
        confirmLabel = stringResource(R.string.firstweek_shizuku_play),
        onConfirm = { host.shizukuSources = false; host.openPlayStore() },
        neutralLabel = stringResource(R.string.firstweek_shizuku_github),
        onNeutral = { host.shizukuSources = false; host.openShizukuReleases() },
        dismissLabel = stringResource(android.R.string.cancel), onDismiss = { host.shizukuSources = false },
    )
    if (host.shizukuTooOld) RnDialog(
        stringResource(R.string.onboarding_adb_shizuku_grant_fail_version_title),
        stringResource(R.string.onboarding_adb_shizuku_grant_fail_version),
        confirmLabel = stringResource(R.string.update),
        onConfirm = { host.shizukuTooOld = false; host.shizukuSources = true },
        dismissLabel = stringResource(android.R.string.ok), onDismiss = { host.shizukuTooOld = false },
    )
}

/** Shizuku (recommended, with what it is and a button to open or get it) or ADB from a computer. */
@Composable
private fun MethodPage(host: RnSetupActivity) {
    val supported = SdkCheck.isQ
    val shizukuTitle = stringResource(R.string.onboarding_methods_shizuku_title) +
        if (supported) "" else " (${stringResource(R.string.onboarding_methods_unsupported_append)})"
    RnNavRow(shizukuTitle, stringResource(R.string.onboarding_methods_rootless_shizuku), enabled = supported) {
        host.chooseMethod(RnSetupActivity.Method.Shizuku)
    }
    if (supported) {
        RnParagraph(stringResource(R.string.firstweek_shizuku_explain))
        Box(Modifier.padding(horizontal = 8.dp)) {
            RnButtonRow {
                RnOutlineButton(stringResource(if (host.shizukuInstalled) R.string.firstweek_shizuku_open else R.string.firstweek_shizuku_get),
                    Modifier.weight(1f), onClick = host::openShizuku)
            }
        }
    }
    RnBand()
    RnNavRow(stringResource(R.string.onboarding_methods_adb_title), stringResource(R.string.onboarding_methods_rootless_adb)) {
        host.chooseMethod(RnSetupActivity.Method.Adb)
    }
}

/** The numbered steps of the Shizuku or the ADB setup (legacy updateSetupInstructions). */
@Composable
private fun AdbPage(host: RnSetupActivity) {
    val pkg = host.packageName
    RnParagraph(stringResource(R.string.onboarding_adb_caption))
    if (host.method != RnSetupActivity.Method.Adb) {
        val installed = host.shizukuInstalled
        val running = host.shizukuAlive && installed
        Step("1", installed, null, stringResource(R.string.onboarding_adb_shizuku_install_instruction),
            stringResource(if (installed) R.string.onboarding_adb_shizuku_install_button_done else R.string.onboarding_adb_shizuku_install_button),
            buttonEnabled = !installed) { host.shizukuSources = true }
        Step("2", running, null, stringResource(R.string.onboarding_adb_shizuku_open_instruction),
            stringResource(if (running) R.string.onboarding_adb_shizuku_open_button_done else R.string.onboarding_adb_shizuku_open_button),
            buttonEnabled = !running, onButton = host::openShizuku)
        Step("3", false, null, stringResource(R.string.onboarding_adb_shizuku_grant_instruction),
            stringResource(R.string.onboarding_adb_shizuku_grant_button), onButton = host::grantViaShizuku)
    } else {
        Step("1", false, null, stringResource(R.string.onboarding_adb_manual_step1),
            stringResource(R.string.onboarding_adb_manual_step1_button), onButton = host::openDeveloperSettings)
        Step("2", false, null, stringResource(R.string.onboarding_adb_manual_step2))
        Step("3", false, null, stringResource(R.string.onboarding_adb_manual_step3))
        Step("4", false, null, stringResource(R.string.onboarding_adb_manual_step4, pkg), selectable = true)
        Step("5", false, null, stringResource(R.string.onboarding_adb_manual_step5b_required, pkg), selectable = true)
        Step("i", false, null, stringResource(R.string.onboarding_adb_manual_step5c, pkg), selectable = true)
        Step("6", false, null, stringResource(R.string.onboarding_adb_manual_step5))
    }
}

/** What the next button asks for: microphone (capture), notifications (13+), and the per-start capture consent. */
@Composable
private fun PermissionsPage() {
    RnParagraph(stringResource(R.string.onboarding_perm_caption))
    if (!BuildConfig.FOSS_ONLY) {
        val app = rememberAppPrefs()
        val key = stringResource(R.string.key_share_crash_reports)
        val default = booleanResource(R.bool.default_share_crash_reports)
        RnSwitchRow(stringResource(R.string.onboarding_perm_diag), app.bool(key, default), { app.put(key, it) },
            line = stringResource(R.string.onboarding_perm_diag_caption))
    }
    RnNavRow(stringResource(R.string.onboarding_perm_microphone_title), stringResource(R.string.onboarding_perm_microphone_caption), onClick = null)
    if (SdkCheck.isTiramisu)
        RnNavRow(stringResource(R.string.onboarding_perm_notification_title), stringResource(R.string.onboarding_perm_notification_caption), onClick = null)
    RnNavRow(stringResource(R.string.onboarding_perm_cast_title), stringResource(R.string.firstweek_capture_consent), onClick = null)
}

/** Battery: the exemption request (done when exempt) and the One UI settings. */
@Composable
private fun BatteryPage(host: RnSetupActivity) {
    RnParagraph(stringResource(R.string.firstweek_battery_caption))
    val exempt = host.batteryExempt
    Step(null, exempt, stringResource(R.string.firstweek_battery_request_title), stringResource(R.string.firstweek_battery_request_body),
        stringResource(if (exempt) R.string.firstweek_battery_request_done else R.string.firstweek_battery_request_button),
        buttonEnabled = !exempt, onButton = host::requestBatteryExemption)
    Step(null, false, stringResource(R.string.firstweek_battery_oneui_title), stringResource(R.string.firstweek_battery_oneui_body),
        stringResource(R.string.firstweek_battery_oneui_button), onButton = host::openBatterySettings)
}

/**
 * One step: a numbered mark (a check when [done]; none when [mark] is null and the title carries the number), an
 * optional title, the instruction (selectable when it holds a command) and an optional button.
 */
@Composable
private fun Step(
    mark: String?, done: Boolean, title: String?, body: String,
    button: String? = null, buttonEnabled: Boolean = true, selectable: Boolean = false, onButton: () -> Unit = {},
) {
    val c = LocalRn.current
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        if (mark != null || done) Box(
            Modifier.size(28.dp).clearAndSetSemantics {}.then(
                if (done) Modifier.background(c.fill, CircleShape) else Modifier.border(1.5.dp, c.textSecondary, CircleShape)),
            contentAlignment = Alignment.Center,
        ) {
            if (done) RnCheckMark(c.onFill, 18.dp)
            else Text(mark ?: "", color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, fontWeight = FontWeight.Bold)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (title != null) Text(title, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            if (selectable) SelectionContainer { Text(body, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp) }
            else Text(body, color = c.textPrimary, fontSize = 15.sp, lineHeight = 21.sp)
            if (button != null) Row { RnOutlineButton(button, enabled = buttonEnabled, onClick = onButton) }
        }
    }
}

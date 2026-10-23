package me.timschneeberger.rootlessjamesdsp.advanced

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.delay
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.exclusions.RnExclusionsActivity
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain
import me.timschneeberger.rootlessjamesdsp.pvb.PvbAnalyzerCard
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbRuntime
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.PvbStatusText
import me.timschneeberger.rootlessjamesdsp.settings.RnSettingsActivity
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnEndSpace
import me.timschneeberger.rootlessjamesdsp.ui.RnIconAction
import me.timschneeberger.rootlessjamesdsp.ui.RnMultiChoiceDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnNote
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.RnTextAction
import me.timschneeberger.rootlessjamesdsp.ui.rememberAppPrefs
import me.timschneeberger.rootlessjamesdsp.ui.rememberPrefsFile
import me.timschneeberger.rootlessjamesdsp.utils.ProfileManager
import me.timschneeberger.rootlessjamesdsp.utils.RoutingObserver
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast

/**
 * The advanced screen, top to bottom as the legacy DspFragment: the audio service switch and the live status, the
 * PVB settings, the research tools (after the unlock), the chain note, the upstream device profiles (when on in
 * settings), then the JamesDSP modules with their seal notes. Top bar: presets, settings and "더보기" (excluded apps,
 * revert).
 */
@Composable
fun AdvancedScreen(host: RnAdvancedActivity) {
    val app = rememberAppPrefs()
    val showIcons = app.bool(host.getString(R.string.key_appearance_show_icons), true)
    val profilesOn = app.bool(host.getString(R.string.key_device_profiles_enable), false)
    val pvb = rememberPrefsFile(PvbSettings.PREFS_NAME, dsp = false)
    host.statusTick
    host.resumeTick
    val s = pvb.read { PvbSettings.load(it) }
    // the same conditions as the audio path (PvbController): PVB in the path, and PVB processing on this route
    val inPath = JdspChain.pvbInPath(s, abActive = false)
    val sealed = JdspChain.sealed(s, PvbRuntime.status.speaker)
    val spatialSealed = JdspChain.spatialSealed(s, PvbRuntime.status.speaker)
    val brand = stringResource(R.string.app_brand_name)

    var presets by remember { mutableStateOf(false) }
    var more by remember { mutableStateOf(false) }
    var revert by remember { mutableStateOf(false) }

    RnPage(
        stringResource(R.string.home_advanced_title), onBack = host::returnToHome,
        actions = {
            RnIconAction(stringResource(R.string.action_presets), onClick = { presets = true }) { tint ->
                Icon(painterResource(R.drawable.ic_twotone_folder_special_24dp), null, tint = tint)
            }
            RnIconAction(stringResource(R.string.action_settings), onClick = {
                host.startActivity(RnSettingsActivity.intent(host, RnSettingsActivity.Route.ROOT))
            }) { tint -> Icon(painterResource(R.drawable.ic_twotone_settings_24dp), null, tint = tint) }
            RnIconAction(stringResource(R.string.rn_adv_more), onClick = { more = true }) { tint ->
                Icon(painterResource(R.drawable.ic_twotone_more_horiz_24), null, tint = tint)
            }
        },
    ) {
        ServiceAndStatus(host)
        RnBand()
        PvbSection(host, showIcons)
        if (PvbBuild.researchUi) {
            RnBand()
            RnNote(stringResource(R.string.research_section_header))
            AndroidView(factory = { PvbAnalyzerCard(it) }, modifier = Modifier.fillMaxWidth())
        }
        val chain = stringResource(R.string.pvb_jamesdsp_chain_note, brand)
        val chainResearch = stringResource(R.string.pvb_jamesdsp_chain_research, brand)
        if (inPath) RnNote(if (PvbBuild.recordFeatures) "$chain $chainResearch" else chain)
        if (profilesOn) DeviceProfiles(host)
        RnBand()
        RnSectionTitle(stringResource(R.string.rn_adv_section_jdsp))
        JamesDspModules(host, sealed, spatialSealed, showIcons)
        RnEndSpace()
    }

    if (presets) FileLibrarySheet(host, LibraryType.PRESETS, stringResource(R.string.action_presets), null,
        onSelect = {}, onDismiss = { presets = false })
    if (more) RnSheet({ more = false }) {
        RnNavRow(stringResource(R.string.action_blocked_apps)) {
            more = false
            host.startActivity(RnExclusionsActivity.intent(host))
        }
        RnNavRow(stringResource(R.string.action_revert), chevron = false) { more = false; revert = true }
    }
    if (revert) RnDialog(
        stringResource(R.string.revert_confirmation_title), stringResource(R.string.revert_confirmation),
        confirmLabel = stringResource(R.string.action_revert), onConfirm = { revert = false; host.revert() },
        dismissLabel = stringResource(android.R.string.cancel), onDismiss = { revert = false },
    )
    host.pendingImport?.let { p ->
        RnChoiceSheet(stringResource(p.title),
            listOf(RnChoice(false, stringResource(R.string.intent_import_mode_add), p.name),
                RnChoice(true, stringResource(R.string.intent_import_mode_select))),
            selected = null, onDismiss = { host.pendingImport = null }) { use -> host.finishImport(p, use) }
    }
    host.alert?.let { (t, m) -> RnDialog(t, m, onConfirm = { host.alert = null }) }
}

/**
 * The legacy power button as a switch (on asks for capture; off stops the service), and the PVB status text, refreshed
 * twice a second while the screen is started.
 */
@Composable
private fun ServiceAndStatus(host: RnAdvancedActivity) {
    val c = LocalRn.current
    val context = LocalContext.current
    val on = host.serviceOn
    val starting = host.startPending && !on
    RnSwitchRow(
        stringResource(R.string.rn_adv_service), on || starting, host::setService, bold = true,
        line = stringResource(when {
            starting -> R.string.rn_adv_service_starting
            on -> R.string.rn_adv_service_on
            else -> R.string.rn_adv_service_off
        }),
        icon = painterResource(R.drawable.ic_twotone_power_settings_24dp),
    )
    val status = remember { PvbStatusText(context) }
    val offText = stringResource(R.string.rn_adv_status_off)
    var rendered by remember { mutableStateOf(status.render(offText)) }
    LaunchedEffect(host.started, on) {
        while (host.started) {
            rendered = status.render(offText)
            delay(500L)
        }
    }
    RnSectionTitle(stringResource(R.string.rn_adv_status))
    SelectionContainer {
        Text(rendered.text, color = c.textSecondary, fontSize = 13.sp, lineHeight = 19.sp,
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 12.dp))
    }
    if (rendered.canCopyResearch) RnTextAction(stringResource(R.string.rn_adv_research_copy)) {
        PvbStatusText.copyResearch(context)
    }
}

/**
 * Upstream device profiles (Settings > 기기 프로파일): the output device now, and copy or delete of the stored
 * profiles (DeviceProfilesCardFragment).
 */
@Composable
private fun DeviceProfiles(host: RnAdvancedActivity) {
    val routing = host.routingObserver
    var current by remember { mutableStateOf(routing.currentDevice) }
    DisposableEffect(routing) {
        val cb = object : RoutingObserver.RoutingChangedCallback {
            override fun onRoutingDeviceChanged(device: RoutingObserver.Device?) { current = device }
        }
        routing.registerOnRoutingChangeListener(cb)
        onDispose { routing.unregisterOnRoutingChangeListener(cb) }
    }
    val manager = (host.application as MainApplication).profileManager
    var menu by remember { mutableStateOf(false) }
    var copyFrom by remember { mutableStateOf<List<ProfileManager.Profile>?>(null) }
    var copySource by remember { mutableStateOf<ProfileManager.Profile?>(null) }
    var deleting by remember { mutableStateOf<List<ProfileManager.Profile>?>(null) }
    val actions = stringArrayResource(R.array.manange_profiles_menu)

    RnBand()
    RnNavRow(stringResource(R.string.device_profile_status), current?.name ?: stringResource(R.string.unknown_error),
        value = stringResource(R.string.rn_adv_device_profile_manage)) { menu = true }

    if (menu) RnChoiceSheet(stringResource(R.string.device_profile_status),
        actions.mapIndexed { i, a -> RnChoice(i, a) }, selected = null, onDismiss = { menu = false }) { i ->
        menu = false
        val profiles = manager.allProfiles.toList()
        when (i) {
            0 -> if (profiles.size <= 1) host.toast(R.string.device_profile_manage_copy_select_no_target) else copyFrom = profiles
            1 -> deleting = profiles
        }
    }
    copyFrom?.let { profiles ->
        RnChoiceSheet(stringResource(R.string.device_profile_manage_copy_select), profiles.map { RnChoice(it, it.name) },
            selected = null, onDismiss = { copyFrom = null }) { src -> copyFrom = null; copySource = src }
    }
    copySource?.let { src ->
        val remaining = manager.allProfiles.filter { it.id != src.id }
        RnMultiChoiceDialog(stringResource(R.string.device_profile_manage_paste_select), remaining.map { RnChoice(it, it.name) },
            confirmLabel = stringResource(R.string.paste),
            onConfirm = { dest -> copySource = null; manager.copy(src, dest.toTypedArray()) },
            onDismiss = { copySource = null })
    }
    deleting?.let { profiles ->
        RnMultiChoiceDialog(stringResource(R.string.device_profile_manage_delete), profiles.map { RnChoice(it, it.name) },
            confirmLabel = stringResource(R.string.delete),
            onConfirm = { list -> deleting = null; manager.delete(list.toTypedArray()) },
            onDismiss = { deleting = null })
    }
}

package me.timschneeberger.rootlessjamesdsp.exclusions

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.graphics.drawable.Drawable
import android.os.Bundle
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import androidx.core.text.HtmlCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.model.room.BlockedApp
import me.timschneeberger.rootlessjamesdsp.pvb.QuickExclude
import me.timschneeberger.rootlessjamesdsp.session.dump.DumpManager
import me.timschneeberger.rootlessjamesdsp.session.rootless.SessionRecordingPolicyManager
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnEmpty
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnMultiChoiceDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnNote
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import me.timschneeberger.rootlessjamesdsp.ui.RnSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnTopBar
import me.timschneeberger.rootlessjamesdsp.ui.RnCheckMark
import me.timschneeberger.rootlessjamesdsp.ui.RnSwitchRow
import me.timschneeberger.rootlessjamesdsp.ui.rememberAppPrefs
import me.timschneeberger.rootlessjamesdsp.service.ForegroundAppWatcher
import me.timschneeberger.hiddenapi_impl.ShizukuSystemServerApi
import rikka.shizuku.Shizuku
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import timber.log.Timber
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.extensions.CompatExtensions.getApplicationInfoCompat
import me.timschneeberger.rootlessjamesdsp.utils.extensions.CompatExtensions.getInstalledApplicationsCompat
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getAppNameFromUidSafe
import org.koin.android.ext.android.inject
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.height

/**
 * "제외된 앱" (general build, Compose; replaces BlocklistActivity/BlocklistFragment/AppsListFragment here). Same Room
 * table through MainApplication.blockedAppRepository, so the service rebuilds its capture exactly as before.
 *
 * Page: the delay note with "영상·게임·통화 앱 추가" (QuickExclude, nothing preselected), the unsupported-apps note
 * when the system blocks capture for some apps, an "앱 추가" row that opens the app picker sheet, then the excluded
 * apps (icon, name, package and UID); tapping one asks before removing it, as before.
 */
class RnExclusionsActivity : RnActivity() {
    private val dumpManager: DumpManager by inject()
    private var unsupported by mutableStateOf(listOf<String>())
    /** Usage access (needed by "pause while an excluded app is in front"); refreshed on resume. */
    var usageAccess by mutableStateOf(false)
        private set
    /** The user turned the pause on before granting access: switch it on when access comes back granted. */
    var pendingPause = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setRnContent { ExclusionsPage(this) }
    }

    override fun onResume() {
        super.onResume()
        refreshUnsupported()
        usageAccess = ForegroundAppWatcher.hasAccess(this)
        if (pendingPause && usageAccess) setPause(true)
        pendingPause = false
    }

    private val pauseKey get() = getString(R.string.key_exclusions_pause_foreground)

    fun setPause(on: Boolean) {
        getSharedPreferences(Constants.PREF_APP, MODE_PRIVATE).edit().putBoolean(pauseKey, on).apply()
    }

    /** Usage access: through Shizuku when it is connected and allowed, else the system settings page. */
    fun requestUsageAccess() {
        try {
            if (Shizuku.pingBinder() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                ShizukuSystemServerApi.exec("appops set $packageName GET_USAGE_STATS allow")
                usageAccess = ForegroundAppWatcher.hasAccess(this)
                if (usageAccess) { setPause(true); return }
            }
        } catch (ex: Exception) {
            Timber.w(ex, "usage access through Shizuku")
        }
        pendingPause = true
        val withPkg = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS, Uri.parse("package:$packageName"))
        try { startActivity(withPkg) } catch (_: Exception) {
            try { startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) } catch (_: Exception) { pendingPause = false }
        }
    }

    val unsupportedApps: List<String> get() = unsupported

    /** Apps whose capture the system blocks (excluded automatically when "지원되지 않는 앱 제외" is on). */
    private fun refreshUnsupported() {
        val app = getSharedPreferences(Constants.PREF_APP, MODE_PRIVATE)
        val on = app.getBoolean(getString(R.string.key_session_exclude_restricted), resources.getBoolean(R.bool.default_session_exclude_restricted))
        if (!on) { unsupported = emptyList(); return }
        val manager = SessionRecordingPolicyManager(this)
        try {
            dumpManager.dumpCaptureAllowlistLog()?.let { manager.update(it) }
            unsupported = manager.getRestrictedUids().map { "${getAppNameFromUidSafe(it)} (UID $it)" }
        } catch (_: Exception) {
            unsupported = emptyList()
        } finally {
            manager.destroy()
        }
    }

    companion object {
        fun intent(context: Context) = Intent(context, RnExclusionsActivity::class.java)
    }
}

private fun iconOf(context: Context, pkg: String?): ImageBitmap? = try {
    pkg?.let { context.packageManager.getApplicationIcon(it).toBitmap(96, 96).asImageBitmap() }
} catch (_: Exception) { null }

@Composable
private fun ExclusionsPage(host: RnExclusionsActivity) {
    val c = LocalRn.current
    val repo = (host.application as MainApplication).blockedAppRepository
    val apps by repo.blocklist.collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    var removing by remember { mutableStateOf<BlockedApp?>(null) }
    var picker by remember { mutableStateOf(false) }
    var quick by remember { mutableStateOf<List<Pair<QuickExclude.Candidate, ApplicationInfo>>?>(null) }
    var quickNone by remember { mutableStateOf(false) }
    var unsupportedOpen by remember { mutableStateOf(false) }
    val icons = remember { HashMap<String, ImageBitmap?>() }
    val sorted = apps?.sortedBy { it.appName?.lowercase() }

    fun openQuick() {
        val pm = host.packageManager
        val installed = QuickExclude.APPS.mapNotNull { a ->
            try { a.packageName to pm.getApplicationInfoCompat(a.packageName, 0) } catch (_: Exception) { null }
        }.toMap()
        val excluded = apps.orEmpty().mapNotNull { it.packageName }.toSet()
        val candidates = QuickExclude.candidates(installed.keys, excluded)
        if (candidates.isEmpty()) quickNone = true
        else quick = candidates.mapNotNull { a -> installed[a.packageName]?.let { a to it } }
    }

    Column(Modifier.fillMaxSize().background(c.bg).statusBarsPadding().navigationBarsPadding()) {
        RnTopBar(stringResource(R.string.title_activity_blocklist), onBack = host::finish)
        LazyColumn(Modifier.weight(1f).fillMaxWidth()) {
            item {
                RnNote(stringResource(R.string.firstweek_exclude_note))
                Box(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                    RnFilledButton(stringResource(R.string.firstweek_exclude_quick_button)) { openQuick() }
                }
                PauseSection(host)
                if (host.unsupportedApps.isNotEmpty()) RnNote(
                    pluralStringResource(R.plurals.unsupported_apps, host.unsupportedApps.size, host.unsupportedApps.size),
                    warning = true, onClick = { unsupportedOpen = true },
                )
                Spacer(Modifier.height(8.dp))
                RnBand()
                AddRow(stringResource(R.string.blocklist_add_exclusion_alt)) { picker = true }
                if (sorted != null && sorted.isNotEmpty()) RnSectionTitle(stringResource(R.string.title_activity_blocklist))
            }
            if (sorted == null) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(16.dp), color = c.fill, trackColor = c.sliderInactive) }
            else if (sorted.isEmpty()) item { RnEmpty(stringResource(R.string.blocklist_no_exclusions), top = 32.dp) }
            else items(sorted, key = { it.uid }) { app ->
                val icon = icons.getOrPut(app.packageName ?: "") { iconOf(host, app.packageName) }
                AppRow(icon, app.appName ?: app.packageName ?: "", "${app.packageName} (UID: ${app.uid})") { removing = app }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }

    removing?.let { app ->
        RnDialog(
            stringResource(R.string.blocklist_delete_title), stringResource(R.string.blocklist_delete),
            confirmLabel = stringResource(R.string.yes), onConfirm = { scope.launch { repo.delete(app) }; removing = null },
            dismissLabel = stringResource(R.string.no), onDismiss = { removing = null },
        )
    }
    if (quickNone) RnDialog(stringResource(R.string.firstweek_exclude_quick_button), stringResource(R.string.firstweek_exclude_quick_none),
        onConfirm = { quickNone = false })
    quick?.let { list ->
        val pm = host.packageManager
        RnMultiChoiceDialog(
            stringResource(R.string.firstweek_exclude_quick_title),
            list.map { (a, info) -> RnChoice(a.packageName, pm.getApplicationLabel(info).toString().ifBlank { a.label }) },
            confirmLabel = stringResource(R.string.firstweek_exclude_quick_add),
            onConfirm = { picked ->
                scope.launch {
                    for ((a, info) in list) if (a.packageName in picked)
                        repo.insert(BlockedApp(info.uid, a.packageName, pm.getApplicationLabel(info).toString().ifBlank { a.label }))
                }
                quick = null
            },
            onDismiss = { quick = null },
        )
    }
    if (unsupportedOpen) RnDialog(
        stringResource(R.string.blocklist_unsupported_apps),
        HtmlCompat.fromHtml(stringResource(R.string.blocklist_unsupported_apps_message, host.unsupportedApps.joinToString("<br/>")),
            HtmlCompat.FROM_HTML_MODE_COMPACT).toString().trim(),
        onConfirm = { unsupportedOpen = false },
    )
    if (picker) AppPickerSheet(
        excluded = apps.orEmpty().map { it.uid }.toSet(),
        onDismiss = { picker = false },
        onPick = { info, label ->
            scope.launch { repo.insert(BlockedApp(info.uid, info.packageName, label)) }
            picker = false
        },
    )
}

/** "+ 앱 추가": a row with a plus in the accent colour. */
@Composable
private fun AddRow(label: String, onClick: () -> Unit) {
    val c = LocalRn.current
    Row(
        Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onClick).heightIn(min = 56.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Box(Modifier.size(40.dp).background(c.chipSelectedBg, CircleShape), contentAlignment = Alignment.Center) {
            Text("+", color = c.accentText, fontSize = 22.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold)
        }
        Text(label, color = c.accentText, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
    }
}

/** An app row: 40 dp icon, name (16/22), a line (13/18, one line); [trailing] on the right. */
@Composable
private fun AppRow(icon: ImageBitmap?, name: String, line: String, enabled: Boolean = true,
                   trailing: (@Composable () -> Unit)? = null, onClick: () -> Unit) {
    val c = LocalRn.current
    Row(
        Modifier.fillMaxWidth().clickable(enabled = enabled, role = Role.Button, onClick = onClick).heightIn(min = 64.dp)
            .padding(horizontal = 16.dp, vertical = 10.dp).alpha(if (enabled) 1f else 0.5f),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (icon != null) Image(icon, contentDescription = null, modifier = Modifier.size(40.dp))
        else Box(Modifier.size(40.dp).background(c.band, RoundedCornerShape(10.dp)))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(name, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(line, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        trailing?.invoke()
    }
}

private data class PickerApp(val info: ApplicationInfo, val label: String, val system: Boolean, val icon: Drawable?)

/**
 * The app picker (legacy AppsListFragment): every installed app, user apps first then system apps, each by name;
 * search by name or package; apps already excluded show a check and cannot be picked twice.
 */
@Composable
private fun AppPickerSheet(excluded: Set<Int>, onDismiss: () -> Unit, onPick: (ApplicationInfo, String) -> Unit) {
    val c = LocalRn.current
    val context = androidx.compose.ui.platform.LocalContext.current
    var all by remember { mutableStateOf<List<PickerApp>?>(null) }
    var query by remember { mutableStateOf("") }
    LaunchedEffect(Unit) {
        all = withContext(Dispatchers.IO) {
            val pm = context.packageManager
            pm.getInstalledApplicationsCompat(0)
                .filter { (it.flags and ApplicationInfo.FLAG_INSTALLED) != 0 }
                .map { PickerApp(it, pm.getApplicationLabel(it).toString(), (it.flags and ApplicationInfo.FLAG_SYSTEM) != 0,
                    try { pm.getApplicationIcon(it) } catch (_: Exception) { null }) }
                .sortedWith(compareBy({ it.system }, { it.label.lowercase() }))
        }
    }
    val icons = remember { HashMap<String, ImageBitmap?>() }
    RnSheet(onDismiss, stringResource(R.string.blocklist_add_exclusion_alt)) {
        OutlinedTextField(
            value = query, onValueChange = { query = it }, singleLine = true,
            label = { Text(stringResource(R.string.app_list_search)) },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 4.dp),
            shape = RoundedCornerShape(14.dp),
            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = c.fill, unfocusedBorderColor = c.chipBorder,
                cursorColor = c.fill, focusedLabelColor = c.accentText, focusedTextColor = c.textPrimary, unfocusedTextColor = c.textPrimary),
        )
        val list = all
        if (list == null) {
            Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LinearProgressIndicator(Modifier.fillMaxWidth(), color = c.fill, trackColor = c.sliderInactive)
                Text(stringResource(R.string.app_list_loading), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
            }
        } else {
            val q = query.trim().lowercase()
            val shown = if (q.isEmpty()) list else list.filter { it.label.lowercase().contains(q) || it.info.packageName.lowercase().contains(q) }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 560.dp)) {
                items(shown, key = { it.info.packageName }) { a ->
                    val done = a.info.uid in excluded
                    val icon = icons.getOrPut(a.info.packageName) { a.icon?.toBitmap(96, 96)?.asImageBitmap() }
                    AppRow(icon, a.label, a.info.packageName, enabled = !done,
                        trailing = if (done) ({ RnCheckMark() }) else null) { onPick(a.info, a.label) }
                }
            }
        }
    }
}


/**
 * "제외한 앱을 쓰는 동안 완전히 멈추기" (service/ForegroundPause.kt): the switch, what it does and its rule (the main
 * window counts, not a picture-in-picture or floating window), and the usage access it needs.
 */
@Composable
private fun PauseSection(host: RnExclusionsActivity) {
    val app = rememberAppPrefs()
    val key = host.getString(R.string.key_exclusions_pause_foreground)
    val on = app.bool(key, false) && host.usageAccess
    var explain by remember { mutableStateOf(false) }
    RnBand()
    RnSwitchRow(stringResource(R.string.exclusions_pause_title), on, { want ->
        if (!want) host.setPause(false)
        else if (host.usageAccess) host.setPause(true)
        else host.requestUsageAccess()
    }, line = stringResource(R.string.exclusions_pause_summary))
    if (!host.usageAccess) RnNote(stringResource(R.string.exclusions_pause_needs_access))
    RnNote(stringResource(R.string.exclusions_pause_rule_open), onClick = { explain = true })
    if (explain) RnDialog(stringResource(R.string.exclusions_pause_rule_title), stringResource(R.string.exclusions_pause_rule),
        onConfirm = { explain = false })
}

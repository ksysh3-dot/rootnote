package me.timschneeberger.rootlessjamesdsp.advanced

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Canvas
import androidx.compose.ui.geometry.Offset
import androidx.core.content.FileProvider
import androidx.core.content.getSystemService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.LiveprogEditorActivity
import me.timschneeberger.rootlessjamesdsp.interop.JdspImpResToolbox
import me.timschneeberger.rootlessjamesdsp.liveprog.EelParser
import me.timschneeberger.rootlessjamesdsp.model.preset.Preset
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnButtonRow
import me.timschneeberger.rootlessjamesdsp.ui.RnCheckMark
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnInputDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnOutlineButton
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.ui.RnSheet
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.storage.StorageUtils
import timber.log.Timber
import java.io.File
import java.util.Locale
import kotlin.math.roundToInt

/**
 * The file libraries of the advanced screen (legacy FileLibraryPreference + FileLibraryDialogFragment): presets,
 * DDC (.vdc), convolver impulse responses (.flac/.wav/.irs) and Liveprog scripts (.eel), each a folder under the
 * app's external files dir. A module stores the chosen file as a path relative to that dir.
 */
enum class LibraryType(val dir: String, val exts: List<String>) {
    PRESETS("Presets", listOf(".tar")),
    DDC("DDC", listOf(".vdc")),
    CONVOLVER("Convolver", listOf(".flac", ".wav", ".irs")),
    LIVEPROG("Liveprog", listOf(".eel"));

    fun accepts(name: String) = exts.any { name.endsWith(it) }
}

/** One file of a library: [name] without the extension, [path] relative to the external files dir. */
data class LibraryFile(val name: String, val path: String, val file: File)

object FileLibrary {
    fun dir(context: Context, type: LibraryType): File? =
        context.getExternalFilesDir(null)?.let { File(it, type.dir).apply { mkdirs() } }

    /** The files with the right extension, sorted by name (one entry per name, like the legacy list). */
    fun list(context: Context, type: LibraryType): List<LibraryFile> {
        val base = context.getExternalFilesDir(null) ?: return emptyList()
        val dir = dir(context, type) ?: return emptyList()
        return (dir.list() ?: emptyArray()).filter(type::accepts)
            .associate { it.substringBeforeLast('.') to File(dir, it) }
            .toSortedMap()
            .map { (name, f) -> LibraryFile(name, f.toRelativeString(base), f) }
    }

    /** The stored value as a relative path (old values were full paths). */
    fun relative(context: Context, value: String): String {
        if (!value.startsWith("/")) return value
        val base = context.getExternalFilesDir(null) ?: return value
        return File(value).toRelativeString(base)
    }

    /** The shown name of a stored value: the file name without its extension, or null for none. */
    fun displayName(value: String?): String? =
        value?.takeIf { it.isNotBlank() }?.let { File(it).nameWithoutExtension }

    fun fullPath(context: Context, value: String): String =
        me.timschneeberger.rootlessjamesdsp.preference.FileLibraryPreference.createFullPathCompat(context, value)
}

/** A rename/duplicate/new-preset prompt: the new file goes next to [base] with its extension. */
private data class NamePrompt(val title: Int, val base: File, val autofill: Boolean, val allowOverwrite: Boolean,
                              val then: (File) -> Unit)

/**
 * The library sheet: the files (a check on the selected one; presets load on tap), Liveprog tag chips, the actions of
 * a file (⋯ button or long press: edit, overwrite, rename, duplicate, offline resample, share, delete), and
 * "가져오기" / "새 프리셋". [selected] is the module's stored value; [onSelect] stores a new one ("" = none).
 */
@Composable
fun FileLibrarySheet(
    host: RnAdvancedActivity,
    type: LibraryType,
    title: String,
    selected: String?,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val c = LocalRn.current
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    val files = remember(tick) { FileLibrary.list(context, type) }
    val selectedRel = selected?.let { FileLibrary.relative(context, it) }
    var actionsFor by remember { mutableStateOf<LibraryFile?>(null) }
    var prompt by remember { mutableStateOf<NamePrompt?>(null) }
    var deleting by remember { mutableStateOf<LibraryFile?>(null) }
    var error by remember { mutableStateOf<Pair<String, String>?>(null) }
    // Liveprog: tag -> script names, scanned off the main thread
    var tags by remember { mutableStateOf<List<Pair<String, List<String>>>>(emptyList()) }
    var tag by remember { mutableStateOf<String?>(null) }
    val untagged = stringResource(R.string.rn_files_untagged)
    LaunchedEffect(tick) {
        if (type != LibraryType.LIVEPROG) return@LaunchedEffect
        tags = withContext(Dispatchers.IO) { scanTags(context, files, untagged) }
        if (tag != null && tags.none { it.first == tag }) tag = null
    }
    fun refresh() { tick++ }

    fun importFile() = host.pickFile { uri -> importInto(host, type, uri, onError = { error = it }) { scope.launch { refresh() } } }

    RnSheet(onDismiss, title) {
        if (type == LibraryType.LIVEPROG && tags.isNotEmpty()) {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TagChip(stringResource(R.string.rn_files_all), tag == null) { tag = null }
                for ((t, _) in tags) TagChip(t, tag == t) { tag = if (tag == t) null else t }
            }
        }
        val shown = tag?.let { t -> tags.firstOrNull { it.first == t }?.second }?.let { names -> files.filter { it.name in names } } ?: files
        if (shown.isEmpty()) {
            RnParagraph(stringResource(if (type == LibraryType.PRESETS) R.string.rn_presets_empty else R.string.rn_files_empty),
                Modifier.padding(horizontal = 8.dp, vertical = 16.dp))
        } else {
            Column(Modifier.fillMaxWidth().heightIn(max = 420.dp).verticalScroll(rememberScrollState()).selectableGroup()) {
                for (f in shown) {
                    val isSelected = type != LibraryType.PRESETS && f.path == selectedRel
                    FileRow(f.name, isSelected, type != LibraryType.PRESETS,
                        actionsLabel = stringResource(R.string.rn_files_actions, f.name),
                        onClick = {
                            if (type == LibraryType.PRESETS) {
                                try {
                                    Preset(f.file.name).load()
                                    context.toast(context.getString(R.string.filelibrary_preset_loaded, f.name))
                                    onDismiss()
                                } catch (ex: Exception) {
                                    error = context.getString(R.string.filelibrary_corrupted_title) to
                                        (ex.localizedMessage ?: context.getString(R.string.filelibrary_preset_load_failed, f.name))
                                }
                            } else {
                                onSelect(f.path)
                                onDismiss()
                            }
                        },
                        onActions = { actionsFor = f })
                }
            }
        }
        RnButtonRow {
            if (type == LibraryType.PRESETS) {
                RnOutlineButton(stringResource(R.string.action_import), Modifier.weight(1f)) { importFile() }
                RnFilledButton(stringResource(R.string.filelibrary_context_new_preset_long), Modifier.weight(1f)) {
                    val base = Preset("Untitled.tar").file()
                    prompt = NamePrompt(R.string.filelibrary_context_new_preset_long, base, autofill = false, allowOverwrite = true) { file ->
                        val overwritten = file.exists()
                        val ok = Preset(file.name).save()
                        context.toast(when {
                            !ok -> context.getString(R.string.filelibrary_preset_save_failed)
                            overwritten -> context.getString(R.string.filelibrary_preset_overwritten, file.nameWithoutExtension)
                            else -> context.getString(R.string.filelibrary_preset_created, file.nameWithoutExtension)
                        })
                        refresh()
                    }
                }
            } else {
                RnFilledButton(stringResource(R.string.action_import), Modifier.weight(1f)) { importFile() }
            }
        }
    }

    actionsFor?.let { f ->
        FileActionsSheet(type, f, onDismiss = { actionsFor = null }) { action ->
            actionsFor = null
            when (action) {
                FileAction.EDIT -> {
                    host.launchSafely {
                        host.startActivity(Intent(host, LiveprogEditorActivity::class.java)
                            .putExtra(LiveprogEditorActivity.EXTRA_TARGET_FILE, f.file.absolutePath))
                    }
                    onDismiss()
                }
                FileAction.OVERWRITE -> {
                    context.toast(if (Preset(f.file.name).save()) context.getString(R.string.filelibrary_preset_overwritten, f.name)
                        else context.getString(R.string.filelibrary_preset_save_failed))
                    refresh()
                }
                FileAction.RENAME -> prompt = NamePrompt(R.string.filelibrary_context_rename, f.file, autofill = true, allowOverwrite = false) { to ->
                    val wasSelected = f.path == selectedRel
                    if (f.file.renameTo(to)) {
                        context.toast(context.getString(R.string.filelibrary_renamed, to.nameWithoutExtension))
                        // the module keeps using the file under its new name
                        if (wasSelected) context.getExternalFilesDir(null)?.let { onSelect(to.toRelativeString(it)) }
                    }
                    refresh()
                }
                FileAction.DUPLICATE -> prompt = NamePrompt(R.string.filelibrary_context_duplicate, f.file, autofill = true, allowOverwrite = false) { to ->
                    try { f.file.copyTo(to) } catch (ex: Exception) { Timber.e(ex) }
                    refresh()
                }
                FileAction.RESAMPLE -> resample(host, f.file) { refresh() }
                FileAction.SHARE -> {
                    val uri = FileProvider.getUriForFile(context, BuildConfig.APPLICATION_ID + ".file_library_provider", f.file)
                    val share = Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM, uri)
                        .setType("application/octet-stream").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    host.launchSafely { host.startActivity(Intent.createChooser(share, context.getString(R.string.filelibrary_context_share))) }
                }
                FileAction.DELETE -> deleting = f
            }
        }
    }

    deleting?.let { f ->
        RnDialog(
            stringResource(R.string.filelibrary_context_delete), stringResource(R.string.rn_files_delete_confirm, f.name),
            confirmLabel = stringResource(R.string.delete),
            onConfirm = {
                deleting = null
                f.file.delete()
                context.toast(context.getString(R.string.filelibrary_deleted, f.name))
                // the module no longer has this file: clear its selection
                if (type != LibraryType.PRESETS && f.path == selectedRel) onSelect("")
                refresh()
            },
            dismissLabel = stringResource(android.R.string.cancel), onDismiss = { deleting = null },
        )
    }

    prompt?.let { pr ->
        val exists = stringResource(R.string.filelibrary_file_exists)
        val empty = stringResource(R.string.rn_files_name_empty)
        fun target(name: String) = File(pr.base.absoluteFile.parentFile, name + "." + pr.base.extension)
        RnInputDialog(
            title = stringResource(pr.title),
            initial = if (pr.autofill) pr.base.nameWithoutExtension else "",
            hint = stringResource(R.string.filelibrary_new_file_name),
            suffix = "." + pr.base.extension,
            validate = { name ->
                when {
                    name.isBlank() -> empty
                    // a plain file name, kept inside the library folder
                    name.contains('/') || name.contains('\\') || name == "." || name == ".." -> empty
                    !pr.allowOverwrite && target(name).exists() -> exists
                    else -> null
                }
            },
            onDone = { name -> prompt = null; pr.then(target(name)) },
            onDismiss = { prompt = null },
        )
    }

    error?.let { (t, m) -> RnDialog(t, m, onConfirm = { error = null }) }
}

private enum class FileAction(val label: Int) {
    EDIT(R.string.filelibrary_context_edit),
    OVERWRITE(R.string.filelibrary_context_overwrite),
    RENAME(R.string.filelibrary_context_rename),
    DUPLICATE(R.string.filelibrary_context_duplicate),
    RESAMPLE(R.string.filelibrary_context_resample),
    SHARE(R.string.filelibrary_context_share),
    DELETE(R.string.filelibrary_context_delete),
}

/** The legacy context menu, per type: edit (Liveprog), overwrite (presets), duplicate (Liveprog, presets), resample (IRs). */
@Composable
private fun FileActionsSheet(type: LibraryType, f: LibraryFile, onDismiss: () -> Unit, onAction: (FileAction) -> Unit) {
    val actions = FileAction.entries.filter { a ->
        when (a) {
            FileAction.EDIT -> type == LibraryType.LIVEPROG
            FileAction.OVERWRITE -> type == LibraryType.PRESETS
            FileAction.DUPLICATE -> type == LibraryType.LIVEPROG || type == LibraryType.PRESETS
            FileAction.RESAMPLE -> type == LibraryType.CONVOLVER
            else -> true
        }
    }
    RnSheet(onDismiss, f.name) {
        for (a in actions) RnNavRow(stringResource(a.label), chevron = false) { onAction(a) }
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
/** A file row: the name, a check when selected (role RadioButton for module files), and a 48 dp ⋯ actions button. */
@Composable
private fun FileRow(name: String, selected: Boolean, radio: Boolean, actionsLabel: String, onClick: () -> Unit, onActions: () -> Unit) {
    val c = LocalRn.current
    Row(
        Modifier.fillMaxWidth()
            .then(if (radio) Modifier.selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
                else Modifier.combinedClickable(role = Role.Button, onLongClick = onActions, onClick = onClick))
            .heightIn(min = 56.dp).padding(start = 24.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(name, color = if (selected) c.accentText else c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal, modifier = Modifier.weight(1f).padding(vertical = 8.dp))
        if (selected) RnCheckMark()
        Box(
            Modifier.size(48.dp).clickable(role = Role.Button, onClick = onActions).semantics { contentDescription = actionsLabel },
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(20.dp)) {
                val r = size.width / 12f
                for (i in -1..1) drawCircle(c.textSecondary, r, Offset(size.width / 2f + i * size.width / 3.2f, size.height / 2f))
            }
        }
    }
}

/** A tag filter chip (single choice; tapping the chosen one again shows all). */
@Composable
private fun TagChip(label: String, on: Boolean, onClick: () -> Unit) {
    val c = LocalRn.current
    Box(
        Modifier.heightIn(min = 48.dp).selectable(selected = on, role = Role.RadioButton, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = if (on) c.onFill else c.textPrimary, fontSize = 14.sp, lineHeight = 20.sp,
            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
            modifier = Modifier
                .background(if (on) c.fill else c.bg, RoundedCornerShape(50))
                .border(1.dp, if (on) c.fill else c.chipBorder, RoundedCornerShape(50))
                .padding(horizontal = 14.dp, vertical = 7.dp))
    }
}

/** Liveprog tags from the scripts' metadata (legacy scanScriptMetadata): most used first, "Untagged" for the rest. */
private fun scanTags(context: Context, files: List<LibraryFile>, untaggedLabel: String): List<Pair<String, List<String>>> {
    val parser = EelParser()
    val found = linkedMapOf<String, MutableList<String>>()
    val untagged = mutableListOf<String>()
    for (f in files) {
        parser.load(f.file.absolutePath, force = true, skipProperties = true)
        if (parser.tags.isEmpty()) untagged += f.name
        for (tag in parser.tags) {
            val pretty = tag.lowercase()
                .replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }
                .let { if (it.length <= 3) it.uppercase() else it }
            found.getOrPut(pretty) { mutableListOf() } += f.name
        }
    }
    if (untagged.isNotEmpty()) found.getOrPut(untaggedLabel) { mutableListOf() } += untagged
    return found.entries.sortedWith(compareByDescending<Map.Entry<String, List<String>>> { it.value.size }.thenBy { it.key })
        .map { it.key to it.value.toList() }
}

/** Imports a picked document into the library: extension and (presets) content checks, then the copy. */
private fun importInto(host: RnAdvancedActivity, type: LibraryType, uri: Uri, onError: (Pair<String, String>) -> Unit, then: () -> Unit) {
    val name = StorageUtils.queryName(host, uri) ?: "INVALID"
    if (!type.accepts(name)) {
        onError(host.getString(R.string.filelibrary_unsupported_format_title) to host.getString(R.string.filelibrary_unsupported_format))
        return
    }
    if (type == LibraryType.PRESETS) {
        val valid = StorageUtils.openInputStreamSafe(host, uri)?.use { Preset.validate(it) } ?: true
        if (!valid) {
            onError(host.getString(R.string.filelibrary_corrupted_title) to host.getString(R.string.filelibrary_corrupted))
            return
        }
    }
    val dir = FileLibrary.dir(host, type)?.absolutePath ?: return
    if (StorageUtils.importFile(host, dir, uri) == null) Timber.e("Failed to import file") else then()
}

/** Offline resample of an impulse response to the engine's rate (or the output rate before the engine reports one). */
private fun resample(host: RnAdvancedActivity, file: File, then: () -> Unit) {
    var rate = (host.application as MainApplication).engineSampleRate.roundToInt()
    if (rate <= 0) {
        rate = host.getSystemService<AudioManager>()?.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE)
            ?.toIntOrNull()?.takeUnless { it == 0 } ?: 48000
    }
    val target = rate
    kotlinx.coroutines.CoroutineScope(Dispatchers.IO).launch {
        val newName = JdspImpResToolbox.OfflineAudioResample((file.absoluteFile.parentFile?.absolutePath + "/"), file.name, target)
        withContext(Dispatchers.Main) {
            host.toast(if (newName == "Invalid") host.getString(R.string.filelibrary_resample_failed)
                else host.getString(R.string.filelibrary_resample_complete, target))
            then()
        }
    }
}

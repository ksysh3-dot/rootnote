package me.timschneeberger.rootlessjamesdsp.fragment

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.core.content.FileProvider
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.fragment.settings.SettingsBaseFragment
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbCsv
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbJson
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbRecord
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbTally
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbView
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

/**
 * Alpha 3.3: the saved live blind comparison trials, newest first with the mapping revealed, a tally per comparison,
 * delete (one or all), and export as JSON + CSV: share sheet (files under filesDir/live_ab_export through the same
 * FileProvider as the buzz reports) or a file the user picks (Storage Access Framework).
 */
class LiveAbResultsFragment : SettingsBaseFragment() {
    private lateinit var saveJson: ActivityResultLauncher<String>
    private lateinit var saveCsv: ActivityResultLauncher<String>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        saveJson = registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
            uri?.let { writeTo(it, json()) }
        }
        saveCsv = registerForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
            uri?.let { writeTo(it, LiveAbCsv.encode(records())) }
        }
    }

    override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
        preferenceScreen = preferenceManager.createPreferenceScreen(requireContext())
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    private fun records(): List<LiveAbRecord> = LiveAbView.openStore(requireContext()).newestFirst()

    private fun stamp(pattern: String) = SimpleDateFormat(pattern, Locale.US).format(Date())

    private fun json() = LiveAbJson.encodeExport(records(), stamp("yyyy-MM-dd HH:mm:ssXXX"),
        "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")

    private fun fileBase() = "pvb_live_ab_" + stamp("yyyyMMdd_HHmmss")

    private fun db(v: Float) = if (!v.isFinite()) "?" else v.roundToInt().let { if (it > 0) "+$it dB" else "$it dB" }

    private fun render() {
        val ctx = context ?: return
        val all = records()
        val screen = preferenceScreen ?: return
        screen.removeAll()
        fun item(title: CharSequence, summary: CharSequence? = null, click: (() -> Unit)? = null) = Preference(ctx).apply {
            isPersistent = false
            isIconSpaceReserved = false
            isSingleLineTitle = false
            this.title = title
            this.summary = summary
            isSelectable = click != null
            click?.let { c -> setOnPreferenceClickListener { c(); true } }
        }
        fun category(title: String) = PreferenceCategory(ctx).apply {
            this.title = title
            isIconSpaceReserved = false
        }.also { screen.addPreference(it) }

        val export = category(getString(R.string.pvb_live_ab_export))
        if (all.isEmpty()) {
            export.addPreference(item(getString(R.string.pvb_live_ab_empty)))
            return
        }
        export.addPreference(item(getString(R.string.pvb_live_ab_share), getString(R.string.pvb_live_ab_share_summary, all.size)) { share() })
        export.addPreference(item(getString(R.string.pvb_live_ab_save_json)) { launch(saveJson, fileBase() + ".json") })
        export.addPreference(item(getString(R.string.pvb_live_ab_save_csv)) { launch(saveCsv, fileBase() + ".csv") })

        val tally = category(getString(R.string.pvb_live_ab_tally))
        for (row in LiveAbTally.tally(all)) {
            val parts = row.conditionIds.joinToString(", ") { "${row.labels[it] ?: it} ${row.wins[it] ?: 0}" } +
                ", " + getString(R.string.pvb_live_ab_same) + " ${row.same}"
            val p = row.pValue?.let { "\np = " + String.format(Locale.US, "%.2f", it) + " " + getString(R.string.pvb_live_ab_p_hint) } ?: ""
            val chips = if (row.chips.isEmpty()) "" else "\n" + getString(R.string.pvb_live_ab_chips) + ": " +
                row.chips.entries.joinToString(", ") { "${it.key} ${it.value}" }
            tally.addPreference(item(getString(R.string.pvb_live_ab_tally_title, row.comparisonLabel, row.trials), parts + p + chips))
        }

        val list = category(getString(R.string.pvb_live_ab_trials, all.size))
        for (r in all) list.addPreference(item(title(r), summary(r)) { confirmDelete(r) })
        list.addPreference(item(getString(R.string.pvb_live_ab_clear_all)) {
            AlertDialog.Builder(ctx)
                .setTitle(R.string.pvb_live_ab_clear_all)
                .setMessage(getString(R.string.pvb_live_ab_clear_all_confirm, all.size))
                .setPositiveButton(R.string.pvb_live_ab_delete) { _, _ ->
                    if (!LiveAbView.openStore(ctx).clear()) ctx.toast(getString(R.string.pvb_live_ab_delete_failed))
                    render()
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        })
    }

    private fun verdictText(r: LiveAbRecord): String {
        val w = r.winner()
        return if (w == null) getString(R.string.pvb_live_ab_same) else "${w.letter} = ${w.label}"
    }

    private fun title(r: LiveAbRecord) = "${r.timeLocal.take(16)} · ${r.comparisonLabel} · ${verdictText(r)}"

    private fun summary(r: LiveAbRecord): String {
        val lines = ArrayList<String>()
        lines += r.sides.joinToString(", ") { "${it.letter} = ${it.label}" }
        if (r.chips.isNotEmpty()) lines += getString(R.string.pvb_live_ab_chips) + ": " + r.chips.joinToString(", ")
        if (r.note.isNotBlank()) lines += getString(R.string.pvb_live_ab_note) + ": " + r.note
        lines += r.track?.let { t -> listOfNotNull(t.title, t.artist).joinToString(" — ").ifBlank { t.packageName } }
            ?: getString(R.string.pvb_live_ab_no_track)
        lines += getString(R.string.pvb_live_ab_state, r.volumePct.roundToInt(), db(r.vbSliderDb),
            r.sides.joinToString(" / ") { "${it.letter} ${db(it.effectiveLevelDb)}" },
            if (r.batteryPct >= 0) "${r.batteryPct}%" else "?")
        return lines.joinToString("\n")
    }

    private fun confirmDelete(r: LiveAbRecord) {
        val ctx = context ?: return
        AlertDialog.Builder(ctx)
            .setTitle(title(r))
            .setMessage(summary(r) + "\n\n" + getString(R.string.pvb_live_ab_delete_confirm))
            .setPositiveButton(R.string.pvb_live_ab_delete) { _, _ ->
                if (!LiveAbView.openStore(ctx).delete(r.id)) ctx.toast(getString(R.string.pvb_live_ab_delete_failed))
                render()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun launch(l: ActivityResultLauncher<String>, name: String) {
        try {
            l.launch(name)
        } catch (_: Exception) {
            context?.toast(getString(R.string.no_activity_found))
        }
    }

    private fun writeTo(uri: Uri, text: String) {
        val ctx = context ?: return
        try {
            ctx.contentResolver.openOutputStream(uri, "wt")?.use { it.write(text.toByteArray(Charsets.UTF_8)) }
                ?: error("no stream")
            ctx.toast(getString(R.string.pvb_live_ab_saved))
        } catch (_: Exception) {
            ctx.toast(getString(R.string.pvb_live_ab_save_failed))
        }
    }

    /** Both files through the share sheet, the same way the buzz reports are shared (BuzzFileProvider). */
    private fun share() {
        val ctx = context ?: return
        try {
            val dir = exportDir(ctx)
            dir.listFiles()?.forEach { it.delete() }   // only the latest export is kept for sharing
            val name = fileBase()
            val j = File(dir, "$name.json").apply { writeText(json(), Charsets.UTF_8) }
            val c = File(dir, "$name.csv").apply { writeText(LiveAbCsv.encode(records()), Charsets.UTF_8) }
            val authority = BuildConfig.APPLICATION_ID + ".buzz_provider"
            val uris = arrayListOf(FileProvider.getUriForFile(ctx, authority, j), FileProvider.getUriForFile(ctx, authority, c))
            val send = Intent(Intent.ACTION_SEND_MULTIPLE).setType("*/*")
                .putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
                .putExtra(Intent.EXTRA_SUBJECT, name)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            send.clipData = ClipData.newRawUri(name, uris[0]).apply { addItem(ClipData.Item(uris[1])) }
            startActivity(Intent.createChooser(send, getString(R.string.pvb_live_ab_share)))
        } catch (_: Exception) {
            ctx.toast(getString(R.string.pvb_live_ab_share_failed))
        }
    }

    companion object {
        fun exportDir(ctx: Context): File = File(ctx.filesDir, "live_ab_export").apply { if (!isDirectory) mkdirs() }
    }
}

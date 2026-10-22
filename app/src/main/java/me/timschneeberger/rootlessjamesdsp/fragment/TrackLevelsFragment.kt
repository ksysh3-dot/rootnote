package me.timschneeberger.rootlessjamesdsp.fragment

import android.os.Bundle
import androidx.appcompat.app.AlertDialog
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.fragment.settings.SettingsBaseFragment
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.TrackKeys
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevelEntry
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevels
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import kotlin.math.roundToInt

/** Alpha 3.1 "기억된 곡": status, the remembered songs (tap one to delete it) and 모두 지우기. */
class TrackLevelsFragment : SettingsBaseFragment() {
    private var shown: List<Any?>? = null
    private val onChange: () -> Unit = { if (isAdded) render(force = false) }

    override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
        preferenceScreen = preferenceManager.createPreferenceScreen(requireContext())
        TrackLevels.get(requireContext()).addListener(onChange)
        render(force = true)
    }

    override fun onResume() {
        super.onResume()
        render(force = true)   // back from the notification access screen
    }

    override fun onDestroy() {
        TrackLevels.removeListener(onChange)
        super.onDestroy()
    }

    private fun db(v: Float) = PvbSettings.clampLevel(v).roundToInt().let { if (it > 0) "+$it dB" else "$it dB" }

    private fun appName(pkg: String): String = try {
        val pm = requireContext().packageManager
        pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString()
    } catch (_: Exception) { pkg }

    private fun name(e: TrackLevelEntry): String =
        listOf(e.title.ifBlank { "?" }, e.artist.ifBlank { getString(R.string.pvb_track_levels_no_artist) }).joinToString(" — ")

    /** Rebuilds the list only when something visible changed (the watcher reports every few seconds). */
    private fun render(force: Boolean) {
        val ctx = context ?: return
        val levels = TrackLevels.get(ctx)
        val i = levels.indicator(ctx)
        val entries = levels.entries()
        val playingKey = if (i.usingSaved) TrackKeys.of(i.track) else null
        val signature = listOf(i.enabled, i.access, i.defaultDb, playingKey, entries)
        if (!force && signature == shown) return
        shown = signature

        val screen = preferenceScreen
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

        val status = PreferenceCategory(ctx).apply {
            title = getString(R.string.pvb_track_levels_status)
            isIconSpaceReserved = false
        }
        screen.addPreference(status)
        status.addPreference(if (i.enabled)
            item(getString(R.string.pvb_track_levels_on), getString(R.string.pvb_track_levels_help, db(i.defaultDb)))
        else
            item(getString(R.string.pvb_track_levels_off), getString(R.string.pvb_track_levels_off_summary)))
        status.addPreference(if (i.access)
            item(getString(R.string.pvb_track_levels_access_ok))
        else
            item(getString(R.string.pvb_track_levels_access_missing), getString(R.string.pvb_track_levels_access_missing_summary)) {
                try {
                    startActivity(TrackLevels.notificationAccessIntent(ctx))
                } catch (_: Exception) {
                    ctx.toast(R.string.no_activity_found)
                }
            })

        val list = PreferenceCategory(ctx).apply {
            title = getString(R.string.pvb_track_levels_list, entries.size)
            isIconSpaceReserved = false
        }
        screen.addPreference(list)
        if (entries.isEmpty()) {
            list.addPreference(item(getString(R.string.pvb_track_levels_empty)))
            return
        }
        for (e in entries) {
            val detail = getString(R.string.pvb_track_levels_entry_summary,
                appName(e.packageName), db(e.levelDb), PvbModels.fromKey(e.modelKey).title)
            list.addPreference(item(name(e),
                if (e.key == playingKey) getString(R.string.pvb_track_levels_now_playing, detail) else detail) {
                AlertDialog.Builder(ctx)
                    .setMessage(getString(R.string.pvb_track_levels_delete_confirm, name(e)))
                    .setPositiveButton(R.string.pvb_track_levels_delete) { _, _ -> TrackLevels.remove(e.key); render(force = true) }
                    .setNegativeButton(android.R.string.cancel, null)
                    .show()
            })
        }
        list.addPreference(item(getString(R.string.pvb_track_levels_clear_all), getString(R.string.pvb_track_levels_clear_all_summary)) {
            AlertDialog.Builder(ctx)
                .setTitle(R.string.pvb_track_levels_clear_all)
                .setMessage(getString(R.string.pvb_track_levels_clear_all_confirm, entries.size))
                .setPositiveButton(R.string.pvb_track_levels_clear_all) { _, _ -> TrackLevels.clear(); render(force = true) }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        })
    }
}

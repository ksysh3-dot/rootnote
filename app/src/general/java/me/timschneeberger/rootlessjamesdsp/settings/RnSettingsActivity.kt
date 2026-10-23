package me.timschneeberger.rootlessjamesdsp.settings

import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.backup.BackupCreatorJob
import me.timschneeberger.rootlessjamesdsp.backup.BackupManager
import me.timschneeberger.rootlessjamesdsp.service.NotificationListenerService
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.session.dump.DumpManager
import org.koin.android.ext.android.inject
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter

/**
 * Settings of the general build in Compose (replaces SettingsActivity and its Preference fragments there; the s26u
 * build keeps them). One activity per page: [EXTRA_ROUTE] picks the page, a row opens the next page as a new
 * instance, back finishes it (the system back animation). Same keys, files and behaviours as the legacy screens.
 *
 * The activity owns what a page cannot: the document pickers of the backup page, the session dump, and a tick that
 * pages read to re-check permission state after returning from the system settings.
 */
class RnSettingsActivity : RnActivity() {

    enum class Route { ROOT, APPEARANCE, AUDIO, PROFILES, TROUBLESHOOT, LIMITATIONS, BACKUP, MISC, ABOUT }

    /** Incremented on every resume: pages that show permission state re-read it. */
    var resumeTick by mutableIntStateOf(0)
        private set

    /** A backup picked for restore: the page asks clean or dirty restore. */
    var restoreUri by mutableStateOf<Uri?>(null)

    /** The backup location changed (the backup page re-reads its summary). */
    var backupLocationTick by mutableIntStateOf(0)
        private set

    private val dumpManager: DumpManager by inject()

    lateinit var backupLocationLauncher: ActivityResultLauncher<Uri?>
        private set
    lateinit var backupSaveLauncher: ActivityResultLauncher<String>
        private set
    lateinit var backupLoadLauncher: ActivityResultLauncher<Array<String>>
        private set

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val route = runCatching { Route.valueOf(intent.getStringExtra(EXTRA_ROUTE) ?: "") }.getOrDefault(Route.ROOT)

        backupLocationLauncher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            val app = getSharedPreferences(Constants.PREF_APP, MODE_PRIVATE)
            if (uri != null) {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                app.edit().putString(getString(R.string.key_backup_location), uri.toString()).apply()
            } else if (app.getString(getString(R.string.key_backup_location), "").isNullOrBlank()) {
                // no location: automatic backups cannot run, so the frequency goes back to its default (never)
                app.edit().putString(getString(R.string.key_backup_frequency), getString(R.string.default_backup_frequency)).apply()
                BackupCreatorJob.setupTask(this, getString(R.string.default_backup_frequency).toIntOrNull() ?: 0)
            }
            backupLocationTick++
        }
        backupSaveLauncher = registerForActivityResult(ActivityResultContracts.CreateDocument("application/*")) { uri ->
            uri ?: return@registerForActivityResult
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            BackupCreatorJob.startNow(this, uri)
        }
        backupLoadLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) restoreUri = uri
        }

        setRnContent { SettingsPage(route, this) }
    }

    override fun onResume() {
        super.onResume()
        resumeTick++
    }

    fun open(route: Route) = startActivity(intent(this, route))

    fun launchSafely(block: () -> Unit) {
        try { block() } catch (_: ActivityNotFoundException) { toast(R.string.no_activity_found) }
    }

    fun pickBackupLocation() = launchSafely {
        toast(getString(R.string.backup_select_location), true)
        backupLocationLauncher.launch(null)
    }

    fun createBackup() {
        if (BackupCreatorJob.isManualJobRunning(this)) toast(R.string.backup_in_progress)
        else launchSafely { backupSaveLauncher.launch(BackupManager.getBackupFilename()) }
    }

    fun loadBackup() = launchSafely { backupLoadLauncher.launch(arrayOf("application/tar+gzip", "application/gzip")) }

    /** Collects the session dump and the app log into dump.txt and shares it (the legacy troubleshooting action). */
    fun shareDump() {
        val debug = dumpManager.collectDebugDumps()
        val path = File(filesDir, "dump.txt")
        FileOutputStream(path).use { output ->
            val writer = OutputStreamWriter(output)
            writer.write(debug)
            writer.write("==================> Application log\n")
            writer.flush()
            val log = File(cacheDir, "application.log")
            if (log.exists()) {
                try { log.inputStream().use { it.copyTo(output) } }
                catch (ex: Exception) { writer.write("NOTE: Failed to append log file.\n$ex\n") }
            } else writer.write("NOTE: Log file does not exist\n")
            writer.flush()
        }
        val uri = FileProvider.getUriForFile(this, BuildConfig.APPLICATION_ID + ".dump_provider", path)
        val share = Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM, uri).setType("text/plain")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        launchSafely { startActivity(Intent.createChooser(share, getString(R.string.troubleshooting_dump_share_title))) }
    }

    /** Opens the notification-access setting for the session listener (more reliable session detection). */
    fun openNotificationAccess() {
        val name = NotificationListenerService::class.java.name
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Intent(Settings.ACTION_NOTIFICATION_LISTENER_DETAIL_SETTINGS)
                .putExtra(Settings.EXTRA_NOTIFICATION_LISTENER_COMPONENT_NAME, ComponentName(packageName, name).flattenToString())
        } else {
            Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS).apply {
                val value = "$packageName/$name"
                putExtra(":settings:show_fragment_args", Bundle().also { it.putString(":settings:fragment_args_key", value) })
                putExtra(":settings:fragment_args_key", value)
            }
        }
        try { startActivity(intent) } catch (_: Exception) { toast(R.string.no_activity_found) }
    }

    companion object {
        const val EXTRA_ROUTE = "route"

        fun intent(context: Context, route: Route): Intent =
            Intent(context, RnSettingsActivity::class.java).putExtra(EXTRA_ROUTE, route.name)
    }
}

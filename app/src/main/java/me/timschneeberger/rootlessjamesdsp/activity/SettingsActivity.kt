package me.timschneeberger.rootlessjamesdsp.activity

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.databinding.ActivitySettingsBinding
import me.timschneeberger.rootlessjamesdsp.fragment.settings.SettingsAboutFragment
import me.timschneeberger.rootlessjamesdsp.fragment.settings.SettingsBackupFragment
import me.timschneeberger.rootlessjamesdsp.fragment.settings.SettingsFragment

class SettingsActivity : BaseActivity(),
    PreferenceFragmentCompat.OnPreferenceStartFragmentCallback {

    lateinit var backupLocationSelectLauncher: ActivityResultLauncher<Uri?>
    lateinit var backupSaveFileSelectLauncher: ActivityResultLauncher<String>
    lateinit var backupLoadFileSelectLauncher: ActivityResultLauncher<Array<String>>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // General build: the settings are Compose pages (RnSettingsActivity); every caller lands there.
        if (me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild.general) {
            startActivity(me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral.settingsIntent(this,
                if (intent.getBooleanExtra(EXTRA_ABOUT, false)) "ABOUT" else "ROOT"))
            finish()
            return
        }
        val binding = ActivitySettingsBinding.inflate(layoutInflater)

        setContentView(binding.root)
        setSupportActionBar(binding.settingsToolbar)

        if (savedInstanceState == null && intent.getBooleanExtra(EXTRA_ABOUT, false)) {
            // General build home screen: "About" opens the about page directly (no title, like from the list).
            supportActionBar?.title = ""
            supportFragmentManager
                .beginTransaction()
                .replace(R.id.settings, SettingsAboutFragment())
                .commit()
        }
        else if (savedInstanceState == null) {
            val fragment = SettingsFragment.newInstance()
            @Suppress("DEPRECATION")
            fragment.setTargetFragment(null, 0)

            supportFragmentManager
                .beginTransaction()
                .replace(R.id.settings, fragment)
                .commit()
        }
        else {
            supportActionBar?.title = savedInstanceState.getString(PERSIST_TITLE)
        }

        supportFragmentManager.addOnBackStackChangedListener {
            if (supportFragmentManager.backStackEntryCount == 0) {
                supportActionBar?.title = if (intent.getBooleanExtra(EXTRA_ABOUT, false)) "" else getString(R.string.title_activity_settings)
            }
            else {
                supportActionBar?.title = supportFragmentManager.getBackStackEntryAt(supportFragmentManager.backStackEntryCount - 1).name
            }
        }

        backupLocationSelectLauncher = registerForActivityResult(
            ActivityResultContracts.OpenDocumentTree(),
            ::onBackupLocationSet
        )

        backupSaveFileSelectLauncher = registerForActivityResult(
            ActivityResultContracts.CreateDocument("application/*")
        ) {
            it ?: return@registerForActivityResult
            accessFragment<SettingsBackupFragment> {
                startManualBackup(it)
            }
        }

        backupLoadFileSelectLauncher = registerForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) {
            it ?: return@registerForActivityResult
            accessFragment<SettingsBackupFragment> {
                startManualRestore(it)
            }
        }

        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        binding.settingsToolbar.setNavigationOnClickListener { onBackPressedDispatcher.onBackPressed() }
    }

    private inline fun<reified T> accessFragment(onAccess: T.() -> Unit) {
        val fragment = supportFragmentManager.findFragmentById(R.id.settings)
        if(fragment is T)
            onAccess(fragment)
    }

    private fun onBackupLocationSet(uri: Uri?) {
        accessFragment<SettingsBackupFragment> {
            if (uri != null) {
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                prefsApp.set(R.string.key_backup_location, uri.toString())
                updateSummaries()
            } else {
                resetFrequencyIfLocationUnset()
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString(PERSIST_TITLE, supportActionBar?.title.toString())
        super.onSaveInstanceState(outState)
    }

     override fun onPreferenceStartFragment(caller: PreferenceFragmentCompat, pref: Preference): Boolean {
        // Instantiate the new Fragment
        val args = pref.extras
        val fragment = pref.fragment?.let {
            supportFragmentManager.fragmentFactory.instantiate(
                classLoader,
                it)
        }
        fragment ?: return false

        fragment.arguments = args
        @Suppress("DEPRECATION")
        fragment.setTargetFragment(caller, 0)

        // Set the action bar title; the about page doesn't need one
        val title = if(fragment is SettingsAboutFragment)
            ""
        else
            pref.title.toString()

        // Replace the existing Fragment with the new Fragment
        supportFragmentManager.beginTransaction()
            .setReorderingAllowed(true)
            .replace(R.id.settings, fragment)
            .addToBackStack(title)
            .commit()
        return true
    }

    companion object {
        private const val PERSIST_TITLE = "title"
        /** Open the about page instead of the settings list (general build home screen). */
        const val EXTRA_ABOUT = "open_about"
    }
}


package me.timschneeberger.rootlessjamesdsp.fragment.settings

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceGroup
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.flavor.UpdateManager
import me.timschneeberger.rootlessjamesdsp.model.Translator
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.utils.Result
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.isPlugin
import me.timschneeberger.rootlessjamesdsp.utils.isRoot
import org.koin.android.ext.android.inject
import java.util.Locale


class SettingsAboutFragment : SettingsBaseFragment() {

    private val updateManager: UpdateManager by inject()

    private val version by lazy { findPreference<Preference>(getString(R.string.key_credits_version)) }
    private val buildInfo by lazy { findPreference<Preference>(getString(R.string.key_credits_build_info)) }
    private val googlePlay by lazy { findPreference<Preference>(getString(R.string.key_credits_google_play)) }
    private val selfCheckUpdates by lazy { findPreference<Preference>(getString(R.string.key_credits_check_update)) }
    private val translatorsGroup by lazy { findPreference<PreferenceGroup>(getString(R.string.key_translators)) }

    override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
        setPreferencesFromResource(R.xml.app_about_preferences, rootKey)

        version?.summary = BuildConfig.VERSION_NAME
        buildInfo?.isVisible = BuildConfig.DEBUG || BuildConfig.PREVIEW || isPlugin()
        val type = if(BuildConfig.PREVIEW)
            "Preview"
        else if(BuildConfig.DEBUG)
            "Debug"
        else
            "Release"

        buildInfo?.summary = "$type build (${BuildConfig.FLAVOR_dependencies}) @${BuildConfig.COMMIT_SHA} (compiled at ${BuildConfig.BUILD_TIME})"

        googlePlay?.isVisible = !isRoot()
        selfCheckUpdates?.isVisible = isRoot()
        selfCheckUpdates?.setOnPreferenceClickListener {
            checkForUpdates()
            true
        }

        if (PvbBuild.general) setupGeneral()

        Translator.readLanguageMap(requireContext()).forEach { (cc, tls) ->
            translatorsGroup?.addPreference(Preference(requireContext()).apply {
                val language = Locale.forLanguageTag(cc).getDisplayLanguage(requireContext().resources.configuration.locales[0])
                val region = Locale.forLanguageTag(cc).getDisplayCountry(requireContext().resources.configuration.locales[0])

                isIconSpaceReserved = false
                title = if(region.isNullOrBlank()) language else "$language ($region)"
                summary = tls.joinToString(", ") { it.name }

                setOnPreferenceClickListener {
                    if(tls.size == 1)
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://crowdin.com/profile/${tls[0].username}")))
                    else {
                        this@SettingsAboutFragment.context?.let { ctx ->
                            MaterialAlertDialogBuilder(ctx)
                                .setItems(tls.map { it.name }.toTypedArray()) { dialogInterface, i ->
                                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://crowdin.com/profile/${tls[i].username}")))
                                    dialogInterface.dismiss()
                                }
                                .setTitle(title)
                                .setNegativeButton(getString(android.R.string.cancel)){ _, _ -> }
                                .create()
                                .show()
                        }
                    }
                    true
                }
            })
        }
    }

    /**
     * General build: the fork notice (brand, upstream base, GPL-3.0, source, privacy, third-party licences), the
     * upstream links relabelled as the original project, and the hidden "개발자/연구" unlock on the version entry.
     */
    private fun setupGeneral() {
        val ctx = requireContext()
        val screen = preferenceScreen
        googlePlay?.isVisible = false
        findPreference<Preference>("credits_project_translate")?.isVisible = false
        findPreference<Preference>("credits_project_page")?.apply {
            title = getString(R.string.about_upstream_title)
            summary = "https://github.com/thepbone/RootlessJamesDSP"
        }
        version?.setOnPreferenceClickListener {
            if (PvbGeneral.onVersionTapped(ctx)) researchCategory?.isVisible = true
            true
        }

        fun item(title: CharSequence, summary: CharSequence?, order: Int, click: (() -> Unit)?): Preference {
            val pref = Preference(ctx)
            pref.isIconSpaceReserved = false
            pref.title = title
            pref.summary = summary
            pref.order = order
            pref.isSelectable = click != null
            if (click != null) pref.setOnPreferenceClickListener { click(); true }
            return pref
        }

        // Right below the app icon: shift the inflated entries down by one place.
        val inflated = (0 until screen.preferenceCount).map { screen.getPreference(it) }
        inflated.forEach { if (it.order >= 1) it.order = it.order + 1 }
        val app = PreferenceCategory(ctx).apply {
            title = getString(R.string.about_category_app)
            isIconSpaceReserved = false
            order = 1
        }
        screen.addPreference(app)
        val activity = requireActivity()
        app.addPreference(item(getString(R.string.app_brand_name), getString(R.string.app_subtitle), 0, null))
        app.addPreference(item(getString(R.string.about_based_on_title, BuildConfig.UPSTREAM_VERSION),
            getString(R.string.about_based_on_summary), 1, null))
        app.addPreference(item(getString(R.string.about_license_title), getString(R.string.about_license_summary), 2) {
            PvbGeneral.showAssetText(activity, getString(R.string.about_license_title), "GPL-3.0.txt")
        })
        val source = getString(R.string.source_url)
        app.addPreference(item(getString(R.string.about_source_title), source, 3) { PvbGeneral.openUrl(ctx, source) })
        app.addPreference(item(getString(R.string.about_privacy_title), getString(R.string.about_privacy_summary), 4) {
            PvbGeneral.showPrivacy(activity)
        })
        app.addPreference(item(getString(R.string.about_third_party_title), getString(R.string.about_third_party_summary), 5) {
            PvbGeneral.showThirdPartyLicenses(activity)
        })

        val research = PreferenceCategory(ctx).apply {
            title = getString(R.string.about_research_category)
            isIconSpaceReserved = false
            isVisible = PvbBuild.researchUnlocked
        }
        screen.addPreference(research)
        // Developer mode (general build): reachable once the research tools are shown.
        if (PvbBuild.general) research.addPreference(item(getString(R.string.pvb_dev_mode),
            getString(R.string.pvb_dev_mode_summary), -1) { PvbGeneral.openDevMode(activity) })
        research.addPreference(item(getString(R.string.about_research_hide_title),
            getString(R.string.about_research_hide_summary), 0) {
            PvbGeneral.setResearchUnlocked(ctx, false)
            research.isVisible = false
        })
        researchCategory = research
    }

    private var researchCategory: PreferenceCategory? = null

    private fun checkForUpdates() {
        if(!isRoot())
            return

        CoroutineScope(Dispatchers.Default).launch {
            updateManager.isUpdateAvailable().collect {
                when(it) {
                    is Result.Success -> it.data
                    else -> false
                }.let { hasUpdate ->
                    withContext(Dispatchers.Main) {
                        if (hasUpdate)
                            updateManager.installUpdate(requireActivity())
                        else
                            context?.toast(getString(R.string.self_update_no_updates))
                    }
                }
            }
        }
    }

    companion object {
        fun newInstance(): SettingsAboutFragment {
            return SettingsAboutFragment()
        }
    }
}
package me.timschneeberger.rootlessjamesdsp.settings

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.model.Translator
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.DevShareCode
import me.timschneeberger.rootlessjamesdsp.pvb.SettingsSummary
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnChoice
import me.timschneeberger.rootlessjamesdsp.ui.RnChoiceSheet
import me.timschneeberger.rootlessjamesdsp.ui.RnDialog
import me.timschneeberger.rootlessjamesdsp.ui.RnEndSpace
import me.timschneeberger.rootlessjamesdsp.ui.RnNavRow
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnSectionTitle
import java.util.Locale

/**
 * "앱 정보" (the general build's About; legacy SettingsAboutFragment + setupGeneral): the app icon and name, "이 앱에
 * 대해" (fork notice, upstream base, GPL-3.0, source, privacy, third-party licences), the version (7 taps show the
 * developer/research tools), the original project, credits and translators, and "개발자/연구" once unlocked.
 * Licence texts and the privacy summary open in the kit's dialogs instead of the legacy ones.
 */
@Composable
fun AboutPage(host: RnSettingsActivity) {
    val c = LocalRn.current
    var research by remember { mutableStateOf(PvbBuild.researchUnlocked) }
    var assetText by remember { mutableStateOf<Pair<String, String>?>(null) }
    var privacy by remember { mutableStateOf(false) }
    var summaryShown by remember { mutableStateOf<Pair<String, String>?>(null) }
    var thirdParty by remember { mutableStateOf(false) }
    var translatorPick by remember { mutableStateOf<Pair<String, List<Translator>>?>(null) }
    val translators = remember { Translator.readLanguageMap(host) }
    val icon = remember { host.packageManager.getApplicationIcon(host.applicationInfo).toBitmap(192, 192).asImageBitmap() }
    fun openUrl(url: String) = PvbGeneral.openUrl(host, url)
    fun showAsset(title: String, file: String) {
        val text = try { host.assets.open("licenses/$file").bufferedReader().use { it.readText() } } catch (_: Exception) { "" }
        assetText = title to text
    }
    RnPage(stringResource(R.string.home_about_title), onBack = host::finish) {
        Column(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 16.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Image(icon, contentDescription = null, modifier = Modifier.size(64.dp))
            Text(stringResource(R.string.app_brand_name), color = c.textPrimary, fontSize = 22.sp, lineHeight = 30.sp,
                fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, modifier = Modifier.semantics { heading() })
            Text(stringResource(R.string.app_subtitle), color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp,
                modifier = Modifier.padding(horizontal = 32.dp))
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.about_category_app))
        RnNavRow(stringResource(R.string.about_based_on_title, BuildConfig.UPSTREAM_VERSION), stringResource(R.string.about_based_on_summary), onClick = null)
        val licenseTitle = stringResource(R.string.about_license_title)
        RnNavRow(licenseTitle, stringResource(R.string.about_license_summary)) { showAsset(licenseTitle, "GPL-3.0.txt") }
        val source = stringResource(R.string.source_url)
        RnNavRow(stringResource(R.string.about_source_title), source) { openUrl(source) }
        RnNavRow(stringResource(R.string.about_privacy_title), stringResource(R.string.about_privacy_summary)) { privacy = true }
        val copied = stringResource(R.string.about_copy_settings_done)
        RnNavRow(stringResource(R.string.about_copy_settings_title), stringResource(R.string.about_copy_settings_summary)) {
            val s = PvbSettings.load(host.getSharedPreferences(PvbSettings.PREFS_NAME, android.content.Context.MODE_PRIVATE))
            val values = DevParams.read(s)
            val code = DevShareCode.encode(android.os.Build.MODEL ?: "", BuildConfig.VERSION_NAME, values,
                DevParams.defaults(PvbGeneral.profile(host).settings))
            val text = SettingsSummary.text(s, android.os.Build.MODEL ?: "", BuildConfig.VERSION_NAME, code)
            (host.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager)
                ?.setPrimaryClip(android.content.ClipData.newPlainText("Rootnote", text))
            summaryShown = copied to text
        }
        RnNavRow(stringResource(R.string.about_third_party_title), stringResource(R.string.about_third_party_summary)) { thirdParty = true }
        RnNavRow(stringResource(R.string.credits_version), BuildConfig.VERSION_NAME, chevron = false) {
            if (PvbGeneral.onVersionTapped(host)) research = true
        }
        RnBand()
        RnSectionTitle(stringResource(R.string.credits))
        RnNavRow(stringResource(R.string.about_upstream_title), "https://github.com/thepbone/RootlessJamesDSP") {
            openUrl("https://github.com/thepbone/RootlessJamesDSP")
        }
        RnNavRow(stringResource(R.string.credits_app), "Tim Schneeberger (@thepbone)") { openUrl("https://github.com/thepbone") }
        RnNavRow(stringResource(R.string.credits_dsp), "James Fung (@james34602)") { openUrl("https://github.com/james34602") }
        if (translators.isNotEmpty()) {
            RnBand()
            RnSectionTitle(stringResource(R.string.translators))
            val locale = host.resources.configuration.locales[0]
            for ((cc, list) in translators) {
                val tag = Locale.forLanguageTag(cc)
                val region = tag.getDisplayCountry(locale)
                val name = tag.getDisplayLanguage(locale).let { if (region.isNullOrBlank()) it else "$it ($region)" }
                RnNavRow(name, list.joinToString(", ") { it.name }) {
                    if (list.size == 1) openUrl("https://crowdin.com/profile/${list[0].username}") else translatorPick = name to list
                }
            }
        }
        if (research && PvbBuild.general) {
            RnBand()
            RnSectionTitle(stringResource(R.string.about_research_category))
            RnNavRow(stringResource(R.string.pvb_dev_mode), stringResource(R.string.pvb_dev_mode_summary)) { PvbGeneral.openDevMode(host) }
            RnNavRow(stringResource(R.string.about_research_hide_title), stringResource(R.string.about_research_hide_summary), chevron = false) {
                PvbGeneral.setResearchUnlocked(host, false)
                research = false
            }
        }
        RnEndSpace()
    }

    assetText?.let { (title, text) ->
        RnDialog(title, "", onConfirm = { assetText = null }) {
            SelectionContainer {
                Text(text, color = c.textPrimary, fontSize = 12.sp, lineHeight = 16.sp)
            }
        }
    }
    summaryShown?.let { (title, text) ->
        RnDialog(title, "", onConfirm = { summaryShown = null }) {
            SelectionContainer {
                Text(text, color = c.textPrimary, fontSize = 12.sp, lineHeight = 16.sp)
            }
        }
    }
    if (privacy) {
        val source = stringResource(R.string.source_url)
        RnDialog(stringResource(R.string.about_privacy_title), stringResource(R.string.privacy_summary, stringResource(R.string.app_brand_name)),
            onConfirm = { privacy = false }, neutralLabel = stringResource(R.string.privacy_full_text),
            onNeutral = { openUrl("$source/blob/main/PRIVACY.md") })
    }
    if (thirdParty) {
        RnChoiceSheet(
            stringResource(R.string.about_third_party_title),
            PvbGeneral.THIRD_PARTY.mapIndexed { i, (name, license, _) -> RnChoice(i, name, license) },
            selected = null, onDismiss = { thirdParty = false },
        ) { i ->
            val (name, license, file) = PvbGeneral.THIRD_PARTY[i]
            thirdParty = false
            showAsset("$name · $license", file)
        }
    }
    translatorPick?.let { (title, list) ->
        RnChoiceSheet(title, list.mapIndexed { i, t -> RnChoice(i, t.name) }, selected = null, onDismiss = { translatorPick = null }) { i ->
            translatorPick = null
            host.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://crowdin.com/profile/${list[i].username}")))
        }
    }
}


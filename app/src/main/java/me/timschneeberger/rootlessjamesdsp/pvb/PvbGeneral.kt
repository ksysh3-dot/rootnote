package me.timschneeberger.rootlessjamesdsp.pvb

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.widget.Toast
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import timber.log.Timber
import java.lang.ref.WeakReference

/**
 * Android side of the general distribution build: build flags, device profile, first-run notice, the hidden
 * "개발자/연구" unlock and the About-screen texts. In the s26u build [init] only copies the flags and nothing else
 * here changes behaviour.
 */
object PvbGeneral {
    /** App flags (not settings). Excluded from backup like every pvb_* file. */
    const val FLAGS_PREFS = "pvb_flags"
    const val KEY_RESEARCH_UNLOCKED = "research_unlocked"
    const val KEY_UNMEASURED_NOTICE_SHOWN = "unmeasured_notice_shown"
    const val UNLOCK_TAPS = 7

    @Volatile private var profile: DeviceProfile? = null

    fun flags(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences(FLAGS_PREFS, Context.MODE_PRIVATE)

    /** Called first thing in MainApplication.onCreate (every process). */
    fun init(context: Context) {
        PvbBuild.general = BuildConfig.GENERAL_BUILD
        PvbBuild.researchUiBuild = BuildConfig.RESEARCH_UI
        PvbBuild.recordFeatures = BuildConfig.RECORD_FEATURES
        val f = flags(context)
        PvbBuild.researchUnlocked = f.getBoolean(KEY_RESEARCH_UNLOCKED, false)
        PvbBuild.firstRunConfirmed = f.getBoolean(FirstRun.KEY_CONFIRMED, false)
        if (PvbBuild.general) applyProfileOnce(context)
    }

    /** The device profile of this phone (general build), read from the assets once. */
    fun profile(context: Context): DeviceProfile {
        profile?.let { return it }
        val assets = context.applicationContext.assets
        val list = try {
            assets.list(DeviceProfiles.ASSET_DIR).orEmpty().filter { it.endsWith(".json") }.mapNotNull { name ->
                try {
                    assets.open("${DeviceProfiles.ASSET_DIR}/$name").bufferedReader().use { DeviceProfiles.parse(it.readText()) }
                } catch (e: Exception) {
                    Timber.e(e, "Bad device profile $name"); null
                }
            }
        } catch (e: Exception) {
            Timber.e(e); emptyList()
        }
        val selected = try {
            DeviceProfiles.select(list, Build.MANUFACTURER, Build.MODEL)
        } catch (e: IllegalStateException) {
            // No asset at all (should not happen): neutral values built in, nothing written beyond processing off.
            DeviceProfile(DeviceProfiles.NEUTRAL, "Neutral", false, emptyList(), emptyList(), emptyMap(), false)
        }
        profile = selected
        return selected
    }

    /** True when the S26U-specific displays (speaker response, phone limiter estimate) apply to this phone. */
    fun phoneModelCurves(context: Context): Boolean = !PvbBuild.general || profile(context).phoneModelCurves

    /** Unmeasured phone in the general build (status line and the one-time notice). */
    fun unmeasured(context: Context): Boolean = PvbBuild.general && !profile(context).measured

    /** Writes the profile into pvb_settings once (fresh install); later changes are the user's. */
    private fun applyProfileOnce(context: Context) {
        val prefs = context.applicationContext.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        if (prefs.contains(DeviceProfiles.KEY_PROFILE_ID)) return
        val p = profile(context)
        val edit = prefs.edit()
        for ((k, v) in DeviceProfiles.valuesFor(p, PvbBuild.caps)) {
            when (v) {
                is Float -> edit.putFloat(k, v)
                is Boolean -> edit.putBoolean(k, v)
                is String -> edit.putString(k, v)
            }
        }
        edit.commit()
        Timber.i("Applied PVB device profile ${p.id} (${Build.MANUFACTURER} ${Build.MODEL})")
    }

    fun confirmFirstRun(context: Context) {
        flags(context).edit().putBoolean(FirstRun.KEY_CONFIRMED, true).commit()
        PvbBuild.firstRunConfirmed = true
        val prefs = context.applicationContext.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE)
        val edit = prefs.edit()
        FirstRun.valuesOnConfirm().forEach { (k, v) -> if (v is Boolean) edit.putBoolean(k, v) }
        edit.apply()
    }

    fun setResearchUnlocked(context: Context, unlocked: Boolean) {
        flags(context).edit().putBoolean(KEY_RESEARCH_UNLOCKED, unlocked).apply()
        PvbBuild.researchUnlocked = unlocked
    }

    private var taps = 0

    /** The About screen's version entry: 7 taps show the "개발자/연구" section (like Android developer options). */
    fun onVersionTapped(context: Context): Boolean {
        if (PvbBuild.researchUiBuild) return false
        if (PvbBuild.researchUnlocked) {
            Toast.makeText(context, R.string.research_already_shown, Toast.LENGTH_SHORT).show()
            return false
        }
        taps++
        val left = UNLOCK_TAPS - taps
        return when {
            left <= 0 -> {
                taps = 0
                setResearchUnlocked(context, true)
                Toast.makeText(context, R.string.research_unlocked, Toast.LENGTH_SHORT).show()
                true
            }
            left <= 3 -> {
                Toast.makeText(context, context.getString(R.string.research_taps_left, left), Toast.LENGTH_SHORT).show()
                false
            }
            else -> false
        }
    }

    fun brand(context: Context): String = context.getString(R.string.app_brand_name)

    /**
     * The general build's home screen (src/general, Compose). Named by string so the s26u build, which does not
     * contain the class, still compiles; it is only used when [PvbBuild.general] is true.
     */
    const val HOME_ACTIVITY = "me.timschneeberger.rootlessjamesdsp.home.HomeActivity"

    /**
     * Where the app opens: the home screen in the general build, the DSP screen (MainActivity) in the s26u build.
     * Used by the onboarding end, the service notification and the tile's first-run redirect.
     */
    fun homeIntent(context: Context): Intent =
        if (PvbBuild.general) Intent().setClassName(context.packageName, HOME_ACTIVITY)
        else Intent(context, me.timschneeberger.rootlessjamesdsp.activity.MainActivity::class.java)

    /** Developer mode screen of the general build (src/general, Compose); named by string like [HOME_ACTIVITY]. */
    const val DEVMODE_ACTIVITY = "me.timschneeberger.rootlessjamesdsp.devmode.DevModeActivity"
    /** pvb_flags: developer-mode consent given, gauge style, warning counts and hidden warnings. */
    const val KEY_DEV_CONSENT = "dev_consent"
    const val KEY_DEV_GAUGE_VU = "dev_gauge_vu"

    /** Developer mode is offered: general build, research tools unlocked. */
    val devModeAvailable: Boolean get() = PvbBuild.general && PvbBuild.researchUnlocked

    fun openDevMode(context: Context) {
        if (!PvbBuild.general) return
        try {
            context.startActivity(Intent().setClassName(context.packageName, DEVMODE_ACTIVITY))
        } catch (e: Exception) {
            Timber.e(e)
        }
    }

    private var noticeDialog: WeakReference<androidx.appcompat.app.AlertDialog>? = null

    /**
     * The first-run notice of the general build. [onConfirmed] runs after the user confirmed it. Only one notice is
     * shown at a time (the first caller's continuation wins).
     */
    fun showFirstRunNotice(activity: Activity, onConfirmed: () -> Unit, onLater: () -> Unit = {}) {
        if (noticeDialog?.get()?.isShowing == true) return
        val ctx = activity
        val commands = FirstRun.adbCommands(BuildConfig.APPLICATION_ID).joinToString("\n")
        MaterialAlertDialogBuilder(ctx)
            .setTitle(R.string.first_run_title)
            .setMessage(ctx.getString(R.string.first_run_message, brand(ctx), BuildConfig.APPLICATION_ID, commands))
            .setCancelable(false)
            .setPositiveButton(R.string.first_run_confirm) { _, _ ->
                confirmFirstRun(ctx)
                onConfirmed()
            }
            .setNegativeButton(R.string.first_run_later) { _, _ -> onLater() }
            .setNeutralButton(R.string.about_privacy_title) { _, _ ->
                showPrivacy(activity) { showFirstRunNotice(activity, onConfirmed, onLater) }
            }
            .show()
            .also { noticeDialog = WeakReference(it) }
    }

    /** One-time notice for a phone without a measured profile (general build). */
    fun maybeShowUnmeasuredNotice(activity: Activity) {
        if (!unmeasured(activity) || !PvbBuild.firstRunConfirmed) return
        val f = flags(activity)
        if (f.getBoolean(KEY_UNMEASURED_NOTICE_SHOWN, false)) return
        f.edit().putBoolean(KEY_UNMEASURED_NOTICE_SHOWN, true).apply()
        MaterialAlertDialogBuilder(activity)
            .setTitle(R.string.unmeasured_title)
            .setMessage(activity.getString(R.string.unmeasured_message, brand(activity), "${Build.MANUFACTURER} ${Build.MODEL}"))
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }

    fun showPrivacy(activity: Activity, after: (() -> Unit)? = null) {
        MaterialAlertDialogBuilder(activity)
            .setTitle(R.string.about_privacy_title)
            .setMessage(activity.getString(R.string.privacy_summary, brand(activity)))
            .setPositiveButton(android.R.string.ok) { _, _ -> after?.invoke() }
            .setNeutralButton(R.string.privacy_full_text) { _, _ ->
                openUrl(activity, activity.getString(R.string.source_url) + "/blob/main/PRIVACY.md")
                after?.invoke()
            }
            .setCancelable(false)
            .show()
    }

    fun openUrl(context: Context, url: String) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: Exception) {
            Toast.makeText(context, R.string.no_activity_found, Toast.LENGTH_SHORT).show()
        }
    }

    /** A licence or notice text from assets/licenses (general build). */
    fun showAssetText(activity: Activity, title: CharSequence, asset: String) {
        val text = try {
            activity.assets.open("licenses/$asset").bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            Timber.e(e); asset
        }
        MaterialAlertDialogBuilder(activity)
            .setTitle(title)
            .setMessage(text)
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }

    /** Third-party licences: a list of components; each opens its licence text. */
    fun showThirdPartyLicenses(activity: Activity) {
        val items = THIRD_PARTY.map { "${it.first}\n${it.second}" }.toTypedArray<CharSequence>()
        MaterialAlertDialogBuilder(activity)
            .setTitle(R.string.about_third_party_title)
            .setItems(items) { _, which ->
                val (name, license, file) = THIRD_PARTY[which]
                showAssetText(activity, "$name · $license", file)
            }
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }

    /** Component, licence, asset file. Kept in step with app/build.gradle.kts dependencies (fdroid flavor). */
    val THIRD_PARTY: List<Triple<String, String, String>> = listOf(
        Triple("RootlessJamesDSP (Tim Schneeberger)", "GPL-3.0", "GPL-3.0.txt"),
        Triple("JamesDSP / libjamesdsp (James Fung)", "GPL-3.0", "GPL-3.0.txt"),
        Triple("libsamplerate (Erik de Castro Lopo)", "BSD-2-Clause", "libsamplerate-BSD-2-Clause.txt"),
        Triple("dr_libs: dr_wav, dr_flac, dr_mp3 (David Reid)", "Public domain / MIT-0", "THIRD_PARTY.txt"),
        Triple("JetBrains Mono font", "SIL OFL 1.1", "OFL-1.1.txt"),
        Triple("AndroidX (incl. Jetpack Compose), Material Components", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Kotlin, kotlinx.coroutines, kotlinx.serialization", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Koin", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Retrofit, OkHttp, Okio (Square)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Gson (Google)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Timber (Jake Wharton)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Treessence", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Shizuku API (RikkaApps)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("Refine, HiddenApiBypass (RikkaApps, LSPosed)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("UniFile (Tachiyomi)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("jtar (Kamran Zafar)", "Apache-2.0", "Apache-2.0.txt"),
        Triple("CodeView (AmrDeveloper)", "MIT", "THIRD_PARTY.txt"),
        Triple("Pluto (no-op in release)", "Apache-2.0", "Apache-2.0.txt"),
    )
}

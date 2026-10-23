package me.timschneeberger.rootlessjamesdsp.home

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.drawable.ColorDrawable
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.HapticFeedbackConstants
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.BaseActivity
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission

/**
 * "반가워요": the first-run notice of the general build as six full-screen pages (WelcomeScreen.kt). It replaces the old
 * first-run dialog and carries the same consent: "확인하고 시작하기" confirms it (PvbGeneral.confirmFirstRun turns
 * processing and virtual bass on, at the profile's strength) and, since the first page already said how this phone
 * starts, the separate "not measured" notice is marked shown.
 *
 * Two ways in:
 * - [thenSetup]: the first launch with permissions missing (HomeActivity). Either answer goes on to the setup
 *   screens (OnboardingActivity), like the old dialog; back on the first page closes the app.
 * - for a result (PvbGeneral.showFirstRunNotice, from the home screen, the DSP screen or the switch): RESULT_OK when
 *   confirmed, RESULT_CANCELED for "나중에" or back. "나중에" is remembered for the process
 *   (PvbGeneral.welcomeLater): the home screen stops opening the welcome by itself, and the next time it opens (when
 *   processing is switched on) it opens on the last page.
 */
class WelcomeActivity : BaseActivity() {
    private var reduceMotion by mutableStateOf(false)
    private var thenSetup = false
    private var answered = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        PvbGeneral.welcomeOpen = true
        thenSetup = intent.getBooleanExtra(EXTRA_THEN_SETUP, false)
        window.setBackgroundDrawable(ColorDrawable(ContextCompat.getColor(this, R.color.rn_bg)))
        val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply {
            isAppearanceLightStatusBars = !night
            isAppearanceLightNavigationBars = !night
        }
        val profile = PvbGeneral.profile(this)
        val base = WelcomeState(
            measuredName = if (profile.measured) profile.name else null,
            permissionsReady = hasDumpPermission() && hasRecordPermission(),
            consentEveryTime = SdkCheck.isUpsideDownCake,
            screenShareSetting = SdkCheck.isVanillaIceCream,
            initialPage = if (intent.getBooleanExtra(PvbGeneral.EXTRA_WELCOME_AT_CONSENT, false)) WELCOME_LAST_PAGE else 0,
        )
        val actions = WelcomeActions(
            onStart = { answer(confirmed = true) },
            onLater = { answer(confirmed = false) },
            onLeave = { leave() },
            onPrivacy = { PvbGeneral.showPrivacy(this) },
            onLicense = { PvbGeneral.showAssetText(this, getString(R.string.about_license_title), "GPL-3.0.txt") },
        )
        setContent {
            WelcomeScreen(base.copy(reduceMotion = reduceMotion), actions)
        }
    }

    override fun onResume() {
        super.onResume()
        reduceMotion = try {
            Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        } catch (_: Exception) { false }
    }

    override fun onDestroy() {
        if (isFinishing) PvbGeneral.welcomeOpen = false
        super.onDestroy()
    }

    private fun answer(confirmed: Boolean) {
        if (answered) return
        answered = true
        if (confirmed) {
            // starting turns processing on: the same feel as the home screen's switch turning it on
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
                window.decorView.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
            PvbGeneral.confirmFirstRun(this)
            PvbGeneral.markUnmeasuredNoticeShown(this)
        } else {
            PvbGeneral.welcomeLater = true
        }
        if (thenSetup) {
            startActivity(Intent(this, OnboardingActivity::class.java).apply {
                putExtra(OnboardingActivity.EXTRA_FIX_PERMS, intent.getBooleanExtra(EXTRA_FIX_PERMS, false))
            })
        } else {
            setResult(if (confirmed) RESULT_OK else RESULT_CANCELED)
        }
        finish()
    }

    /** Back on the first page: the first launch closes the app (the welcome comes again next time); else "나중에". */
    private fun leave() {
        if (thenSetup) finish() else answer(confirmed = false)
    }

    companion object {
        private const val EXTRA_THEN_SETUP = "then_setup"
        private const val EXTRA_FIX_PERMS = "fix_perms"

        /** First launch with permissions missing: the welcome, then the setup screens. */
        fun thenSetup(context: Context, fixPerms: Boolean): Intent =
            Intent(context, WelcomeActivity::class.java)
                .putExtra(EXTRA_THEN_SETUP, true)
                .putExtra(EXTRA_FIX_PERMS, fixPerms)
                .putExtra(PvbGeneral.EXTRA_WELCOME_AT_CONSENT, PvbGeneral.welcomeLater)
    }
}

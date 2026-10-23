package me.timschneeberger.rootlessjamesdsp.setup

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager.PERMISSION_GRANTED
import android.os.Build
import android.os.Bundle
import android.os.Process.myUid
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import me.timschneeberger.hiddenapi_impl.ShizukuSystemServerApi
import me.timschneeberger.hiddenapi_impl.UserHandle
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.MainActivity
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeek
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.isPackageInstalled
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.launchApp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.openPlayStoreApp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasNotificationPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasProjectMediaAppOp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission
import rikka.shizuku.Shizuku
import timber.log.Timber

/**
 * The setup steps of the general build in Compose (replaces OnboardingFragment there for the rootless setup; root
 * and the s26u build keep the legacy wizard). The general build never shows the welcome, limitation and "ready" pages
 * (FirstWeek: the welcome screen carries them), so the steps are: setup method, Shizuku or ADB, runtime permissions,
 * battery. Each step is skipped when already done; the same page numbers, skip rules, Shizuku grants and checks as the
 * legacy fragment.
 *
 * Extras (OnboardingActivity's): [OnboardingActivity.EXTRA_FIX_PERMS] (a permission was revoked: a notice first),
 * [OnboardingActivity.EXTRA_ROOTLESS_REDO_ADB_SETUP] (method and ADB pages only; finishing just closes) and
 * [OnboardingActivity.EXTRA_BATTERY_SETUP] (the battery page only, from the home screen's banner).
 */
class RnSetupActivity : RnActivity() {

    enum class Method { None, Shizuku, Adb }

    /** The page shown (PAGE_*). */
    var page by mutableIntStateOf(PAGE_METHOD_SELECT)
        private set
    /** True when the last page change went forward (the slide direction). */
    var forward by mutableStateOf(true)
        private set
    var method by mutableStateOf(Method.None)
        private set
    var shizukuAlive by mutableStateOf(false)
        private set
    /** Back from Shizuku, the store or the battery settings: pages re-read installed and exempt states. */
    var resumeTick by mutableIntStateOf(0)
        private set
    /** A message dialog (title, text). */
    var alert by mutableStateOf<Pair<Int, Int>?>(null)
    /** Where to get Shizuku (Play Store or GitHub releases; nothing is downloaded here). */
    var shizukuSources by mutableStateOf(false)
    /** Shizuku is older than v11: offer the update. */
    var shizukuTooOld by mutableStateOf(false)

    var redoAdbSetup = false
        private set
    var batteryOnly = false
        private set
    private var startPage = PAGE_METHOD_SELECT
    /** Pages of this run (the redo setup has only the method and ADB pages). */
    private var pageCount = PAGE_READY

    private lateinit var runtimePermissionLauncher: ActivityResultLauncher<Array<String>>

    private val binderReceivedListener = Shizuku.OnBinderReceivedListener {
        Timber.d("Shizuku binder received")
        shizukuAlive = true
    }
    private val binderDeadListener = Shizuku.OnBinderDeadListener {
        Timber.d("Shizuku binder died")
        shizukuAlive = false
    }
    private val permissionResultListener = Shizuku.OnRequestPermissionResultListener { requestCode, grantResult ->
        if (grantResult == PERMISSION_GRANTED) {
            if (requestCode == REQUEST_CODE_SHIZUKU_GRANT) changePage(true)
        } else showDeniedMessage()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        redoAdbSetup = intent.getBooleanExtra(OnboardingActivity.EXTRA_ROOTLESS_REDO_ADB_SETUP, false)
        batteryOnly = intent.getBooleanExtra(OnboardingActivity.EXTRA_BATTERY_SETUP, false)

        runtimePermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
            if (granted.all { it.value }) {
                if (page == PAGE_RUNTIME_PERMISSIONS) changePage(forward = true, ignoreConditions = true)
            } else alert = R.string.onboarding_perm_missing_title to R.string.onboarding_perm_missing
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = back()
        })

        if (redoAdbSetup) pageCount = PAGE_ADB_SETUP

        if (savedInstanceState != null) {
            startPage = savedInstanceState.getInt(STATE_START, startPage)
            page = savedInstanceState.getInt(STATE_PAGE, startPage)
            method = Method.entries.getOrElse(savedInstanceState.getInt(STATE_METHOD, 0)) { Method.None }
        } else when {
            redoAdbSetup -> { startPage = PAGE_METHOD_SELECT; page = PAGE_METHOD_SELECT }
            batteryOnly -> { startPage = PAGE_BATTERY; page = PAGE_BATTERY }
            else -> {
                // the welcome screen was the first page: open on the first step that is still needed
                startPage = requestNextPage(PAGE_WELCOME, true)
                if (startPage > pageCount) {
                    finishSetup()
                    return
                }
                page = startPage
            }
        }

        if (intent.getBooleanExtra(OnboardingActivity.EXTRA_FIX_PERMS, false) && savedInstanceState == null)
            alert = R.string.onboarding_fix_permissions_title to R.string.onboarding_fix_permissions

        Shizuku.addBinderReceivedListenerSticky(binderReceivedListener)
        Shizuku.addBinderDeadListener(binderDeadListener)
        Shizuku.addRequestPermissionResultListener(permissionResultListener)

        setRnContent { SetupScreen(this) }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putInt(STATE_PAGE, page)
        outState.putInt(STATE_START, startPage)
        outState.putInt(STATE_METHOD, method.ordinal)
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        resumeTick++
    }

    override fun onDestroy() {
        Shizuku.removeBinderReceivedListener(binderReceivedListener)
        Shizuku.removeBinderDeadListener(binderDeadListener)
        Shizuku.removeRequestPermissionResultListener(permissionResultListener)
        super.onDestroy()
    }

    // ------------------------------------------------------------------------------------------------ navigation

    /** Back stays in the steps while there is one to go back to; otherwise it leaves. */
    val canGoBack: Boolean
        get() = when {
            batteryOnly || page == startPage -> false
            redoAdbSetup -> true
            else -> requestNextPage(page - 1, false) >= PAGE_METHOD_SELECT
        }

    /** The next button finishes: no further page would be shown. */
    val isLastPage: Boolean
        get() = batteryOnly || requestNextPage(page + 1, true) > pageCount

    fun back() {
        if (canGoBack) changePage(false) else finish()
    }

    fun next() = changePage(true)

    fun chooseMethod(m: Method) {
        method = m
        changePage(true)
    }

    private fun changePage(forward: Boolean, ignoreConditions: Boolean = false) {
        // the battery page opened from the home screen: done (or back) returns there
        if (batteryOnly) {
            finish()
            return
        }
        val nextIndex = if (forward) requestNextPage(page + 1, true) else requestNextPage(page - 1, false)
        if (nextIndex < 1) return
        if (forward && !ignoreConditions && !canAccessNextPage(page)) return
        // the redo setup has no pages before the method page
        if (redoAdbSetup && !forward && page - 1 < PAGE_METHOD_SELECT) {
            finish()
            return
        }
        goToPage(nextIndex, forward)
    }

    private fun goToPage(number: Int, forward: Boolean) {
        if (number > pageCount) {
            finishSetup()
            return
        }
        this.forward = forward
        page = number
    }

    private fun areAdbPermissionsGranted(): Boolean =
        // Android 15+ doesn't allow keyguard recording without PROJECT_MEDIA
        hasDumpPermission() && hasProjectMediaAppOp()

    private fun requestNextPage(nextPage: Int, forward: Boolean): Int {
        val skip = when {
            // pages the general build never shows (the redo setup keeps its own page set)
            !redoAdbSetup && pageOf(nextPage)?.let { it in FirstWeek.skippedAlways(true) } == true -> true
            nextPage == PAGE_METHOD_SELECT || nextPage == PAGE_ADB_SETUP -> areAdbPermissionsGranted() && !redoAdbSetup
            nextPage == PAGE_RUNTIME_PERMISSIONS -> hasNotificationPermission() && hasRecordPermission()
            nextPage == PAGE_BATTERY -> !batteryOnly &&
                !FirstWeek.batteryStepNeeded(true, FirstWeekStore.isIgnoringBatteryOptimizations(this))
            else -> false
        }
        if (!skip) return nextPage
        // out of range on either side: nothing left to show
        if (nextPage < PAGE_WELCOME || nextPage > PAGE_READY) return nextPage
        return requestNextPage(if (forward) nextPage + 1 else nextPage - 1, forward)
    }

    private fun canAccessNextPage(current: Int): Boolean = when (current) {
        PAGE_ADB_SETUP -> ensureAdbPermissions()
        PAGE_RUNTIME_PERMISSIONS -> ensureRuntimePermissions()
        else -> true
    }

    /** DUMP and PROJECT_MEDIA: already granted, or granted now through Shizuku; else what is missing is shown. */
    private fun ensureAdbPermissions(): Boolean {
        // redoing the setup with Shizuku runs the grants again (they include optional ones)
        if (areAdbPermissionsGranted() && (!redoAdbSetup || method != Method.Shizuku)) return true

        if (shizukuAlive && Shizuku.checkSelfPermission() == PERMISSION_GRANTED) {
            val pkg = packageName
            val uid = myUid()
            Timber.d("Granting DUMP via Shizuku (uid ${Shizuku.getUid()}) for $pkg")
            ShizukuSystemServerApi.PermissionManager_grantRuntimePermission(pkg, Manifest.permission.DUMP, UserHandle.USER_SYSTEM)
            try {
                ShizukuSystemServerApi.PermissionManager_grantRuntimePermission(pkg, Manifest.permission.SYSTEM_ALERT_WINDOW,
                    UserHandle.USER_SYSTEM)
            } catch (ex: Exception) {
                Timber.e(ex)
            }
            try {
                ShizukuSystemServerApi.AppOpsService_setMode(ShizukuSystemServerApi.APP_OPS_OP_SYSTEM_ALERT_WINDOW, uid, pkg,
                    ShizukuSystemServerApi.APP_OPS_MODE_ALLOW)
            } catch (ex: Exception) {
                Timber.e(ex)
                ShizukuSystemServerApi.exec("appops set $pkg SYSTEM_ALERT_WINDOW allow")
            }
            try {
                ShizukuSystemServerApi.AppOpsService_setMode(ShizukuSystemServerApi.APP_OPS_OP_PROJECT_MEDIA, uid, pkg,
                    ShizukuSystemServerApi.APP_OPS_MODE_ALLOW)
            } catch (ex: Exception) {
                Timber.e(ex)
                ShizukuSystemServerApi.exec("appops set $pkg PROJECT_MEDIA allow")
            }
            if (areAdbPermissionsGranted()) return true
            alert = R.string.onboarding_adb_shizuku_no_dump_perm_title to R.string.onboarding_adb_shizuku_no_dump_perm
            return false
        }

        when {
            !hasDumpPermission() -> alert = R.string.onboarding_adb_not_granted_title to R.string.onboarding_adb_dump_permission_not_granted
            !hasProjectMediaAppOp() -> alert = R.string.onboarding_adb_not_granted_title to R.string.onboarding_adb_project_media_not_granted
        }
        return false
    }

    private fun ensureRuntimePermissions(): Boolean {
        val requested = arrayListOf<String>()
        if (!hasRecordPermission()) requested += Manifest.permission.RECORD_AUDIO
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasNotificationPermission())
            requested += Manifest.permission.POST_NOTIFICATIONS
        if (requested.isEmpty()) return true
        runtimePermissionLauncher.launch(requested.toTypedArray())
        return false
    }

    private fun finishSetup() {
        if (!redoAdbSetup) {
            // the home screen asks for capture right away
            startActivity(PvbGeneral.homeIntent(this).putExtra(MainActivity.EXTRA_FORCE_SHOW_CAPTURE_PROMPT, true))
        }
        prefsVar.set(R.string.key_first_boot, false)
        finish()
    }

    // ------------------------------------------------------------------------------------------------ Shizuku and ADB

    val shizukuInstalled: Boolean get() = isPackageInstalled(SHIZUKU_PKG)

    /** The method page's button: opens Shizuku, or shows where to get it. */
    fun openShizuku() {
        if (!launchApp(SHIZUKU_PKG)) shizukuSources = true
    }

    fun openPlayStore() = openPlayStoreApp(SHIZUKU_PKG)

    fun openShizukuReleases() = PvbGeneral.openUrl(this, SHIZUKU_RELEASES_URL)

    fun openDeveloperSettings() {
        try {
            startActivity(Intent("android.settings.APPLICATION_DEVELOPMENT_SETTINGS"))
        } catch (_: ActivityNotFoundException) {
            toast(getString(R.string.no_activity_found))
        }
    }

    /** Step 3 of the Shizuku setup: ask Shizuku for its permission (the grants run on "next"). */
    fun grantViaShizuku() {
        if (!shizukuInstalled) {
            shizukuSources = true
            return
        }
        if (!shizukuAlive) {
            alert = R.string.onboarding_adb_shizuku_grant_fail_server_dead_title to R.string.onboarding_adb_shizuku_grant_fail_server_dead
            return
        }
        if (Shizuku.isPreV11()) {
            shizukuTooOld = true
            return
        }
        if (checkShizukuPermission()) changePage(true)
    }

    private fun checkShizukuPermission(): Boolean {
        if (Shizuku.isPreV11()) return false
        try {
            return when {
                Shizuku.checkSelfPermission() == PERMISSION_GRANTED -> true
                Shizuku.shouldShowRequestPermissionRationale() -> { showDeniedMessage(); false }
                else -> { Shizuku.requestPermission(REQUEST_CODE_SHIZUKU_GRANT); false }
            }
        } catch (e: Throwable) {
            Timber.e(e)
        }
        showDeniedMessage()
        return false
    }

    private fun showDeniedMessage() {
        alert = R.string.onboarding_adb_shizuku_grant_fail_denied_title to R.string.onboarding_adb_shizuku_grant_fail_denied
    }

    // ------------------------------------------------------------------------------------------------ battery

    fun requestBatteryExemption() = FirstWeekStore.requestIgnoreBatteryOptimizations(this)
    fun openBatterySettings() = FirstWeekStore.openAppBatterySettings(this)
    val batteryExempt: Boolean get() = FirstWeekStore.isIgnoringBatteryOptimizations(this)

    private fun pageOf(number: Int): FirstWeek.Page? = when (number) {
        PAGE_WELCOME -> FirstWeek.Page.WELCOME
        PAGE_LIMITATIONS -> FirstWeek.Page.LIMITATIONS
        PAGE_METHOD_SELECT -> FirstWeek.Page.METHOD_SELECT
        PAGE_ADB_SETUP -> FirstWeek.Page.ADB_SETUP
        PAGE_RUNTIME_PERMISSIONS -> FirstWeek.Page.RUNTIME_PERMISSIONS
        PAGE_BATTERY -> FirstWeek.Page.BATTERY
        PAGE_READY -> FirstWeek.Page.READY
        else -> null
    }

    companion object {
        const val SHIZUKU_PKG = "moe.shizuku.privileged.api"
        const val SHIZUKU_RELEASES_URL = "https://github.com/RikkaApps/Shizuku/releases"
        private const val REQUEST_CODE_SHIZUKU_GRANT = 1

        const val PAGE_WELCOME = 1
        const val PAGE_LIMITATIONS = 2
        const val PAGE_METHOD_SELECT = 3
        const val PAGE_ADB_SETUP = 4
        const val PAGE_RUNTIME_PERMISSIONS = 5
        const val PAGE_BATTERY = 6
        const val PAGE_READY = 7

        private const val STATE_PAGE = "page"
        private const val STATE_START = "startPage"
        private const val STATE_METHOD = "method"

    }
}

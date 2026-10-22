package me.timschneeberger.rootlessjamesdsp.fragment

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager.PERMISSION_GRANTED
import android.os.Build
import android.os.Bundle
import android.os.Process.myUid
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.transition.TransitionManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.transition.MaterialSharedAxis
import me.timschneeberger.hiddenapi_impl.ShizukuSystemServerApi
import me.timschneeberger.hiddenapi_impl.UserHandle
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.activity.MainActivity
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity.Companion.EXTRA_BATTERY_SETUP
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity.Companion.EXTRA_ROOTLESS_REDO_ADB_SETUP
import me.timschneeberger.rootlessjamesdsp.activity.OnboardingActivity.Companion.EXTRA_ROOT_SETUP_DUMP_PERM
import me.timschneeberger.rootlessjamesdsp.databinding.OnboardingFragmentBinding
import me.timschneeberger.rootlessjamesdsp.flavor.RootShellImpl
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeek
import me.timschneeberger.rootlessjamesdsp.pvb.FirstWeekStore
import me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral
import me.timschneeberger.rootlessjamesdsp.service.RootAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.isPackageInstalled
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.launchApp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.openPlayStoreApp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.resolveColorAttribute
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.showAlert
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.toast
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasNotificationPermission
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasProjectMediaAppOp
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasRecordPermission
import me.timschneeberger.rootlessjamesdsp.utils.isRootless
import me.timschneeberger.rootlessjamesdsp.utils.preferences.Preferences
import me.timschneeberger.rootlessjamesdsp.utils.sdkAbove
import me.timschneeberger.rootlessjamesdsp.view.Card
import org.koin.android.ext.android.inject
import rikka.shizuku.Shizuku
import timber.log.Timber


class OnboardingFragment : Fragment() {
    private lateinit var container: ViewGroup

    private val pageMap = mutableMapOf(
        PAGE_WELCOME                to R.id.onboarding_page1,
        PAGE_LIMITATIONS            to R.id.onboarding_page2,
        PAGE_METHOD_SELECT          to R.id.onboarding_page3,
        PAGE_ADB_SETUP              to R.id.onboarding_page4,
        PAGE_RUNTIME_PERMISSIONS    to R.id.onboarding_page5,
        PAGE_BATTERY                to R.id.onboarding_page6,
        PAGE_READY                  to R.id.onboarding_page7,
    )

    private enum class SetupMethods {
        None,
        Shizuku,
        Adb,
    }

    private var selectedSetupMethod = SetupMethods.None

    private var currentPage = PAGE_WELCOME

    private lateinit var backButton: Button
    private lateinit var nextButton: Button
    private lateinit var runtimePermissionLauncher: ActivityResultLauncher<Array<String>>

    private var useRoot: Boolean = false
    private var redoAdbSetup: Boolean = false
    private var shizukuAlive = false

    /** General build (Rootnote): fewer pages, the Shizuku help and the battery step (FirstWeek). */
    private val general = BuildConfig.GENERAL_BUILD
    /** Opened from the home screen's "stopped by the system" banner: only the battery page. */
    private var batteryOnly: Boolean = false
    /** The page the wizard opened on (the general build starts after the welcome and limitation pages). */
    private var startPage = PAGE_WELCOME

    private val prefsApp: Preferences.App by inject()
    private val prefsVar: Preferences.Var by inject()

    private val binderReceivedListener = Shizuku.OnBinderReceivedListener {
        Timber.d("Shizuku binder received")
        shizukuAlive = true
        updateSetupInstructions()
    }
    private val binderDeadListener =  Shizuku.OnBinderDeadListener {
        Timber.d("Shizuku binder died")
        shizukuAlive = false
        updateSetupInstructions()
    }
    private val requestPermissionResultListener = OnRequestPermissionResult()

    private lateinit var binding: OnboardingFragmentBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        runtimePermissionLauncher = registerForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { isGranted ->
            if (isGranted.all { it.value }) {
                // This callback is async, call goToPage directly from here
                if(currentPage == PAGE_RUNTIME_PERMISSIONS)
                {
                    changePage(forward = true, ignoreConditions = true)
                }
            } else {
                requireContext().showAlert(R.string.onboarding_perm_missing_title,
                    R.string.onboarding_perm_missing)
            }
        }
    }

    override fun onCreateView(
        layoutInflater: LayoutInflater,
        viewGroup: ViewGroup?,
        bundle: Bundle?
    ): View {
        useRoot = requireActivity().intent.getBooleanExtra(EXTRA_ROOT_SETUP_DUMP_PERM, false)
        redoAdbSetup = requireActivity().intent.getBooleanExtra(EXTRA_ROOTLESS_REDO_ADB_SETUP, false)
        batteryOnly = general && requireActivity().intent.getBooleanExtra(EXTRA_BATTERY_SETUP, false)
        binding = OnboardingFragmentBinding.inflate(layoutInflater, viewGroup, false)
        return binding.root
    }

    override fun onViewCreated(view: View, bundle: Bundle?) {
        val controlsLayout = view.findViewById<View>(R.id.controls_layout)
        container = view.findViewById(R.id.onboarding_container)
        backButton = controlsLayout.findViewById(R.id.back_button)
        nextButton = controlsLayout.findViewById(R.id.next_button)
        backButton.setOnClickListener { changePage(false) }
        nextButton.setOnClickListener { changePage(true) }

        if(useRoot || redoAdbSetup) {
            pageMap.remove(PAGE_RUNTIME_PERMISSIONS)
            pageMap.remove(PAGE_BATTERY)
            pageMap.remove(PAGE_READY)
            goToPage(PAGE_METHOD_SELECT)
        }
        else if(batteryOnly) {
            startPage = PAGE_BATTERY
            goToPage(PAGE_BATTERY)
        }
        else if(general && bundle == null) {
            // General build: the first-run notice was the welcome; open on the first step that is still needed.
            startPage = requestNextPage(PAGE_WELCOME, true)
            if(startPage > pageMap.size) {
                finishSetup()
                return
            }
            goToPage(startPage)
        }

        // Method selection page
        val methodPage = binding.methodSelect
        methodPage.methodsRootCard.isVisible = useRoot
        methodPage.methodsShizukuBody.text = getString(
            if(useRoot)
                R.string.onboarding_methods_root_shizuku
            else
                R.string.onboarding_methods_rootless_shizuku
        )
        methodPage.methodsAdbBody.text = getString(
            if(useRoot)
                R.string.onboarding_methods_root_adb
            else
                R.string.onboarding_methods_rootless_adb
        )

        if(!SdkCheck.isQ) {
            methodPage.methodsShizukuCard.isEnabled = false
            methodPage.methodsShizukuCard.isClickable = false
            methodPage.methodsShizukuCard.isFocusable = false
            methodPage.methodsShizukuBody.isEnabled = false
            methodPage.methodsShizukuTitle.isEnabled = false
            methodPage.methodsShizukuTitle.text = "${getString(R.string.onboarding_methods_shizuku_title)} (${getString(R.string.onboarding_methods_unsupported_append)})"
        }

        if(!useRoot && SdkCheck.isQ) {
            // Highlight Shizuku card as preferred option
            methodPage.methodsShizukuCard.setCardBackgroundColor(
                requireContext().resolveColorAttribute(com.google.android.material.R.attr.colorSecondaryContainer)
            )
        }

        // General build: what Shizuku is, and a button that opens it or shows where to get it (no download here).
        if(general && !useRoot && SdkCheck.isQ) {
            methodPage.methodsShizukuExplain.isVisible = true
            methodPage.methodsShizukuButton.isVisible = true
            methodPage.methodsShizukuButton.setOnClickListener {
                if(!requireContext().launchApp(SHIZUKU_PKG))
                    showShizukuSources()
            }
            updateShizukuButton()
        }

        // General build: why the capture consent appears again (Android 14+ per-session consent).
        if(general) {
            binding.onboardingPage5.findViewById<Card>(R.id.onboarding_cast_permission)?.bodyText =
                getString(R.string.firstweek_capture_consent)
        }

        // Battery page (general build only)
        val batteryPage = binding.batterySetup
        batteryPage.batteryRequest.setOnButtonClickListener {
            activity?.let { FirstWeekStore.requestIgnoreBatteryOptimizations(it) }
        }
        batteryPage.batteryOneui.bodyText = getString(R.string.firstweek_battery_oneui_body).replace("\n", "<br/>")
        batteryPage.batteryOneui.setOnButtonClickListener {
            activity?.let { FirstWeekStore.openAppBatterySettings(it) }
        }

        methodPage.methodsRootCard.setOnClickListener {
            RootShellImpl.getShell(object : RootShellImpl.OnShellAttachedCallback {
                override fun onShellAttached(isRoot: Boolean) {
                    Timber.d("onShellAttached: isRoot=$isRoot")
                    if(!isRoot) {
                        context?.showAlert(
                            R.string.onboarding_root_shell_fail_title,
                            R.string.onboarding_root_shell_fail
                        )
                        return
                    }
                    val success = RootShellImpl.cmd("pm grant ${BuildConfig.APPLICATION_ID} android.permission.DUMP\n")
                    if(!success && context?.hasDumpPermission() != true) {
                        context?.showAlert(
                            R.string.onboarding_root_shell_fail_title,
                            R.string.onboarding_root_shell_fail_unknown
                        )
                        return
                    }
                    finishSetup()
                }
            })
        }
        methodPage.methodsShizukuCard.setOnClickListener {
            selectedSetupMethod = SetupMethods.Shizuku
            changePage(true)
        }
        methodPage.methodsAdbCard.setOnClickListener {
            selectedSetupMethod = SetupMethods.Adb
            changePage(true)
        }

        // ADB permission page
        val adbPage = binding.adbSetup
        adbPage.step1.setOnButtonClickListener {
            if (selectedSetupMethod == SetupMethods.Adb) {
                try {
                    // Open developer settings
                    startActivity(Intent("android.settings.APPLICATION_DEVELOPMENT_SETTINGS"))
                } catch (e: ActivityNotFoundException) {
                    context?.toast(getString(R.string.no_activity_found))
                }
            } else {
                // Open Shizuku play store page
                viewShizukuInMarket()
            }
        }
        adbPage.step2.setOnButtonClickListener {
            // Launch Shizuku
            if(!requireContext().launchApp(SHIZUKU_PKG))
            {
                requestShizukuInstallation()
            }
        }
        adbPage.step3.setOnButtonClickListener {
            if(!requireContext().isPackageInstalled(SHIZUKU_PKG))
            {
                requestShizukuInstallation()
                return@setOnButtonClickListener
            }

            if(!shizukuAlive)
            {
                requireContext().showAlert(R.string.onboarding_adb_shizuku_grant_fail_server_dead_title,
                    R.string.onboarding_adb_shizuku_grant_fail_server_dead)
                return@setOnButtonClickListener
            }

            if(Shizuku.isPreV11())
            {
                val alert = MaterialAlertDialogBuilder(requireContext())
                alert.setMessage(getString(R.string.onboarding_adb_shizuku_grant_fail_version))
                alert.setTitle(getString(R.string.onboarding_adb_shizuku_grant_fail_version_title))
                alert.setPositiveButton(getString(R.string.update)) { _, _ -> viewShizukuInMarket() }
                alert.setNegativeButton(android.R.string.ok, null)
                alert.create().show()
                return@setOnButtonClickListener
            }

            if(checkPermission(REQUEST_CODE_SHIZUKU_GRANT))
            {
                // Permission already granted
                changePage(true)
            }
        }

        bundle?.let {
            startPage = it.getInt("startPage", startPage)
            goToPage(it.getInt("currentPage"))
        }

        Shizuku.addBinderReceivedListenerSticky(binderReceivedListener)
        Shizuku.addBinderDeadListener(binderDeadListener)
        Shizuku.addRequestPermissionResultListener(requestPermissionResultListener)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putInt("currentPage", currentPage)
        outState.putInt("startPage", startPage)
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        // Back from Shizuku, the store or the battery settings
        if(general) {
            updateShizukuButton()
            updateBatteryPage()
        }
    }

    private fun updateShizukuButton() {
        val ctx = context ?: return
        binding.methodSelect.methodsShizukuButton.text = getString(
            if(ctx.isPackageInstalled(SHIZUKU_PKG)) R.string.firstweek_shizuku_open else R.string.firstweek_shizuku_get
        )
    }

    private fun updateBatteryPage() {
        val ctx = context ?: return
        val card = binding.batterySetup.batteryRequest
        val exempt = FirstWeekStore.isIgnoringBatteryOptimizations(ctx)
        card.buttonEnabled = !exempt
        card.buttonText = getString(if(exempt) R.string.firstweek_battery_request_done else R.string.firstweek_battery_request_button)
        card.iconSrc = if(exempt) R.drawable.ic_twotone_check_circle_24dp else R.drawable.ic_numeric_1_circle_outline
    }

    /** Where to get Shizuku: the user picks Play Store or the GitHub releases page; nothing is downloaded here. */
    private fun showShizukuSources() {
        val ctx = context ?: return
        MaterialAlertDialogBuilder(ctx)
            .setTitle(R.string.firstweek_shizuku_sources_title)
            .setMessage(R.string.firstweek_shizuku_sources)
            .setPositiveButton(R.string.firstweek_shizuku_play) { _, _ -> ctx.openPlayStoreApp(SHIZUKU_PKG) }
            .setNeutralButton(R.string.firstweek_shizuku_github) { _, _ -> PvbGeneral.openUrl(ctx, SHIZUKU_RELEASES_URL) }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun requestShizukuInstallation(){
        if(general) {
            showShizukuSources()
            return
        }
        val alert = MaterialAlertDialogBuilder(requireContext())
        alert.setMessage(getString(R.string.onboarding_adb_shizuku_not_installed))
        alert.setTitle(getString(R.string.onboarding_adb_shizuku_not_installed_title))
        alert.setPositiveButton(getString(R.string.install)) { _, _ -> viewShizukuInMarket() }
        alert.setNegativeButton(android.R.string.cancel, null)
        alert.create().show()
    }

    override fun onDestroyView() {
        super.onDestroyView()

        Shizuku.removeBinderReceivedListener(binderReceivedListener)
        Shizuku.removeBinderDeadListener(binderDeadListener)
        Shizuku.removeRequestPermissionResultListener(requestPermissionResultListener)
    }

    fun onBackPressed(): Boolean {
        if (canGoBack()) {
            changePage(false)
            return true
        }
        return false
    }

    /** Back stays inside the wizard only when there is a page to go back to (or the root/redo cut-off finishes it). */
    private fun canGoBack(): Boolean = when {
        batteryOnly || isFirstPage -> false
        useRoot || redoAdbSetup -> true
        else -> requestNextPage(currentPage - 1, false) >= 1
    }

    private fun checkPermission(code: Int): Boolean {
        if (Shizuku.isPreV11()) {
            return false
        }
        try {
            return if (Shizuku.checkSelfPermission() == PERMISSION_GRANTED) {
                true
            } else if (Shizuku.shouldShowRequestPermissionRationale()) {
                showDeniedMessage()
                false
            } else {
                Shizuku.requestPermission(code)
                false
            }
        } catch (e: Throwable) {
            e.printStackTrace()
        }

        showDeniedMessage()
        return false
    }

    private fun showDeniedMessage(){
        requireContext().showAlert(R.string.onboarding_adb_shizuku_grant_fail_denied_title,
            R.string.onboarding_adb_shizuku_grant_fail_denied)
    }

    private fun viewShizukuInMarket(){
        if(general) {
            showShizukuSources()
            return
        }
        requireContext().openPlayStoreApp(SHIZUKU_PKG)
    }

    private inner class OnRequestPermissionResult : Shizuku.OnRequestPermissionResultListener
    {
        override fun onRequestPermissionResult(requestCode: Int, grantResult: Int) {
            if (grantResult == PERMISSION_GRANTED) {
                when (requestCode) {
                    REQUEST_CODE_SHIZUKU_GRANT -> {
                        changePage(true)
                    }
                }
            } else {
                showDeniedMessage()
            }
        }
    }

    @SuppressLint("ApplySharedPref")
    private fun finishSetup() {

        if(!redoAdbSetup) {
            // General build: the home screen (it asks for capture like MainActivity does); s26u: MainActivity.
            val intent = context?.let { me.timschneeberger.rootlessjamesdsp.pvb.PvbGeneral.homeIntent(it) } ?: return
            intent.putExtra(MainActivity.EXTRA_FORCE_SHOW_CAPTURE_PROMPT, true)
            startActivity(intent)
        }
        activity?.finish()

        // Mark setup as done
        if(!useRoot) {
            prefsVar.set(R.string.key_first_boot, false)
        }
        // Root: enable enhanced processing
        else {
            prefsApp.set(R.string.key_audioformat_enhanced_processing, true, async = false)
            context?.let {
                RootAudioProcessorService.startServiceEnhanced(it)
                it.toast(R.string.onboarding_root_enhanced_processing_setup_success)
            }
        }
    }

    private fun goToPage(number: Int)
    {
        // Check if we're finished
        if(number > pageMap.size)
        {
            finishSetup()
            return
        }

        // Prepare pages
        if(number == PAGE_ADB_SETUP) {
            updateSetupInstructions()
        }
        else if(number == PAGE_BATTERY) {
            updateBatteryPage()
        }
        else if(number == PAGE_RUNTIME_PERMISSIONS) {
            val pageBinding = binding.onboardingPage5
            if(!SdkCheck.isTiramisu) {
                pageBinding.findViewById<View>(R.id.onboarding_notification_permission).visibility = View.GONE
            }
            pageBinding.findViewById<Card>(R.id.privacy_card).apply {
                isVisible = !BuildConfig.FOSS_ONLY
                checkboxIsChecked = prefsApp.get(R.string.key_share_crash_reports)
                setOnCheckChangedListener {
                    Timber.d("Should share crash reports? $it")
                    prefsApp.set(R.string.key_share_crash_reports, it)
                }
            }
        }

        // Hide next button because user should continue by choosing a setup method
        nextButton.isVisible = number != PAGE_METHOD_SELECT

        val prev = pageMap[currentPage]
        val next = pageMap[number]
        if(prev == null || next == null) {
            Timber.e("Unknown page resource (prev=$prev; next=$next)")
            return
        }

        val prevView = view?.findViewById<View>(prev)
        val nextView = view?.findViewById<View>(next)
        if(prevView == null || nextView == null) {
            Timber.e("View is null (prev=$prev; next=$next)")
            return
        }

        // Change the visibility of the start and end views, animating using a shared axis transition.
        val sharedAxis = createTransition(currentPage <= number, prevView, nextView)
        TransitionManager.beginDelayedTransition(container, sharedAxis)

        prevView.visibility = View.GONE
        nextView.visibility = View.VISIBLE

        currentPage = number

        backButton.isEnabled = canGoBack()
        nextButton.text = getString(if (isLastPage) R.string.onboarding_finish else R.string.onboarding_next)
    }

    private fun changePage(forward: Boolean, ignoreConditions: Boolean = false) {
        // Battery page opened from the home screen: done (or back) returns there.
        if(batteryOnly) {
            requireActivity().finish()
            return
        }
        val nextIndex = if (forward) requestNextPage(currentPage + 1, forward) else requestNextPage(currentPage - 1, forward)
        if(nextIndex < 1) {
            Timber.w("Page index out of range ($nextIndex)")
            return
        }

        if(forward && !canAccessNextPage(currentPage) && !ignoreConditions) {
            Timber.d("Next page not ready; instructions not yet fulfilled by the user")
            return
        }

        // Root setup or rootless re-setup; cut-off first two pages
        if((redoAdbSetup || useRoot) && !forward && (currentPage - 1) <= PAGE_LIMITATIONS) {
            requireActivity().finish()
            return
        }

        goToPage(nextIndex)
    }

    private fun areAdbPermissionsGranted(): Boolean {
        return requireContext().hasDumpPermission() &&
                // Android 15+ doesn't allow keyguard recording without PROJECT_MEDIA
                requireContext().hasProjectMediaAppOp()
    }

    private fun requestNextPage(nextPage: Int, forward: Boolean): Int
    {
        val shouldSkip = when {
            // Pages the build never shows in the normal flow (FirstWeek: general skips welcome, limitations and
            // the ready page; the s26u build has no battery page). Root/redo setups keep their own page set.
            !useRoot && !redoAdbSetup && pageOf(nextPage)?.let { it in FirstWeek.skippedAlways(general) } == true -> true
            // Don't skip ADB setup if redoAdbSetup is set
            nextPage == PAGE_METHOD_SELECT -> areAdbPermissionsGranted() && !redoAdbSetup
            nextPage == PAGE_ADB_SETUP -> areAdbPermissionsGranted() && !redoAdbSetup
            nextPage == PAGE_RUNTIME_PERMISSIONS -> {
               requireContext().hasNotificationPermission() && requireContext().hasRecordPermission()
            }
            nextPage == PAGE_BATTERY -> !batteryOnly &&
                !FirstWeek.batteryStepNeeded(general, FirstWeekStore.isIgnoringBatteryOptimizations(requireContext()))
            else -> false
        }

        Timber.d("requestNextPage: shouldSkip $nextPage? $shouldSkip")

        if(!shouldSkip)
            return nextPage

        return requestNextPage(if(forward) nextPage + 1 else nextPage - 1, forward)
    }

    private fun canAccessNextPage(currentPage: Int): Boolean
    {
        return when (currentPage) {
            PAGE_ADB_SETUP -> ensureAdbPermissions()
            PAGE_RUNTIME_PERMISSIONS -> ensureRuntimePermissions()
            else -> true
        }
    }

    private fun ensureAdbPermissions(): Boolean {
        /* Permission already granted?
         * Note: If were are redoing the ADB setup, make sure that the Shizuku setup
         *       can run regardless to grant optional permissions
         */
        if(areAdbPermissionsGranted() && (!redoAdbSetup || selectedSetupMethod != SetupMethods.Shizuku)) {
            Timber.d("ADB permissions already granted")
            return true
        }

        // If not, use Shizuku to grant it if connected
        if(shizukuAlive && Shizuku.checkSelfPermission() == PERMISSION_GRANTED) {
            val pkg = requireContext().packageName
            val uid = myUid()
            Timber
                .d("Granting DUMP via Shizuku (uid ${Shizuku.getUid()}) for $pkg")

            // Grant DUMP as shell
            ShizukuSystemServerApi.PermissionManager_grantRuntimePermission(
                pkg,
                Manifest.permission.DUMP,
                UserHandle.USER_SYSTEM
            )

            // Grant SYSTEM_ALERT_WINDOW as shell
            try {
                ShizukuSystemServerApi.PermissionManager_grantRuntimePermission(
                    pkg,
                    Manifest.permission.SYSTEM_ALERT_WINDOW,
                    UserHandle.USER_SYSTEM
                )
            }
            catch (ex: Exception) {
                Timber.e(ex)
            }

            // Grant permanent SYSTEM_ALERT_WINDOW op as shell
            try {
                ShizukuSystemServerApi.AppOpsService_setMode(
                    ShizukuSystemServerApi.APP_OPS_OP_SYSTEM_ALERT_WINDOW,
                    uid,
                    pkg,
                    ShizukuSystemServerApi.APP_OPS_MODE_ALLOW
                )
            }
            catch (ex: Exception) {
                Timber.e("AppOpsService_setMode for system_alert_window threw an exception")
                Timber.e(ex)
                ShizukuSystemServerApi.exec("appops set $pkg SYSTEM_ALERT_WINDOW allow")
            }

            // Grant permanent PROJECT_MEDIA op as shell
            try {
                ShizukuSystemServerApi.AppOpsService_setMode(
                    ShizukuSystemServerApi.APP_OPS_OP_PROJECT_MEDIA,
                    uid,
                    pkg,
                    ShizukuSystemServerApi.APP_OPS_MODE_ALLOW
                )
            }
            catch (ex: Exception) {
                Timber.e("AppOpsService_setMode threw an exception")
                Timber.e(ex)
                ShizukuSystemServerApi.exec("appops set $pkg PROJECT_MEDIA allow")
            }

            // Re-check permission
            return if (areAdbPermissionsGranted()) {
                Timber.d("ADB permissions via Shizuku granted")
                true
            } else {
                Timber.e("ADB permissions not granted")
                requireContext().showAlert(R.string.onboarding_adb_shizuku_no_dump_perm_title,
                    R.string.onboarding_adb_shizuku_no_dump_perm)
                false
            }
        }

        // Regular ADB setup
        if(!requireContext().hasDumpPermission()) {
            requireContext().showAlert(R.string.onboarding_adb_not_granted_title,
                R.string.onboarding_adb_dump_permission_not_granted)
        }
        else if(!requireContext().hasProjectMediaAppOp()) {
            requireContext().showAlert(R.string.onboarding_adb_not_granted_title,
                R.string.onboarding_adb_project_media_not_granted)
        }

        return false
    }

    private fun ensureRuntimePermissions(): Boolean
    {
        val requestedPermissions = arrayListOf<String>()
        if(!requireContext().hasRecordPermission()) {
            requestedPermissions.add(Manifest.permission.RECORD_AUDIO)
        }

        sdkAbove(Build.VERSION_CODES.TIRAMISU) {
            if(!requireContext().hasNotificationPermission())
                requestedPermissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        return if(requestedPermissions.isNotEmpty()) {
            runtimePermissionLauncher.launch(requestedPermissions.toTypedArray())
            false
        }
        else {
            true
        }
    }

    private fun updateSetupInstructions() {
        val page = binding.adbSetup

        page.step4.isVisible = selectedSetupMethod == SetupMethods.Adb
        page.step6.isVisible = selectedSetupMethod == SetupMethods.Adb
        page.step5b.isVisible = selectedSetupMethod == SetupMethods.Adb && isRootless()
        page.step5cOptional.isVisible = selectedSetupMethod == SetupMethods.Adb && isRootless()

        if(selectedSetupMethod == SetupMethods.Shizuku) {
            val installed = requireContext().isPackageInstalled(SHIZUKU_PKG)
            page.step1.buttonEnabled = !installed
            if(installed) {
                page.step1.buttonText = getString(R.string.onboarding_adb_shizuku_install_button_done)
                page.step1.iconSrc = R.drawable.ic_twotone_check_circle_24dp
            }
            else {
                page.step1.buttonText = getString(R.string.onboarding_adb_shizuku_install_button)
                page.step1.iconSrc = R.drawable.ic_numeric_1_circle_outline
            }

            page.step2.buttonEnabled = !(shizukuAlive && installed)
            if(shizukuAlive && installed) {
                page.step2.buttonText = getString(R.string.onboarding_adb_shizuku_open_button_done)
                page.step2.iconSrc = R.drawable.ic_twotone_check_circle_24dp
            }
            else {
                page.step2.buttonText = getString(R.string.onboarding_adb_shizuku_open_button)
                page.step2.iconSrc = R.drawable.ic_numeric_2_circle_outline
            }

            page.step3.buttonText = getString(R.string.onboarding_adb_shizuku_grant_button)

            page.step1.bodyText = getString(R.string.onboarding_adb_shizuku_install_instruction)
            page.step2.bodyText = getString(R.string.onboarding_adb_shizuku_open_instruction)
            page.step3.bodyText = getString(R.string.onboarding_adb_shizuku_grant_instruction)

            page.title.text = getString(R.string.onboarding_adb_shizuku_title)
        }
        else {
            page.step1.iconSrc = R.drawable.ic_numeric_1_circle_outline
            page.step2.iconSrc = R.drawable.ic_numeric_2_circle_outline

            page.step1.buttonText = getString(R.string.onboarding_adb_manual_step1_button)
            page.step2.buttonText = null
            page.step3.buttonText = null
            page.step1.bodyText = getString(R.string.onboarding_adb_manual_step1)
            page.step2.bodyText = getString(R.string.onboarding_adb_manual_step2)
            page.step3.bodyText = getString(R.string.onboarding_adb_manual_step3)
            page.step4.bodyText = getString(R.string.onboarding_adb_manual_step4, requireContext().packageName)
            page.step6.bodyText = getString(R.string.onboarding_adb_manual_step5)
            page.step5b.bodyText = getString(R.string.onboarding_adb_manual_step5b_required, requireContext().packageName)
            page.step5cOptional.bodyText = getString(R.string.onboarding_adb_manual_step5c, requireContext().packageName)

            page.title.text = getString(R.string.onboarding_adb_adb_title)
        }
    }

    private fun createTransition(entering: Boolean, start: View, end: View): MaterialSharedAxis {
        val transition = MaterialSharedAxis(MaterialSharedAxis.X, entering)

        // Add targets for this transition to explicitly run transitions only on these views. Without
        // targeting, a MaterialSharedAxis transition would be run for every view in the
        // the ViewGroup's layout.
        transition.addTarget(start)
        transition.addTarget(end)
        return transition
    }

    private val isFirstPage: Boolean
        get() = currentPage == startPage
    /** The next button finishes the wizard: no further page would be shown. */
    private val isLastPage: Boolean
        get() = batteryOnly || requestNextPage(currentPage + 1, true) > pageMap.size

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

    companion object
    {
        fun newInstance() = OnboardingFragment()

        const val SHIZUKU_PKG = "moe.shizuku.privileged.api"
        const val SHIZUKU_RELEASES_URL = "https://github.com/RikkaApps/Shizuku/releases"

        const val REQUEST_CODE_SHIZUKU_GRANT = 1

        const val PAGE_WELCOME = 1
        const val PAGE_LIMITATIONS = 2
        const val PAGE_METHOD_SELECT = 3
        const val PAGE_ADB_SETUP = 4
        const val PAGE_RUNTIME_PERMISSIONS = 5
        const val PAGE_BATTERY = 6
        const val PAGE_READY = 7
    }
}
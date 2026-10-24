package me.timschneeberger.rootlessjamesdsp.setup

import android.app.Activity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.flavor.RootShellImpl
import me.timschneeberger.rootlessjamesdsp.interop.JamesDspRemoteEngine
import me.timschneeberger.rootlessjamesdsp.utils.extensions.PermissionExtensions.hasDumpPermission
import timber.log.Timber

/**
 * Rootnote for rooted phones (docs/ROOT_BUILD_PLAN.md): what the root build needs instead of the rootless setup
 * screens. DUMP (to find the apps' audio sessions) is granted with su; the installed JamesDSP effect must be the
 * Rootnote module's (librootnotefx, with the virtual bass engine), not the stock JamesDSP one.
 */
object RnRootSetup {
    fun check(activity: Activity) {
        if (!activity.hasDumpPermission()) {
            RootShellImpl.getShell(object : RootShellImpl.OnShellAttachedCallback {
                override fun onShellAttached(isRoot: Boolean) {
                    val ok = isRoot && RootShellImpl.cmd("pm grant ${activity.packageName} android.permission.DUMP")
                    Timber.i("root setup: su=$isRoot, DUMP granted=$ok")
                    if (!isRoot) activity.runOnUiThread { show(activity, R.string.root_no_su_title, R.string.root_no_su_body) }
                }
            })
        }
        when {
            JamesDspRemoteEngine.isRootnoteModule() -> Unit
            JamesDspRemoteEngine.isPluginInstalled() != JamesDspRemoteEngine.PluginState.Unavailable ->
                show(activity, R.string.root_stock_module_title, R.string.root_stock_module_body)
            else -> show(activity, R.string.root_no_module_title, R.string.root_no_module_body)
        }
    }

    private fun show(activity: Activity, title: Int, body: Int) {
        if (activity.isFinishing) return
        MaterialAlertDialogBuilder(activity)
            .setTitle(title)
            .setMessage(body)
            .setPositiveButton(android.R.string.ok, null)
            .show()
    }
}

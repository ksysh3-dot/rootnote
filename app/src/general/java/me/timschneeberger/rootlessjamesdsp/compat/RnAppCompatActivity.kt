package me.timschneeberger.rootlessjamesdsp.compat

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.getSystemService
import androidx.core.graphics.drawable.toBitmap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.advanced.RnAdvancedActivity
import me.timschneeberger.rootlessjamesdsp.model.room.BlockedApp
import me.timschneeberger.rootlessjamesdsp.service.RootlessAudioProcessorService
import me.timschneeberger.rootlessjamesdsp.ui.LocalRn
import me.timschneeberger.rootlessjamesdsp.ui.RnActivity
import me.timschneeberger.rootlessjamesdsp.ui.RnBand
import me.timschneeberger.rootlessjamesdsp.ui.RnButtonRow
import me.timschneeberger.rootlessjamesdsp.ui.RnChevron
import me.timschneeberger.rootlessjamesdsp.ui.RnFilledButton
import me.timschneeberger.rootlessjamesdsp.ui.RnOutlineButton
import me.timschneeberger.rootlessjamesdsp.ui.RnPage
import me.timschneeberger.rootlessjamesdsp.ui.RnParagraph
import me.timschneeberger.rootlessjamesdsp.utils.SdkCheck
import me.timschneeberger.rootlessjamesdsp.utils.extensions.CompatExtensions.getParcelableAs
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getAppIcon
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getAppNameFromUidSafe
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getPackageNameFromUid
import me.timschneeberger.rootlessjamesdsp.utils.notifications.Notifications
import timber.log.Timber

/**
 * "호환성 문제" of the general build in Compose (replaces AppCompatibilityActivity/Fragment there): an app the service
 * cannot capture stopped processing. Shows the app (tap opens it), then retry (the service restarts with the same
 * capture consent) or exclude (the app goes on the excluded list, then the restart). Same extras as the legacy screen.
 */
class RnAppCompatActivity : RnActivity() {

    private var busy by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        getSystemService<NotificationManager>()?.cancel(Notifications.ID_SERVICE_APPCOMPAT)
        val extras = intent.extras
        val uid = extras?.getInt(RootlessAudioProcessorService.EXTRA_APP_UID, -1) ?: -1
        if (uid < 0) {
            finish()
            return
        }
        val internalCall = extras?.getBoolean(RootlessAudioProcessorService.EXTRA_APP_COMPAT_INTERNAL_CALL, false) ?: false
        val projectIntent = extras?.getParcelableAs<Intent>(RootlessAudioProcessorService.EXTRA_MEDIA_PROJECTION_DATA)
        val pkg = getPackageNameFromUid(uid) ?: getString(R.string.app_compat_unknown_pkg_name)
        val name = getAppNameFromUidSafe(uid)
        val icon = (getAppIcon(pkg) ?: getAppIcon("android"))?.toBitmap(96, 96)?.asImageBitmap()

        fun restartAndClose() {
            projectIntent?.let { if (SdkCheck.isQ) RootlessAudioProcessorService.start(this, it) }
            window.decorView.postDelayed({
                finish()
                if (internalCall) startActivity(RnAdvancedActivity.intent(this))
            }, 300L)
        }

        setRnContent {
            val c = LocalRn.current
            RnPage(stringResource(R.string.title_activity_app_compat), onBack = this@RnAppCompatActivity::finish,
                bottomBar = {
                    RnButtonRow {
                        RnOutlineButton(stringResource(R.string.app_compat_retry), Modifier.weight(1f), enabled = !busy) {
                            busy = true
                            Timber.d("Requesting retry")
                            restartAndClose()
                        }
                        RnFilledButton(stringResource(R.string.app_compat_exclude), Modifier.weight(1f), enabled = !busy) {
                            busy = true
                            Timber.d("Requesting exclude of $pkg")
                            val repo = (application as MainApplication).blockedAppRepository
                            CoroutineScope(Dispatchers.IO).launch { repo.insert(BlockedApp(uid, pkg, name)) }
                            window.decorView.postDelayed({ restartAndClose() }, 100L)
                        }
                    }
                }) {
                Text(stringResource(R.string.app_compat_title), color = c.textPrimary, fontSize = 17.sp, lineHeight = 24.sp,
                    fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
                RnParagraph(stringResource(R.string.app_compat_explanation))
                AppRow(name, pkg, icon) {
                    packageManager.getLaunchIntentForPackage(pkg)?.let { startActivity(it) }
                }
                RnBand()
                RnParagraph(stringResource(R.string.app_compat_instruction))
                RnParagraph(stringResource(R.string.app_compat_instruction_exclude))
            }
        }
    }

    override fun onResume() {
        super.onResume()
        prefsVar.set(R.string.key_is_app_compat_activity_active, true)
    }

    override fun onPause() {
        super.onPause()
        prefsVar.set(R.string.key_is_app_compat_activity_active, false)
    }

    override fun onDestroy() {
        prefsVar.set(R.string.key_is_app_compat_activity_active, false)
        super.onDestroy()
    }
}

/** The app that could not be captured: icon, name, package; tapping opens it. */
@Composable
private fun AppRow(name: String, pkg: String, icon: androidx.compose.ui.graphics.ImageBitmap?, onClick: () -> Unit) {
    val c = LocalRn.current
    Row(
        Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onClick).heightIn(min = 72.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (icon != null) Image(icon, contentDescription = null, modifier = Modifier.size(40.dp))
        Column(Modifier.weight(1f)) {
            Text(name, color = c.textPrimary, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            Text(pkg, color = c.textSecondary, fontSize = 13.sp, lineHeight = 18.sp)
        }
        RnChevron()
    }
}

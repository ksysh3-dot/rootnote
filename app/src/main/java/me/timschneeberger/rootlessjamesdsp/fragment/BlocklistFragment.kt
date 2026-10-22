package me.timschneeberger.rootlessjamesdsp.fragment

import android.graphics.drawable.Drawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.recyclerview.widget.LinearLayoutManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import me.timschneeberger.rootlessjamesdsp.BuildConfig
import me.timschneeberger.rootlessjamesdsp.MainApplication
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.adapter.AppBlocklistAdapter
import me.timschneeberger.rootlessjamesdsp.databinding.FragmentBlocklistBinding
import me.timschneeberger.rootlessjamesdsp.model.AppInfo
import me.timschneeberger.rootlessjamesdsp.model.ItemViewModel
import me.timschneeberger.rootlessjamesdsp.model.room.AppBlocklistViewModel
import me.timschneeberger.rootlessjamesdsp.model.room.AppBlocklistViewModelFactory
import me.timschneeberger.rootlessjamesdsp.model.room.BlockedApp
import me.timschneeberger.rootlessjamesdsp.pvb.QuickExclude
import me.timschneeberger.rootlessjamesdsp.session.dump.DumpManager
import me.timschneeberger.rootlessjamesdsp.session.rootless.SessionRecordingPolicyManager
import me.timschneeberger.rootlessjamesdsp.utils.extensions.CompatExtensions.getApplicationInfoCompat
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getAppIcon
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.getAppNameFromUidSafe
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.showAlert
import me.timschneeberger.rootlessjamesdsp.utils.extensions.ContextExtensions.showYesNoAlert
import me.timschneeberger.rootlessjamesdsp.utils.extensions.asHtml
import me.timschneeberger.rootlessjamesdsp.utils.isRootless
import me.timschneeberger.rootlessjamesdsp.utils.preferences.Preferences
import org.koin.android.ext.android.inject

class BlocklistFragment : Fragment() {

    private lateinit var binding: FragmentBlocklistBinding
    private lateinit var appsListFragment: AppsListFragment
    private lateinit var adapter: AppBlocklistAdapter

    private val dumpManager: DumpManager by inject()
    private val preferences: Preferences.App by inject()

    private val viewModel: AppBlocklistViewModel by viewModels {
        AppBlocklistViewModelFactory((requireActivity().application as MainApplication).blockedAppRepository)
    }
    private val appListViewModel: ItemViewModel<AppInfo> by viewModels()

    private val iconCache: HashMap<Int, Drawable> = hashMapOf()

    private lateinit var sessionRecordingPolicyManager: SessionRecordingPolicyManager
    private val policyPollingScope = CoroutineScope(Dispatchers.Main)
    private var restrictedApps = arrayOf<String>()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        binding = FragmentBlocklistBinding.inflate(layoutInflater, container, false)

        sessionRecordingPolicyManager = SessionRecordingPolicyManager(requireContext())

        appsListFragment = AppsListFragment()
        appListViewModel.selectedItem.observe(viewLifecycleOwner) { (appName, packageName, _, _, uid) ->
            // TODO merge BlockedApp and AppInfo?
            viewModel.insert(BlockedApp(uid, packageName, appName))
        }

        adapter = AppBlocklistAdapter()
        adapter.setOnItemClickListener {
            requireContext().showYesNoAlert(R.string.blocklist_delete_title, R.string.blocklist_delete) { confirm ->
                if(confirm)
                    viewModel.delete(it)
            }
        }

        binding.recyclerview.adapter = adapter
        binding.recyclerview.layoutManager = LinearLayoutManager(requireContext())

        binding.notice.isVisible = false
        binding.notice.setOnClickListener {
            requireContext().showAlert(
                getString(R.string.blocklist_unsupported_apps),
                getString(R.string.blocklist_unsupported_apps_message, restrictedApps.joinToString("<br/>")).asHtml()
            )
        }
        updateUnsupportedApps()

        // General build: the delay note and the quick-add list (QuickExclude), unchecked; the user chooses.
        binding.quickExclude.isVisible = BuildConfig.GENERAL_BUILD
        binding.quickExcludeButton.setOnClickListener { showQuickExclude() }

        viewModel.blockedApps.observe(requireActivity()) { apps ->
            val isEmpty = apps == null || apps.isEmpty()

            // Update the cached copy of the blocked apps in the adapter.
            apps?.let { list ->
                list.forEach {
                    it.appIcon = if(iconCache.containsKey(it.uid))
                        iconCache[it.uid]
                    else {
                        it.packageName?.let { pkg ->
                            val icon = requireContext().getAppIcon(pkg)
                            icon?.let { i ->
                                iconCache[it.uid] = i
                            }
                            icon
                        }
                    }
                }
                adapter.submitList(list.sortedBy { it.appName })
            }
            binding.recyclerview.isVisible = !isEmpty
            binding.emptyview.isVisible = isEmpty
        }

        return binding.root
    }

    override fun onDestroyView() {
        sessionRecordingPolicyManager.destroy()
        super.onDestroyView()
    }

    override fun onResume() {
        updateUnsupportedApps()
        super.onResume()
    }

    /** Installed video, live-streaming and call apps that are not excluded yet, as an unchecked multi-choice list. */
    private fun showQuickExclude() {
        val ctx = context ?: return
        val pm = ctx.packageManager
        // Package visibility: these packages are listed in the general manifest's <queries>.
        val installed = QuickExclude.APPS.mapNotNull { c ->
            try { c.packageName to pm.getApplicationInfoCompat(c.packageName, 0) } catch (e: Exception) { null }
        }.toMap()
        val excluded = viewModel.blockedApps.value.orEmpty().mapNotNull { it.packageName }.toSet()
        val candidates = QuickExclude.candidates(installed.keys, excluded)
        if (candidates.isEmpty()) {
            ctx.showAlert(getString(R.string.firstweek_exclude_quick_button), getString(R.string.firstweek_exclude_quick_none))
            return
        }
        val labels = candidates.map { c ->
            installed[c.packageName]?.let { pm.getApplicationLabel(it).toString() }?.takeIf { it.isNotBlank() } ?: c.label
        }
        val checked = BooleanArray(candidates.size)  // nothing preselected
        MaterialAlertDialogBuilder(ctx)
            .setTitle(R.string.firstweek_exclude_quick_title)
            .setMultiChoiceItems(labels.toTypedArray<CharSequence>(), checked) { _, which, isChecked -> checked[which] = isChecked }
            .setPositiveButton(R.string.firstweek_exclude_quick_add) { _, _ ->
                candidates.forEachIndexed { i, c ->
                    val info = installed[c.packageName]
                    if (checked[i] && info != null) viewModel.insert(BlockedApp(info.uid, c.packageName, labels[i]))
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    fun showAppSelector() {
        if(!appsListFragment.isAdded)
            appsListFragment.show(childFragmentManager, AppsListFragment::class.java.name)
    }

    private fun updateUnsupportedApps() {
        if(isRootless()) {
            policyPollingScope.launch {
                val isAllowed = preferences.get<Boolean>(R.string.key_session_exclude_restricted)

                restrictedApps = if (!isAllowed) {
                    arrayOf()
                } else {
                    dumpManager.dumpCaptureAllowlistLog()?.let {
                        sessionRecordingPolicyManager.update(it)
                    }

                    sessionRecordingPolicyManager
                        .getRestrictedUids()
                        .map { """${requireContext().getAppNameFromUidSafe(it)} (UID $it)""" }
                        .toTypedArray()
                }

                this@BlocklistFragment.binding.notice.isVisible = restrictedApps.isNotEmpty()
                context?.let {
                    this@BlocklistFragment.binding.noticeLabel.text = it.resources.getQuantityString(
                        R.plurals.unsupported_apps,
                        restrictedApps.size,
                        restrictedApps.size
                    )
                }
            }
        }
    }

    companion object {
        fun newInstance(): BlocklistFragment {
            return BlocklistFragment()
        }
    }
}
package me.timschneeberger.rootlessjamesdsp.fragment

import android.animation.LayoutTransition
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.view.isVisible
import com.google.android.material.card.MaterialCardView
import androidx.fragment.app.Fragment
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.databinding.FragmentDspBinding
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.utils.Constants
import me.timschneeberger.rootlessjamesdsp.utils.preferences.Preferences
import org.koin.android.ext.android.inject
import timber.log.Timber
import java.util.Locale

class DspFragment : Fragment(), SharedPreferences.OnSharedPreferenceChangeListener {
    private val prefsApp: Preferences.App by inject()
    private val prefsVar: Preferences.Var by inject()

    private lateinit var binding: FragmentDspBinding
    private var updateNoticeOnClick: (() -> Unit)? = null
    private var pvbNote: TextView? = null
    private var pvbPrefs: SharedPreferences? = null
    // PVB active (on, or off with "끌 때 음량 맞춤") = the service plays through the PVB engine only; the JamesDSP
    // cards below then change nothing you hear (same condition as PvbController.updateActive)
    private val pvbListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == PvbSettings.KEY_ENABLE || key == PvbSettings.KEY_MATCH_ON_DISABLE) updatePvbNote()
    }
    private var researchHeader: View? = null
    private var updateNoticeOnCloseClick: (() -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        prefsApp.registerOnSharedPreferenceChangeListener(this)
        super.onCreate(savedInstanceState)
    }

    override fun onDestroy() {
        prefsApp.unregisterOnSharedPreferenceChangeListener(this)
        super.onDestroy()
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        binding = FragmentDspBinding.inflate(layoutInflater, container, false)

        binding.translationNotice.setOnCloseClickListener(::hideTranslationNotice)
        binding.translationNotice.setOnRootClickListener {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://crowdin.com/project/rootlessjamesdsp")))
            hideTranslationNotice()
        }

        binding.updateNotice.setOnCloseClickListener {
            updateNoticeOnCloseClick?.invoke()
        }
        binding.updateNotice.setOnRootClickListener {
            updateNoticeOnClick?.invoke()
        }

        // Should show notice?
        Timber.e(Locale.getDefault().language.toString())
        binding.translationNotice.isVisible =
           prefsVar.get<Long>(R.string.key_snooze_translation_notice) < (System.currentTimeMillis() / 1000L) &&
                    !Locale.getDefault().language.equals("en") &&
                    !PvbBuild.general  // the general build ships English and Korean only; upstream Crowdin is not its project
        binding.updateNotice.isVisible = false

        val transition = LayoutTransition()
        transition.enableTransitionType(LayoutTransition.CHANGING)
        binding.cardContainer.layoutTransition = transition

        childFragmentManager.beginTransaction()
            .replace(
                R.id.card_pvb, PreferenceGroupFragment.newInstance(PvbSettings.PREFS_NAME,
                    R.xml.dsp_pvb_preferences
                ))
            .replace(R.id.card_device_profiles, DeviceProfilesCardFragment.newInstance())
            .replace(
                R.id.card_output_control, PreferenceGroupFragment.newInstance(Constants.PREF_OUTPUT,
                    R.xml.dsp_output_control_preferences
                ))
            .replace(
                R.id.card_compressor, PreferenceGroupFragment.newInstance(Constants.PREF_COMPANDER,
                    R.xml.dsp_compander_preferences
                ))
            .replace(
                R.id.card_bass, PreferenceGroupFragment.newInstance(Constants.PREF_BASS,
                    R.xml.dsp_bass_preferences
                ))
            .replace(
                R.id.card_eq, PreferenceGroupFragment.newInstance(Constants.PREF_EQ,
                    R.xml.dsp_equalizer_preferences
                ))
            .replace(
                R.id.card_peq, PreferenceGroupFragment.newInstance(Constants.PREF_PEQ,
                    R.xml.dsp_parametriceq_preferences
                ))
            .replace(
                R.id.card_geq, PreferenceGroupFragment.newInstance(Constants.PREF_GEQ,
                    R.xml.dsp_graphiceq_preferences
                ))
            .replace(
                R.id.card_ddc, PreferenceGroupFragment.newInstance(Constants.PREF_DDC,
                    R.xml.dsp_ddc_preferences
                ))
            .replace(
                R.id.card_convolver, PreferenceGroupFragment.newInstance(Constants.PREF_CONVOLVER,
                    R.xml.dsp_convolver_preferences
                ))
            .replace(
                R.id.card_liveprog, PreferenceGroupFragment.newInstance(Constants.PREF_LIVEPROG,
                    R.xml.dsp_liveprog_preferences
                ))
            .replace(
                R.id.card_tube, PreferenceGroupFragment.newInstance(Constants.PREF_TUBE,
                    R.xml.dsp_tube_preferences
                ))
            .replace(
                R.id.card_stereowide, PreferenceGroupFragment.newInstance(Constants.PREF_STEREOWIDE,
                    R.xml.dsp_stereowide_preferences
                ))
            .replace(
                R.id.card_crossfeed, PreferenceGroupFragment.newInstance(Constants.PREF_CROSSFEED,
                    R.xml.dsp_crossfeed_preferences
                ))
            .replace(
                R.id.card_reverb, PreferenceGroupFragment.newInstance(Constants.PREF_REVERB,
                    R.xml.dsp_reverb_preferences
                ))
            .commit()

        // Load initial preferences
        arrayOf(R.string.key_device_profiles_enable).forEach {
            onSharedPreferenceChanged(null, getString(it))
        }

        addPvbNote()
        arrangeResearchCards()

        return binding.root
    }

    /**
     * Research cards (analysis, fixed blind comparison, measurement). s26u: all shown, as before. General: the
     * blind comparison and measurement cards do not exist (they store records; RECORD_FEATURES = false), and the
     * analysis card sits under a "개발자/연구" header below the PVB settings, shown only after the hidden unlock.
     */
    private fun arrangeResearchCards() {
        val container = binding.cardContainer
        val analyzer = binding.pvbAnalyzer.parent as View
        if (!PvbBuild.recordFeatures) {
            container.removeView(binding.pvbAb.parent as View)
            container.removeView(binding.pvbMeasure.parent as View)
        }
        if (PvbBuild.researchUiBuild) return
        val ctx = requireContext()
        val header = TextView(ctx).apply {
            val pad = (16 * resources.displayMetrics.density).toInt()
            setPadding(pad, pad * 3 / 4, pad, pad * 3 / 4)
            textSize = 13f
            text = getString(R.string.research_section_header)
        }
        val headerCard = MaterialCardView(ctx).apply { addView(header) }
        container.removeView(analyzer)
        val at = container.indexOfChild(binding.cardPvb.parent as View) + 1
        val lp = { ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT) }
        container.addView(headerCard, at, lp())
        container.addView(analyzer, at + 1, lp())
        researchHeader = headerCard
        updateResearchVisibility()
    }

    private fun updateResearchVisibility() {
        if (PvbBuild.researchUiBuild) return
        val on = PvbBuild.researchUi
        researchHeader?.isVisible = on
        (binding.pvbAnalyzer.parent as View).isVisible = on
    }

    override fun onResume() {
        super.onResume()
        updateResearchVisibility()  // the unlock happens in Settings > About
    }

    /** The JamesDSP cards (and device profiles, which switch JamesDSP settings). */
    private fun jamesDspCards(): List<View> = listOf(
        binding.cardDeviceProfiles, binding.cardOutputControl, binding.cardCompressor, binding.cardBass, binding.cardEq,
        binding.cardPeq, binding.cardGeq, binding.cardDdc, binding.cardConvolver, binding.cardLiveprog, binding.cardTube,
        binding.cardStereowide, binding.cardCrossfeed, binding.cardReverb,
    ).map { it.parent as View }

    private fun addPvbNote() {
        val ctx = requireContext()
        val note = TextView(ctx).apply {
            val pad = (16 * resources.displayMetrics.density).toInt()
            setPadding(pad, pad * 3 / 4, pad, pad * 3 / 4)
            textSize = 13f
            text = getString(R.string.pvb_jamesdsp_note, getString(R.string.app_brand_name),
                getString(R.string.pvb_match_on_disable))
        }
        val card = MaterialCardView(ctx).apply { addView(note) }
        val container = binding.cardContainer
        val at = container.indexOfChild(binding.cardPvb.parent as View) + 1
        container.addView(card, at, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        pvbNote = note
        pvbPrefs = ctx.getSharedPreferences(PvbSettings.PREFS_NAME, Context.MODE_PRIVATE).also {
            it.registerOnSharedPreferenceChangeListener(pvbListener)
        }
        updatePvbNote()
    }

    private fun updatePvbNote() {
        // Same condition as the audio path (PvbController.updateActive): PVB on, or off with loudness matching.
        val on = pvbPrefs?.let { PvbSettings.load(it).let { s -> s.enabled || s.matchOnDisable } } ?: false
        (pvbNote?.parent as? View)?.isVisible = on
        jamesDspCards().forEach { it.alpha = if (on) 0.45f else 1f }
    }

    override fun onDestroyView() {
        pvbPrefs?.unregisterOnSharedPreferenceChangeListener(pvbListener)
        pvbPrefs = null
        pvbNote = null
        super.onDestroyView()
    }

    override fun onSharedPreferenceChanged(sharedPreferences: SharedPreferences?, key: String?) {
        when(key) {
            getString(R.string.key_device_profiles_enable) -> {
                (binding.cardDeviceProfiles.parent as ViewGroup).isVisible =
                    prefsApp.get<Boolean>(R.string.key_device_profiles_enable)
            }
        }
    }

    private fun hideTranslationNotice() {
        binding.translationNotice.isVisible = false
        // Set timer +1y
        prefsVar.set<Long>(R.string.key_snooze_translation_notice, (System.currentTimeMillis() / 1000L) + 31536000L)
    }

    fun setUpdateCardVisible(visible: Boolean) {
        binding.updateNotice.isVisible = visible
    }

    fun setUpdateCardTitle(title: String) {
        binding.updateNotice.titleText = title
    }

    fun setUpdateCardOnClick(onClick: () -> Unit) {
        updateNoticeOnClick = onClick
    }

    fun setUpdateCardOnCloseClick(onClick: () -> Unit) {
        updateNoticeOnCloseClick = onClick
    }

    fun restartFragment(id: Int, newFragment: Fragment) {
        CoroutineScope(Dispatchers.Main).launch {
            try {
                childFragmentManager.beginTransaction()
                    .replace(id, newFragment)
                    .commitAllowingStateLoss()
            }
            catch(ex: IllegalStateException) {
                Timber.e("Failed to restart fragment")
                Timber.i(ex)
            }
        }
    }

    companion object {
        fun newInstance(): DspFragment {
            return DspFragment()
        }
    }
}
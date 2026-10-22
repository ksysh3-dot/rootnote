package me.timschneeberger.rootlessjamesdsp.activity

import android.os.Bundle
import androidx.core.widget.NestedScrollView
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.databinding.ActivitySettingsBinding
import me.timschneeberger.rootlessjamesdsp.pvb.LiveAbView

/**
 * Alpha 3.3 "실청 블라인드 비교" (same frame as the settings screens). The comparison runs while this screen exists;
 * rotation does not recreate it (manifest configChanges), leaving it ends the comparison.
 */
class LiveAbActivity : BaseActivity() {
    private var view: LiveAbView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.settingsToolbar)
        supportActionBar?.title = getString(R.string.title_activity_live_ab)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        binding.settingsToolbar.setNavigationOnClickListener { onBackPressedDispatcher.onBackPressed() }

        val v = LiveAbView(this)
        view = v
        binding.settings.addView(NestedScrollView(this).apply { addView(v) })
    }

    override fun onResume() {
        super.onResume()
        view?.onScreenResumed()   // back from the results screen: new count
    }
}

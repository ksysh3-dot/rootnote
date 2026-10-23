package me.timschneeberger.rootlessjamesdsp.model.preference

import me.timschneeberger.rootlessjamesdsp.R

enum class AppTheme(val titleResId: Int?) {
    /** "심해 틸": the Rootnote palette (general build only; the s26u build falls back to DEFAULT's look). */
    ROOTNOTE(R.string.theme_rootnote),
    DEFAULT(R.string.theme_default),
    MONET(R.string.theme_monet),
    GREEN_APPLE(R.string.theme_greenapple),
    HONEY(R.string.theme_honey),
    STRAWBERRY_DAIQUIRI(R.string.theme_strawberrydaiquiri),
    TEALTURQUOISE(R.string.theme_tealturquoise),
    TIDAL_WAVE(R.string.theme_tidalwave),
    YINYANG(R.string.theme_yinyang),
    YOTSUBA(R.string.theme_yotsuba);

    companion object {
        fun fromInt(titleResId: Int) = values().first { it.titleResId == titleResId }

        /**
         * The themes offered in the picker, in order. General build: 심해 틸 first (its default), the upstream
         * default last. s26u: the upstream list without 심해 틸.
         */
        fun choices(general: Boolean, dynamicAvailable: Boolean): List<AppTheme> {
            val all = values().filter { it.titleResId != null && (it != MONET || dynamicAvailable) }
            return if (general) listOf(ROOTNOTE) + all.filter { it != ROOTNOTE && it != DEFAULT } + DEFAULT
            else all.filter { it != ROOTNOTE }
        }
    }
}
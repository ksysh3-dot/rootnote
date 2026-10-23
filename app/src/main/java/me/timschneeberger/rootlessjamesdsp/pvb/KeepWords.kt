package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Korean wraps whole words, as it is set in print and on the web (CSS word-break: keep-all). Left alone, Android may
 * break between any two syllables ("어" / "긋나면"). This puts a word joiner (U+2060: no width, not read aloud)
 * between two characters of one word when either is a Hangul syllable, so lines break only at spaces; a word wider
 * than the line still breaks. Text without Hangul (English) comes back unchanged.
 *
 * Nothing goes before a combining mark, a format character or the second half of a surrogate pair, and conjoining
 * jamo (decomposed Hangul) are not treated as syllables, so no character is ever split from what it combines with.
 * Pure Kotlin (tested on the host: tools/pvb-harness/jvm/FirstWeekTest.kt).
 */
fun keepWords(s: String): String {
    if (s.none { it.isHangulSyllable() }) return s
    val b = StringBuilder(s.length * 2)
    for (i in s.indices) {
        val ch = s[i]
        if (i > 0) {
            val prev = s[i - 1]
            // (after a format character such as a word joiner already there: nothing, so a second pass changes nothing)
            if (!prev.isWhitespace() && !ch.isWhitespace() && !ch.attachesToPrevious() &&
                Character.getType(prev) != Character.FORMAT.toInt() &&
                !prev.isConjoiningJamo() && !ch.isConjoiningJamo() &&
                (prev.isHangulSyllable() || ch.isHangulSyllable())
            ) b.append(WORD_JOINER)
        }
        b.append(ch)
    }
    return b.toString()
}

const val WORD_JOINER = '\u2060'

/** A precomposed syllable (가..힣) or a compatibility jamo (ㄱ, ㅏ: drawn alone, as in "ㅋㅋ"). */
private fun Char.isHangulSyllable(): Boolean = this in '\uAC00'..'\uD7A3' || this in '\u3130'..'\u318F'

/** Decomposed Hangul: a syllable written as its letters, which the font joins (never split, never joined to). */
private fun Char.isConjoiningJamo(): Boolean =
    this in '\u1100'..'\u11FF' || this in '\uA960'..'\uA97F' || this in '\uD7B0'..'\uD7FF'

private fun Char.attachesToPrevious(): Boolean = isLowSurrogate() || when (Character.getType(this).toByte()) {
    Character.NON_SPACING_MARK, Character.ENCLOSING_MARK, Character.COMBINING_SPACING_MARK, Character.FORMAT -> true
    else -> false
}

package me.timschneeberger.rootlessjamesdsp.pvb

import java.util.Locale

/**
 * PVB device profiles of the general build (assets/pvb_profiles/<id>.json). Pure Kotlin, so the host tests read the
 * same asset files the app ships.
 *
 * A profile only sets PVB settings (pvb_settings); the upstream JamesDSP device profiles are separate and untouched.
 * The s26u build never applies a profile: it keeps its own defaults (PvbSettings / dsp_pvb_preferences.xml).
 */
data class DeviceProfile(
    val id: String,
    val name: String,
    /** Measured on the real device. false = conservative defaults and the "not measured" notice. */
    val measured: Boolean,
    /** Build.MANUFACTURER values, compared without case. Empty = any manufacturer. */
    val manufacturers: List<String>,
    /** Build.MODEL prefixes, compared without case. Empty = never matched by model (the neutral fallback). */
    val modelPrefixes: List<String>,
    /** PVB settings this profile writes (keys of [PvbSettings], values Float or Boolean). */
    val settings: Map<String, Any>,
    /** The S26U-specific analysis curves (speaker response, phone limiter estimate) apply to this device. */
    val phoneModelCurves: Boolean,
    /** Short device name for evidence tags ("실측 S26U"); empty for the neutral profile. */
    val shortName: String = "",
    /** Below this the speaker plays practically nothing (developer-mode graph: "이 폰이 못 내는 곳"), Hz. */
    val speakerFloorHz: Float = DEFAULT_SPEAKER_FLOOR_HZ,
    /**
     * The phone's bass protection threshold at our output (150-400 Hz, sine-equivalent dBFS) as a line over the media
     * volume: [protectDbAt50] at 50 % and [protectDbPerPct] per volume %. Measured on the S26U (UMIK-1, 2026-10-21:
     * about -15 dBFS at 50 %, -27 dBFS at 80 %); other phones carry the same line as an estimate ([measured] false).
     */
    val protectDbAt50: Float = DEFAULT_PROTECT_DB_AT_50,
    val protectDbPerPct: Float = DEFAULT_PROTECT_DB_PER_PCT,
) {
    /** Protection threshold at [volumePct] (0..100), dBFS, kept within -60..0. */
    fun protectThresholdDb(volumePct: Float): Float {
        val v = if (volumePct.isFinite()) volumePct.coerceIn(0f, 100f) else 50f
        return (protectDbAt50 + protectDbPerPct * (v - 50f)).coerceIn(-60f, 0f)
    }

    companion object {
        const val DEFAULT_SPEAKER_FLOOR_HZ = 150f
        const val DEFAULT_PROTECT_DB_AT_50 = -15f
        const val DEFAULT_PROTECT_DB_PER_PCT = -0.4f
    }

    fun matches(manufacturer: String?, model: String?): Boolean {
        if (modelPrefixes.isEmpty()) return false
        val man = manufacturer.orEmpty().trim().lowercase(Locale.ROOT)
        val mod = model.orEmpty().trim().uppercase(Locale.ROOT)
        if (manufacturers.isNotEmpty() && manufacturers.none { it.lowercase(Locale.ROOT) == man }) return false
        return modelPrefixes.any { it.isNotBlank() && mod.startsWith(it.uppercase(Locale.ROOT)) }
    }
}

object DeviceProfiles {
    const val NEUTRAL = "neutral"
    const val S26U = "s26u"
    const val ASSET_DIR = "pvb_profiles"

    /** Keys a profile may set, with their type. Anything else in a profile file is ignored. */
    val FLOAT_KEYS = setOf(
        PvbSettings.KEY_HP_HZ, PvbSettings.KEY_LOW_HZ, PvbSettings.KEY_LOW_DB, PvbSettings.KEY_LOW_Q,
        PvbSettings.KEY_HI_HZ, PvbSettings.KEY_HI_DB, PvbSettings.KEY_HI_Q, PvbSettings.KEY_HS_HZ, PvbSettings.KEY_HS_DB,
        PvbSettings.KEY_OUT_DB, PvbSettings.KEY_CEIL_DB, PvbSettings.KEY_RELEASE_MS, PvbSettings.KEY_VB_STRENGTH_DB,
    )
    val BOOL_KEYS = setOf(
        PvbSettings.KEY_MATCH_ON_DISABLE, PvbSettings.KEY_SPEAKER_ONLY, PvbSettings.KEY_VOL_LINK, PvbSettings.KEY_DYN_ON,
        PvbSettings.KEY_VB_ON, PvbSettings.KEY_VB_VOL_LINK,
    )

    fun parse(json: String): DeviceProfile {
        @Suppress("UNCHECKED_CAST")
        val o = ProfileJson.parse(json) as? Map<String, Any?> ?: throw IllegalArgumentException("profile is not an object")
        val id = o["id"] as? String ?: throw IllegalArgumentException("profile without id")
        @Suppress("UNCHECKED_CAST")
        val match = o["match"] as? Map<String, Any?> ?: emptyMap()
        @Suppress("UNCHECKED_CAST")
        val raw = o["settings"] as? Map<String, Any?> ?: emptyMap()
        val settings = LinkedHashMap<String, Any>()
        for ((k, v) in raw) {
            when {
                k in FLOAT_KEYS && v is Double && v.isFinite() -> settings[k] = v.toFloat()
                k in BOOL_KEYS && v is Boolean -> settings[k] = v
            }
        }
        return DeviceProfile(
            id = id,
            name = o["name"] as? String ?: id,
            measured = o["measured"] as? Boolean ?: false,
            manufacturers = strings(match["manufacturer"]),
            modelPrefixes = strings(match["model_prefixes"]),
            settings = settings,
            phoneModelCurves = o["phone_model_curves"] as? Boolean ?: false,
            shortName = o["short_name"] as? String ?: "",
            speakerFloorHz = num(o["speaker_floor_hz"], DeviceProfile.DEFAULT_SPEAKER_FLOOR_HZ, 40f, 400f),
            protectDbAt50 = num(o["protect_db_at_50"], DeviceProfile.DEFAULT_PROTECT_DB_AT_50, -60f, 0f),
            protectDbPerPct = num(o["protect_db_per_pct"], DeviceProfile.DEFAULT_PROTECT_DB_PER_PCT, -2f, 0f),
        )
    }

    private fun num(v: Any?, def: Float, lo: Float, hi: Float): Float =
        (v as? Double)?.toFloat()?.takeIf { it.isFinite() }?.coerceIn(lo, hi) ?: def

    private fun strings(v: Any?): List<String> = (v as? List<*>)?.filterIsInstance<String>() ?: emptyList()

    /** The first measured profile matching the device, else the neutral one (which must exist). */
    fun select(profiles: List<DeviceProfile>, manufacturer: String?, model: String?): DeviceProfile =
        profiles.firstOrNull { it.id != NEUTRAL && it.matches(manufacturer, model) }
            ?: profiles.firstOrNull { it.id == NEUTRAL }
            ?: throw IllegalStateException("no neutral profile")

    /**
     * What applying [profile] writes into pvb_settings: its settings, the caps applied, and processing off
     * (the first-run notice turns it on, [FirstRun.valuesOnConfirm]).
     */
    fun valuesFor(profile: DeviceProfile, caps: SafeCaps?): Map<String, Any> {
        val out = LinkedHashMap<String, Any>(profile.settings)
        if (caps != null) {
            fun cap(key: String, f: (Float) -> Float) { (out[key] as? Float)?.let { out[key] = f(it) } }
            cap(PvbSettings.KEY_OUT_DB) { it.coerceAtMost(caps.outDbMax) }
            cap(PvbSettings.KEY_CEIL_DB) { it.coerceAtMost(caps.ceilDbMax) }
            cap(PvbSettings.KEY_LOW_DB) { it.coerceAtMost(caps.lowDbMax) }
            cap(PvbSettings.KEY_LOW_Q) { it.coerceAtMost(caps.lowQMax) }
            cap(PvbSettings.KEY_HP_HZ) { it.coerceAtLeast(caps.hpHzMin) }
            cap(PvbSettings.KEY_RELEASE_MS) { it.coerceAtLeast(caps.releaseMsMin) }
        }
        out[PvbSettings.KEY_ENABLE] = false
        out[KEY_PROFILE_ID] = profile.id
        return out
    }

    /** Stored in pvb_settings: the profile last applied (the engine never reads it). */
    const val KEY_PROFILE_ID = "pvb_device_profile"
}

/** A small JSON reader for the profile assets (objects -> Map, arrays -> List, numbers -> Double). */
object ProfileJson {
    fun parse(text: String): Any? {
        val p = Parser(text)
        val v = p.value()
        p.ws()
        if (p.i != text.length) throw IllegalArgumentException("trailing data at ${p.i}")
        return v
    }

    private class Parser(val s: String) {
        var i = 0
        fun ws() { while (i < s.length && s[i].isWhitespace()) i++ }
        fun fail(what: String): Nothing = throw IllegalArgumentException("$what at $i")
        fun value(): Any? {
            ws()
            if (i >= s.length) fail("unexpected end")
            return when (s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                else -> num()
            }
        }
        fun lit(word: String, v: Any?): Any? {
            if (!s.startsWith(word, i)) fail("bad literal")
            i += word.length
            return v
        }
        fun num(): Double {
            val start = i
            while (i < s.length && (s[i].isDigit() || s[i] in "+-.eE")) i++
            return s.substring(start, i).toDoubleOrNull() ?: fail("bad number")
        }
        fun str(): String {
            i++ // opening quote
            val b = StringBuilder()
            while (true) {
                if (i >= s.length) fail("unterminated string")
                val c = s[i++]
                when (c) {
                    '"' -> return b.toString()
                    '\\' -> {
                        if (i >= s.length) fail("bad escape")
                        when (val e = s[i++]) {
                            '"', '\\', '/' -> b.append(e)
                            'n' -> b.append('\n')
                            't' -> b.append('\t')
                            'r' -> b.append('\r')
                            'b' -> b.append('\b')
                            'f' -> b.append('\u000C')
                            'u' -> {
                                if (i + 4 > s.length) fail("bad unicode escape")
                                b.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4
                            }
                            else -> fail("bad escape")
                        }
                    }
                    else -> b.append(c)
                }
            }
        }
        fun arr(): List<Any?> {
            i++
            val out = ArrayList<Any?>()
            ws()
            if (i < s.length && s[i] == ']') { i++; return out }
            while (true) {
                out += value()
                ws()
                if (i >= s.length) fail("unterminated array")
                when (s[i++]) {
                    ',' -> continue
                    ']' -> return out
                    else -> fail("expected , or ]")
                }
            }
        }
        fun obj(): Map<String, Any?> {
            i++
            val out = LinkedHashMap<String, Any?>()
            ws()
            if (i < s.length && s[i] == '}') { i++; return out }
            while (true) {
                ws()
                if (i >= s.length || s[i] != '"') fail("expected key")
                val k = str()
                ws()
                if (i >= s.length || s[i++] != ':') fail("expected :")
                out[k] = value()
                ws()
                if (i >= s.length) fail("unterminated object")
                when (s[i++]) {
                    ',' -> continue
                    '}' -> return out
                    else -> fail("expected , or }")
                }
            }
        }
    }
}

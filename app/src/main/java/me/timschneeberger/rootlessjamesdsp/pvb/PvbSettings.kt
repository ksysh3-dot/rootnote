package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.SharedPreferences

/**
 * User settings of the PVB card (shared preferences file [PREFS_NAME]). The keys are the ones used in
 * res/xml/dsp_pvb_preferences.xml; the defaults here must match the android:defaultValue there.
 */
data class PvbSettings(
    val enabled: Boolean = true,
    val matchOnDisable: Boolean = true,
    val speakerOnly: Boolean = true,
    val hpHz: Float = 100f,
    val lowHz: Float = 220f,
    val lowDb: Float = 3f,
    val lowQ: Float = 1f,
    val hiHz: Float = 4500f,
    val hiDb: Float = -3f,
    val hiQ: Float = 0.6f,
    val outDb: Float = -5f,
    val ceilDb: Float = -1f,
    val releaseMs: Float = 60f,
    val volLink: Boolean = false,
    val volRefPct: Float = 40f,
    val volSlope: Float = 0.19f,
    val volCapDb: Float = 6f,
    val volMaxDb: Float = 1f,
    val dynOn: Boolean = false,
    val dynRefDb: Float = -30f,
    val dynUpMaxDb: Float = 2f,
    val hsHz: Float = 2500f,
    val hsDb: Float = 0f,
    val vbOn: Boolean = false,          // virtual bass (experimental, alpha): off unless the user confirmed the warning
    val vbAlgo: Int = PvbModels.P1,
    val vbLevelDb: Float = PvbSettings.VB_LEVEL_DEFAULT,
    // Alpha 3.2 "볼륨 연동 세기": the layer gets weaker as the volume rises (VolumeLevelLink); applied at push time.
    val vbVolLink: Boolean = false,
    val vbVolRefPct: Float = VolumeLevelLink.REF_PCT_DEFAULT,
    val vbVolSlope: Float = VolumeLevelLink.SLOPE_DEFAULT,
    val vbVolMaxDb: Float = VolumeLevelLink.MAX_DB_DEFAULT,
    // Experimental layer options ("실험 기능"), all off by default; the engine ignores them while virtual bass is off.
    // Not part of device profiles (DeviceProfiles.FLOAT_KEYS / BOOL_KEYS) nor of the blind-comparison conditions.
    val xSmooth: Boolean = false,       // 층 출렁임 완화
    val xRise: Boolean = false,         // 급상승 완화
    val xS1m: Boolean = false,          // 배음별 단일 포락선 (P1 only)
    val xDense: Boolean = false,        // 복합음 감응 세기
    // Developer mode ("개발자 모드", general build only; DevParams). devOn = the user consented and the values below
    // reach the engine (P_DEV_ON); each value at its default is the model itself. Not part of device profiles.
    val devOn: Boolean = false,
    val devBoundaryHz: Float = DevParams.BOUNDARY.default,
    val devOutLoHz: Float = DevParams.OUT_LO.default,
    val devOutHiHz: Float = DevParams.OUT_HI.default,
    val devH2Db: Float = 0f,
    val devH3Db: Float = 0f,
    val devH4Db: Float = 0f,
    val devH5Db: Float = 0f,
    val devRolloffOffset: Float = 0f,
    val devSustDb: Float = 0f,
    val devPercDb: Float = 0f,
    val devAttackMs: Float = DevParams.ATTACK_DEFAULT,
    val devReleaseMs: Float = DevParams.RELEASE_DEFAULT,
    // Crosstalk cancellation ("공간감", pvb_xtc.h): off by default; applied on the speaker in landscape only
    // (PvbController). Head size is a hat-size preset, never measured. Not part of device profiles or comparisons.
    val xtcMode: Int = XTC_OFF,
    val xtcStrengthDb: Float = XTC_STRENGTH_DEFAULT,
    val xtcDistanceCm: Float = XTC_DISTANCE_DEFAULT,
    val xtcHatCm: Float = XTC_HAT_DEFAULT,
) {
    companion object {
        // Not "dsp_*": upstream presets, backups and device profiles swap those files behind the listeners' back.
        const val PREFS_NAME = "pvb_settings"

        const val KEY_ENABLE = "pvb_enable"
        const val KEY_MATCH_ON_DISABLE = "pvb_match_on_disable"
        const val KEY_SPEAKER_ONLY = "pvb_speaker_only"
        const val KEY_HP_HZ = "pvb_hp_hz"
        const val KEY_LOW_HZ = "pvb_low_hz"
        const val KEY_LOW_DB = "pvb_low_db"
        const val KEY_LOW_Q = "pvb_low_q"
        const val KEY_HI_HZ = "pvb_hi_hz"
        const val KEY_HI_DB = "pvb_hi_db"
        const val KEY_HI_Q = "pvb_hi_q"
        const val KEY_OUT_DB = "pvb_out_db"
        const val KEY_CEIL_DB = "pvb_ceil_db"
        const val KEY_RELEASE_MS = "pvb_release_ms"
        const val KEY_VOL_LINK = "pvb_vol_link"
        const val KEY_VOL_REF_PCT = "pvb_vol_ref_pct"
        const val KEY_VOL_SLOPE = "pvb_vol_slope"
        const val KEY_VOL_CAP_DB = "pvb_vol_cap_db"
        const val KEY_VOL_MAX_DB = "pvb_vol_max_db"
        const val KEY_DYN_ON = "pvb_dyn_enable"
        const val KEY_DYN_REF_DB = "pvb_dyn_ref_db"
        const val KEY_DYN_UP_MAX_DB = "pvb_dyn_up_max_db"
        const val KEY_HS_HZ = "pvb_hs_hz"
        const val KEY_HS_DB = "pvb_hs_db"
        const val KEY_VB_ON = "pvb_vb_enable"
        const val KEY_VB_ALGO = "pvb_vb_algo"
        /** Alpha 1/2 discrete level list (a string). Read once by the alpha 3 migration, then left untouched. */
        const val KEY_VB_LEVEL_DB = "pvb_vb_level_db"
        /** Alpha 3 strength slider (a float, whole dB in [VB_LEVEL_MIN]..[VB_LEVEL_MAX]). */
        const val KEY_VB_STRENGTH_DB = "pvb_vb_strength_db"
        /** Not persisted: the preset control is derived from model + level. */
        const val KEY_VB_MODE = "pvb_vb_mode"
        /** Alpha 3.1 "곡별 세기 기억" (default off). Not part of [PvbSettings]: the engine never reads it. */
        const val KEY_VB_TRACK_MEMORY = "pvb_vb_track_memory"
        /** Not persisted: opens the "기억된 곡" list. */
        const val KEY_VB_TRACK_LIST = "pvb_vb_track_list"
        /** Not persisted: opens the alpha 3.3 live blind comparison (LiveAbActivity). */
        const val KEY_VB_LIVE_AB = "pvb_vb_live_ab"
        /** Alpha 3.2 "볼륨 연동 세기" (default off) and its three sliders. */
        const val KEY_VB_VOL_LINK = "pvb_vb_vol_link"
        const val KEY_VB_VOL_REF_PCT = "pvb_vb_vol_ref_pct"
        const val KEY_VB_VOL_SLOPE = "pvb_vb_vol_slope"
        const val KEY_VB_VOL_MAX_DB = "pvb_vb_vol_max_db"
        /** Experimental layer options (switches in the "실험 기능" group, default off). */
        const val KEY_X_SMOOTH = "pvb_x_smooth"
        const val KEY_X_RISE = "pvb_x_rise"
        const val KEY_X_S1M = "pvb_x_s1m"
        const val KEY_X_DENSE = "pvb_x_dense"
        /** Crosstalk cancellation ("공간감"): list values as strings, distance as a slider float. */
        const val KEY_XTC_MODE = "pvb_xtc_mode"
        const val KEY_XTC_STRENGTH = "pvb_xtc_strength"
        const val KEY_XTC_DISTANCE = "pvb_xtc_distance_cm"
        const val KEY_XTC_HEAD = "pvb_xtc_head"
        const val XTC_OFF = 0
        const val XTC_CENTRE = 1
        const val XTC_FULL = 2
        const val XTC_STRENGTH_DEFAULT = -6f
        const val XTC_DISTANCE_DEFAULT = 40f
        const val XTC_DISTANCE_MIN = 25f
        const val XTC_DISTANCE_MAX = 60f
        const val XTC_HAT_DEFAULT = 57f
        /** Speaker spacing in landscape and the feedback band: device and design values, not user settings. */
        const val XTC_SPACING_CM = 15.5f
        const val XTC_LO_HZ = 400f
        const val XTC_HI_HZ = 8000f
        private val XTC_STRENGTHS = listOf(-6f, -4.5f, -3f)
        private val XTC_HATS = listOf(54f, 57f, 60f)

        /** Not persisted: the "실험 기능" header and the feedback link (opens GitHub Issues). */
        const val KEY_X_HEADER = "pvb_x_header"
        const val KEY_X_FEEDBACK = "pvb_x_feedback"
        const val KEY_VB_MODEL_SCHEMA = "pvb_vb_model_schema"
        const val KEY_VB_LEGACY_MODEL = "pvb_vb_alpha1_model"
        /** The alpha 2 model a schema-3 migration replaced (only the reference is replaced). */
        const val KEY_VB_ALPHA2_MODEL = "pvb_vb_alpha2_model"
        /** 2 = alpha 2 model keys; 3 = alpha 3 (reference -> P1 once, level slider). */
        const val VB_MODEL_SCHEMA = 3

        /** Virtual bass algorithms (same numbers as pvb::VbAlgo). */
        const val VB_HPV = 0
        const val VB_BANKSTOWN = 1
        const val VB_HPV52M = 2
        const val VB_GENTLE = 3
        const val VB_GENTLE_STRONG = 4
        const val VB_GENTLE_ADAPTIVE = 5
        /** Layer silent, algorithm (and its latency) kept: the reference side of the virtual bass blind comparisons. */
        const val VB_LEVEL_OFF = -120f
        /** Strength slider range, dB re the 'faithful' level, whole-dB steps (the engine accepts up to +12). */
        const val VB_LEVEL_MIN = 0f
        const val VB_LEVEL_MAX = 12f
        const val VB_LEVEL_DEFAULT = 6f

        /** Any number to a slider value: whole dB, clamped into the slider range; non-finite gives the default. */
        fun clampLevel(v: Float): Float =
            if (v.isFinite()) Math.round(v).toFloat().coerceIn(VB_LEVEL_MIN, VB_LEVEL_MAX) else VB_LEVEL_DEFAULT

        fun vbAlgoName(algo: Int) = PvbModels.fromId(algo)?.title ?: when (algo) {
            VB_BANKSTOWN -> "Bankstown"
            VB_HPV52M -> "hpv52m"
            VB_GENTLE_ADAPTIVE -> "적응형 배음 완화 (시험)"
            else -> "hpv"
        }

        /**
         * Upgrade the virtual bass model and level once. EQ, output, enable and historical A/B results are untouched.
         * - alpha 1 names / unknown -> default model (P1); the old name is kept in [KEY_VB_LEGACY_MODEL].
         * - schema < 3 and the alpha 2 reference -> P1 (one time; [KEY_VB_ALPHA2_MODEL] records it). Any other
         *   current model is kept, and choosing the reference again later is respected.
         * - the old level string (-6..+9) -> slider value clamped into 0..12; no old level -> the new default.
         */
        fun migrateVirtualBassModel(p: SharedPreferences) {
            val all = p.all
            val raw = all[KEY_VB_ALGO]
            val old = raw as? String ?: PvbModels.DEFAULT_KEY
            val schema = try { p.getInt(KEY_VB_MODEL_SCHEMA, 0) } catch (_: ClassCastException) { 0 }
            val fromReference = schema < VB_MODEL_SCHEMA && old == PvbModels.REFERENCE_KEY
            val current = if (fromReference) PvbModels.DEFAULT_KEY else PvbModels.fromKey(old).key
            val strength = all[KEY_VB_STRENGTH_DB]
            val strengthOk = strength is Float && strength.isFinite() && clampLevel(strength) == strength
            if (old == current && schema == VB_MODEL_SCHEMA && raw is String && strengthOk) return
            val edit = p.edit().putString(KEY_VB_ALGO, current).putInt(KEY_VB_MODEL_SCHEMA, VB_MODEL_SCHEMA)
            if (old != current && !fromReference && p.str(KEY_VB_LEGACY_MODEL, "").isEmpty())
                edit.putString(KEY_VB_LEGACY_MODEL, old)
            if (fromReference) edit.putString(KEY_VB_ALPHA2_MODEL, old)
            if (!strengthOk) edit.putFloat(KEY_VB_STRENGTH_DB, migratedLevel(all[KEY_VB_LEVEL_DB], strength))
            edit.apply()
        }

        /** The slider value for an old list value (string) or a damaged slider value. */
        private fun migratedLevel(legacy: Any?, strength: Any?): Float {
            (strength as? Number)?.toFloat()?.takeIf { it.isFinite() }?.let { return clampLevel(it) }
            val old = when (legacy) {
                is String -> legacy.trim().toFloatOrNull()
                is Number -> legacy.toFloat()
                else -> null
            }
            return if (old != null && old.isFinite()) clampLevel(old) else VB_LEVEL_DEFAULT
        }

        /**
         * The settings as the engine plays them. The last step is [PvbBuild.finish]: in the general build the
         * first-run gate and the safe caps ([SafeCaps.GENERAL]); in the s26u build it changes nothing.
         */
        fun load(p: SharedPreferences): PvbSettings {
            val d = PvbSettings()
            return PvbBuild.finish(PvbSettings(
                enabled = p.bool(KEY_ENABLE, d.enabled),
                matchOnDisable = p.bool(KEY_MATCH_ON_DISABLE, d.matchOnDisable),
                speakerOnly = p.bool(KEY_SPEAKER_ONLY, d.speakerOnly),
                hpHz = p.float(KEY_HP_HZ, d.hpHz),
                lowHz = p.float(KEY_LOW_HZ, d.lowHz),
                lowDb = p.float(KEY_LOW_DB, d.lowDb),
                lowQ = p.float(KEY_LOW_Q, d.lowQ),
                hiHz = p.float(KEY_HI_HZ, d.hiHz),
                hiDb = p.float(KEY_HI_DB, d.hiDb),
                hiQ = p.float(KEY_HI_Q, d.hiQ),
                outDb = p.float(KEY_OUT_DB, d.outDb),
                ceilDb = p.float(KEY_CEIL_DB, d.ceilDb),
                releaseMs = p.float(KEY_RELEASE_MS, d.releaseMs),
                volLink = p.bool(KEY_VOL_LINK, d.volLink),
                volRefPct = p.float(KEY_VOL_REF_PCT, d.volRefPct),
                volSlope = p.float(KEY_VOL_SLOPE, d.volSlope),
                volCapDb = p.float(KEY_VOL_CAP_DB, d.volCapDb),
                volMaxDb = p.float(KEY_VOL_MAX_DB, d.volMaxDb),
                dynOn = p.bool(KEY_DYN_ON, d.dynOn),
                dynRefDb = p.float(KEY_DYN_REF_DB, d.dynRefDb),
                dynUpMaxDb = p.float(KEY_DYN_UP_MAX_DB, d.dynUpMaxDb),
                hsHz = p.float(KEY_HS_HZ, d.hsHz),
                hsDb = p.float(KEY_HS_DB, d.hsDb),
                vbOn = p.bool(KEY_VB_ON, d.vbOn),
                vbAlgo = PvbModels.fromKey(p.str(KEY_VB_ALGO, PvbModels.DEFAULT_KEY)).id,
                vbLevelDb = clampLevel(p.float(KEY_VB_STRENGTH_DB, d.vbLevelDb)),
                vbVolLink = p.bool(KEY_VB_VOL_LINK, d.vbVolLink),
                vbVolRefPct = Math.round(p.float(KEY_VB_VOL_REF_PCT, d.vbVolRefPct)).toFloat()
                    .coerceIn(VolumeLevelLink.REF_PCT_MIN, VolumeLevelLink.REF_PCT_MAX),
                vbVolSlope = p.float(KEY_VB_VOL_SLOPE, d.vbVolSlope)
                    .coerceIn(VolumeLevelLink.SLOPE_MIN, VolumeLevelLink.SLOPE_MAX),
                vbVolMaxDb = p.float(KEY_VB_VOL_MAX_DB, d.vbVolMaxDb)
                    .coerceIn(VolumeLevelLink.MAX_DB_MIN, VolumeLevelLink.MAX_DB_MAX),
                xSmooth = p.bool(KEY_X_SMOOTH, d.xSmooth),
                xRise = p.bool(KEY_X_RISE, d.xRise),
                xS1m = p.bool(KEY_X_S1M, d.xS1m),
                xDense = p.bool(KEY_X_DENSE, d.xDense),
                devOn = PvbBuild.general && p.bool(DevParams.KEY_DEV_ON, false),
                devBoundaryHz = DevParams.clampStored(DevParams.KEY_BOUNDARY, p.float(DevParams.KEY_BOUNDARY, d.devBoundaryHz)),
                devOutLoHz = DevParams.clampStored(DevParams.KEY_OUT_LO, p.float(DevParams.KEY_OUT_LO, d.devOutLoHz)),
                devOutHiHz = DevParams.clampStored(DevParams.KEY_OUT_HI, p.float(DevParams.KEY_OUT_HI, d.devOutHiHz)),
                devH2Db = DevParams.clampStored(DevParams.KEY_H2, p.float(DevParams.KEY_H2, d.devH2Db)),
                devH3Db = DevParams.clampStored(DevParams.KEY_H3, p.float(DevParams.KEY_H3, d.devH3Db)),
                devH4Db = DevParams.clampStored(DevParams.KEY_H4, p.float(DevParams.KEY_H4, d.devH4Db)),
                devH5Db = DevParams.clampStored(DevParams.KEY_H5, p.float(DevParams.KEY_H5, d.devH5Db)),
                devRolloffOffset = DevParams.clampStored(DevParams.KEY_ROLLOFF, p.float(DevParams.KEY_ROLLOFF, d.devRolloffOffset)),
                devSustDb = DevParams.clampStored(DevParams.KEY_SUST, p.float(DevParams.KEY_SUST, d.devSustDb)),
                devPercDb = DevParams.clampStored(DevParams.KEY_PERC, p.float(DevParams.KEY_PERC, d.devPercDb)),
                devAttackMs = DevParams.clampStored(DevParams.KEY_ATTACK, p.float(DevParams.KEY_ATTACK, d.devAttackMs)),
                devReleaseMs = DevParams.clampStored(DevParams.KEY_RELEASE, p.float(DevParams.KEY_RELEASE, d.devReleaseMs)),
                xtcMode = p.str(KEY_XTC_MODE, "0").trim().toIntOrNull()?.takeIf { it in XTC_OFF..XTC_FULL } ?: d.xtcMode,
                xtcStrengthDb = p.str(KEY_XTC_STRENGTH, "-6").trim().toFloatOrNull()?.takeIf { it in XTC_STRENGTHS }
                    ?: d.xtcStrengthDb,
                xtcDistanceCm = Math.round(p.float(KEY_XTC_DISTANCE, d.xtcDistanceCm)).toFloat()
                    .coerceIn(XTC_DISTANCE_MIN, XTC_DISTANCE_MAX),
                xtcHatCm = p.str(KEY_XTC_HEAD, "57").trim().toFloatOrNull()?.takeIf { it in XTC_HATS } ?: d.xtcHatCm,
            ))
        }

        // List preferences store strings.
        private fun SharedPreferences.str(key: String, def: String): String =
            try {
                getString(key, def) ?: def
            } catch (ignored: ClassCastException) {
                def
            }

        // A value stored with another type (for example by an older build) falls back to the default.
        private fun SharedPreferences.float(key: String, def: Float): Float =
            try {
                getFloat(key, def).takeIf { it.isFinite() } ?: def
            } catch (ignored: ClassCastException) {
                def
            }

        private fun SharedPreferences.bool(key: String, def: Boolean): Boolean =
            try {
                getBoolean(key, def)
            } catch (ignored: ClassCastException) {
                def
            }
    }
}


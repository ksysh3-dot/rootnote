package me.timschneeberger.rootlessjamesdsp.pvb

import java.util.Locale

/**
 * "내 설정 복사" (앱 정보): one plain-text block a user can paste into feedback, so a starting point for their phone
 * can be built from it. It carries the app version, the phone model, the EQ and output values, virtual bass (model,
 * strength, volume link), spatial, and the developer-mode share code (the virtual-bass detail values). Nothing else:
 * no song, no app list, no account.
 *
 * Pure Kotlin (host-tested in tools/pvb-harness/jvm/DevModeTest.kt).
 */
object SettingsSummary {
    private fun f(v: Float, digits: Int = 1): String = String.format(Locale.US, "%.${digits}f", v)
    private fun db(v: Float): String = (if (v > 0f) "+" else "") + f(v) + " dB"

    fun text(s: PvbSettings, model: String, appVersion: String, devCode: String): String {
        val vbModel = PvbModels.fromId(s.vbAlgo)?.key ?: s.vbAlgo.toString()
        val spatial = when (s.xtcMode) {
            PvbSettings.XTC_CENTRE -> "centre"
            PvbSettings.XTC_FULL -> "full"
            else -> "off"
        }
        return buildString {
            appendLine("Rootnote $appVersion · $model")
            appendLine("on=${s.enabled} speakerOnly=${s.speakerOnly}")
            appendLine("EQ: hp ${f(s.hpHz, 0)} Hz · low-mid ${db(s.lowDb)} @ ${f(s.lowHz, 0)} Hz Q ${f(s.lowQ, 2)} · " +
                "treble ${db(s.hiDb)} @ ${f(s.hiHz, 0)} Hz Q ${f(s.hiQ, 2)} · tilt ${db(s.hsDb)} @ ${f(s.hsHz, 0)} Hz")
            appendLine("out ${db(s.outDb)} · ceiling ${db(s.ceilDb)} · volume link ${s.volLink} · quiet bass ${s.dynOn}")
            appendLine("virtual bass: ${s.vbOn} · $vbModel ${db(s.vbLevelDb)} · volume link ${s.vbVolLink}")
            appendLine("spatial: $spatial ${db(s.xtcStrengthDb)} · ${f(s.xtcDistanceCm, 0)} cm · hat ${f(s.xtcHatCm, 0)} · " +
                "balance ${db(s.xtcBalLoDb)} / ${db(s.xtcBalHiDb)}")
            append("code: $devCode")
        }
    }
}

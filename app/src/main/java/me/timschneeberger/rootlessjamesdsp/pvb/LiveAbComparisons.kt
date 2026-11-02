package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.roundToInt

/**
 * Current live blind comparisons: P1 strength, P1 volume link, and the independent spatial pairs.
 * No measured loudness trims exist for the P1 comparisons (0 dB, trimMeasured=false).
 * They use common output headroom except volume-link on/off (0 dB headroom), where raising the
 * volume would alter the tested link. Historical records remain readable after pair removal.
 * Pure Kotlin; tested by tools/pvb-harness/jvm/LiveAbTest.kt.
 */
object LiveAbComparisons {
    /** The size step of the "lower level" condition. */
    const val LOWER_DB = 3f

    class Side(
        val id: String,
        val trimDb: Float,
        val trimMeasured: Boolean,
        private val labelOf: (PvbSettings) -> String,
        private val strengthOf: ((PvbSettings) -> Float)? = null,
        val apply: (PvbSettings) -> PvbSettings,
    ) {
        /** Display label with the user's current slider value (e.g. "P1 +6 dB"). */
        fun label(base: PvbSettings): String = displayLabel(id, labelOf(base), strengthOf?.invoke(base))
        /** Stable actual-dB text in research records and runtime conditions. */
        fun actualLabel(base: PvbSettings): String = labelOf(base)
    }

    class Comparison(
        val id: String,
        val label: String,
        val description: String,
        val headroomDb: Float,
        val sides: List<Side>,
    ) {
        /** The engine-facing condition of one side, labelled for this run. */
        fun condition(side: Side, base: PvbSettings): PvbRuntime.AbCondition =
            PvbRuntime.AbCondition(side.id, side.actualLabel(base), side.trimDb, headroomDb, side.apply)
    }

    /** The user's slider value as the engine reads it (whole dB, -6..12; the model's own level trim is added where the engine level is formed, [VolumeLevelLink.levelFor]). */
    fun userLevel(base: PvbSettings): Float = PvbSettings.clampLevel(base.vbLevelDb)

    /** [LOWER_DB] below the user's level, not below the volume link's floor. */
    fun loweredLevel(base: PvbSettings): Float = (userLevel(base) - LOWER_DB).coerceAtLeast(VolumeLevelLink.FLOOR_DB)

    fun dbText(v: Float): String {
        val r = v.roundToInt()
        return if (r > 0) "+$r dB" else "$r dB"
    }

    /** Convert only a known strength prefix for display. Original saved labels and JSON/CSV stay actual. */
    fun displayLabel(id: String, actualLabel: String, actualDb: Float?): String {
        if (actualDb == null || id !in setOf("p1", "p1_minus3", "p1_link_on", "p1_link_off")) return actualLabel
        return actualLabel.replaceFirst(Regex("^P1 [+-]?[0-9]+ dB"), "P1 ${dbText(StrengthDisplay.UI.toDisplay(actualDb))}")
    }

    private const val UNMEASURED = 0f

    val P1 = Side("p1", UNMEASURED, false, { "P1 ${dbText(userLevel(it))}" }, ::userLevel) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it))
    }
    val P1_LOWER = Side("p1_minus3", UNMEASURED, false, { "P1 ${dbText(loweredLevel(it))} (3 dB 작게)" }, ::loweredLevel) {
        PvbAbConditions.v11vb(it, PvbModels.P1, loweredLevel(it))
    }
    val P1_LINK_ON = Side("p1_link_on", UNMEASURED, false, { "P1 ${dbText(userLevel(it))} · 볼륨 연동 켬" }, ::userLevel) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it)).copy(vbVolLink = true)   // the user's link sliders
    }
    val P1_LINK_OFF = Side("p1_link_off", UNMEASURED, false, { "P1 ${dbText(userLevel(it))} · 볼륨 연동 끔" }, ::userLevel) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it))
    }
    // Spatial (review 2026-10-23, questions 1-2): the canceller against the M/S widener with the same mid and side
    // magnitude per frequency (pvb_xtc.h MS_*), at the user's strength, distance and head size, virtual bass off.
    // Equal level by construction (test_xtc.py: within 0.4 dB per third octave, total within 0.2 dB), so 0 dB trim;
    // equal latency (the canceller runs with the widener's 256-sample delay).
    // Upright is off on both sides: the comparison is for the phone held sideways.
    private fun spatial(s: PvbSettings, mode: Int) =
        PvbAbConditions.v11(s).copy(xtcMode = mode, xtcPortrait = PvbSettings.XTC_PORTRAIT_OFF)

    val XTC_CENTRE = Side("xtc_centre", UNMEASURED, false, { "공간감 중앙 보존 (크로스토크 제거)" }) {
        spatial(it, PvbSettings.XTC_CENTRE_ALIGNED)   // same latency as the widener side
    }
    val MS_CENTRE = Side("ms_centre", UNMEASURED, false, { "같은 크기의 좌우 넓히기 (지연 없음)" }) {
        spatial(it, PvbSettings.XTC_MS_CENTRE)
    }
    val XTC_FULL = Side("xtc_full", UNMEASURED, false, { "공간감 완전 (크로스토크 제거)" }) {
        spatial(it, PvbSettings.XTC_FULL_ALIGNED)
    }
    val MS_FULL = Side("ms_full", UNMEASURED, false, { "같은 크기의 좌우 넓히기 (지연 없음, 완전 기준)" }) {
        spatial(it, PvbSettings.XTC_MS_FULL)
    }
    private const val SPATIAL_NOTE = "폰을 가로로 들고 들으세요(세로로 들면 두 쪽 모두 공간감이 꺼집니다). 두 쪽은 중앙과 좌우 성분의 크기가 " +
        "대역마다 같고, 크로스토크 제거의 지연 구조만 다릅니다. 그래서 음량 보정 없이 같은 크기입니다. 가상 저음은 두 쪽 모두 끕니다. " +
        "공간감 세기·듣는 거리·머리 크기는 내 설정을 씁니다."

    private const val TRIM_NOTE = "음량 보정값은 아직 측정하지 않아 0 dB입니다."


    val ALL: List<Comparison> = listOf(
        Comparison("p1_vs_p1_minus3", "P1 vs P1 3 dB 작게 (크기)",
            "같은 P1에서 가상 저음 크기만 3 dB 다릅니다(지금 슬라이더 값 기준). $TRIM_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(P1, P1_LOWER)),
        Comparison("p1_link_on_vs_off", "P1 볼륨 연동 켬 vs 끔",
            "한쪽만 「볼륨 연동 세기」를 켭니다(내 설정의 시작 볼륨·감소 기울기·최대 감소). 이 비교만 출력을 낮추지 않으니 " +
                "평소 듣는 볼륨 그대로 들으세요. 볼륨이 시작 볼륨보다 높아야 차이가 생깁니다. $TRIM_NOTE",
            0f, listOf(P1_LINK_ON, P1_LINK_OFF)),
        Comparison("xtc_centre_vs_ms", "공간감 중앙 보존 vs 같은 크기 좌우 넓히기",
            "크로스토크 제거(중앙 보존)가 단순히 좌우 성분을 키운 것보다 나은지 봅니다. $SPATIAL_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(XTC_CENTRE, MS_CENTRE)),
        Comparison("xtc_full_vs_ms", "공간감 완전 vs 같은 크기 좌우 넓히기",
            "크로스토크 제거(완전)가 같은 크기의 단순 넓히기보다 나은지 봅니다. $SPATIAL_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(XTC_FULL, MS_FULL)),
    )

    fun byId(id: String?): Comparison? = ALL.firstOrNull { it.id == id }
}

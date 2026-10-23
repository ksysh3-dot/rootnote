package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.roundToInt

/**
 * Alpha 3.3 "실청 블라인드 비교": the predefined comparisons. Same level-matching scheme as the existing blind
 * comparison ([PvbAbConditions]): every condition starts from EQ v1.1 ([PvbAbConditions.v11vb], which also switches the
 * alpha 3.2 volume link off), carries a loudness trim on the output gain, and plays behind a common headroom in the
 * engine's final gate (the listener turns the volume up instead), so the phone's own processor before the volume
 * control hardly compresses either side.
 *
 * Trims: no album measurement exists yet for the P1 / D2 / reference conditions, so they are 0 dB and every record
 * says so ([Side.trimMeasured] = false). Within one model only the layer level differs; the measured hpv trims for
 * that difference are 0.01-0.13 dB (PvbAbConditions), far below the 0.6 dB song-to-song spread of the EQ trims.
 *
 * Exception: "volume link on vs off" runs without the common headroom ([Comparison.headroomDb] = 0), because the link
 * reads the media volume: with the headroom the listener would raise the volume and the link would take off more
 * than it does at the usual listening level. Only this comparison turns the link on, on one side.
 *
 * Pure Kotlin (no Android types): host-tested in tools/pvb-harness/jvm/LiveAbTest.kt.
 */
object LiveAbComparisons {
    /** The size step of the "lower level" condition. */
    const val LOWER_DB = 3f

    class Side(
        val id: String,
        val trimDb: Float,
        val trimMeasured: Boolean,
        private val labelOf: (PvbSettings) -> String,
        val apply: (PvbSettings) -> PvbSettings,
    ) {
        /** Display label with the user's current slider value (e.g. "P1 +6 dB"). */
        fun label(base: PvbSettings): String = labelOf(base)
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
            PvbRuntime.AbCondition(side.id, side.label(base), side.trimDb, headroomDb, side.apply)
    }

    /** The user's slider value as the engine reads it (whole dB, 0..12). */
    fun userLevel(base: PvbSettings): Float = PvbSettings.clampLevel(base.vbLevelDb)

    /** [LOWER_DB] below the user's level, not below the volume link's floor. */
    fun loweredLevel(base: PvbSettings): Float = (userLevel(base) - LOWER_DB).coerceAtLeast(VolumeLevelLink.FLOOR_DB)

    fun dbText(v: Float): String {
        val r = v.roundToInt()
        return if (r > 0) "+$r dB" else "$r dB"
    }

    private const val UNMEASURED = 0f

    val P1 = Side("p1", UNMEASURED, false, { "P1 ${dbText(userLevel(it))}" }) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it))
    }
    val P1_LOWER = Side("p1_minus3", UNMEASURED, false, { "P1 ${dbText(loweredLevel(it))} (3 dB 작게)" }) {
        PvbAbConditions.v11vb(it, PvbModels.P1, loweredLevel(it))
    }
    val P1_LINK_ON = Side("p1_link_on", UNMEASURED, false, { "P1 ${dbText(userLevel(it))} · 볼륨 연동 켬" }) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it)).copy(vbVolLink = true)   // the user's link sliders
    }
    val P1_LINK_OFF = Side("p1_link_off", UNMEASURED, false, { "P1 ${dbText(userLevel(it))} · 볼륨 연동 끔" }) {
        PvbAbConditions.v11vb(it, PvbModels.P1, userLevel(it))
    }
    val D2 = Side("d2", UNMEASURED, false, { "D2 (ID 7) ${dbText(userLevel(it))}" }) {
        PvbAbConditions.v11vb(it, PvbModels.D2, userLevel(it))
    }
    val ID4 = Side("id4", UNMEASURED, false, { "기준형 (ID 4) ${dbText(userLevel(it))}" }) {
        PvbAbConditions.v11vb(it, PvbModels.REFERENCE, userLevel(it))
    }

    // Spatial (review 2026-10-23, questions 1-2): the canceller against the M/S widener with the same mid and side
    // magnitude per frequency (pvb_xtc.h MS_*), at the user's strength, distance and head size, virtual bass off.
    // Equal level by construction (test_xtc.py: within 0.3 dB per third octave, total within 0.2 dB), so 0 dB trim.
    // Upright is off on both sides: the comparison is for the phone held sideways.
    private fun spatial(s: PvbSettings, mode: Int) =
        PvbAbConditions.v11(s).copy(xtcMode = mode, xtcPortrait = PvbSettings.XTC_PORTRAIT_OFF)

    val XTC_CENTRE = Side("xtc_centre", UNMEASURED, false, { "공간감 중앙 보존 (크로스토크 제거)" }) {
        spatial(it, PvbSettings.XTC_CENTRE)
    }
    val MS_CENTRE = Side("ms_centre", UNMEASURED, false, { "같은 크기의 좌우 넓히기 (지연 없음)" }) {
        spatial(it, PvbSettings.XTC_MS_CENTRE)
    }
    val XTC_FULL = Side("xtc_full", UNMEASURED, false, { "공간감 완전 (크로스토크 제거)" }) {
        spatial(it, PvbSettings.XTC_FULL)
    }
    val MS_FULL = Side("ms_full", UNMEASURED, false, { "같은 크기의 좌우 넓히기 (지연 없음, 완전 기준)" }) {
        spatial(it, PvbSettings.XTC_MS_FULL)
    }
    private const val SPATIAL_NOTE = "폰을 가로로 들고 들으세요(세로로 들면 두 쪽 모두 공간감이 꺼집니다). 두 쪽은 중앙과 좌우 성분의 크기가 " +
        "대역마다 같고, 크로스토크 제거의 지연 구조만 다릅니다. 그래서 음량 보정 없이 같은 크기입니다. 가상 저음은 두 쪽 모두 끕니다. " +
        "공간감 세기·듣는 거리·머리 크기는 내 설정을 씁니다."

    private const val TRIM_NOTE = "음량 보정값은 아직 측정하지 않아 0 dB입니다."
    private const val MODEL_NOTE = "모델이 바뀔 때마다 엔진이 짧게(30 ms) 페이드하고 모델을 새로 시작합니다. 어느 쪽으로 바꿔도 같으므로 " +
        "그 자체로는 구분되지 않습니다."

    val ALL: List<Comparison> = listOf(
        Comparison("p1_vs_p1_minus3", "P1 vs P1 3 dB 작게 (크기)",
            "같은 P1에서 가상 저음 크기만 3 dB 다릅니다(지금 슬라이더 값 기준). $TRIM_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(P1, P1_LOWER)),
        Comparison("p1_link_on_vs_off", "P1 볼륨 연동 켬 vs 끔",
            "한쪽만 「볼륨 연동 세기」를 켭니다(내 설정의 시작 볼륨·감소 기울기·최대 감소). 이 비교만 출력을 낮추지 않으니 " +
                "평소 듣는 볼륨 그대로 들으세요. 볼륨이 시작 볼륨보다 높아야 차이가 생깁니다. $TRIM_NOTE",
            0f, listOf(P1_LINK_ON, P1_LINK_OFF)),
        Comparison("p1_vs_d2", "P1 vs D2 (ID 7)",
            "같은 크기에서 모델만 다릅니다. $MODEL_NOTE $TRIM_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(P1, D2)),
        Comparison("p1_vs_id4", "P1 vs 기준형 (ID 4)",
            "같은 크기에서 모델만 다릅니다. $MODEL_NOTE $TRIM_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(P1, ID4)),
        Comparison("p1_vs_d2_vs_id4", "P1 vs D2 vs 기준형 (셋)",
            "같은 크기에서 세 모델을 A·B·C로 비교합니다. $MODEL_NOTE $TRIM_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(P1, D2, ID4)),
        Comparison("xtc_centre_vs_ms", "공간감 중앙 보존 vs 같은 크기 좌우 넓히기",
            "크로스토크 제거(중앙 보존)가 단순히 좌우 성분을 키운 것보다 나은지 봅니다. $SPATIAL_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(XTC_CENTRE, MS_CENTRE)),
        Comparison("xtc_full_vs_ms", "공간감 완전 vs 같은 크기 좌우 넓히기",
            "크로스토크 제거(완전)가 같은 크기의 단순 넓히기보다 나은지 봅니다. $SPATIAL_NOTE",
            PvbAbConditions.HEADROOM_DB, listOf(XTC_FULL, MS_FULL)),
    )

    fun byId(id: String?): Comparison? = ALL.firstOrNull { it.id == id }
}

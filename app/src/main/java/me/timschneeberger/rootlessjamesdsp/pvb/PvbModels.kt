package me.timschneeberger.rootlessjamesdsp.pvb

/** Stable saved keys and native IDs. List positions are never engine IDs. */
object PvbModels {
    data class Model(val key: String, val id: Int, val title: String, val description: String)
    const val GENTLE12 = 3
    const val REFERENCE = 4
    const val P1 = 6
    const val D2 = 7
    const val J2 = 8
    const val OSC = 9
    const val OSC_CORRECT = 10
    const val REFERENCE_KEY = "alpha2_reference"
    const val P1_KEY = "alpha2_p1"
    const val GENTLE12_KEY = "alpha3_gentle12"
    /** Alpha 3: P1 is the default (2026-10-19/20 phone listening: less noise than the reference, kept the gains). */
    const val DEFAULT_KEY = P1_KEY

    val models: List<Model> = listOf(
        Model(P1_KEY, P1, "연결형 (P1)", "음이 잠깐 약해질 때도 배음을 이어가며, 강약과 음정 변화를 함께 따라갑니다. 기본 모델입니다."),
        Model(REFERENCE_KEY, REFERENCE, "기준형", "상부 배음을 완화한 알파 2 기준 방식입니다 (24 dB/oct). 다른 모델과 비교할 때 기준으로 사용하세요."),
        Model("alpha2_d2", D2, "세부 추적 (D2)", "빠른 강약·음정 변화를 짧게 다시 읽습니다. 조건이 맞지 않으면 연결형으로 동작합니다."),
        Model("alpha2_j2", J2, "변조 추적 (J2)", "규칙적으로 울렁이는 저음을 추적합니다. 조건이 맞지 않으면 세부 추적으로 동작합니다."),
        Model("alpha2_osc", OSC, "연속 합성", "위상을 이어서 배음을 만듭니다. 연결형·세부 추적과 질감을 비교해 보세요."),
        Model("alpha2_osc_correct", OSC_CORRECT, "연속 합성 · 위상 보정", "연속 합성에 작은 위상 보정을 더합니다. 보정 없는 연속 합성과 비교해 보세요."),
        Model(GENTLE12_KEY, GENTLE12, "부드러운 저음 (12 dB/oct)", "위쪽 배음을 덜 줄여(12 dB/oct) 효과가 더 잘 들립니다. 대신 버즈음이 생길 가능성이 큽니다."),
    )

    val defaultModel: Model get() = models.first { it.key == DEFAULT_KEY }

    fun fromKey(key: String?): Model = models.firstOrNull { it.key == key } ?: defaultModel
    fun fromId(id: Int): Model? = models.firstOrNull { it.id == id }
    fun isCurrent(key: String?): Boolean = models.any { it.key == key }

    /**
     * A preset ("모드") only writes a model and a virtual bass level. It is a shortcut, not new processing:
     * EQ, high-pass, output and every other setting stay as they are.
     */
    data class Preset(val key: String, val title: String, val description: String, val modelKey: String, val levelDb: Float)
    const val PRESET_FULLNESS = "fullness"
    const val PRESET_DEEP = "deep"
    const val PRESET_CUSTOM = "custom"

    /**
     * Level of the "풍성함 증가" preset: +4 in the general build (2026-10-22 listening on the S26U, LOGOFF at volume
     * 100/150 with the volume link on: the buzz of +6 drops clearly at +3..+4, and +3 is still much better than off),
     * +6 in the s26u research build.
     */
    val fullnessLevelDb: Float get() = if (PvbBuild.general) 4f else 6f

    val presets: List<Preset> get() = listOf(
        Preset(PRESET_FULLNESS, "풍성함 증가 (권장)",
            "악기의 몸통감과 풍성함, 잔향을 키워 곡을 풍성하게 합니다. 초저역도 조금 좋아질 수 있지만 풍성함에 중점을 둡니다. " +
                "보수적으로 동작해 버즈음이 생길 가능성이 낮습니다.",
            P1_KEY, fullnessLevelDb),
        Preset(PRESET_DEEP, "초저역 강조 (실험)",
            "스피커 한계보다 낮은 저음을 재현하려 합니다. 곡에 따라 차이가 크고 버즈음이 생길 수 있습니다. 공격적으로 동작합니다.",
            GENTLE12_KEY, 9f),
    )
    const val CUSTOM_TITLE = "사용자 지정"
    const val CUSTOM_DESCRIPTION = "모델이나 크기를 직접 바꾼 상태입니다."

    /** The preset whose model and level match exactly, else null (= 사용자 지정). */
    fun presetFor(modelKey: String?, levelDb: Float): Preset? =
        presets.firstOrNull { it.modelKey == fromKey(modelKey).key && it.levelDb == levelDb }
}

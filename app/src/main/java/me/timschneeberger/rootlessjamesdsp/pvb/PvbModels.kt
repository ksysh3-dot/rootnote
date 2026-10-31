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
    const val P1_PLUS = 11
    const val P1PP = 12
    const val P1PP_V03 = 13
    const val P1_C1 = 14
    const val RESULTANT = 15
    const val RESULTANT_V16 = 16
    const val REFERENCE_KEY = "alpha2_reference"
    const val P1_KEY = "alpha2_p1"
    const val GENTLE12_KEY = "alpha3_gentle12"
    /** Alpha 3: P1 is the default (2026-10-19/20 phone listening: less noise than the reference, kept the gains). */
    const val DEFAULT_KEY = P1_KEY

    val models: List<Model> = listOf(
        Model(P1_KEY, P1, "연결형 (P1)", "음이 잠깐 약해질 때도 배음을 이어가며, 강약과 음정 변화를 함께 따라갑니다. 기본 모델입니다."),
        Model("resultant_core_v15", RESULTANT, "Resultant 코어 v1.5 (실험)", "P1의 음 추적은 그대로 두고, 배음층을 음마다 이어지는 새 방식으로 만듭니다. 음이 다시 칠 때 층이 끊기거나 깜빡이던 것이 크게 줄었습니다(연구 측정). 어택이 약 20 ms 늦고, 베이스가 없는 곳에서 낮은 소리가 조금 더 날 수 있습니다. 지연은 P1과 같습니다."),
        Model("resultant_core_v16", RESULTANT_V16, "Resultant 코어 v1.6 (실험)", "v1.5보다 낮은 현악곡에서 들리던 \"쿠쿠쿵\" 같은 기저음의 원인(위상을 빠르게 당기던 동작)을 줄였습니다: 150 Hz 아래 번짐이 약 11 dB 줄었습니다(연구 측정, 14곡). 음 끝의 꼬리도 v1.5보다 짧습니다. 음이 바뀔 때 새 음높이에 붙는 시간이 약 9 ms 늦습니다. 또 폰 스피커가 낼 수 없는 150 Hz 아래의 층 자체 성분을 약 9 dB 더 깎았고(연구 측정), 몸통(150-600 Hz)은 그대로입니다. 지연은 P1과 같습니다."),
        Model("alpha2_p1_c1", P1_C1, "연결형 P1 · 킥 뒤 보정 (실험)", "P1과 같지만, 킥 뒤에 남는 킥의 저음 꼬리 때문에 저음층이 잘못 깎이던 것을 줄였습니다(합성 신호 확인군에서 킥 뒤 잔여 지표 8.2 dB 감소). 저음이 끝날 때 저음층이 조금 더 남을 수 있습니다. 지연은 P1과 같습니다."),
        Model("alpha2_p1plus", P1_PLUS, "연결형 P1+ (실험)", "연결형에 위상 유지와 앞뒤를 함께 보는 분리를 더했습니다. 짧은 음의 강약 윤곽이 원음에 더 가깝습니다(합성 신호 시험). 지연이 약 0.18초로 늘어납니다."),
        Model("alpha2_p1pp", P1PP, "연결형 P1++ (실험)", "P1+에 강한 타격 뒤에 남는 잔여를 줄이는 처리를 더했습니다(합성 신호 시험). 타격 직후 80 ms 잔여는 조금 늘 수 있습니다. 지연은 P1+와 같은 약 0.18초입니다."),
        Model("alpha2_p1pp_v03", P1PP_V03, "연결형 P1++ v0.3 (실험)", "P1++에서 새 음을 붙잡아 두는 규칙을 고쳤습니다. 주파수와 세기가 안정된 음은 붙잡지 않아 짧은 음의 시작이 P1+에 가깝게 돌아왔고, 타격 뒤 잔여 감소는 P1++와 거의 같습니다(합성 신호 시험). 타격 직후 잠깐의 잔여 증가는 그대로이고, 지연은 약 0.18초입니다."),
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

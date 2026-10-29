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
    const val REFERENCE_KEY = "alpha2_reference"
    const val P1_KEY = "alpha2_p1"
    const val GENTLE12_KEY = "alpha3_gentle12"
    /** Alpha 3: P1 is the default (2026-10-19/20 phone listening: less noise than the reference, kept the gains). */
    const val DEFAULT_KEY = P1_KEY

    // Display names (2026-10-29): musical articulation marks for the character of each model, a version number for
    // confirmed changes within it (x.1 a confirmed local fix, x.5 a broad listening-confirmed gain, 2.0 a structural
    // step). Saved keys and engine IDs are unchanged; research codes (P1, D2, ...) stay in the descriptions.
    val models: List<Model> = listOf(
        Model(P1_KEY, P1, "Legato 1.0 · 연결형", "레가토(끊김 없이 이어서). 음이 잠깐 약해질 때도 배음을 이어가며, 강약과 음정 변화를 함께 따라갑니다. 기본 모델입니다(연구 이름 P1)."),
        Model("alpha2_p1_c1", P1_C1, "Legato 1.1 · 킥 뒤 보정 (실험)", "Legato 1.0과 같지만, 킥 뒤에 남는 킥의 저음 꼬리 때문에 저음층이 잘못 깎이던 것을 줄였습니다(합성 신호 확인군에서 킥 뒤 잔여 지표 8.2 dB 감소). 저음이 끝날 때 저음층이 조금 더 남을 수 있습니다. 지연은 Legato 1.0과 같습니다(연구 이름 P1 + C1)."),
        Model("alpha2_p1plus", P1_PLUS, "Preciso 1.0 · 정밀 분리 (실험)", "프레치소(정확하게). Legato에 위상 유지와 앞뒤를 함께 보는 분리를 더했습니다. 짧은 음의 강약 윤곽이 원음에 더 가깝습니다(합성 신호 시험). 지연이 약 0.18초로 늘어납니다(연구 이름 P1+)."),
        Model("alpha2_p1pp", P1PP, "Preciso 1.1 · 타격 잔여 감소 (실험)", "Preciso 1.0에 강한 타격 뒤에 남는 잔여를 줄이는 처리를 더했습니다(합성 신호 시험). 타격 직후 80 ms 잔여는 조금 늘 수 있습니다. 지연은 Preciso 1.0과 같은 약 0.18초입니다(연구 이름 P1++)."),
        Model("alpha2_p1pp_v03", P1PP_V03, "Preciso 1.2 · 짧은 음 회복 (실험)", "Preciso 1.1에서 새 음을 붙잡아 두는 규칙을 고쳤습니다. 주파수와 세기가 안정된 음은 붙잡지 않아 짧은 음의 시작이 Preciso 1.0에 가깝게 돌아왔고, 타격 뒤 잔여 감소는 Preciso 1.1과 거의 같습니다(합성 신호 시험). 타격 직후 잠깐의 잔여 증가는 그대로이고, 지연은 약 0.18초입니다(연구 이름 P1++ v0.3)."),
        Model(REFERENCE_KEY, REFERENCE, "Primo · 기준형", "프리모(원래대로). 상부 배음을 완화한 알파 2 기준 방식입니다 (24 dB/oct). 다른 모델과 비교할 때 기준으로 사용하세요."),
        Model("alpha2_d2", D2, "Staccato · 세부 추적", "스타카토(짧고 또렷하게). 빠른 강약·음정 변화를 짧게 다시 읽습니다. 조건이 맞지 않으면 Legato로 동작합니다(연구 이름 D2)."),
        Model("alpha2_j2", J2, "Tremolo · 변조 추적", "트레몰로(규칙적인 떨림). 규칙적으로 울렁이는 저음을 추적합니다. 조건이 맞지 않으면 Staccato로 동작합니다(연구 이름 J2)."),
        Model("alpha2_osc", OSC, "Sostenuto 1.0 · 연속 합성", "소스테누토(음을 지속해서). 위상을 이어서 배음을 만듭니다. Legato·Staccato와 질감을 비교해 보세요."),
        Model("alpha2_osc_correct", OSC_CORRECT, "Sostenuto 1.1 · 위상 보정", "Sostenuto 1.0에 작은 위상 보정을 더합니다. 보정 없는 Sostenuto 1.0과 비교해 보세요."),
        Model(GENTLE12_KEY, GENTLE12, "Dolce · 부드러운 저음 (12 dB/oct)", "돌체(부드럽게). 위쪽 배음을 덜 줄여(12 dB/oct) 효과가 더 잘 들립니다. 대신 버즈음이 생길 가능성이 큽니다."),
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

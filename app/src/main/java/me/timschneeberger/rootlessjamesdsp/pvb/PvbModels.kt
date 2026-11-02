package me.timschneeberger.rootlessjamesdsp.pvb

/** Stable saved keys and native IDs. List positions are never engine IDs. */
object PvbModels {
    /** [levelTrimDb]: added to the strength slider where the engine level is formed ([VolumeLevelLink.levelFor]); 0 = none. */
    data class Model(val key: String, val id: Int, val title: String, val description: String, val levelTrimDb: Float = 0f)
    const val P1 = 6
    const val P1_KEY = "alpha2_p1"
    const val DEFAULT_KEY = P1_KEY
    // P1+++ is a separate opt-in preset (param 57), never a new native/model ID.
    val models: List<Model> = listOf(
        Model(P1_KEY, P1, "연결형 (P1)", "음이 잠깐 약해질 때도 배음을 이어가며, 강약과 음정 변화를 함께 따라갑니다. 기본 모델입니다."),
    )

    val defaultModel: Model get() = models.first { it.key == DEFAULT_KEY }

    fun fromKey(key: String?): Model = models.firstOrNull { it.key == key } ?: defaultModel
    fun fromId(id: Int): Model? = models.firstOrNull { it.id == id }
    fun isCurrent(key: String?): Boolean = models.any { it.key == key }
    /**
     * An engine algorithm id the status text may call "in use": the legacy ids 0..10 and every catalogue model (the
     * engine reports the algorithm in the signal path as id + 1; no algorithm gives -1 and a bypassed one 0 - 1).
     */
    fun inUse(algo: Int): Boolean = algo == P1
    /** The level trim of an engine id (0 for an unknown id or a model without one). */
    fun trimDb(id: Int): Float = fromId(id)?.levelTrimDb ?: 0f

    /**
     * A preset ("모드") only writes a model and a virtual bass level. It is a shortcut, not new processing:
     * EQ, high-pass, output and every other setting stay as they are.
     */
    data class Preset(val key: String, val title: String, val description: String, val modelKey: String, val levelDb: Float)
    const val PRESET_FULLNESS = "fullness"
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

    )
    const val CUSTOM_TITLE = "사용자 지정"
    const val CUSTOM_DESCRIPTION = "모델이나 크기를 직접 바꾼 상태입니다."

    /** The preset whose model and level match exactly, else null (= 사용자 지정). */
    fun presetFor(modelKey: String?, levelDb: Float): Preset? =
        presets.firstOrNull { it.modelKey == fromKey(modelKey).key && it.levelDb == levelDb }
}

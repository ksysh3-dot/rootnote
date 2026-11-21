package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Conditions for the in-app blind comparison. Every condition starts from EQ v1.1 with the experimental extras
 * (volume link, quiet-passage bass) off, so only the named difference changes.
 *
 * Both sides share output headroom. Each condition applies its own fixed loudness trim.
 */
object PvbAbConditions {
    const val HEADROOM_DB = 10f
    private const val TRIM_NOHI = -1.60f
    /** One condition with its loudness trim (dB, before the phone, on top of the common headroom). */
    class Cond(val id: String, val label: String, val trimDb: Float, private val f: (PvbSettings) -> PvbSettings) {
        val condition = PvbRuntime.AbCondition(id, label, trimDb, HEADROOM_DB, f)
    }

    /**
     * [stage]: the output-headroom comparison. Its two conditions are built when a run starts, from the in-app
     * measurement (volume steps and the phone's compressor): EQ v1.1 at the usual output and volume, against EQ v1.1
     * X dB quieter with the volume k steps up. It runs without the common headroom and the app sets the volume.
     */
    class Pair(val id: String, val label: String, val first: Cond, val second: Cond, val stage: Boolean = false, val unavailableReason: String? = null)

    fun v11(s: PvbSettings) = s.copy(
        enabled = true, hpHz = 100f, lowHz = 220f, lowDb = 3f, lowQ = 1f, hiHz = 4500f, hiDb = -3f, hiQ = 0.6f,
        outDb = -5f, ceilDb = -1f, releaseMs = 60f, volLink = false, dynOn = false, hsHz = 2500f, hsDb = 0f,
        combo = false, p1ppp = false, devOn = false, vbOn = false, vbVolLink = false,   // alpha 3.2: fixed layer levels, as measured for the trims
        xtcMode = PvbSettings.XTC_OFF,   // spatial: only the spatial comparisons turn it on (LiveAbComparisons)
    )

    /** EQ v1.1 with a virtual bass algorithm at [levelDb] ([PvbSettings.VB_LEVEL_OFF] = layer silent). */
    fun v11vb(s: PvbSettings, algo: Int, levelDb: Float) = v11(s).copy(combo = true, vbOn = true, vbAlgo = algo, vbLevelDb = levelDb)

    val REF = Cond("v11", "EQ v1.1", 0f) { v11(it) }
    val ORIG = Cond("orig", "EQ 없음", -1.41f) { v11(it).copy(hpHz = 20f, lowDb = 0f, hiDb = 0f) }
    val SHELF3 = Cond("shelf3", "고음 기울기 −3", 1.23f) { v11(it).copy(hsDb = -3f) }
    val SHELF6 = Cond("shelf6", "고음 기울기 −6", 2.30f) { v11(it).copy(hsDb = -6f) }
    val HP160 = Cond("hp160", "저역 차단 160 Hz", 0.07f) { v11(it).copy(hpHz = 160f) }
    val NOHI = Cond("nohi", "4.5 kHz 감쇠 없음", TRIM_NOHI) { v11(it).copy(hiDb = 0f) }
    val HP160S3 = Cond("hp160s3", "저역 160 + 기울기 −3", 1.31f) { v11(it).copy(hpHz = 160f, hsDb = -3f) }

    val PAIRS = listOf(
        Pair("v11_vs_orig", "EQ v1.1 vs EQ 없음", REF, ORIG),
        Pair("v11_vs_nohi", "EQ v1.1 vs 4.5 kHz 감쇠 없음", REF, NOHI),
        Pair("v11_vs_stage", "출력 여유: EQ v1.1 기준 출력 vs 출력 낮추고 볼륨 올림 (측정 필요)", REF, REF, stage = true),
        Pair("v11_vs_shelf3", "EQ v1.1 vs 고음 기울기 −3", REF, SHELF3),
        Pair("v11_vs_shelf6", "EQ v1.1 vs 고음 기울기 −6", REF, SHELF6),
        Pair("v11_vs_hp160", "EQ v1.1 vs 저역 차단 160 Hz", REF, HP160),
        Pair("v11_vs_hp160s3", "EQ v1.1 vs 저역 160 + 기울기 −3", REF, HP160S3),
    )
}

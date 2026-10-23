package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Conditions for the in-app blind comparison. Every condition starts from EQ v1.1 with the experimental extras
 * (volume link, quiet-passage bass) off, so only the named difference changes.
 *
 * Both sides are sent [HEADROOM_DB] quieter than usual, so the phone's own processor (before the volume control)
 * hardly compresses them; the listener turns the volume up instead. Only there does a fixed trim not depend on the
 * details of the phone model: at the usual level the phone squashes part of every trim and the two cross-band
 * variants of the model disagree by 0.9-1.9 dB on the treble shelves, with headroom by under 0.1 dB. The trims
 * below make each condition as loud as EQ v1.1 after the phone (phone model 'octx', mean of 23 songs; spread
 * about 0.6 dB, from the songs' different treble content). See tools/pvb-harness/study/RESULTS_phone_model.md.
 */
object PvbAbConditions {
    const val HEADROOM_DB = 10f
    private const val TRIM_NOHI = -1.60f   // album study, octx (oct: -1.64), spread 0.54 dB
    // virtual bass, album study (tools/pvb-harness/vb_port/trims.py), octx headroom mode; spread in README_PVB.md
    private const val TRIM_HPV_M3 = -0.01f   // spread 0.01 dB (oct: -0.01)
    private const val TRIM_HPV_0 = -0.02f   // spread 0.01 dB (oct: -0.02)
    private const val TRIM_HPV_P3 = -0.04f   // spread 0.02 dB (oct: -0.04)
    private const val TRIM_HPV_P6 = -0.07f   // spread 0.05 dB (oct: -0.07)
    private const val TRIM_HPV_P9 = -0.13f   // spread 0.08 dB (oct: -0.12)
    private const val TRIM_BANK_0 = -0.13f   // spread 0.28 dB (oct: -0.10)

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
        vbOn = false, vbVolLink = false,   // alpha 3.2: fixed layer levels, as measured for the trims
        xSmooth = false, xRise = false, xS1m = false, xDense = false,   // experimental options: not in comparisons
        xtcMode = PvbSettings.XTC_OFF,   // spatial: only the spatial comparisons turn it on (LiveAbComparisons)
    )

    /** EQ v1.1 with a virtual bass algorithm at [levelDb] ([PvbSettings.VB_LEVEL_OFF] = layer silent). */
    fun v11vb(s: PvbSettings, algo: Int, levelDb: Float) = v11(s).copy(vbOn = true, vbAlgo = algo, vbLevelDb = levelDb)

    val REF = Cond("v11", "EQ v1.1", 0f) { v11(it) }
    val ORIG = Cond("orig", "EQ 없음", -1.41f) { v11(it).copy(hpHz = 20f, lowDb = 0f, hiDb = 0f) }
    val SHELF3 = Cond("shelf3", "고음 기울기 −3", 1.23f) { v11(it).copy(hsDb = -3f) }
    val SHELF6 = Cond("shelf6", "고음 기울기 −6", 2.30f) { v11(it).copy(hsDb = -6f) }
    val HP160 = Cond("hp160", "저역 차단 160 Hz", 0.07f) { v11(it).copy(hpHz = 160f) }
    val NOHI = Cond("nohi", "4.5 kHz 감쇠 없음", TRIM_NOHI) { v11(it).copy(hiDb = 0f) }
    val HP160S3 = Cond("hp160s3", "저역 160 + 기울기 −3", 1.31f) { v11(it).copy(hpHz = 160f, hsDb = -3f) }

    // Virtual bass (experimental). The EQ v1.1 side runs the same algorithm with its layer silent: both sides have
    // the same latency (hpv: 147 ms), so switching neither jumps in time nor reveals the side, and the algorithm stays
    // warm. Trims: same method as above (album, phone model 'octx', headroom mode); see README_PVB.md.
    val REF_HPV = Cond("v11_hpv0", "EQ v1.1", 0f) { v11vb(it, PvbSettings.VB_HPV, PvbSettings.VB_LEVEL_OFF) }
    val HPV_M3 = Cond("hpv_m3", "+ 가상 저음 −3 dB", TRIM_HPV_M3) { v11vb(it, PvbSettings.VB_HPV, -3f) }
    val HPV_0 = Cond("hpv_0", "+ 가상 저음 0 dB", TRIM_HPV_0) { v11vb(it, PvbSettings.VB_HPV, 0f) }
    val HPV_P3 = Cond("hpv_p3", "+ 가상 저음 +3 dB", TRIM_HPV_P3) { v11vb(it, PvbSettings.VB_HPV, 3f) }
    val HPV_P6 = Cond("hpv_p6", "+ 가상 저음 +6 dB", TRIM_HPV_P6) { v11vb(it, PvbSettings.VB_HPV, 6f) }
    val HPV_P9 = Cond("hpv_p9", "+ 가상 저음 +9 dB", TRIM_HPV_P9) { v11vb(it, PvbSettings.VB_HPV, 9f) }
    val REF_BANK = Cond("v11_bank0", "EQ v1.1", 0f) { v11vb(it, PvbSettings.VB_BANKSTOWN, PvbSettings.VB_LEVEL_OFF) }
    val BANK_0 = Cond("bank_0", "+ Bankstown 0 dB", TRIM_BANK_0) { v11vb(it, PvbSettings.VB_BANKSTOWN, 0f) }

    // No unmeasured trims: these pairs become runnable only after vb_port/trims.py is run on the album.
    private const val WAIT_52 = "hpv52m의 앨범 음량 보정값을 아직 계산하지 못했습니다. 원음 확보 후 비교를 열 예정입니다. 일반 설정에서는 hpv52m을 시험할 수 있습니다."
    val REF_52 = Cond("v11_hpv52m0", "EQ v1.1", 0f) { v11vb(it, PvbSettings.VB_HPV52M, PvbSettings.VB_LEVEL_OFF) }
    val HPV52_P3 = Cond("hpv52m_p3", "+ hpv52m +3 dB", 0f) { v11vb(it, PvbSettings.VB_HPV52M, 3f) }
    val HPV52_P6 = Cond("hpv52m_p6", "+ hpv52m +6 dB", 0f) { v11vb(it, PvbSettings.VB_HPV52M, 6f) }

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

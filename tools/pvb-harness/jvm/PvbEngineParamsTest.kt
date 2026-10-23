import me.timschneeberger.rootlessjamesdsp.pvb.PvbEngineParams
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.VolumeLevelLink

// PvbEngineParams.encode: the rules PvbController.push used to apply inline, one case per rule. The extraction itself
// was checked against the previous push body (200 000 random states, all 56 slots bit-identical) and is not repeated.

private const val ROT_0 = 0
private const val ROT_90 = 1
private const val ROT_270 = 3

private fun inputs(
    speaker: Boolean = true, upright: Boolean = false, rotation: Int = ROT_90, volumeIndex: Int = 7,
    diagnosticSolo: Boolean = false, abActive: Boolean = false, abHidden: Boolean = false, abTag: Int = 0,
    gateDb: Float = 0f, measuring: Boolean = false, devMeter: Boolean = false,
) = PvbEngineParams.Inputs(
    rampMs = 20f, speaker = speaker, upright = upright, rotation = rotation, volumeIndex = volumeIndex, volumeMax = 15,
    lowDb = 3f, matchSeedDb = -6f, diagnosticSolo = diagnosticSolo, abActive = abActive, abHidden = abHidden,
    abTag = abTag, gateDb = gateDb, measuring = measuring, devMeter = devMeter,
)

private fun encode(s: PvbSettings, i: PvbEngineParams.Inputs = inputs()) = PvbEngineParams.encode(s, i)
private fun FloatArray.on(slot: Int) = this[slot] == 1f

fun main() {
    val base = PvbSettings(enabled = true, matchOnDisable = true, speakerOnly = true, vbOn = true)

    // on, on the speaker: processing, the flat path kept ready, virtual bass in
    encode(base).params.let {
        check(it.on(PvbParam.ENABLED) && it.on(PvbParam.FLAT) && it.on(PvbParam.VB_ON)) { "on: processing" }
        check(it[PvbParam.MATCH_HOLD] == 0f) { "on: matcher runs" }
    }
    // off with matched bypass: silent effect, flat path heard, virtual bass kept for the same latency
    encode(base.copy(enabled = false)).params.let {
        check(!it.on(PvbParam.ENABLED) && it.on(PvbParam.FLAT) && it.on(PvbParam.VB_ON)) { "matched bypass" }
    }
    // off without matched bypass: nothing kept
    encode(base.copy(enabled = false, matchOnDisable = false)).params.let {
        check(!it.on(PvbParam.ENABLED) && !it.on(PvbParam.FLAT) && !it.on(PvbParam.VB_ON)) { "plain off" }
    }
    // "speaker only" with headphones: route not allowed, so no effect, no flat path, matcher held, no spatial
    encode(base.copy(xtcMode = PvbSettings.XTC_FULL), inputs(speaker = false)).params.let {
        check(!it.on(PvbParam.ENABLED) && !it.on(PvbParam.FLAT) && !it.on(PvbParam.VB_ON)) { "route bypass" }
        check(it.on(PvbParam.MATCH_HOLD) && it[PvbParam.XTC_MODE] == 0f) { "route bypass: hold, no spatial" }
    }
    // not "speaker only": headphones are processed, but spatial stays the speakers' own
    encode(base.copy(speakerOnly = false, xtcMode = PvbSettings.XTC_FULL), inputs(speaker = false)).params.let {
        check(it.on(PvbParam.ENABLED) && it[PvbParam.XTC_MODE] == 0f) { "headphones processed, no spatial" }
    }

    // blind comparison: tag and gate carried, matcher held, no developer values, no solo monitor; spatial as the
    // condition sets it (EQ v1.1 turns it off, the spatial comparisons turn it on)
    val dev = base.copy(devOn = true, xtcMode = PvbSettings.XTC_FULL)
    encode(dev, inputs(abActive = true, abTag = 42, gateDb = -10f, diagnosticSolo = true)).let {
        val p = it.params
        check(p[PvbParam.TAG] == 42f && p[PvbParam.GATE_DB] == -10f) { "comparison: tag and gate" }
        check(p.on(PvbParam.MATCH_HOLD) && !p.on(PvbParam.DEV_ON)) { "comparison holds" }
        check(p[PvbParam.XTC_MODE] == PvbSettings.XTC_FULL.toFloat()) { "comparison: spatial follows the condition" }
        check(!it.diagnosticSolo && !p.on(PvbParam.DIAGNOSTIC_SOLO)) { "comparison drops the solo monitor" }
    }
    check(encode(base, inputs(abTag = 42)).params[PvbParam.TAG] == 0f) { "tag only during a comparison" }
    check(encode(base.copy(xtcMode = PvbSettings.XTC_MS_FULL), inputs(abActive = true)).params[PvbParam.XTC_MODE] == 7f) {
        "comparison: M/S widener mode passed through"
    }
    check(encode(base.copy(xtcMode = PvbSettings.XTC_OFF), inputs(abActive = true)).params[PvbParam.XTC_MODE] == 0f) {
        "comparison with spatial off"
    }
    // the comparison's hidden-bypass phase: no flat path
    check(!encode(base.copy(enabled = false), inputs(abHidden = true)).params.on(PvbParam.FLAT)) { "hidden bypass" }
    // a comparison's mute reaches the gate as is
    check(encode(base, inputs(abActive = true, gateDb = -100f)).params[PvbParam.GATE_DB] == -100f) { "mute" }

    // measurement: matcher held, no spatial, no solo monitor
    encode(base.copy(xtcMode = PvbSettings.XTC_FULL), inputs(measuring = true, diagnosticSolo = true)).let {
        check(it.params.on(PvbParam.MATCH_HOLD) && it.params[PvbParam.XTC_MODE] == 0f) { "measuring" }
        check(!it.diagnosticSolo) { "measuring drops the solo monitor" }
    }
    // solo monitor: kept when allowed, dropped without virtual bass or with the effect off
    check(encode(base, inputs(diagnosticSolo = true)).diagnosticSolo) { "solo kept" }
    check(!encode(base.copy(vbOn = false), inputs(diagnosticSolo = true)).diagnosticSolo) { "solo needs virtual bass" }
    check(!encode(base.copy(enabled = false), inputs(diagnosticSolo = true)).diagnosticSolo) { "solo needs the effect" }

    // volume link: the array carries the level played at this volume, not the one the user set
    val linked = base.copy(vbVolLink = true, vbLevelDb = 0f)
    val loud = encode(linked, inputs(volumeIndex = 15)).params[PvbParam.VB_LEVEL_DB]
    check(loud == VolumeLevelLink.levelFor(linked, 15, 15) && loud < 0f) { "linked level at full volume: $loud" }
    check(encode(base.copy(vbLevelDb = -3f), inputs(volumeIndex = 15)).params[PvbParam.VB_LEVEL_DB] == -3f) {
        "unlinked level as set"
    }

    // spatial and balance: sideways keeps the mode; balance swaps sides when turned the other way round
    val bal = base.copy(xtcMode = PvbSettings.XTC_FULL, xtcBalLoDb = 2f, xtcBalHiDb = -1f, xtcBalRotation = ROT_90)
    encode(bal, inputs(rotation = ROT_90)).params.let {
        check(it[PvbParam.XTC_MODE] == PvbSettings.XTC_FULL.toFloat()) { "sideways: mode as set" }
        check(it[PvbParam.XTC_BAL_LO_DB] == 2f && it[PvbParam.XTC_BAL_HI_DB] == -1f) { "balance as set" }
    }
    encode(bal, inputs(rotation = ROT_270)).params.let {
        check(it[PvbParam.XTC_BAL_LO_DB] == -2f && it[PvbParam.XTC_BAL_HI_DB] == 1f) { "turned round: sides swap" }
    }
    // screen in portrait while the phone lies sideways (rotation lock): balance as set
    check(encode(bal, inputs(rotation = ROT_0)).params[PvbParam.XTC_BAL_LO_DB] == 2f) { "unknown rotation keeps" }
    // balance set before the rotation was recorded: never swapped
    check(encode(bal.copy(xtcBalRotation = 0), inputs(rotation = ROT_270)).params[PvbParam.XTC_BAL_LO_DB] == 2f) {
        "no recorded rotation"
    }
    // held upright: portrait choice (off / mono / split, low channel side), no balance
    for ((portrait, lowRight, mode) in listOf(
        Triple(PvbSettings.XTC_PORTRAIT_OFF, true, 0f), Triple(PvbSettings.XTC_PORTRAIT_MONO, true, 3f),
        Triple(PvbSettings.XTC_PORTRAIT_SPLIT, false, 4f), Triple(PvbSettings.XTC_PORTRAIT_SPLIT, true, 5f),
    )) {
        val p = encode(bal.copy(xtcPortrait = portrait, xtcPortraitLowRight = lowRight), inputs(upright = true)).params
        check(p[PvbParam.XTC_MODE] == mode) { "upright portrait=$portrait lowRight=$lowRight: ${p[PvbParam.XTC_MODE]}" }
        check(p[PvbParam.XTC_BAL_LO_DB] == 0f && p[PvbParam.XTC_BAL_HI_DB] == 0f) { "upright: no balance" }
    }

    // developer options: on outside a comparison; experimental layer options only with virtual bass
    encode(dev.copy(devH2Db = -4f, xSmooth = true), inputs(devMeter = true)).params.let {
        check(it.on(PvbParam.DEV_ON) && it[PvbParam.D_H2_DB] == -4f && it.on(PvbParam.DEV_METER)) { "developer on" }
        check(it.on(PvbParam.X_SMOOTH)) { "layer option with virtual bass" }
    }
    check(!encode(base.copy(vbOn = false, xSmooth = true)).params.on(PvbParam.X_SMOOTH)) { "layer option needs vb" }
    check(!encode(base).params.on(PvbParam.DEV_ON)) { "developer off" }

    println("PvbEngineParamsTest: all checks passed")
}

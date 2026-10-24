package me.timschneeberger.rootlessjamesdsp.pvb

import java.util.Locale

/*
 * "저음 맞추기" validation mode (docs/BASS_FIT_PLAN.md, UMIK-1 validation): one step repeated under "virtual
 * speakers" of known floor (the engine's high-pass), hidden from the listener and in a random order, and a CSV log of
 * every run for the criterion (UMIK-1) and test-retest comparisons. Pure Kotlin, host tested (BassFitSessionTest).
 */

object FitConditions {
    /** Virtual speakers: null = the speaker as it is; else the engine's high-pass (2nd order) at that frequency. */
    val ALL: List<Double?> = listOf(null, 120.0, 150.0, 180.0, 220.0)

    /** Short name in the log: "real" or the high-pass in Hz. */
    fun id(hp: Double?): String = hp?.let { String.format(Locale.ROOT, "hp%.0f", it) } ?: "real"
}

/** The runs of one validation block: every condition [repeats] times, shuffled by [seed] (a new seed every block). */
class ValidationPlan(seed: Long, conditions: List<Double?>, val repeats: Int) {
    val runs: List<Double?>

    init {
        require(conditions.isNotEmpty() && repeats >= 1)
        val list = ArrayList<Double?>()
        repeat(repeats) { list.addAll(conditions) }
        // Fisher-Yates with the seeded generator; no condition twice in a row where avoidable
        val rng = FitRng(seed)
        for (i in list.size - 1 downTo 1) {
            val j = rng.below(i + 1)
            val t = list[i]; list[i] = list[j]; list[j] = t
        }
        for (i in 1 until list.size) {
            if (list[i] == list[i - 1]) {
                val k = (i + 1 until list.size).firstOrNull { list[it] != list[i] && (it + 1 >= list.size || list[it + 1] != list[i - 1]) }
                if (k != null) { val t = list[i]; list[i] = list[k]; list[k] = t }
            }
        }
        runs = list
    }
}

/** One line per run (ear floor, ear break-up, or the microphone's probe), CSV with a fixed header. */
object ValidationLog {
    const val HEADER = "time,model,app,kind,condition,seed,volume,volume_max,value,reliable,questions,catch,false_alarms," +
        "mic_floor_hz,mic_clipped,latency_ms,room_pass,room_margin_db,rattles,buzzes,catch_rattles,catch_buzzes,first_kind,ref_db,noise_corr_100_db"

    enum class Kind(val id: String) { EAR_FLOOR("ear_floor_hz"), EAR_BREAKUP("ear_breakup_db"), MIC_PROBE("mic_floor_hz") }

    data class Row(
        val time: String, val model: String, val app: String, val kind: Kind, val conditionHp: Double?, val seed: Long,
        val volume: Int, val volumeMax: Int, val value: Double?, val reliable: Boolean?, val questions: Int?, val catchTrials: Int?,
        val falseAlarms: Int?, val micFloorHz: Double?, val micClipped: Boolean?, val latencyMs: Double?, val roomPass: Boolean?,
        val roomMarginDb: Double?,
        /** Break-up rows: answers by kind (level trials, then layer-off ones) and the kind heard first. */
        val rattles: Int? = null, val buzzes: Int? = null, val catchRattles: Int? = null, val catchBuzzes: Int? = null,
        val firstKind: BreakupStaircase.Answer? = null,
        /** Floor rows: the listener's threshold at 300 Hz, dB re the full test tone (the bursts play 10 dB over it). */
        val refDb: Double? = null,
        /** Floor rows with "소음 보정" on: the correction of the 100 Hz burst, dB. */
        val noiseCorrDb: Double? = null,
    )

    private fun clean(s: String) = s.replace(Regex("[,\\n\\r\"]"), "_")
    private fun num(v: Double?, d: Int = 1) = v?.takeIf { it.isFinite() }?.let { String.format(Locale.ROOT, "%.${d}f", it) } ?: ""
    private fun b(v: Boolean?) = v?.let { if (it) "1" else "0" } ?: ""

    fun line(r: Row): String = listOf(
        clean(r.time), clean(r.model), clean(r.app), r.kind.id, FitConditions.id(r.conditionHp),
        String.format(Locale.ROOT, "%016X", r.seed), r.volume.toString(), r.volumeMax.toString(), num(r.value),
        b(r.reliable), r.questions?.toString() ?: "", r.catchTrials?.toString() ?: "", r.falseAlarms?.toString() ?: "",
        num(r.micFloorHz), b(r.micClipped), num(r.latencyMs, 0), b(r.roomPass), num(r.roomMarginDb),
        r.rattles?.toString() ?: "", r.buzzes?.toString() ?: "", r.catchRattles?.toString() ?: "",
        r.catchBuzzes?.toString() ?: "", r.firstKind?.name?.lowercase(Locale.ROOT) ?: "", num(r.refDb), num(r.noiseCorrDb),
    ).joinToString(",")
}

package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.pow

/**
 * Developer-mode warnings (docs/DEVMODE_COPY.md, "경고 문구") and the numbers behind the graphs. Pure Kotlin.
 *
 * - [evaluate] turns one meter snapshot into the set of warning conditions active now.
 * - [DevWarningTracker] decides when a dialog opens: a condition must hold for [DevWarningTracker.CONFIRM_MS], one
 *   dialog per episode (the condition must clear for [DevWarningTracker.CLEAR_MS] before it can count again), at most
 *   one per type every [DevWarningTracker.COOLDOWN_MS]. Every dialog shown is one occurrence (persisted); from the 3rd
 *   occurrence of the same type the dialog offers "이 경고 다시 표시하지 않기". The loud-output warning can never be
 *   hidden; the unmeasured-phone notice is shown once only. The inline note on the graph always shows, hidden or not.
 */
enum class DevWarning(val hideable: Boolean) {
    /** Output at the safety ceiling (limiter working hard). Cannot be hidden. */
    NEAR_CEILING(false),
    /** Harmonics around 220-400 Hz and the band over the protection threshold ("쿠훙"). */
    BUZZ_ZONE(true),
    /** The layer outlasts the dry note ("쿠웅" tail). */
    TAIL(true),
    /** Volume link off at a high volume. */
    VOLUME_NO_LINK(true),
    /** Phone without a measured profile (shown once, on the first entry). */
    UNMEASURED(false),
}

/** One meter reading of the developer-mode screen (engine dev meters + engine meters + controller status). */
/** One held bass track of the developer display: fundamental and k = 2..8 at the output, dBFS. */
class DevTrack(val f0Hz: Float, val harmonicDb: FloatArray)

class DevSnapshot(
    val f0Hz: Float,
    /** k = 2..8 at the output, dBFS (-120 = none). */
    val harmonicDb: FloatArray,
    val dryBandDb: Float,
    val layerBandDb: Float,
    /** Oldest first, one value per [binMs]. */
    val ringDry: FloatArray,
    val ringLayer: FloatArray,
    val binMs: Float,
    val outPeakDb: Float,
    val limiterGrDb: Float,
    val ceilingDb: Float,
    val volumePct: Float,
    val volumeLink: Boolean,
    val volumeLinkReductionDb: Float,
    val thresholdDb: Float,
    /** Quieter tracks held at the same time (bass notes together), each a fundamental and k = 2..8 dBFS. */
    val extraTracks: List<DevTrack> = emptyList(),
) {
    /** Sum of the dry band and the layer band (power), dBFS. */
    val totalBandDb: Float get() = DevMath.sumDb(dryBandDb, layerBandDb)
    val headroomDb: Float get() = thresholdDb - totalBandDb

    companion object {
        /** From the engine's dev meter array ([PvbDevMeter] layout). */
        fun fromMeters(
            m: FloatArray, outPeakDb: Float, limiterGrDb: Float, ceilingDb: Float, volumePct: Float,
            volumeLink: Boolean, volumeLinkReductionDb: Float, thresholdDb: Float,
        ): DevSnapshot {
            val ring = PvbDevMeter.RING
            return DevSnapshot(
                f0Hz = m[PvbDevMeter.F0],
                harmonicDb = FloatArray(7) { m[PvbDevMeter.H2_DB + it] },
                dryBandDb = m[PvbDevMeter.DRY_BAND_DB],
                layerBandDb = m[PvbDevMeter.LAYER_BAND_DB],
                ringDry = FloatArray(ring) { m[PvbDevMeter.FIELDS + 2 * it] },
                ringLayer = FloatArray(ring) { m[PvbDevMeter.FIELDS + 2 * it + 1] },
                binMs = m[PvbDevMeter.RING_BIN_MS].takeIf { it > 0f } ?: 5f,
                outPeakDb = outPeakDb, limiterGrDb = limiterGrDb, ceilingDb = ceilingDb, volumePct = volumePct,
                volumeLink = volumeLink, volumeLinkReductionDb = volumeLinkReductionDb, thresholdDb = thresholdDb,
                extraTracks = listOf(PvbDevMeter.T2_F0 to PvbDevMeter.T2_H2_DB, PvbDevMeter.T3_F0 to PvbDevMeter.T3_H2_DB)
                    .filter { (f, _) -> m[f] > 0f }
                    .map { (f, h) -> DevTrack(m[f], FloatArray(7) { m[h + it] }) },
            )
        }
    }
}

object DevMath {
    fun sumDb(a: Float, b: Float): Float = (10 * log10(10.0.pow(a / 10.0) + 10.0.pow(b / 10.0))).toFloat()

    /** Share of the threshold's power used by [db] (0.5 = half), never negative. */
    fun shareOfThreshold(db: Float, thresholdDb: Float): Float = 10.0.pow((db - thresholdDb) / 10.0).toFloat().coerceAtLeast(0f)

    const val BUZZ_LO_HZ = 220f
    const val BUZZ_HI_HZ = 400f
    /** Harmonics more than this below the loudest are not counted ("배음 n개"). */
    const val COUNT_RANGE_DB = 30f
    /** A harmonic counts as present above this level. */
    const val PRESENT_DB = -80f

    data class Bar(val k: Int, val hz: Float, val db: Float)

    /** Harmonic bars k = 2..8 that are present (above [PRESENT_DB] and within [COUNT_RANGE_DB] of the loudest). */
    fun bars(s: DevSnapshot): List<Bar> {
        if (s.f0Hz <= 0f) return emptyList()
        val loud = s.harmonicDb.maxOrNull() ?: return emptyList()
        return (0 until 7).mapNotNull { i ->
            val db = s.harmonicDb[i]
            if (db > PRESENT_DB && db >= loud - COUNT_RANGE_DB) Bar(i + 2, s.f0Hz * (i + 2), db) else null
        }
    }

    /**
     * Bars of every held track (loudest first): the loudest track's bars as [bars]; a quieter track's harmonics count
     * against the same loudest level, so a faint second note shows few bars or none.
     */
    fun trackBars(s: DevSnapshot): List<Pair<Float, List<Bar>>> {
        if (s.f0Hz <= 0f) return emptyList()
        val loud = s.harmonicDb.maxOrNull() ?: return emptyList()
        val out = ArrayList<Pair<Float, List<Bar>>>()
        bars(s).takeIf { it.isNotEmpty() }?.let { out += s.f0Hz to it }
        for (t in s.extraTracks) {
            if (t.f0Hz <= 0f) continue
            val b = (0 until 7).mapNotNull { i ->
                val db = t.harmonicDb[i]
                if (db > PRESENT_DB && db >= loud - COUNT_RANGE_DB) Bar(i + 2, t.f0Hz * (i + 2), db) else null
            }
            if (b.isNotEmpty()) out += t.f0Hz to b
        }
        return out
    }

    /** "기음 55 Hz, 배음 4개, 가장 큰 배음 165 Hz, 여유 3 dB": the numbers of the harmonic summary. */
    data class HarmonicSummary(val f0Hz: Int, val count: Int, val loudestHz: Int, val headroomDb: Float)

    fun harmonicSummary(s: DevSnapshot): HarmonicSummary? {
        val b = bars(s)
        if (b.isEmpty()) return null
        val loud = b.maxByOrNull { it.db }!!
        return HarmonicSummary(Math.round(s.f0Hz), b.size, Math.round(loud.hz), s.headroomDb)
    }

    enum class GaugeStatus { ROOM, TIGHT, DANGER }

    /** "여유 있음" at 6 dB or more below the threshold, "빠듯함" 0..6 dB, "지직 위험" above it. */
    fun gaugeStatus(headroomDb: Float): GaugeStatus = when {
        headroomDb >= 6f -> GaugeStatus.ROOM
        headroomDb >= 0f -> GaugeStatus.TIGHT
        else -> GaugeStatus.DANGER
    }

    /** Gauge scale: level relative to the threshold from [GAUGE_MIN_DB] (left) to [GAUGE_MAX_DB] (right). */
    const val GAUGE_MIN_DB = -24f
    const val GAUGE_MAX_DB = 6f
    fun gaugeFraction(relDb: Float): Float = ((relDb - GAUGE_MIN_DB) / (GAUGE_MAX_DB - GAUGE_MIN_DB)).coerceIn(0f, 1f)
    val thresholdFraction: Float get() = gaugeFraction(0f)

    /**
     * Gauge gradient (docs/DESIGN.md 2.3): green 0, yellow 0.45, orange 0.72, red 1, as 0xRRGGBB. The filled part of
     * the track uses the same gradient over the whole track (not stretched to the level), so the colour at the level
     * ([gaugeColorAt]) is the colour of the track there; the level dot's ring uses it.
     */
    val GAUGE_STOP_POS = floatArrayOf(0f, 0.45f, 0.72f, 1f)
    val GAUGE_STOP_RGB = intArrayOf(0x2E9E5B, 0xE8C547, 0xE8892F, 0xD64545)

    fun gaugeColorAt(f: Float): Int {
        val x = if (f.isFinite()) f.coerceIn(0f, 1f) else 0f
        var i = 0
        while (i < GAUGE_STOP_POS.size - 2 && x > GAUGE_STOP_POS[i + 1]) i++
        val t = (x - GAUGE_STOP_POS[i]) / (GAUGE_STOP_POS[i + 1] - GAUGE_STOP_POS[i])
        fun ch(c: Int, s: Int) = (c shr s) and 0xFF
        fun mix(s: Int) = Math.round(ch(GAUGE_STOP_RGB[i], s) + (ch(GAUGE_STOP_RGB[i + 1], s) - ch(GAUGE_STOP_RGB[i], s)) * t)
        return (mix(16) shl 16) or (mix(8) shl 8) or mix(0)
    }

    /** Share of the threshold's power, in whole percent for the gauge caption (0..999). */
    fun sharePct(db: Float, thresholdDb: Float): Int =
        if (!db.isFinite() || db <= -100f) 0 else Math.round(100f * shareOfThreshold(db, thresholdDb)).coerceIn(0, 999)

    /** Harmonic-bar graph: logarithmic frequency axis [GRAPH_LO_HZ]..[GRAPH_HI_HZ] -> 0..1. */
    const val GRAPH_LO_HZ = 35f
    const val GRAPH_HI_HZ = 700f
    fun graphX(hz: Float): Float =
        (ln(hz.coerceIn(GRAPH_LO_HZ, GRAPH_HI_HZ) / GRAPH_LO_HZ) / ln(GRAPH_HI_HZ / GRAPH_LO_HZ))

    /** Bar height 0..1 from dBFS ([BAR_LO_DB]..[BAR_HI_DB]). */
    const val BAR_LO_DB = -66f
    const val BAR_HI_DB = -6f
    fun barHeight(db: Float): Float = if (!db.isFinite()) 0f else ((db - BAR_LO_DB) / (BAR_HI_DB - BAR_LO_DB)).coerceIn(0f, 1f)

    /** VU-style meter (option): -12..+2 dB re the threshold, positions on an amplitude scale like a VU meter. */
    const val VU_MIN_DB = -12f
    const val VU_MAX_DB = 2f
    fun vuFraction(relDb: Float): Float {
        val lo = 10.0.pow(VU_MIN_DB / 20.0)
        val hi = 10.0.pow(VU_MAX_DB / 20.0)
        val v = 10.0.pow(relDb.coerceIn(VU_MIN_DB - 6f, VU_MAX_DB + 1f) / 20.0)
        return ((v - lo) / (hi - lo)).toFloat().coerceIn(-0.05f, 1.05f)
    }

    /**
     * Tail of the layer after the last dry note end in the ring, ms (null: no note end with enough level, or the layer
     * has not ended yet and too little time passed). A note ends where the dry low band falls below its recent
     * maximum - [TAIL_DROP_DB]; the layer ends where it falls (and stays for 3 bins) below its own level before that
     * end - [TAIL_DROP_DB].
     */
    const val TAIL_DROP_DB = 20f

    /** Ring indices of the last dry note end ([start]) and of the layer's end ([end]; [ongoing]: not ended yet). */
    data class TailSpan(val start: Int, val end: Int, val ongoing: Boolean)

    fun tailSpan(dry: FloatArray, layer: FloatArray): TailSpan? {
        val n = minOf(dry.size, layer.size)
        if (n < 20) return null
        val dryMax = dry.maxOrNull() ?: return null
        if (dryMax < -50f) return null
        val thD = dryMax - TAIL_DROP_DB
        var end = -1
        for (i in n - 2 downTo 0) if (dry[i] >= thD && dry[i + 1] < thD) { end = i + 1; break }
        if (end < 0) return null
        var layerRef = -200f
        for (i in max(0, end - 40) until end) layerRef = max(layerRef, layer[i])
        if (layerRef < -70f) return null
        val thL = layerRef - TAIL_DROP_DB
        var j = end
        while (j < n) {
            if (layer[j] < thL && (j + 1 >= n || layer[j + 1] < thL) && (j + 2 >= n || layer[j + 2] < thL)) break
            // the next note starts before the layer ended: the tail lasts at least until here
            if (j > end && dry[j] >= thD) break
            j++
        }
        return TailSpan(end, minOf(j, n - 1), j >= n)
    }

    fun tailMs(dry: FloatArray, layer: FloatArray, binMs: Float): Float? {
        val t = tailSpan(dry, layer) ?: return null
        val ms = (t.end - t.start) * binMs
        if (t.ongoing) return if (ms >= 400f) ms else null
        return ms.coerceAtLeast(0f)
    }

    /** A tail longer than this is a warning (the model's own tail is about 20-40 ms). */
    const val TAIL_WARN_MS = 80f
    /** Volume (%) at and above which the volume-link warning applies while the link is off. */
    const val VOLUME_WARN_PCT = 60f

    fun evaluate(s: DevSnapshot): Set<DevWarning> {
        val out = LinkedHashSet<DevWarning>()
        if (s.outPeakDb >= s.ceilingDb - 0.5f || s.limiterGrDb >= 3f) out += DevWarning.NEAR_CEILING
        val inZone = bars(s).any { it.hz in BUZZ_LO_HZ..BUZZ_HI_HZ }
        if (inZone && s.headroomDb < 0f && s.layerBandDb >= s.thresholdDb - 6f) out += DevWarning.BUZZ_ZONE
        val tail = tailMs(s.ringDry, s.ringLayer, s.binMs)
        if (tail != null && tail > TAIL_WARN_MS) out += DevWarning.TAIL
        if (!s.volumeLink && s.volumePct >= VOLUME_WARN_PCT) out += DevWarning.VOLUME_NO_LINK
        return out
    }

    /** Which active warning the graph's inline note shows (most important first). */
    fun inlineWarning(active: Set<DevWarning>): DevWarning? =
        listOf(DevWarning.NEAR_CEILING, DevWarning.BUZZ_ZONE, DevWarning.TAIL, DevWarning.VOLUME_NO_LINK)
            .firstOrNull { it in active }
}

/** Persisted warning counts and hidden types ("pvb_flags"; host tests use a map). */
interface DevWarningStore {
    fun count(w: DevWarning): Int
    fun setCount(w: DevWarning, n: Int)
    fun hidden(w: DevWarning): Boolean
    fun setHidden(w: DevWarning, hidden: Boolean)
}

class DevWarningTracker(private val store: DevWarningStore) {
    private class State { var since = -1L; var clearSince = -1L; var shownThisEpisode = false; var lastShown = Long.MIN_VALUE / 2 }
    private val states = DevWarning.values().associateWith { State() }

    /**
     * Called with the conditions active now ([DevMath.evaluate]). Returns the warning whose dialog should open now
     * (its occurrence already counted), or null. [dialogOpen]: a dialog is showing, nothing new opens.
     */
    fun update(active: Set<DevWarning>, nowMs: Long, dialogOpen: Boolean = false): DevWarning? {
        var show: DevWarning? = null
        for (w in DevWarning.values()) {
            if (w == DevWarning.UNMEASURED) continue
            val st = states.getValue(w)
            if (w in active) {
                st.clearSince = -1
                if (st.since < 0) st.since = nowMs
                if (show == null && !dialogOpen && !st.shownThisEpisode && nowMs - st.since >= CONFIRM_MS &&
                    nowMs - st.lastShown >= COOLDOWN_MS && !(w.hideable && store.hidden(w))) {
                    st.shownThisEpisode = true
                    st.lastShown = nowMs
                    store.setCount(w, store.count(w) + 1)
                    show = w
                }
            } else {
                st.since = -1
                if (st.clearSince < 0) st.clearSince = nowMs
                if (nowMs - st.clearSince >= CLEAR_MS) st.shownThisEpisode = false
            }
        }
        return show
    }

    /** The unmeasured-phone notice on entering the screen: once ever. */
    fun unmeasuredOnEntry(measured: Boolean): Boolean {
        if (measured || store.count(DevWarning.UNMEASURED) > 0) return false
        store.setCount(DevWarning.UNMEASURED, 1)
        return true
    }

    /** The dialog of [w] offers "이 경고 다시 표시하지 않기" (from the 3rd occurrence; never for the loud output). */
    fun offerHide(w: DevWarning): Boolean = w.hideable && store.count(w) >= HIDE_FROM

    fun hide(w: DevWarning) { if (w.hideable) store.setHidden(w, true) }

    fun hiddenTypes(): List<DevWarning> = DevWarning.values().filter { it.hideable && store.hidden(it) }

    /** "숨긴 경고 다시 표시": every hidden warning shows again (counts are kept). */
    fun restoreAll() { for (w in DevWarning.values()) if (store.hidden(w)) store.setHidden(w, false) }

    companion object {
        const val CONFIRM_MS = 800L
        const val CLEAR_MS = 2000L
        const val COOLDOWN_MS = 30000L
        const val HIDE_FROM = 3
    }
}

/** Evidence badges and threshold labels that depend on the active device profile. */
object DevEvidenceText {
    /**
     * The "실측" badge of an item measured on [measuredOn]: on that very phone (active profile, measured) it reads
     * "실측됨" ([here] true), elsewhere "실측 <short name of the measured phone>" ([deviceName]).
     */
    data class MeasuredBadge(val here: Boolean, val deviceName: String)

    fun measuredBadge(active: DeviceProfile, measuredOn: DeviceProfile?): MeasuredBadge {
        val here = measuredOn != null && active.measured && active.id == measuredOn.id
        val name = measuredOn?.let { it.shortName.ifEmpty { it.name } } ?: DEFAULT_MEASURED_ON_NAME
        return MeasuredBadge(here, name)
    }

    /** Every 실측 item of the copy source was measured on the S26U profile. */
    const val MEASURED_ON_ID = DeviceProfiles.S26U
    const val DEFAULT_MEASURED_ON_NAME = "S26U"

    /** The gauge's threshold label: measured on this phone, or an estimate from the measured phone. */
    fun thresholdMeasured(active: DeviceProfile): Boolean = active.measured
}

package me.timschneeberger.rootlessjamesdsp.pvb

import kotlin.math.max
import kotlin.math.min

/*
 * "저음 맞추기" session (docs/BASS_FIT_PLAN.md): the order of the steps, what each question plays and what the answers
 * set. Pure Kotlin, host tested (tools/pvb-harness/jvm/BassFitSessionTest.kt). The screen shows [BassFitSession.prompt],
 * plays it and passes the answer back; the room check, the microphone and the timing stay in the screen.
 *
 * One seed per run (the screen draws a new one every time): every part gets its own seed from it, so the questions'
 * order, the catch trials and the A/B/X sides differ from run to run, and a run can still be replayed from its seed.
 */

/** Test material: [LOW] a sustained bass line (41-73 Hz), [MID] notes just above the generator edge (edge check). */
enum class FitMaterial { LOW, MID }

/** How one clip plays, on top of the stored settings ([BassFitSettings.of]). */
data class FitVariant(
    val vbOn: Boolean,
    val levelDb: Double,
    /** Band from a found floor; null = the stored values. */
    val floor: BassFitMapping.FloorSettings? = null,
    /** Generator edge instead of the floor's (the edge check), Hz. */
    val boundaryHz: Double? = null,
    /** Harmonic shape; null = the stored roll-off and harmonic offsets. */
    val shape: ShapeGrid.Cell? = null,
    /** Step 1: the speaker alone (no layer, flat EQ, high-pass out of the way). */
    val raw: Boolean = false,
) {
    companion object {
        val RAW = FitVariant(vbOn = false, levelDb = 0.0, raw = true)
    }
}

enum class FitStage { FLOOR, EDGE, LAYER, STRENGTH, BREAKUP, SHAPE_OFFER, SHAPE, DONE }

sealed class FitPrompt {
    enum class Purpose { EDGE, LAYER, STRENGTH, SHAPE }

    /** Step 1: two intervals, a tone in one of them, or in neither (catch trial). */
    data class Floor(val trial: FloorStaircase.Trial, val number: Int) : FitPrompt()

    /** Is there a difference: A, B and X (X is A or B, hidden). [toneHz]: the edge, for [FitMaterial.MID]. */
    data class Abx(
        val purpose: Purpose, val material: FitMaterial, val toneHz: Double,
        val a: FitVariant, val b: FitVariant, val xIsA: Boolean, val number: Int, val maxTrials: Int,
    ) : FitPrompt()

    /** Which is better: A or B, or no difference. */
    data class Prefer(
        val purpose: Purpose, val material: FitMaterial, val toneHz: Double,
        val a: FitVariant, val b: FitVariant, val number: Int,
    ) : FitPrompt()

    /** Step 3: does this clip buzz? */
    data class Buzz(val variant: FitVariant, val number: Int) : FitPrompt()

    object ShapeOffer : FitPrompt()
    object Done : FitPrompt()
}

/** What a run found and what it applies (null = keep the stored value). */
data class FitResult(
    val seed: Long,
    val floorHz: Double?,
    val floorReliable: Boolean,
    /** Applied band (floor found and reliable). */
    val floor: BassFitMapping.FloorSettings?,
    /** Applied generator edge (the floor's, or 1.3 times it when the listener preferred that). */
    val edgeHz: Double?,
    /** Off vs on told apart (null: not tested). */
    val layerAudible: Boolean?,
    val preferredDb: Int?,
    val strengthConsistent: Boolean,
    val breakupDb: Double?,
    val limitDb: Double?,
    val limitReliable: Boolean,
    val shapeTried: Boolean,
    val shapeConsistent: Boolean,
    /** Applied shape (tried and consistent). */
    val shape: ShapeGrid.Cell?,
    /** Applied strength: the preferred one (or the stored one) capped by a reliable limit. */
    val strengthDb: Double?,
    /** Question counts (validation log): step 1 and step 3, catch trials and "heard" / "buzz" on them. */
    val floorQuestions: Int = 0,
    val floorCatch: Int = 0,
    val floorFalseAlarms: Int = 0,
    val breakupQuestions: Int = 0,
    val breakupCatch: Int = 0,
    val breakupFalseAlarms: Int = 0,
) {
    /** [values] ([DevParams.ALL] order) with what this run applies. */
    fun applyTo(values: FloatArray): FloatArray {
        val v = values.copyOf()
        fun set(spec: DevSpec, x: Double) { v[DevParams.ALL.indexOf(spec)] = spec.snap(x.toFloat()) }
        floor?.let {
            set(DevParams.HP, it.hpHz)
            set(DevParams.BOUNDARY, edgeHz ?: it.boundaryHz)
            set(DevParams.OUT_LO, it.outLoHz)
            set(DevParams.TABLE_FLOOR, it.tableScale * BassFitMapping.REF_FLOOR_HZ)
        }
        strengthDb?.let { set(DevParams.STRENGTH, it) }
        shape?.let { cell ->
            set(DevParams.ROLLOFF, cell.rolloffDbOct)
            val h = BassFitMapping.harmonicOffsets(cell.lowOrderDb)
            set(DevParams.H2, h[0]); set(DevParams.H3, h[1]); set(DevParams.H4, h[2]); set(DevParams.H5, h[3])
        }
        return v
    }
}

/** What a run asks: everything, or one step alone (validation mode: repeated against the UMIK-1). */
enum class FitScope { ALL, FLOOR, BREAKUP }

class BassFitSession(val seed: Long, val storedStrengthDb: Double, val scope: FitScope = FitScope.ALL) {
    private val seeds = FitRng(seed)
    private fun sub(): Long = seeds.next()

    var stage = FitStage.FLOOR; private set
    /** Question number within the stage (1-based once a question is shown). */
    private var number = 1

    private val floorTest = FloorStaircase(sub())
    private var floor: BassFitMapping.FloorSettings? = null
    private val edgeSeed = sub()
    private var edgeAbx: AbxRun? = null
    private val edgeRng = FitRng(sub())
    private var edgeLoIsA = false
    private var edgeVotes = 0
    private var edgeAsked = 0
    private var edgeHz: Double? = null
    private val layerAbx = AbxRun(sub())
    private var layerAudible: Boolean? = null
    private val strength = StrengthBracket(sub())
    private var strengthTried = false
    private val breakupSeed = sub()
    private var breakup: BreakupStaircase? = null
    private val shape = ShapeGrid(sub())
    private var shapeTried = false

    /** Strength the edge and layer checks play at: the stored one, at least +4 and at most +8. */
    val probeDb: Double = storedStrengthDb.coerceIn(4.0, 8.0)

    init {
        if (scope == FitScope.BREAKUP) startBreakup()
    }

    /** 1..4: the step the screen shows ("1단계" ...); 0 when done. */
    val step: Int
        get() = when (stage) {
            FitStage.FLOOR, FitStage.EDGE -> 1
            FitStage.LAYER, FitStage.STRENGTH -> 2
            FitStage.BREAKUP -> 3
            FitStage.SHAPE_OFFER, FitStage.SHAPE -> 4
            FitStage.DONE -> 0
        }

    val prompt: FitPrompt
        get() = when (stage) {
            FitStage.FLOOR -> FitPrompt.Floor(floorTest.current, number)
            FitStage.EDGE -> edgePrompt()
            FitStage.LAYER -> FitPrompt.Abx(FitPrompt.Purpose.LAYER, FitMaterial.LOW, 0.0,
                FitVariant(false, probeDb, floor, edgeHz), FitVariant(true, probeDb, floor, edgeHz),
                layerAbx.xIsA(), number, layerAbx.maxTrials)
            FitStage.STRENGTH -> strength.current!!.let { p ->
                val lo = FitVariant(true, p.lo.toDouble(), floor, edgeHz)
                val hi = FitVariant(true, p.hi.toDouble(), floor, edgeHz)
                FitPrompt.Prefer(FitPrompt.Purpose.STRENGTH, FitMaterial.LOW, 0.0,
                    if (p.loIsA) lo else hi, if (p.loIsA) hi else lo, number)
            }
            FitStage.BREAKUP -> when (val t = breakup!!.current) {
                is BreakupStaircase.Trial.Level -> FitPrompt.Buzz(FitVariant(true, t.db, floor, edgeHz), number)
                is BreakupStaircase.Trial.Catch -> FitPrompt.Buzz(FitVariant(false, 0.0, floor, edgeHz), number)
            }
            FitStage.SHAPE_OFFER -> FitPrompt.ShapeOffer
            FitStage.SHAPE -> shape.current!!.let { (i, j, iIsA) ->
                val level = currentStrength()
                val vi = FitVariant(true, level, floor, edgeHz, shape.cells[i])
                val vj = FitVariant(true, level, floor, edgeHz, shape.cells[j])
                FitPrompt.Prefer(FitPrompt.Purpose.SHAPE, FitMaterial.LOW, 0.0, if (iIsA) vi else vj, if (iIsA) vj else vi, number)
            }
            FitStage.DONE -> FitPrompt.Done
        }

    // ------------------------------------------------------------------------------------------------ answers

    fun answerFloor(c: FloorStaircase.Choice) {
        check(stage == FitStage.FLOOR)
        floorTest.answer(c)
        number++
        if (!floorTest.done) return
        val f = floorTest.floorHz()
        floor = if (f != null && floorTest.reliable) BassFitMapping.fromFloor(f) else null
        edgeHz = floor?.boundaryHz
        if (scope == FitScope.FLOOR) { enter(FitStage.DONE); return }
        // the edge check needs room above the floor's edge (the engine stops at 280 Hz)
        if (floor != null && raisedEdge() / floor!!.boundaryHz >= 1.1) {
            edgeAbx = AbxRun(edgeSeed)
            enter(FitStage.EDGE)
        } else enter(FitStage.LAYER)
    }

    private fun raisedEdge(): Double = min(BassFitMapping.MAX_EDGE_HZ, floor!!.boundaryHz * 1.3)

    private fun edgePrompt(): FitPrompt {
        val f = floor!!
        val low = FitVariant(true, probeDb, f, f.boundaryHz)
        val high = FitVariant(true, probeDb, f, raisedEdge())
        val abx = edgeAbx
        return if (abx != null) FitPrompt.Abx(FitPrompt.Purpose.EDGE, FitMaterial.MID, f.boundaryHz, low, high,
            abx.xIsA(), number, abx.maxTrials)
        else FitPrompt.Prefer(FitPrompt.Purpose.EDGE, FitMaterial.MID, f.boundaryHz,
            if (edgeLoIsA) low else high, if (edgeLoIsA) high else low, number)
    }

    /** ABX of the edge check, the layer check (X is A?). */
    fun answerAbx(saidXIsA: Boolean) {
        when (stage) {
            FitStage.EDGE -> {
                val abx = edgeAbx ?: error("edge preference, not ABX")
                number++
                when (abx.answer(saidXIsA)) {
                    AbxRun.State.RUNNING -> {}
                    // no difference keeps the lower edge
                    AbxRun.State.NOT_DISTINGUISHED -> enter(FitStage.LAYER)
                    // told apart: which is better? two blind pairs, sides swapped; the higher edge only if both pick it
                    AbxRun.State.DISTINGUISHED -> {
                        edgeAbx = null
                        edgeLoIsA = edgeRng.bit()
                        number = 1
                    }
                }
            }
            FitStage.LAYER -> {
                number++
                when (layerAbx.answer(saidXIsA)) {
                    AbxRun.State.RUNNING -> {}
                    AbxRun.State.DISTINGUISHED -> { layerAudible = true; strengthTried = true; enter(FitStage.STRENGTH) }
                    // the layer can't be told from no layer at this volume: no strength preference to ask for
                    AbxRun.State.NOT_DISTINGUISHED -> { layerAudible = false; startBreakup() }
                }
            }
            else -> error("no ABX in $stage")
        }
    }

    enum class Pick { A, B, SAME }

    fun answerPrefer(p: Pick) {
        when (stage) {
            FitStage.EDGE -> {
                check(edgeAbx == null)
                val pickedHigh = (p == Pick.A && !edgeLoIsA) || (p == Pick.B && edgeLoIsA)
                if (pickedHigh) edgeVotes++
                edgeAsked++
                number++
                if (edgeAsked < 2) edgeLoIsA = !edgeLoIsA
                else {
                    if (edgeVotes == 2) edgeHz = raisedEdge()
                    enter(FitStage.LAYER)
                }
            }
            FitStage.STRENGTH -> {
                strength.answer(when (p) { Pick.A -> StrengthBracket.Answer.A; Pick.B -> StrengthBracket.Answer.B; Pick.SAME -> StrengthBracket.Answer.SAME })
                number++
                if (strength.done) startBreakup()
            }
            FitStage.SHAPE -> {
                shape.answer(when (p) { Pick.A -> ShapeGrid.Answer.A; Pick.B -> ShapeGrid.Answer.B; Pick.SAME -> ShapeGrid.Answer.SAME })
                number++
                if (shape.done) enter(FitStage.DONE)
            }
            else -> error("no preference in $stage")
        }
    }

    fun answerBuzz(buzz: Boolean) {
        check(stage == FitStage.BREAKUP)
        val b = breakup!!
        b.answer(if (buzz) BreakupStaircase.Answer.BUZZ else BreakupStaircase.Answer.CLEAN)
        number++
        if (b.done) enter(if (scope == FitScope.BREAKUP) FitStage.DONE else FitStage.SHAPE_OFFER)
    }

    /** The optional shape step: take it (about 18 pairs) or finish. */
    fun shapeChoice(take: Boolean) {
        check(stage == FitStage.SHAPE_OFFER)
        shapeTried = take
        enter(if (take) FitStage.SHAPE else FitStage.DONE)
    }

    private fun enter(s: FitStage) { stage = s; number = 1 }

    private fun startBreakup() {
        breakup = BreakupStaircase(breakupSeed, max(2.0, preferred()?.toDouble() ?: storedStrengthDb))
        enter(FitStage.BREAKUP)
    }

    private fun preferred(): Int? = if (layerAudible == true && strength.done && strength.consistent) strength.result else null

    private fun limit(): Double? = breakup?.takeIf { it.done && it.reliable }?.limitDb

    /** Preferred (or stored) strength capped by a reliable limit. */
    private fun currentStrength(): Double {
        val base = preferred()?.toDouble() ?: storedStrengthDb
        return limit()?.let { min(base, it) } ?: base
    }

    val result: FitResult
        get() {
            val pref = preferred()
            val lim = limit()
            val capped = lim != null && lim < (pref?.toDouble() ?: storedStrengthDb)
            val b = breakup
            return FitResult(
                seed = seed,
                floorHz = floorTest.floorHz(),
                floorReliable = floorTest.reliable,
                floor = floor,
                edgeHz = edgeHz,
                layerAudible = layerAudible,
                preferredDb = if (strengthTried && strength.done) strength.result else null,
                strengthConsistent = strength.consistent,
                breakupDb = b?.breakupDb(),
                limitDb = b?.limitDb,
                limitReliable = b != null && b.done && b.reliable,
                shapeTried = shapeTried,
                shapeConsistent = shapeTried && shape.done && shape.consistent,
                shape = if (shapeTried && shape.done && shape.consistent) shape.best() else null,
                strengthDb = if (pref != null || capped) currentStrength() else null,
                floorQuestions = floorTest.toneTrials + floorTest.catchTrials,
                floorCatch = floorTest.catchTrials,
                floorFalseAlarms = floorTest.falseAlarms,
                breakupQuestions = b?.let { it.levelTrials + it.catchTrials } ?: 0,
                breakupCatch = b?.catchTrials ?: 0,
                breakupFalseAlarms = b?.falseAlarms ?: 0,
            )
        }
}

/** The final check on the listener's own music: [trials] blind pairs of the stored and the new settings. */
class CheckRound(seed: Long, val trials: Int = 3) {
    enum class Answer { FIRST, SECOND, SAME }

    private val rng = FitRng(seed)
    var number = 0; private set
    /** Whether the new settings are "1번" in the current trial. */
    var newIsFirst = rng.bit(); private set
    var newPicked = 0; private set
    var oldPicked = 0; private set
    var same = 0; private set

    fun answer(a: Answer) {
        check(!done)
        when (a) {
            Answer.SAME -> same++
            Answer.FIRST -> if (newIsFirst) newPicked++ else oldPicked++
            Answer.SECOND -> if (newIsFirst) oldPicked++ else newPicked++
        }
        number++
        if (!done) newIsFirst = rng.bit()
    }

    val done: Boolean get() = number >= trials
}

/** What a clip plays: the stored settings with the test holds and the variant (never stored). */
object BassFitSettings {
    /** High-pass of step 1: out of the way of the 70-300 Hz tones (the engine accepts 10 Hz and up). */
    const val RAW_HP_HZ = 20f

    /**
     * [stored] played for a clip: developer values on, the volume link and quiet-passage bass held off (the strength
     * asked for is the strength played), spatial off; then [v]. Step 1 ([FitVariant.raw]): no layer, flat EQ.
     */
    fun of(stored: PvbSettings, v: FitVariant): PvbSettings {
        var s = stored.copy(devOn = true, vbVolLink = false, dynOn = false, xtcMode = PvbSettings.XTC_OFF)
        if (v.raw) return s.copy(vbOn = false, hpHz = RAW_HP_HZ, lowDb = 0f, hiDb = 0f, hsDb = 0f)
        v.floor?.let { f ->
            s = s.copy(
                hpHz = DevParams.HP.snap(f.hpHz.toFloat()),
                devBoundaryHz = DevParams.BOUNDARY.snap((v.boundaryHz ?: f.boundaryHz).toFloat()),
                devOutLoHz = DevParams.OUT_LO.snap(f.outLoHz.toFloat()),
                devTableFloorHz = DevParams.TABLE_FLOOR.snap((f.tableScale * BassFitMapping.REF_FLOOR_HZ).toFloat()),
            )
        }
        if (v.floor == null && v.boundaryHz != null) s = s.copy(devBoundaryHz = DevParams.BOUNDARY.snap(v.boundaryHz.toFloat()))
        v.shape?.let { cell ->
            val h = BassFitMapping.harmonicOffsets(cell.lowOrderDb)
            s = s.copy(
                devRolloffOffset = DevParams.ROLLOFF.snap(cell.rolloffDbOct.toFloat()),
                devH2Db = DevParams.H2.snap(h[0].toFloat()), devH3Db = DevParams.H3.snap(h[1].toFloat()),
                devH4Db = DevParams.H4.snap(h[2].toFloat()), devH5Db = DevParams.H5.snap(h[3].toFloat()),
            )
        }
        return s.copy(vbOn = v.vbOn, vbLevelDb = DevParams.STRENGTH.snap(v.levelDb.toFloat()))
    }
}

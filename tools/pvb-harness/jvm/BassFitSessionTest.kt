import me.timschneeberger.rootlessjamesdsp.pvb.BassFitSession
import me.timschneeberger.rootlessjamesdsp.pvb.BassFitSettings
import me.timschneeberger.rootlessjamesdsp.pvb.CheckRound
import me.timschneeberger.rootlessjamesdsp.pvb.DevParams
import me.timschneeberger.rootlessjamesdsp.pvb.FitMaterial
import me.timschneeberger.rootlessjamesdsp.pvb.FitPrompt
import me.timschneeberger.rootlessjamesdsp.pvb.FitRng
import me.timschneeberger.rootlessjamesdsp.pvb.FitStage
import me.timschneeberger.rootlessjamesdsp.pvb.FitVariant
import me.timschneeberger.rootlessjamesdsp.pvb.FloorStaircase
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import me.timschneeberger.rootlessjamesdsp.pvb.ShapeGrid
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.log2
import kotlin.system.exitProcess

// "저음 맞추기" session (BassFitSession.kt): step order, fresh order per seed, what the answers apply.

private var passed = 0
private fun check(ok: Boolean, what: String) {
    if (!ok) { println("[FAIL] $what"); exitProcess(1) }
    println("[PASS] $what"); passed++
}

/** A simulated listener. [edgeAudible]: hears the higher edge; [layerAudible]: hears off vs on. */
private class Listener(
    val floorHz: Double, val idealDb: Double, val breakDb: Double, val seed: Long,
    val edgeAudible: Boolean = false, val layerAudible: Boolean = true, val catchLiar: Boolean = false,
    val takeShape: Boolean = false, val shapeTarget: Int = 4,
) {
    val r = FitRng(seed * 7 + 3)
    fun u() = (r.next() ushr 11).toDouble() / (1L shl 53)
    val log = ArrayList<String>()

    fun run(s: BassFitSession): BassFitSession {
        var guard = 0
        while (s.stage != FitStage.DONE && guard++ < 400) {
            when (val p = s.prompt) {
                is FitPrompt.Floor -> {
                    val t = p.trial
                    log += when (t) { is FloorStaircase.Trial.Catch -> "c"; is FloorStaircase.Trial.Tone -> if (t.inFirst) "1" else "2" }
                    s.answerFloor(when (t) {
                        is FloorStaircase.Trial.Catch -> if (catchLiar) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.NEITHER
                        is FloorStaircase.Trial.Tone -> {
                            val heard = u() < 1 / (1 + exp(-log2(t.hz / floorHz) / 0.06))
                            when {
                                heard -> if (t.inFirst) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND
                                u() < 0.5 -> FloorStaircase.Choice.NEITHER
                                else -> FloorStaircase.Choice.BUZZ_ONLY
                            }
                        }
                    })
                }
                is FitPrompt.Abx -> {
                    log += "x" + (if (p.xIsA) "A" else "B")
                    val hears = when (p.purpose) { FitPrompt.Purpose.EDGE -> edgeAudible; else -> layerAudible }
                    s.answerAbx(if (hears) p.xIsA else r.bit())
                }
                is FitPrompt.Prefer -> {
                    log += "p" + p.a.levelDb.toInt() + p.b.levelDb.toInt()
                    val pick = when (p.purpose) {
                        FitPrompt.Purpose.STRENGTH -> {
                            val da = abs(p.a.levelDb - idealDb); val db = abs(p.b.levelDb - idealDb)
                            when { abs(da - db) < 1e-9 -> BassFitSession.Pick.SAME; da < db -> BassFitSession.Pick.A; else -> BassFitSession.Pick.B }
                        }
                        FitPrompt.Purpose.EDGE -> if ((p.a.boundaryHz ?: 0.0) > (p.b.boundaryHz ?: 0.0)) BassFitSession.Pick.A else BassFitSession.Pick.B
                        else -> {
                            val t = ShapeGrid(0).cells[shapeTarget]
                            fun d(v: FitVariant) = abs(v.shape!!.rolloffDbOct - t.rolloffDbOct) / 6 + abs(v.shape.lowOrderDb - t.lowOrderDb) / 4
                            when { abs(d(p.a) - d(p.b)) < 1e-9 -> BassFitSession.Pick.SAME; d(p.a) < d(p.b) -> BassFitSession.Pick.A; else -> BassFitSession.Pick.B }
                        }
                    }
                    s.answerPrefer(pick)
                }
                is FitPrompt.Buzz -> {
                    val v = p.variant
                    val buzz = v.vbOn && u() < 1 / (1 + exp(-(v.levelDb - breakDb) / 0.7))
                    log += "b" + (if (v.vbOn) v.levelDb.toInt().toString() else "-") + (if (buzz) "B" else "c")
                    s.answerBuzz(buzz)
                }
                is FitPrompt.ShapeOffer -> s.shapeChoice(takeShape)
                is FitPrompt.Done -> {}
            }
        }
        return s
    }
}

fun main() {
    // ---------------------------------------------------------------------------------------- full runs
    val stored = DevParams.read(PvbSettings(vbLevelDb = 4f))
    run {
        val l1 = Listener(floorHz = 200.0, idealDb = 6.0, breakDb = 11.0, seed = 1)
        val s = l1.run(BassFitSession(11L, 4.0))
        val r = s.result
        check(s.stage == FitStage.DONE && r.floorReliable && r.floorHz != null && abs(log2(r.floorHz!! / 200.0)) < 0.25,
            "floor 200 Hz found (${r.floorHz?.toInt()} Hz), reliable")
        check(r.edgeHz == r.floor!!.boundaryHz, "edge: no difference heard -> the lower edge (${r.edgeHz?.toInt()} Hz)")
        check(r.layerAudible == true && r.preferredDb == 6 && r.strengthConsistent, "layer heard, preferred +6")
        check(r.limitReliable && r.limitDb != null && r.limitDb!! in 6.0..9.0 && r.strengthDb == 6.0,
            "break-up near 11 dB -> limit ${r.limitDb}, strength +6 kept")
        check(!r.shapeTried && r.shape == null, "shape skipped: roll-off and harmonics unchanged")
        val v = r.applyTo(stored)
        fun at(spec: me.timschneeberger.rootlessjamesdsp.pvb.DevSpec) = v[DevParams.ALL.indexOf(spec)]
        val m = me.timschneeberger.rootlessjamesdsp.pvb.BassFitMapping.fromFloor(r.floorHz!!)
        check(at(DevParams.TABLE_FLOOR) == DevParams.TABLE_FLOOR.snap(r.floorHz!!.toFloat()) &&
            at(DevParams.OUT_LO) == DevParams.OUT_LO.snap(m.outLoHz.toFloat()) && at(DevParams.BOUNDARY) == DevParams.BOUNDARY.snap(m.boundaryHz.toFloat()) &&
            at(DevParams.HP) == DevParams.HP.snap(m.hpHz.toFloat()) && at(DevParams.STRENGTH) == 6f,
            "applied: table floor ${at(DevParams.TABLE_FLOOR)}, out low ${at(DevParams.OUT_LO)}, edge ${at(DevParams.BOUNDARY)}, HP ${at(DevParams.HP)}, strength ${at(DevParams.STRENGTH)}")
        check(at(DevParams.ROLLOFF) == stored[DevParams.ALL.indexOf(DevParams.ROLLOFF)] && at(DevParams.H2) == 0f,
            "untested values untouched")
    }
    run {
        // preferred +8, but the speaker breaks up at 7: capped
        val r = Listener(floorHz = 150.0, idealDb = 9.0, breakDb = 7.0, seed = 2).run(BassFitSession(22L, 4.0)).result
        check(r.preferredDb == 8 && r.limitDb != null && r.limitDb!! <= 5.0 && r.strengthDb == r.limitDb,
            "preferred +8, break-up at 7 -> strength capped at the limit (${r.limitDb})")
    }
    run {
        // the higher edge is heard and preferred twice
        val s = Listener(floorHz = 160.0, idealDb = 4.0, breakDb = 12.0, seed = 3, edgeAudible = true).run(BassFitSession(33L, 4.0))
        val r = s.result
        check(r.floor != null && r.edgeHz != null && r.edgeHz!! > r.floor!!.boundaryHz * 1.25,
            "edge told apart and preferred -> 1.3 times higher (${r.floor?.boundaryHz?.toInt()} -> ${r.edgeHz?.toInt()} Hz)")
    }
    run {
        // the layer can't be heard at this volume: no strength questions; only a cap below the stored strength applies
        val l = Listener(floorHz = 150.0, idealDb = 6.0, breakDb = 99.0, seed = 4, layerAudible = false)
        val s = l.run(BassFitSession(44L, 4.0))
        val r = s.result
        check(r.layerAudible == false && r.preferredDb == null && r.strengthDb == null && l.log.none { it.startsWith("p") && it != "p00" },
            "layer not heard -> no strength pairs, stored strength kept")
    }
    run {
        // a listener who "hears" silent trials: floor unreliable -> band values untouched
        val r = Listener(floorHz = 150.0, idealDb = 4.0, breakDb = 12.0, seed = 5, catchLiar = true).run(BassFitSession(55L, 4.0)).result
        check(!r.floorReliable && r.floor == null && r.applyTo(stored)[DevParams.ALL.indexOf(DevParams.HP)] == stored[DevParams.ALL.indexOf(DevParams.HP)],
            "floor unreliable -> high-pass, edge, band and table floor unchanged")
    }
    run {
        val r = Listener(floorHz = 150.0, idealDb = 4.0, breakDb = 12.0, seed = 6, takeShape = true, shapeTarget = 2).run(BassFitSession(66L, 4.0)).result
        val v = r.applyTo(stored)
        check(r.shapeTried && r.shapeConsistent && r.shape == ShapeGrid(0).cells[2] &&
            v[DevParams.ALL.indexOf(DevParams.ROLLOFF)] == -6f && v[DevParams.ALL.indexOf(DevParams.H2)] == 4f &&
            v[DevParams.ALL.indexOf(DevParams.H3)] == -1f, "shape taken: cell (-6 dB/oct, +4) -> roll-off -6, H2 +4, H3..5 -1")
    }

    // ---------------------------------------------------------------------------------------- a new order every run
    run {
        fun order(seed: Long) = Listener(floorHz = 170.0, idealDb = 6.0, breakDb = 10.0, seed = 9).also { it.run(BassFitSession(seed, 4.0)) }.log
        val a = order(1001); val b = order(1001); val c = order(2002)
        check(a == b, "same seed -> the same questions in the same order (a run can be replayed)")
        check(a != c, "another seed -> another order of the questions and other A/B/X sides")
        val sides = (0 until 30).map { seed ->
            val s = BassFitSession(seed * 104729L + 17, 4.0)
            (s.prompt as FitPrompt.Floor).trial.let { if (it is FloorStaircase.Trial.Tone) it.inFirst else null }
        }
        check(sides.count { it == true } in 8..22, "first tone in interval 1 in ${sides.count { it == true }} of 30 runs (about half)")
        val firstX = (0 until 40).map { seed ->
            val s = BassFitSession(seed * 7919L + 5, 4.0)
            Listener(floorHz = 150.0, idealDb = 4.0, breakDb = 12.0, seed = 1).let { l ->
                var g = 0
                while (s.stage == FitStage.FLOOR && g++ < 100) {
                    val t = (s.prompt as FitPrompt.Floor).trial
                    s.answerFloor(if (t is FloorStaircase.Trial.Tone) (if (t.hz > 150) (if (t.inFirst) FloorStaircase.Choice.FIRST else FloorStaircase.Choice.SECOND) else FloorStaircase.Choice.NEITHER) else FloorStaircase.Choice.NEITHER)
                }
            }
            (s.prompt as? FitPrompt.Abx)?.xIsA
        }.filterNotNull()
        check(firstX.size >= 30 && firstX.count { it } in (firstX.size / 4)..(firstX.size * 3 / 4),
            "first X of the ABX is A in ${firstX.count { it }} of ${firstX.size} runs (about half)")
    }

    // ---------------------------------------------------------------------------------------- one step alone
    run {
        val l = Listener(floorHz = 180.0, idealDb = 4.0, breakDb = 9.0, seed = 12)
        val s = l.run(BassFitSession(1212L, 4.0, me.timschneeberger.rootlessjamesdsp.pvb.FitScope.FLOOR))
        val r = s.result
        check(s.stage == FitStage.DONE && r.floorHz != null && l.log.all { it.length == 1 } && r.floorQuestions in 10..30 &&
            r.floorCatch >= 2 && r.layerAudible == null && r.limitDb == null,
            "floor only: ${r.floorQuestions} questions (${r.floorCatch} catch), floor ${r.floorHz?.toInt()} Hz, nothing else asked")
        val lb = Listener(floorHz = 180.0, idealDb = 4.0, breakDb = 9.0, seed = 13)
        val sb = BassFitSession(1313L, 4.0, me.timschneeberger.rootlessjamesdsp.pvb.FitScope.BREAKUP)
        check(sb.stage == FitStage.BREAKUP, "break-up only: starts at step 3")
        lb.run(sb)
        val rb = sb.result
        check(sb.stage == FitStage.DONE && lb.log.all { it.startsWith("b") } && rb.limitDb != null && rb.breakupCatch >= 2 &&
            rb.floorQuestions == 0, "break-up only: ${rb.breakupQuestions} questions, limit ${rb.limitDb}, no other step")
    }

    // ---------------------------------------------------------------------------------------- validation plan, log
    run {
        val conds = me.timschneeberger.rootlessjamesdsp.pvb.FitConditions.ALL
        val a = me.timschneeberger.rootlessjamesdsp.pvb.ValidationPlan(5L, conds, 3).runs
        val b = me.timschneeberger.rootlessjamesdsp.pvb.ValidationPlan(6L, conds, 3).runs
        check(a.size == 15 && conds.all { c -> a.count { it == c } == 3 } && a != b,
            "plan: every virtual speaker 3 times, another order for another seed")
        check((1 until a.size).all { a[it] != a[it - 1] }, "plan: no condition twice in a row")
        val line = me.timschneeberger.rootlessjamesdsp.pvb.ValidationLog.line(me.timschneeberger.rootlessjamesdsp.pvb.ValidationLog.Row(
            "2026-10-24T09:40", "SM-S948N", "0.9.0-beta.6", me.timschneeberger.rootlessjamesdsp.pvb.ValidationLog.Kind.EAR_FLOOR,
            150.0, 0x1234L, 8, 15, 162.34, true, 22, 4, 0, 158.0, false, 152.0, true, 41.25))
        val cols = me.timschneeberger.rootlessjamesdsp.pvb.ValidationLog.HEADER.split(",").size
        check(line.split(",").size == cols && line.contains(",ear_floor_hz,hp150,0000000000001234,8,15,162.3,1,22,4,0,158.0,0,152,1,41.3"),
            "log line: $line")
    }

    // ---------------------------------------------------------------------------------------- clip settings
    run {
        val base = PvbSettings(hpHz = 120f, lowDb = 2f, hiDb = -2f, vbOn = true, vbLevelDb = 5f, vbVolLink = true, dynOn = true,
            xtcMode = PvbSettings.XTC_CENTRE)
        val raw = BassFitSettings.of(base, FitVariant.RAW)
        check(!raw.vbOn && raw.hpHz == BassFitSettings.RAW_HP_HZ && raw.lowDb == 0f && raw.hiDb == 0f && raw.hsDb == 0f &&
            raw.xtcMode == PvbSettings.XTC_OFF && !raw.vbVolLink && !raw.dynOn, "step 1 plays the speaker alone (no layer, flat, high-pass 20 Hz)")
        val f = me.timschneeberger.rootlessjamesdsp.pvb.BassFitMapping.fromFloor(200.0)
        val on = BassFitSettings.of(base, FitVariant(true, 7.0, f))
        check(on.devOn && on.vbOn && on.vbLevelDb == 7f && on.devTableFloorHz == 200f && on.devOutLoHz == 200f &&
            on.devBoundaryHz == 255f && on.hpHz == 135f && on.lowDb == 2f && !on.vbVolLink,
            "a clip with a found floor: table floor 200, out low 200, edge 255, HP 135, strength as asked, EQ kept")
        val off = BassFitSettings.of(base, FitVariant(false, 7.0, f))
        check(!off.vbOn && off.devTableFloorHz == 200f, "layer off: same band, no layer")
        check(BassFitSettings.of(base, FitVariant(true, 4.0)).let { it.hpHz == 120f && it.devBoundaryHz == DevParams.BOUNDARY.default },
            "no floor: stored band values")
    }
    check(FitMaterial.values().size == 2, "two clip materials")

    // ---------------------------------------------------------------------------------------- music check
    run {
        val c = CheckRound(7)
        val sides = ArrayList<Boolean>()
        while (!c.done) { sides += c.newIsFirst; c.answer(if (c.newIsFirst) CheckRound.Answer.FIRST else CheckRound.Answer.SECOND) }
        check(c.newPicked == 3 && c.oldPicked == 0 && c.number == 3, "music check: picking the new settings each time counts 3 of 3")
        val varied = (0 until 20).map { s -> CheckRound(s.toLong()).newIsFirst }.toSet().size == 2
        check(varied, "music check: which side is new changes with the seed")
    }

    println("BassFitSessionTest: $passed checks passed")
}

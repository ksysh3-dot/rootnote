// JamesDSP -> PVB chain (JdspChain.kt): route decision table, per-module sealing, sealed output control and the
// restore of the user's values, 16-bit conversion against the PVB engine's own 16-bit path (host libpvbengine.so),
// and the en/ko strings of the chain notes. Arguments: repository root. Run with run_jvm_test.sh.
import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain.Module
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain.Policy
import me.timschneeberger.rootlessjamesdsp.pvb.JdspChain.Route
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbEngine
import me.timschneeberger.rootlessjamesdsp.pvb.PvbParam
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.random.Random
import kotlin.system.exitProcess

private var failures = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name${if (info.isNotEmpty()) " ($info)" else ""}")
    if (!ok) failures++
}

private class ChainPrefs(val values: Map<String, Any?>) : SharedPreferences {
    override val all: Map<String, *> get() = values
    override fun getString(key: String, defValue: String?): String? = values[key] as String? ?: defValue
    override fun getFloat(key: String, defValue: Float): Float = values[key] as Float? ?: defValue
    override fun getBoolean(key: String, defValue: Boolean): Boolean = values[key] as Boolean? ?: defValue
    override fun getInt(key: String, defValue: Int): Int = values[key] as Int? ?: defValue
    override fun edit(): SharedPreferences.Editor = throw UnsupportedOperationException("read only")
}

/**
 * What JamesDspBaseEngine sends to the native engine for one sync, from the user's (never modified) values: the same
 * JdspChain calls the engine makes. Returns output control, bass/tube switches and the chain's "JamesDSP on".
 */
private data class Sent(val output: JdspChain.Output, val bass: Boolean, val tube: Boolean, val effects: Boolean)

private fun sync(user: JdspChain.Output, enabled: Set<Module>, sealed: Boolean) = Sent(
    JdspChain.output(user, sealed),
    JdspChain.allowed(Module.BASS, Module.BASS in enabled, sealed),
    JdspChain.allowed(Module.TUBE, Module.TUBE in enabled, sealed),
    JdspChain.hasEffects(enabled, sealed),
)

fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "." })
    PvbBuild.reset()

    // --- route decision table: PVB in path x research mode x JamesDSP effects ---
    for (inPath in listOf(false, true)) for (research in listOf(false, true)) for (fx in listOf(false, true)) {
        val expected = when {
            !inPath -> Route.JDSP_ONLY            // PVB off: JamesDSP alone, as before
            research -> Route.PVB_ONLY            // blind comparison / measurement / buzz: as before
            !fx -> Route.PVB_ONLY                 // JamesDSP has nothing on: PVB alone, as before
            else -> Route.JDSP_THEN_PVB
        }
        val r = JdspChain.route(inPath, research, fx)
        check("route inPath=$inPath research=$research jdsp=$fx -> $expected", r == expected, "$r")
    }
    check("route flags: JDSP_ONLY", Route.JDSP_ONLY.jdsp && !Route.JDSP_ONLY.pvb)
    check("route flags: PVB_ONLY", !Route.PVB_ONLY.jdsp && Route.PVB_ONLY.pvb)
    check("route flags: chain (PVB last)", Route.JDSP_THEN_PVB.jdsp && Route.JDSP_THEN_PVB.pvb)

    // --- PVB settings -> in path / sealed (the real PvbSettings.load) ---
    data class Case(val enabled: Boolean, val match: Boolean, val speakerOnly: Boolean, val speaker: Boolean,
                    val inPath: Boolean, val sealed: Boolean)
    val cases = listOf(
        Case(true, true, true, true, inPath = true, sealed = true),     // on, on the speaker
        Case(true, false, true, true, inPath = true, sealed = true),
        Case(true, true, true, false, inPath = true, sealed = false),   // on, headphones: route bypass, not sealed
        Case(true, true, false, false, inPath = true, sealed = true),   // on everywhere
        Case(false, true, true, true, inPath = true, sealed = false),   // off, matched bypass: in path, not sealed
        Case(false, false, true, true, inPath = false, sealed = false), // off: JamesDSP alone
        Case(false, false, false, false, inPath = false, sealed = false),
    )
    for (c in cases) {
        val s = PvbSettings.load(ChainPrefs(mapOf(PvbSettings.KEY_ENABLE to c.enabled,
            PvbSettings.KEY_MATCH_ON_DISABLE to c.match, PvbSettings.KEY_SPEAKER_ONLY to c.speakerOnly)))
        check("settings $c", JdspChain.pvbInPath(s, false) == c.inPath && JdspChain.sealed(s, c.speaker) == c.sealed)
    }
    val off = PvbSettings.load(ChainPrefs(mapOf(PvbSettings.KEY_ENABLE to false, PvbSettings.KEY_MATCH_ON_DISABLE to false)))
    check("blind comparison keeps PVB in the path", JdspChain.pvbInPath(off, abActive = true))
    // general build before the first-run notice: nothing processes, nothing is sealed
    PvbBuild.general = true; PvbBuild.firstRunConfirmed = false
    val gated = PvbSettings.load(ChainPrefs(emptyMap()))
    check("general, first run not confirmed: not in path, not sealed", !JdspChain.pvbInPath(gated, false) && !JdspChain.sealed(gated, true))
    PvbBuild.reset()

    // --- the sealing table as implemented ---
    val expectedPolicy = mapOf(
        Module.BASS to Policy.SEALED, Module.TUBE to Policy.SEALED,
        Module.COMPRESSOR to Policy.INFO, Module.EQ to Policy.INFO, Module.PEQ to Policy.INFO, Module.GEQ to Policy.INFO,
        Module.CONVOLVER to Policy.ALLOWED, Module.DDC to Policy.ALLOWED, Module.LIVEPROG to Policy.ALLOWED,
        Module.CROSSFEED to Policy.ALLOWED, Module.STEREO_WIDE to Policy.SPATIAL, Module.REVERB to Policy.ALLOWED,
    )
    check("every module has the approved policy", Module.values().all { expectedPolicy[it] == it.policy },
        Module.values().joinToString { "${it.name}=${it.policy}" })
    for (m in Module.values()) for (enabled in listOf(false, true)) for (sealed in listOf(false, true))
        for (spatial in listOf(false, true)) {
            val expected = enabled && !(sealed && expectedPolicy[m] == Policy.SEALED) &&
                !(spatial && expectedPolicy[m] == Policy.SPATIAL)
            if (JdspChain.allowed(m, enabled, sealed, spatial) != expected)
                check("allowed $m enabled=$enabled sealed=$sealed spatial=$spatial", false)
        }
    check("allowed(): 12 modules x enabled x sealed x spatial", true)
    // one widener at a time: the stereo widener is off while PVB's spatial effect plays, and only then
    val sp = PvbSettings(enabled = true, speakerOnly = true, xtcMode = PvbSettings.XTC_CENTRE)
    check("spatial seal: on, speaker, spatial on", JdspChain.spatialSealed(sp, speaker = true))
    check("spatial seal: not on headphones", !JdspChain.spatialSealed(sp.copy(speakerOnly = false), speaker = false))
    check("spatial seal: not with spatial off", !JdspChain.spatialSealed(sp.copy(xtcMode = PvbSettings.XTC_OFF), true))
    check("spatial seal: not while PVB is off", !JdspChain.spatialSealed(sp.copy(enabled = false), true))
    check("only the widener, spatial sealed -> PVB alone", !JdspChain.hasEffects(setOf(Module.STEREO_WIDE), true, true))
    check("only the widener, spatial off -> JamesDSP runs", JdspChain.hasEffects(setOf(Module.STEREO_WIDE), true, false))

    // "JamesDSP on" for the chain: any module that still runs
    check("nothing enabled -> no effects", !JdspChain.hasEffects(emptySet(), false) && !JdspChain.hasEffects(emptySet(), true))
    check("only bass boost, sealed -> PVB alone", !JdspChain.hasEffects(setOf(Module.BASS), true))
    check("only bass boost + tube, sealed -> PVB alone", !JdspChain.hasEffects(setOf(Module.BASS, Module.TUBE), true))
    check("only bass boost, not sealed -> JamesDSP runs", JdspChain.hasEffects(setOf(Module.BASS), false))
    check("bass boost + EQ, sealed -> JamesDSP runs (EQ only)", JdspChain.hasEffects(setOf(Module.BASS, Module.EQ), true))
    for (m in Module.values().filter { it.policy != Policy.SEALED })   // the spatial seal is off here
        check("$m alone, sealed -> JamesDSP runs", JdspChain.hasEffects(setOf(m), true))

    // --- output control and the restore of the user's values ---
    val user = JdspChain.Output(thresholdDb = -3.5f, releaseMs = 120f, postGainDb = 4f)
    val userCopy = user.copy()
    val enabled = setOf(Module.BASS, Module.TUBE, Module.EQ, Module.COMPRESSOR)
    val before = sync(user, enabled, sealed = false)
    val during = sync(user, enabled, sealed = true)
    val after = sync(user, enabled, sealed = false)
    check("unsealed: the user's output control as saved", before.output == user)
    check("sealed: 0 dB post gain, neutral limiter, user release",
        during.output == JdspChain.Output(JdspChain.NEUTRAL_LIMITER_DB, 120f, 0f), "${during.output}")
    check("sealed: bass boost and analog modelling off", !during.bass && !during.tube)
    check("sealed: EQ + compressor still run", during.effects)
    check("PVB off again: every user value is sent again", after == before && after.bass && after.tube)
    check("user values never modified by sealing", user == userCopy)
    // a neutral limiter really is neutral: JamesDSP's gain = threshold / max(threshold, peak) stays exactly 1
    val thr = Math.pow(10.0, JdspChain.NEUTRAL_LIMITER_DB / 20.0).toFloat()
    check("neutral limiter: gain exactly 1 up to +23.9 dBFS", thr / maxOf(thr, 15.6f) == 1f && thr > 15.6f, "threshold $thr")
    check("sealed output is 0 dB also for a negative user post gain", JdspChain.output(user.copy(postGainDb = -12f), true).postGainDb == 0f)

    // --- 16-bit conversion: exact round trip and the same result as the PVB engine's own 16-bit path ---
    val shorts = ShortArray(65536) { (it - 32768).toShort() }
    val floats = FloatArray(65536)
    val back = ShortArray(65536)
    JdspChain.shortToFloat(shorts, floats, shorts.size)
    JdspChain.floatToShort(floats, back, floats.size)
    check("short -> float -> short is exact for all 65536 values", shorts.contentEquals(back))
    val edge = floatArrayOf(1.5f, -1.5f, 32767.4f / 32768f, 32767.6f / 32768f, -1f, 0.5f / 32768f, 1.5f / 32768f,
        -0.5f / 32768f, Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)
    val edgeOut = ShortArray(edge.size)
    JdspChain.floatToShort(edge, edgeOut, edge.size)
    check("float -> short clamps, rounds half to even, NaN -> 0",
        edgeOut.toList() == listOf<Short>(32767, -32768, 32767, 32767, -32768, 0, 2, 0, 0, 32767, -32768), edgeOut.joinToString())

    if (args.size > 1 && args[1] == "--jni") {
        // PVB_ONLY on 16-bit capture uses PvbEngine.processShort; the chain uses shortToFloat -> processFloat ->
        // floatToShort. Both must give the same samples (same scale, same rounding), so a route change keeps level.
        val sr = 48000
        val a = PvbEngine(sr)
        val b = PvbEngine(sr)
        val p = FloatArray(PvbParam.COUNT)
        // the app's defaults with virtual bass on (P1 at +6 dB), no ramps
        p[PvbParam.ENABLED] = 1f; p[PvbParam.HP_HZ] = 100f; p[PvbParam.LOW_HZ] = 220f; p[PvbParam.LOW_DB] = 3f
        p[PvbParam.LOW_Q] = 1f; p[PvbParam.HI_HZ] = 4500f; p[PvbParam.HI_DB] = -3f; p[PvbParam.HI_Q] = 0.6f
        p[PvbParam.OUT_DB] = -5f; p[PvbParam.CEIL_DB] = -1f; p[PvbParam.REL_MS] = 60f; p[PvbParam.RAMP_MS] = 0f
        p[PvbParam.DYN_REF_DB] = -30f; p[PvbParam.DYN_DOWN_RATIO] = 0.5f; p[PvbParam.DYN_UP_RATIO] = 0.19f
        p[PvbParam.DYN_UP_MAX_DB] = 2f; p[PvbParam.HS_HZ] = 2500f; p[PvbParam.VB_ON] = 1f; p[PvbParam.VB_ALGO] = 6f
        p[PvbParam.VB_LEVEL_DB] = 6f; p[PvbParam.MATCH_SEED_DB] = -6f
        a.setParams(p); b.setParams(p)
        val rnd = Random(7)
        val n = 4096 * 2
        val inS = ShortArray(n); val outA = ShortArray(n); val outB = ShortArray(n)
        val fIn = FloatArray(n); val fOut = FloatArray(n)
        var same = true
        var nonZero = 0
        for (blk in 0 until 24) {
            for (i in 0 until n) {
                val t = (blk * n + i) / 2
                val v = 0.6 * Math.sin(2 * Math.PI * 55.0 * t / sr) + 0.25 * (rnd.nextDouble() * 2 - 1)
                inS[i] = (v * 32767).toInt().coerceIn(-32768, 32767).toShort()
            }
            a.processShort(inS, outA, n)
            JdspChain.shortToFloat(inS, fIn, n)
            b.processFloat(fIn, fOut, n)
            JdspChain.floatToShort(fOut, outB, n)
            if (!outA.contentEquals(outB)) same = false
            nonZero += outA.count { it.toInt() != 0 }
        }
        check("16-bit chain conversion == PVB engine 16-bit path (bit exact, 24 blocks)", same && nonZero > 0, "nonzero $nonZero")
        a.close(); b.close()
    }

    // --- strings of the chain notes: same keys en/ko, same arguments, Android-safe text ---
    fun strings(dir: String): Map<String, String> {
        val f = File(root, "app/src/main/res/$dir/strings_general.xml")
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(f)
        val nodes = doc.getElementsByTagName("string")
        return (0 until nodes.length).map { nodes.item(it) as org.w3c.dom.Element }
            .filter { it.getAttribute("name").startsWith("pvb_jamesdsp_") }
            .associate { it.getAttribute("name") to it.textContent }
    }
    val en = strings("values")
    val ko = strings("values-ko")
    val keys = setOf("pvb_jamesdsp_chain_note", "pvb_jamesdsp_chain_research", "pvb_jamesdsp_sealed",
        "pvb_jamesdsp_output_sealed", "pvb_jamesdsp_compressor_info", "pvb_jamesdsp_eq_info",
        "pvb_jamesdsp_stereowide_spatial")
    check("chain strings: en and ko have exactly the used keys", en.keys == keys && ko.keys == keys,
        "en ${en.keys}, ko ${ko.keys}")
    val placeholder = Regex("%(\\d+\\$)?[sdf]")
    for ((key, text) in en + ko.mapKeys { "ko:" + it.key }) {
        check("no bare apostrophe in $key", Regex("(?<!\\\\)'").find(text) == null)
        if (placeholder.containsMatchIn(text))
            check("no lone % in $key", Regex("%(?!(\\d+\\$)?[sdf%])").find(text.replace("%%", "")) == null)
        check("brand placeholder only in $key", placeholder.findAll(text).all { it.value == "%1\$s" })
    }
    for (k in keys) {
        fun args(t: String?) = placeholder.findAll(t ?: "").map { it.value }.toSet()
        check("same arguments en/ko in $k", args(en[k]) == args(ko[k]))
    }
    check("approved lock note (ko)", ko["pvb_jamesdsp_sealed"]?.startsWith("%1\$s 가상 저음이 켜져 있어 잠겨 있어요") == true)
    check("approved lock note (en)", en["pvb_jamesdsp_sealed"]?.startsWith("Locked while %1\$s virtual bass is on") == true)
    check("chain note names the order (ko)", ko["pvb_jamesdsp_chain_note"]?.startsWith("JamesDSP 효과 → %1\$s 순서로 함께 적용 중") == true)
    check("old \"not applied\" note is gone", File(root, "app/src/main/res/values-ko/strings_general.xml").readText().contains("적용되지 않습니다").not())

    if (failures > 0) {
        println("JdspChain: $failures check(s) failed")
        exitProcess(1)
    }
    println("JdspChain: route table, sealing table, sealed output and restore, 16-bit conversion, strings en/ko: OK")
}

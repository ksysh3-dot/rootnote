import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File
import kotlin.math.abs

// Real pure-Kotlin settings/share/Undo actions plus the Compose wiring contract, without an Android build.
fun main(args: Array<String>) {
    var checks = 0
    fun expect(ok: Boolean, message: String) { checks++; check(ok) { message } }
    val spec = DevParams.STRENGTH
    val si = DevParams.ALL.indexOf(spec)
    val defaults = DevParams.defaults(emptyMap()).also { it[si] = 4f }
    val golden = listOf(
        "RN1-Fixture-1.0-0400-0080-5FFQ",
        "RN1-Fixture-1.0-0400-0081-5BEP",
        "RN1-Fixture-1.0-0400-0082-57DN",
        "RN1-Fixture-1.0-0400-0083-53CM",
        "RN1-Fixture-1.0-0400-0000-4D2Y",
        "RN1-Fixture-1.0-0400-0085-5VAJ",
        "RN1-Fixture-1.0-0400-0086-5Q9H",
        "RN1-Fixture-1.0-0400-0087-5K8G",
        "RN1-Fixture-1.0-0400-0088-4F7Z",
        "RN1-Fixture-1.0-0400-0089-4B6Y",
        "RN1-Fixture-1.0-0400-008A-5MT1",
        "RN1-Fixture-1.0-0400-008B-5RS2",
        "RN1-Fixture-1.0-0400-008C-5WR3"
    )
    for (v in -6..12) {
        val values = defaults.copyOf().also { it[si] = v.toFloat() }
        expect(spec.snap(v.toFloat()) == v.toFloat(), "developer grid preserves $v")
        expect(DevParams.apply(PvbSettings(), values).vbLevelDb == v.toFloat(), "apply preserves $v")
        val code = DevShareCode.encode("Fixture", "1.0", values, defaults)
        val decoded = DevShareCode.decode(code, defaults) as DevShareCode.Result.Ok
        expect(decoded.values[si] == v.toFloat(), "RN1 round trip preserves $v")
        if (v >= 0) expect(code == golden[v], "legacy positive bytes changed: $v $code")
        if (v < 0) {
            val other = defaults.copyOf().also { it[si] = 6f }
            val cross = DevShareCode.decode(code, other) as DevShareCode.Result.Ok
            expect(cross.values[si] == v.toFloat(), "negative value changed on another phone")
        }
    }
    for (v in 0..12) {
        val decoded = DevShareCode.decode(golden[v], defaults) as DevShareCode.Result.Ok
        expect(decoded.values[si] == v.toFloat(), "legacy value-set1 index changed: $v")
    }
    val negDefaults = defaults.copyOf().also { it[si] = -6f }
    val zero = negDefaults.copyOf().also { it[si] = 0f }
    val zeroCode = DevShareCode.encode("Fixture", "1.0", zero, negDefaults)
    expect((DevShareCode.decode(zeroCode, defaults) as DevShareCode.Result.Ok).values[si] == 0f,
           "0 dB must be explicitly stored when default is negative")
    // The production Undo writeAll callback uses this exact writer.
    val undo = defaults.copyOf().also { it[si] = -5f }
    val stored = mutableMapOf<String, Float>()
    DevParams.write(undo, { k, v -> stored[k] = v }, { _, _ -> })
    expect(stored[PvbSettings.KEY_VB_STRENGTH_DB] == -5f, "Undo writer raises negative strength")
    expect(DevParams.clampStored(PvbSettings.KEY_VB_STRENGTH_DB, -6f) == -6f, "stored negative clamped upward")
    for (v in -6..1) expect(DevParams.lowerStrength(v.toFloat()) == maxOf(-6, v-2).toFloat(), "lower2 $v")
    expect(HomeLogic.sliderValue(-6f, SafeCaps.GENERAL) == -6, "home floor")
    expect(HomeLogic.sliderMax(SafeCaps.GENERAL) == 9, "home cap")
    val root = File(args[0])
    val home = File(root, "app/src/general/java/me/timschneeberger/rootlessjamesdsp/home/HomeScreen.kt").readText()
    val dev = File(root, "app/src/general/java/me/timschneeberger/rootlessjamesdsp/devmode/DevModeActivity.kt").readText()
    expect(home.contains("min = PvbSettings.VB_LEVEL_MIN.toInt()"), "strength slider missing negative minimum")
    expect(home.contains("range = min.toFloat()..max.toFloat()"), "slider track ignores minimum")
    expect(home.contains("(state.level - 1).coerceAtLeast(PvbSettings.VB_LEVEL_MIN.toInt())"), "limiter suggestion raises negative level")
    expect(dev.contains("write(DevParams.STRENGTH, DevParams.lowerStrength(cur))"), "lower2 UI ignores common floor")
    expect(dev.contains("DevParams.write(values,"), "Undo does not use the tested writer")

    // Closed-form binomial tails: tiny exact values, overflow boundary, and large-session limits.
    val sign = LiveAbTally
    expect(sign.signTestP(0, 0) == 1.0, "empty sign test")
    for (n in 1..20) for (k in 0..n) {
        val m = minOf(k, n-k)
        var c = 1.0; var tail = 1.0
        for (i in 1..m) { c *= (n-i+1).toDouble()/i; tail += c }
        val expected = minOf(1.0, 2.0*tail/Math.pow(2.0,n.toDouble()))
        expect(abs(sign.signTestP(k,n)-expected)<1e-12, "small exact sign test $k/$n")
    }
    for (n in listOf(1024, 1025, 1030, 10000, 100000)) {
        for (k in listOf(0,1,n/4,n/2,n/2-1,n-1,n)) {
            val p = sign.signTestP(k,n)
            expect(p.isFinite() && p in 0.0..1.0, "large sign test nonfinite/out of bounds $k/$n")
            expect(abs(p-sign.signTestP(n-k,n))<1e-12, "sign symmetry")
        }
        expect(sign.signTestP(n/2,n)==1.0, "balanced sign test")
    }
    expect(abs(sign.signTestP(0,1024)-Math.scalb(1.0,-1023))<1e-320, "extreme n1024 exact")
    expect(abs(sign.signTestP(4999,10000)-0.9920213538606178)<1e-8, "large central tail")
    println("NegativeStrengthTest: PASS $checks checks")
}

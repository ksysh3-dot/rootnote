package me.timschneeberger.rootlessjamesdsp.pvb

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** cbc393b fixtures were produced by compiling that revision's unmodified app sources with this driver. */
object StrengthRegressionStates {
    fun digest(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    fun bytes(params: FloatArray): ByteArray = ByteBuffer.allocate(params.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        .apply { params.forEach { putInt(it.toRawBits()) } }.array()

    fun states(): List<Pair<String, PvbSettings>> = listOf(false, true).flatMap { general ->
        listOf(-6f, -3f, 0f, 4f, 9f, 12f).flatMapIndexed { index, level ->
            listOf(false, true).map { fixed ->
                "${if (general) "general" else "s26u"}:$level:$fixed" to PvbSettings(
                    enabled = index != 0, vbOn = true, vbLevelDb = level, p1ppp = fixed,
                    vbVolLink = index % 2 == 1, devOn = general && index == 5,
                    outDb = if (general) -3f else -5f, xtcMode = if (index % 2 == 0) 1 else 0,
                )
            }
        }
    }

    fun inputs(s: PvbSettings, index: Int) = PvbEngineParams.Inputs(
        rampMs = 30f, speaker = index % 5 != 0, upright = index % 3 == 0, rotation = 1,
        volumeIndex = 100, volumeMax = 150, lowDb = s.lowDb, matchSeedDb = -2f,
        diagnosticSolo = index == 3, abActive = index == 7, abHidden = index == 7, abTag = 2,
        gateDb = 0f, measuring = index == 9, devMeter = false, sampleRate = if (index % 4 == 0) 44100 else 48000,
    )

    fun snapshot(): String = states().mapIndexed { index, (key, raw) ->
        PvbBuild.reset(); PvbBuild.general = key.startsWith("general"); PvbBuild.firstRunConfirmed = true
        val caps = PvbBuild.caps
        val s = PvbBuild.finish(raw)
        val defaults = DevParams.defaults(emptyMap())
        val code = DevShareCode.encode("Fixture", "1.0", DevParams.read(s), defaults)
        listOf(key, HomeLogic.sliderValue(s.vbLevelDb, caps), HomeLogic.sliderMax(caps),
            HomeLogic.levelLabel(s.vbLevelDb.toInt()), HomeLogic.presetWrite(HomeLogic.Chip.FULLNESS, caps),
            digest(SettingsSummary.text(s, "Fixture", "1.0", code).toByteArray()), code,
            digest(bytes(PvbEngineParams.encode(s, inputs(s, index)).params))).joinToString("\t")
    }.joinToString("\n", postfix = "\n").also { PvbBuild.reset() }
}

/** Host driver also permits a direct cmp of all raw engine packets before/after the UI edit. */
fun main(args: Array<String>) {
    java.io.File(args[0]).writeText(StrengthRegressionStates.snapshot())
    val packets = StrengthRegressionStates.states().mapIndexed { i, (key, raw) ->
        PvbBuild.reset(); PvbBuild.general = key.startsWith("general"); PvbBuild.firstRunConfirmed = true
        val s = PvbBuild.finish(raw)
        StrengthRegressionStates.bytes(PvbEngineParams.encode(s, StrengthRegressionStates.inputs(s, i)).params)
    }.fold(ByteArray(0)) { a, b -> a + b }
    java.io.File(args[1]).writeBytes(packets)
    PvbBuild.reset()
}

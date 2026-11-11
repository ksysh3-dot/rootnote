package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.SharedPreferences
import java.lang.reflect.Proxy
import org.junit.After
import org.junit.Assert.*
import org.junit.Test

class StrengthDisplayTest {
    @After fun reset() = PvbBuild.reset()

    @Test fun roundTripAndShiftedEndpoints() {
        for (offset in listOf(0, 3, -2)) {
            val scale = StrengthDisplay(offset)
            assertEquals((-6 + offset).toFloat(), scale.range(-6f, 12f).start, 0f)
            assertEquals((12 + offset).toFloat(), scale.range(-6f, 12f).endInclusive, 0f)
            for (q in -24..48) {
                val actual = q / 4f
                assertEquals(actual + offset, scale.toDisplay(actual), 0f)
                assertEquals(actual, scale.toActual(scale.toDisplay(actual)), 0f)
            }
            assertEquals(-6f, scale.toActual(-100f), 0f)
            assertEquals(12f, scale.toActual(100f), 0f)
            assertEquals((-6 + offset).toFloat(), scale.sliderValue(-100f), 0f)
            assertEquals((12 + offset).toFloat(), scale.sliderValue(100f), 0f)
            assertEquals(9f, scale.toActual(100f, SafeCaps.GENERAL.vbLevelMax), 0f)
            assertEquals((9 + offset).toFloat(), scale.sliderValue(12f, SafeCaps.GENERAL.vbLevelMax), 0f)
            // Volume link and the silent/reference side can be below the UI floor. Display must not raise them.
            assertEquals(-12f + offset, scale.toDisplay(-12f), 0f)
            assertEquals(-120f + offset, scale.toDisplay(PvbSettings.VB_LEVEL_OFF), 0f)
        }
    }

    @Test fun nonFiniteFallsBackToActualDefault() {
        for (offset in listOf(0, 3, -2)) for (bad in listOf(Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY)) {
            val scale = StrengthDisplay(offset)
            assertEquals(4f, scale.toActual(bad), 0f)
            assertEquals(4f + offset, scale.toDisplay(bad), 0f)
            assertEquals(4f + offset, scale.sliderValue(bad), 0f)
        }
    }

    @Test fun migrationKeepsExistingActualValuesAndIsIdempotent() {
        // No historical storage path used shifted display coordinates. Schema 4 already migrates actual list values.
        for (general in listOf(false, true)) for (level in -6..12) {
            PvbBuild.general = general; PvbBuild.firstRunConfirmed = true
            val p = MemoryPrefs(mapOf(PvbSettings.KEY_VB_LEVEL_DB to level.toString(), PvbSettings.KEY_P1PPP to true))
            PvbSettings.migrateVirtualBassModel(p.proxy)
            assertEquals(level.toFloat(), p.values[PvbSettings.KEY_VB_STRENGTH_DB])
            assertEquals(PvbSettings.VB_MODEL_SCHEMA, p.values[PvbSettings.KEY_VB_MODEL_SCHEMA])
            val writes = p.writes
            PvbSettings.migrateVirtualBassModel(p.proxy)
            assertEquals(writes, p.writes)
            assertTrue(PvbSettings.load(p.proxy).p1ppp)
            for (offset in listOf(0, 3, -2)) {
                val scale = StrengthDisplay(offset)
                val stored = p.values[PvbSettings.KEY_VB_STRENGTH_DB] as Float
                assertEquals(stored, scale.toActual(scale.toDisplay(stored)), 0f)
                assertEquals(level.toFloat(), p.values[PvbSettings.KEY_VB_STRENGTH_DB])
            }
            // A restored/current strength wins over a conflicting legacy list, including negative strength.
            p.values[PvbSettings.KEY_VB_LEVEL_DB] = "12"
            PvbSettings.migrateVirtualBassModel(p.proxy)
            assertEquals(level.toFloat(), p.values[PvbSettings.KEY_VB_STRENGTH_DB])
        }
    }

    @Test fun presetsAndShareCodeAlwaysCarryActualDb() {
        val spec = DevParams.STRENGTH
        val si = DevParams.ALL.indexOf(spec)
        val defaults = DevParams.defaults(emptyMap())
        for (general in listOf(false, true)) {
            PvbBuild.general = general
            val caps = PvbBuild.caps
            val preset = HomeLogic.presetWrite(HomeLogic.Chip.FULLNESS, caps)!!
            assertEquals(4f, preset.second, 0f)
            for (offset in listOf(0, 3, -2)) {
                val scale = StrengthDisplay(offset)
                assertEquals(4f + offset, scale.toDisplay(preset.second), 0f)
                assertEquals(HomeLogic.Chip.FULLNESS, HomeLogic.selectedChip(preset.first, preset.second))
                for (actual in -6..12) {
                    val v = defaults.copyOf().also { it[si] = scale.toActual(scale.toDisplay(actual.toFloat())) }
                    val code = DevShareCode.encode("Fixture", "1.0", v, defaults)
                    val canonical = defaults.copyOf().also { it[si] = actual.toFloat() }
                    assertEquals(DevShareCode.encode("Fixture", "1.0", canonical, defaults), code)
                    val decoded = DevShareCode.decode(code, defaults) as DevShareCode.Result.Ok
                    assertEquals(actual.toFloat(), decoded.values[si], 0f)
                    assertEquals(actual.toFloat() + offset, scale.toDisplay(decoded.values[si]), 0f)
                    val saved = mutableMapOf<String, Float>()
                    DevParams.write(decoded.values, { k, value -> saved[k] = value }, { _, _ -> })
                    assertEquals(actual.toFloat(), saved[PvbSettings.KEY_VB_STRENGTH_DB])
                }
            }
        }
    }

    @Test fun productionBoundariesKeepActualUnits() {
        val offset = StrengthDisplay.STRENGTH_DISPLAY_OFFSET_DB
        for (actual in -6..12) {
            val s = PvbSettings(vbLevelDb = actual.toFloat())
            val shown = actual + offset
            assertEquals(shown.toFloat(), DevParams.STRENGTH.displayValue(actual.toFloat()), 0f)
            assertEquals(actual.toFloat(), DevParams.STRENGTH.actualValue(shown.toFloat()), 0f)
            assertEquals(if (shown < 0) "$shown" else "+$shown", HomeLogic.levelLabel(actual))
            val label = LiveAbComparisons.P1.label(s)
            assertEquals("P1 ${LiveAbComparisons.dbText(shown.toFloat())}", label)
            assertEquals("P1 ${LiveAbComparisons.dbText(actual.toFloat())}", LiveAbComparisons.P1.actualLabel(s))
            val cmp = LiveAbComparisons.ALL.first()
            assertEquals(LiveAbComparisons.P1.actualLabel(s), cmp.condition(LiveAbComparisons.P1, s).label)
            assertEquals(actual.toFloat(), LiveAbComparisons.P1.apply(s).vbLevelDb, 0f)
            assertEquals(0f, DevParams.H2.displayValue(0f), 0f) // differences/harmonic offsets are not strength
        }
    }

    @Test fun offsetZeroMatchesCbc393bUiCodesAndAllEnginePacketBytes() {
        org.junit.Assume.assumeTrue(StrengthDisplay.STRENGTH_DISPLAY_OFFSET_DB == 0)
        val golden = javaClass.getResource("/cbc393b-strength.tsv")!!.readText()
        assertEquals(golden, StrengthRegressionStates.snapshot())
        for ((_, s) in StrengthRegressionStates.states()) {
            assertEquals(s.vbLevelDb, StrengthDisplay.UI.toDisplay(s.vbLevelDb), 0f)
            assertEquals(s.vbLevelDb, StrengthDisplay.UI.toActual(s.vbLevelDb), 0f)
        }
    }

    @Test fun stableModeMigrationAndFixedStrength() {
        PvbBuild.general = false
        val legacy = MemoryPrefs(mapOf(PvbSettings.KEY_P1PPP to true))
        PvbSettings.migrateVirtualBassModel(legacy.proxy)
        assertEquals("strong", PvbSettings.load(legacy.proxy).bassMode)
        for (mode in listOf("off", "strong", "stable")) {
            val prefs = MemoryPrefs(mapOf(PvbSettings.KEY_BASS_MODE to mode,
                PvbSettings.KEY_P1PPP to true, PvbSettings.KEY_VB_STRENGTH_DB to 9f))
            val settings = PvbSettings.load(prefs.proxy)
            assertEquals(mode, settings.bassMode)
            assertEquals(mode != "off", settings.fixedBass)
            assertEquals(mode == "stable", settings.stable)
            assertEquals(9f, settings.vbLevelDb, 0f)
        }
    }

    /** Dynamic proxy works against Android's interface and the repository's host-only interface. */
    private class MemoryPrefs(initial: Map<String, Any>) {
        val values = initial.toMutableMap()
        var writes = 0
        private val staged = mutableMapOf<String, Any?>()
        private val editor: SharedPreferences.Editor = Proxy.newProxyInstance(
            SharedPreferences.Editor::class.java.classLoader, arrayOf(SharedPreferences.Editor::class.java),
        ) { proxy, method, args ->
            when {
                method.name.startsWith("put") -> { staged[args!![0] as String] = args[1]; proxy }
                method.name == "remove" -> { staged[args!![0] as String] = null; proxy }
                method.name == "apply" || method.name == "commit" -> {
                    staged.forEach { (k, v) -> if (v == null) values.remove(k) else values[k] = v }
                    staged.clear(); writes++; if (method.name == "commit") true else null
                }
                else -> error(method.name)
            }
        } as SharedPreferences.Editor
        val proxy: SharedPreferences = Proxy.newProxyInstance(
            SharedPreferences::class.java.classLoader, arrayOf(SharedPreferences::class.java),
        ) { _, method, args ->
            when (method.name) {
                "getAll" -> values.toMap()
                "edit" -> editor
                "getString" -> if (values.containsKey(args!![0])) values[args[0]] as String? else args[1]
                "getFloat" -> if (values.containsKey(args!![0])) values[args[0]] as Float else args[1]
                "getBoolean" -> if (values.containsKey(args!![0])) values[args[0]] as Boolean else args[1]
                "getInt" -> if (values.containsKey(args!![0])) values[args[0]] as Int else args[1]
                else -> error(method.name)
            }
        } as SharedPreferences
    }
}

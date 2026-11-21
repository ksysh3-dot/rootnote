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
            assertTrue(PvbSettings.load(p.proxy).combo)
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

    @Test fun offsetZeroMatchesStrengthDisplayFixture() {
        org.junit.Assume.assumeTrue(StrengthDisplay.STRENGTH_DISPLAY_OFFSET_DB == 0)
        val golden = javaClass.getResource("/strength-display.tsv")!!.readText().replace("\r\n", "\n")
        assertEquals(golden, StrengthRegressionStates.snapshot())
        for ((_, s) in StrengthRegressionStates.states()) {
            assertEquals(s.vbLevelDb, StrengthDisplay.UI.toDisplay(s.vbLevelDb), 0f)
            assertEquals(s.vbLevelDb, StrengthDisplay.UI.toActual(s.vbLevelDb), 0f)
        }
    }

    @Test fun retiredModesMigrateToComboAndOffStaysOff() {
        for (general in listOf(false, true)) {
            PvbBuild.general = general; PvbBuild.firstRunConfirmed = true
            for (on in listOf(false, true)) {
                val old = MemoryPrefs(mapOf(PvbSettings.KEY_VB_ON to on, PvbSettings.KEY_VB_ALGO to "alpha2_p1"))
                PvbSettings.migrateVirtualBassModel(old.proxy)
                val restored = PvbSettings.load(old.proxy)
                assertEquals(on, restored.combo)
                assertEquals(on, restored.vbOn)
            }
            val unlocked = MemoryPrefs(mapOf(PvbSettings.KEY_BASS_MODE to "conducted",
                PvbSettings.KEY_FIXED_EQ_OPEN to "conducted", PvbSettings.KEY_VB_ON to true))
            PvbSettings.migrateVirtualBassModel(unlocked.proxy)
            assertTrue(PvbSettings.load(unlocked.proxy).fixedEqOpen)
            assertEquals("combo", unlocked.values[PvbSettings.KEY_FIXED_EQ_OPEN])
            val legacy = MemoryPrefs(mapOf(PvbSettings.KEY_P1PPP to true))
            PvbSettings.migrateVirtualBassModel(legacy.proxy)
            assertEquals("combo", PvbSettings.load(legacy.proxy).bassMode)
            for (mode in listOf("off", "strong", "separated", "stable", "epoch6", "conducted")) {
                val prefs = MemoryPrefs(mapOf(PvbSettings.KEY_BASS_MODE to mode,
                    PvbSettings.KEY_P1PPP to true, PvbSettings.KEY_VB_STRENGTH_DB to 9f,
                    PvbSettings.KEY_FIXED_LEVEL_DB to -3f, PvbSettings.KEY_VB_ON to false))
                val expected = if (mode == "off") "off" else "combo"
                assertEquals(expected, PvbSettings.load(prefs.proxy).bassMode)
                PvbSettings.migrateVirtualBassModel(prefs.proxy)
                val settings = PvbSettings.load(prefs.proxy)
                assertEquals(expected, settings.bassMode)
                assertEquals(expected, prefs.values[PvbSettings.KEY_BASS_MODE])
                assertEquals(mode != "off", settings.fixedBass)
                assertFalse(settings.p1ppp)
                assertEquals(mode != "off", settings.vbOn)
                assertEquals(9f, settings.vbLevelDb, 0f)
                assertEquals(-3f, settings.fixedLevelDb, 0f)
                val writes = prefs.writes
                PvbSettings.migrateVirtualBassModel(prefs.proxy)
                assertEquals(writes, prefs.writes)
            }
        }
    }

    @Test fun explicitBassModeWinsOnReadAndRepairsOnlyOnce() {
        for (on in listOf(false, true)) for (combo in listOf(false, true)) {
            val mode = if (combo) "combo" else "off"
            val p = MemoryPrefs(mapOf(PvbSettings.KEY_VB_ON to on, PvbSettings.KEY_BASS_MODE to mode))
            repeat(2) {
                val s = PvbSettings.load(p.proxy)
                assertEquals(combo, s.vbOn)
                assertEquals(combo, s.combo)
                assertEquals(combo, p.values[PvbSettings.KEY_VB_ON])
                assertEquals(mode, p.values[PvbSettings.KEY_BASS_MODE])
            }
            assertEquals(if (on == combo) 0 else 1, p.writes)
        }
    }

    @Test fun settingsHomeAndWelcomeStoreTheSameBassSelection() {
        PvbBuild.general = true
        val settings = MemoryPrefs(emptyMap())
        var confirm: (() -> Unit)? = null
        PvbSettings.selectBass(settings.proxy, true) { confirm = it }
        assertNotNull(confirm)
        assertEquals(0, settings.writes) // cancel or back performs no write
        confirm!!.invoke()
        assertEquals(true, settings.values[PvbSettings.KEY_VB_ON])
        assertEquals("combo", settings.values[PvbSettings.KEY_BASS_MODE])
        PvbBuild.firstRunConfirmed = true
        val home = MemoryPrefs(emptyMap())
        for (on in listOf(false, true, false)) {
            PvbSettings.selectBass(settings.proxy, on) { fail("already confirmed") }
            PvbSettings.setHomePower(home.proxy, on)
            for (p in listOf(settings, home)) {
                assertEquals(on, p.values[PvbSettings.KEY_VB_ON])
                assertEquals(if (on) "combo" else "off", p.values[PvbSettings.KEY_BASS_MODE])
            }
            assertEquals(on, home.values[PvbSettings.KEY_ENABLE])
        }
        val welcome = FirstRun.valuesOnConfirm()
        assertEquals(true, welcome[PvbSettings.KEY_ENABLE])
        assertEquals(true, welcome[PvbSettings.KEY_VB_ON])
        assertEquals("combo", welcome[PvbSettings.KEY_BASS_MODE])
    }

    @Test fun switchAndComboAreBothRequiredByTheEngine() {
        for (on in listOf(false, true)) for (combo in listOf(false, true)) {
            val s = PvbSettings(enabled = true, vbOn = on, combo = combo)
            val input = StrengthRegressionStates.inputs(s, 1).copy(sampleRate = 48000)
            assertEquals(if (on && combo) 1f else 0f, PvbEngineParams.encode(s, input).params[PvbParam.VB_ON], 0f)
        }
    }

    @Test fun bassFitRestoresOnlyItsChangesIncludingAbsentKeys() {
        val flags = MemoryPrefs(emptyMap()).proxy
        val hp = PvbSettings.KEY_HP_HZ
        val level = PvbSettings.KEY_FIXED_LEVEL_DB
        val unrelated = PvbSettings.KEY_LOW_DB
        val original = mapOf(hp to 137f, level to -5.25f, unrelated to 1.25f,
            DevParams.KEY_DEV_ON to false, BassFitStore.RECORD to "earlier", BassFitStore.FLOOR to 148.5f)
        val result = BassFitSession(41L, -5.25, FitScope.BREAKUP).result.copy(strengthDb = -3.0)
        for (initial in listOf(original, emptyMap(), mapOf(hp to 137f))) {
            for (changeFloor in listOf(false, true)) {
                val prefs = MemoryPrefs(initial)
                val settings = PvbSettings(hpHz = initial[hp] as? Float ?: 100f,
                    fixedLevelDb = initial[level] as? Float ?: 0f)
                val fit = if (changeFloor) result.copy(floor = BassFitMapping.fromFloor(200.0)) else result
                BassFitStore.save(prefs.proxy, flags, BassFitStore.changes(settings, fit), "this run", fit.floor?.speakerFloorHz?.toFloat())
                assertEquals(-3f, prefs.values[level])
                if (changeFloor) {
                    assertEquals(135f, prefs.values[hp])
                    assertEquals(true, prefs.values[DevParams.KEY_DEV_ON])
                } else {
                    assertEquals(initial[hp], prefs.values[hp])
                    assertEquals(initial[DevParams.KEY_DEV_ON], prefs.values[DevParams.KEY_DEV_ON])
                }
                assertTrue(BassFitStore.canRestore(prefs.proxy, flags))
                BassFitStore.restore(prefs.proxy, flags)
                assertEquals(initial, prefs.values)
            }
        }
        val prefs = MemoryPrefs(original)
        BassFitStore.save(prefs.proxy, flags, BassFitStore.changes(PvbSettings(hpHz = 137f, fixedLevelDb = -5.25f), result), "one", null)
        prefs.values[unrelated] = 2.25f
        BassFitStore.restore(prefs.proxy, flags)
        assertEquals(original + (unrelated to 2.25f), prefs.values)
    }

    @Test fun legacyUndoIsReplacedByOneNewUndo() {
        val level = PvbSettings.KEY_FIXED_LEVEL_DB
        val legacy = mapOf("bass_fit_before" to "100", "fit_before_fixed_level" to -9f,
            BassFitStore.RECORD to "old", BassFitStore.FLOOR to 141f)
        for (saveCount in 0..2) {
            val flags = MemoryPrefs(legacy)
            val prefs = MemoryPrefs(mapOf(level to -6f))
            assertTrue(BassFitStore.canRestore(prefs.proxy, flags.proxy))
            if (saveCount >= 1) {
                BassFitStore.save(prefs.proxy, flags.proxy, mapOf(level to -3f), "A", null)
                assertEquals(1, prefs.writes)
                assertEquals(141f, prefs.values[BassFitStore.FLOOR])
            }
            if (saveCount == 2) BassFitStore.save(prefs.proxy, flags.proxy, mapOf(level to 0f), "B", 190f)
            BassFitStore.restore(prefs.proxy, flags.proxy)
            assertEquals(listOf(-9f, -6f, -3f)[saveCount], prefs.values[level])
            assertEquals(listOf(null, "old", "A")[saveCount], prefs.values[BassFitStore.RECORD])
            assertEquals(if (saveCount == 0) null else 141f, prefs.values[BassFitStore.FLOOR])
            assertFalse(BassFitStore.canRestore(prefs.proxy, flags.proxy))
            val restored = prefs.values.toMap()
            BassFitStore.restore(prefs.proxy, flags.proxy)
            assertEquals(restored, prefs.values)
        }
    }

    @Test fun strengthOnlyPreviewMatchesSavedUnlockedFilter() {
        PvbBuild.general = true
        PvbBuild.firstRunConfirmed = true
        val prefs = MemoryPrefs(mapOf(PvbSettings.KEY_HP_HZ to 137f, PvbSettings.KEY_BASS_MODE to "combo",
            PvbSettings.KEY_FIXED_EQ_OPEN to "combo", PvbSettings.KEY_VB_ON to true,
            PvbSettings.KEY_FIXED_LEVEL_DB to -5.25f))
        val initial = PvbSettings.load(prefs.proxy)
        assertTrue(initial.fixedEqOpen)
        val result = BassFitSession(41L, -5.25, FitScope.BREAKUP).result.copy(strengthDb = -3.0)
        val changes = BassFitStore.changes(initial, result)
        assertEquals(mapOf(PvbSettings.KEY_FIXED_LEVEL_DB to -3f), changes)
        val preview = BassFitStore.preview(initial, changes)
        BassFitStore.save(prefs.proxy, MemoryPrefs(emptyMap()).proxy, changes, "fit", null)
        assertEquals(initial.copy(fixedLevelDb = -3f), preview)
        assertEquals(137f, preview.hpHz, 0f)
        val saved = PvbSettings.load(prefs.proxy)
        assertEquals(preview, saved)
        val inputs = StrengthRegressionStates.inputs(initial, 1).copy(sampleRate = 48000)
        for (settings in listOf(preview, saved)) {
            val packet = PvbEngineParams.encode(settings, inputs).params
            assertEquals(137f, packet[PvbParam.HP_HZ], 0f)
            assertEquals(-3f, packet[PvbParam.VB_LEVEL_DB], 0f)
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
                "contains" -> values.containsKey(args!![0])
                "getStringSet" -> values[args!![0]] ?: args[1]
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

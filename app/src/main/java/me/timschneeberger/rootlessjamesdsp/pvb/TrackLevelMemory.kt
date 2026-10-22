package me.timschneeberger.rootlessjamesdsp.pvb

import java.text.Normalizer
import java.util.Locale

/*
 * Alpha 3.1: per-song virtual bass level memory, the pure part (no Android types; host JVM tested in
 * tools/pvb-harness/jvm/TrackLevelMemoryTest.kt). The Android side is TrackLevels (state, persistence) and
 * TrackLevelWatcher (media sessions).
 */

/** What a media session reports about its current item. Album is kept for display only, never part of the key. */
data class TrackInfo(
    val packageName: String,
    val artist: String?,
    val title: String?,
    val album: String? = null,
)

/** One player as seen at a moment: its item and whether it plays (or is paused). */
data class PlayerSnapshot(val track: TrackInfo?, val playing: Boolean, val paused: Boolean)

object TrackKeys {
    private const val SEP = '\u001F'
    // Unicode spaces (NBSP, U+3000 ...) and control characters count as whitespace; the separator is a control char,
    // so it can never survive inside a part.
    private val SPACES = Regex("[\\s\\p{Z}\\p{Cntrl}]+")

    /** NFC, trim, lowercase, any run of whitespace -> one space. Null -> "". */
    fun normalize(s: String?): String {
        if (s == null) return ""
        val nfc = Normalizer.normalize(s, Normalizer.Form.NFC)
        return nfc.replace(SPACES, " ").trim().lowercase(Locale.ROOT)
    }

    /** Stable key from (package, artist, title). No title (or no package) -> no key. */
    fun of(t: TrackInfo?): String? {
        if (t == null) return null
        val title = normalize(t.title)
        val pkg = normalize(t.packageName)
        if (title.isEmpty() || pkg.isEmpty()) return null
        return "$pkg$SEP${normalize(t.artist)}$SEP$title"
    }

    /**
     * The track the memory follows: the first playing player with a keyed item (session order = system priority);
     * otherwise the previous track while its player is only paused (pausing does not switch back to the default);
     * otherwise none.
     */
    fun select(players: List<PlayerSnapshot>, previousKey: String?): TrackInfo? {
        players.firstOrNull { it.playing && of(it.track) != null }?.let { return it.track }
        if (previousKey != null) players.firstOrNull { it.paused && of(it.track) == previousKey }?.let { return it.track }
        return null
    }
}

/** A virtual bass setting: the slider level and the model (the "mode" is derived from these two). */
data class VbLevel(val levelDb: Float, val modelKey: String) {
    companion object {
        /** Same normalisation PvbSettings.load applies, so a value written and read back compares equal. */
        fun of(levelDb: Float, modelKey: String?): VbLevel =
            VbLevel(PvbSettings.clampLevel(levelDb), PvbModels.fromKey(modelKey).key)
    }
}

data class TrackLevelEntry(
    val key: String,
    val packageName: String,
    val artist: String,
    val title: String,
    val levelDb: Float,
    val modelKey: String?,
    val lastUsed: Long,
)

/** Key -> saved setting, at most [capacity] entries; the least recently used one goes first. */
class TrackLevelStore(val capacity: Int = DEFAULT_CAPACITY) {
    private val map = LinkedHashMap<String, TrackLevelEntry>()

    val size: Int get() = map.size
    fun get(key: String): TrackLevelEntry? = map[key]

    fun put(entry: TrackLevelEntry) {
        map[entry.key] = entry
        trim(protect = entry.key)
    }

    fun touch(key: String, now: Long) {
        val e = map[key] ?: return
        if (now > e.lastUsed) map[key] = e.copy(lastUsed = now)
    }

    fun remove(key: String): Boolean = map.remove(key) != null
    fun clear() = map.clear()

    /** Most recently used first. */
    fun entries(): List<TrackLevelEntry> = map.values.sortedByDescending { it.lastUsed }

    private fun trim(protect: String?) {
        while (map.size > capacity.coerceAtLeast(1)) {
            val oldest = map.values.filter { it.key != protect }.minByOrNull { it.lastUsed } ?: return
            map.remove(oldest.key)
        }
    }

    /** One line per entry, tab separated, escaped; a header line carries the format version. */
    fun encode(): String = buildString {
        append(HEADER)
        for (e in map.values) {
            append('\n')
            append(listOf(e.key, e.packageName, e.artist, e.title, e.levelDb.toString(), e.modelKey ?: "",
                e.lastUsed.toString()).joinToString("\t") { escape(it) })
        }
    }

    companion object {
        const val DEFAULT_CAPACITY = 500
        private const val HEADER = "pvb-track-levels 1"

        /** Damaged lines are skipped; an unknown header gives an empty store. Never throws. */
        fun decode(text: String?, capacity: Int = DEFAULT_CAPACITY): TrackLevelStore {
            val store = TrackLevelStore(capacity)
            if (text.isNullOrEmpty()) return store
            val lines = text.split('\n')
            if (lines.first() != HEADER) return store
            for (line in lines.drop(1)) {
                val f = line.split('\t').map { unescape(it) }
                if (f.size != 7) continue
                val level = f[4].toFloatOrNull()?.takeIf { it.isFinite() } ?: continue
                val used = f[6].toLongOrNull() ?: continue
                if (f[0].isEmpty()) continue
                store.map[f[0]] = TrackLevelEntry(f[0], f[1], f[2], f[3], level, f[5].ifEmpty { null }, used)
            }
            store.trim(protect = null)
            return store
        }

        private fun escape(s: String): String = buildString {
            for (c in s) when (c) {
                '\\' -> append("\\\\")
                '\t' -> append("\\t")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                else -> append(c)
            }
        }

        private fun unescape(s: String): String {
            if ('\\' !in s) return s
            val out = StringBuilder(s.length)
            var i = 0
            while (i < s.length) {
                val c = s[i]
                if (c == '\\' && i + 1 < s.length) {
                    when (s[i + 1]) {
                        't' -> out.append('\t')
                        'n' -> out.append('\n')
                        'r' -> out.append('\r')
                        else -> out.append(s[i + 1])
                    }
                    i += 2
                } else {
                    out.append(c); i++
                }
            }
            return out.toString()
        }
    }
}

/**
 * Decides what the virtual bass setting should be. The engine-facing value ("applied") lives in the normal
 * PVB settings (slider + model); this class only says what to write there and what to remember.
 *
 * - Memory off: nothing is saved or recalled; every change is the global default.
 * - Memory on, a keyed track: a user change is saved for that track; a track with an entry gets its saved
 *   setting, a track without one gets the default.
 * - Memory on, no track: a user change is the new default.
 * - A value equal to what this class last asked for is its own write coming back, not a user change.
 *
 * Methods that return a [VbLevel] return the setting to write, or null when nothing needs to change.
 * Not thread safe: the app calls it on the main thread only.
 */
class TrackLevelPolicy(
    val store: TrackLevelStore,
    default: VbLevel,
    enabled: Boolean,
    /** Persisted: a remembered value was in effect when the state was last saved. */
    overrideActive: Boolean,
    /** What the settings hold right now. */
    current: VbLevel,
) {
    var default: VbLevel = default
        private set
    var enabled: Boolean = enabled
        private set
    var track: TrackInfo? = null
        private set
    var trackKey: String? = null
        private set
    /** True while the current track's remembered setting is in effect. */
    var usingSaved: Boolean = false
        private set
    /** Bumped whenever something that is persisted (store, default, usingSaved) changes. */
    var revision: Long = 0
        private set

    private var applied: VbLevel = current
    private var startupRestore: VbLevel? = null

    init {
        // Not in a remembered track: whatever is set now is the default. Otherwise the process ended inside a
        // remembered track (no track is known yet): go back to the default once.
        if (!overrideActive) {
            if (this.default != current) revision++
            this.default = current
        } else {
            startupRestore = push(this.default)
            revision++
        }
    }

    /** The write needed once after loading (see init), or null. */
    fun takeStartupRestore(): VbLevel? = startupRestore.also { startupRestore = null }

    fun onPlayers(players: List<PlayerSnapshot>, now: Long): VbLevel? = onTrack(TrackKeys.select(players, trackKey), now)

    fun onTrack(t: TrackInfo?, now: Long): VbLevel? {
        if (!enabled) return null
        val key = TrackKeys.of(t)
        if (key == trackKey) {
            if (key != null) track = t    // e.g. album filled in later: display only
            return null
        }
        trackKey = key
        track = if (key != null) t else null
        return recall(now)
    }

    /** The slider, the mode or the model list changed (or our own write came back). Returns true if remembered. */
    fun onSettingsChanged(observed: VbLevel, now: Long): Boolean {
        if (observed == applied) return false
        applied = observed
        val key = trackKey
        val t = track
        if (enabled && key != null && t != null) {
            store.put(TrackLevelEntry(key, t.packageName, t.artist?.trim().orEmpty(), t.title?.trim().orEmpty(),
                observed.levelDb, observed.modelKey, now))
            usingSaved = true
            revision++
            return true
        }
        if (default != observed) {
            default = observed
            revision++
        }
        return false
    }

    fun setEnabled(on: Boolean, now: Long): VbLevel? {
        if (on == enabled) return null
        enabled = on
        trackKey = null
        track = null
        if (!on) {
            val was = usingSaved
            usingSaved = false
            revision++
            return if (was) push(default) else null
        }
        // Turning on: the setting in effect is the global default; the next track report recalls.
        if (default != applied) {
            default = applied
            revision++
        }
        return recall(now)
    }

    /** An entry was deleted in the list screen. Returns the default if that track is playing with it. */
    fun remove(key: String): VbLevel? {
        if (!store.remove(key)) return null
        revision++
        if (key == trackKey && usingSaved) {
            usingSaved = false
            return push(default)
        }
        return null
    }

    fun clear(): VbLevel? {
        store.clear()
        revision++
        if (usingSaved) {
            usingSaved = false
            return push(default)
        }
        return null
    }

    private fun recall(now: Long): VbLevel? {
        val key = trackKey
        val e = if (enabled && key != null) store.get(key) else null
        val wasSaved = usingSaved
        val target = if (e != null) {
            store.touch(key!!, now)
            VbLevel.of(e.levelDb, e.modelKey ?: default.modelKey)
        } else default
        usingSaved = e != null
        if (e != null || wasSaved) revision++
        return push(target)
    }

    private fun push(target: VbLevel): VbLevel? {
        if (target == applied) return null
        applied = target
        return target
    }
}

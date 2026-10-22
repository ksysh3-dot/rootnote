import me.timschneeberger.rootlessjamesdsp.pvb.PlayerSnapshot
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.TrackInfo
import me.timschneeberger.rootlessjamesdsp.pvb.TrackKeys
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevelEntry
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevelPolicy
import me.timschneeberger.rootlessjamesdsp.pvb.TrackLevelStore
import me.timschneeberger.rootlessjamesdsp.pvb.VbLevel

// Alpha 3.1 per-song level memory: key normalisation, LRU store and its text format, recall/save decisions.

private const val PKG = "com.google.android.apps.youtube.music"
private fun t(title: String?, artist: String? = "Ana", pkg: String = PKG, album: String? = null) = TrackInfo(pkg, artist, title, album)
private fun playing(track: TrackInfo?) = PlayerSnapshot(track, playing = true, paused = false)
private fun paused(track: TrackInfo?) = PlayerSnapshot(track, playing = false, paused = true)
private fun stopped(track: TrackInfo?) = PlayerSnapshot(track, playing = false, paused = false)
private fun lv(db: Float, model: String = PvbModels.P1_KEY) = VbLevel.of(db, model)
private fun entry(key: String, used: Long, db: Float = 6f) = TrackLevelEntry(key, PKG, "a", key, db, PvbModels.P1_KEY, used)

private fun keys() {
    // Normalisation: trim, lowercase, whitespace runs (incl. NBSP, ideographic space, tabs) collapse, NFC.
    check(TrackKeys.normalize("  Sunrise \t  ") == "sunrise")
    check(TrackKeys.normalize("Night falls　ALL") == "night falls all")
    check(TrackKeys.normalize("가") == "가")   // decomposed 가 == composed 가
    check(TrackKeys.normalize(null) == "")
    val k = TrackKeys.of(t("Sunrise"))!!
    check(k == TrackKeys.of(t("  SUNRISE ", artist = " ana ", pkg = " $PKG ")))
    check(k == TrackKeys.of(t("Sunrise", album = "Morning set")))      // album is not part of the key
    check(k != TrackKeys.of(t("Sunrise", pkg = "com.spotify.music")))
    check(k != TrackKeys.of(t("Sunrise", artist = "Someone")))
    check(TrackKeys.of(t("Sun rise")) != k)
    // No title -> no key; missing artist is allowed.
    for (bad in listOf(null, "", "   ", "　")) check(TrackKeys.of(t(bad)) == null) { "title '$bad'" }
    check(TrackKeys.of(null) == null)
    check(TrackKeys.of(t("Song", pkg = " ")) == null)
    check(TrackKeys.of(t("Song", artist = null)) != null && TrackKeys.of(t("Song", artist = null)) == TrackKeys.of(t("Song", artist = "  ")))
    // A separator inside a part cannot fake another split.
    check(TrackKeys.of(t("b", artist = "a\u001Fx")) != TrackKeys.of(t("x\u001Fb", artist = "a")))

    // Selection: a playing keyed item wins; a paused one only keeps the track that was already followed.
    val a = t("A"); val b = t("B")
    check(TrackKeys.select(listOf(paused(a), playing(b)), null) == b)
    check(TrackKeys.select(listOf(playing(t(null)), playing(b)), null) == b)
    check(TrackKeys.select(listOf(paused(a)), null) == null)
    check(TrackKeys.select(listOf(paused(a)), TrackKeys.of(a)) == a)
    check(TrackKeys.select(listOf(stopped(a)), TrackKeys.of(a)) == null)
    check(TrackKeys.select(emptyList(), TrackKeys.of(a)) == null)
}

private fun store() {
    val s = TrackLevelStore(capacity = 3)
    s.put(entry("k1", 10)); s.put(entry("k2", 20)); s.put(entry("k3", 30))
    s.touch("k1", 40)                       // k1 is now the most recent
    s.put(entry("k4", 50))                  // evicts the least recently used: k2
    check(s.size == 3 && s.get("k2") == null && s.get("k1") != null)
    check(s.entries().map { it.key } == listOf("k4", "k1", "k3"))
    s.touch("k3", 5)                        // an older clock never moves an entry back
    check(s.get("k3")!!.lastUsed == 30L)
    // The entry just written survives even if the clock went backwards.
    s.put(entry("k5", 1))
    check(s.get("k5") != null && s.size == 3 && s.get("k3") == null)
    // Updating an existing key does not evict anything.
    s.put(entry("k4", 60, db = 9f))
    check(s.size == 3 && s.get("k4")!!.levelDb == 9f)
    check(s.remove("k4") && !s.remove("k4") && s.size == 2)

    // Cap 500 by default.
    val big = TrackLevelStore()
    for (i in 0 until 600) big.put(entry("k$i", i.toLong()))
    check(big.size == 500 && big.get("k99") == null && big.get("k100") != null && big.get("k599") != null)

    // Round trip with awkward text; damaged input never throws.
    val r = TrackLevelStore()
    r.put(TrackLevelEntry("x\u001Fy\u001Fz", PKG, "Tab\there", "New\nline \\ back\\t", 7f, null, 123))
    r.put(TrackLevelEntry("k", "p", "", "제목", 12f, "alpha3_gentle12", Long.MAX_VALUE))
    val back = TrackLevelStore.decode(r.encode())
    check(back.entries() == r.entries()) { "${back.entries()} vs ${r.entries()}" }
    check(TrackLevelStore.decode(null).size == 0 && TrackLevelStore.decode("").size == 0)
    check(TrackLevelStore.decode("{\"json\":1}").size == 0)
    val damaged = r.encode() + "\nonly\tthree\tfields\n\tp\ta\tt\t1\t\t2\nk2\tp\ta\tt\tNaN\t\t2\nk3\tp\ta\tt\t4\t\tx\nk4\tp\ta\tt\t4\t\t9"
    val d = TrackLevelStore.decode(damaged)
    check(d.size == 3 && d.get("k4")!!.levelDb == 4f && d.get("k2") == null && d.get("k3") == null)
    check(TrackLevelStore.decode(TrackLevelStore().also { for (i in 0 until 9) it.put(entry("k$i", i.toLong())) }.encode(), 4).size == 4)
}

private fun policy() {
    val def = lv(6f)
    val a = t("A"); val b = t("B"); val c = t("C")
    var now = 1000L
    fun tick() = ++now

    // Fresh: memory on, nothing remembered. Unknown track -> default; playing a track without entry -> default.
    val p = TrackLevelPolicy(TrackLevelStore(), def, enabled = true, overrideActive = false, current = def)
    check(p.takeStartupRestore() == null)
    check(p.onPlayers(listOf(playing(a)), tick()) == null && p.trackKey == TrackKeys.of(a) && !p.usingSaved)
    // The user moves the slider during A -> remembered for A, default untouched.
    check(p.onSettingsChanged(lv(9f), tick()))
    check(p.store.get(TrackKeys.of(a)!!)!!.levelDb == 9f && p.usingSaved && p.default == def)
    // A preset during A changes model and level: both remembered.
    check(p.onSettingsChanged(lv(9f, PvbModels.GENTLE12_KEY), tick()))
    check(p.store.get(TrackKeys.of(a)!!)!!.modelKey == PvbModels.GENTLE12_KEY)
    // B has no entry -> back to the default (model too).
    check(p.onTrack(b, tick()) == def && !p.usingSaved)
    // Our own write coming back is not a user change.
    check(!p.onSettingsChanged(def, tick()) && p.store.get(TrackKeys.of(b)!!) == null)
    // Back to A -> its setting.
    check(p.onTrack(a, tick()) == lv(9f, PvbModels.GENTLE12_KEY) && p.usingSaved)
    check(!p.onSettingsChanged(lv(9f, PvbModels.GENTLE12_KEY), tick()))
    // Same track again (metadata refresh, album added): nothing to write.
    check(p.onTrack(t("A", album = "X"), tick()) == null && p.track?.album == "X")
    // Pause A: stays on A's setting. Stop: no track -> default.
    check(p.onPlayers(listOf(paused(a)), tick()) == null && p.usingSaved)
    check(p.onPlayers(listOf(stopped(a)), tick()) == def && p.trackKey == null && !p.usingSaved)
    // No track: a change is the new default; then a track without entry gets the new default.
    check(!p.onSettingsChanged(lv(4f), tick()) && p.default == lv(4f))
    check(p.onTrack(c, tick()) == null)                // already at the new default
    check(p.onTrack(a, tick()) == lv(9f, PvbModels.GENTLE12_KEY))
    check(p.onTrack(b, tick()) == lv(4f))
    // Untitled item -> no key -> default and nothing saved on a change.
    p.onTrack(a, tick())
    check(p.onTrack(t(null), tick()) == lv(4f) && p.trackKey == null)
    val sizeBefore = p.store.size
    check(!p.onSettingsChanged(lv(5f), tick()) && p.store.size == sizeBefore && p.default == lv(5f))

    // Recall touches the entry (LRU by last use).
    val usedBefore = p.store.get(TrackKeys.of(a)!!)!!.lastUsed
    p.onTrack(a, tick())
    check(p.store.get(TrackKeys.of(a)!!)!!.lastUsed > usedBefore)

    // Deleting the playing track's entry returns to the default; deleting another one changes nothing audible.
    check(p.remove(TrackKeys.of(a)!!) == lv(5f) && !p.usingSaved)
    check(p.remove("missing") == null)
    p.onSettingsChanged(lv(8f), tick())               // remembered again for A
    p.onTrack(b, tick())                               // B: default
    p.onSettingsChanged(lv(2f), tick())                // remembered for B
    p.onTrack(a, tick())
    check(p.clear() == lv(5f) && p.store.size == 0 && !p.usingSaved)

    // Toggle off: no saving, no recall; the default comes back if a remembered value was playing.
    val q = TrackLevelPolicy(TrackLevelStore(), def, enabled = true, overrideActive = false, current = def)
    q.onTrack(a, tick()); q.onSettingsChanged(lv(10f), tick())
    check(q.setEnabled(false, tick()) == def && !q.usingSaved && q.trackKey == null)
    check(q.onTrack(b, tick()) == null && q.onTrack(a, tick()) == null)        // no recall while off
    check(!q.onSettingsChanged(lv(3f), tick()) && q.store.get(TrackKeys.of(a)!!)!!.levelDb == 10f) // no save
    check(q.default == lv(3f))                                                  // off: changes are the default
    // Off with nothing remembered in effect: turning off writes nothing.
    check(q.setEnabled(true, tick()) == null && q.default == lv(3f))
    check(q.onTrack(a, tick()) == lv(10f))
    check(q.setEnabled(false, tick()) == lv(3f))
    check(q.setEnabled(false, tick()) == null)                                  // idempotent
    val r = TrackLevelPolicy(TrackLevelStore(), def, enabled = false, overrideActive = false, current = def)
    check(r.setEnabled(false, tick()) == null && r.onTrack(a, tick()) == null)

    // Turning on takes the current setting as the default (the user's global value).
    val s = TrackLevelPolicy(TrackLevelStore(), def, enabled = false, overrideActive = false, current = lv(11f))
    check(s.default == lv(11f))
    check(s.setEnabled(true, tick()) == null && s.default == lv(11f))

    // Restart inside a remembered track (process killed): back to the stored default once.
    val store = TrackLevelStore().also { it.put(TrackLevelEntry(TrackKeys.of(a)!!, PKG, "Ana", "A", 12f, null, 1)) }
    val u = TrackLevelPolicy(store, lv(5f), enabled = true, overrideActive = true, current = lv(12f))
    check(u.takeStartupRestore() == lv(5f) && u.takeStartupRestore() == null)
    check(!u.onSettingsChanged(lv(5f), tick()))                    // that restore echoing back
    check(u.onTrack(a, tick()) == lv(12f, PvbModels.DEFAULT_KEY))   // entry without a model uses the default model
    // Without the flag the current setting simply is the default.
    val v = TrackLevelPolicy(TrackLevelStore(), lv(5f), enabled = true, overrideActive = false, current = lv(7f))
    check(v.takeStartupRestore() == null && v.default == lv(7f))

    // Stored values are normalised like the settings (clamped whole dB, unknown model -> default model).
    val w = TrackLevelPolicy(TrackLevelStore().also { it.put(TrackLevelEntry(TrackKeys.of(a)!!, PKG, "", "A", 30f, "gone", 1)) },
        def, enabled = true, overrideActive = false, current = def)
    check(w.onTrack(a, tick()) == VbLevel(12f, PvbModels.DEFAULT_KEY))

    // Revision moves on every persisted change only.
    val x = TrackLevelPolicy(TrackLevelStore(), def, enabled = true, overrideActive = false, current = def)
    val r0 = x.revision
    x.onTrack(a, tick()); x.onSettingsChanged(def, tick())
    check(x.revision == r0)
    x.onSettingsChanged(lv(7f), tick())
    check(x.revision > r0)
}

fun main() {
    keys()
    store()
    policy()
    println("Track level memory: key normalisation (case, spaces, NFC, no title -> none), player selection, " +
        "LRU cap 3/500 and text round trip, recall/default/save, toggle off, delete/clear, restart restore passed")
}

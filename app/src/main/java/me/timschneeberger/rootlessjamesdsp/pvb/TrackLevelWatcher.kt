package me.timschneeberger.rootlessjamesdsp.pvb

import android.content.Context
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import me.timschneeberger.rootlessjamesdsp.session.shared.BaseSessionManager
import timber.log.Timber

/**
 * Alpha 3.1: follows the playing song for [TrackLevels], using the audio service's session manager (the app's one
 * MediaSessionManager listener and its NotificationListenerService). Lives as long as the audio service.
 *
 * Every callback is delivered on the main looper. Controllers can die at any time and the user can revoke
 * notification access at any time: both read as "no song", which returns to the default level.
 */
class TrackLevelWatcher(context: Context, private val sessions: BaseSessionManager) {
    private val main = Handler(Looper.getMainLooper())
    private val levels = TrackLevels.get(context)
    private val hooked = HashMap<MediaSession.Token, Pair<MediaController, MediaController.Callback>>()
    private var started = false
    private var listenerInstalled = false

    private val refreshRunnable = Runnable { refresh() }
    private val poll = object : Runnable {
        override fun run() {
            refresh()   // also notices access granted or revoked in the system settings
            if (started) main.postDelayed(this, POLL_MS)
        }
    }

    fun start() {
        if (started) return
        started = true
        sessions.onMediaSessionsChanged = { refreshSoon() }
        levels.watcherRefresh = { refreshSoon() }
        levels.setWatching(true)
        refresh()
        main.postDelayed(poll, POLL_MS)
    }

    fun stop() {
        if (!started) return
        started = false
        main.removeCallbacks(poll)
        main.removeCallbacks(refreshRunnable)
        sessions.onMediaSessionsChanged = null
        levels.watcherRefresh = null
        unhookAll()
        levels.onPlayers(emptyList())   // no song is known without the service: back to the default
        levels.setWatching(false)
    }

    /** Players often send title, artist and state in quick succession: read once they settle. */
    private fun refreshSoon() {
        main.removeCallbacks(refreshRunnable)
        if (started) main.postDelayed(refreshRunnable, SETTLE_MS)
    }

    private fun refresh() {
        if (!started) return
        if (!levels.enabled) {
            unhookAll()
            return
        }
        if (!sessions.hasNotificationAccess()) {
            unhookAll()
            listenerInstalled = false
            levels.onPlayers(emptyList())
            return
        }
        if (!listenerInstalled) {
            sessions.refreshNotificationListener()   // access may have been granted after the service started
            listenerInstalled = true
        }
        val controllers = sessions.activeMediaControllers()
        sync(controllers)
        levels.onPlayers(controllers.map { snapshot(it) })
    }

    private fun sync(controllers: List<MediaController>) {
        val tokens = controllers.mapNotNull { c -> try { c.sessionToken } catch (_: Exception) { null } }.toSet()
        val gone = hooked.keys.filter { it !in tokens }
        for (token in gone) hooked.remove(token)?.let { (c, cb) -> unregister(c, cb) }
        for (c in controllers) {
            val token = try { c.sessionToken } catch (_: Exception) { null } ?: continue
            if (token in hooked) continue
            val cb = object : MediaController.Callback() {
                override fun onMetadataChanged(metadata: MediaMetadata?) = refreshSoon()
                override fun onPlaybackStateChanged(state: PlaybackState?) = refreshSoon()
                override fun onSessionDestroyed() = refreshSoon()
            }
            try {
                c.registerCallback(cb, main)
                hooked[token] = c to cb
            } catch (e: Exception) {
                Timber.w(e, "TrackLevelWatcher: registerCallback failed for ${c.packageName}")
            }
        }
    }

    private fun unhookAll() {
        for ((c, cb) in hooked.values) unregister(c, cb)
        hooked.clear()
    }

    private fun unregister(c: MediaController, cb: MediaController.Callback) {
        try { c.unregisterCallback(cb) } catch (_: Exception) { }
    }

    private fun snapshot(c: MediaController): PlayerSnapshot = try {
        val state = c.playbackState?.state ?: PlaybackState.STATE_NONE
        val md = c.metadata
        fun text(key: String): String? = md?.getText(key)?.toString()?.takeIf { it.isNotBlank() }
        val title = text(MediaMetadata.METADATA_KEY_TITLE) ?: text(MediaMetadata.METADATA_KEY_DISPLAY_TITLE)
        val artist = text(MediaMetadata.METADATA_KEY_ARTIST) ?: text(MediaMetadata.METADATA_KEY_ALBUM_ARTIST)
        val album = text(MediaMetadata.METADATA_KEY_ALBUM)
        PlayerSnapshot(
            track = if (md != null) TrackInfo(c.packageName, artist, title, album) else null,
            playing = state in PLAYING_STATES,
            paused = state == PlaybackState.STATE_PAUSED,
        )
    } catch (e: Exception) {
        // A dead session (DeadObjectException) or a malformed metadata bundle: treat it as no song.
        PlayerSnapshot(null, playing = false, paused = false)
    }

    companion object {
        private const val POLL_MS = 5000L
        private const val SETTLE_MS = 300L
        private val PLAYING_STATES = setOf(
            PlaybackState.STATE_PLAYING,
            PlaybackState.STATE_BUFFERING,
            PlaybackState.STATE_CONNECTING,
            PlaybackState.STATE_FAST_FORWARDING,
            PlaybackState.STATE_REWINDING,
            PlaybackState.STATE_SKIPPING_TO_NEXT,
            PlaybackState.STATE_SKIPPING_TO_PREVIOUS,
            PlaybackState.STATE_SKIPPING_TO_QUEUE_ITEM,
        )
    }
}

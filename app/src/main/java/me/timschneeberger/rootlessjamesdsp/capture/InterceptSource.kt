package me.timschneeberger.rootlessjamesdsp.capture

import android.content.Context
import android.media.AudioRecord
import rikka.shizuku.Shizuku
import timber.log.Timber
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * "가로채기 캡처", the app side: starts [InterceptServer] as the shell user through Shizuku and reads its PCM
 * (16-bit stereo) from the process' stdout. Stopping only stops reading; the process keeps the players off the
 * speaker until [release] closes it (then the system removes its policy and they play normally again).
 */
class InterceptSource private constructor(private val process: Process, sampleRate: Int) : CaptureSource {
    private val input: InputStream = process.inputStream
    private val stdin: OutputStream = process.outputStream
    @Volatile private var recording = false
    @Volatile private var released = false
    @Volatile private var dead = false

    // Keep draining shell stdout independently of the DSP/AudioTrack. A blocking AudioTrack.write or expensive
    // effect must not fill the shell pipe and stall the remote-submix recorder (video apps use its playback clock).
    // 150 ms bounds latency after a stall; excess *old* stereo frames are discarded, never played at a faster rate.
    private val pcm = InterceptPcmQueue((sampleRate * 150 / 1000).coerceAtLeast(1))

    init {
        Thread({
            val chunk = ByteArray(4096)
            var lastLoggedDrops = 0L
            var lastLogMs = 0L
            try {
                while (!released) {
                    val n = input.read(chunk)
                    if (n < 0) break
                    if (n == 0) continue
                    pcm.offer(chunk, 0, n)
                    val drops = pcm.droppedFrames
                    if (drops > lastLoggedDrops) {
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastLogMs >= 5000L) {
                            Timber.w("Intercept PCM backlog: %d old frames dropped in %d ms",
                                drops - lastLoggedDrops, (drops - lastLoggedDrops) * 1000 / sampleRate)
                            lastLoggedDrops = drops
                            lastLogMs = now
                        }
                    }
                }
            } catch (e: Exception) {
                if (!released) Timber.w(e, "Intercept PCM pipe read failed")
            } finally {
                if (!released) {
                    dead = true
                    Timber.w("Intercept PCM pipe closed; capture needs recreation")
                }
                pcm.close()
            }
        }, "intercept-pcm-reader").apply { isDaemon = true }.start()
    }

    override val state get() = if (released || dead) AudioRecord.STATE_UNINITIALIZED else AudioRecord.STATE_INITIALIZED
    override val recordingState get() = if (recording) AudioRecord.RECORDSTATE_RECORDING else AudioRecord.RECORDSTATE_STOPPED
    override val intercepting = true

    override fun startRecording() {
        if (released || dead) return
        pcm.start() // drop anything captured while stopped, without relying on InputStream.available()
        recording = true
    }

    override fun stop() {
        recording = false
        pcm.stop() // the reader still drains stdout so the Android playback mixer never waits on the app
    }

    override fun release() {
        if (released) return
        released = true
        recording = false
        pcm.close() // unblock a read before closing the pipe
        try { stdin.close() } catch (_: Exception) {}
        try { input.close() } catch (_: Exception) {}
        try { process.destroy() } catch (_: Exception) {}
    }

    override fun read(buf: ShortArray, off: Int, size: Int): Int {
        if (released || dead) return AudioRecord.ERROR_DEAD_OBJECT
        val n = pcm.read(buf, off, size)
        return if (n < 0) AudioRecord.ERROR_DEAD_OBJECT else n
    }

    override fun read(buf: FloatArray, off: Int, size: Int): Int {
        if (released || dead) return AudioRecord.ERROR_DEAD_OBJECT
        val n = pcm.read(buf, off, size)
        return if (n < 0) AudioRecord.ERROR_DEAD_OBJECT else n
    }

    companion object {
        /** Why the last start failed (for the status line and the log), or null. */
        @Volatile var lastError: String? = null; private set

        /** Shizuku is running and lets this app use it. */
        fun shizukuReady(): Boolean = try {
            Shizuku.pingBinder() && !Shizuku.isPreV11() && Shizuku.checkSelfPermission() == android.content.pm.PackageManager.PERMISSION_GRANTED
        } catch (_: Throwable) { false }

        /**
         * Starts the shell process and waits up to [timeoutMs] for it to say it records. Null when it can't (no
         * Shizuku, Android before 13, the policy refused); [lastError] says why.
         */
        fun start(context: Context, sampleRate: Int, excludedUids: Collection<Int>, timeoutMs: Long = 8000): InterceptSource? {
            lastError = null
            if (android.os.Build.VERSION.SDK_INT < 33) { lastError = "android_13_needed"; return null }
            if (!shizukuReady()) { lastError = "shizuku_off"; return null }
            val apk = context.applicationInfo.sourceDir
            val cmd = (listOf("app_process", "-Djava.class.path=$apk", "/system/bin", InterceptServer::class.java.name) +
                InterceptArgs.build(sampleRate, excludedUids)).toTypedArray()
            val process = try {
                // Shizuku.newProcess is not public in this API version; it is what the shell commands use
                val m = Shizuku::class.java.getDeclaredMethod("newProcess",
                    Array<String>::class.java, Array<String>::class.java, String::class.java)
                m.isAccessible = true
                m.invoke(null, cmd, null, null) as Process
            } catch (t: Throwable) {
                lastError = "spawn: ${t.cause?.message ?: t.message}"
                Timber.e(t, "Intercept capture: could not start the shell process")
                return null
            }
            val ready = CountDownLatch(1)
            val ok = java.util.concurrent.atomic.AtomicBoolean(false)
            val ended = java.util.concurrent.atomic.AtomicBoolean(false)
            // the last lines the process wrote (a Java exception from app_process does not start with "ERROR")
            val tail = ArrayDeque<String>()
            Thread({
                try {
                    process.errorStream.bufferedReader().forEachLine { line ->
                        Timber.d("Intercept server: $line")
                        if (line.isNotBlank()) synchronized(tail) { tail.addLast(line.trim()); if (tail.size > 4) tail.removeFirst() }
                        if (line == InterceptServer.READY) { ok.set(true); ready.countDown() }
                        else if (line.startsWith("ERROR")) { lastError = line; ready.countDown() }
                    }
                } catch (_: Exception) {}
                ended.set(true)
                ready.countDown()
            }, "intercept-stderr").apply { isDaemon = true }.start()
            if (!ready.await(timeoutMs, TimeUnit.MILLISECONDS) || !ok.get()) {
                if (lastError == null) {
                    val last = synchronized(tail) { tail.lastOrNull { !it.startsWith("at ") } ?: tail.lastOrNull() }
                    lastError = InterceptReason.describe(ended.get(), (timeoutMs / 1000).toInt(), last)
                }
                Timber.w("Intercept capture failed: $lastError")
                try { process.destroy() } catch (_: Exception) {}
                return null
            }
            Timber.i("Intercept capture running (excluded UIDs: ${excludedUids.joinToString()})")
            return InterceptSource(process, sampleRate)
        }
    }
}

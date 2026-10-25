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
class InterceptSource private constructor(private val process: Process) : CaptureSource {
    private val input: InputStream = process.inputStream
    private val stdin: OutputStream = process.outputStream
    @Volatile private var recording = false
    @Volatile private var released = false
    @Volatile private var dead = false
    private var bytes = ByteArray(0)

    override val state get() = if (released || dead) AudioRecord.STATE_UNINITIALIZED else AudioRecord.STATE_INITIALIZED
    override val recordingState get() = if (recording) AudioRecord.RECORDSTATE_RECORDING else AudioRecord.RECORDSTATE_STOPPED
    override val intercepting = true

    override fun startRecording() {
        if (released) return
        // what piled up while stopped is old: skip it, the output starts with fresh audio
        try { val n = input.available(); if (n > 0) input.skip(n.toLong()) } catch (_: Exception) {}
        recording = true
    }

    override fun stop() { recording = false }

    override fun release() {
        if (released) return
        released = true
        recording = false
        try { stdin.close() } catch (_: Exception) {}
        try { input.close() } catch (_: Exception) {}
        try { process.destroy() } catch (_: Exception) {}
    }

    /** Fills [bytes] with [n] bytes; false at the end of the stream. */
    private fun readFully(n: Int): Boolean {
        if (bytes.size < n) bytes = ByteArray(n)
        var got = 0
        while (got < n) {
            val r = try { input.read(bytes, got, n - got) } catch (_: Exception) { -1 }
            if (r < 0) return false
            got += r
        }
        return true
    }

    override fun read(buf: ShortArray, off: Int, size: Int): Int {
        if (released || dead) return AudioRecord.ERROR_DEAD_OBJECT
        if (!readFully(size * 2)) { dead = true; return AudioRecord.ERROR_DEAD_OBJECT }
        for (i in 0 until size) buf[off + i] = ((bytes[2 * i].toInt() and 0xff) or (bytes[2 * i + 1].toInt() shl 8)).toShort()
        return size
    }

    override fun read(buf: FloatArray, off: Int, size: Int): Int {
        if (released || dead) return AudioRecord.ERROR_DEAD_OBJECT
        if (!readFully(size * 2)) { dead = true; return AudioRecord.ERROR_DEAD_OBJECT }
        for (i in 0 until size) {
            val s = (bytes[2 * i].toInt() and 0xff) or (bytes[2 * i + 1].toInt() shl 8)
            buf[off + i] = s.toShort() / 32768f
        }
        return size
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
            val cmd = arrayOf("app_process", "-Djava.class.path=$apk", "/system/bin",
                InterceptServer::class.java.name, sampleRate.toString(), excludedUids.joinToString(","))
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
                    lastError = when {
                        ended.get() -> "exited: ${last ?: "no output"}"
                        else -> "timeout ${timeoutMs / 1000} s${last?.let { ": $it" } ?: ""}"
                    }
                }
                Timber.w("Intercept capture failed: $lastError")
                try { process.destroy() } catch (_: Exception) {}
                return null
            }
            Timber.i("Intercept capture running (excluded UIDs: ${excludedUids.joinToString()})")
            return InterceptSource(process).also { it.recording = false }
        }
    }
}

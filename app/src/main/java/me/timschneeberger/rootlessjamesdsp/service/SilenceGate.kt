package me.timschneeberger.rootlessjamesdsp.service

/**
 * Battery: lets the speaker path rest while nothing plays. Pure logic (no Android types), tested on the host JVM
 * (tools/pvb-harness/jvm/SilenceGateTest.kt).
 *
 * A paused music app usually keeps its audio session, so the service is not "idle" and the loop goes on reading
 * silence, processing it and playing it. That keeps our output track active, so the phone's speaker path (DSP,
 * amplifier) never enters standby. The gate watches the processed blocks: once the captured input and the processed
 * output have both been silent for [holdFrames] in a row, the loop pauses the output track and stops writing. The
 * capture and both engines keep running on the silence, so a setting changed meanwhile (a virtual-bass switch, a
 * volume-link glide, a reset fade) still plays out in the silence, and the first block that is not silent resumes
 * the track and is played exactly as it would have been.
 *
 * "Silent" means every sample at most one 16-bit step (-90 dBFS) from zero, so a pause never cuts anything audible.
 *
 * Deep sleep (optional, off by default): once the output has been paused for the chosen time ([deepDue]), the loop
 * stops the capture too, so nothing keeps the phone awake. That is the only step that can cut sound: playback is
 * noticed (a playback callback, then the capture restarts), so the first ~0.1 s of the next sound may be lost.
 */
class SilenceGate(holdFrames: Long) {
    /** Silent frames before the output pauses (the user's choice; a change applies to the silence counted so far). */
    var holdFrames = holdFrames
    /** True while the output is paused (silent blocks are processed but not written). */
    var paused = false
        private set
    private var quietFrames = 0L
    /** Frames skipped since the pause (or since the capture came back from deep sleep). */
    var pausedFrames = 0L
        private set

    /**
     * After processing a block, before writing it. True = do not write it (paused, the block is still silent and
     * pausing is allowed). Otherwise the gate is open again (if it was paused, the caller restarts its output first).
     */
    fun skip(silent: Boolean, allowed: Boolean, frames: Int = 0): Boolean {
        if (!paused) return false
        if (silent && allowed) {
            pausedFrames += frames
            return true
        }
        paused = false
        quietFrames = 0
        pausedFrames = 0
        return false
    }

    /** True = the output has rested for [deepFrames] (> 0): stop the capture too. 0 = deep sleep off. */
    fun deepDue(deepFrames: Long) = paused && deepFrames > 0 && pausedFrames >= deepFrames

    /** The capture came back from deep sleep: still paused, and a new deep sleep needs the full time again. */
    fun rearm() {
        pausedFrames = 0
    }

    /** After a processed block of [frames] frames: true = pause the output now. */
    fun afterBlock(silent: Boolean, frames: Int, allowed: Boolean): Boolean {
        if (!silent || !allowed) {
            quietFrames = 0
            return false
        }
        quietFrames += frames
        if (quietFrames < holdFrames) return false
        paused = true
        return true
    }

    /** Forget everything (the output was stopped or rebuilt by someone else). */
    fun reset() {
        paused = false
        quietFrames = 0
        pausedFrames = 0
    }

    companion object {
        /** Seconds of silence (input and output) before the output pauses, unless the user chose otherwise. */
        const val HOLD_SECONDS = 2.0
        private const val FLOAT_LIMIT = 1f / 32768f
        private const val SHORT_LIMIT = 1

        fun forRate(sampleRate: Int) = SilenceGate((HOLD_SECONDS * sampleRate).toLong())

        /** Hold setting (seconds, "2" / "5" / "10") in frames; anything unknown or below 1 s is the default 2 s. */
        fun holdFrames(setting: String?, sampleRate: Int): Long {
            val seconds = setting?.trim()?.toLongOrNull()
            return if (seconds == null || seconds < 1) (HOLD_SECONDS * sampleRate).toLong() else seconds * sampleRate
        }

        /** Deep-sleep setting (seconds of rest, "0" = off) in frames; anything unknown or negative is off. */
        fun deepFrames(setting: String?, sampleRate: Int): Long {
            val seconds = setting?.trim()?.toLongOrNull() ?: return 0
            return if (seconds <= 0) 0 else seconds * sampleRate
        }

        /** True if the first [n] samples are all within one 16-bit step of zero (NaN is not silent). */
        fun isSilent(buf: FloatArray, n: Int): Boolean {
            for (i in 0 until n) {
                val v = buf[i]
                if (!(v <= FLOAT_LIMIT && v >= -FLOAT_LIMIT)) return false
            }
            return true
        }

        fun isSilent(buf: ShortArray, n: Int): Boolean {
            for (i in 0 until n) {
                val v = buf[i].toInt()
                if (v > SHORT_LIMIT || v < -SHORT_LIMIT) return false
            }
            return true
        }
    }
}

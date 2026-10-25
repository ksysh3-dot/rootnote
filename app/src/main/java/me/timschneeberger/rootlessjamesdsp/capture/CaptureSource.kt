package me.timschneeberger.rootlessjamesdsp.capture

import android.media.AudioRecord

/**
 * What the capture loop reads from: the MediaProjection AudioRecord ([RecordSource]) or the shell process of
 * "가로채기 캡처" ([InterceptSource]). States and return codes are AudioRecord's.
 */
interface CaptureSource {
    /** AudioRecord.STATE_INITIALIZED or STATE_UNINITIALIZED. */
    val state: Int
    /** AudioRecord.RECORDSTATE_RECORDING or RECORDSTATE_STOPPED. */
    val recordingState: Int
    /** True for "가로채기 캡처" (the players are taken off the device output, nothing has to be muted). */
    val intercepting: Boolean
    fun startRecording()
    fun stop()
    fun release()
    /** Interleaved stereo samples; blocks until [size] are read; < 0 on error (AudioRecord's codes). */
    fun read(buf: ShortArray, off: Int, size: Int): Int
    fun read(buf: FloatArray, off: Int, size: Int): Int
}

/** The MediaProjection capture, unchanged. */
class RecordSource(val record: AudioRecord) : CaptureSource {
    override val state get() = record.state
    override val recordingState get() = record.recordingState
    override val intercepting = false
    override fun startRecording() = record.startRecording()
    override fun stop() = record.stop()
    override fun release() = record.release()
    override fun read(buf: ShortArray, off: Int, size: Int) = record.read(buf, off, size, AudioRecord.READ_BLOCKING)
    override fun read(buf: FloatArray, off: Int, size: Int) = record.read(buf, off, size, AudioRecord.READ_BLOCKING)
}

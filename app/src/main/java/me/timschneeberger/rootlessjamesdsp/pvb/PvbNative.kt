package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * JNI entry points of libpvbengine (app/src/main/cpp/libpvb). Use [PvbEngine] instead of calling these
 * directly. A handle of 0 is accepted everywhere: processing then passes audio through unchanged.
 */
object PvbNative {
    @JvmStatic external fun matchDb(handle: Long): Float
    init {
        System.loadLibrary("pvbengine")
    }

    @JvmStatic external fun create(sampleRate: Int): Long
    @JvmStatic external fun destroy(handle: Long)
    @JvmStatic external fun setSampleRate(handle: Long, sampleRate: Int)
    @JvmStatic external fun reset(handle: Long)
    @JvmStatic external fun setParams(handle: Long, values: FloatArray)
    @JvmStatic external fun processFloat(handle: Long, input: FloatArray, output: FloatArray, length: Int)
    @JvmStatic external fun processShort(handle: Long, input: ShortArray, output: ShortArray, length: Int)
    @JvmStatic external fun setDiagnosticCapture(handle: Long, enabled: Boolean)
    @JvmStatic external fun copyDiagnostic(handle: Long, layer: FloatArray, full: FloatArray, trace: FloatArray, samples: Int): Boolean
    @JvmStatic external fun copyHarmonicTrace(handle: Long, out: FloatArray): Int
    @JvmStatic external fun copyDevMeters(handle: Long, out: FloatArray): Int
    @JvmStatic external fun devMeterSize(): Int
    @JvmStatic external fun readMeters(handle: Long, out: FloatArray)
    @JvmStatic external fun latency(handle: Long): Int
    @JvmStatic external fun openMs(handle: Long, tag: Int): Int
    @JvmStatic external fun paramCount(): Int
    @JvmStatic external fun meterCount(): Int
    @JvmStatic external fun anaInfoCount(): Int
    @JvmStatic external fun analyze(
        handle: Long, inDb: FloatArray, outDb: FloatArray, diffDb: FloatArray, eqDb: FloatArray,
        info: FloatArray, dtSeconds: Double,
    ): Int
}


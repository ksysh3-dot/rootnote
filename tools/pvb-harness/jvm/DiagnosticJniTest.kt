import me.timschneeberger.rootlessjamesdsp.pvb.*
import kotlin.math.*

fun main() {
    PvbEngine(48000).use { e ->
        val p = PvbEngine.defaultParams().apply {
            this[PvbParam.VB_ON]=1f; this[PvbParam.VB_ALGO]=5f; this[PvbParam.VB_LEVEL_DB]=9f
            this[PvbParam.OUT_DB]=-18f; this[PvbParam.RAMP_MS]=0f
        }
        e.setParams(p); e.setDiagnosticCapture(true)
        val n=4096
        val src=FloatArray(n); val out=FloatArray(n); val layer=FloatArray(n); val full=FloatArray(n)
        val trace=FloatArray(BuzzRing.DETAIL_FIELDS)
        val hops=FloatArray(HarmonicHistory.ROWS*HarmonicHistory.FIELDS)
        var seenHops=0
        var phase=0
        var heardLayer=false
        repeat(100) {
            for(i in 0 until n/2) {
                val x=(.1*sin(2*PI*55*(phase++)/48000)).toFloat()
                src[2*i]=x;src[2*i+1]=x
            }
            e.processFloat(src,out,n)
            check(e.copyDiagnostic(layer,full,trace,n))
            check(full.contentEquals(out))
            val rows=e.copyHarmonicTrace(hops)
            check(rows in 0..HarmonicHistory.ROWS)
            repeat(rows) { r ->
                val off=r*HarmonicHistory.FIELDS
                check(hops[off]>=0 && hops[off]<n/2 && hops[off+23]==1f)
            }
            seenHops+=rows
            check(trace[0]==1f && trace[1]==n/2f && trace.all { it.isFinite() })
            heardLayer = heardLayer || layer.any { abs(it)>1e-5f }
        }
        check(heardLayer && seenHops>500)
        check(e.copyHarmonicTrace(FloatArray(1))==-3)
        p[PvbParam.DIAGNOSTIC_SOLO]=1f;e.setParams(p)
        repeat(10) { e.processFloat(src,out,n) }
        check(e.copyDiagnostic(layer,full,trace,n))
        check(out.indices.all { abs(out[it]-layer[it])<1e-6f })
        check(!full.contentEquals(out))
        val pcm=ShortArray(n) { (src[it]*32768).roundToInt().toShort() };val pcmOut=ShortArray(n)
        e.processShort(pcm,pcmOut,n)
        check(e.copyDiagnostic(layer,full,trace,n))
        check(e.copyHarmonicTrace(hops)>0)
        check(pcmOut.indices.all { abs(pcmOut[it].toInt()-(layer[it]*32768).roundToInt())<=1 })
        e.setDiagnosticCapture(false)
        check(!e.copyDiagnostic(layer,full,trace,n))
        check(e.copyHarmonicTrace(hops)==-1)
    }
    println("Diagnostic JNI: float/int16 stems, field schema, harmonic hops, solo and disabled capture passed")
}

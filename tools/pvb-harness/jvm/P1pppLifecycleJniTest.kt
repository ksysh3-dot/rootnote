import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File

private fun check67(ok: Boolean, name: String) { check(ok) { name }; println("PASS $name") }
private fun inputs67(rate: Int = 48000, speaker: Boolean = true, volume: Int = 5) = PvbEngineParams.Inputs(
    rampMs=0f, speaker=speaker, upright=false, rotation=0, volumeIndex=volume, volumeMax=15,
    lowDb=3f, matchSeedDb=-6f, diagnosticSolo=false, abActive=false, abHidden=false,
    abTag=0, gateDb=0f, measuring=false, devMeter=false, sampleRate=rate)
fun main(args: Array<String>) {
    val root=File(args[0])
    val settings=PvbSettings(enabled=true, vbOn=true, p1ppp=true, vbVolLink=true, volLink=true, vbLevelDb=9f)
    val fixed=PvbEngineParams.encode(settings,inputs67()).params
    check67(fixed[PvbParam.P1PPP]==1f && fixed[PvbParam.VB_LEVEL_DB]==0f && fixed[PvbParam.OUT_DB]==-5f,"frozen atomic packet")
    for (v in listOf(0,1,7,15,150,Int.MAX_VALUE))
        check67(PvbEngineParams.encode(settings,inputs67(volume=v)).params.contentEquals(fixed),"volume link suspended $v")
    PvbEngine(48000).use { e ->
        for (rate in listOf(48000,44100,48000,96000,48000)) {
            e.setSampleRate(rate)
            val p=PvbEngineParams.encode(settings,inputs67(rate)).params
            e.setParams(p); e.reset()
            repeat(100) { e.processFloat(FloatArray(512),FloatArray(512)) }
            val m=FloatArray(PvbMeter.COUNT);e.readMeters(m)
            check67(m[PvbMeter.SAMPLE_RATE].toInt()==rate,"same route stream rate $rate")
            check67(m[PvbMeter.P1PPP_STATE].toInt()==if(rate==48000)1 else 0,"complete fallback and return $rate")
        }
        for (speaker in listOf(false,true,false,true)) {
            e.setParams(PvbEngineParams.encode(settings,inputs67(speaker=speaker)).params)
            repeat(100) { e.processFloat(FloatArray(512),FloatArray(512)) }
            val m=FloatArray(PvbMeter.COUNT);e.readMeters(m)
            check67(m[PvbMeter.P1PPP_STATE].toInt()==if(speaker)1 else 0,"route preset $speaker")
        }
    }
    // The owning Kotlin wrapper's closed path calls the same null JNI handle.
    for (n in listOf(1,2,511,2048,2049,5001)) {
        val e=PvbEngine(48000);e.close()
        val si=ShortArray(n){(it*73-17000).toShort()};val so=ShortArray(n)
        e.processShort(si,so);check67(si.contentEquals(so),"closed short passthrough $n")
        val fi=FloatArray(n){(it-10)*.001f};val fo=FloatArray(n)
        e.processFloat(fi,fo);check67(fi.contentEquals(fo),"closed float passthrough $n")
        val count=n/2;val limited=ShortArray(n){111};e.processShort(si,limited,count)
        check67((0 until count).all{limited[it]==si[it]} && (count until n).all{limited[it]==111.toShort()},"closed length bound $n")
    }
    PvbEngine(48000).use { e ->
        val p=fixed.copyOf();p[PvbParam.P1PPP]=0f;e.setParams(p);e.setDiagnosticCapture(true)
        var sample=0
        fun block() {
            val x=FloatArray(512){i -> (.3*Math.sin(2*Math.PI*63*(sample+i/2)/48000)).toFloat()}
            sample+=256
            val y=FloatArray(512);e.processFloat(x,y)
            val layer=FloatArray(512);val full=FloatArray(512);val trace=FloatArray(32+PvbParam.COUNT)
            check(e.copyDiagnostic(layer,full,trace,512))
            check67(full.contentEquals(y),"full stereo during toggle sample=$sample")
        }
        repeat(8){block()};p[PvbParam.P1PPP]=1f;e.setParams(p);repeat(50){block()}
        p[PvbParam.P1PPP]=0f;e.setParams(p);repeat(50){block()}
    }
    // Structural owner checks are labelled separately from executed JNI lifecycle checks.
    val controller=File(root,"app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb/PvbController.kt").readText()
    val attach=controller.substringAfter("fun attachTrack(").substringBefore("// ----")
    check67(attach.contains("updateRoute(push = false)") && attach.contains("push(rampMs = EDIT_RAMP_MS)") && !attach.contains("main.post"),"structural synchronous unconditional stream packet")
    val service=File(root,"app/src/main/java/me/timschneeberger/rootlessjamesdsp/service/RootlessAudioProcessorService.kt").readText()
    check67(service.indexOf("pvbController.attachTrack(track)") < service.indexOf("w.thread.start()"),"structural packet before worker start")
    val recreate=service.substringAfter("if(recreateRecorderRequested)").substringBefore("// Suspend core")
    check67(recreate.contains("pvbWasActive = false") && recreate.contains("capture_recreated"),"structural recorder reset contract")
    println("P1pppLifecycleJniTest passed")
}

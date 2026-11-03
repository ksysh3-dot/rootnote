import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File
private fun inputs74(rate: Int=48000,speaker: Boolean=true,volume: Int=5)=PvbEngineParams.Inputs(
 rampMs=0f,speaker=speaker,upright=false,rotation=0,volumeIndex=volume,volumeMax=15,
 lowDb=3f,matchSeedDb=-6f,diagnosticSolo=false,abActive=false,abHidden=false,
 abTag=0,gateDb=0f,measuring=false,devMeter=false,sampleRate=rate)
fun main(args: Array<String>) {
 val root=File(args[0]);val bytes=File(root,"app/src/main/assets/stable_ab_1218.bin").readBytes()
 var assertions=0
 fun ck(ok: Boolean,what: String){check(ok){what};assertions++}
 val settings=PvbSettings(enabled=true,vbOn=true,stable=true,vbVolLink=true,volLink=true,vbLevelDb=9f)
 val stable=PvbEngineParams.encode(settings,inputs74()).params
 ck(stable[57]==2f && stable[24]==0f && stable[8]==-5f,"atomic stable fixed layer")
 for(volume in listOf(0,1,15,Int.MAX_VALUE))ck(stable.contentEquals(PvbEngineParams.encode(settings,inputs74(volume=volume)).params),"fixed volume $volume")
 PvbEngine(48000).use { engine ->
  ck(!engine.loadStableWeights(ByteArray(1)),"invalid size rejected")
  ck(engine.loadStableWeights(bytes),"asset loaded before audio")
  var clock=0
  fun blocks(n: Int){repeat(n){
   val input=FloatArray(128){i -> (.2*Math.sin(2*Math.PI*63*(clock+i/2)/48000)).toFloat()};clock+=64
   val output=FloatArray(128);engine.processFloat(input,output);ck(output.all{it.isFinite()},"finite callback")
   val layer=FloatArray(128);val full=FloatArray(128);val trace=FloatArray(90)
   ck(engine.copyDiagnostic(layer,full,trace,128) && output.contentEquals(full),"diagnostic stereo fade")
  }}
  engine.setDiagnosticCapture(true)
  for(mode in listOf(0,1,2,1,2,0,2,1,0)) {
   val p=stable.copyOf();p[57]=mode.toFloat();engine.setParams(p);blocks(260)
   val m=FloatArray(PvbMeter.COUNT);engine.readMeters(m)
   ck(m[PvbMeter.P1PPP_STATE].toInt()==when(mode){1->1;2->3;else->0},"settled mode $mode")
   ck(engine.latencyFrames==if(mode==2)10332 else 7140,"reported latency $mode")
  }
  for(rate in listOf(44100,48000,96000,48000)) {
   engine.setSampleRate(rate);engine.setParams(PvbEngineParams.encode(settings,inputs74(rate)).params);engine.reset();blocks(260)
   val m=FloatArray(PvbMeter.COUNT);engine.readMeters(m)
   ck(m[PvbMeter.SAMPLE_RATE].toInt()==rate,"stream rate $rate")
   ck(m[PvbMeter.P1PPP_STATE].toInt()==if(rate==48000)3 else 0,"48k stable gate $rate")
  }
  for(speaker in listOf(false,true,false,true)) {
   engine.setParams(PvbEngineParams.encode(settings,inputs74(speaker=speaker)).params);engine.reset();blocks(260)
   val m=FloatArray(PvbMeter.COUNT);engine.readMeters(m)
   ck(m[PvbMeter.P1PPP_STATE].toInt()==if(speaker)3 else 0,"route fallback $speaker")
  }
 }
 println("StableLifecycleJniTest PASS assertions=$assertions")
}

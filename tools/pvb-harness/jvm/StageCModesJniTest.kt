import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File
import java.security.MessageDigest
private fun stageCInputs(rate: Int=48000)=PvbEngineParams.Inputs(
 rampMs=0f,speaker=true,upright=false,rotation=0,volumeIndex=5,volumeMax=15,
 lowDb=3f,matchSeedDb=-6f,diagnosticSolo=false,abActive=false,abHidden=false,
 abTag=0,gateDb=0f,measuring=false,devMeter=false,sampleRate=rate)
fun main(args: Array<String>) {
 val root=File(args[0]);val assets=File(root,"app/src/main/assets")
 val ctrl=File(assets,"E60KD.bin").readBytes();val sep=File(assets,"T3a16_96.bin").readBytes()
 val epoch=File(assets,"stable_ab_1218.bin").readBytes()
 var assertions=0
 fun ck(v: Boolean,s: String){check(v){s};assertions++}
 fun sha(b: ByteArray)=MessageDigest.getInstance("SHA-256").digest(b).joinToString(""){"%02x".format(it)}
 ck(sha(ctrl)=="8fd3284cd08c101754fff524988e5987ea7e3cf897b494c44ce845e900c80310","control asset")
 ck(sha(sep)=="e7be71d65f05c7a84527e1c58a71edde05012a86034069c933288a597051906d","separator asset")
 ck(PvbSettings().bassMode=="off" && PvbSettings.VB_LEVEL_DEFAULT==4f,"default mode and strength preserved")
 val modes=listOf(
  PvbSettings(enabled=true,vbOn=true),
  PvbSettings(enabled=true,vbOn=true,p1ppp=true),
  PvbSettings(enabled=true,vbOn=true,separated=true),
  PvbSettings(enabled=true,vbOn=true,conducted=true),
  PvbSettings(enabled=true,vbOn=true,stable=true))
 // Real JNI also compares lifecycle preparation with the unchanged, freshly created paths.
 for (id in listOf(0,1,4,3)) {
  PvbEngine(48000).use { reference ->
   PvbEngine(48000).use { prepared ->
    val s=modes[id];val data=when(id){3->ctrl;4->epoch;else->null}
    if(id==3) ck(reference.prepareStageC(id,data,false,false,48000),"reference control")
    else ck(reference.loadStableWeights(epoch),"legacy unconditional epoch6 load")
    ck(prepared.prepareStageC(id,data,false,true,48000),"prepared comparison $id")
    val params=PvbEngineParams.encode(s,stageCInputs()).params
    reference.setParams(params);prepared.setParams(params)
    var clock=0
    repeat(260) { block ->
     val n=listOf(37,64,256,1024)[block%4]
     val input=FloatArray(2*n){i -> (.13*Math.sin(2*Math.PI*71*(clock+i/2)/48000)).toFloat()};clock+=n
     val a=FloatArray(2*n);val b=FloatArray(2*n)
     reference.processFloat(input,a);prepared.processFloat(input,b)
     ck(a.contentEquals(b),"real JNI lifecycle/telemetry byte identity $id block=$block")
    }
   }
  }
 }
 PvbEngine(48000).use { e ->
  val snapshot=LongArray(2012)
  ck(!e.prepareStageC(3,ByteArray(1),false,false,48000),"reject malformed weight")
  for (id in listOf(0,1,2,3,4,3,1,0,3)) {
   val s=modes[id];val data=when(id){2->sep;3->ctrl;4->epoch;else->null}
   ck(s.stageCId==id,"settings selects native mode $id")
   ck(e.prepareStageC(s.stageCId,data,false,true,48000),"real lifecycle JNI prepare $id")
   e.setParams(PvbEngineParams.encode(s,stageCInputs()).params)
   var clock=0
   repeat(450) {
    val input=FloatArray(512){i -> (.14*Math.sin(2*Math.PI*63*(clock+i/2)/48000)+.03*Math.sin(2*Math.PI*126*(clock+i/2)/48000)).toFloat()}
    clock+=256;val out=FloatArray(512);e.processFloat(input,out)
    ck(out.all{it.isFinite()},"finite output $id")
   }
   ck(e.copyStageC(snapshot),"real JNI telemetry $id")
   ck(snapshot[5].toInt()==id,"native configured state $id")
   val m=FloatArray(PvbMeter.COUNT);e.readMeters(m)
   ck(m[PvbMeter.P1PPP_STATE].toInt()==when(id){0->0;2,4->3;else->1},"native engine state $id")
   ck(e.latencyFrames==if(id==2 || id==4)8796 else 7140,"latency $id")
   ck((snapshot[6].toInt() and 4 !=0)==(id==2 || id==4),"separator loaded only in separator modes")
   if(id==3) {
    ck(snapshot[6]==1L && snapshot[0]>0 && snapshot[1]>0,"synchronous real control frames")
    ck(snapshot[4]==0L && snapshot[9]==33L && snapshot[10]==8L,"no separator call; modules33; 8 values")
    ck(snapshot.drop(12).sum()==snapshot[0],"histogram counts equal frame count")
   } else ck(snapshot[0]==0L,"control frame count zero in $id")
   println("mode=$id engine_state=" + m[PvbMeter.P1PPP_STATE] + " flags=" + snapshot[6] + " frames=" + snapshot[0] + " latency=" + e.latencyFrames)
  }
  ck(e.prepareStageC(3,ctrl,true,true,48000),"developer worker lifecycle")
  e.setParams(PvbEngineParams.encode(modes[3],stageCInputs()).params)
  repeat(100){val input=FloatArray(512){.01f};e.processFloat(input,FloatArray(512));Thread.sleep(1)}
  ck(e.copyStageC(snapshot) && snapshot[6]==3L && snapshot[0]>0,"real worker reachable only opt-in")
  ck(e.prepareStageC(1,null,false,false,48000),"worker stops on strong mode")
  ck(e.copyStageC(snapshot) && snapshot[6]==0L && snapshot[11]==0L,"default-off telemetry/control")
 }
 println("StageCModesJniTest PASS assertions=$assertions")
}

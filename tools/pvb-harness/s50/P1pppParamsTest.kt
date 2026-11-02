import me.timschneeberger.rootlessjamesdsp.pvb.*
fun main() {
 val input=PvbEngineParams.Inputs(20f,true,false,1,12,15,12f,-6f,false,false,false,0,0f,false,false)
 val s=PvbSettings(vbOn=true,p1ppp=true,vbAlgo=17,vbLevelDb=9f,lowDb=9f,outDb=0f,dynOn=true,xtcMode=2,xRise=true,devOn=true,vbVolLink=true)
 val p=PvbEngineParams.encode(s,input).params;val d=PvbEngine.defaultParams()
 check(BuzzRing.DETAIL_FIELDS==32+PvbParam.COUNT)
 check(p.size==58 && d.size==58 && d[PvbParam.P1PPP]==0f)
 check(p[PvbParam.P1PPP]==1f && p[PvbParam.VB_ALGO]==6f && p[PvbParam.VB_ON]==1f)
 for(k in intArrayOf(PvbParam.HP_HZ,PvbParam.LOW_DB,PvbParam.HI_DB,PvbParam.OUT_DB,PvbParam.CEIL_DB,PvbParam.REL_MS,PvbParam.DYN_ON,PvbParam.XTC_MODE,PvbParam.DEV_ON,PvbParam.X_RISE,PvbParam.VB_LEVEL_DB,PvbParam.FLAT))check(p[k]==d[k]) {"locked $k"}
 check(s.outDb==0f && s.vbAlgo==17 && s.vbLevelDb==9f) {"saved settings preserved"}
 for(i in listOf(input.copy(abActive=true),input.copy(measuring=true),input.copy(diagnosticSolo=true),input.copy(speaker=false)))check(PvbEngineParams.encode(s,i).params[PvbParam.P1PPP]==0f)
 check(PvbEngineParams.encode(s.copy(enabled=false),input).params[PvbParam.P1PPP]==0f)
 check(PvbEngineParams.encode(s.copy(vbOn=false),input).params[PvbParam.P1PPP]==0f)
 check(PvbEngineParams.encode(s.copy(p1ppp=false),input).params[PvbParam.OUT_DB]==0f)
 println("P1+++ atomic encoding, frozen locks, saved settings and exit boundaries passed")
}

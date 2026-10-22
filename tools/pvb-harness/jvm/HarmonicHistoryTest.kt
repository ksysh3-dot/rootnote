import me.timschneeberger.rootlessjamesdsp.pvb.*

fun main() {
    val h=HarmonicHistory()
    val data=FloatArray(HarmonicHistory.FIELDS)
    data[23]=1f; data[HarmonicHistory.HEADER]=9f
    repeat(2500) { i -> data[0]=7f; data[HarmonicHistory.HEADER]=i.toFloat(); h.record(i*256L,256,data,1) }
    data.fill(-999f) // writer must have copied owned values
    var count=0;var previous=-1L
    h.forEach(1000*256L,2500*256L) { frame,values,off ->
        check(frame>previous && frame%256==7L);previous=frame
        check(values[off+HarmonicHistory.HEADER]==((frame-7)/256).toFloat());++count
    }
    check(count==1500 && !h.truncated(1000*256L) && h.truncated(0))
    h.record(2500*256L,256,null,-2)
    var explicit=false
    h.forEachBlock(2500*256L,2501*256L) { _,_,status -> explicit=status==-2 }
    check(explicit)
    h.reset();data.fill(0f);data[0]=256f;data[23]=1f
    h.record(0,256,data,1)
    var bad=false
    h.forEachBlock(0,256) { _,_,status -> bad=status==-3 }
    check(bad)
    var rows=0;h.forEach(0,256) { _,_,_ -> ++rows };check(rows==0)
    // A complete8s window after a warm history, with every5.333ms decision.
    val ring=BuzzRing(48000,detailed=true).apply { armed=true }
    val audio=FloatArray(512);data.fill(0f);data[23]=1f
    repeat(6*48000/256) { ring.recordFloat(audio,audio,512,null,7140,5,1f,true,harmonic=data,harmonicRows=1) }
    check(ring.trigger())
    while(!ring.frozen) ring.recordFloat(audio,audio,512,null,7140,5,1f,true,harmonic=data,harmonicRows=1)
    val w=ring.window();rows=0
    ring.harmonicHistory!!.forEach(w.start,w.end) { _,_,_ -> ++rows }
    check(w.frames==8*48000 && rows==1500 && !ring.harmonicHistory!!.truncated(w.start))
    println("Harmonic history: wrap/ownership, explicit missing/malformed blocks and complete1500-hop8s passed")
}

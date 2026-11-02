import me.timschneeberger.rootlessjamesdsp.pvb.PvbNative;
import java.security.MessageDigest;
import java.util.HexFormat;
public final class NativeRegression56 {
 static final float[] DEFAULTS={1.0f,100.0f,220.0f,3.0f,1.0f,4500.0f,-3.0f,0.6000000238418579f,-5.0f,-1.0f,60.0f,20.0f,0.0f,-30.0f,0.5f,0.0f,0.1899999976158142f,2.0f,2500.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,-6.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,190.0f,150.0f,600.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,0.0f,10.666666984558105f,32.0f,0.0f,-6.0f,40.0f,57.0f,15.5f,400.0f,8000.0f,0.0f,0.0f,1.0f,0.0f};
 static void put(MessageDigest md,float x){int v=Float.floatToRawIntBits(x);for(int i=0;i<4;i++)md.update((byte)(v>>(8*i)));}
 static void run(int sr,int bs,boolean on,boolean pcm16) throws Exception {
  long h=PvbNative.create(sr);if(h==0)throw new AssertionError("create");
  float[] p=DEFAULTS.clone();p[22]=1;p[23]=6;p[11]=0;p[57]=on?1:0;PvbNative.setParams(h,p);
  float[] in=new float[2048],out=new float[2048];short[] si=new short[2048],so=new short[2048];
  for(int i=0;i<49152;i+=bs) {if(pcm16)PvbNative.processShort(h,si,so,bs*2);else PvbNative.processFloat(h,in,out,bs*2);}
  MessageDigest md=MessageDigest.getInstance("SHA-256");int seed=50;
  // Same steady fixture length as s50, plus identical live toggles and seek.
  int total=(int)(sr*.9);
  for(int a=0;a<total;a+=bs) {
   int n=Math.min(bs,total-a);
   if(a==0 || a/bs==12){PvbNative.setParams(h,p);}
   if(a/bs==24){p[57]=0;PvbNative.setParams(h,p);}
   if(a/bs==40){p[57]=on?1:0;PvbNative.setParams(h,p);PvbNative.reset(h);}
   for(int j=0;j<n;j++) {seed=seed*1664525+1013904223;float noise=(seed>>8)*(1f/16777216f);
    in[2*j]=(float)(.31*Math.sin(2*Math.PI*63*(a+j)/sr))+.02f*noise;
    in[2*j+1]=(float)(.27*Math.sin(2*Math.PI*78*(a+j)/sr+.4))-.025f*noise;
    si[2*j]=(short)(in[2*j]*32767);si[2*j+1]=(short)(in[2*j+1]*32767);
   }
   if(pcm16){PvbNative.processShort(h,si,so,n*2);for(int j=0;j<n*2;j++){md.update((byte)so[j]);md.update((byte)(so[j]>>8));}}
   else {PvbNative.processFloat(h,in,out,n*2);for(int j=0;j<n*2;j++){if(!Float.isFinite(out[j]))throw new AssertionError("finite");put(md,out[j]);}}
  }
  System.out.println(sr+","+bs+","+on+","+pcm16+","+HexFormat.of().formatHex(md.digest()));PvbNative.destroy(h);
 }
 public static void main(String[] args)throws Exception {
  if(PvbNative.paramCount()!=58 || PvbNative.meterCount()!=28)throw new AssertionError("ABI");
  for(int sr:new int[]{48000,44100})for(int bs:new int[]{64,256,1024})for(boolean on:new boolean[]{false,true})for(boolean pcm16:new boolean[]{false,true})run(sr,bs,on,pcm16);
 }
}

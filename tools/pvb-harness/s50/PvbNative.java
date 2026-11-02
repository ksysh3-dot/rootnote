package me.timschneeberger.rootlessjamesdsp.pvb;
public final class PvbNative {
 static {System.loadLibrary("pvbengine");}
 public static native long create(int sr);
 public static native void destroy(long h);
 public static native void setParams(long h,float[] p);
 public static native void setSampleRate(long h,int sr);
 public static native void reset(long h);
 public static native void processFloat(long h,float[] in,float[] out,int length);
 public static native void processShort(long h,short[] in,short[] out,int length);
 public static native int paramCount();
 public static native int meterCount();
 public static native void readMeters(long h,float[] p);
 public static native void allocationProbe(boolean on);
 public static native long allocationCount();
}

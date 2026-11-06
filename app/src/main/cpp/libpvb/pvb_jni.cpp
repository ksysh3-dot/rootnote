// JNI bridge for the PVB speaker engine (Kotlin side: me.timschneeberger.rootlessjamesdsp.pvb.PvbNative).
//
// Audio arrays are copied into an engine-owned buffer with Get/Set<Type>ArrayRegion, so no Java array
// is pinned while processing. Fixed, zero-initialized scratch is ready before streaming; oversized calls
// are split into at most1024-frame chunks without callback allocation.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include <jni.h>

#include <algorithm>
#include <array>
#include <limits>
#include <new>
#include <vector>

#include "pvb_engine.h"

namespace {

struct Handle {
    explicit Handle(int sampleRate) : engine(sampleRate) {}
    pvb::Engine engine;
    static constexpr int kSamples=2048;
    std::array<float,kSamples> floats{};
    std::array<int16_t,kSamples> shortsIn{},shortsOut{};
    float diagnosticLayer[pvb::Engine::kDiagnosticSamples] = {};
    float diagnosticFull[pvb::Engine::kDiagnosticSamples] = {};
    float diagnosticTrace[pvb::Engine::kDiagnosticFields] = {};
    float harmonic[pvb::HarmonicTrace::kBlockRows * pvb::HarmonicTrace::kFields] = {};
};

inline Handle* fromJ(jlong h) { return reinterpret_cast<Handle*>(h); }

}  // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_create(JNIEnv*, jclass, jint sampleRate) {
    try {return reinterpret_cast<jlong>(new Handle(sampleRate));}
    catch(const std::bad_alloc&) {return 0;}
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_destroy(JNIEnv*, jclass, jlong handle) {
    delete fromJ(handle);
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_setSampleRate(JNIEnv*, jclass, jlong handle, jint sampleRate) {
    if (Handle* h = fromJ(handle)) h->engine.setSampleRate(sampleRate);
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_reset(JNIEnv*, jclass, jlong handle) {
    if (Handle* h = fromJ(handle)) h->engine.requestReset();
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_setParams(JNIEnv* env, jclass, jlong handle, jfloatArray values) {
    Handle* h = fromJ(handle);
    if (h == nullptr || values == nullptr) return;
    const jsize n = std::min<jsize>(env->GetArrayLength(values), pvb::P_COUNT);
    float v[pvb::P_COUNT];
    pvb::defaultParams(v);
    env->GetFloatArrayRegion(values, 0, n, v);
    if(v[pvb::P_P1PPP]>=.5f && env->GetArrayLength(values)!=pvb::P_COUNT)return;
    h->engine.setParams(v, pvb::P_COUNT);
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_processFloat(JNIEnv* env, jclass, jlong handle,
                                                                     jfloatArray input, jfloatArray output, jint length) {
    if (input == nullptr || output == nullptr) return;
    jsize len = std::min(env->GetArrayLength(input), env->GetArrayLength(output));
    if (length >= 0) len = std::min<jsize>(len, length);
    if (len <= 0) return;

    Handle* h = fromJ(handle);
    std::array<float,Handle::kSamples> fallback{};
    float* buf=h?h->floats.data():fallback.data();
    for(jsize offset=0;offset<len;) {
        const jsize n=std::min<jsize>(Handle::kSamples,len-offset);
        env->GetFloatArrayRegion(input,offset,n,buf);
        if(h)h->engine.process(buf,n/2);
        env->SetFloatArrayRegion(output,offset,n,buf);
        offset+=n; // kSamples is even; only the final chunk can contain an odd sample.
    }
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_processShort(JNIEnv* env, jclass, jlong handle,
                                                                     jshortArray input, jshortArray output, jint length) {
    if (input == nullptr || output == nullptr) return;
    jsize len = std::min(env->GetArrayLength(input), env->GetArrayLength(output));
    if (length >= 0) len = std::min<jsize>(len, length);
    if (len <= 0) return;

    Handle* h = fromJ(handle);
    std::array<int16_t,Handle::kSamples> fallback{};
    int16_t* in=h?h->shortsIn.data():fallback.data();
    int16_t* out=h?h->shortsOut.data():fallback.data();
    for(jsize offset=0;offset<len;) {
        const jsize n=std::min<jsize>(Handle::kSamples,len-offset);
        env->GetShortArrayRegion(input,offset,n,reinterpret_cast<jshort*>(in));
        if(h)h->engine.processInt16(in,out,n/2);
        if(n%2)out[n-1]=in[n-1];
        env->SetShortArrayRegion(output,offset,n,reinterpret_cast<const jshort*>(out));offset+=n;
    }
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_setDiagnosticCapture(JNIEnv*, jclass, jlong handle, jboolean enabled) {
    if (Handle* h = fromJ(handle)) h->engine.setDiagnosticCapture(enabled == JNI_TRUE);
}

JNIEXPORT jboolean JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_copyDiagnostic(JNIEnv* env, jclass, jlong handle,
        jfloatArray layer, jfloatArray full, jfloatArray trace, jint samples) {
    Handle* h = fromJ(handle);
    if (!h || !layer || !full || !trace || samples <= 0 || samples > pvb::Engine::kDiagnosticSamples ||
        env->GetArrayLength(layer) < samples || env->GetArrayLength(full) < samples ||
        env->GetArrayLength(trace) != pvb::Engine::kDiagnosticFields) return JNI_FALSE;
    if (!h->engine.copyDiagnostic(h->diagnosticLayer, h->diagnosticFull, samples, h->diagnosticTrace,
                                  pvb::Engine::kDiagnosticFields)) return JNI_FALSE;
    env->SetFloatArrayRegion(layer, 0, samples, h->diagnosticLayer);
    env->SetFloatArrayRegion(full, 0, samples, h->diagnosticFull);
    env->SetFloatArrayRegion(trace, 0, pvb::Engine::kDiagnosticFields, h->diagnosticTrace);
    return JNI_TRUE;
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_readMeters(JNIEnv* env, jclass, jlong handle, jfloatArray out) {
    Handle* h = fromJ(handle);
    if (h == nullptr || out == nullptr) return;
    float m[pvb::M_COUNT];
    h->engine.readMeters(m, pvb::M_COUNT);
    const jsize n = std::min<jsize>(env->GetArrayLength(out), pvb::M_COUNT);
    env->SetFloatArrayRegion(out, 0, n, m);
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_copyHarmonicTrace(JNIEnv* env,jclass,jlong handle,jfloatArray out) {
    Handle* h=fromJ(handle);
    constexpr int capacity=pvb::HarmonicTrace::kBlockRows*pvb::HarmonicTrace::kFields;
    if(!h || !out || env->GetArrayLength(out)!=capacity) return -3;
    const int rows=h->engine.copyHarmonicTrace(h->harmonic,capacity);
    if(rows>0) env->SetFloatArrayRegion(out,0,rows*pvb::HarmonicTrace::kFields,h->harmonic);
    return rows;
}

// Developer-mode meters (Engine::copyDevMeters); out must hold devMeterSize() floats. Returns the floats written.
JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_copyDevMeters(JNIEnv* env, jclass, jlong handle, jfloatArray out) {
    Handle* h = fromJ(handle);
    constexpr int n = pvb::Engine::kDevMeterSize;
    if (!h || !out || env->GetArrayLength(out) != n) return 0;
    float buf[n];
    const int r = h->engine.copyDevMeters(buf, n);
    if (r > 0) env->SetFloatArrayRegion(out, 0, r, buf);
    return r;
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_devMeterSize(JNIEnv*, jclass) {
    return pvb::Engine::kDevMeterSize;
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_latency(JNIEnv*, jclass, jlong handle) {
    Handle* h = fromJ(handle);
    return h ? h->engine.latencyFrames() : 0;
}

// Loudness-match gain in dB once measured; NaN while it is still the seed (or for a null handle).
JNIEXPORT jfloat JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_matchDb(JNIEnv*, jclass, jlong handle) {
    Handle* h = fromJ(handle);
    if (!h || !h->engine.matchMeasured()) return std::numeric_limits<float>::quiet_NaN();
    return h->engine.matchDb();
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_openMs(JNIEnv*, jclass, jlong handle, jint tag) {
    Handle* h = fromJ(handle);
    return h ? h->engine.openMs(tag) : -1;
}

// Spectrum analysis (see Engine::analyze). The four point arrays must have the same length (2..1024).
JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_analyze(JNIEnv* env, jclass, jlong handle, jfloatArray inDb,
                                                                jfloatArray outDb, jfloatArray diffDb, jfloatArray eqDb,
                                                                jfloatArray info, jdouble dtSeconds) {
    Handle* h = fromJ(handle);
    if (h == nullptr || inDb == nullptr || outDb == nullptr || diffDb == nullptr || eqDb == nullptr) return 0;
    const jsize n = env->GetArrayLength(inDb);
    if (n < 2 || n > pvb::kAnaMaxPoints || env->GetArrayLength(outDb) != n || env->GetArrayLength(diffDb) != n ||
        env->GetArrayLength(eqDb) != n) {
        return 0;
    }
    float a[pvb::kAnaMaxPoints], b[pvb::kAnaMaxPoints], c[pvb::kAnaMaxPoints], d[pvb::kAnaMaxPoints];
    float inf[pvb::A_COUNT];
    const int r = h->engine.analyze(a, b, c, d, n, inf, pvb::A_COUNT, dtSeconds);
    if (r <= 0) return 0;
    env->SetFloatArrayRegion(inDb, 0, n, a);
    env->SetFloatArrayRegion(outDb, 0, n, b);
    env->SetFloatArrayRegion(diffDb, 0, n, c);
    env->SetFloatArrayRegion(eqDb, 0, n, d);
    if (info != nullptr) {
        const jsize ni = std::min<jsize>(env->GetArrayLength(info), pvb::A_COUNT);
        env->SetFloatArrayRegion(info, 0, ni, inf);
    }
    return r;
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_anaInfoCount(JNIEnv*, jclass) {
    return pvb::A_COUNT;
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_paramCount(JNIEnv*, jclass) {
    return pvb::P_COUNT;
}

JNIEXPORT jint JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_meterCount(JNIEnv*, jclass) {
    return pvb::M_COUNT;
}

}  // extern "C"


extern "C" JNIEXPORT jboolean JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_loadStableWeights(JNIEnv* env,jclass,jlong handle,jbyteArray data){
    auto* h=fromJ(handle);if(!h || !data || env->GetArrayLength(data)!=531208)return JNI_FALSE;
    jbyte* bytes=env->GetByteArrayElements(data,nullptr);if(!bytes)return JNI_FALSE;
    bool ok=h->engine.loadStableWeights(reinterpret_cast<unsigned char*>(bytes),531208);
    env->ReleaseByteArrayElements(data,bytes,JNI_ABORT);return ok?JNI_TRUE:JNI_FALSE;
}

// Lifecycle entry: caller has joined the previous audio generation before calling.
extern "C" JNIEXPORT jboolean JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_prepareStageC(JNIEnv* env,jclass,jlong handle,jint mode,jbyteArray data,jboolean worker,jboolean telemetry,jint rate){
    auto* h=fromJ(handle);if(!h)return JNI_FALSE;
    const jsize n=data?env->GetArrayLength(data):0;
    jbyte* bytes=data?env->GetByteArrayElements(data,nullptr):nullptr;
    if(data && !bytes)return JNI_FALSE;
    bool ok=false;
    try {ok=h->engine.prepareStageC(mode,reinterpret_cast<unsigned char*>(bytes),n,worker==JNI_TRUE,telemetry==JNI_TRUE,rate);}
    catch(...) {ok=false;}
    if(bytes)env->ReleaseByteArrayElements(data,bytes,JNI_ABORT);
    return ok?JNI_TRUE:JNI_FALSE;
}
extern "C" JNIEXPORT jboolean JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_copyStageC(JNIEnv* env,jclass,jlong handle,jlongArray out){
    auto* h=fromJ(handle);
    if(!h || !out || env->GetArrayLength(out)!=pvb::Engine::kStageCSize)return JNI_FALSE;
    int64_t values[pvb::Engine::kStageCSize];h->engine.copyStageC(values);
    jlong converted[pvb::Engine::kStageCSize];
    for(int i=0;i<pvb::Engine::kStageCSize;++i)converted[i]=values[i];
    env->SetLongArrayRegion(out,0,pvb::Engine::kStageCSize,converted);return JNI_TRUE;
}

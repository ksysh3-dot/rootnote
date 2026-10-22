// JNI bridge for the PVB speaker engine (Kotlin side: me.timschneeberger.rootlessjamesdsp.pvb.PvbNative).
//
// Audio arrays are copied into an engine-owned buffer with Get/Set<Type>ArrayRegion, so no Java array
// is pinned while processing and the buffer is only reallocated when a longer block than ever before
// arrives (never in steady state).
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include <jni.h>

#include <algorithm>
#include <limits>
#include <new>
#include <vector>

#include "pvb_engine.h"

namespace {

struct Handle {
    explicit Handle(int sampleRate) : engine(sampleRate) {}
    pvb::Engine engine;
    std::vector<float> floats;
    std::vector<int16_t> shortsIn, shortsOut;
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
    Handle* h = new (std::nothrow) Handle(sampleRate);
    return reinterpret_cast<jlong>(h);
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
    if (h == nullptr) {  // no engine: pass through
        std::vector<float> tmp(static_cast<size_t>(len));
        env->GetFloatArrayRegion(input, 0, len, tmp.data());
        env->SetFloatArrayRegion(output, 0, len, tmp.data());
        return;
    }

    if (h->floats.size() < static_cast<size_t>(len)) h->floats.resize(static_cast<size_t>(len));
    float* buf = h->floats.data();
    env->GetFloatArrayRegion(input, 0, len, buf);
    const jsize frames = len / 2;
    h->engine.process(buf, frames);
    env->SetFloatArrayRegion(output, 0, len, buf);  // an odd trailing sample passes through unchanged
}

JNIEXPORT void JNICALL
Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_processShort(JNIEnv* env, jclass, jlong handle,
                                                                     jshortArray input, jshortArray output, jint length) {
    if (input == nullptr || output == nullptr) return;
    jsize len = std::min(env->GetArrayLength(input), env->GetArrayLength(output));
    if (length >= 0) len = std::min<jsize>(len, length);
    if (len <= 0) return;

    Handle* h = fromJ(handle);
    if (h == nullptr) {
        std::vector<jshort> tmp(static_cast<size_t>(len));
        env->GetShortArrayRegion(input, 0, len, tmp.data());
        env->SetShortArrayRegion(output, 0, len, tmp.data());
        return;
    }

    if (h->shortsIn.size() < static_cast<size_t>(len)) {
        h->shortsIn.resize(static_cast<size_t>(len));
        h->shortsOut.resize(static_cast<size_t>(len));
    }
    env->GetShortArrayRegion(input, 0, len, reinterpret_cast<jshort*>(h->shortsIn.data()));
    const jsize frames = len / 2;
    h->engine.processInt16(h->shortsIn.data(), h->shortsOut.data(), frames);
    if (len % 2) h->shortsOut[static_cast<size_t>(len - 1)] = h->shortsIn[static_cast<size_t>(len - 1)];
    env->SetShortArrayRegion(output, 0, len, reinterpret_cast<const jshort*>(h->shortsOut.data()));
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


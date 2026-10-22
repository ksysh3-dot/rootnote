/*
 * Host C API for the JamesDSP engine (libjamesdsp submodule), for the JamesDSP -> PVB chain test
 * (test_jdsp_chain.py). It calls the same libjamesdsp functions as app/src/main/cpp/libjamesdsp-wrapper with the
 * same arguments; only the JNI layer is left out. Built by build_host_jdsp.sh.
 */
#include <stdlib.h>
#include <string.h>
#include "jdsp_header.h"
#include "../../app/src/main/cpp/EELStdOutExtension.h"

static int g_global = 0;

void* jdsp_create(int sr) {
    if (!g_global) { JamesDSPGlobalMemoryAllocation(); g_global = 1; }
    JamesDSPLib* d = (JamesDSPLib*)malloc(sizeof(JamesDSPLib));
    memset(d, 0, sizeof(JamesDSPLib));
    JamesDSPInit(d, 128, 48000);          /* same as JamesDspWrapper.alloc */
    JamesDSPSetSampleRate(d, (float)sr, 0);
    return d;
}

void jdsp_destroy(void* p) { JamesDSPFree((JamesDSPLib*)p); free(p); }

/* JamesDspLocalEngine.setOutputControl: limiter threshold (dB) and release (ms), then the post gain (dB). */
void jdsp_set_output(void* p, float thresholdDb, float releaseMs, float postGainDb) {
    JLimiterSetCoefficients((JamesDSPLib*)p, thresholdDb, releaseMs);
    JamesDSPSetPostGain((JamesDSPLib*)p, postGainDb);
}

/* setMultiEqualizer: 15 frequencies then 15 gains (dB). */
void jdsp_set_eq(void* p, int enable, int filterType, int interpolationMode, double* bands30) {
    JamesDSPLib* d = (JamesDSPLib*)p;
    if (enable) {
        MultimodalEqualizerAxisInterpolation(d, interpolationMode, filterType, bands30, bands30 + 15);
        MultimodalEqualizerEnable(d, 1);
    } else {
        MultimodalEqualizerDisable(d);
    }
}

/* setCompander: 7 frequencies then 7 gains. */
void jdsp_set_compander(void* p, int enable, float timeConstant, int granularity, int tfTransforms, double* bands14) {
    JamesDSPLib* d = (JamesDSPLib*)p;
    if (enable) {
        CompressorSetParam(d, timeConstant, granularity, tfTransforms, 0);
        CompressorSetGain(d, bands14, bands14 + 7, 1);
        CompressorEnable(d, 1);
    } else {
        CompressorDisable(d);
    }
}

void jdsp_set_bass(void* p, int enable, float maxGain) {
    JamesDSPLib* d = (JamesDSPLib*)p;
    if (enable) { BassBoostSetParam(d, maxGain); BassBoostEnable(d); }
    else BassBoostDisable(d);
}

/* Interleaved stereo float, [frames] frames (JamesDspWrapper.processFloat passes size / 2). */
void jdsp_process(void* p, const float* in, float* out, int frames) {
    JamesDSPLib* d = (JamesDSPLib*)p;
    d->processFloatMultiplexd(d, (float*)in, out, (size_t)frames);
}

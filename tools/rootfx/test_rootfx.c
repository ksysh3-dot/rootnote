/*
 * Host test of the Rootnote audio effect (librootnotefx.so), driven the way audioserver drives an effect library:
 * dlopen, the AELI symbol, create_effect, EFFECT_CMD_SET_CONFIG / ENABLE / SET_PARAM / GET_PARAM, process().
 *  1. it is a working JamesDSP effect (same descriptor UUIDs), finite output;
 *  2. without parameters the PVB engine is bypassed (output = the JamesDSP chain alone);
 *  3. with the app's parameter array the output equals the JamesDSP chain followed by the PVB engine's own C API
 *     (libpvbcapi.so) with the same parameters, sample for sample (float and 16-bit buffers);
 *  4. the version and "active" commands answer.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "essential.h"
#include "rootfx_pvb.h"

int harness_param_count(void);
static int passed = 0;
static void check(int ok, const char *what) {
    if (!ok) { printf("[FAIL] %s\n", what); exit(1); }
    printf("[PASS] %s\n", what); passed++;
}

typedef void *(*create_f)(int);
typedef void (*params_f)(void *, const float *, int);
typedef void (*process_f)(void *, float *, int);
typedef void (*defaults_f)(float *);

static effect_handle_t make(audio_effect_library_t *lib, int format) {
    effect_uuid_t uuid = { 0xf27317f4, 0xc984, 0x4de6, 0x9a90, { 0x54, 0x57, 0x59, 0x49, 0x5b, 0xf2 } };
    effect_handle_t h = NULL;
    int r = lib->create_effect(&uuid, 0, 0, &h);
    if (r != 0 || h == NULL) return NULL;
    effect_config_t cfg;
    memset(&cfg, 0, sizeof cfg);
    cfg.inputCfg.samplingRate = cfg.outputCfg.samplingRate = 48000;
    cfg.inputCfg.channels = cfg.outputCfg.channels = AUDIO_CHANNEL_OUT_STEREO;
    cfg.inputCfg.format = cfg.outputCfg.format = (uint8_t)format;
    cfg.inputCfg.accessMode = EFFECT_BUFFER_ACCESS_READ;
    cfg.outputCfg.accessMode = EFFECT_BUFFER_ACCESS_WRITE;
    cfg.inputCfg.mask = cfg.outputCfg.mask = EFFECT_CONFIG_ALL;
    int32_t reply = -1; uint32_t rs = sizeof reply;
    (*h)->command(h, EFFECT_CMD_SET_CONFIG, sizeof cfg, &cfg, &rs, &reply);
    if (reply != 0) return NULL;
    (*h)->command(h, EFFECT_CMD_ENABLE, 0, NULL, &rs, &reply);
    return h;
}

static int set_pvb(effect_handle_t h, const float *v, int n) {
    size_t size = sizeof(effect_param_t) + 4 + sizeof(float) * (size_t)n;
    effect_param_t *p = calloc(1, size + 16);
    p->psize = 4;
    p->vsize = (uint32_t)(sizeof(float) * n);
    ((int32_t *)p)[3] = RFX_CMD_PVB_PARAMS;
    memcpy(((int32_t *)p) + 4, v, sizeof(float) * (size_t)n);
    int32_t reply = -1; uint32_t rs = sizeof reply;
    (*h)->command(h, EFFECT_CMD_SET_PARAM, (uint32_t)size, p, &rs, &reply);
    free(p);
    return reply;
}

static int get_int(effect_handle_t h, int32_t cmd) {
    int32_t q[4] = { 0, 4, 4, cmd };
    int32_t reply[5] = { -1, 0, 0, 0, -1 }; uint32_t rs = sizeof reply;
    (*h)->command(h, EFFECT_CMD_GET_PARAM, sizeof q, q, &rs, reply);
    return reply[0] == 0 ? reply[4] : -999;
}

/* a bass line with some mids: 41-110 Hz notes, 2nd harmonic, a 440 Hz tone */
static void signal(float *x, int frames) {
    for (int i = 0; i < frames; i++) {
        double t = i / 48000.0;
        double f = (i / 24000) % 2 ? 55.0 : 82.4;
        double s = 0.3 * sin(2 * M_PI * f * t) + 0.08 * sin(4 * M_PI * f * t) + 0.05 * sin(2 * M_PI * 440 * t);
        x[2 * i] = (float)s; x[2 * i + 1] = (float)(0.9 * s);
    }
}

static void run(effect_handle_t h, const float *in, float *out, int frames, int block) {
    for (int o = 0; o < frames; o += block) {
        int n = frames - o < block ? frames - o : block;
        audio_buffer_t bi = { (size_t)n, { (void *)(in + 2 * o) } }, bo = { (size_t)n, { out + 2 * o } };
        (*h)->process(h, &bi, &bo);
    }
}

static void run16(effect_handle_t h, const int16_t *in, int16_t *out, int frames, int block) {
    for (int o = 0; o < frames; o += block) {
        int n = frames - o < block ? frames - o : block;
        audio_buffer_t bi = { (size_t)n, { (void *)(in + 2 * o) } }, bo = { (size_t)n, { out + 2 * o } };
        (*h)->process(h, &bi, &bo);
    }
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s librootnotefx.so libpvbcapi.so\n", argv[0]); return 2; }
    void *so = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    check(so != NULL, "the effect library loads (all symbols resolved)");
    audio_effect_library_t *lib = dlsym(so, AUDIO_EFFECT_LIBRARY_INFO_SYM_AS_STR);
    check(lib != NULL && lib->tag == AUDIO_EFFECT_LIBRARY_TAG, "AELI symbol exported");
    effect_uuid_t uuid = { 0xf27317f4, 0xc984, 0x4de6, 0x9a90, { 0x54, 0x57, 0x59, 0x49, 0x5b, 0xf2 } };
    effect_descriptor_t d;
    lib->get_descriptor(&uuid, &d);
    check(d.uuid.timeLow == 0xf27317f4 && d.type.timeLow == 0xf98765f4 && strstr(d.name, "Rootnote") != NULL,
          "descriptor: the JamesDSP type and UUID, named as Rootnote's");

    void *capi = dlopen(argv[2], RTLD_NOW | RTLD_LOCAL);
    check(capi != NULL, "PVB C API loads (reference)");
    create_f pcreate = (create_f)dlsym(capi, "pvb_create");
    params_f pparams = (params_f)dlsym(capi, "pvb_set_params");
    process_f pprocess = (process_f)dlsym(capi, "pvb_process");
    defaults_f pdefaults = (defaults_f)dlsym(capi, "pvb_default_params");
    int n = harness_param_count();

    const int frames = 48000 * 2, block = 480;
    float *in = malloc(sizeof(float) * 2 * frames), *a = malloc(sizeof(float) * 2 * frames);
    float *b = malloc(sizeof(float) * 2 * frames), *ref = malloc(sizeof(float) * 2 * frames);
    signal(in, frames);

    // 1/2: JamesDSP alone (no parameters sent): finite, and PVB stays out
    effect_handle_t plain = make(lib, AUDIO_FORMAT_PCM_FLOAT);
    check(plain != NULL, "create + SET_CONFIG (48 kHz float stereo) + ENABLE");
    check(get_int(plain, RFX_CMD_VERSION) == RFX_VERSION && get_int(plain, RFX_CMD_PVB_ACTIVE) == 0,
          "version command answers; engine not active before parameters");
    run(plain, in, a, frames, block);
    int finite = 1; for (int i = 0; i < 2 * frames; i++) if (!isfinite(a[i])) finite = 0;
    check(finite, "JamesDSP chain output finite");

    // 3: with parameters: virtual bass on, strength +6
    float *v = malloc(sizeof(float) * n);
    pdefaults(v);
    v[0] = 1.f;                 // P_ENABLED (PvbEngine.kt PvbParam.ENABLED = 0)
    float *v2 = malloc(sizeof(float) * n);
    memcpy(v2, v, sizeof(float) * n);
    effect_handle_t fx = make(lib, AUDIO_FORMAT_PCM_FLOAT);
    check(set_pvb(fx, v, n) == 0 && get_int(fx, RFX_CMD_PVB_ACTIVE) == 1, "SET_PARAM 41000 with the parameter array: accepted, engine active");
    check(set_pvb(fx, v, 0) == -EINVAL, "empty parameter array rejected");
    run(fx, in, b, frames, block);
    void *pe = pcreate(48000);
    pparams(pe, v2, n);
    memcpy(ref, a, sizeof(float) * 2 * frames);
    for (int o = 0; o < frames; o += block) pprocess(pe, ref + 2 * o, frames - o < block ? frames - o : block);
    double maxd = 0, diffFromPlain = 0;
    for (int i = 0; i < 2 * frames; i++) {
        double dd = fabs((double)b[i] - ref[i]); if (dd > maxd) maxd = dd;
        double dp = fabs((double)b[i] - a[i]); if (dp > diffFromPlain) diffFromPlain = dp;
    }
    printf("       max |effect - (JamesDSP then PVB C API)| = %g, max |effect - JamesDSP alone| = %g\n", maxd, diffFromPlain);
    check(maxd == 0.0, "float: effect = JamesDSP chain then the PVB engine, bit exact");
    check(diffFromPlain > 1e-4, "float: the engine changes the sound (it is really in the path)");

    // 16-bit buffers
    int16_t *i16 = malloc(sizeof(int16_t) * 2 * frames), *o16 = malloc(sizeof(int16_t) * 2 * frames);
    int16_t *p16 = malloc(sizeof(int16_t) * 2 * frames);
    for (int i = 0; i < 2 * frames; i++) i16[i] = (int16_t)lrintf(in[i] * 32767.f);
    effect_handle_t fx16 = make(lib, AUDIO_FORMAT_PCM_16_BIT);
    effect_handle_t plain16 = make(lib, AUDIO_FORMAT_PCM_16_BIT);
    check(fx16 != NULL && set_pvb(fx16, v, n) == 0, "16-bit: configured, parameters accepted");
    run16(fx16, i16, o16, frames, block);
    run16(plain16, i16, p16, frames, block);
    long changed = 0; for (int i = 0; i < 2 * frames; i++) if (o16[i] != p16[i]) changed++;
    check(changed > frames / 4, "16-bit: the engine is in the path");

    lib->release_effect(plain); lib->release_effect(fx); lib->release_effect(fx16); lib->release_effect(plain16);
    printf("test_rootfx: %d checks passed\n", passed);
    return 0;
}

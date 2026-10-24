/*
 * Rootnote root build: the PVB engine (libpvb) behind a C interface, for the JamesDSP audio effect wrapper
 * (jamesdsp_rootnote.c). The effect runs inside audioserver; the app sends the engine's parameter array with
 * EFFECT_CMD_SET_PARAM (RFX_CMD_PVB_PARAMS), exactly the array PvbEngineParams.encode() builds for the rootless build.
 */
#ifndef ROOTFX_PVB_H
#define ROOTFX_PVB_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/** SET_PARAM: psize 4 (this code), vsize 4 x n: the engine's float parameter array (PvbParam order). */
#define RFX_CMD_PVB_PARAMS 41000
/** GET_PARAM: psize 4, vsize 4: RFX_VERSION (the app tells this library from the stock JamesDSP one). */
#define RFX_CMD_VERSION 41002
/** GET_PARAM: psize 4, vsize 4: 1 once parameters arrived and the engine runs, else 0. */
#define RFX_CMD_PVB_ACTIVE 41003
/** Interface version of this library (bump when the commands or the parameter array change). */
#define RFX_VERSION 1

void* rfx_pvb_create(int sampleRate);
void rfx_pvb_destroy(void* e);
void rfx_pvb_set_sample_rate(void* e, int sampleRate);
void rfx_pvb_set_params(void* e, const float* values, int count);
void rfx_pvb_process_f32(void* e, float* interleavedStereo, int frames);
void rfx_pvb_process_s16(void* e, int16_t* interleavedStereo, int frames);
/** Number of parameters the engine expects (P_COUNT). */
int rfx_pvb_param_count(void);

#ifdef __cplusplus
}
#endif
#endif

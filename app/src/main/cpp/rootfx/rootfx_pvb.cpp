// Rootnote root build: C interface of the PVB engine for the audio effect (rootfx_pvb.h).
#include "rootfx_pvb.h"
#include "pvb_engine.h"

extern "C" {

void* rfx_pvb_create(int sampleRate) { return new pvb::Engine(sampleRate > 0 ? sampleRate : 48000); }

void rfx_pvb_destroy(void* e) { delete static_cast<pvb::Engine*>(e); }

void rfx_pvb_set_sample_rate(void* e, int sampleRate) {
    if (e && sampleRate > 0) static_cast<pvb::Engine*>(e)->setSampleRate(sampleRate);
}

void rfx_pvb_set_params(void* e, const float* values, int count) {
    if (e && values && count > 0) static_cast<pvb::Engine*>(e)->setParams(values, count);
}

void rfx_pvb_process_f32(void* e, float* io, int frames) {
    if (e && io && frames > 0) static_cast<pvb::Engine*>(e)->process(io, frames);
}

void rfx_pvb_process_s16(void* e, int16_t* io, int frames) {
    if (e && io && frames > 0) static_cast<pvb::Engine*>(e)->processInt16(io, io, frames);
}

int rfx_pvb_param_count(void) { return pvb::P_COUNT; }

}

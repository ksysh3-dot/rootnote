// Host-only C API around pvb::Engine for the Python test suite (ctypes). Not part of the app build.
#include "pvb_engine.h"
#include "pvb_vb.h"
#include "pvb_vb_tables.h"
#include "pvb_vb_detail.h"
#include "pvb_track_assignment.h"

namespace pvb {
// Host-only injection, not a second synthesizer. Analysis, HPSS, bus gain,
// OLA placement, filters and device playback are deliberately outside this probe.
struct HarmonicRendererTestAccess {
    static void add(VbHpv& v,int64_t centre,const double* grain) {v.addGrain52(centre,grain,0.);}
    static double take(VbHpv& v,int64_t index) {double sample,amplitude;v.takeGrain52(index,sample,amplitude);return sample;}
    static int grain(VbHpv& v, const double* fit, int mode, double* out) {
        if (!fit || !out || mode<0 || mode>3) return -1;
        for(int j=0;j<20;++j) if(!std::isfinite(fit[j])) return -1;
        if(fit[0]<=0 || fit[1]<25 || fit[1]>190 || fit[9]!=1) return -1;
        VbHpv::Track52 tr;
        tr.a=fit[0]; tr.f=fit[1]; tr.phi=fit[2]; tr.dadt=fit[3]; tr.dfdt=fit[4];
        tr.fade=tr.life=1;
        auto& m=tr.modulation;
        m.amplitude=fit[0];m.frequency=fit[1];m.phase=fit[2];m.amplitudeSlope=fit[3];m.frequencySlope=fit[4];
        m.carrier=fit[5];m.slope=fit[6];m.valid=true;
        for(int j=0;j<5;++j) m.z[j]={fit[10+2*j],fit[11+2*j]};
        if(std::abs(m.z[0])<1e-12) return -1;
        double src[2][256]={}; const int ns[2]={0,7};
        for(int j=0;j<7;++j) {tr.off[j]=vbt::kPsi[j];src[1][j]=(j+2)*tr.f;}
        v.modulationMode_=mode;
        std::fill(out,out+32,0.);double nominalAmplitude=0;
        v.renderTrack52(tr,src,ns,true,false,0,out,nominalAmplitude);
        return 32;
    }
};
struct RendererProbe {
    VbHpv vb{true,false};
    int64_t nextCentre=16,readPosition=0,finalized=0;
    bool ended=false;
    void reset() {vb.reset();nextCentre=16;readPosition=finalized=0;ended=false;}
};
struct HostStageCapture {
    Engine* engine;
    double* rows;
    int capacity,count=0;
    bool overflow=false;
    HostStageCapture(Engine* e,int n):engine(e),rows(new double[static_cast<size_t>(n)*StageCapture52::kFields]),capacity(n) {}
    ~HostStageCapture() {delete[] rows;}
    static void push(void* user,uint64_t index,const double* values) {
        auto& s=*static_cast<HostStageCapture*>(user);
        if(s.count>=s.capacity) {s.overflow=true;return;}
        double* row=s.rows+static_cast<size_t>(s.count++)*StageCapture52::kFields;
        row[0]=static_cast<double>(index&0xffffffffu);row[1]=static_cast<double>(index>>32);
        std::copy(values,values+StageCapture52::kValues,row+2);
    }
};
}

extern "C" {

int pvb_set_p1plus_research(void* e,unsigned flags) {
    if(!e || flags>15 || ((flags&8) && !(flags&4))) return 0;
    static_cast<pvb::Engine*>(e)->setP1PlusResearch(flags);return 1;
}

int pvb_set_p1pp_research_params(void* e,int hold,double historyDb,int steadyHops,double steadyA,double releaseStrength) {
    if(!e || hold<1 || steadyHops<1 || steadyA<=0 || releaseStrength<0) return 0;
    static_cast<pvb::Engine*>(e)->setP1PPResearchParams(hold,historyDb,steadyHops,steadyA,releaseStrength);return 1;
}

int pvb_set_p1pp_impact_research(void* e,int mode) {
    if(!e || mode<0 || mode>8) return 0;
    static_cast<pvb::Engine*>(e)->setP1PPImpactResearch(mode);return 1;
}

int pvb_stage_fields() {return pvb::StageCapture52::kFields;}
// Attach before process and detach before destroying the engine. Allocation and
// copying happen outside the audio call. Overflow is explicit, never truncated.
void* pvb_stage_attach(void* e,unsigned flags,int capacity) {
    const unsigned predictors=pvb::StageTrackLinear|pvb::StageTrackBurg;
    if(!e || flags>8191 || (flags&predictors)==predictors ||
       ((flags&pvb::StageOscillatorCorrect) && !(flags&pvb::StageOscillator)) ||
       ((flags&predictors) && !(flags&pvb::StageGlobalTrack)) || capacity<=0 || capacity>2000000) return nullptr;
    auto* s=new pvb::HostStageCapture(static_cast<pvb::Engine*>(e),capacity);
    s->engine->setStageResearch(flags,pvb::HostStageCapture::push,s);return s;
}
// Same state used by production P2-O; probe inputs are endpoint controls,
// not audio analysis results. out contains16 audio+16 nominal samples.
void* pvb_oscillator_probe_create() {return new pvb::oscillator52::State;}
void pvb_oscillator_probe_destroy(void* p) {delete static_cast<pvb::oscillator52::State*>(p);}
void pvb_oscillator_probe_reset(void* p) {if(p) *static_cast<pvb::oscillator52::State*>(p)={};}
int pvb_oscillator_probe_hop(void* p,double f,const double* amplitudes,const double* phases,double nominal,int correct,double* out) {
    if(!p || !amplitudes || !phases || !out || !std::isfinite(f) || f<20 || f>200 ||
       !std::isfinite(nominal) || nominal<0 || (correct!=0 && correct!=1)) return -1;
    for(int j=0;j<7;++j) if(!std::isfinite(amplitudes[j]) || amplitudes[j]<0 || !std::isfinite(phases[j])) return -1;
    std::fill(out,out+32,0.);
    static_cast<pvb::oscillator52::State*>(p)->add(f,amplitudes,phases,nominal,correct!=0,out,out+16);
    return 16;
}
int pvb_stage_copy(void* p,double* out,int capacity) {
    if(!p || !out) return -1;
    auto& s=*static_cast<pvb::HostStageCapture*>(p);
    if(s.overflow || capacity<s.count*pvb::StageCapture52::kFields) return -2;
    std::copy(s.rows,s.rows+static_cast<size_t>(s.count)*pvb::StageCapture52::kFields,out);return s.count;
}
void pvb_stage_detach(void* p) {
    if(p) {auto* s=static_cast<pvb::HostStageCapture*>(p);s->engine->setStageResearch(0);delete s;}
}

// v1 fit layout matches pvb_modulation_fit's20 doubles. Explicitly open grid,
// fade/life=1 and table phase offsets; output is32 raw core samples at3kHz.
void* pvb_renderer_probe_create() {
    auto* v=new pvb::RendererProbe;
    if(!v->vb.configure(48000)) {delete v;return nullptr;}
    return v;
}
void pvb_renderer_probe_destroy(void* p) {delete static_cast<pvb::RendererProbe*>(p);}
int pvb_renderer_probe_grain(void* p,const double* fit,int mode,double* out,int capacity) {
    if(!p || capacity<32) return -1;
    return pvb::HarmonicRendererTestAccess::grain(static_cast<pvb::RendererProbe*>(p)->vb,fit,mode,out);
}
void pvb_renderer_probe_reset(void* p) {if(p) static_cast<pvb::RendererProbe*>(p)->reset();}
// Push one16-sample control hop. A null fit means silence. The shared production
// OLA only finalizes samples before the next grain begins; no future reads.
int pvb_renderer_probe_push(void* p,const double* fit,int mode) {
    if(!p || mode<0 || mode>3) return -1;
    auto& s=*static_cast<pvb::RendererProbe*>(p);
    if(s.ended) return -1;
    if(s.nextCentre+16-s.readPosition>512) return -3;
    double grain[32]={};
    if(fit && pvb::HarmonicRendererTestAccess::grain(s.vb,fit,mode,grain)!=32) return -1;
    pvb::HarmonicRendererTestAccess::add(s.vb,s.nextCentre,grain);
    s.finalized=s.nextCentre;s.nextCentre+=16;return 16;
}
int pvb_renderer_probe_finish(void* p) {
    if(!p) return -1;
    auto& s=*static_cast<pvb::RendererProbe*>(p);
    s.ended=true;s.finalized=s.nextCentre>16?s.nextCentre:0;
    return static_cast<int>(s.finalized-s.readPosition);
}
int pvb_renderer_probe_available(void* p) {
    if(!p) return -1;
    auto& s=*static_cast<pvb::RendererProbe*>(p);
    return static_cast<int>(s.finalized-s.readPosition);
}
int pvb_renderer_probe_read(void* p,double* out,int count) {
    if(!p || count<0 || count>512 || (!out && count)) return -1;
    auto& s=*static_cast<pvb::RendererProbe*>(p);
    if(count>s.finalized-s.readPosition) return -2;
    for(int j=0;j<count;++j) out[j]=pvb::HarmonicRendererTestAccess::take(s.vb,s.readPosition++);
    return count;
}

void* pvb_create(int sampleRate) { return new pvb::Engine(sampleRate); }
void pvb_destroy(void* e) { delete static_cast<pvb::Engine*>(e); }
void pvb_set_sample_rate(void* e, int sr) { static_cast<pvb::Engine*>(e)->setSampleRate(sr); }
void pvb_set_params(void* e, const float* v, int n) { static_cast<pvb::Engine*>(e)->setParams(v, n); }
void pvb_process(void* e, float* io, int frames) { static_cast<pvb::Engine*>(e)->process(io, frames); }
void pvb_process_i16(void* e, const short* in, short* out, int frames) {
    static_cast<pvb::Engine*>(e)->processInt16(reinterpret_cast<const int16_t*>(in), reinterpret_cast<int16_t*>(out), frames);
}
void pvb_set_diagnostic_capture(void* e, int enabled) { static_cast<pvb::Engine*>(e)->setDiagnosticCapture(enabled != 0); }
int pvb_copy_diagnostic(void* e, float* layer, float* full, int samples, float* trace, int fields) {
    return static_cast<pvb::Engine*>(e)->copyDiagnostic(layer, full, samples, trace, fields) ? 1 : 0;
}
int pvb_harmonic_fields() { return pvb::HarmonicTrace::kFields; }
int pvb_harmonic_rows() { return pvb::HarmonicTrace::kBlockRows; }
// Developer-mode meters (Engine::copyDevMeters): DM_FIELDS values, then kDevRing (dry, layer) pairs.
int pvb_dev_meter_size() { return pvb::Engine::kDevMeterSize; }
int pvb_dev_meter_fields() { return pvb::Engine::kDevFields; }
int pvb_copy_dev_meters(void* e, float* out, int capacity) {
    return static_cast<pvb::Engine*>(e)->copyDevMeters(out, capacity);
}
int pvb_copy_harmonic(void* e,float* out,int capacity) {
    return static_cast<pvb::Engine*>(e)->copyHarmonicTrace(out,capacity);
}
void pvb_set_continuity_research(void* e,int enabled,int attack,int hold,int release) {
    pvb::ContinuityParams p; p.enabled=enabled!=0; p.attack=attack; p.hold=hold; p.release=release;
    static_cast<pvb::Engine*>(e)->setContinuityResearch(p);
}
// gen-s1s2 research (host only). v: attackMs, releaseMs, onsetReleaseMs, gainReleaseMs,
// burstAttackMs, burstDecayMs, onsetDb, refractoryMs, onsetMode; n may be shorter (defaults kept).
void pvb_set_gen_research(void* e,int envelope,int bursts,const double* v,int n) {
    pvb::GenResearch52 g; g.envelope=envelope!=0; g.bursts=bursts!=0;
    double* f[8]={&g.attackMs,&g.releaseMs,&g.onsetReleaseMs,&g.gainReleaseMs,&g.burstAttackMs,&g.burstDecayMs,&g.onsetDb,&g.refractoryMs};
    for(int j=0;j<n && j<8;++j) *f[j]=v[j];
    if(n>8) g.onsetMode=static_cast<int>(v[8]);
    static_cast<pvb::Engine*>(e)->setGenResearch(g);
}
void pvb_set_modulation_research(void* e,int mode,int tonalOnly) {
    static_cast<pvb::Engine*>(e)->setModulationResearch(mode,tonalOnly!=0);
}
// Direct estimator oracle: x=384 core samples, explicit seed/neighbors, out=20 doubles.
int pvb_modulation_fit(const double* x,double seed,const double* neighbors,int count,double* out) {
    const auto m=pvb::modulation::fit(x,seed,neighbors,count);
    out[0]=m.amplitude;out[1]=m.frequency;out[2]=m.phase;out[3]=m.amplitudeSlope;out[4]=m.frequencySlope;
    out[5]=m.carrier;out[6]=m.slope;out[7]=m.residual;out[8]=m.qrDiagonalRatio;out[9]=m.valid?1:0;
    for(int j=0;j<5;++j) {out[10+2*j]=m.z[j].real();out[11+2*j]=m.z[j].imag();}
    return m.valid?1:0;
}
int pvb_detail_fit(const double* x,double seed,double slope,double* out) {
    if(!x || !out) return -1;
    const auto m=pvb::detail::fit(x,seed,slope);
    out[0]=m.amplitude;out[1]=m.frequency;out[2]=m.phase;out[3]=m.amplitudeSlope;out[4]=m.frequencySlope;
    out[5]=m.carrier;out[6]=m.slope;out[7]=m.residual;out[8]=m.qrDiagonalRatio;out[9]=m.valid?1:0;
    for(int j=0;j<5;++j) {out[10+2*j]=m.z[j].real();out[11+2*j]=m.z[j].imag();}
    return m.valid?1:0;
}
// J2-S host oracle:384 band-filtered samples, output10 scalars +3complex observations.
int pvb_am_family_fit(const double* x,double seed,double* out) {
    if(!x || !out) return -1;
    const auto m=pvb::amfamily::fit(x,seed,pvb::vbt::kBandSos);
    out[0]=m.valid?1:0;out[1]=m.carrier;out[2]=m.rate;out[3]=m.meanAmplitude;out[4]=m.phase;
    out[5]=m.cosine;out[6]=m.sine;out[7]=m.residual;out[8]=m.coherence;out[9]=m.qrRatio;
    for(int j=0;j<3;++j) {out[10+2*j]=m.observed[j].real();out[11+2*j]=m.observed[j].imag();}
    return m.valid?1:0;
}
// Host oracle uses the exact production assignment and state cost. Each state
// is5doubles:frequency,phase,amplitude,life,missing. The caller owns output.
static int trackAssignment(const double* observed,int count,const double* previous,int tracks,int* out,const double* prediction) {
    if(!observed || !previous || !out || count<0 || count>6 || tracks<0 || tracks>12) return -1;
    pvb::assignment52::State a[6],b[12];
    for(int i=0;i<count*5;++i) if(!std::isfinite(observed[i])) return -2;
    for(int i=0;i<tracks*5;++i) if(!std::isfinite(previous[i])) return -2;
    if(prediction) for(int i=0;i<tracks;++i) if(!std::isfinite(prediction[i]) || prediction[i]<=0) return -2;
    for(int i=0;i<count;++i) if(observed[5*i+4]<0 || observed[5*i+4]>100) return -2;
    for(int i=0;i<tracks;++i) if(previous[5*i+4]<0 || previous[5*i+4]>100) return -2;
    for(int i=0;i<count;++i) a[i]={observed[5*i],observed[5*i+1],observed[5*i+2],observed[5*i+3],static_cast<int>(observed[5*i+4])};
    for(int i=0;i<tracks;++i) b[i]={previous[5*i],previous[5*i+1],previous[5*i+2],previous[5*i+3],static_cast<int>(previous[5*i+4])};
    pvb::assignment52::match(a,count,b,tracks,out,prediction);return 0;
}
int pvb_track_assignment(const double* observed,int count,const double* previous,int tracks,int* out) {
    return trackAssignment(observed,count,previous,tracks,out,nullptr);
}
int pvb_track_assignment_predicted(const double* observed,int count,const double* previous,int tracks,const double* prediction,int* out) {
    if(!prediction) return -1;
    return trackAssignment(observed,count,previous,tracks,out,prediction);
}
// Contiguous measured history, oldest first. Output: forecast, raw, used mode,
// limited flag. This oracle is the same fixed-storage predictor as production.
int pvb_track_prediction(const double* history,int count,int horizon,int mode,double* out) {
    if(!history || !out || count<1 || count>32 || horizon<1 || horizon>100 || mode<0 || mode>2) return -1;
    pvb::prediction52::History h;
    for(int i=0;i<count;++i) {if(!std::isfinite(history[i]) || history[i]<20 || history[i]>200) return -2;h.observe(history[i]);}
    const auto p=h.forecast(mode,horizon);out[0]=p.frequency;out[1]=p.raw;out[2]=p.used;out[3]=p.limited?1.:0.;return 0;
}
void pvb_reset(void* e) { static_cast<pvb::Engine*>(e)->requestReset(); }
void pvb_read_meters(void* e, float* out, int n) { static_cast<pvb::Engine*>(e)->readMeters(out, n); }
int pvb_latency(void* e) { return static_cast<pvb::Engine*>(e)->latencyFrames(); }
int pvb_open_ms(void* e, int tag) { return static_cast<pvb::Engine*>(e)->openMs(tag); }
float pvb_match_db(void* e) { return static_cast<pvb::Engine*>(e)->matchDb(); }
int pvb_match_measured(void* e) { return static_cast<pvb::Engine*>(e)->matchMeasured() ? 1 : 0; }
int pvb_param_count() { return pvb::P_COUNT; }
int pvb_meter_count() { return pvb::M_COUNT; }
void pvb_default_params(float* out) { pvb::defaultParams(out); }
double pvb_estimate_phone_gr(double levelDb) { return pvb::estimatePhoneLimiterGr(levelDb); }
int pvb_analyze(void* e, float* in, float* out, float* diff, float* eq, int n, float* info, int nInfo, double dt) {
    return static_cast<pvb::Engine*>(e)->analyze(in, out, diff, eq, n, info, nInfo, dt);
}
int pvb_ana_info_count() { return pvb::A_COUNT; }
double pvb_ana_point_hz(int i, int n) { return pvb::anaPointHz(i, n); }

// Virtual bass modules on their own (layer only), for the comparison with the Python reference.
void* pvb_vb_create(int algo, int sampleRate) {
    if(algo<0 || algo>=pvb::VB_ALGO_COUNT) return nullptr;
    if(algo>=pvb::VB_ALPHA2_P1) {
        auto* m=new pvb::VbHpv(true,true,1);
        if(!m->configure(sampleRate) || !m->setAlpha2Profile(algo)) {delete m;return nullptr;}
        return m;
    }
    pvb::VbModule* m = algo == pvb::VB_BANKSTOWN ? static_cast<pvb::VbModule*>(new pvb::VbBankstown())
                                                 : static_cast<pvb::VbModule*>(new pvb::VbHpv(
                                                     algo >= pvb::VB_HPV52M && algo <= pvb::VB_GENTLE_ADAPTIVE,
                                                     algo >= pvb::VB_GENTLE && algo <= pvb::VB_GENTLE_ADAPTIVE,
                                                     algo == pvb::VB_GENTLE_STRONG ? 1 : algo == pvb::VB_GENTLE_ADAPTIVE ? 2 : 0));
    if (!m->configure(sampleRate)) {
        delete m;
        return nullptr;
    }
    return m;
}
void pvb_vb_destroy(void* m) { delete static_cast<pvb::VbModule*>(m); }
int pvb_vb_latency(void* m) { return static_cast<pvb::VbModule*>(m)->latencyFrames(); }
void pvb_vb_reset(void* m) { static_cast<pvb::VbModule*>(m)->reset(); }
void pvb_vb_process(void* m, const double* inL, const double* inR, double* outL, double* outR, int n) {
    auto* v = static_cast<pvb::VbModule*>(m);
    for (int i = 0; i < n; ++i) v->tick(inL[i], inR[i], outL[i], outR[i]);
}

}



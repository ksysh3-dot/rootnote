// GPL-3.0. COMBO harmonic generator for 48000 Hz input.
#pragma once
#include "pvb_vb.h"
#include "combo1/pvb_vb.h"
namespace pvb {
class Combo1Module final : public VbModule {
    pvb_combo1::VbHpv generator_{true,true,1};
    double protectedBranchGain_=1.;
    RampedSvf cut_[2];SvfState mixCut_[2][2],layerCut_[2][2],layerEq_[2][4],mixEq_[2][4];
    HarmonicTrace trace_;
public:
    bool configure(int rate) override {
        if(rate!=48000)return false;
        generator_.configure(rate);generator_.freezeCombo1();
        auto c=svfHighpass(rate,80.,0.70710678118654752);
        const double r=std::pow(10.,-6./80.);
        c.m0=1.;c.m1=std::sqrt(2.)*(r-1.);c.m2=r*r-1.;
        for(auto& f:cut_)f.snap(c);
        reset();return true;
    }
    void reset() override {
        generator_.reset();protectedBranchGain_=1.;
        for(auto& c:mixCut_)for(auto& s:c)s=SvfState{};
        for(auto& c:layerCut_)for(auto& s:c)s=SvfState{};
        for(auto& c:layerEq_)for(auto& s:c)s=SvfState{};
        for(auto& c:mixEq_)for(auto& s:c)s=SvfState{};
    }
    int latencyFrames() const override{return generator_.latencyFrames();}
    void flushTiny() {for(auto& channel:mixEq_)for(auto& state:channel)state.flushTiny();}
    bool inputAfterEq() const override{return false;}
    void tick(double l,double r,double& a,double& b) override {generator_.tick(l,r,a,b);}
    void setHarmonicCapture(bool enabled) override {generator_.setHarmonicCapture(enabled);}
    const HarmonicTrace* takeHarmonicTrace() override {
        const auto* source=generator_.takeHarmonicTrace();
        if(!source)return nullptr;
        static_assert(HarmonicTrace::kFields==pvb_combo1::HarmonicTrace::kFields);
        std::copy_n(source->data,HarmonicTrace::kFields,trace_.data);return &trace_;
    }
    void setDevMeter(bool enabled) override {generator_.setDevMeter(enabled);}
    bool devLevel(int slot,float* out) override {return generator_.comboDev(slot,out);}
    bool devHarmonics(DevHarmonics& out) override {
        pvb_combo1::DevHarmonics source;
        if(!generator_.devHarmonics(source))return false;
        out.n=source.n;out.gain=source.gain*0.782609253712266*5.72334054722333*protectedBranchGain_;
        for(int t=0;t<DevHarmonics::kTracks;++t){
            out.f[t]=source.f[t];out.sum[t]=source.sum[t];
            std::copy_n(source.amp[t],7,out.amp[t]);
        }
        return true;
    }
    double devOutResponse(double hz) const override {return generator_.devOutResponse(hz);}
    void setProtectedBranchGain(double gain){protectedBranchGain_=gain;}
    void post(double input[2],double layer[2],RampedSvf& hp,RampedSvf& lo,RampedSvf& hi) {
        for(int c=0;c<2;++c){
            // Use separate state for the mix and layer. Flush at the end of the callback.
            auto* m=mixEq_[c];input[c]=hi.tick(m[3],lo.tick(m[2],hp.tick(m[1],hp.tick(m[0],input[c]))));
            auto* q=layerEq_[c];layer[c]=hi.tick(q[3],lo.tick(q[2],hp.tick(q[1],hp.tick(q[0],layer[c]))));
            for(int j=0;j<2;++j){input[c]=cut_[j].tick(mixCut_[c][j],input[c]);layer[c]=cut_[j].tick(layerCut_[c][j],layer[c]);}
        }
    }
};
}

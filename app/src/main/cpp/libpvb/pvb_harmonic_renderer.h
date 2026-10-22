#pragma once
#include <algorithm>
#include <cmath>

namespace pvb { namespace oscillator52 {
// Research P2-O. A control point describes the END of this16/3000s interval.
// It is available before its first sample is consumed: production centre=i+16.
// Each sample is emitted once, without overlapping independently phased grains.
// Amplitudes are nonnegative linear ramps. Frequency is linear; phase is its
// exact integral. Optional observation correction is bounded to10cents and
// changes phase continuously; it is not an ownership claim for existing audio.
// This candidate consumes f/A endpoint controls, not P1 local polynomial/AM
// envelopes. Compare it with mode0; those richer trajectory adapters are future work.
constexpr int kHop=16,kPartials=7;
constexpr double kRate=3000.,kTwoPi=6.283185307179586476925286766559;
inline double wrap(double x) {return std::remainder(x,kTwoPi);}
struct State {
    bool initialized=false;
    double frequency=0,phase[kPartials]={},amplitude[kPartials]={},nominal=0;
    void add(double f,const double* targetAmplitude,const double* targetPhase,
             double targetNominal,bool correct,double* out,double* nominalOut) {
        const double duration=kHop/kRate;
        if(!initialized) {
            frequency=f;
            for(int j=0;j<kPartials;++j) phase[j]=wrap(targetPhase[j]-kTwoPi*(j+2)*f*duration);
            initialized=true;
        }
        for(int j=0;j<kPartials;++j) {
            const double k=j+2,advance=kTwoPi*k*(frequency+f)*.5*duration;
            const double bound=kTwoPi*k*std::min(frequency,f)*std::expm1(std::log(2.)*10./1200.)*duration;
            const double correction=correct?std::clamp(wrap(targetPhase[j]-phase[j]-advance),-bound,bound):0.;
            const double a=std::max(0.,targetAmplitude[j]);
            for(int n=0;n<kHop;++n) {
                const double u=static_cast<double>(n)/kHop,t=n/kRate;
                const double p=phase[j]+kTwoPi*k*(frequency*t+.5*(f-frequency)*t*u)+correction*u;
                out[n]+=(amplitude[j]+(a-amplitude[j])*u)*std::cos(p);
            }
            phase[j]=wrap(phase[j]+advance+correction);amplitude[j]=a;
        }
        for(int n=0;n<kHop;++n) nominalOut[n]+=nominal+(targetNominal-nominal)*static_cast<double>(n)/kHop;
        nominal=targetNominal;frequency=f;
    }
};
} }

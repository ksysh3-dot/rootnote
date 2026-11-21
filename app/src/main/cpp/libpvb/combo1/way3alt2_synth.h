#pragma once
#include <algorithm>
#include <cmath>
#include <complex>
namespace alt2 {
constexpr double pi=3.141592653589793238462643383279502884;
class NumericGrain {
    double values_[32]{};
public:
    void addConstant(double amplitude,int order,double frequency,double phase,double offset) {
        for(int g=0;g<32;++g) values_[g]+=amplitude*std::cos(order*(phase+2*pi*frequency*(g-16)/3000)+offset);
    }
    void addLocal(int g,double amplitude,double ratio,int order,double phase,double delta,double offset) {
        values_[g]+=amplitude*ratio*std::cos(order*(phase+delta)+offset);
    }
    void addSideband(int g,double amplitude,int order,double phase,double frequency,double offset,
                     double envelopeReal,double envelopeImag) {
        const double t=(g-16)/3000.;
        values_[g]+=amplitude*(std::polar(1.,order*(phase+2*pi*frequency*t)+offset)*std::complex<double>(envelopeReal,envelopeImag)).real();
    }
    void copyTo(double* output) const {std::copy_n(values_,32,output);}
};
// Stereo-linked, zero-lookahead, instantaneous attack and 50 ms release.
// It measures ONLY the generated branch. No dry or downstream feedback input.
class BranchLimiter {
    double gain_=1.;
public:
    void reset(){gain_=1.;}
    double gain() const{return gain_;}
    void process(double& l,double& r,double threshold,double release) {
        const double peak=std::max(std::abs(l),std::abs(r));
        const double target=peak>threshold?threshold/peak:1.;
        gain_=target<gain_?target:release*gain_+(1.-release)*target;
        l*=gain_;r*=gain_;
    }
};
}

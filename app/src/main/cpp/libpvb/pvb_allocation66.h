#pragma once
#include <cmath>
#include <algorithm>
namespace pvb {
// Startup-only host research parameters. Mode0 executes no audio arithmetic.
// This allocator has no signal buffer or added latency. Native A/TP8 certificate
// and limiter see the allocated components, preserving their existing schedule.
class Allocation66 {
 int mode_=0; bool high_=true; double low_[2]={},fast_=0.,slow_=0.,gain_=1.;
public:
 bool set(int mode,bool high) {if(mode<0||mode>3)return false;mode_=mode;high_=high;reset();return true;}
 void reset() {low_[0]=low_[1]=fast_=slow_=0.;gain_=1.;}
 int mode() const {return mode_;}
 void tick(double& dL,double& dR,double& lL,double& lR,double fs) {
  if(!mode_)return;
  constexpr double up=.0901844923851276+1.; // +0.75dB
  if(mode_==1) {const double down=1./up;dL*=down;dR*=down;lL*=up;lR*=up;return;}
  if(mode_==2) {
   const double p=.5*(lL*lL+lR*lR);
   const double af=1.-std::exp(-1./(.010*fs)),as=1.-std::exp(-1./(.400*fs));
   fast_+=af*(p-fast_);slow_+=as*(p-slow_);
   const double excess=10.*std::log10(std::max(fast_,1e-30)/std::max(slow_,1e-30))-3.;
   const double attenuation=std::max(0.,std::min(3.,excess));
   const double target=std::pow(10.,-attenuation/20.);
   const double ag=1.-std::exp(-1./((target<gain_?.005:.200)*fs));
   gain_+=ag*(target-gain_);lL*=up*gain_;lR*=up*gain_;return;
  }
  // Causal one-pole LP300. Complement is exact before allocation.
  const double a=1.-std::exp(-2.*3.14159265358979323846*300./fs);
  low_[0]+=a*(lL-low_[0]);low_[1]+=a*(lR-low_[1]);
  const double gu=std::pow(10.,1./20.),gd=1./gu;
  const double gl=high_?gd:gu,gh=high_?gu:gd;
  lL=gl*low_[0]+gh*(lL-low_[0]);lR=gl*low_[1]+gh*(lR-low_[1]);
 }
};
}

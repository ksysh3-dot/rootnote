// P1+++ only. Parallel certificate inside the existing 88-sample schedule.
// For any A gain a_i in [0,1], |D_i+a_i L_i| <= U_i=max(|D_i|,|D_i+L_i|).
// B_t=max_p sum_k |h_pk| U_(t+k). If each support gain g_j<=C/B_t,
// triangle inequality proves the final float output TP8<=C, including moving A,
// limiter, fade and gate gains. This is a conservative FIR TP8 certificate,
// not a guarantee for an unspecified continuous-time reconstruction filter.
#pragma once
#include "pvb_layer_peak42.h"
namespace pvb {
class BoundedPeak50 {
public:
 BoundedPeak50() {reset();}
 void reset() {n_=-1;lastConstraint_=-1;gain_=1.;std::fill(std::begin(hist_),std::end(hist_),0.);std::fill(std::begin(bounds_),std::end(bounds_),1.);}
 void setCeilingDb(double db) {
  double norm=1.;for(int p=0;p<8;++p) {double s=0.;for(int k=-20;k<=20;++k)s+=std::abs(LayerPeak42::coefficient(p,k));norm=std::max(norm,s);}
  // Reserve the TP8 image of int16 nearest-rounding error as well as float conversion.
  ceiling_=std::max(0.,std::pow(10.,db/20.)*(1.-1e-6)-norm*(.5/32768.));
 }
 void setReleaseMs(double ms,double fs) {release_=1.-std::exp(-1./(.001*ms*fs));}
 double process(double dl,double dr,double ll,double lr) {
  ++n_;const int pos=static_cast<int>(n_)&127;
  const double u=std::max({std::abs(dl),std::abs(dr),std::abs(dl+ll),std::abs(dr+lr)});
  hist_[pos]=hist_[pos+128]=u;
  const int64_t t=n_-20;
  if(t>=0) {
   const double* x=hist_+pos+88;double peak=0.;
   double umax=0.;
   for(int k=0;k<41;++k)if(!(x[k]<=umax))umax=x[k];
   if(umax*kNormBound_<=ceiling_) {
    bounds_[static_cast<int>(t)&255]=1.;
   } else {
    double v[8]={};
    for(int k=0;k<41;++k)for(int p=0;p<8;++p)v[p]+=std::abs(tp50::doubleBank[k][p])*x[k];
    for(double z:v)peak=std::max(peak,z);
    bounds_[static_cast<int>(t)&255]=peak>ceiling_?ceiling_/peak:1.;
   }
   if(bounds_[static_cast<int>(t)&255]<1.)lastConstraint_=t;
  }
  const int64_t j=n_-88;double target=1.;
  const int64_t tt0=std::max<int64_t>(0,j-20);
  if(j>=0&&lastConstraint_>=tt0) for(int64_t tt=tt0;tt<=t;++tt) {
   const double r=bounds_[static_cast<int>(tt)&255];
   if(r==1.)continue;
   // The 48-sample attack reaches a constraint before its first support sample.
   const double ramp=std::clamp(static_cast<double>(tt-20-j)/48.,0.,1.);
   target=std::min(target,r+ramp*(1.-r));
  }
  gain_=target<gain_?target:gain_+(target-gain_)*release_;
  return gain_;
 }
 double gain()const{return gain_;}
private:
 static constexpr double kNormBound_=[]() constexpr {
  double norm=0.;
  for(int p=0;p<8;++p) {
   double s=0.;
   for(int k=0;k<41;++k) {
    const double c=tp50::doubleBank[k][p];
    s+=c<0.?-c:c;
   }
   if(s>norm)norm=s;
  }
  return norm*(1.+1e-12);
 }();
 int64_t n_=-1,lastConstraint_=-1;double hist_[256]={},bounds_[256]={};
 double gain_=1.,ceiling_=.891249,release_=1.-std::exp(-1./2880.);
};
}

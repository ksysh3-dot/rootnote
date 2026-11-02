// S42 host-only causal layer controller. OFF does no processing.
// Reuses the existing 88-frame limiter delay; never modifies a dry sample.
// Bounded-variation triangle TP control: each constraint covers all 41 support samples.
// Fixed dry infeasibility is recorded; layer attenuation cannot repair that condition.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include "pvb_tp50_coeff.h"
#ifndef PVB_TP_FLOAT32
#define PVB_TP_FLOAT32 0
#endif
#ifndef PVB_TP_FACTOR
#define PVB_TP_FACTOR 8
#endif
static_assert(PVB_TP_FACTOR==8 || PVB_TP_FACTOR==4,"TP factor must be4 or8");
namespace pvb {
#if PVB_TP_FLOAT32
using TpScalar50=float;
#else
using TpScalar50=double;
#endif
static constexpr auto kTp50Bank=tp50::transpose<TpScalar50>();
class LayerPeak42 {
public:
 bool configure(int mode,double fs,double release) {
  if(mode<0 || mode>3 || !std::isfinite(release) || release<50 || release>200) return false;
  mode_=mode;fs_=fs;release_=release;
  dpCoef_=std::exp(-1./fs_);lpCoef_=std::exp(-1./(.2*fs_));
  bgDown_=1.-std::exp(-1./(.020*fs_));bgUp_=1.-std::exp(-1./(.200*fs_));
  releaseCoef_=1.-std::exp(-1./(.001*release_*fs_));reset();return true;
 }
 bool setRecovery66(int ms) {if(ms!=20 && ms!=100)return false;releaseCoef_=1.-std::exp(-1./(.001*ms*fs_));return true;}
 void reset() {
  for(double& v:gains_)v=0.;
  n_=-1;refPeak_=dp_=lp_=bg_=gain_=0.;infeasible_=0;lower_=0;
  for(auto& a:x_)for(double& v:a)v=0.;
  for(auto& a:hist_)for(auto& v:a)v=0.;
  for(double& v:r_)v=0.;
  for(double& v:b_)v=0.;
 }
 static double coefficient(int p,int k){return coef_[p][k+20];}
 bool enabled()const{return mode_!=0;}
 double gain()const{return gain_;}
 double referencePeak()const{return refPeak_;}
 double gainFor(int m)const{return gains_[m-1];}
 uint64_t infeasible()const{return infeasible_;}
 uint64_t lower()const{return lower_;}
 void process(double dl,double dr,double ll,double lr,double rl,double rr,int delay,
              double& odL,double& odR,double& olL,double& olR) {
  ++n_;const int pos=static_cast<int>(n_)&511;
  const double xx[6]={dl,dr,ll,lr,rl,rr};
  const int hp=static_cast<int>(n_)&63;
  for(int c=0;c<6;++c) {x_[c][pos]=xx[c];hist_[c][hp]=hist_[c][hp+64]=static_cast<TpScalar50>(xx[c]);}
  if(mode_!=1) {
  const double pkd=std::max(std::abs(dl),std::abs(dr)),pkl=std::max(std::abs(ll),std::abs(lr));
  dp_=std::max(pkd,dp_*dpCoef_);
  lp_=std::max(pkl,lp_*lpCoef_);
  // Running crest allowance from the causal P1 reference peak; no whole-track scalar.
  double bt=std::clamp((refPeak_-dp_)/std::max(lp_,1e-30),0.,1.);
  bg_+=(bt-bg_)*(bt<bg_?bgDown_:bgUp_);
  b_[pos]=bg_;
  }
  const int64_t t=n_-20;
  if(mode_!=2 && t>=0) {
   TpScalar50 ds[8][2]={},ls[8][2]={},absls[8][2]={};
   TpScalar50 refs[8][2]={};
   // Phase lanes are independent accumulators with the original tap order.
   // The transposed coefficient bank and mirrored histories permit NEON/SSE
   // vector lanes without fast-math, a horizontal reduction, or FMA.
   for(int k=0;k<41;++k)for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
    const TpScalar50 z=kTp50Bank[k][p];const int q=hp+24+k;
    ds[p][c]+=z*hist_[c][q];ls[p][c]+=z*hist_[c+2][q];
    absls[p][c]+=std::abs(z*hist_[c+2][q]);refs[p][c]+=z*hist_[c+4][q];
   }
   for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c)
    refPeak_=std::max(refPeak_,static_cast<double>(std::abs(refs[p][c])));
   double need=1.;bool bad=false,positive=false;
   // 1e-6 linear margin covers float32 conversion, not an empirical global TP adjustment.
   const double ceiling=refPeak_*(1.-1e-6);
   for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
    const double room=ceiling-std::abs(ds[p][c]);
    if(room < -1e-12)bad=true;
    if(std::abs(ls[p][c])>1e-20) {
     double a=(-ceiling-ds[p][c])/ls[p][c],b=(ceiling-ds[p][c])/ls[p][c];
     if(std::min(a,b)>1e-9)positive=true;
    }
    if(absls[p][c]>1e-20)need=std::min(need,std::clamp(room/absls[p][c],0.,1.));
   }
   if(bad)++infeasible_;
   if(positive)++lower_;
   r_[static_cast<int>(t)&511]=need;
  } else if(mode_==2 && t>=0) {
   // Slow estimator still uses TP8 P1 running reference, independently of proposed sum.
   for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
    TpScalar50 ref=0.;
    for(int k=0;k<41;++k)ref+=static_cast<TpScalar50>(coef_[p][k])*hist_[c+4][hp+24+k];
    refPeak_=std::max(refPeak_,static_cast<double>(std::abs(ref)));
   }
  }
  const int64_t j=n_-delay;double target=1.;
  if(j<0)target=0.;
  else if(mode_!=2) {
   // Constraints at t influence output samples [t-20,t+20].
   // 48-frame linear attack reaches each bound before its support begins.
   for(int64_t tt=std::max<int64_t>(0,j-20);tt<=t;++tt) {
    const double ramp=std::clamp(static_cast<double>(tt-20-j)/48.,0.,1.);
    target=std::min(target,r_[static_cast<int>(tt)&511]+ramp*(1.-r_[static_cast<int>(tt)&511]));
   }
  }
  const double bb=j>=0?b_[static_cast<int>(j)&511]:0.;
  const double targets[3]={target,bb,std::min(target,bb)};
  for(int m=0;m<3;++m)if(mode_!=1 || m==0)gains_[m]=targets[m]<gains_[m]?targets[m]:gains_[m]+(targets[m]-gains_[m])*releaseCoef_;
  gain_=gains_[mode_-1];
  const int rd=static_cast<int>(j)&511;
  odL=j>=0?x_[0][rd]:0.;odR=j>=0?x_[1][rd]:0.;
  olL=j>=0?x_[2][rd]*gain_:0.;olR=j>=0?x_[3][rd]*gain_:0.;
 }
private:
 int mode_=0;double fs_=48000.,release_=100.;
 double dpCoef_=0.,lpCoef_=0.,bgDown_=0.,bgUp_=0.,releaseCoef_=0.;
 alignas(64) TpScalar50 hist_[6][128]={};
 int64_t n_=-1;double refPeak_=0.,dp_=0.,lp_=0.,bg_=0.,gain_=0.;
 uint64_t infeasible_=0,lower_=0;
 double gains_[3]={};
 double x_[6][512]={},r_[512]={},b_[512]={};
 static constexpr const auto& coef_=tp50::coef_;
};
}

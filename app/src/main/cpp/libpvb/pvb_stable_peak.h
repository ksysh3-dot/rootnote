#pragma once
// The frozen s71 FAST_PEAK detector is float32. OFF/STRONG keep the original double detector.
// Coefficients, release, constraints and output arithmetic are unchanged.
#include "pvb_layer_peak42.h"
#include "pvb_dry_peak44.h"
namespace pvb {
static constexpr auto kStableTp50Bank=tp50::transpose<float>();
class StableLayerPeak42 {
public:
 bool configure(int mode,double fs,double release) {
  if(mode<0 || mode>3 || !std::isfinite(release) || release<50 || release>200) return false;
  mode_=mode;fs_=fs;release_=release;
  dpCoef_=std::exp(-1./fs_);lpCoef_=std::exp(-1./(.2*fs_));
  bgDown_=1.-std::exp(-1./(.020*fs_));bgUp_=1.-std::exp(-1./(.200*fs_));
  releaseCoef_=1.-std::exp(-1./(.001*release_*fs_));reset();return true;
 }
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
  for(int c=0;c<6;++c) {x_[c][pos]=xx[c];hist_[c][hp]=hist_[c][hp+64]=static_cast<float>(xx[c]);}
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
   float ds[8][2]={},ls[8][2]={},absls[8][2]={};
   float refs[8][2]={};
   // Phase lanes are independent accumulators with the original tap order.
   // The transposed coefficient bank and mirrored histories permit NEON/SSE
   // vector lanes without fast-math, a horizontal reduction, or FMA.
   for(int k=0;k<41;++k)for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
    const float z=kStableTp50Bank[k][p];const int q=hp+24+k;
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
    float ref=0.;
    for(int k=0;k<41;++k)ref+=static_cast<float>(coef_[p][k])*hist_[c+4][hp+24+k];
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
 alignas(64) float hist_[6][128]={};
 int64_t n_=-1;double refPeak_=0.,dp_=0.,lp_=0.,bg_=0.,gain_=0.;
 uint64_t infeasible_=0,lower_=0;
 double gains_[3]={};
 double x_[6][512]={},r_[512]={},b_[512]={};
 static constexpr const auto& coef_=tp50::coef_;
};
class StableDryPeak44 {
public:
 void reset() {
  n_=-1; peak_=0.; blockNeed_=1.; alpha_=1.;
  for(auto& a:x_)for(double& v:a)v=0.;
  for(auto& a:hist_)for(auto& v:a)v=0.;
  for(int i=0;i<1024;++i){tags_[i]=-1000000;bounds_[i]=1.;}
 }
 StableDryPeak44(){reset();}
 double alpha()const{return alpha_;}
 double peak()const{return peak_;}
 void process(double dl,double dr,double sl,double sr,int delay,double& ol,double& orr) {
  ++n_;const int pos=static_cast<int>(n_)&16383;
  x_[0][pos]=dl;x_[1][pos]=dr;x_[2][pos]=sl;x_[3][pos]=sr;
  const int hp=static_cast<int>(n_)&63;const double v[4]={dl,dr,sl-dl,sr-dr};
  for(int c=0;c<4;++c)hist_[c][hp]=hist_[c][hp+64]=static_cast<float>(v[c]);
  const int64_t t=n_-20;
  if(t>=0) {
   float b[8][2]={},e[8][2]={};
   for(int k=-20;k<=20;++k) {
    if(t+k<0)continue;
    for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
     const float cf=kStableTp50Bank[k+20][p];
     b[p][c]+=cf*hist_[c][hp+44+k];e[p][c]+=cf*hist_[c+2][hp+44+k];
    }
   }
   for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c)
    peak_=std::max(peak_,static_cast<double>(std::abs(b[p][c])));
   double need=1.;
   for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
    const double v=b[p][c]+e[p][c];
    if(std::abs(v)>peak_ && std::abs(e[p][c])>1e-30) {
     const double hi=(std::copysign(peak_,v)-b[p][c])/e[p][c];
     need=std::min(need,std::clamp(hi,0.,1.));
    }
   }
   blockNeed_=std::min(blockNeed_,need);
   if(t%48==47) {
    const int64_t left=(t-47-20)/48-1,right=(t+20+47)/48;
    if(blockNeed_<1.)for(int64_t f=std::max<int64_t>(0,left-50);f<=right;++f) {
     const double u=std::clamp(static_cast<double>(left-f)/50.,0.,1.);
     const double ramp=u*u*(3.-2.*u),v=blockNeed_+(1.-blockNeed_)*ramp;
     const int q=static_cast<int>(f)&1023;
     if(tags_[q]!=f){tags_[q]=f;bounds_[q]=1.;}
     bounds_[q]=std::min(bounds_[q],v);
    }
    blockNeed_=1.;
   }
  }
  const int64_t j=n_-delay;
  if(j<0){ol=orr=0.;return;}
  const int64_t f=j/48;const double mix=static_cast<double>(j%48)/48.;
  const auto get=[&](int64_t q){const int r=static_cast<int>(q)&1023;return tags_[r]==q?bounds_[r]:1.;};
  const double target=get(f)+(get(f+1)-get(f))*mix;
  alpha_=target<alpha_?target:alpha_+(target-alpha_)*(1.-std::exp(-1./12000.));
  const int r=static_cast<int>(j)&16383;
  ol=x_[0][r]+alpha_*(x_[2][r]-x_[0][r]);
  orr=x_[1][r]+alpha_*(x_[3][r]-x_[1][r]);
 }
private:
 int64_t n_=-1,tags_[1024]={};double bounds_[1024]={};
 alignas(64) float hist_[4][128]={};
 double x_[4][16384]={},peak_=0.,blockNeed_=1.,alpha_=1.;
};
class ModeLayerPeak42 {
 LayerPeak42 original_;StableLayerPeak42 stable_;bool useStable_=false;
public:
 void setStable(bool on){useStable_=on;}
 bool configure(int mode,double fs,double release){bool ok=original_.configure(mode,fs,release);return stable_.configure(mode,fs,release)&&ok;}
 void reset(){original_.reset();stable_.reset();}
 bool enabled()const{return original_.enabled();}
 double gain()const{return useStable_?stable_.gain():original_.gain();}
 double referencePeak()const{return useStable_?stable_.referencePeak():original_.referencePeak();}
 double gainFor(int m)const{return useStable_?stable_.gainFor(m):original_.gainFor(m);}
 uint64_t infeasible()const{return useStable_?stable_.infeasible():original_.infeasible();}
 uint64_t lower()const{return useStable_?stable_.lower():original_.lower();}
 void process(double dl,double dr,double ll,double lr,double rl,double rr,int delay,double& odL,double& odR,double& olL,double& olR){
  if(useStable_)stable_.process(dl,dr,ll,lr,rl,rr,delay,odL,odR,olL,olR);
  else original_.process(dl,dr,ll,lr,rl,rr,delay,odL,odR,olL,olR);
 }
};
class ModeDryPeak44 {
 DryPeak44 original_;StableDryPeak44 stable_;bool useStable_=false;
public:
 void setStable(bool on){useStable_=on;}
 void reset(){original_.reset();stable_.reset();}
 double alpha()const{return useStable_?stable_.alpha():original_.alpha();}
 double peak()const{return useStable_?stable_.peak():original_.peak();}
 void process(double dl,double dr,double sl,double sr,int delay,double& ol,double& orr){
  if(useStable_)stable_.process(dl,dr,sl,sr,delay,ol,orr);else original_.process(dl,dr,sl,sr,delay,ol,orr);
 }
};
}

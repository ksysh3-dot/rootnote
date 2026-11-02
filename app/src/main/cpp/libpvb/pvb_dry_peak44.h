// S44 host research. Predict dry before its existing 7052-frame alignment delay.
// Fixed parameters, P1, no dynamic EQ/XTC. No audio delay is added.
#pragma once
#include "pvb_layer_peak42.h"
namespace pvb {
class DryPeak44 {
public:
 void reset() {
  n_=-1; peak_=0.; blockNeed_=1.; alpha_=1.;
  for(auto& a:x_)for(double& v:a)v=0.;
  for(auto& a:hist_)for(auto& v:a)v=0.;
  for(int i=0;i<1024;++i){tags_[i]=-1000000;bounds_[i]=1.;}
 }
 DryPeak44(){reset();}
 double alpha()const{return alpha_;}
 double peak()const{return peak_;}
 void process(double dl,double dr,double sl,double sr,int delay,double& ol,double& orr) {
  ++n_;const int pos=static_cast<int>(n_)&16383;
  x_[0][pos]=dl;x_[1][pos]=dr;x_[2][pos]=sl;x_[3][pos]=sr;
  const int hp=static_cast<int>(n_)&63;const double v[4]={dl,dr,sl-dl,sr-dr};
  for(int c=0;c<4;++c)hist_[c][hp]=hist_[c][hp+64]=static_cast<TpScalar50>(v[c]);
  const int64_t t=n_-20;
  if(t>=0) {
   TpScalar50 b[8][2]={},e[8][2]={};
   for(int k=-20;k<=20;++k) {
    if(t+k<0)continue;
    for(int p=0;p<8;p+=8/PVB_TP_FACTOR)for(int c=0;c<2;++c) {
     const TpScalar50 cf=kTp50Bank[k+20][p];
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
 alignas(64) TpScalar50 hist_[4][128]={};
 double x_[4][16384]={},peak_=0.,blockNeed_=1.,alpha_=1.;
};
}

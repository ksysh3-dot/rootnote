// GPL-3.0. Harmonic levels from the current spectrum and envelope state.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace combo1 {

struct HoldEvent {
    double outer[33]{}, inner[33]{};
    int next=0, used=0, left=0;
    bool previous=false;
    bool step(double o,double e,bool valid,bool global,double& rise){
        double oldO=-1e300,oldE=-1e300;
        for(int lag=9;lag<=std::min(32,used);++lag){
            const int j=(next+33-lag)%33;
            oldO=std::max(oldO,outer[j]);
            oldE=std::max(oldE,inner[j]);
        }
        const bool ready=used>=(global?32:9);
        rise=ready?o-oldO:0.;
        const bool condition=ready && valid && rise>=6. && (global || e-oldE<3.);
        if(left==0 && condition && !previous)left=24;
        previous=condition;
        const bool active=left>0;
        if(active)--left;
        outer[next]=o;inner[next]=e;next=(next+1)%33;used=std::min(33,used+1);
        return active;
    }
};

struct State {
 int nFast=0;
 double energyRef=-1.; int downRun=0;
 HoldEvent eventB{};

 uint32_t id=0;uint64_t steps=0;int64_t stamp=-1;
 int pos=0,n=0;float history[5]{};float raw=-100,db=-100,amp=0; double smooth=0., previous=0., observedAmplitude=0.;
};
struct FinishDetail { double level, ageGain, expanderLoss; };
struct Values {double T=0,M=0,R=0,supply=0,raw=0;};
inline void prefixPower(const double* re,const double* im,double wsum,double* prefix){
 prefix[0]=0.;
 for(int b=0;b<1025;++b){
  const double r=re[b]*2/wsum,i=im[b]*2/wsum;
  const float e=float(r*r+i*i);prefix[b+1]=prefix[b]+double(e);
 }
}
inline double edge(const double* p,double hz){
 const double q=std::clamp(hz/(3000./2048)+.5,0.,1025.);
 const int k=int(std::floor(q));return p[k]+(k<1025?(q-k)*(p[k+1]-p[k]):0.);
}
inline Values values(const float*x,const double* p){
 Values v;const double f=55*std::pow(2.,double(x[0]));
 v.T=std::pow(10.,2*double(x[1])-3./20);
 double peaks[3];for(int k=0;k<3;++k)peaks[k]=(k+1)*std::max(0.,std::pow(10.,2*double(x[68+k]))-1e-6);
 std::sort(peaks,peaks+3);const double r=400*double(x[5])/(.12*f);
 // Keep the original rawM multiply order for its tracker cap.
 v.M=std::min(std::pow(10.,-3./20)*std::pow(10.,2*double(x[1])),std::pow(10.,6./20)*peaks[1]/std::sqrt(1+r*r));
 double sum=0;for(int k=0;k<4;++k){const double a=x[68+k]<=-3?0.:std::pow(10.,2*double(x[68+k]));sum+=a*a;}
 v.R=std::sqrt(sum/4);
 const double J=std::max(0.,edge(p,f+(3000./2048)/2)-edge(p,20.))/16.;
 // lvl2's saved physical feature is float32 before the min operation.
 v.supply=float(std::pow(10.,6./20)*std::sqrt(2*J));
 v.raw=std::min(v.T,std::min(v.supply,std::sqrt(.75*v.M*v.M+.25*v.R*v.R)));
 return v;
}
inline float finish(State&s,double a,uint32_t id,int64_t stamp,bool median=true,bool age=true,bool x35=true,FinishDetail* detail=nullptr){
 if(s.id!=id||(s.stamp>=0&&stamp-s.stamp!=16)){s=State{};s.id=id;}
 s.stamp=stamp;s.raw=float(std::clamp(20*std::log10(std::max(a,1e-5)),-100.,6.));
 s.history[s.pos]=s.raw;s.pos=(s.pos+1)%5;s.n=std::min(5,s.n+1);
 float v[5];std::copy_n(s.history,s.n,v);std::sort(v,v+s.n);
 s.db=median?(s.n%2?v[s.n/2]:(v[s.n/2-1]+v[s.n/2])*.5f):s.raw;
 const float med=s.db<=-90?0.f:std::pow(10.f,s.db/20.f);
 const double lev=med>0?20*std::log10(double(med)):-100.;
 const double n=double(s.steps),g=age?(n<=6?-30+n:std::min(0.,-24+6*(n-6))):0.;
 const double loss=x35?std::min(10.,std::max(0.,-35.-lev)):0.;
 const double ex=lev-loss;
 if(detail)*detail={lev,g,loss};
 const double z=std::max(-100.,ex+g);double out=z<=-90?0.:std::pow(10.,z/20.);
 const double tau=out>s.smooth?10.0:40.0;
 const double alpha=std::exp(-(16./3000)/(tau*.001));
 s.smooth=alpha*s.smooth+(1-alpha)*out;out=s.smooth;
 ++s.steps;s.amp=float(out);return s.amp;
}
}

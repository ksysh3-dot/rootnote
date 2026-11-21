// GPL-3.0. Look-ahead peak protection. Fixed 48 kHz, no allocation in tick.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace peak1 {
constexpr int look=240; // 5 ms, shared by P1 and P2, stages add when combined.
constexpr double ceiling=0.12589254117941673; // -18 dBFS hypothesis, not device measurement.
struct Smooth {
 static constexpr int N=look+1, Q=N+1;
 double values[Q]{},avg[N]{},sum=double(N),env=1.,gain=1.;int64_t stamps[Q]{},clock=0;int head=0,tail=0,pos=0;
 Smooth(){reset();}
 void reset(){std::fill_n(avg,N,1.);sum=N;env=gain=1.;clock=0;head=tail=pos=0;}
 double tick(double target){
  const double release=std::exp(-1./(.050*48000.));
  env=target<env?target:release*env+(1-release)*target;
  while(head!=tail && stamps[head]<clock-look)head=(head+1)%Q;
  while(head!=tail){int p=(tail+Q-1)%Q;if(values[p]<env)break;tail=p;}
  values[tail]=env;stamps[tail]=clock++;tail=(tail+1)%Q;
  sum+=values[head]-avg[pos];avg[pos]=values[head];pos=(pos+1)%N;
  gain=std::clamp(sum/N,0.,1.);return gain;
 }
};
struct Delay {
 double v[look][4]{};int pos=0;
 void reset(){for(auto& a:v)std::fill_n(a,4,0.);pos=0;}
 void tick(double& a,double& b,double& c,double& d){double in[4]={a,b,c,d};a=v[pos][0];b=v[pos][1];c=v[pos][2];d=v[pos][3];std::copy_n(in,4,v[pos]);pos=(pos+1)%look;}
};
struct Band {
 double z[2][2]{};
 double tick(double x){
  // scipy.signal.butter(2,[100,300],btype='bandpass',fs=48000,output='sos')
  static constexpr double c[2][6]={{0.0001682237085914695,0.00033644741718293899,0.0001682237085914695,1,-1.9731736715915937,0.97436570003472067},{1,-2,1,1,-1.9887878343526535,0.9890054465067547}};
  for(int j=0;j<2;++j){double y=c[j][0]*x+z[j][0];z[j][0]=c[j][1]*x-c[j][4]*y+z[j][1];z[j][1]=c[j][2]*x-c[j][5]*y;x=y;}return x;
 }
};
struct Protect {
 Smooth smooth;Delay delay;Band dry[2],layer[2];double gain=1.,levels[look]{};
 Protect(){std::fill_n(levels,look,1.);}
 void reset(){smooth.reset();delay.reset();std::fill_n(levels,look,1.);for(auto& b:dry)b=Band{};for(auto& b:layer)b=Band{};gain=1.;}
 void branch(double& l,double& r,double& d0,double& d1,double vg,double og){
  double a=l*vg*og,b=r*vg*og;const double peak=std::max(std::abs(a),std::abs(b));
  gain=smooth.tick(peak>0.06309573444801933?0.06309573444801933/peak:1.);
  // Preserve old arithmetic at constant layer gain; align changes with delayed samples.
  const double delayedLevel=levels[delay.pos];levels[delay.pos]=vg;
  delay.tick(l,r,d0,d1);l*=gain;r*=gain;
  const double ratio=std::abs(vg)>1e-30?delayedLevel/vg:0.;l*=ratio;r*=ratio;
 }
 void mixed(double sum[2],double component[2],double og,bool enabled=true){
  double d0=sum[0]-component[0],d1=sum[1]-component[1],a=component[0],b=component[1];
  double target=1.;
  for(int c=0;c<2;++c){double d=dry[c].tick((c?d1:d0)*og),h=layer[c].tick((c?b:a)*og);
    // A cancelling layer uses no headroom. Limit the corrective gain range.
    const double excess=std::max(0.,std::abs(d+h)-std::max(ceiling,std::abs(d)));
    target=std::min(target,std::max(0.7498942093324559,1.-excess/std::max(std::abs(h),1e-30)));
  }
  if(!enabled)target=1.;
  gain=smooth.tick(target);delay.tick(a,b,d0,d1);component[0]=a*gain;component[1]=b*gain;sum[0]=d0+component[0];sum[1]=d1+component[1];
 }
};
}

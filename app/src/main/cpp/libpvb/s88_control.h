#pragma once
// s91 ports only frozen modules 1 and 32. No waveform/mask enters this interface.
#include "pvb_control_stream.h"
#include <algorithm>
#include <cmath>
namespace pvb {
struct Control88 {
 bool enabled=false;unsigned modules=0;const float* frames=nullptr;int count=0,stride=8;
 ControlStream* stream=nullptr;ControlWorker* worker=nullptr;double origin=49152,time=-49152,g=1,epsilon89=.5;
 const float* frame=nullptr;float compact89[80]{},selected[8]{};
 uint64_t lateFrames=0;int lastLateIndex=-1;
 uint64_t hops=0,staleHops=0,injections=0,eventPreview=0,eventRelease=0,reviewKeep=0,reviewDrop=0;
 uint64_t injectionEvents=0,holdEvents=0,capacityOmissions=0,heldHops=0,holdHops=0;
 double maxHoldMs=0,tokens=0,injectStart=-1,nextRefill=144000;
 float* diagnostic=nullptr;int diagnosticCapacity=0,diagnosticCount=0;float* diag=nullptr;
 void beginDiag(double input){diag=nullptr;if(diagnostic && diagnosticCount<diagnosticCapacity){diag=diagnostic+272*diagnosticCount++;std::fill(diag,diag+272,0.f);diag[0]=float(input-origin);}}
 double sal(double f)const{if(!frame || f<=0)return 1.;if(f<30 || f>250)return 0.;double m=std::clamp(69+12*std::log2(f/440.),23.,59.);int a=std::min(35,int(m-23));double q=m-23-a;return frame[4+a]*(1-q)+frame[5+a]*q;}
 double prior(double f)const{return f>=30 && f<=250?epsilon89+(1-epsilon89)*sal(f):1.;}
 void hop(double input){
  const uint64_t previousStale=staleHops;time=input-origin;++hops;int j=int(std::floor((time/6.-256.)/64.));frame=nullptr;
  if(stream || worker){int64_t used=-1;auto& store=worker?worker->stream.frames:stream->frames;if(j>=0 && store.get(j,selected,used)){frame=selected;if(used<j)++staleHops;}else if(j>=0)++staleHops;}
  else if(j>=0 && count>0)frame=frames+std::min(j,count-1)*stride;
  if(staleHops>previousStale && j!=lastLateIndex){++lateFrames;lastLateIndex=j;}
  if(frame && stride==8){const float* p=frame;std::fill(compact89,compact89+80,0.f);compact89[0]=p[0];compact89[2]=p[1];compact89[3]=p[2];compact89[41]=p[3];for(int k=4;k<8;k+=2){int m=int(std::nearbyint(p[k]));if(m>=23 && m<=59)compact89[4+m-23]=p[k+1];}frame=compact89;}
  if(modules&32){double target=frame?frame[0]*(1-frame[2]*(1-frame[41]))*(1-frame[3]*(1-frame[41])):1.;g+=(target-g)*(1-std::exp(-256./48000./(target>g?.010:.120)));}
 }
};
}

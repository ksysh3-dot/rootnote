#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace nb5 {
constexpr int Inputs=80, Channels=22, Params=10649, Macs=10494;
struct State {
 uint32_t id=0;uint64_t steps=0;int64_t stamp=-1;
 int pos=0,n=0;float history[126*Channels]={},median[5]={};
 float raw=-100,db=-100,amp=0;
};
inline float infer(State& s,const float* x,const float* weights) {
 const float* w=weights;const float* bias=w+Channels*Inputs;
 float h[Channels],z[Channels];
 for(int o=0;o<Channels;++o){float a=0;for(int j=0;j<Inputs;++j)a+=w[o*Inputs+j]*x[j];h[o]=std::max(0.f,a+bias[o]);}
 w=bias+Channels;int offset=0;
 for(int b=0,d=1;b<6;++b,d*=2){
  bias=w+Channels*Channels*3;int size=2*d,pos=int(s.steps%size),old1=(pos+d)%size;
  const float* v0=s.history+Channels*(offset+pos);const float* v1=s.history+Channels*(offset+old1);
  for(int o=0;o<Channels;++o){float a=0;for(int j=0;j<Channels;++j){const float* k=w+(o*Channels+j)*3;a+=k[0]*v0[j];a+=k[1]*v1[j];a+=k[2]*h[j];}z[o]=std::max(0.f,h[o]+a+bias[o]);}
  std::copy_n(h,Channels,s.history+Channels*(offset+pos));std::copy_n(z,Channels,h);offset+=size;w=bias+Channels;
 }
 float a=0;for(int j=0;j<Channels;++j)a+=w[j]*h[j];return a+w[Channels];
}
inline float step(State& s,const float* x,const float* weights,uint32_t id,int64_t stamp) {
 if(s.id!=id || (s.stamp>=0 && stamp-s.stamp!=16)){s=State{};s.id=id;}
 s.stamp=stamp;s.raw=std::clamp(infer(s,x,weights)*40.f-60.f,-100.f,6.f);
 s.median[s.pos]=s.raw;s.pos=(s.pos+1)%5;s.n=std::min(5,s.n+1);
 float v[5];std::copy_n(s.median,s.n,v);std::sort(v,v+s.n);
 s.db=s.n%2?v[s.n/2]:(v[s.n/2-1]+v[s.n/2])*.5f;
 if(s.db<=-90.f)s.db=-100.f;
 s.amp=s.db<=-90.f?0.f:std::pow(10.f,s.db/20.f);++s.steps;return s.amp;
}
}

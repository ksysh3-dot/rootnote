#pragma once
#include "pvb_control_net.h"
#include <atomic>
#include <array>
#include <cstdint>
#include <memory>
#include <thread>
namespace pvb {
struct ControlFft;
struct ControlCompact {
 bool state[4]{};int on[4]{},off[4]{};
 float tauB=.71949303150177f,tau=.5f;
 void reset(){for(int k=0;k<4;++k){state[k]=false;on[k]=off[k]=0;}}
 void run(const float* p,float* out){
  for(int k=0;k<4;++k){bool b=p[k]>=(k==3?tauB:k==0?.5f:tau);on[k]=b?on[k]+1:0;off[k]=b?0:off[k]+1;if(!state[k] && on[k]>=2)state[k]=true;if(state[k] && off[k]>=6)state[k]=false;out[k]=state[k]?1.f:0.f;}
  int a=0,b=1;if(p[6]>p[5]){a=1;b=0;}
  for(int k=2;k<37;++k){if(p[5+k]>p[5+a]){b=a;a=k;}else if(p[5+k]>p[5+b])b=k;}
  out[4]=a+23;out[5]=p[5+a]*out[0];out[6]=b+23;out[7]=p[5+b]*out[0];
 }
};
// Atomic payload prevents C++ data races even while a ring slot is reused.
class ControlFrames {
 struct Slot {std::atomic<int64_t> sequence{-1};std::atomic<uint32_t> bits[8]{};};
 std::array<Slot,1024> slots_{};std::atomic<int64_t> latest_{-1};
public:
 void reset(){latest_.store(-1);for(auto& s:slots_)s.sequence.store(-1);}
 void put(int64_t j,const float* v){auto& s=slots_[j&1023];s.sequence.store(-1,std::memory_order_seq_cst);for(int k=0;k<8;++k){uint32_t b;std::memcpy(&b,v+k,4);s.bits[k].store(b,std::memory_order_seq_cst);}s.sequence.store(j,std::memory_order_seq_cst);latest_.store(j,std::memory_order_seq_cst);}
 bool get(int64_t wanted,float* out,int64_t& used)const{
  int64_t j=std::min(wanted,latest_.load(std::memory_order_seq_cst));if(j<0)return false;
  const auto& s=slots_[j&1023];if(s.sequence.load(std::memory_order_seq_cst)!=j)return false;
  for(int k=0;k<8;++k){uint32_t b=s.bits[k].load(std::memory_order_seq_cst);std::memcpy(out+k,&b,4);}
  if(s.sequence.load(std::memory_order_seq_cst)!=j)return false;
  used=j;return true;
 }
 int64_t latest()const{return latest_.load(std::memory_order_seq_cst);}
};
class ControlStream {
 ControlNet net_;ControlCompact compact_;std::unique_ptr<ControlFft> fft_;
 float raw_[128]{},low_[512]{},scratch_[4096]{};int64_t seen_=0,lowCount_=0,frame_=0;
 void frame();
public:
 ControlFrames frames;float lastProbability[42]{};float lastFeature[257]{};float lastDown=0;bool downReady=false;
 std::array<std::atomic<uint64_t>,2000> observedHistogram{};
 std::atomic<uint64_t> observedCount{0},observedMax{0};
 bool telemetry=false;uint64_t frameCount=0,frameNanoseconds=0,maxNanoseconds=0;std::array<uint64_t,2000> timeHistogram{};
 ControlStream();~ControlStream();
 bool load(const unsigned char*,size_t);bool loaded()const{return net_.loaded;}
 void reset();bool tick(float l,float r);void model(const float* f,float* p){net_.run(f,p);}void compact(const float* p,float* v){compact_.run(p,v);}
};
// Optional SPSC audio-to-worker queue. tick() performs bounded atomics only.
class ControlWorker {
 static constexpr uint64_t N=65536;struct Sample{float l,r;int64_t time;};
 std::array<Sample,N> queue_{};std::atomic<uint64_t> head_{0},tail_{0};std::atomic<bool> stop_{false};std::thread thread_;
 int64_t inputTime_=0;
public:
 ControlStream stream;std::atomic<uint64_t> dropped{0},processed{0};
 ~ControlWorker(){stop();}
 void start();void stop();void reset();bool tick(float l,float r);
 void drain(); // Test/lifecycle only; never called by an audio callback.
};
}

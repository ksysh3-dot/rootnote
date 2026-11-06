#include "pvb_control_stream.h"
#include "pvb_stable_tables.h"
#include "pvb_stable_host_math.h"
#include <chrono>
#define DUCC0_NO_LOWLEVEL_THREADING
#define DUCC0_NO_SIMD
#include "stable_vendor/ducc0/fft/fft1d_impl.h"
namespace pvb {
struct ControlFft {ducc0::detail_fft::pocketfft_r<float> plan{512};};
ControlStream::ControlStream()=default;ControlStream::~ControlStream()=default;
bool ControlStream::load(const unsigned char* p,size_t n){try{if(!net_.load(p,n))return false;fft_=std::make_unique<ControlFft>();if(fft_->plan.bufsize()>4096)return false;reset();return true;}catch(...){return false;}}
void ControlStream::reset(){net_.reset();compact_.reset();frames.reset();std::memset(raw_,0,sizeof raw_);std::memset(low_,0,sizeof low_);seen_=lowCount_=frame_=0;downReady=false;frameCount=frameNanoseconds=maxNanoseconds=0;timeHistogram.fill(0);}
void ControlStream::frame(){
 auto began=telemetry?std::chrono::steady_clock::now():std::chrono::steady_clock::time_point{};
 float input[512];for(int i=0;i<512;++i)input[i]=low_[i]*kStableWin[i];
 auto z=fft_->plan.exec(input,scratch_,1.f,true,1);
 for(int i=0;i<257;++i){float re=i==0?z[0]:i==256?z[511]:z[2*i-1],im=(i==0 || i==256)?0.f:z[2*i];float m=stableHostMagnitude(re,im);lastFeature[i]=std::clamp(stableHostLog10(m*m+1e-8f),-8.f,4.f)/4.f;}
 net_.run(lastFeature,lastProbability);float v[8];compact_.run(lastProbability,v);frames.put(frame_++,v);++frameCount;
 if(telemetry){auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-began).count();frameNanoseconds+=ns;maxNanoseconds=std::max(maxNanoseconds,uint64_t(ns));++timeHistogram[std::min<size_t>(1999,ns/10000)];}
}
bool ControlStream::tick(float l,float r){
 downReady=false;if(!loaded())return false;
 const int64_t t=seen_++;raw_[t&127]=(l+r)*.5f;
 if(t%6 || t<60)return false;
 float v=0;for(int q=120;q>=0;--q)if(t>=q)v+=kStableFir[q]*raw_[(t-q)&127];
 lastDown=v;downReady=true;
 // Initial 256 zeros are exactly spectrum(...): pad(512-256, 0).
 if(lowCount_==0)std::fill(low_,low_+256,0.f);
 // Keep end-aligned 512-sample windows in chronological order.
 ++lowCount_;
 if(lowCount_<=256){low_[256+lowCount_-1]=v;if(lowCount_==256){frame();std::memmove(low_,low_+64,448*sizeof(float));}return lowCount_==256;}
 low_[448+(lowCount_-257)%64]=v;
 if((lowCount_-256)%64==0){frame();std::memmove(low_,low_+64,448*sizeof(float));return true;}return false;
}
void ControlWorker::start(){stop();stop_.store(false);thread_=std::thread([this]{int64_t expected=0;while(!stop_.load(std::memory_order_acquire)){uint64_t t=tail_.load(std::memory_order_relaxed),h=head_.load(std::memory_order_acquire);if(t==h){std::this_thread::yield();continue;}Sample v=queue_[t&(N-1)];if(v.time!=expected){stream.reset();expected=v.time;}stream.tick(v.l,v.r);expected=v.time+1;processed.store(t+1,std::memory_order_release);tail_.store(t+1,std::memory_order_release);}});}
void ControlWorker::stop(){stop_.store(true,std::memory_order_release);if(thread_.joinable())thread_.join();}
void ControlWorker::reset(){stop();head_.store(0);tail_.store(0);processed.store(0);dropped.store(0);inputTime_=0;stream.reset();}
bool ControlWorker::tick(float l,float r){uint64_t h=head_.load(std::memory_order_relaxed),t=tail_.load(std::memory_order_acquire);int64_t tm=inputTime_++;if(h-t==N){dropped.fetch_add(1,std::memory_order_relaxed);return false;}queue_[h&(N-1)]={l,r,tm};head_.store(h+1,std::memory_order_release);return true;}
void ControlWorker::drain(){uint64_t h=head_.load(std::memory_order_acquire);while(processed.load(std::memory_order_acquire)<h)std::this_thread::yield();}
}

#include "pvb_engine.h"
#include "pvb_control_stream.h"
#include <fstream>
extern "C" {
void* s91_create(const unsigned char* p,int n){auto* s=new pvb::ControlStream();if(!s->load(p,n)){delete s;return nullptr;}return s;}
void s91_destroy(void* h){delete static_cast<pvb::ControlStream*>(h);}
void s91_reset(void* h){static_cast<pvb::ControlStream*>(h)->reset();}
void s91_model(void* h,const float* f,float* p,int n){auto& s=*static_cast<pvb::ControlStream*>(h);for(int i=0;i<n;++i)s.model(f+i*257,p+i*42);}
void s91_compact(void* h,const float* p,float* v,int n){auto& s=*static_cast<pvb::ControlStream*>(h);for(int i=0;i<n;++i)s.compact(p+i*42,v+i*8);}
int s91_stream(void* h,const float* x,int n,float* p,float* v,float* down,int* nd){auto& s=*static_cast<pvb::ControlStream*>(h);int frames=0,d=0;for(int i=0;i<n;++i){bool ready=s.tick(x[2*i],x[2*i+1]);if(s.downReady && down)down[d++]=s.lastDown;if(ready){if(p)std::copy_n(s.lastProbability,42,p+42*frames);if(v){int64_t used;bool ok=s.frames.get(s.frames.latest(),v+8*frames,used);if(!ok)return -1;}++frames;}}if(nd)*nd=d;return frames;}
int s91_engine_load(void* e,const unsigned char* p,int n,int worker){auto& v=*static_cast<pvb::Engine*>(e);return v.loadControl91(p,n) && (!worker || v.loadWorker91(p,n));}
int s91_engine_enable(void* e,int enabled,int worker,int64_t origin){return static_cast<pvb::Engine*>(e)->setStream91(enabled,worker,origin);}
int s91_engine_stats(void* e,double* p,int n){if(n<8)return 0;auto& v=*static_cast<pvb::Engine*>(e);p[0]=v.stale91();p[1]=v.control91_.frameCount;p[2]=v.separatorTicks88_;p[3]=v.control91_.frameNanoseconds;p[4]=v.control91_.maxNanoseconds;p[5]=v.worker91_?v.worker91_->dropped.load():0;p[6]=8;p[7]=v.latencyFrames();return 8;}
int s91_worker_test(const unsigned char* p,int size,const float* x,int n,float* out){pvb::ControlWorker w;if(!w.stream.load(p,size))return -1;w.start();int64_t j=0;for(int i=0;i<n;){int end=std::min(n,i+1024);for(;i<end;++i)if(!w.tick(x[2*i],x[2*i+1]))return -2;w.drain();int64_t last=w.stream.frames.latest();for(;j<=last;++j){int64_t used;if(!w.stream.frames.get(j,out+j*8,used) || used!=j)return -3;}}w.stop();return int(j);}
}

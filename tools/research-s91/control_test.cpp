#include "pvb_control_stream.h"
#include "pvb_engine.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <vector>
#include <cstdlib>
static thread_local bool countNew=false;
static thread_local unsigned allocations=0;
void* operator new(std::size_t n){if(countNew)++allocations;if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete[](void* p)noexcept{::operator delete(p);}
void operator delete[](void* p,std::size_t)noexcept{::operator delete(p);}
int main(int argc,char** argv){
 assert(argc==2);std::ifstream f(argv[1],std::ios::binary);std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});assert(b.size()==ControlNet::kBytes);
 auto s=std::make_unique<pvb::ControlStream>();assert(!s->load(b.data(),b.size()-4));assert(s->load(b.data(),b.size()));
 pvb::ControlCompact c;float p[42]{},out[8];p[0]=p[1]=p[2]=p[3]=1;for(int i=5;i<42;++i)p[i]=.5f;
 c.run(p,out);assert(out[0]==0);c.run(p,out);assert(out[0]==1 && out[4]==23 && out[6]==24);
 for(int k=0;k<4;++k)p[k]=0;for(int i=0;i<5;++i){c.run(p,out);assert(out[0]==1);}c.run(p,out);assert(out[0]==0);
 std::vector<float> values;values.reserve(8*250);
 countNew=true;
 for(int i=0;i<96000;++i)if(s->tick(.1f*std::sin(i*.008),.12f*std::sin(i*.01))){float v[8];int64_t used;assert(s->frames.get(s->frames.latest(),v,used));for(float x:v){assert(std::isfinite(x));values.push_back(x);}}
 countNew=false;assert(allocations==0);s->reset();size_t pos=0;
 for(int i=0;i<96000;++i)if(s->tick(.1f*std::sin(i*.008),.12f*std::sin(i*.01))){float v[8];int64_t used;assert(s->frames.get(s->frames.latest(),v,used));for(float x:v)assert(x==values[pos++]);}
 assert(pos==values.size());pvb::ControlWorker worker;assert(worker.stream.load(b.data(),b.size()));worker.start();
 for(int i=0;i<96000;){int stop=std::min(96000,i+1024);for(;i<stop;++i)assert(worker.tick(.1f*std::sin(i*.008),.12f*std::sin(i*.01)));worker.drain();}
 worker.stop();assert(worker.dropped.load()==0);int64_t j=worker.stream.frames.latest();float a[8],v[8];int64_t u;assert(worker.stream.frames.get(j,a,u));assert(s->frames.get(j,v,u));for(int k=0;k<8;++k)assert(a[k]==v[k]);
 // Exercise the actual modules33 consumer, dry alignment and output limiter
 // with sanitizer instrumentation too; no separator weights are loaded.
 auto engine=std::make_unique<pvb::Engine>(48000);float params[pvb::P_COUNT];pvb::defaultParams(params);
 params[8]=-5;params[11]=0;params[22]=1;params[23]=6;params[24]=0;params[57]=1;
 assert(engine->trySetParams(params,pvb::P_COUNT));assert(engine->loadControl91(b.data(),b.size()));assert(engine->setStream91(true,false,49152));
 float block[74];countNew=true;
 for(int base=0;base<49152+96000+48000;base+=37){for(int k=0;k<37;++k){float v=base+k>=49152 && base+k<49152+96000?.1f*std::sin((base+k)*.008):0.f;block[2*k]=block[2*k+1]=v;}engine->process(block,37);for(float v:block)assert(std::isfinite(v));}
 countNew=false;assert(allocations==0);assert(engine->latencyFrames()==7140);double stats[10];assert(engine->stats88(stats,10)==10 && stats[6]==0 && stats[7]==0);
 b[3]=0x7f;b[2]=0x80;b[1]=b[0]=0;assert(!s->load(b.data(),b.size()));
 std::cout<<"PASS control unit: finite weights, hysteresis2/6, stable top2, reset, callback allocations0, worker parity\n";
}

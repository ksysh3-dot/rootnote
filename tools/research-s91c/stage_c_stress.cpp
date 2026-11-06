#include "pvb_engine.h"
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <new>
static bool countAlloc=false;static size_t allocations=0;
void* operator new(std::size_t size){if(countAlloc)++allocations;void* p=std::malloc(size);if(!p)throw std::bad_alloc();return p;}
void operator delete(void* p)noexcept{std::free(p);}void operator delete(void* p,std::size_t)noexcept{std::free(p);}
static std::vector<unsigned char> read(const std::string& s){std::ifstream f(s,std::ios::binary);return {(std::istreambuf_iterator<char>(f)),{}};}
int main(int argc,char** argv){
 if(argc!=2)return 2;
 std::string root=argv[1];
 auto sep=read(root+"/app/src/main/assets/T3a16_96.bin");
 auto ctrl=read(root+"/app/src/main/assets/E60KD.bin");
 auto epoch=read(root+"/app/src/main/assets/stable_ab_1218.bin");
 auto* e=new pvb::Engine(48000);
 float buf[2048];uint32_t rng=9103;uint64_t callbacks=0;
 int64_t snapshot[pvb::Engine::kStageCSize];
 for(int mode:{0,1,2,3,4,3,2,0}){
  const auto& weight=mode==3?ctrl:mode==4?epoch:sep;
  if(!e->prepareStageC(mode,mode>=2?weight.data():nullptr,mode>=2?weight.size():0,false,true,48000))return 3;
  float p[pvb::P_COUNT];pvb::defaultParams(p);p[pvb::P_VB_ON]=1;p[pvb::P_RAMP_MS]=0;p[pvb::P_P1PPP]=mode==0?0:mode==2||mode==4?2:1;
  if(!e->trySetParams(p,pvb::P_COUNT))return 4;
  for(int block=0;block<260;++block){
   int n=block%17==0?1024:block%3==0?37:block%5==0?256:64;
   for(int j=0;j<2*n;++j){rng=rng*1664525+1013904223;buf[j]=float(int(rng>>8)%10000-5000)*.00003f;}
   if(block==100 || block==200)e->requestReset();
   countAlloc=true;e->process(buf,n);countAlloc=false;++callbacks;
   for(int j=0;j<2*n;++j)if(!std::isfinite(buf[j]))return 5;
   e->copyStageC(snapshot);
  }
  if(mode==3 && (snapshot[0]<=0 || snapshot[4]!=0 || snapshot[6]!=1))return 6;
 }
 std::cout<<"callbacks="<<callbacks<<" callback_allocations="<<allocations<<" nonfinite=0 modes=8\n";
 delete e;return allocations?7:0;
}

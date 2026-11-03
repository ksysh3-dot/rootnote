#include "pvb_engine.h"
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <new>
#include <limits>
static bool countAlloc=false;static size_t allocations=0;
void* operator new(std::size_t size){if(countAlloc)++allocations;void* p=std::malloc(size);if(!p)throw std::bad_alloc();return p;}
void operator delete(void* p)noexcept{std::free(p);}void operator delete(void* p,std::size_t)noexcept{std::free(p);}
int main(int argc,char**argv){
 if(argc!=2)return 2;std::ifstream f(argv[1],std::ios::binary);std::vector<unsigned char>w((std::istreambuf_iterator<char>(f)),{});
 auto* e=new pvb::Engine(48000);if(!e->loadStableWeights(w.data(),w.size()))return 3;
 float p[pvb::P_COUNT];pvb::defaultParams(p);p[pvb::P_VB_ON]=1;p[pvb::P_VB_ALGO]=6;p[pvb::P_RAMP_MS]=0;p[pvb::P_P1PPP]=2;
 if(!e->trySetParams(p,pvb::P_COUNT))return 4;e->setDiagnosticCapture(true);
 float buf[2048],layer[2048],full[2048],trace[90];uint32_t rng=7403;int nonfinite=0,diagnostic=0;
 for(int block=0;block<3200;block++){
  if(block%233==0){p[pvb::P_P1PPP]=float((block/233)%3);e->setParams(p,pvb::P_COUNT);}
  if(block%317==0)e->requestReset();
  if(block==601){e->setSampleRate(44100);p[pvb::P_P1PPP]=0;e->setParams(p,pvb::P_COUNT);}
  if(block==777){e->setSampleRate(48000);p[pvb::P_P1PPP]=2;e->setParams(p,pvb::P_COUNT);}
  const int n=block%17==0?1024:block%3==0?37:64;
  for(int j=0;j<2*n;j++){rng=rng*1664525+1013904223;buf[j]=float(int(rng>>8)%10000-5000)*.00005f;}
  if(block%101==0)buf[0]=std::numeric_limits<float>::quiet_NaN();
  if(block%103==0)buf[1]=std::numeric_limits<float>::infinity();
  countAlloc=true;e->process(buf,n);countAlloc=false;
  if(!e->copyDiagnostic(layer,full,2*n,trace,90))return 5;
  for(int j=0;j<2*n;j++){if(!std::isfinite(buf[j]))nonfinite++;if(buf[j]!=full[j])diagnostic++;}
 }
 std::cout<<"nonfinite="<<nonfinite<<" diagnostic="<<diagnostic<<" callback_allocations="<<allocations<<"\n";
 delete e;return nonfinite||diagnostic||allocations?6:0;
}

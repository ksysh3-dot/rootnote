#include "pvb_engine.h"
#include <cassert>
#include <cmath>
#include <memory>
int main() {
 pvb::ResultantCore c;double v[30]={0,0,0,15,22,6,8,30,.05,.1,1.,30,24,.03,0,200,1.5,16,2,150,8,1,0,10,0,0,0,0,0,0};
 static_assert(sizeof(v)/sizeof(v[0])==30,"historical prefix");
 assert(c.setParams(v,30));assert(c.setParams(nullptr,0));assert(!c.setParams(nullptr,1));
 assert(!c.setParams(v,pvb::ResultantCore::kParams+1));
 auto e=std::make_unique<pvb::Engine>(48000);float p[pvb::P_COUNT];pvb::defaultParams(p);p[pvb::P_VB_ON]=1;p[pvb::P_RAMP_MS]=0;
 float x[2048]={};for(int algo:{16,17,6,17,16}) {
  p[pvb::P_VB_ALGO]=static_cast<float>(algo);e->setParams(p,pvb::P_COUNT);e->requestReset();
  for(int block=0;block<80;++block){for(int i=0;i<2048;++i)x[i]=.1f*std::sin(i*.071f+block);e->process(x,1024);}
 }
 return 0;
}

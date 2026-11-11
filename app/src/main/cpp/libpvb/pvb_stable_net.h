#pragma once
// Frozen s71 FP32 forward; GPL application asset, see STABLE_MODEL.md.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>
struct StableNet {
 std::vector<float> prew,preb,dw[6],db[6],pw[6],pb[6],postw,postb;
 std::vector<float> pt,wt[6],ot; float hist[6][64][96]{}; long step=0;
 bool read(std::istream &f,std::vector<float>&v,size_t n){v.resize(n);return bool(f.read(reinterpret_cast<char*>(v.data()),n*4));}
 StableNet() = default;
 void load(const unsigned char* bytes,size_t size){
  std::string data(reinterpret_cast<const char*>(bytes),size);
  std::istringstream f(data,std::ios::binary);
  bool ok=read(f,prew,96*257)&&read(f,preb,96);
  for(int i=0;i<6;i++)ok=ok&&read(f,dw[i],96*3)&&read(f,db[i],96)&&read(f,pw[i],96*96)&&read(f,pb[i],96);
  ok=ok&&read(f,postw,514*96)&&read(f,postb,514);
  if(!ok || size!=531208)throw 1;
  for(size_t i=0;i<size;i+=4){float x;std::memcpy(&x,bytes+i,4);if(!std::isfinite(x))throw 1;}
  pt.resize(257*96);ot.resize(96*514);
  for(int j=0;j<257;j++)for(int o=0;o<96;o++)pt[j*96+o]=prew[o*257+j];
  for(int i=0;i<6;i++){wt[i].resize(96*96);for(int j=0;j<96;j++)for(int o=0;o<96;o++)wt[i][j*96+o]=pw[i][o*96+j];}
  for(int j=0;j<96;j++)for(int o=0;o<514;o++)ot[j*514+o]=postw[o*96+j];
 }
 void reset(){std::memset(hist,0,sizeof(hist));step=0;}
 void run(const float* feat,float* out){
  float z[96],v[96],next[96];
  std::memcpy(z,preb.data(),sizeof(z));
  for(int j=0;j<257;j++)for(int o=0;o<96;o++)z[o]+=pt[j*96+o]*feat[j];
  for(float& a:z)a=std::max(0.f,a);
  for(int i=0;i<6;i++){
   int d=1<<i,n=2*d,k=step%n,k1=(step+d)%n;
   for(int c=0;c<96;c++)v[c]=std::max(0.f,db[i][c]+dw[i][c*3]*hist[i][k][c]+dw[i][c*3+1]*hist[i][k1][c]+dw[i][c*3+2]*z[c]);
   std::memcpy(next,pb[i].data(),sizeof(next));
   for(int j=0;j<96;j++)for(int o=0;o<96;o++)next[o]+=wt[i][j*96+o]*v[j];
   for(int o=0;o<96;o++)next[o]=z[o]+.2f*std::max(0.f,next[o]);
   std::memcpy(hist[i][k],z,sizeof(z));std::memcpy(z,next,sizeof(z));
  }
  std::memcpy(out,postb.data(),514*sizeof(float));
  for(int j=0;j<96;j++)for(int o=0;o<514;o++)out[o]+=ot[j*514+o]*z[j];
  for(int o=0;o<514;o++){const float a=out[o];out[o]=o<257 ? 2.f/(1.f+std::exp(-a))-.5f : 1.5f*std::tanh(a);}
  step++;
 }
};

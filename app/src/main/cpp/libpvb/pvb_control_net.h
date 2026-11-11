#pragma once
// s91: generated E60KD FP32 layout: pre, 8 x (dw, db, pw, pb), post.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <vector>
struct ControlNet {
 using f4=float __attribute__((vector_size(16)));
 static f4 ld4(const float* p){f4 v;std::memcpy(&v,p,16);return v;}
 static void st4(float* p,f4 v){std::memcpy(p,&v,16);}
 static void tr(const std::vector<float>& s,std::vector<float>& d,size_t O,size_t J){d.resize(O*J);for(size_t o=0;o<O;++o)for(size_t j=0;j<J;++j)d[j*O+o]=s[o*J+j];}
 static constexpr size_t kBytes=106410*4;
 std::vector<float> prew,preb,dw[8],db[8],pw[8],pb[8],postw,postb,hist[8],prewt,pwt[8],postwt;
 uint64_t step=0;bool loaded=false;
 bool load(const unsigned char* p,size_t n) {
  if(!p || n!=kBytes)return false;
  for(size_t j=0;j<n;j+=4){float f;std::memcpy(&f,p+j,4);if(!std::isfinite(f))return false;}
  size_t pos=0;
  auto read=[&](std::vector<float>& v,size_t count){v.resize(count);std::memcpy(v.data(),p+pos,count*4);pos+=count*4;};
  read(prew,96*257);read(preb,96);tr(prew,prewt,96,257);
  for(int i=0;i<8;++i){read(dw[i],96*3);read(db[i],96);read(pw[i],96*96);read(pb[i],96);tr(pw[i],pwt[i],96,96);hist[i].resize(2*(1<<i)*96);}
  read(postw,42*96);read(postb,42);tr(postw,postwt,42,96);loaded=pos==n;reset();return loaded;
 }
 void reset(){for(auto& h:hist)std::fill(h.begin(),h.end(),0.f);step=0;}
 void run(const float* feat,float* out) {
  float z[96],v[96],next[96];
  for(int o=0;o<96;o+=8){
   f4 a0=ld4(&preb[o]),a1=ld4(&preb[o+4]);
   for(int j=0;j<257;++j){float x=feat[j];f4 vx={x,x,x,x};a0+=ld4(&prewt[j*96+o])*vx;a1+=ld4(&prewt[j*96+o+4])*vx;}
   float a[8];st4(a,a0);st4(a+4,a1);for(int k=0;k<8;++k)z[o+k]=std::max(0.f,a[k]);
  }
  for(int i=0;i<8;++i){int d=1<<i,n=2*d,k=step%n,k1=(step+d)%n;
   for(int c=0;c<96;++c)v[c]=std::max(0.f,db[i][c]+dw[i][c*3]*hist[i][k*96+c]+dw[i][c*3+1]*hist[i][k1*96+c]+dw[i][c*3+2]*z[c]);
   for(int o=0;o<96;o+=8){
    f4 a0=ld4(&pb[i][o]),a1=ld4(&pb[i][o+4]);
    for(int j=0;j<96;++j){float x=v[j];f4 vx={x,x,x,x};a0+=ld4(&pwt[i][j*96+o])*vx;a1+=ld4(&pwt[i][j*96+o+4])*vx;}
    float a[8];st4(a,a0);st4(a+4,a1);for(int k=0;k<8;++k)next[o+k]=z[o+k]+.2f*std::max(0.f,a[k]);
   }
   std::memcpy(hist[i].data()+k*96,z,sizeof z);std::memcpy(z,next,sizeof z);
  }
  for(int o=0;o<40;o+=8){
   f4 a0=ld4(&postb[o]),a1=ld4(&postb[o+4]);
   for(int j=0;j<96;++j){float x=z[j];f4 vx={x,x,x,x};a0+=ld4(&postwt[j*42+o])*vx;a1+=ld4(&postwt[j*42+o+4])*vx;}
   float a[8];st4(a,a0);st4(a+4,a1);for(int k=0;k<8;++k){int c=o+k;out[c]=c==4?std::clamp(a[k],0.f,1.f):1.f/(1.f+std::exp(-a[k]));}
  }
  for(int o=40;o<42;++o){float a=postb[o];for(int j=0;j<96;++j)a+=postw[o*96+j]*z[j];out[o]=1.f/(1.f+std::exp(-a));}
  ++step;
 }
};

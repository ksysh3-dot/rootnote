// Frozen s71 stream math; SciPy1.18.1 ducc FFT, BSD/GPL notices in stable_vendor.
#include "pvb_stable.h"
#define DUCC0_NO_LOWLEVEL_THREADING
#define DUCC0_NO_SIMD
#include "stable_vendor/ducc0/fft/fft1d_impl.h"
namespace pvb {
struct StableFft {ducc0::detail_fft::pocketfft_r<float> plan{512};};
StableSeparator::StableSeparator() = default;
StableSeparator::~StableSeparator() = default;
void StableSeparator::frame(){
  std::complex<float> sp[2][257];float feat[257],mask[514],input[512];
  for(int c=0;c<2;c++){
   for(int i=0;i<512;i++)input[i]=low_[i][c]*kStableWin[i];
   auto result=fft_->plan.exec(input,scratch_,1.f,true,1);
   sp[c][0]={result[0],0};sp[c][256]={result[511],0};
   for(int i=1;i<256;i++)sp[c][i]={result[2*i-1],result[2*i]};
  }
  for(int i=0;i<257;i++){
   auto m=(sp[0][i]+sp[1][i])*.5f;float mag=std::abs(m);float power=mag*mag+1e-8f;
   feat[i]=std::min(4.f,std::max(-8.f,std::log10(power)))/4.f;
  }
  net_.run(feat,mask);
  for(int c=0;c<2;c++){
   for(int i=0;i<257;i++)sp[c][i]*=std::complex<float>(mask[i],mask[257+i]);
   input[0]=sp[c][0].real();input[511]=sp[c][256].real();
   for(int i=1;i<256;i++){input[2*i-1]=sp[c][i].real();input[2*i]=sp[c][i].imag();}
   auto result=fft_->plan.exec(input,scratch_,1.f/512.f,false,1);
   for(int i=0;i<512;i++)ola_[i][c]+=result[i]*kStableWin[i];
  }
  for(int i=0;i<512;i++)den_[i]+=kStableWin[i]*kStableWin[i];
  if(frame_>=7){
   for(int i=0;i<64;i++)for(int c=0;c<2;c++)up_[20+i][c]=ola_[i][c]/std::max(den_[i],1e-8f);
   for(int i=0;i<384;i++){
    int64_t pos=upsamples_-60+3192+i;
    for(int c=0;c<2;c++){
     float value=0;int phase=i%6,j=i/6;
     for(int q=(120-phase)/6;q>=0;q--)value+=(kStableFir[phase+6*q]*6.f)*up_[20+j-q][c];
     ready_[pos&8191][c]=value;
    }
   }
   for(int i=0;i<20;i++)for(int c=0;c<2;c++)up_[i][c]=up_[64+i][c];
   upsamples_+=384;
  }
  for(int i=0;i<448;i++)for(int c=0;c<2;c++){low_[i][c]=low_[i+64][c];ola_[i][c]=ola_[i+64][c];}
  for(int i=448;i<512;i++)for(int c=0;c<2;c++)ola_[i][c]=0;
  for(int i=0;i<448;i++)den_[i]=den_[i+64];
  for(int i=448;i<512;i++)den_[i]=0;
  lowN_=448;frame_++;
 }
bool StableSeparator::load(const unsigned char* p,size_t size){try{net_.load(p,size);fft_=std::make_unique<StableFft>();if(fft_->plan.bufsize()>4096)throw 1;loaded_=true;reset();return true;}catch(...){return false;}}
void StableSeparator::reset(){
  net_.reset();std::memset(raw_,0,sizeof raw_);std::memset(low_,0,sizeof low_);std::memset(ola_,0,sizeof ola_);
  std::memset(den_,0,sizeof den_);std::memset(up_,0,sizeof up_);std::memset(ready_,0,sizeof ready_);std::memset(mix_,0,sizeof mix_);
  seen_=down_=frame_=upsamples_=0;lowN_=448;
 }
bool StableSeparator::tick(float l,float r,float* separated,float* original){
  int64_t t=seen_;raw_[t&127][0]=l;raw_[t&127][1]=r;mix_[t&8191][0]=l;mix_[t&8191][1]=r;seen_++;
  if(seen_%6==0){
   float d[2]{};int64_t source=seen_-6;
   for(int c=0;c<2;c++)for(int q=120;q>=0;q--)if(source>=q)d[c]+=kStableFir[q]*raw_[(source-q)&127][c];
   if(++down_>10){for(int c=0;c<2;c++)low_[lowN_][c]=d[c];if(++lowN_==512)frame();}
  }
  if(t<3192)return false;
  for(int c=0;c<2;c++){separated[c]=ready_[t&8191][c];original[c]=mix_[(t-3192)&8191][c];}return true;
 }
}

#pragma once
#include "pvb_stable_net.h"
#include "pvb_stable_tables.h"
#include <complex>
#include <cstdint>
#include <memory>
namespace pvb {
struct StableFft;
// Bounded streaming replica of s71_stream.py. No allocation, IO or locks in tick().
class StableSeparator {
 StableNet net_;
 float raw_[128][2]{}, low_[512][2]{}, ola_[512][2]{}, den_[512]{}, up_[84][2]{};
 float ready_[8192][2]{}, mix_[8192][2]{};
 int64_t seen_=0,down_=0,frame_=0,upsamples_=0;
 int lowN_=448;
 bool loaded_=false;
 std::unique_ptr<StableFft> fft_;
 float scratch_[4096]{};
 void frame();
public:
 StableSeparator();
 ~StableSeparator();
 bool load(const unsigned char* p,size_t size);
 bool loaded()const{return loaded_;}
 void reset();
 bool tick(float l,float r,float* separated,float* original);
};
}

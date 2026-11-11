#pragma once
// Scalar transcription of NumPy2.5.4 SIMD cabsolute and Intel SVML log10f16.
// Copyright (C)2023 Intel Corporation. BSD-3-Clause. See STABLE_HOST_MATH_LICENSE.txt.
#include <cmath>
#include <cstring>
#include <cstdint>
namespace pvb {
static constexpr float kStableLog10[6][16] = {
{0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f,0x1.0000000000000p+0f},
{-0x1.935d360000000p-4f,-0x1.4df9e80000000p-4f,-0x1.1758ec0000000p-4f,-0x1.d794600000000p-5f,-0x1.9153360000000p-5f,-0x1.58153e0000000p-5f,-0x1.2901b60000000p-5f,-0x1.01f5e40000000p-5f,-0x1.0475520000000p-2f,-0x1.cac6900000000p-3f,-0x1.95f7720000000p-3f,-0x1.68d12a0000000p-3f,-0x1.41fffe0000000p-3f,-0x1.2074160000000p-3f,-0x1.0352380000000p-3f,-0x1.d3d09c0000000p-4f},
{0x1.27b1100000000p-3f,0x1.2150f80000000p-3f,0x1.172b860000000p-3f,0x1.0afe160000000p-3f,0x1.fbc0700000000p-4f,0x1.e101b20000000p-4f,0x1.c6983c0000000p-4f,0x1.ad06660000000p-4f,0x1.58dd1c0000000p-4f,0x1.aa94a20000000p-4f,0x1.e61e800000000p-4f,0x1.0846ba0000000p-3f,0x1.16e0660000000p-3f,0x1.2059200000000p-3f,0x1.25d75a0000000p-3f,0x1.283ff00000000p-3f},
{-0x1.bcb5360000000p-3f,-0x1.bc4cee0000000p-3f,-0x1.bb07ea0000000p-3f,-0x1.b8c02c0000000p-3f,-0x1.b57a160000000p-3f,-0x1.b14dfa0000000p-3f,-0x1.ac5c040000000p-3f,-0x1.a6c5f00000000p-3f,-0x1.d1c4f80000000p-3f,-0x1.c8ce8e0000000p-3f,-0x1.c334e60000000p-3f,-0x1.bfe0b40000000p-3f,-0x1.be0ae00000000p-3f,-0x1.bd25a00000000p-3f,-0x1.bccc560000000p-3f,-0x1.bcb8100000000p-3f},
{0x1.bcb7b00000000p-2f,0x1.bcb68a0000000p-2f,0x1.bcafb00000000p-2f,0x1.bc9d620000000p-2f,0x1.bc7a6e0000000p-2f,0x1.bc42cc0000000p-2f,0x1.bbf3b20000000p-2f,0x1.bb8b760000000p-2f,0x1.bc11da0000000p-2f,0x1.bc65ce0000000p-2f,0x1.bc92ce0000000p-2f,0x1.bca9200000000p-2f,0x1.bcb2fe0000000p-2f,0x1.bcb6a00000000p-2f,0x1.bcb7940000000p-2f,0x1.bcb7b20000000p-2f},
{0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f,0x1.3441360000000p-2f}};
inline float stableHostMagnitude(float re,float im){
 re=std::abs(re);im=std::abs(im);float large=std::max(re,im),small=std::min(re,im);
 if(large==0.f)return 0.f;
 if(!std::isfinite(large))return std::hypot(re,im);
 const float ratio=small/large;return std::sqrt(std::fma(ratio,ratio,1.f))*large;
}
inline float stableHostLog10(float x){
 if(!(x>0.f) || !std::isfinite(x))return std::log10(x);
 uint32_t bits;std::memcpy(&bits,&x,4);int exponent=int((bits>>23)&255)-127;
 if(exponent==-127)return std::log10(x);
 bits=(bits&0x007fffffU)|0x3f800000U;float mant;std::memcpy(&mant,&bits,4);
 if(mant>=1.5f){mant*=.5f;exponent++;}
 std::memcpy(&bits,&mant,4);int index=(bits>>19)&15;float r=mant-1.f;
 float p=std::fma(kStableLog10[1][index],r,kStableLog10[2][index]);
 p=std::fma(p,r,kStableLog10[3][index]);p=std::fma(p,r,kStableLog10[4][index]);
 float e=float(exponent)*kStableLog10[5][0];return std::fma(p,r,e);
}
}

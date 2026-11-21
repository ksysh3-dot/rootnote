#include "way3alt1_synth.h"
namespace alt1 {
constexpr double pi=3.141592653589793238462643383279502884;
void addPartial(double amplitude,int order,double frequency,double phase,double offset,double* grain){
 for(int g=0;g<32;++g)grain[g]+=amplitude*std::cos(order*(phase+2*pi*frequency*(g-16)/3000)+offset);
}
double shapeSample(double phase,double amplitude,int shape){
 const double x=std::cos(phase);
 if(shape==Nonlinear){
  // Apply the amplitude before the fixed transfer function.
  const double u=std::tanh(amplitude*x/kNonlinearScale);
  double t0=1.,t1=u,y=0.;
  for(int k=2;k<=8;++k){double t=2*u*t1-t0;const double dc=k%2?0.:(k%4?-1.:1.);y+=kStrict[k-2]*(t-dc);t0=t1;t1=t;}
  return kNonlinearScale*y;
 }
 if(shape==Poly){
  // Preserve the phase offsets using T_k and sin(theta) U_(k-1).
  // This is a unit-carrier polynomial, with the envelope outside it.
  double c0=1.,c1=x,s0=0.,s1=std::sin(phase),y=0.;
  for(int k=2;k<=8;++k){double c=2*x*c1-c0,s=2*x*s1-s0;
   y+=kStrict[k-2]*(c*kPhaseCos[k-2]-s*kPhaseSin[k-2]);c0=c1;c1=c;s0=s1;s1=s;}
  return amplitude*y;
 }
 // Sum orders 2..8, constant ratio r; no f-dependent order.
 const double r=.85,r7=std::pow(r,7),r8=r7*r;
 const double y=(std::cos(2*phase)-r*x-r7*std::cos(9*phase)+r8*std::cos(8*phase))/(1-2*r*x+r*r);
 return amplitude*kDsfScale*y;
}
void addShape(double amplitude,double frequency,double phase,int shape,double* grain){
 for(int g=0;g<32;++g)grain[g]+=shapeSample(phase+2*pi*frequency*(g-16)/3000,amplitude,shape);
}
}
extern "C" void way3alt1_shape(const double* phase,const double* amplitude,int n,int shape,double* out){
 for(int i=0;i<n;++i)out[i]=alt1::shapeSample(phase[i],amplitude[i],shape);
}

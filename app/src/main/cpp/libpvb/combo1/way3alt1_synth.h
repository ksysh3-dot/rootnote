#pragma once
#include <cmath>
#include <algorithm>
#include "way3alt1_coefficients.h"
namespace alt1 {
enum Flags { Fixed=1, Strict=2, Nonlinear=4, All=8, Post=16, Numeric=32, Poly=64, Dsf=128 };
inline bool fixed(int f){return f&(Fixed|Nonlinear|Poly|Dsf);}
inline bool strict(int f){return f&(Strict|Nonlinear|Poly|Dsf);}
struct EqState {
 double z[3][2]{};
 void clear(){for(auto& s:z)s[0]=s[1]=0.;}
 double tick(double x,bool strictMode){
  const auto& sos=strictMode?kSosStrict:kSosKeep;
  for(int j=0;j<3;++j){const auto* c=sos[j];double y=c[0]*x+z[j][0];z[j][0]=c[1]*x-c[4]*y+z[j][1];z[j][1]=c[2]*x-c[5]*y;x=y;}return x;
 }
};
// A synthesis boundary with numeric controls only. 'grain' is output only;
// there is no raw-audio input, feature array, tracker or Engine reference.
void addPartial(double amplitude,int order,double frequency,double phase,double offset,double* grain);
void addShape(double amplitude,double frequency,double phase,int shape,double* grain);
double shapeSample(double carrierPhase,double amplitude,int shape);
}

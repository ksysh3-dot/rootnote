// Run with ASan/UBSan: the 288-element stack frame has no padded tail.
#include "pvb_vb_modulation.h"
#include <cassert>
#include <cmath>
int main() {
 static_assert(pvb::modulation::N==384 && pvb::modulation183::N==288);
 double shortFrame[288], legacyFrame[384];
 for(int i=0;i<288;++i) shortFrame[i]=.1*std::cos(2*pvb::modulation183::Pi*70*(i-144)/3000.);
 for(int i=0;i<384;++i) legacyFrame[i]=.1*std::cos(2*pvb::modulation::Pi*70*(i-192)/3000.);
 auto a=pvb::modulation183::fit(shortFrame,70),b=pvb::modulation::fit(legacyFrame,70);
 assert(a.valid && b.valid && std::abs(a.frequency-70)<1e-5 && std::abs(b.frequency-70)<1e-5);
 double ratio,phase;pvb::modulation183::local(a,.01,ratio,phase);
 assert(std::abs(ratio-1)<1e-5 && std::abs(phase-2*pvb::modulation183::Pi*70*.01)<1e-5);
 for(double& v:shortFrame)v=0;
 assert(!pvb::modulation183::fit(shortFrame,70).valid);
}

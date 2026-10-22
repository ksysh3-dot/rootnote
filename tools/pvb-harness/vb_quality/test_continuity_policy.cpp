#include "pvb_vb_continuity.h"
#include <cassert>
#include <cmath>
#include <iostream>
int main() {
    pvb::ContinuityParams p; p.enabled=true;
    pvb::HarmonicPermission m;
    pvb::HarmonicPermission uncertain;
    uncertain.step(1,p); const double partial=uncertain.value;
    uncertain.step(0,p); assert(uncertain.value==partial);
    assert(m.step(0,p)==0); // no ghost birth without evidence
    m.step(1,p);assert(m.value>0 && m.value<1);m.step(1,p);assert(m.value==1);
    for(int j=0;j<6;++j) assert(m.step(0,p)==1); //32ms uncertain gap
    assert(m.step(0,p)<1);m.step(1,p);assert(m.value==1); // reacquire, not reset
    for(int j=0;j<12;++j) m.step(0,p);
    assert(m.value==0); // no indefinite hold
    for(int j=0;j<10;++j) assert(m.step(.6,p)==0); // weak evidence cannot create a new harmonic
    m.step(1,p);m.step(1,p);assert(m.step(.6,p)==1); // existing partial hysteresis
    m.step(0,p,true);m.step(0,p,true);assert(m.value==0); // confirmed end bypasses hold
    std::cout << "C1 permission: birth,32ms gap/reacquire, bounded release, hysteresis, fast stop passed\n";
}

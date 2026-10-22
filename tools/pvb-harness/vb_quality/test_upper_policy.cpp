#include "pvb_vb_policy.h"
#include <cassert>
#include <cmath>
#include <iostream>

int main() {
    pvb::UpperHarmonicPolicy p;
    for(int i=0;i<500;++i) p.step(i%2==0);
    assert(p.switches()==0 && p.blend()==1);
    for(int i=0;i<200;++i) p.step(true);
    assert(p.target()==0 && p.blend()==0 && p.switches()==1);
    for(int i=0;i<4;++i) p.step(false);
    assert(p.target()==0); // brief disturbance does not switch
    for(int i=0;i<20;++i) p.step(false);
    assert(p.target()==1 && p.blend()==1 && p.switches()==2);
    for(int i=0;i<40;++i) p.step(true);
    assert(p.target()==1); // dwell prevents immediate reversal
    double previous=p.blend();
    for(int i=0;i<600;++i) {
        p.step(true);
        assert(p.blend()>=0 && p.blend()<=1);
        assert(std::abs(p.blend()-previous)<=16./3000/.04+1e-12);
        previous=p.blend();
    }
    assert(p.target()==0 && p.blend()==0);
    p.reset();
    assert(p.target()==1 && p.blend()==1 && p.switches()==0);
    std::cout << "PASS: evidence, chatter, dwell, bounded slew, endpoints, reset\n";
}

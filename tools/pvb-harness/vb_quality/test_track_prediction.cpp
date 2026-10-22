#include "pvb_track_prediction.h"
#include <cassert>
#include <cmath>
int main() {
    using namespace pvb::prediction52;
    History h;
    for(int i=0;i<40;++i) h.observe(60.+i*.1);
    assert(h.count==32 && std::abs(h.values[0]-60.8)<1e-12);
    assert(std::abs(h.forecast(Linear,3).frequency-64.2)<1e-12);
    const auto original=h.forecast(Burg,3);
    assert(std::isfinite(original.frequency));
    // Forecasts do not manufacture observations or advance measurement time.
    assert(h.count==32 && h.values[31]==63.9);
    h.observe(65.,4);
    assert(h.count==1 && h.values[0]==65.);
    assert(h.forecast(Linear,2).frequency==65.);
    assert(h.forecast(Burg,2).used==Constant);
    for(int i=0;i<8;++i) h.observe(65.);
    assert(h.forecast(Burg,6).frequency==65.);
    History extreme;extreme.observe(20.);extreme.observe(200.);
    const auto limited=extreme.forecast(Linear,6);
    assert(limited.limited && limited.frequency==200.);
}

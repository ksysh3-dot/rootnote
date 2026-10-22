#pragma once
#include <algorithm>
#include <cmath>
namespace pvb {
namespace prediction52 {
constexpr int Capacity=32,Order=2,Minimum=8;
constexpr double Hop=16./3000,MaxSlope=400.;
enum Mode { Constant=0,Linear=1,Burg=2 };
struct Forecast {double frequency=0,raw=0;int used=Constant;bool limited=false;};
// Measured frequencies only. Missing hops are forecast, never inserted as
// observations. Reacquisition resets the uniform LP history after a gap.
struct History {
    double values[Capacity]={};int count=0;
    void observe(double frequency,int elapsed=1) {
        if(elapsed!=1) count=0;
        if(count==Capacity) {std::move(values+1,values+Capacity,values);--count;}
        values[count++]=frequency;
    }
    Forecast forecast(int mode,int horizon) const {
        Forecast out;if(!count) return out;
        const double last=values[count-1];out.frequency=out.raw=last;
        if(mode==Constant || count<2 || horizon<1 || horizon>100) return out;
        out.raw=last+(last-values[count-2])*horizon;out.used=Linear;
        if(mode==Burg && count>=Minimum) {
            double mean=0;for(int i=0;i<count;++i) mean+=values[i];mean/=count;
            double f[Capacity],b[Capacity],a[Order+1]={1.,0.,0.};
            for(int i=0;i<count;++i) f[i]=b[i]=values[i]-mean;
            bool valid=true;
            for(int order=1;order<=Order;++order) {
                const int n=count-order;double numerator=0,denominator=0;
                for(int i=0;i<n;++i) {numerator+=f[i+1]*b[i];denominator+=f[i+1]*f[i+1]+b[i]*b[i];}
                if(denominator<1e-18 || !std::isfinite(denominator)) {valid=false;break;}
                const double reflection=std::max(-.999,std::min(.999,-2*numerator/denominator));
                double next[Order+1]={};next[0]=1.;next[order]=reflection;
                for(int j=1;j<order;++j) next[j]=a[j]+reflection*a[order-j];
                std::copy(next,next+Order+1,a);
                for(int i=0;i<n;++i) {const double forward=f[i+1],backward=b[i];f[i]=forward+reflection*backward;b[i]=backward+reflection*forward;}
            }
            if(valid) {
                double recent[Order]={values[count-1]-mean,values[count-2]-mean};
                for(int h=0;h<horizon;++h) {const double next=-a[1]*recent[0]-a[2]*recent[1];recent[1]=recent[0];recent[0]=next;}
                if(std::isfinite(recent[0])) {out.raw=recent[0]+mean;out.used=Burg;}
            }
        }
        const double bound=MaxSlope*Hop*horizon;
        out.frequency=std::max(20.,std::min(200.,std::max(last-bound,std::min(last+bound,out.raw))));
        out.limited=out.frequency!=out.raw;return out;
    }
};
}
}

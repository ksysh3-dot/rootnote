// S54 host research only. Causal output-level backoff, no extra audio delay.
#pragma once
#include <algorithm>
#include <cmath>
namespace pvb {
class Level54 {
public:
    bool configure(int mode,int sr,double knee,double slope,double enter,double exit,
                   double attackMs,double releaseMs) {
        const double v[]={knee,slope,enter,exit,attackMs,releaseMs};
        for(double x:v) if(!std::isfinite(x))return false;
        if(mode<0 || mode>1 || sr!=48000 || knee< -60 || knee>0 || slope<0 || slope>4 ||
           exit<0 || enter<=exit || enter>12 || attackMs<5 || attackMs>1000 ||
           releaseMs<20 || releaseMs>5000)return false;
        // Repeating the same setting preserves live state; mutation is host-thread only.
        if(mode_==mode && knee_==knee && slope_==slope && enter_==enter && exit_==exit &&
           attackMs_==attackMs && releaseMs_==releaseMs)return true;
        mode_=mode;knee_=knee;slope_=slope;enter_=enter;exit_=exit;
        attackMs_=attackMs;releaseMs_=releaseMs;
        rmsC_=1.-std::exp(-1./(.020*sr));
        attackC_=1.-std::exp(-1./(.001*attackMs*sr));
        releaseC_=1.-std::exp(-1./(.001*releaseMs*sr));
        reset();return true;
    }
    void reset(){full_=base_=0.;backoffDb_=predicted_=target_=0.;engaged_=false;count_=0;switches_=0;}
    bool enabled()const{return mode_!=0;}
    double tick(double dl,double dr,double ll,double lr,double proposed,double baseGain,double outGain) {
        const double a=(dl+proposed*ll)*outGain,b=(dr+proposed*lr)*outGain;
        const double c=(dl+baseGain*ll)*outGain,d=(dr+baseGain*lr)*outGain;
        full_+=rmsC_*(.5*(a*a+b*b)-full_);base_+=rmsC_*(.5*(c*c+d*d)-base_);
        if(++count_==48){
            count_=0;
            const double f=10.*std::log10(std::max(full_,1e-30));
            const double r=10.*std::log10(std::max(base_,1e-30));
            predicted_=std::max(0.,slope_*(std::max(0.,f-knee_)-std::max(0.,r-knee_)));
            const bool was=engaged_;
            if(!engaged_ && predicted_>=enter_)engaged_=true;
            else if(engaged_ && predicted_<=exit_)engaged_=false;
            if(was!=engaged_)++switches_;
            target_=engaged_?std::min(6.,predicted_):0.;
        }
        backoffDb_+=(target_-backoffDb_)*(target_>backoffDb_?attackC_:releaseC_);
        // Only EXTRA strength is backed off. Never remove the P1 layer at this point.
        return baseGain+(proposed-baseGain)*std::pow(10.,-backoffDb_/20.);
    }
    int state(double* out,int cap)const {
        if(!out || cap<6)return 0;
        out[0]=backoffDb_;out[1]=predicted_;out[2]=engaged_?1.:0.;out[3]=switches_;
        out[4]=full_;out[5]=base_;return 6;
    }
private:
    int mode_=0,count_=0;unsigned switches_=0;
    double knee_=-24.,slope_=1.5,enter_=1.5,exit_=.5,attackMs_=40.,releaseMs_=250.;
    double rmsC_=0.,attackC_=0.,releaseC_=0.;
    double full_=0.,base_=0.,backoffDb_=0.,predicted_=0.,target_=0.;bool engaged_=false;
};
}

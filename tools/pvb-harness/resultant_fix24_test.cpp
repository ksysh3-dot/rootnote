// Host regression fixtures for section-24 phase, Fade rejection, and active-filter redistribution.
// Compile with the production pvb_engine/analysis/vb/vb52 translation units; no audio files are written.
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3.
#include <bits/stdc++.h>
#define private public
#include "pvb_vb.h"
#undef private
using pvb::ResultantCore;
static int checks=0;
static void need(bool ok,const char* msg) { ++checks; if(!ok) { std::cerr<<msg<<"\n";std::exit(1); } }
int main() {
    constexpr double pi=3.14159265358979323846, dt=16.0/3000;
    double worst=0;
    for(int mode=0;mode<=1;++mode) for(int born=0;born<=1;++born)
    for(int f=40;f<=160;++f) for(int j=0;j<24;++j) {
        ResultantCore c;c.p_.birthPhaseUnwrap=1;c.p_.renderFreqMode=mode;
        auto& u=c.vo_[0];auto cx=ResultantCore::Ctx{};
        cx.lsOk=true;u.state=born?ResultantCore::On:ResultantCore::Cand;
        u.born=born;u.inLs=true;u.f=u.fOsc=f;
        u.theta=u.thetaStart=(j-12)*pi/12;
        const double prev=u.theta,pred=prev+2*pi*f*dt;
        u.thetaMeas=std::remainder(pred,2*pi);
        c.updatePhase(cx);
        const double err=std::abs(u.theta-pred);worst=std::max(worst,err);
        need(err<1e-10,"predicted unwrap failed");
        if(mode) {
            c.updateRender();
            need(std::abs(u.thetaR-u.theta)<1e-10 && u.thetaRStart==prev,"render birth reference failed");
        }
        u.a[0]=u.aStart[0]=.1;
        c.synthesize(cx);
        for(int n=0;n<16;++n) need(std::abs(c.take(n)-.1*std::cos(2*(prev+2*pi*f*n/3000.)))<1e-6,
                                   "synthesis follows wrong birth branch");
    }
    for(int enabled=0;enabled<=1;++enabled) for(int audible=0;audible<=1;++audible)
    for(int fullFade=0;fullFade<=1;++fullFade) {
        ResultantCore c;c.p_.fadeRejectBan=enabled;c.hopCount_=100;
        for(int q=0;q<8;++q) {
            auto& u=c.vo_[q];u.state=ResultantCore::On;u.trackId=100+q;
            u.A=q?1:.1;u.c=1;if(audible)u.a[0]=u.aStart[0]=u.A;
        }
        if(fullFade)for(int q=8;q<10;++q) { c.vo_[q].state=ResultantCore::Fade;c.vo_[q].a[0]=1; }
        ResultantCore::Ctx cx;
        need(c.allocateSlot(cx,2)==0,"wrong victim");
        const bool expected=enabled||!audible;
        need(c.rejected(100)==expected,"evicted track ban missing");
        if(expected) {
            for(int age=0;age<24;++age) { c.hopCount_=100+age;need(c.rejected(100),"ban shorter than 24 hops"); }
            c.hopCount_=124;need(!c.rejected(100),"ban exceeds 24 hops");
        }
        if(audible) {
            bool found=false;for(int q=8;q<10;++q)if(c.vo_[q].A==.1){found=true;need(c.vo_[q].trackId==0,"Fade retains track binding");}
            need(found,"victim not moved to Fade");
        }
    }

    double responseError=0, powerError=0, legacyResponseDifference=0;
    for(double lo : {150.,250.}) for(double hi : {400.,600.,1000.})
    for(int order : {4,8}) {
        pvb::VbHpv v(true,true,1);
        need(v.configure(48000),"configure");
        need(v.setAlpha2Profile(15),"profile");
        auto dev=pvb::DevVoicing{};dev.outLoHz=lo;dev.outHiHz=hi;v.setDev(dev);
        ResultantCore c;c.p_.redistActualFilter=1;c.p_.layerHpHz=150;c.p_.layerHpOrder=order;c.designHp();
        for(int f=160;f<=590;f+=10) {
            for(auto& b:v.out_)b.clear();
            c.reset();
            std::complex<double> z=0.;
            for(int n=0;n<8192;++n) {
                double x=n==0?1.:0.;
                for(auto& b:v.out_)x=b.tick(x);
                x=c.hpTick(x);
                z+=x*std::polar(1.,-2*pi*f*n/3000.);
            }
            const double analytic=c.outputMagnitude(v,f), observed=std::abs(z);
            responseError=std::max(responseError,std::abs(analytic-observed));
            need(std::abs(analytic-observed)<1e-10,"active filter response differs from actual impulse DFT");
            if(lo==250 && f==180) {
                c.p_.redistActualFilter=0;
                legacyResponseDifference=std::max(legacyResponseDifference,std::abs(c.outputMagnitude(v,f)-analytic));
                c.p_.redistActualFilter=1;
            }
        }
        for(double f : {40.,55.,80.,100.,160.}) for(int mode : {1,2}) {
            auto u=ResultantCore::Voice{};u.f=u.fOsc=f;u.A=.1;u.c=u.sigma=1;u.psiSet=127;
            c.p_.redistMode=0;c.amplitudes(v,u);
            auto power=[&] {
                double sum=0;for(int k=0;k<7 && (k+2)*f<=700;++k) {
                    const double h=c.outputMagnitude(v,(k+2)*f);
                    sum+=.5*u.a[k]*u.a[k]*h*h;
                }
                return sum;
            };
            const double before=power();
            c.p_.redistMode=mode;c.p_.redistAlpha=.5;c.amplitudes(v,u);
            const double error=std::abs(power()-before)/std::max(before,1e-30);
            powerError=std::max(powerError,error);
            need(error<1e-12,"active-filter redistribution does not preserve modeled steady partial power");
        }
    }
    need(legacyResponseDifference>.01,"fixture does not expose stale output filter");
    std::cout<<"filter_response_max_abs_error="<<std::setprecision(17)<<responseError
             <<" power_relative_error="<<powerError<<" stale_H_difference="<<legacyResponseDifference<<std::endl;
    std::cout<<"PASS checks="<<checks<<" unwrap_cases="<<2*2*121*24<<" max_phase_error="<<std::setprecision(17)<<worst<<"\n";
}

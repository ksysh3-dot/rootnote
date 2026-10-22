// hpv52m strictly causal port; vb51/PORT_SPEC.md and hpv51.py are the reference.
#include "pvb_vb.h"
#include "pvb_dsp.h"
#include "pvb_vb_tables.h"
#include "pvb_vb52_tables.h"
#include "pvb_vb_detail.h"
#include "pvb_track_assignment.h"
#include <algorithm>
#include <cmath>
#include <complex>
namespace pvb {
namespace {
double interp52(const double* a, int n, double idx) {
    idx=clampv(idx,0.0,static_cast<double>(n-1));
    const int j=static_cast<int>(idx); const double r=idx-j;
    return a[j]*(1-r)+a[std::min(j+1,n-1)]*r;
}
double kernel52(double d) {
    return (d < -40 || d > 40) ? 0 : interp52(vb52t::kHann,5121,(d+40)*64);
}
double offset52(double a, double b, double c) {
    const double den=a-2*b+c;
    return clampv(std::abs(den)>1e-12 ? .5*(a-c)/den : 0.0,-1.0,1.0);
}
}


void VbHpv::beginHarmonic52() {
    if(!harmonicCapture_) return;
    std::fill(std::begin(harmonicTrace_.data),std::end(harmonicTrace_.data),0.f);
    auto* h=harmonicTrace_.data; h[2]=static_cast<float>(harmonicEpoch_);
    for(int j=0;j<4;++j) h[3+j]=static_cast<float>((i_>>(16*j))&65535);
    h[7]=-383; h[8]=191;
    const double hostPerCore=static_cast<double>(M_)/L_;
    const double fractional=static_cast<double>(M_)*static_cast<double>(m_)/L_-static_cast<double>(n_);
    const double firDelay=static_cast<double>(taps_-1)/(2*L_);
    h[9]=static_cast<float>(fractional-382.*hostPerCore-firDelay);
    h[10]=static_cast<float>(fractional+16*hostPerCore+firDelay);
    h[15]=static_cast<float>(harmEnv52_); h[16]=static_cast<float>(percEnv52_);
    h[23]=HarmonicTrace::kVersion; h[27]=static_cast<float>(modulationMode_+(tonalOnly_?16:0)); harmonicReady_=true;
}
void VbHpv::traceTrack52(int slot,const Track52& t,int state,int reason) {
    if(!harmonicCapture_ || slot>=HarmonicTrace::kTracks) return;
    auto* r=harmonicTrace_.data+HarmonicTrace::kHeader+slot*HarmonicTrace::kTrack;
    r[0]=static_cast<float>(t.id&65535); r[1]=static_cast<float>(state);
    r[2]=static_cast<float>(t.f); r[3]=static_cast<float>(t.dfdt); r[4]=static_cast<float>(t.a);
    r[5]=static_cast<float>(std::atan2(std::sin(t.phi),std::cos(t.phi)));
    r[6]=static_cast<float>(t.residual); r[7]=static_cast<float>(t.fade);
    r[8]=static_cast<float>(t.age); r[9]=static_cast<float>(t.missing);
    r[10]=static_cast<float>(reason); r[11]=static_cast<float>(t.life); r[12]=static_cast<float>(t.rawResidual); r[13]=static_cast<float>(t.id>>16);
}
void VbHpv::renderTrack52(Track52& tr,const double src[2][256],const int ns[2],
                        bool observed,bool fast,int traceSlot,double* grain,double& agrain) {
    const double tc=2.*80/48000+(192.+15+191)/3000-7052./48000;
    double w[7],gain; lookup(tr.f,w,gain); const double amp=tr.a*gain*tr.fade*tr.life;
    const bool oscillator=stageFlags_&StageOscillator;
    double targetAmplitude[7]={},targetPhase[7]={};
    for(int j=0;j<7;++j) targetPhase[j]=(j+2)*tr.phi+tr.off[j];
    for(int k=2;k<=8;++k) {
        // Exact gentle128 reference: sustained partials above 220 Hz lose
        // 12 dB/octave; no redistribution, no percussion or level change.
        if(gentle_ && k*tr.f>220) {
            const double g12=std::pow(10.,-12*std::log2(k*tr.f/220.)/20);
            // Both budgets share frequency, phase, grid and track history.
            // A convex amplitude blend introduces no second oscillator.
            w[k-2]*=g12+research_.upperBlend*(g12*g12-g12);
        }
        float* ht=harmonicCapture_ && traceSlot<HarmonicTrace::kTracks ?
            harmonicTrace_.data+HarmonicTrace::kHeader+traceSlot*HarmonicTrace::kTrack+14+6*(k-2) : nullptr;
        if(ht) { ht[0]=static_cast<float>(amp*w[k-2]); ht[4]=tr.residual>-15?HarmonicTrace::Fit:0; }
        if(w[k-2]<=1e-4) {
            if(ht) ht[4]=static_cast<float>(static_cast<int>(ht[4])|HarmonicTrace::Weight);
            if(continuity_.enabled) tr.permission[k-2]={};
            continue;
        }
        const double fk=k*tr.f,tolGrid=std::max(4.,.1*24.7*(4.37*fk/1000+1));
        bool on=false; double distance=1e30;
        for(int j=0;j<ns[1];++j) if(std::abs(fk-src[1][j])<=tolGrid) on=true;
        for(int j=0;j<ns[0];++j) for(int h=2;h<=8;++h) if(std::abs(fk-h*src[0][j])<=tolGrid) on=true;
        if(continuity_.enabled || ht) {
            if(observed) {
                for(int j=0;j<ns[1];++j) distance=std::min(distance,std::abs(fk-src[1][j]));
                for(int j=0;j<ns[0];++j) for(int h=2;h<=8;++h) distance=std::min(distance,std::abs(fk-h*src[0][j]));
            }
        }
        const double evidence=observed?clampv(2-distance/tolGrid,0.,1.):0.;
        if(ht) ht[5]=static_cast<float>(evidence);
        const double mask=(stageFlags_&StageBypassPermission)?1.:
            continuity_.enabled?tr.permission[k-2].step(evidence,continuity_,fast):(on?1.:0.);
        if(ht) {
            ht[1]=static_cast<float>(amp*w[k-2]*mask); ht[2]=static_cast<float>(mask);
            if(!on) ht[4]=static_cast<float>(static_cast<int>(ht[4])|HarmonicTrace::Grid);
        }
        if(mask<=0) continue;
        const double tol=std::max(3.,.02*fk);
        const int b0=std::max(1,static_cast<int>(std::floor((fk-tol)/binHz_)));
        const int b1=std::min(kHalfFft,static_cast<int>(std::ceil((fk+tol)/binHz_))+1);
        bool found=false; int ii=b0;
        if(observed && on && b1-b0>=3) {
            for(int b=b0+1;b<b1;++b) if(sm52_[b]>sm52_[ii]) ii=b;
            if(sm52_[ii]>=sm52_[ii-1] && sm52_[ii]>sm52_[ii+1]) {
                const double a=std::log(sm52_[ii-1]+1e-30),b=std::log(sm52_[ii]+1e-30),c=std::log(sm52_[ii+1]+1e-30);
                const double off=offset52(a,b,c),fe=ii*binHz_+off*binHz_,ae=std::exp(b-.25*(a-c)*off)*2/pvWsum_;
                found=std::abs(fe-fk)<=tol && ae>=tr.a*.01 && ae>=pvAbs_;
            }
        }
        const double target=!observed || !on ? tr.off[k-2] : found ? std::atan2(si52_[ii],sr52_[ii])+interp52(vb52t::kPhase,3920,(fk-20)*4)+phaseDelta52(fk)+2*kPi*fk*tc-k*tr.phi : vbt::kPsi[k-2];
        const double d=target-tr.off[k-2];
        const double adjustment=(stageFlags_&StageFreezePhase)?0.:clampv(std::atan2(std::sin(d),std::cos(d)),-.12,.12);
        tr.off[k-2]+=adjustment;
        // Trace field3 describes the old offset step, not the oscillator's
        // separate bounded endpoint correction. Do not report it as applied.
        if(ht) ht[3]=oscillator?0.f:static_cast<float>(adjustment);
        if(oscillator) {
            targetAmplitude[k-2]=amp*w[k-2]*mask;
            targetPhase[k-2]=k*tr.phi+tr.off[k-2];
            continue;
        }
        // J2-F: compensate the KNOWN output filter at the two AM sidebands.
        // The time budget follows actual frame placement/FIR delay/declared
        // module latency. No alignment is estimated from an output fixture.
        bool compensated=(modulationMode_&1) && observed && tr.family.valid && (stageFlags_&StageFamilyFilterComp);
        std::complex<double> lower,upper;
        if(compensated) {
            auto response=[](double frequency) {
                const auto z=std::polar(1.,-2*kPi*frequency/kFsd);std::complex<double> h=1.;
                for(int j=0;j<3;++j) {const auto* b=vbt::kOutSos+6*j;h*=(b[0]+b[1]*z+b[2]*z*z)/(1.+b[4]*z+b[5]*z*z);}
                return h;
            };
            const double hostRate=kFsd*static_cast<double>(M_)/L_;
            const double fixedDelay=(2.*(kPvN/2-1)+kPvH)/kFsd+(taps_-1)/(L_*hostRate);
            const double envelopeDelay=latency_/hostRate-fixedDelay;
            const auto a=tr.family.sourceModulation*std::polar(1.,-2*kPi*tr.family.rate*envelopeDelay);
            const auto h=response(fk),hl=response(fk-tr.family.rate),hu=response(fk+tr.family.rate);
            compensated=std::abs(hl)>.01 && std::abs(hu)>.01 && std::abs(h/hl)<=2 && std::abs(h/hu)<=2;
            if(compensated) {lower=.5*std::conj(a)*h/hl;upper=.5*a*h/hu;}
        }
        if(compensated) {
            const double mean=amp/(1+tr.family.cosine);
            for(int g=0;g<32;++g) {
                const double t=(g-16)/3000.;const auto z=std::polar(1.,2*kPi*tr.family.rate*t);
                const auto envelope=1.+lower*std::conj(z)+upper*z;
                grain[g]+=mean*w[k-2]*mask*(std::polar(1.,k*(tr.phi+2*kPi*tr.f*t)+tr.off[k-2])*envelope).real();
            }
        } else if(!(modulationMode_&1) || !observed) {
            for(int g=0;g<32;++g) grain[g]+=amp*w[k-2]*mask*std::cos(k*(tr.phi+2*kPi*tr.f*(g-16)/3000)+tr.off[k-2]);
        } else for(int g=0;g<32;++g) {
            const double t=(g-16)/3000.;double ratio,phase;
            if(tr.family.valid) tr.family.local(t,ratio,phase);
            else if(tr.modulation.valid) modulation::local(tr.modulation,t,ratio,phase);
            else {
                ratio=clampv(1+tr.dadt*t/std::max(tr.a,1e-12),0.,3.);
                phase=2*kPi*tr.f*t+kPi*clampv(tr.dfdt,-400.,400.)*t*t;
            }
            grain[g]+=amp*w[k-2]*mask*ratio*std::cos(k*(tr.phi+phase)+tr.off[k-2]);
        }
    }

    const double nominal=tr.a*tr.fade*tr.life;
    if(oscillator) tr.oscillator.add(tr.f,targetAmplitude,targetPhase,nominal,
        stageFlags_&StageOscillatorCorrect,grain,oscillatorNominal52_);
    agrain+=nominal;
}
void VbHpv::missingFrame52(int reason,bool fast) {
    std::fill(std::begin(oscillatorNominal52_),std::end(oscillatorNominal52_),0.);
    if(harmonicCapture_) { harmonicTrace_.data[13]=static_cast<float>(reason); harmonicTrace_.data[22]=static_cast<float>(nt52_); }
    if(!continuity_.enabled && !(stageFlags_&StageOscillator)) {
        for(int j=0;j<nt52_;++j) traceTrack52(j,tr52_[j],HarmonicTrace::End,reason|HarmonicTrace::Lost);
        nt52_=0; return;
    }
    const double src[2][256]={}; const int ns[2]={};
    double grain[32]={},agrain=0; int n=0;
    for(int j=0;j<nt52_;++j) {
        auto tr=tr52_[j]; ++tr.age; ++tr.missing;
        const bool fastEnd=fast || tr.fastEnding; tr.fastEnding=fastEnd;
        tr.phi+=2*kPi*tr.f*kPvH/kFsd;
        if(fastEnd || tr.missing>continuity_.hold)
            tr.life=std::max(0.,tr.life-1./std::max(1,fastEnd?continuity_.fastRelease:continuity_.release));
        if(!continuity_.enabled) tr.life=0;
        if(tr.life<1e-12) tr.life=0;
        const int state=tr.life<=0?HarmonicTrace::End:(fastEnd || tr.missing>continuity_.hold?HarmonicTrace::Release:HarmonicTrace::Held);
        traceTrack52(j,tr,state,reason|HarmonicTrace::Lost);
        if(tr.life>0 || (stageFlags_&StageOscillator)) renderTrack52(tr,src,ns,false,fastEnd,j,grain,agrain);
        if(tr.life>0) tr52_[n++]=tr;
    }
    nt52_=n;
    double energy=0;
    for(int g=0;g<32;++g) energy+=grain[g]*grain[g];
    addGrain52(static_cast<int64_t>(i_)+16,grain,agrain);
    if(harmonicCapture_) { harmonicTrace_.data[12]=static_cast<float>(n); harmonicTrace_.data[20]=static_cast<float>(std::sqrt(energy/32)); }
}

double VbHpv::phaseDelta52(double f) const {
    if (!eq52_[0]) return 0.0;
    auto response = [f](const SvfCoef& c, double fs) {
        const std::complex<double> s(0, std::tan(kPi*f/fs));
        const auto den=s*s+c.k*c.g*s+c.g*c.g;
        return c.m0+c.m1*c.g*s/den+c.m2*c.g*c.g/den;
    };
    auto actual=response(eq52_[0]->current(),eqFs52_);
    actual*=actual;
    for(int j=1;j<4;++j) actual*=response(eq52_[j]->current(),eqFs52_);
    auto ref=response(svfHighpass(48000,100,std::sqrt(.5)),48000);
    ref*=ref;
    ref*=response(svfBell(48000,220,3,1),48000)*response(svfBell(48000,4500,-3,.6),48000);
    // Both resamplers have the same FIR group delay in seconds. Only rounding the dry delay differs by rate.
    const double timing=2*kPi*f*(7052./48000-static_cast<double>(latency_)/eqFs52_);
    return std::arg(actual/ref)+timing;
}

void VbHpv::pvFrame52() {
    std::fill(std::begin(oscillatorNominal52_),std::end(oscillatorNominal52_),0.);
    detailApplied52_=familyApplied52_=false;
    beginHarmonic52();
    const int64_t s0=static_cast<int64_t>(i_)-(kPvN-1);
    spectrum52(bhRing_,s0,xr52_,xi52_);
    double mag[256], mx=0;
    const int nb=hiBin_-loBin_;
    for (int b=0;b<nb;++b) { mag[b]=std::hypot(xr52_[loBin_+b],xi52_[loBin_+b]); mx=std::max(mx,mag[b]); }
    if(harmonicCapture_) harmonicTrace_.data[14]=static_cast<float>(mx*2/pvWsum_);
    if (mx*2/pvWsum_<pvAbs_) {
        observeScene(VB_SCENE_UNKNOWN);
        missingFrame52(HarmonicTrace::Absolute,true); apkCount_=histCount_=0; return;
    }
    int lm[256], nl=0;
    for (int b=1;b<nb-1;++b) if (mag[b]>=mag[b-1] && mag[b]>mag[b+1]) lm[nl++]=b;
    if (!nl) { observeScene(VB_SCENE_UNKNOWN); missingFrame52(HarmonicTrace::NoPeak,false); return; }
    // Same magnitude order as the original module; indices break exact ties deterministically.
    std::sort(lm,lm+nl,[&](int a,int b) {return mag[a]==mag[b] ? a>b : mag[a]>mag[b];});
    struct Peak { double f,a,ph,beta,res; double raw=0; ModulationFit modulation={}; AmFamily52 family={}; } pk[6];
    int np=0;
    for (int j=0;j<nl && np<6;++j) {
        const int b=lm[j]; if (mag[b]<mx*pvRel_) break;
        const double a=std::log(mag[b-1]+1e-30), v=std::log(mag[b]+1e-30), c=std::log(mag[b+1]+1e-30);
        const double off=offset52(a,v,c);
        pk[np++]={ (loBin_+b)*binHz_+off*binHz_, std::exp(v-.25*(a-c)*off)*2/pvWsum_,
                   std::atan2(xi52_[loBin_+b],xr52_[loBin_+b]), loBin_+b+off, 0 };
    }
    if(harmonicCapture_) {
        for(int j=0;j<nl;++j) {
            if(mag[lm[j]]<mx*pvRel_) harmonicTrace_.data[13]=HarmonicTrace::Relative;
            else if(j>=6) harmonicTrace_.data[21]+=1;
        }
    }
    if (!np) { observeScene(VB_SCENE_UNKNOWN); missingFrame52(HarmonicTrace::Relative,false); return; }
    double minb=pk[0].beta,maxb=minb;
    for (int p=1;p<np;++p) { minb=std::min(minb,pk[p].beta); maxb=std::max(maxb,pk[p].beta); }
    const int lo=std::max(0,static_cast<int>(minb)-12), hi=static_cast<int>(maxb)+13;
    double err[256]={};
    for (int b=lo;b<hi;++b) {
        std::complex<double> model=0;
        for (int p=0;p<np;++p) model+=(pk[p].a*pvWsum_/2)*std::exp(std::complex<double>(0,pk[p].ph))*kernel52(b-pk[p].beta);
        err[b-lo]=std::norm(std::complex<double>(xr52_[b],xi52_[b])-model);
    }
    for (int p=0;p<np;++p) {
        double e=0,own=0;
        for (int b=lo;b<hi;++b) if (std::abs(b-pk[p].beta)<=11) {
            e+=err[b-lo]; const double k=kernel52(b-pk[p].beta); own+=k*k;
        }
        own*=std::pow(pk[p].a*pvWsum_/2,2);
        pk[p].res=10*std::log10(e/std::max(own,1e-30)+1e-12); pk[p].raw=pk[p].res;
    }
    // Fit only the dominant observed peak. Other distinct peaks are stationary
    // nuisance columns, never claimed to be separated note/instrument labels.
    if((modulationMode_&2) && np>0) {
        double frame[kPvN], neighbors[3];int nn=0;
        for(int n=0;n<kPvN;++n) frame[n]=bhRing_[(s0+n)&(kRing-1)];
        for(int j=1;j<np && nn<3;++j) if(std::abs(pk[j].f-pk[0].f)>12) neighbors[nn++]=pk[j].f;
        AmFamily52 family;
        if(stageFlags_&StageAmFamily) {
            double raw[kPvN];for(int n=0;n<kPvN;++n) raw[n]=detailRing52_[(s0+n)&(kRing-1)];
            const int64_t sourceCentre=s0+kPvN/2;
            if(family52_.valid && sourceCentre-familyCentre52_<=128) {
                family=family52_;family.advance(static_cast<double>(sourceCentre-familyCentre52_)/kFsd);
                if(amfamily::predictionResidual(family,raw)>-25) family.valid=false;
            }
            if(familyCountdown52_--<=0) {
                familyCountdown52_=7;const auto proposed=amfamily::fit(raw,pk[0].f,vbt::kBandSos);
                if(proposed.valid) {family=family52_=proposed;familyCentre52_=sourceCentre;}
            }
            if(family.valid) {np=1;pk[0].family=family;familyApplied52_=true;}
        }
        auto m=family.valid?family.trajectory():modulation::fit(frame,pk[0].f,neighbors,nn);
        if(m.valid && !family.valid && (stageFlags_&StageShortDetail)) {
            double local[detail::N];const int64_t centre=s0+kPvN/2;
            for(int n=0;n<detail::N;++n) local[n]=detailRing52_[(centre-detail::N/2+n)&(kRing-1)];
            auto shortFit=detail::fit(local,m.frequency,m.frequencySlope);
            if(shortFit.valid) {
                // Structural acceptance remains the128ms path's decision.
                shortFit.residual=m.residual;m=shortFit;detailApplied52_=true;
            }
        }
        if(m.valid) {pk[0].modulation=m;pk[0].f=m.frequency;pk[0].a=m.amplitude;pk[0].ph=m.phase;}
    }
    std::sort(pk,pk+np,[](const Peak& a,const Peak& b){return a.f<b.f;});
    int nk=0;
    for (int p=0;p<np;++p) {
        bool own=false;
        for (int q=0;q<nk;++q) {
            const double n=std::nearbyint(pk[p].f/pk[q].f);
            if (n>=2 && n<=5 && std::abs(pk[p].f-n*pk[q].f)<=std::max(1.5,.015*pk[p].f)) own=true;
        }
        if (!own) pk[nk++]=pk[p];
    }
    if(harmonicCapture_ && nk<np) harmonicTrace_.data[13]=static_cast<float>(static_cast<int>(harmonicTrace_.data[13])|HarmonicTrace::Dependent);
    np=nk;
    double am=0; for(int p=0;p<np;++p) am=std::max(am,pk[p].a);
    bool born=false;
    if (histCount_>0) for (int p=0;p<np;++p) if(pk[p].a>=.5*am) {
        bool found=false;
        for(int h=0;h<histCount_;++h) for(int q=0;q<histN52_[h];++q)
            if(std::abs(hist52_[h][q]-pk[p].f)<.20*pk[p].f) found=true;
        for(int q=0;q<nt52_;++q) if(tr52_[q].strong && std::abs(tr52_[q].f-pk[p].f)<.20*pk[p].f) found=true;
        if(!found) born=true;
    }
    double recent=0,past=0;
    for(int h=std::max(0,apkCount_-8);h<apkCount_;++h) recent=std::max(recent,apk52_[h]);
    for(int h=0;h<apkCount_-8;++h) past=std::max(past,apk52_[h]);
    const bool falling=apkCount_>0 && am<recent/1.19;
    if(apkCount_<=8 || am>1.41*past || born) onsetLeft_=24;
    if(apkCount_==56) { std::move(apk52_+1,apk52_+56,apk52_); --apkCount_; }
    apk52_[apkCount_++]=am;
    double* hm=hold52_[holdPos_]; std::fill(hm,hm+190,-200.0);
    if(onsetLeft_<=0 && !falling) for(int p=0;p<np;++p) for(int g=0;g<190;++g)
        if(std::abs(g+20-pk[p].f)<=8) hm[g]=std::max(hm[g],pk[p].res);
    if(harmonicCapture_) { harmonicTrace_.data[24]=static_cast<float>(onsetLeft_); harmonicTrace_.data[25]=falling?1.f:0.f; harmonicTrace_.data[26]=static_cast<float>(holdCount_); }
    --onsetLeft_; holdPos_=(holdPos_+1)%28; holdCount_=std::min(28,holdCount_+1);
    for(int p=0;p<np;++p) {
        double r=-200;
        for(int h=0;h<holdCount_;++h) for(int g=0;g<190;++g)
            if(std::abs(g+20-pk[p].f)<=8) r=std::max(r,hold52_[h][g]);
        pk[p].res=pk[p].modulation.valid?pk[p].modulation.residual:r;
    }
    spectrum52(md2_52_,s0,sr52_,si52_);
    for(int b=0;b<=kHalfFft;++b) sm52_[b]=std::hypot(sr52_[b],si52_[b]);
    double src[2][256]; int ns[2]={};
    for(int band=0;band<2;++band) {
        const int lb=static_cast<int>(std::ceil((band?140:20)/binHz_));
        const int hb=static_cast<int>(std::floor((band?620:200)/binHz_));
        double maxmag=0; for(int b=lb;b<=hb;++b) maxmag=std::max(maxmag,sm52_[b]);
        for(int b=lb+1;b<hb;++b) {
            const double v=sm52_[b];
            if(!(v>=sm52_[b-1] && v>sm52_[b+1] && v>=maxmag*std::pow(10.,(band?-60.:-50.)/20))) continue;
            double med[55]; for(int q=-27;q<=27;++q) med[q+27]=sm52_[clampv(b+q,lb,hb)];
            std::nth_element(med,med+27,med+55);
            if(v<(med[27]+1e-20)*std::sqrt(10.)) continue;
            const double off=offset52(std::log(sm52_[b-1]+1e-30),std::log(v+1e-30),std::log(sm52_[b+1]+1e-30));
            src[band][ns[band]++]=b*binHz_+off*binHz_;
        }
    }
    const int64_t centre=s0+kPvN+kRtShift;
    int poly=0; for(int p=0;p<np;++p) if(pk[p].a>=.25*am) ++poly;
    // Unvalidated scene labels are diagnostics only. Fit residual is not a buzz
    // score; AM sidebands may look like several independent bass components.
    bool unresolved=false;
    for(int p=0;p<np;++p) if(pk[p].a>=.25*am && pk[p].res>-15) unresolved=true;
    observeScene(percEnv52_>2*harmEnv52_ ? VB_SCENE_TRANSIENT :
                 (poly>=2 || unresolved) ? VB_SCENE_COMPLEX : VB_SCENE_STEADY);
    for(int g=0;g<kPvH;++g) polyT52_[(centre+g)&(kRing-1)]=poly>=2 ? 0 : 1;
    Track52 next[12]; bool used[12]={}; double grain[32]={},agrain=0;
    int nextCount=np;int global[6]={};
    if(stageFlags_&StageGlobalTrack) {
        assignment52::State observed[6],old[12];
        double predicted[12];
        const int mode=(stageFlags_&StageTrackBurg)?prediction52::Burg:
                       (stageFlags_&StageTrackLinear)?prediction52::Linear:prediction52::Constant;
        for(int p=0;p<np;++p) observed[p]={pk[p].f,pk[p].ph,pk[p].a,1,0};
        for(int t=0;t<nt52_;++t) {
            const auto& tr=tr52_[t];old[t]={tr.f,tr.phi,tr.a,tr.life,tr.missing};
            // History is at the last MEASURED frequency; phi is at the previous
            // hop. Only the frequency forecast uses missing+1, never phi.
            predicted[t]=mode==prediction52::Constant?tr.f:tr.prediction.forecast(mode,tr.missing+1).frequency;
        }
        assignment52::match(observed,np,old,nt52_,global,predicted);
    }
    for(int p=0;p<np;++p) {
        const auto& q=pk[p]; int best=-1;
        if(stageFlags_&StageGlobalTrack) best=global[p];
        else for(int t=0;t<nt52_;++t) if(!used[t] && std::abs(tr52_[t].f-q.f)<.1*q.f &&
            (best<0 || std::abs(tr52_[t].f-q.f)<std::abs(tr52_[best].f-q.f))) best=t;
        Track52 tr; tr.f=q.f; tr.phi=q.ph; tr.a=q.a; tr.strong=q.a>=.7*am;
        if(best>=0) {
            used[best]=true; const auto& prev=tr52_[best];
            // Held tracks already advance phi once on each missing hop below.
            const double pred=prev.phi+kPi*(prev.f+q.f)*16/3000;
            tr.phi=q.ph+2*kPi*std::nearbyint((pred-q.ph)/(2*kPi));
            std::copy(prev.off,prev.off+7,tr.off); tr.fade=prev.fade;
            tr.id=prev.id; tr.age=prev.age+1; tr.dfdt=(q.f-prev.f)*kFsd/(kPvH*(prev.missing+1));
            std::copy(std::begin(prev.permission),std::end(prev.permission),std::begin(tr.permission));
            if(stageFlags_&StageOscillator) tr.oscillator=prev.oscillator;
            tr.life=continuity_.enabled?std::min(1.,prev.life+1./std::max(1,continuity_.attack)):1.;
            if(stageFlags_&StageGlobalTrack) tr.prediction=prev.prediction;
        } else {
            std::copy(vbt::kPsi,vbt::kPsi+7,tr.off); tr.fade=q.res<=-15 ? 1 : 0;
            tr.id=++nextTrackId_; tr.age=1;
        }
        if(stageFlags_&StageGlobalTrack) tr.prediction.observe(q.f,best>=0?tr52_[best].missing+1:1);
        tr.modulation=q.modulation;tr.family=q.family;
        if(harmonicCapture_ && q.modulation.valid) harmonicTrace_.data[27]+=32;
        if(modulationMode_&1) {
            if(best>=0) tr.dadt=clampv((q.a-tr52_[best].a)*kFsd/(kPvH*(tr52_[best].missing+1)),-100*q.a,100*q.a);
            if(q.modulation.valid) {tr.dadt=q.modulation.amplitudeSlope;tr.dfdt=q.modulation.frequencySlope;}
        }
        tr.residual=q.res; tr.rawResidual=q.raw;
        tr.fade+=((q.res>-15?0.:1.)-tr.fade)*(1-std::exp(-16./90));
        traceTrack52(p,tr,best>=0?HarmonicTrace::Tracked:HarmonicTrace::Birth,q.res>-15?HarmonicTrace::Fit:0);
        renderTrack52(tr,src,ns,true,false,p,grain,agrain);
        next[p]=tr;
    }
    int lost=0,traceSlot=np;
    for(int t=0;t<nt52_;++t) if(!used[t]) {
        ++lost; auto tr=tr52_[t]; ++tr.age; ++tr.missing;
        if(!continuity_.enabled && !(stageFlags_&StageOscillator)) {
            traceTrack52(np+lost-1,tr,HarmonicTrace::End,HarmonicTrace::Lost); continue;
        }
        const bool fast=born || tr.fastEnding; tr.fastEnding=fast;
        tr.phi+=2*kPi*tr.f*kPvH/kFsd;
        if(fast || tr.missing>continuity_.hold)
            tr.life=std::max(0.,tr.life-1./std::max(1,fast?continuity_.fastRelease:continuity_.release));
        if(!continuity_.enabled) tr.life=0;
        if(tr.life<1e-12) tr.life=0;
        const int state=tr.life<=0?HarmonicTrace::End:(fast || tr.missing>continuity_.hold?HarmonicTrace::Release:HarmonicTrace::Held);
        if(nextCount>=12) {
            if(harmonicCapture_) harmonicTrace_.data[21]+=1;
            continue;
        }
        const int traceIndex=traceSlot++;
        if(harmonicCapture_ && traceIndex>=HarmonicTrace::kTracks) harmonicTrace_.data[21]+=1;
        traceTrack52(traceIndex,tr,state,HarmonicTrace::Lost);
        if(tr.life>0 || (stageFlags_&StageOscillator)) {
            renderTrack52(tr,src,ns,false,fast,traceIndex,grain,agrain);
            if(tr.life>0) next[nextCount++]=tr;
        }
    }
    if(harmonicCapture_) {
        auto* h=harmonicTrace_.data; h[11]=static_cast<float>(np); h[12]=static_cast<float>(nextCount-np);
        h[14]=static_cast<float>(am); h[22]=static_cast<float>(lost);
        if(h[21]>0) h[13]=static_cast<float>(static_cast<int>(h[13])|HarmonicTrace::Capacity);
        double power=0; for(double v:grain) power+=v*v; h[20]=static_cast<float>(std::sqrt(power/32));
    }
    std::copy(next,next+nextCount,tr52_); nt52_=nextCount;
    if(histCount_==11) {
        for(int h=0;h<10;++h) { std::copy(hist52_[h+1],hist52_[h+1]+6,hist52_[h]); histN52_[h]=histN52_[h+1]; }
        --histCount_;
    }
    int n=0; for(int p=0;p<np;++p) if(tr52_[p].strong) hist52_[histCount_][n++]=tr52_[p].f;
    histN52_[histCount_++]=n;
    addGrain52(centre,grain,agrain);
}

void VbHpv::addGrain52(int64_t centre,const double* grain,double nominalAmplitude) {
    if(stageFlags_&StageOscillator) {
        // Current frame's centre=i+16. Both endpoint controls are known now;
        // write[i,i+15] before core52 takes sample i. Declared latency unchanged.
        for(int g=0;g<kPvH;++g) {
            const int slot=(centre-kPvH+g)&(kRing-1);
            pvOut_[slot]+=grain[g];pvApv_[slot]+=oscillatorNominal52_[g];
        }
        return;
    }
    for(int g=0;g<32;++g) {
        const int slot=(centre-16+g)&(kRing-1);
        pvOut_[slot]+=grain[g]*gw_[g];pvApv_[slot]+=nominalAmplitude*gw_[g];
    }
}
void VbHpv::takeGrain52(int64_t index,double& sample,double& nominalAmplitude) {
    const int slot=index&(kRing-1);
    sample=pvOut_[slot];nominalAmplitude=pvApv_[slot];
    pvOut_[slot]=pvApv_[slot]=0;
}

double VbHpv::core52(double d) {
    const int64_t i=static_cast<int64_t>(i_); const int slot=i&(kRing-1);
    md52_[slot]=d; md2_52_[slot]=i>=191?md52_[(i-191)&(kRing-1)]:0;
    double b=d; for(auto& s:band_) b=s.tick(b); bRing_[slot]=b;
    if((i+1)%16==0) hpssFrame();
    double bh=0,bp=0;
    if(i>=191) {
        const int64_t t=i-191; const int s=t&(kRing-1); const double ws=wsumHp_[t%16];
        bh=olaH_[s]/ws; bp=olaP_[s]/ws; olaH_[s]=olaP_[s]=0;
    }
    const double originalH=bh,originalP=bp,bandDelayed=i>=191?bRing_[(i-191)&(kRing-1)]:0.;
    detailRing52_[slot]=bandDelayed;
    if(stageFlags_&StageBypassHpss) {bh=bandDelayed;bp=0.;}
    double hr,hi,pr,pi; hilH_.tick(bh,hr,hi); hilP_.tick(bp,pr,pi);
    bhRing_[slot]=bh; aRing_[slot]=std::hypot(hr,hi);
    const double att=std::exp(-1./6),rel=std::exp(-1./120);
    const double ep=bp*bp,eh=bh*bh;
    double a=ep>percEnv52_?att:rel; percEnv52_=a*percEnv52_+(1-a)*ep;
    a=eh>harmEnv52_?att:rel; harmEnv52_=a*harmEnv52_+(1-a)*eh;
    const double gate=clampv((10*std::log10((percEnv52_+1e-20)/(harmEnv52_+1e-20))+3)/6,0.,1.);
    hpRing_[slot]=bandLayer(pr,pi)*gate;
    if(i>=383 && (i-383)%16==0) pvFrame52();
    // Exact nearest-edge centred closing, evaluated with the existing vocoder delay.
    if(i>=90) {
        double m=0; for(int64_t j=std::max<int64_t>(0,i-180);j<=i;++j) m=std::max(m,aRing_[j&(kRing-1)]);
        max52_[(i-90)&(kRing-1)]=m;
    }
    double ac=0;
    if(i>=207) {
        const int64_t t=i-207; ac=1e30;
        for(int64_t j=std::max<int64_t>(0,t-90);j<=t+90;++j) ac=std::min(ac,max52_[j&(kRing-1)]);
    }
    double out,apv;takeGrain52(i,out,apv);
    const double as=envA_.tick(ac),ps=envP_.tick(apv);
    const double gain=apv>0?clampv(as/(ps+1e-9),0.,1.):0;
    const double gainTarget=(familyApplied52_ || detailApplied52_)?1.:0.;
    if(stageFlags_&StageConditionalGain) {
        const double smoothing=std::exp(-1./(gainTarget>conditionalGain52_?60:120));
        conditionalGain52_=smoothing*conditionalGain52_+(1-smoothing)*gainTarget;
    }
    const double selectedGain=(stageFlags_&StageConditionalGain)?gain+(1-gain)*conditionalGain52_:gain;
    const double appliedGain=(stageFlags_&StageBypassGain)?(apv>0?1.:0.):selectedGain;
    const double target=polyT52_[slot]; polyT52_[slot]=1;
    a=std::exp(-1./(target<poly52_?60:600)); poly52_=a*poly52_+(1-a)*target;
    const double hp=i>=207?hpRing_[(i-207)&(kRing-1)]*poly52_:0;
    const double preFilter=out*appliedGain+(tonalOnly_?0:hp);
    double y=preFilter;for(auto& s:out_) y=s.tick(y);
    if(harmonicReady_) {
        harmonicTrace_.data[17]=static_cast<float>(gain); harmonicTrace_.data[18]=static_cast<float>(poly52_);
        harmonicTrace_.data[19]=static_cast<float>(out);
    }
    if(stageSink_) {
        const double values[StageCapture52::kValues]={d,b,bandDelayed,originalH,originalP,bh,bp,std::hypot(hr,hi),
            out,apv,as,ps,gain,appliedGain,out*appliedGain,tonalOnly_?0.:hp,preFilter,y,
            research_.upperBlend,static_cast<double>(stageFlags_),static_cast<double>(modulationMode_),gate,detailApplied52_?1.:0.,
            familyApplied52_?1.:0.,family52_.residual,family52_.coherence};
        stageSink_(stageUser_,i_,values);
    }
    ++i_; return y;
}
void VbHpv::spectrum52(const double* ring, int64_t s0, double* re, double* im) {
    const int half = kPvN / 2;
    double frame[kPvN];
    for (int n = 0; n < kPvN; ++n) frame[n] = ring[(s0 + n) & (kRing - 1)] * winPv_[n];
    // zero-phase arrangement fr = [frame[half:], zeros, frame[:half]] (2048 points), real FFT: the even samples go into
    // the real and the odd ones into the imaginary part of a 1024-point complex FFT.
    
    std::fill(std::begin(zr_), std::end(zr_), 0.0);
    std::fill(std::begin(zi_), std::end(zi_), 0.0);
    auto put = [&](int pos, double v) {
        const int j = bitrev_[pos >> 1];
        if (pos & 1) zi_[j] = v; else zr_[j] = v;
    };
    for (int n = 0; n < half; ++n) {
        put(n, frame[half + n]);
        put(kPvNfft - half + n, frame[n]);
    }
    for (int len = 2; len <= kHalfFft; len <<= 1) {
        const int hl = len >> 1, step = kPvNfft / len;  // twiddle exp(-2 pi i k / len) = table index 2 k step / 2
        for (int i0 = 0; i0 < kHalfFft; i0 += len) {
            for (int k = 0; k < hl; ++k) {
                const double wr = cosPv_[k * step], wi = -sinPv_[k * step];
                const int a = i0 + k, b = a + hl;
                const double tr = zr_[b] * wr - zi_[b] * wi;
                const double ti = zr_[b] * wi + zi_[b] * wr;
                zr_[b] = zr_[a] - tr;
                zi_[b] = zi_[a] - ti;
                zr_[a] += tr;
                zi_[a] += ti;
            }
        }
    }
    re[0]=zr_[0]+zi_[0]; im[0]=0;
    re[kHalfFft]=zr_[0]-zi_[0]; im[kHalfFft]=0;
    for (int k=1;k<kHalfFft;++k) {
        const double ar=zr_[k], ai=zi_[k], br=zr_[kHalfFft-k], bi=-zi_[kHalfFft-k];
        const double er=.5*(ar+br), ei=.5*(ai+bi), dr=.5*(ar-br), di=.5*(ai-bi);
        const double wr=cosPv_[k], wi=-sinPv_[k];
        re[k]=er+di*wr+dr*wi; im[k]=ei+di*wi-dr*wr;
    }
}
}



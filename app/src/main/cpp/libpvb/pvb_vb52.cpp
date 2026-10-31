// hpv52m strictly causal port; vb51/PORT_SPEC.md and hpv51.py are the reference.
#include "pvb_vb.h"
#include "pvb_dsp.h"
#include "pvb_vb_tables.h"
#include "pvb_vb52_tables.h"
#include "pvb_vb_r1_tables.h"
#include "pvb_vb_detail.h"
#include "pvb_track_assignment.h"
#include <algorithm>
#include <cmath>
#include <complex>
#include <vector>
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
// Grid points g (0..189) that can pass |g + 20 - f| <= 8: about 17 of the 190. The test itself is still applied to
// each of them, so exactly the same points pass as with a scan of the whole grid.
void holdRange52(double f, int& lo, int& hi) {
    if (!(f == f)) { lo = 0; hi = -1; return; }   // NaN: no point passes
    const double c = clampv(f, -1000.0, 1000.0);
    lo = std::max(0, static_cast<int>(std::floor(c - 29)));
    hi = std::min(189, static_cast<int>(std::ceil(c - 11)));
}
// Offset of a harmonic without a partial of its own in the input: kPsi, or with Resultant R1 kPsi plus the
// crest-optimal change for the fundamental (linear in f between table points, clamped at the table ends).
double psi52(int k, double f, bool crest) {
    if (!crest) return vbt::kPsi[k-2];
    const double x = clampv((f - vbr1::kF0) / vbr1::kStep, 0.0, static_cast<double>(vbr1::kN - 1));
    const int j = std::min(static_cast<int>(x), vbr1::kN - 2); const double r = x - j;
    return vbt::kPsi[k-2] + vbr1::kDelta[j][k-2] * (1 - r) + vbr1::kDelta[j+1][k-2] * r;
}
}


void VbHpv::beginHarmonic52() {
    if(!harmonicCapture_) return;
    std::fill(std::begin(harmonicTrace_.data),std::end(harmonicTrace_.data),0.f);
    auto* h=harmonicTrace_.data; h[2]=static_cast<float>(harmonicEpoch_);
    for(int j=0;j<4;++j) h[3+j]=static_cast<float>((i_>>(16*j))&65535);
    h[7]=-383; h[8]=static_cast<float>(191+hpssLookahead());
    const double hostPerCore=static_cast<double>(M_)/L_;
    const double fractional=static_cast<double>(M_)*static_cast<double>(m_)/L_-static_cast<double>(n_);
    const double firDelay=static_cast<double>(taps_-1)/(2*L_);
    h[9]=static_cast<float>(fractional-(382.+hpssLookahead())*hostPerCore-firDelay);
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
    double w[7],gain; lookup(tr.f,w,gain);
    if(devHarm_) devWeights(w);   // developer mode: per-harmonic offsets (off: untouched)
    double devH[7]={};
    // A track that is itself the 2nd or 3rd harmonic of a live lower track (a sub-bass with a strong native 2nd
    // harmonic) keeps 220 Hz and its level (R4, R4-L): its upper partials are high orders of the lower series.
    const bool upperRegister=tr.f*3>220;
    bool harmonicOfLower=false;
    if(upperRegister && (stageFlags_&(StageRegisterCorner|StageRegisterLevel))) for(int t=0;t<nt52_;++t) {
        const auto& o=tr52_[t];
        if(o.life>0 && o.f<tr.f*.9 && (std::abs(tr.f/2-o.f)<=.03*o.f || std::abs(tr.f/3-o.f)<=.03*o.f)) {harmonicOfLower=true;break;}
    }
    // Share of the register corner and level: onsetBlend52_, times the track's own after a failed fit (R4-L v2).
    const double share=onsetBlend52_*((stageFlags_&StageReentrySlow)?tr.r4Share:1.);
    // Resultant R4-L: the register level, 0 dB at 73.3 Hz, full from 92.4 to 150 Hz, 0 dB again at 220 Hz; it scales
    // the rendered amplitude only (the nominal level below uses tr.a), blended by the share like the corner.
    if((stageFlags_&StageRegisterLevel) && upperRegister && !harmonicOfLower && tr.f<220) {
        const double s=tr.f<92.4?3*std::log2(tr.f*3/220):tr.f<=150?1.:std::log2(220/tr.f)/std::log2(220/150.);
        gain*=1+share*(std::pow(10.,r4LevelDb52_*clampv(s,0.,1.)/20)-1);
    }
    // S1 research: the per-harmonic envelope below is the only time gate.
    const double amp=gen_.envelope?tr.a*gain:tr.a*gain*tr.fade*tr.life;
    // P1++ v0.4 bit 16: a track held back only by the fit guard emits the harmonics found in the input at k f
    const double ampHeld=tr.guarded && !gen_.envelope ? tr.a*gain*tr.life : 0.;
    double heldW=0,allW=0;
    const double hopMs=1000.*kPvH/kFsd;
    // S1 per-harmonic envelope: the harmonic's own amplitude (a x table gain x weight x
    // on/off) followed by one asymmetric one-pole. Attack reaches 90% in attackMs; a fall is
    // limited to the release (onsetRelease only for a track ended by a newly born note).
    // Returns the multiplier that turns amp*w into the envelope.
    double envSum=0,refSum=0;
    auto envelope=[&](HarmonicPermission& e,double weight,bool on) {
        const double target=on?amp*weight:0.;
        const double tau=target>e.value?gen_.attackMs/2.3:(tr.fastEnding?gen_.onsetReleaseMs:gen_.releaseMs);
        e.value+=(target-e.value)*(1-std::exp(-hopMs/std::max(1e-3,tau)));
        if(e.value<1e-12) e.value=0;
        const double ref=amp*weight;
        envSum+=e.value; refSum+=ref;
        return ref>0?e.value/ref:0.;
    };
    const bool alive=!tr.fastEnding && tr.missing<=continuity_.hold;
    const bool oscillator=stageFlags_&StageOscillator;
    const bool preserveUnreferencedPhase=p1PlusProfile_ && (p1PlusFlags_&2);
    double targetAmplitude[7]={},targetPhase[7]={};
    for(int j=0;j<7;++j) targetPhase[j]=(j+2)*tr.phi+tr.off[j];
    // Resultant R4: the roll-off factor for a corner; the register corner is blended in by onsetBlend52_ (1 without
    // StageOnsetProtect), and equals 220 Hz below 73.3 Hz, so those weights stay bit-identical.
    auto rolloff=[&](double fk,double corner) {
        if(devRolloff_) {
            // Developer mode: the module's own slope (12 or 24 dB/oct) plus the offset, 0..48 dB/oct.
            const double slope=clampv((upperMode_==0?12.:24.)+dev_.rolloffOffset,0.,48.);
            return std::pow(10.,-slope*std::log2(fk/corner)/20);
        }
        const double g12=std::pow(10.,-12*std::log2(fk/corner)/20);
        // Both budgets share frequency, phase, grid and track history.
        // A convex amplitude blend introduces no second oscillator.
        return g12+research_.upperBlend*(g12*g12-g12);
    };
    const bool registerCorner=(stageFlags_&StageRegisterCorner) && !harmonicOfLower;
    const double corner=std::max(220.,3*tr.f);
    for(int k=2;k<=8;++k) {
        // Exact gentle128 reference: sustained partials above 220 Hz lose
        // 12 dB/octave; no redistribution, no percussion or level change.
        if(gentle_ && k*tr.f>220) {
            const double base=w[k-2]*rolloff(k*tr.f,220.);
            if(registerCorner) {
                const double moved=k*tr.f>corner?w[k-2]*rolloff(k*tr.f,corner):w[k-2];
                w[k-2]=base+share*(moved-base);
            } else w[k-2]=base;
        }
        float* ht=harmonicCapture_ && traceSlot<HarmonicTrace::kTracks ?
            harmonicTrace_.data+HarmonicTrace::kHeader+traceSlot*HarmonicTrace::kTrack+14+6*(k-2) : nullptr;
        if(ht) { ht[0]=static_cast<float>(amp*w[k-2]); ht[4]=tr.residual>-15?HarmonicTrace::Fit:0; }
        bool weightOff=false;
        if(w[k-2]<=1e-4) {
            if(ht) ht[4]=static_cast<float>(static_cast<int>(ht[4])|HarmonicTrace::Weight);
            if(gen_.envelope) {
                // S1: a harmonic whose table weight vanished releases like any other.
                weightOff=true; w[k-2]=std::max(w[k-2],1e-20);
                if(tr.permission[k-2].value<=0) continue;
            } else {
                if(continuity_.enabled) tr.permission[k-2]={};
                continue;
            }
        }
        const double fk=k*tr.f;
        double tolGrid=std::max(4.,.1*24.7*(4.37*fk/1000+1));
        // Study 3 C3: below 65 Hz a fundamental within 10 % supports its harmonics (k x tolerance, not tolerance);
        // C4: the same outside an impact context only
        const bool lowGrid=(stageFlags_&StageLowGridTolerance) ||
            ((stageFlags_&StageLowGridOutsideImpact) && lowGridHold52_==0);
        if(lowGrid && tr.f<65) tolGrid=std::max(tolGrid,k*.1*tr.f);
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
        double mask;
        if(gen_.envelope) {
            auto& e=tr.permission[k-2];
            const bool supported=observed && (evidence>=1.0 || (e.value>0 && evidence>=.5));
            if(supported) e.missing=0; else ++e.missing;
            const bool target=!weightOff && alive && tr.residual<=-15 && (supported || e.missing<=continuity_.hold);
            mask=envelope(e,w[k-2],target);
        } else mask=(stageFlags_&StageBypassPermission)?1.:
            continuity_.enabled?tr.permission[k-2].step(evidence,continuity_,fast):(on?1.:0.);
        if(ht) {
            ht[1]=static_cast<float>(amp*w[k-2]*mask); ht[2]=static_cast<float>(mask);
            if(!on) ht[4]=static_cast<float>(static_cast<int>(ht[4])|HarmonicTrace::Grid);
        }
        if(mask<=0) continue;
        if(devMeter_) devH[k-2]=amp*w[k-2]*mask;
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
        const double ak=ampHeld>amp && found ? ampHeld : amp;
        if(ampHeld>0) { allW+=w[k-2]*mask; if(found) heldW+=w[k-2]*mask; }
        double target=!observed || !on ? tr.off[k-2] : found ? std::atan2(si52_[ii],sr52_[ii])+interp52(vb52t::kPhase,3920,(fk-20)*4)+phaseDelta52(fk)+2*kPi*fk*tc-k*tr.phi : psi52(k,tr.f,stageFlags_&StagePhaseCrest);
        // Losing a reference gives no new phase observation. Returning to an
        // arbitrary table offset would itself modulate an otherwise steady
        // oscillator. Keep its offset until a valid reference or a new track.
        // No stale source phase is advanced or claimed as a new observation.
        if(preserveUnreferencedPhase && !found) target=tr.off[k-2];
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
            const double mean=ak/(1+tr.family.cosine);
            for(int g=0;g<32;++g) {
                const double t=(g-16)/3000.;const auto z=std::polar(1.,2*kPi*tr.family.rate*t);
                const auto envelope=1.+lower*std::conj(z)+upper*z;
                grain[g]+=mean*w[k-2]*mask*(std::polar(1.,k*(tr.phi+2*kPi*tr.f*t)+tr.off[k-2])*envelope).real();
            }
        } else if(!(modulationMode_&1) || !observed) {
            for(int g=0;g<32;++g) grain[g]+=ak*w[k-2]*mask*std::cos(k*(tr.phi+2*kPi*tr.f*(g-16)/3000)+tr.off[k-2]);
        } else for(int g=0;g<32;++g) {
            const double t=(g-16)/3000.;double ratio,phase;
            if(tr.family.valid) tr.family.local(t,ratio,phase);
            else if(tr.modulation.valid) modulation::local(tr.modulation,t,ratio,phase);
            else {
                ratio=clampv(1+tr.dadt*t/std::max(tr.a,1e-12),0.,3.);
                phase=2*kPi*tr.f*t+kPi*clampv(tr.dfdt,-400.,400.)*t*t;
            }
            grain[g]+=ak*w[k-2]*mask*ratio*std::cos(k*(tr.phi+phase)+tr.off[k-2]);
        }
    }

    if(devMeter_) {
        // Developer-mode display: the loudest rendered tracks of this frame.
        double sum=0; for(double v:devH) sum+=v;
        devFrame_.add(tr.f,devH,sum);
    }
    // S1: rendered level relative to the current target sum; nominal and removal use it.
    const double envPeak=refSum>1e-12?envSum/refSum:(envSum>0?1.:0.);
    tr.envPeak=envPeak;
    const double nominal=gen_.envelope?tr.a*envPeak:
        tr.a*std::max(tr.fade,ampHeld>0 && allW>0 ? heldW/allW : 0.)*tr.life;
    if(oscillator) tr.oscillator.add(tr.f,targetAmplitude,targetPhase,nominal,
        stageFlags_&StageOscillatorCorrect,grain,oscillatorNominal52_);
    agrain+=(stageFlags_&StageNominalPower)?nominal*nominal:nominal;
}
void VbHpv::missingFrame52(int reason,bool fast) {
    std::fill(std::begin(oscillatorNominal52_),std::end(oscillatorNominal52_),0.);
    if(harmonicCapture_) { harmonicTrace_.data[13]=static_cast<float>(reason); harmonicTrace_.data[22]=static_cast<float>(nt52_); }
    if(!continuity_.enabled && !(stageFlags_&StageOscillator)) {
        for(int j=0;j<nt52_;++j) traceTrack52(j,tr52_[j],HarmonicTrace::End,reason|HarmonicTrace::Lost);
        nt52_=0; if(devMeter_) devEndFrame(); return;
    }
    const double src[2][256]={}; const int ns[2]={};
    double grain[32]={},agrain=0; int n=0;
    for(int j=0;j<nt52_;++j) {
        auto tr=tr52_[j]; ++tr.age; ++tr.missing;
        // S1: silence (Absolute) is not a note onset; only a born note cuts fast.
        const bool fastEnd=gen_.envelope?tr.fastEnding:(fast || tr.fastEnding); tr.fastEnding=fastEnd;
        tr.phi+=2*kPi*tr.f*kPvH/kFsd;
        if(fastEnd || tr.missing>continuity_.hold)
            tr.life=std::max(0.,tr.life-1./std::max(1,fastEnd?continuity_.fastRelease:continuity_.release));
        if(!continuity_.enabled) tr.life=0;
        if(tr.life<1e-12) tr.life=0;
        if(gen_.envelope) tr.life=1;
        const int state=tr.life<=0?HarmonicTrace::End:(fastEnd || tr.missing>continuity_.hold?HarmonicTrace::Release:HarmonicTrace::Held);
        traceTrack52(j,tr,state,reason|HarmonicTrace::Lost);
        // Resultant core: the tracker is kept as it is, only P1's grain renderer is skipped
        if((tr.life>0 || (stageFlags_&StageOscillator)) && !resultantOn_) renderTrack52(tr,src,ns,false,fastEnd,j,grain,agrain);
        if(gen_.envelope && tr.envPeak<1e-2) tr.life=0;
        if(tr.life>0) tr52_[n++]=tr; else grave52(tr);
    }
    nt52_=n; ++hop52_;
    double energy=0;
    for(int g=0;g<32;++g) energy+=grain[g]*grain[g];
    if(!resultantOn_) addGrain52(static_cast<int64_t>(i_)+16,grain,agrain);
    if(harmonicCapture_) { harmonicTrace_.data[12]=static_cast<float>(n); harmonicTrace_.data[20]=static_cast<float>(std::sqrt(energy/32)); }
    if(devMeter_) devEndFrame();
    if(resultantOn_) resultant_.hop(*this,false,nullptr,nullptr);   // a hop without a measurement (Absolute, NoPeak, Relative)
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
    // latency_ is the base placement/rounding correction. HQ HPSS delays both
    // source observations and the dry stream equally; do not subtract that
    // additional delay again from the relative harmonic phase reference.
    const double timing=2*kPi*f*(7052./48000-static_cast<double>(latency_)/eqFs52_);
    return std::arg(actual/ref)+timing;
}

void VbHpv::grave52(const Track52& tr) {
    // a track that ends may have been pulled away by an impact sweeping through it: remember where it was when it
    // was last confirmed, and when
    // Only a tone confirmed for 300 ms (56 hops) counts: an impact's own body is shorter than that.
    if(!(p1ppV04_&8) || p1ppImpactMode_!=8 || hop52_-tr.confHop>47 || tr.confHops<56) return;
    int slot=0; for(int g=1;g<8;++g) if(graveHop52_[g]<graveHop52_[slot]) slot=g;
    if(graveN52_<8) slot=graveN52_++;
    grave52_[slot]=tr.confF; graveHop52_[slot]=tr.confHop;
}

// Study 3 C6: the polyphony count of pvFrame52 (six strongest local maxima above the relative floor, harmonics of a
// lower peak removed, peaks at a quarter of the strongest or more) on the causal HPSS harmonic part. The dominant
// peak's modulation fit is not repeated here; it only refines that peak's own frequency and amplitude.
int VbHpv::polyCausal52(int64_t s0) {
    spectrum52(bhCausal52_,s0,polyXr52_,polyXi52_);
    const int nb=hiBin_-loBin_; double mag[256],mx=0;
    for(int b=0;b<nb;++b) { mag[b]=std::hypot(polyXr52_[loBin_+b],polyXi52_[loBin_+b]); mx=std::max(mx,mag[b]); }
    if(mx*2/pvWsum_<pvAbs_) return 0;
    int lm[256],nl=0;
    for(int b=1;b<nb-1;++b) if(mag[b]>=mag[b-1] && mag[b]>mag[b+1]) lm[nl++]=b;
    std::sort(lm,lm+nl,[&](int a,int b) {return mag[a]==mag[b] ? a>b : mag[a]>mag[b];});
    double f[6],a[6]; int np=0;
    for(int j=0;j<nl && np<6;++j) {
        const int b=lm[j]; if(mag[b]<mx*pvRel_) break;
        const double l=std::log(mag[b-1]+1e-30),v=std::log(mag[b]+1e-30),c=std::log(mag[b+1]+1e-30);
        const double off=offset52(l,v,c);
        f[np]=(loBin_+b)*binHz_+off*binHz_; a[np++]=std::exp(v-.25*(l-c)*off)*2/pvWsum_;
    }
    int order[6]; for(int p=0;p<np;++p) order[p]=p;
    std::sort(order,order+np,[&](int x,int y){return f[x]<f[y];});
    double kf[6],ka[6]; int nk=0;
    for(int i=0;i<np;++i) {
        const int p=order[i]; bool own=false;
        for(int q=0;q<nk;++q) {
            const double n=std::nearbyint(f[p]/kf[q]);
            if(n>=2 && n<=5 && std::abs(f[p]-n*kf[q])<=std::max(1.5,.015*f[p])) own=true;
        }
        if(!own) {kf[nk]=f[p]; ka[nk++]=a[p];}
    }
    double am=0; for(int p=0;p<nk;++p) am=std::max(am,ka[p]);
    int poly=0; for(int p=0;p<nk;++p) if(ka[p]>=.25*am) ++poly;
    return poly;
}

void VbHpv::pvFrame52() {
    std::fill(std::begin(oscillatorNominal52_),std::end(oscillatorNominal52_),0.);
    detailApplied52_=familyApplied52_=false;
    beginHarmonic52();
    if(devMeter_) devBeginFrame();
    // Study 3 C4: the v0.3 impact context (percussive envelope above a quarter of the harmonic one, held 24 hops =
    // 128 ms) suspends the wider low grid, so an impact's own low tail is judged as before
    if(stageFlags_&StageLowGridOutsideImpact) lowGridHold52_=percEnv52_>.25*harmEnv52_?24:std::max(0,lowGridHold52_-1);
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
    struct Peak { double f,a,ph,beta,res; double raw=0; ModulationFit modulation={}; AmFamily52 family={}; } pk[8];
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
    const bool v04=p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_==8;
    if(v04 && (p1ppV04_&1) && !(stageFlags_&StageGlobalTrack)) {
        // v0.4 bit 1: a broadband impact fills the six strongest peaks and pushes a confirmed tone out; it would end
        // after the hold and come back as a new, guarded track. Keep the confirmed tone's own local peak instead
        // (within 5 % of it, at most 60 dB under the strongest), up to eight peaks.
        for(int t=0;t<nt52_ && np<8;++t) {
            const auto& tr=tr52_[t];
            if(tr.fade<.5 || tr.missing>continuity_.hold) continue;
            bool have=false; for(int p=0;p<np;++p) if(std::abs(pk[p].f-tr.f)<=.05*tr.f) have=true;
            if(have) continue;
            for(int j=0;j<nl;++j) {
                const int b=lm[j]; if(mag[b]<mx*1e-3) break;
                const double fb=(loBin_+b)*binHz_; if(std::abs(fb-tr.f)>.05*tr.f) continue;
                const double a=std::log(mag[b-1]+1e-30), vv=std::log(mag[b]+1e-30), c=std::log(mag[b+1]+1e-30);
                const double off=offset52(a,vv,c);
                pk[np++]={ (loBin_+b)*binHz_+off*binHz_, std::exp(vv-.25*(a-c)*off)*2/pvWsum_,
                           std::atan2(xi52_[loBin_+b],xr52_[loBin_+b]), loBin_+b+off, 0 };
                break;
            }
        }
    }
    double minb=pk[0].beta,maxb=minb;
    for (int p=1;p<np;++p) { minb=std::min(minb,pk[p].beta); maxb=std::max(maxb,pk[p].beta); }
    const int lo=std::max(0,static_cast<int>(minb)-12), hi=static_cast<int>(maxb)+13;
    double err[256]={};
    std::complex<double> peakModel[8];  // (a W / 2) e^(i ph) of each peak, evaluated once instead of once per bin
    for (int p=0;p<np;++p) peakModel[p]=(pk[p].a*pvWsum_/2)*std::exp(std::complex<double>(0,pk[p].ph));
    for (int b=lo;b<hi;++b) {
        std::complex<double> model=0;
        for (int p=0;p<np;++p) model+=peakModel[p]*kernel52(b-pk[p].beta);
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
    const bool ampOnset=apkCount_>8 && am>1.41*past; // S1 research: amplitude onset for the true-onset test
    if(apkCount_<=8 || am>1.41*past || born) onsetLeft_=24;
    // R01 host-only identity protection: arm only long, confirmed stationary
    // tracks at a strong percussive onset. A transient peak crossing their
    // previous frequency may not inherit their ID when it walks away.
    const bool protectIdentity=v04 && (p1ppV04_&64);
    if(protectIdentity) {
        // Reserved trace field 27: high 16 bits hold one-off R01 diagnostic
        // flags (1 strong onset, 2 percussion, 4 mature track, 8 armed).
        // Low 16 bits remain for the existing modulation observer (+=32).
        int diag=(ampOnset?1:0) | (percEnv52_>.25*harmEnv52_?2:0);
        bool mature=false,armed=false;
        for(int t=0;t<nt52_;++t) {
            auto& tr=tr52_[t];
            const bool confirmed=tr.fade>=.5 && tr.missing==0;
            mature |= confirmed && tr.protection.recentlyMature();
            // P&M overlapped for ten hops in the inspected kick while the
            // instantaneous amplitude-onset marker arrived after maturity was
            // lost (O&M=0). Percussion evidence is the earlier trigger here;
            // the long-established tonal track is an independent prerequisite.
            if(diag&2)
                armed |= tr.protection.arm(true,confirmed);
        }
        if(mature) diag|=4;
        if(armed) diag|=8;
        if(harmonicCapture_) harmonicTrace_.data[27]+=static_cast<float>(diag*65536);
    }
    if(apkCount_==56) { std::move(apk52_+1,apk52_+56,apk52_); --apkCount_; }
    apk52_[apkCount_++]=am;
    double* hm=hold52_[holdPos_]; std::fill(hm,hm+190,-200.0);
    const bool modelAwareHistory=p1PlusProfile_ && (p1PlusFlags_&1);
    if(onsetLeft_<=0 && !falling) for(int p=0;p<np;++p) {
        // A stationary-model mismatch explained by a valid modulation model
        // is not evidence against a later stationary frame. Do not insert the
        // modulation residual as a "good" stationary value either.
        if(modelAwareHistory && pk[p].modulation.valid) continue;
        int g0,g1; holdRange52(pk[p].f,g0,g1);
        for(int g=g0;g<=g1;++g) if(std::abs(g+20-pk[p].f)<=8) hm[g]=std::max(hm[g],pk[p].res);
    }
    if(harmonicCapture_) { harmonicTrace_.data[24]=static_cast<float>(onsetLeft_); harmonicTrace_.data[25]=falling?1.f:0.f; harmonicTrace_.data[26]=static_cast<float>(holdCount_); }
    --onsetLeft_; holdPos_=(holdPos_+1)%28; holdCount_=std::min(28,holdCount_+1);
    if(stageFlags_&StageOnsetProtect) {
        // Resultant R4: back to the 220 Hz roll-off within ~10 ms of a low-band onset, the register corner over ~60 ms
        const double target=onsetLeft_>24-r4Hold52_?r4Floor52_:1.,tau=target<onsetBlend52_?10.:r4TauUp52_;
        onsetBlend52_+=(target-onsetBlend52_)*(1-std::exp(-1000.*kPvH/kFsd/tau));
    }
    for(int p=0;p<np;++p) {
        if(pk[p].modulation.valid) { pk[p].res=pk[p].modulation.residual; continue; }
        double r=-200;
        int g0,g1; holdRange52(pk[p].f,g0,g1);
        for(int h=0;h<holdCount_;++h) for(int g=g0;g<=g1;++g)
            if(std::abs(g+20-pk[p].f)<=8) r=std::max(r,hold52_[h][g]);
        // History exclusion must not turn missing history into acceptance.
        // Preserve a direct current-frame check outside the existing onset/
        // falling exceptions (onsetLeft_ was decremented above).
        if((modelAwareHistory && onsetLeft_<0 && !falling) ||
           (p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_==1))
            r=std::max(r,pk[p].raw);
        pk[p].res=r;
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
    if(stageFlags_&StageRawFrequency) for(int p=0;p<np;++p) {
        // Study 3 C2: frequency only, from the nearest unfiltered peak within 10 % that no other peak is nearer to
        int best=-1;
        for(int j=0;j<ns[0];++j) if(std::abs(src[0][j]-pk[p].f)<=.1*pk[p].f &&
            (best<0 || std::abs(src[0][j]-pk[p].f)<std::abs(src[0][best]-pk[p].f))) best=j;
        if(best<0) continue;
        bool nearest=true;
        for(int q=0;q<np;++q) if(q!=p && std::abs(src[0][best]-pk[q].f)<std::abs(src[0][best]-pk[p].f)) nearest=false;
        if(nearest) pk[p].f=src[0][best];
    }
    if(stageFlags_&(StageSubOctave|StageSubOctaveStrict|StageSubOctaveNoHold)) {
        // Resultant R3: a note at T whose unfiltered spectrum shows the odd partial 1.5 T (strict: and 2.5 T) as a peak
        // within 10 dB of T (20 dB while a track already holds T / 2, or strict) is the second harmonic of T / 2, a bass whose
        // fundamental is weak or masked (real-music ground truth: 31 % of 41-55 Hz frames tracked an octave up). The
        // peak becomes T / 2, its phase the half phase whose third harmonic matches the 1.5 T partial; then the
        // harmonic dependence check runs again, so 1.5 T and T itself become harmonics of the new peak.
        const bool strict=stageFlags_&StageSubOctaveStrict;
        auto level=[&](double f,int& at) {
            const int lb=std::max(1,static_cast<int>(std::floor(.975*f/binHz_)));
            const int hb=std::min(kHalfFft-1,static_cast<int>(std::ceil(1.025*f/binHz_)));
            at=lb; for(int b=lb;b<=hb;++b) if(sm52_[b]>sm52_[at]) at=b;
            const bool peak=at>lb && at<hb && sm52_[at]>=sm52_[at-1] && sm52_[at]>=sm52_[at+1];
            return peak?sm52_[at]:0.;
        };
        // ...and T / 2 itself must be heard within 20 dB of T (26 dB while held), peak or not: an octave-up frame has its
        // fundamental at -6 dB re T (median, real-music ground truth), a correctly tracked note nothing at T / 2 (-30 dB)
        auto any=[&](double f) {
            const int lb=std::max(1,static_cast<int>(std::floor(.975*f/binHz_)));
            const int hb=std::min(kHalfFft-1,static_cast<int>(std::ceil(1.025*f/binHz_)));
            double m=0; for(int b=lb;b<=hb;++b) m=std::max(m,sm52_[b]); return m;
        };
        bool changed=false;
        for(int p=0;p<np;++p) {
            const double T=pk[p].f; if(T<54 || T>190) continue;
            bool held=false;   // R3-a: no relaxation for a held T / 2
            if(!(stageFlags_&StageSubOctaveNoHold))
                for(int t=0;t<nt52_;++t) if(tr52_[t].life>0 && std::abs(tr52_[t].f-T/2)<=.03*T/2) held=true;
            const double floor=std::pow(10.,-((held || strict)?20.:10.)/20), floorHalf=std::pow(10.,-(held?26.:20.)/20);
            int bT,b15,b25; const double lT=level(T,bT),l15=level(1.5*T,b15),l25=strict?level(2.5*T,b25):1.;
            if(lT<=0 || l15<floor*lT || (strict && l25<floor*lT) || any(T/2)<floorHalf*lT) continue;
            const double ph15=std::atan2(si52_[b15],sr52_[b15]);
            double c=pk[p].ph/2; const double d0=ph15-3*c,d1=ph15-3*(c+kPi);
            if(std::abs(std::atan2(std::sin(d1),std::cos(d1)))<std::abs(std::atan2(std::sin(d0),std::cos(d0)))) c+=kPi;
            pk[p].f=T/2; pk[p].ph=c; pk[p].modulation=ModulationFit{}; pk[p].family=AmFamily52{}; changed=true;
        }
        if(changed) {
            std::sort(pk,pk+np,[](const Peak& a,const Peak& b){return a.f<b.f;});
            int nk2=0;
            for(int p=0;p<np;++p) {
                bool own=false;
                for(int q=0;q<nk2;++q) {
                    const double n=std::nearbyint(pk[p].f/pk[q].f);
                    if(n>=2 && n<=5 && std::abs(pk[p].f-n*pk[q].f)<=std::max(1.5,.015*pk[p].f)) own=true;
                }
                if(!own) pk[nk2++]=pk[p];
            }
            np=nk2;
        }
    }
    const int64_t centre=s0+kPvN+kRtShift;
    int poly=0; for(int p=0;p<np;++p) if(pk[p].a>=.25*am) ++poly;
    // Study 3 C6: the percussive layer's polyphony mute is decided on the causal HPSS harmonic part, as without C6
    if((stageFlags_&(StageAnalysisProminence|StageCausalProminence)) && hpssLookahead()==0) poly=polyCausal52(s0);
    // Unvalidated scene labels are diagnostics only. Fit residual is not a buzz
    // score; AM sidebands may look like several independent bass components.
    bool unresolved=false;
    for(int p=0;p<np;++p) if(pk[p].a>=.25*am && pk[p].res>-15) unresolved=true;
    observeScene(percEnv52_>2*harmEnv52_ ? VB_SCENE_TRANSIENT :
                 (poly>=2 || unresolved) ? VB_SCENE_COMPLEX : VB_SCENE_STEADY);
    // Study 3 diagnostic (host flag 524288): the polyphony mute of the percussive layer is left off
    for(int g=0;g<kPvH;++g) polyT52_[(centre+g)&(kRing-1)]=poly>=2 && !(stageFlags_&StageNoPolyMute) ? 0 : 1;
    // research modes 5/6 (set aside, research/p1pp/2026-10-26-v03): the fit guard of mode 4 acts only around an impact (percussive envelope above a quarter of the
    // harmonic one, held 24 hops = 128 ms; genuine tonal onsets were 16-27 dB below, impact births within 6 dB); tones that were playing when the impact began are remembered so
    // that the same tone found again after the impact resumes at once instead of waiting for a clean fit.
    constexpr double kImpactCtxRatio=.25;
    const double kHistoryDb=histDbResearch_;
    const double kSteadyA=steadyA52_; const int kSteadyHops=steadyHops52_;
    const bool v03=p1PlusProfile_ && (p1PlusFlags_&6)==6 && (p1ppImpactMode_==5 || p1ppImpactMode_==6);
    if(v03) {
        // mode 5: percussive envelope above a quarter of the harmonic one; mode 6: a percussive spike (above four
        // times its own slow average, about 0.34 s) that is not negligible next to the harmonic part
        const double slow=percSlow52_;
        percSlow52_+=(percEnv52_-percSlow52_)/64.;
        const bool impact=p1ppImpactMode_==5 ? percEnv52_>kImpactCtxRatio*harmEnv52_
                                             : percEnv52_>4*slow+1e-15 && percEnv52_>.05*harmEnv52_;
        if(impact) {
            if(impactCtx52_<=0) {
                preImpactN52_=0;
                for(int t=0;t<nt52_ && preImpactN52_<12;++t)
                    if(tr52_[t].fade>=.5 && tr52_[t].missing==0) preImpactF52_[preImpactN52_++]=tr52_[t].f;
            }
            impactCtx52_=impactHold52_;
        } else if(impactCtx52_>0) --impactCtx52_;
    }
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
        auto q=pk[p]; int best=-1;
        if(stageFlags_&StageGlobalTrack) best=global[p];
        else for(int t=0;t<nt52_;++t) if(!used[t] && (!protectIdentity || tr52_[t].protection.allows(q.f)) &&
            std::abs(tr52_[t].f-q.f)<.1*q.f &&
            (best<0 || std::abs(tr52_[t].f-q.f)<std::abs(tr52_[best].f-q.f))) best=t;
        // Require current evidence only until the track first earns permission.
        // A valid modulation model remains accepted by its own residual.
        // mode 5: a new tone within 3 % of one that was playing when the impact began is that tone again
        bool resumed=false;
        if(v03 && p1ppImpactMode_==5 && impactCtx52_>0 && best<0)
            for(int j=0;j<preImpactN52_;++j) if(std::abs(preImpactF52_[j]-q.f)<=.03*preImpactF52_[j]) resumed=true;
        // mode 7: no guard for a tone with real stationary history before the onset (history residual between
        // -200, the "no history" value, and -6 dB): the guard is for tracks whose only support is missing history.
        const bool history=p1ppImpactMode_==7 && !q.modulation.valid && q.res>-199 && q.res<=kHistoryDb;
        // mode 8: an unconfirmed track whose frequency held within 1 % and whose amplitude did not fall for three
        // hops, and which is at least 0.4 of the strongest peak of the hop, is a steady tone (a note starting, a
        // tone found again after an impact), not a weak partial of an impact: the guard lets it go. Its own
        // stationary fit (as in P1+) still decides; if that passes it starts at full strength, as mode 4 recovers.
        int steady=0;
        if(p1ppImpactMode_==8 && best>=0 && tr52_[best].fade<1e-6) {
            const auto& prev=tr52_[best];
            bool held=std::abs(q.f-prev.f)<=.01*prev.f;
            if(v04 && (p1ppV04_&2)) {
                // v0.4 bit 2: steady = the measured phase lands where the phase vocoder predicts it from the last
                // hop (a tone keeps its phase advance even while an impact disturbs its amplitude)
                const double pred=prev.phi+kPi*(prev.f+q.f)*16/3000;
                held=held && std::abs(std::remainder(q.ph-pred,2*kPi))<=.5;
            } else held=held && q.a>=kSteadyA*prev.a;
            steady=held ? prev.steadyHops+1 : 0;
        }
        const bool strongEnough=(v04 && (p1ppV04_&4)) || q.a>=releaseStrength52_*am;
        // v0.4 bit 8: a birth within 5 % of where a now-ended track was confirmed in the last 250 ms (47 hops) is
        // that track again
        bool inherited=false;
        if(v04 && (p1ppV04_&8) && best<0)
            for(int g=0;g<graveN52_;++g) if(hop52_-graveHop52_[g]<=47 && std::abs(grave52_[g]-q.f)<=.05*grave52_[g]) {
                inherited=true; graveHop52_[g]=-1000; break;
            }
        // ... or near where a track still fading out (pulled away, not yet ended) was confirmed
        if(v04 && (p1ppV04_&8) && best<0 && !inherited)
            for(int t=0;t<nt52_;++t) if(tr52_[t].fade<.5 && hop52_-tr52_[t].confHop<=47 && tr52_[t].confHops>=56 &&
                                        std::abs(tr52_[t].confF-q.f)<=.05*tr52_[t].confF) { inherited=true; break; }
        if(best>=0 && tr52_[best].inherited && tr52_[best].fade<1e-6) inherited=true;  // stays released until confirmed
        const bool released=p1ppImpactMode_==8 && ((steady>=kSteadyHops && strongEnough) || inherited);
        const bool guard=p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_>=2 && !history && !released &&
            ((p1ppImpactMode_!=5 && p1ppImpactMode_!=6) || (impactCtx52_>0 && !resumed));
        const double ownRes=q.res;
        if(guard && !q.modulation.valid && (best<0 || tr52_[best].fade<1e-6))
            q.res=std::max(q.res,q.raw);
        Track52 tr; tr.f=q.f; tr.phi=q.ph; tr.a=q.a; tr.strong=q.a>=.7*am;
        // v0.4 bit 16: held back only by the guard (its own fit passes): still emit what the input already has at k f
        tr.guarded=v04 && (p1ppV04_&16) && q.res>-15 && ownRes<=-15;
        if(best>=0) {
            used[best]=true; const auto& prev=tr52_[best];
            // Held tracks already advance phi once on each missing hop below.
            const double pred=prev.phi+kPi*(prev.f+q.f)*16/3000;
            tr.phi=q.ph+2*kPi*std::nearbyint((pred-q.ph)/(2*kPi));
            std::copy(prev.off,prev.off+7,tr.off); tr.fade=prev.fade; tr.r4Share=prev.r4Share;
            tr.impactRecoveryPending=prev.impactRecoveryPending;
            tr.steadyHops=steady;
            tr.confF=prev.confF; tr.confHop=prev.confHop; tr.confHops=prev.confHops; tr.inherited=inherited;
            tr.pendN=prev.pendN;
            for(int j=0;j<prev.pendN;++j) {
                std::copy(prev.pend[j],prev.pend[j]+32,tr.pend[j]); tr.pendNominal[j]=prev.pendNominal[j]; tr.pendCentre[j]=prev.pendCentre[j]; }
            // only the guard is lifted: the track's own stationary fit must still pass, as in P1+ (a noise
            // partial with a steady peak but a poor fit stays out)
            if(released && prev.fade<1e-6 && q.res<=-15) { tr.fade=1.; tr.impactRecoveryPending=false; }
            tr.id=prev.id; tr.age=prev.age+1; tr.dfdt=(q.f-prev.f)*kFsd/(kPvH*(prev.missing+1));
            if(protectIdentity) {tr.protection=prev.protection;tr.protection.observe(q.f);}
            std::copy(std::begin(prev.permission),std::end(prev.permission),std::begin(tr.permission));
            if(stageFlags_&StageOscillator) tr.oscillator=prev.oscillator;
            tr.life=continuity_.enabled?std::min(1.,prev.life+1./std::max(1,continuity_.attack)):1.;
            // Developer release longer than the model: a tracked partial's amplitude falls no faster than the release
            // (the analysis window alone would end it about as fast as the music).
            if(dev_.releaseHops>DevVoicing::kReleaseHops)
                tr.a=std::max(q.a,prev.a*std::exp(-1./std::max(1,dev_.releaseHops)));
            if(stageFlags_&StageGlobalTrack) tr.prediction=prev.prediction;
        } else {
            // Resultant R1 keeps kPsi at birth: the onset (where the percussive layer, which keeps kPsi, overlaps the
            // tracks) has the unmodified shape, and the slew below moves the offsets to the crest-optimal ones
            std::copy(vbt::kPsi,vbt::kPsi+7,tr.off); tr.fade=q.res<=-15 ? 1 : 0; tr.r4Share=tr.fade;
            tr.impactRecoveryPending=guard && p1ppImpactMode_>=4 && q.res>-15;
            if(resumed) tr.fade=1;
            tr.id=++nextTrackId_; tr.age=1;
            if(protectIdentity) tr.protection.observe(q.f);
        }
        // A track admitted after quarantine should begin like any other valid
        // birth. Otherwise a fake slow attack survives into a recovered tone.
        if(p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_==3 &&
           best>=0 && tr52_[best].fade<1e-6 && q.res<=-15)
            tr.fade=1.;
        if(p1PlusProfile_ && (p1PlusFlags_&6)==6 && p1ppImpactMode_>=4 &&
           tr.impactRecoveryPending && q.raw<=-15 && q.res<=-15) {
            tr.fade=1.;tr.impactRecoveryPending=false;
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
        if(stageFlags_&StageReentrySlow) {
            // Resultant R4-L v2: the share follows the fit like fade, falling within ~10 ms, returning over the tau
            const double target=q.res>-15?0.:1.,tau=target<tr.r4Share?10.:r4ReentryTau52_;
            tr.r4Share+=(target-tr.r4Share)*(1-std::exp(-1000.*kPvH/kFsd/tau));
        }
        if(best<0) tr.inherited=inherited;
        if(tr.fade>=.5) { tr.confF=tr.f; tr.confHop=hop52_; ++tr.confHops; }
        if(gen_.envelope) {
            // S1: one envelope per harmonic. A lost (not onset-ended) track within 3% of this
            // peak is the same partial under another id: hand its envelopes over, render it once.
            for(int t=0;t<nt52_;++t) if(!used[t] && t!=best && !tr52_[t].fastEnding &&
                                         std::abs(tr52_[t].f-q.f)<.03*q.f) {
                used[t]=true;
                if(best<0 && tr.age==1) {tr.id=tr52_[t].id; tr.age=tr52_[t].age+1;} // trace continuity only
                for(int k=0;k<7;++k) tr.permission[k].value=std::max(tr.permission[k].value,tr52_[t].permission[k].value);
            }
        }
        traceTrack52(p,tr,best>=0?HarmonicTrace::Tracked:HarmonicTrace::Birth,q.res>-15?HarmonicTrace::Fit:0);
        if(v04 && (p1ppV04_&32)) {
            // v0.4 bit 32: the layer is read outputDefer() samples late, so what a guarded track would have played can
            // still be put back once the track is released. Only samples not yet read are written.
            const bool pending=q.res>-15 && ownRes<=-15 && !q.modulation.valid;
            const bool releasedNow=best>=0 && tr52_[best].fade<1e-6 && tr.fade>.99;
            if(pending) {
                Track52 copy=tr; copy.fade=1; copy.guarded=false;
                double g2[32]={},a2=0;
                renderTrack52(copy,src,ns,true,false,HarmonicTrace::kTracks,g2,a2);
                if(tr.pendN==kDeferHops) {
                    for(int j=1;j<kDeferHops;++j) {
                        std::copy(tr.pend[j],tr.pend[j]+32,tr.pend[j-1]); tr.pendNominal[j-1]=tr.pendNominal[j]; tr.pendCentre[j-1]=tr.pendCentre[j]; }
                    --tr.pendN;
                }
                std::copy(g2,g2+32,tr.pend[tr.pendN]); tr.pendNominal[tr.pendN]=a2; tr.pendCentre[tr.pendN]=centre; ++tr.pendN;
            } else {
                if(releasedNow) {
                    const int64_t unread=static_cast<int64_t>(i_)-outputDefer();
                    for(int j=0;j<tr.pendN;++j) for(int g=0;g<32;++g) {
                        const int64_t at=tr.pendCentre[j]-16+g; if(at<unread) continue;
                        const int slot=at&(kRing-1);
                        pvOut_[slot]+=tr.pend[j][g]*gw_[g]; pvApv_[slot]+=tr.pendNominal[j]*gw_[g];
                    }
                }
                tr.pendN=0;
            }
        }
        if(!resultantOn_) renderTrack52(tr,src,ns,true,false,p,grain,agrain);
        next[p]=tr;
    }
    int lost=0,traceSlot=np;
    // S1: when capacity runs out, the quietest lost tracks are the ones omitted.
    int order[12]; for(int t=0;t<nt52_;++t) order[t]=t;
    // Stable insertion sort (at most 12 entries): same order as std::stable_sort, which may allocate a buffer.
    if(gen_.envelope) for(int x=1;x<nt52_;++x) {
        const int v=order[x]; const double key=tr52_[v].a*tr52_[v].envPeak; int y=x;
        for(;y>0 && key>tr52_[order[y-1]].a*tr52_[order[y-1]].envPeak;--y) order[y]=order[y-1];
        order[y]=v;
    }
    for(int oi=0;oi<nt52_;++oi) if(!used[order[oi]]) {
        const int t=order[oi];
        ++lost; auto tr=tr52_[t]; ++tr.age; ++tr.missing;
        if(protectIdentity) tr.protection.missing();
        if(!continuity_.enabled && !(stageFlags_&StageOscillator)) {
            traceTrack52(np+lost-1,tr,HarmonicTrace::End,HarmonicTrace::Lost); continue;
        }
        const bool bornCut=!gen_.envelope?born:gen_.onsetMode==0?born:gen_.onsetMode==1?(born && ampOnset):false;
        // R01: measure ID protection separately from the lifespan of a
        // *missing* pre-impact tone. Bit 64 alone uses the original immediate
        // born-cut (A3). Bits 128/256 opt into 4/8 extra hops of grace
        // (4, 8, or 12 total); expiry triggers the *original* fast-release
        // rather than converting an old tone into an unbounded tail.
        const int grace=((p1ppV04_&128)?4:0)+((p1ppV04_&256)?8:0);
        if(protectIdentity && grace>0 && tr.protection.lockHops>0 && bornCut)
            tr.protection.pendingBornCut=true;
        const bool fast=tr.fastEnding || (grace>0 && tr.protection.pendingBornCut
                                        ? tr.missing>grace : bornCut);
        tr.fastEnding=fast;
        tr.phi+=2*kPi*tr.f*kPvH/kFsd;
        if(fast || tr.missing>continuity_.hold)
            tr.life=std::max(0.,tr.life-1./std::max(1,fast?continuity_.fastRelease:continuity_.release));
        if(!continuity_.enabled) tr.life=0;
        if(tr.life<1e-12) tr.life=0;
        if(gen_.envelope) tr.life=1;
        const int state=tr.life<=0?HarmonicTrace::End:(fast || tr.missing>continuity_.hold?HarmonicTrace::Release:HarmonicTrace::Held);
        if(nextCount>=12) {
            if(harmonicCapture_) harmonicTrace_.data[21]+=1;
            grave52(tr); continue;
        }
        const int traceIndex=traceSlot++;
        if(harmonicCapture_ && traceIndex>=HarmonicTrace::kTracks) harmonicTrace_.data[21]+=1;
        traceTrack52(traceIndex,tr,state,HarmonicTrace::Lost);
        if(tr.life>0 || (stageFlags_&StageOscillator)) {
            if(!resultantOn_) renderTrack52(tr,src,ns,false,fast,traceIndex,grain,agrain);
            if(gen_.envelope && tr.envPeak<1e-2) tr.life=0;
            if(tr.life>0) next[nextCount++]=tr; else grave52(tr);
        }
    }
    if(harmonicCapture_) {
        auto* h=harmonicTrace_.data; h[11]=static_cast<float>(np); h[12]=static_cast<float>(nextCount-np);
        h[14]=static_cast<float>(am); h[22]=static_cast<float>(lost);
        if(h[21]>0) h[13]=static_cast<float>(static_cast<int>(h[13])|HarmonicTrace::Capacity);
        double power=0; for(double v:grain) power+=v*v; h[20]=static_cast<float>(std::sqrt(power/32));
    }
    std::copy(next,next+nextCount,tr52_); nt52_=nextCount;
    if(tape_) trackTape52();
    ++hop52_;
    if(histCount_==11) {
        for(int h=0;h<10;++h) { std::copy(hist52_[h+1],hist52_[h+1]+6,hist52_[h]); histN52_[h]=histN52_[h+1]; }
        --histCount_;
    }
    int n=0; for(int p=0;p<np;++p) if(tr52_[p].strong) hist52_[histCount_][n++]=tr52_[p].f;
    histN52_[histCount_++]=n;
    if(!resultantOn_) addGrain52(centre,grain,agrain);
    if(devMeter_) devEndFrame();
    if(resultantOn_) resultant_.hop(*this,true,src,ns);   // after the hop counter and the track list: the core reads both
}

struct VbHpv::TrackTape52 {
    struct Hop { int n=0; Track52 tr[12]; };
    std::vector<Hop> hops;
    long long recorded=0, replaced=0, added=0, kept=0, dupIds=0, overflow=0, windowHops=0;
};
VbHpv::TrackTape52* VbHpv::createTrackTape(int hops) {
    auto* t=new TrackTape52; t->hops.resize(static_cast<size_t>(hops)); return t;
}
void VbHpv::destroyTrackTape(TrackTape52* t) { delete t; }
int VbHpv::trackTapeStats(const TrackTape52* t,long long* out,int n) {
    if(!t || !out || n<7) return -1;
    const long long v[7]={t->recorded,t->replaced,t->added,t->kept,t->dupIds,t->overflow,t->windowHops};
    std::copy(v,v+7,out); return 7;
}
// Study 1 B3 (host only): record the track list after this hop, or replace the bed-corresponding tracks by the
// recorded bed-only state inside the window. Runs after the hop's grains were rendered, so it acts from the next hop.
void VbHpv::trackTape52() {
    auto& t=*tape_; const int64_t h=hop52_;
    if(tapeMode_==1) {
        if(h<static_cast<int64_t>(t.hops.size())) {
            auto& s=t.hops[static_cast<size_t>(h)]; s.n=nt52_; std::copy(tr52_,tr52_+nt52_,s.tr); t.recorded=h+1;
        } else ++t.overflow;
        return;
    }
    if(tapeMode_!=2 || h<tapeStart_ || h>=tapeEnd_ || h>=t.recorded) return;
    ++t.windowHops;
    const auto& s=t.hops[static_cast<size_t>(h)]; bool taken[12]={};
    for(int k=0;k<nt52_;++k) {
        int best=-1; double bd=1e300;
        for(int j=0;j<s.n;++j) if(!taken[j]) {
            const double d=std::abs(s.tr[j].f-tr52_[k].f);
            if(d<=tapeTol_*s.tr[j].f && d<bd) {bd=d;best=j;}
        }
        // the mixture's track slot keeps its own id (ids of the two renders are allocated independently)
        if(best>=0) {const uint32_t id=tr52_[k].id; tr52_[k]=s.tr[best]; tr52_[k].id=id; taken[best]=true; ++t.replaced;}
        else ++t.kept;
    }
    for(int j=0;j<s.n;++j) if(!taken[j]) {
        // an added bed track is marked so its id cannot collide with the mixture's ids
        if(nt52_<12) {tr52_[nt52_]=s.tr[j]; tr52_[nt52_++].id|=0x80000000u; ++t.added;} else ++t.overflow;
    }
    for(int a=0;a<nt52_;++a) for(int b=a+1;b<nt52_;++b) if(tr52_[a].id==tr52_[b].id) ++t.dupIds;
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
    if(stageFlags_&StageNominalPower) nominalAmplitude=std::sqrt(nominalAmplitude);
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
    const int future=hpssLookahead(),hpssDelay=191+future;
    md52_[slot]=d; md2_52_[slot]=i>=hpssDelay?md52_[(i-hpssDelay)&(kRing-1)]:0;
    double b=d; for(auto& s:band_) b=s.tick(b); bRing_[slot]=b;
    if((i+1)%16==0) hpssFrame();
    double bh=0,bp=0,bhA=0;
    if(i>=hpssDelay) {
        const int64_t t=i-hpssDelay; const int s=t&(kRing-1); const double ws=wsumHp_[t%16];
        bh=olaH_[s]/ws; bp=olaP_[s]/ws; bhA=olaHA_[s]/ws; olaH_[s]=olaP_[s]=olaHA_[s]=0;
    }
    const double originalH=bh,originalP=bp,bandDelayed=i>=hpssDelay?bRing_[(i-hpssDelay)&(kRing-1)]:0.;
    detailRing52_[slot]=bandDelayed;
    // Study 3 C6: the vocoder spectrum and the music envelope read the C5-masked harmonic part; the percussive
    // layer, its gate and the harmonic envelope keep the causal HPSS
    // C5: the output and the analysis use the C5 mask; olaHA_ (bhA) is then the causal part, for the polyphony count
    bool analysisH=(stageFlags_&StageAnalysisProminence) && future==0;
    const bool causalA=(stageFlags_&StageCausalProminence) && future==0;
    if(stageFlags_&StageBypassHpss) {bh=bandDelayed;bp=0.;analysisH=false;}
    if(inject_.active(StageInject52::InjectHpss,i)) {bh=inject_.bh[i];bp=inject_.bp[i];analysisH=false;}
    const double bhAnalysis=analysisH?bhA:bh;
    double hr,hi,pr,pi; hilH_.tick(bhAnalysis,hr,hi); hilP_.tick(bp,pr,pi);
    bhRing_[slot]=bhAnalysis; aRing_[slot]=std::hypot(hr,hi); bhCausal52_[slot]=causalA?bhA:bh;
    const double att=std::exp(-1./6),rel=std::exp(-1./120);
    const double ep=bp*bp,eh=bh*bh;
    double a=ep>percEnv52_?att:rel; percEnv52_=a*percEnv52_+(1-a)*ep;
    a=eh>harmEnv52_?att:rel; harmEnv52_=a*harmEnv52_+(1-a)*eh;
    const double gate=clampv((10*std::log10((percEnv52_+1e-20)/(harmEnv52_+1e-20))+3)/6,0.,1.);
    if(!gen_.bursts) hpRing_[slot]=bandLayer(pr,pi)*gate;
    else {
        // S2 research: onsets of the low band (analytic power of H+P, so no 2f ripple),
        // burst written kBurstDelay samples late; the hp read below lags 207 samples.
        bandLayer(pr,pi);
        genAmpRing_[slot]=std::hypot(pr,pi)*lastGk_*gate; genPhaseRing_[slot]=std::atan2(pi,pr);
        const double e=(hr+pr)*(hr+pr)+(hi+pi)*(hi+pi);
        const double c=std::exp(-1./((e>genFastE_?.001:.010)*kFsd)),sl=std::exp(-1./(.150*kFsd));
        genFastE_=c*genFastE_+(1-c)*e; genSlowE_=sl*genSlowE_+(1-sl)*e;
        const bool onset=10*std::log10((genFastE_+1e-30)/(genSlowE_+1e-30))>gen_.onsetDb &&
            static_cast<int64_t>(i)-genLastOnset_>=static_cast<int64_t>(gen_.refractoryMs*1e-3*kFsd);
        if(onset) genLastOnset_=static_cast<int64_t>(i);
        genOnsetRing_[slot]=onset;
        const int64_t j=static_cast<int64_t>(i)-kBurstDelay;
        if(j>=0) hpRing_[j&(kRing-1)]=burstSample52(j);
    }
    if(i>=383+future && (i-383-future)%16==0) pvFrame52();
    // Exact nearest-edge centred closing, evaluated with the existing vocoder delay.
    if(i>=90) {
        double m=0; for(int64_t j=std::max<int64_t>(0,i-180);j<=i;++j) m=std::max(m,aRing_[j&(kRing-1)]);
        max52_[(i-90)&(kRing-1)]=m;
    }
    const int defer=outputDefer();
    double ac=0;
    if(i>=207+defer) {
        const int64_t t=i-207-defer; ac=1e30;
        for(int64_t j=std::max<int64_t>(0,t-90);j<=t+90;++j) ac=std::min(ac,max52_[j&(kRing-1)]);
    }
    double out=0,apv=0;
    if(i>=defer) { if(resultantOn_) out=resultant_.take(i-defer); else takeGrain52(i-defer,out,apv); }
    double as=envA_.tick(ac),ps=envP_.tick(apv);
    if(inject_.active(StageInject52::InjectEnvelope,i)) {as=inject_.as[i];ps=inject_.ps[i];}
    const double gain=apv>0?clampv(as/(ps+1e-9),0.,1.):0;
    const double gainTarget=(familyApplied52_ || detailApplied52_)?1.:0.;
    if(stageFlags_&StageConditionalGain) {
        const double smoothing=std::exp(-1./(gainTarget>conditionalGain52_?60:120));
        conditionalGain52_=smoothing*conditionalGain52_+(1-smoothing)*gainTarget;
    }
    const double selectedGain=(stageFlags_&StageConditionalGain)?gain+(1-gain)*conditionalGain52_:gain;
    double appliedGain=(stageFlags_&StageBypassGain)?(apv>0?1.:0.):selectedGain;
    if(gen_.envelope && gen_.gainReleaseMs>0) {
        // S1 research: the envelope-imposition gain may fall no faster than the harmonic release.
        const double c=std::exp(-1./((appliedGain>genGain_?.003:gen_.gainReleaseMs*1e-3)*kFsd));
        genGain_=c*genGain_+(1-c)*appliedGain; appliedGain=genGain_;
    } else if(dev_.releaseHops!=DevVoicing::kReleaseHops) {
        // Developer release: the envelope-imposition gain (which follows the music's own low band) may fall no
        // faster than the release, so the layer can outlast the dry note; rises stay fast (3 ms).
        const double rel=dev_.releaseHops*static_cast<double>(kPvH)/kFsd;
        const double c=std::exp(-1./((appliedGain>devGain_?.003:rel)*kFsd));
        devGain_=c*devGain_+(1-c)*appliedGain; appliedGain=devGain_;
    }
    if(resultantOn_) appliedGain=1.;   // Resultant core: the layer's level is the input's own, no envelope imposition
    const int pslot=(i-defer)&(kRing-1);
    const double target=i>=defer?polyT52_[pslot]:1.; if(i>=defer) polyT52_[pslot]=1;
    a=std::exp(-1./(target<poly52_?60:600)); poly52_=a*poly52_+(1-a)*target;
    const double hp=i>=207+defer?hpRing_[(i-207-defer)&(kRing-1)]*poly52_:0;
    // Developer mode "지속음 / 타격음 비율": path gains, only while one of them differs from 0 dB.
    double preFilter=devMix_?out*appliedGain*devSustLin_+(tonalOnly_?0:hp)*devPercLin_:out*appliedGain+(tonalOnly_?0:hp);
    if(dev_.attackHops>DevVoicing::kAttackHops) {
        // Developer attack longer than the model: the layer's level (40 ms mean square) may rise no faster than the
        // attack; it follows any fall at once, so a held note is untouched (gain 1) and only onsets are softened.
        const double e=preFilter*preFilter;
        devAttM_+=(e-devAttM_)*(1-std::exp(-1./(.040*kFsd)));
        if(devAttM_<=devAttS_) devAttS_=devAttM_;
        else devAttS_+=(devAttM_-devAttS_)*(1-std::exp(-1./(dev_.attackHops*static_cast<double>(kPvH))));
        if(devAttM_>1e-30) preFilter*=std::sqrt(devAttS_/devAttM_);
        if(devAttM_<1e-30) devAttM_=devAttS_=0;
    }
    if(devMeter_) devSnap_.gain=appliedGain;
    double y=preFilter;for(auto& s:out_) y=s.tick(y);
    if(resultantOn_ && resultant_.hpOn()) y=resultant_.hpTick(y);   // Resultant 19.7: layer high-pass in series with the output band filter
    if(harmonicReady_) {
        harmonicTrace_.data[17]=static_cast<float>(gen_.envelope?appliedGain:gain); harmonicTrace_.data[18]=static_cast<float>(poly52_);
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
double VbHpv::burstSample52(int64_t j) {
    const int s=j&(kRing-1);
    if(genOnsetRing_[s]) {
        double amp=0;
        for(int64_t q=j;q<=static_cast<int64_t>(i_);++q) amp=std::max(amp,genAmpRing_[q&(kRing-1)]);
        // Harmonic composition from the current P1 track nearest the percussive frequency.
        double f=lastFc_,best=.2*lastFc_;
        for(int t=0;t<nt52_;++t) if(tr52_[t].life>0 && std::abs(tr52_[t].f-lastFc_)<best) {best=std::abs(tr52_[t].f-lastFc_);f=tr52_[t].f;}
        f=clampv(f,params.fLoHz,dev_.tableScale!=1.0?params.fHiHz*dev_.tableScale:params.fHiHz);
        auto& v=(!bursts_[0].on || (bursts_[1].on && bursts_[0].start>bursts_[1].start))?bursts_[0]:bursts_[1];
        double g; lookup(f,v.w,g);
        // Resultant R4: the register corner applies to bursts only without the onset protection (bursts are onsets)
        const double corner=(stageFlags_&StageRegisterCorner) && !(stageFlags_&StageOnsetProtect)?std::max(220.,3*f):220.;
        for(int k=2;k<=8;++k) if(gentle_ && k*f>corner) {
            const double g12=std::pow(10.,-12*std::log2(k*f/corner)/20);
            v.w[k-2]*=g12+research_.upperBlend*(g12*g12-g12);
        }
        v.amp=amp; v.phi=genPhaseRing_[s]; v.f=f; v.start=j; v.on=true;
    }
    double y=0;
    const double ta=gen_.burstAttackMs*1e-3,td=gen_.burstDecayMs*1e-3,tau=td/std::log(100.),taper=.010;
    for(auto& v:bursts_) if(v.on) {
        const double t=static_cast<double>(j-v.start)/kFsd;
        if(t>td+taper) {v.on=false;continue;}
        double env=t<ta?t/ta:std::exp(-(t-ta)/tau);
        if(t>td) env*=1-(t-td)/taper;
        const double ph=v.phi+2*kPi*v.f*t;
        double sum=0; for(int k=2;k<=8;++k) sum+=v.w[k-2]*std::cos(k*ph+vbt::kPsi[k-2]);
        y+=v.amp*env*sum;
    }
    return y;
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
    fftHalf();
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

// Resultant core (algorithm 15): defined here, in this translation unit, to use the helpers above and the privates of VbHpv
#include "pvb_resultant.inc"



#pragma once
#include "pvb_vb_modulation.h"
namespace pvb {
struct AmFamily52 {
    bool valid=false;
    double carrier=0,rate=0,meanAmplitude=0,phase=0,cosine=0,sine=0,residual=0,coherence=0,qrRatio=0;
    std::complex<double> observed[3]={},sourceModulation={};
    void advance(double dt) {
        for(int j=0;j<3;++j) observed[j]*=std::polar(1.,2*modulation::Pi*(carrier+(j-1)*rate)*dt);
        sourceModulation*=std::polar(1.,2*modulation::Pi*rate*dt);
        const auto z=std::complex<double>(cosine,-sine)*std::polar(1.,2*modulation::Pi*rate*dt);
        cosine=z.real();sine=-z.imag();phase=std::arg(observed[1]);
    }
    ModulationFit trajectory() const {
        ModulationFit m;m.valid=valid;m.carrier=m.frequency=carrier;m.phase=phase;m.residual=residual;m.qrDiagonalRatio=qrRatio;
        const double w=2*modulation::Pi*rate,h=modulation::Half;
        const auto z=std::complex<double>(cosine,-sine),p=std::polar(meanAmplitude,phase);
        auto derivative=z;double factorial=1,power=1;
        for(int j=0;j<5;++j) {
            if(j) {derivative*=std::complex<double>(0,w);factorial*=j;power*=h;}
            m.z[j]=p*((j==0?1.:0.)+derivative.real())*power/factorial;
        }
        m.amplitude=meanAmplitude*(1+cosine);m.amplitudeSlope=meanAmplitude*w*sine;return m;
    }
    void local(double t,double& ratio,double& phaseDelta) const {
        const double p=2*modulation::Pi*rate*t;
        ratio=(1+cosine*std::cos(p)+sine*std::sin(p))/(1+cosine);
        phaseDelta=2*modulation::Pi*carrier*t;
    }
};
namespace amfamily {
constexpr int N=384,Columns=6;
inline std::complex<double> bandResponse(double frequency,const double* sos) {
    const auto z=std::polar(1.,-2*modulation::Pi*frequency/modulation::Fs);std::complex<double> h=1.;
    for(int j=0;j<4;++j) {const double* b=sos+6*j;h*=(b[0]+b[1]*z+b[2]*z*z)/(1.+b[4]*z+b[5]*z*z);}
    return h;
}
struct Solver {
    double q[Columns][N],r[Columns][Columns],target[N],time[N],weight[N],energy=0;
    explicit Solver(const double* x) {
        for(int n=0;n<N;++n) {time[n]=(n-N/2)/modulation::Fs;weight[n]=std::sqrt(.5-.5*std::cos(2*modulation::Pi*n/N));target[n]=x[n]*weight[n];energy+=target[n]*target[n];}
    }
    bool solve(double f,double rate,double* error,std::complex<double>* z,double& ratio) {
        double p[Columns]={},c[Columns]={};
        for(int j=0;j<Columns;++j) for(int k=0;k<Columns;++k) r[j][k]=0;
        for(int n=0;n<N;++n) for(int j=0;j<3;++j) {
            const double phase=2*modulation::Pi*(f+(j-1)*rate)*time[n];
            q[j][n]=std::cos(phase)*weight[n];q[j+3][n]=std::sin(phase)*weight[n];
        }
        double low=1e100,high=0;
        for(int j=0;j<Columns;++j) {
            for(int pass=0;pass<2;++pass) for(int k=0;k<j;++k) {
                double dot=0;for(int n=0;n<N;++n) dot+=q[k][n]*q[j][n];r[k][j]+=dot;
                for(int n=0;n<N;++n) q[j][n]-=dot*q[k][n];
            }
            double norm=0;for(int n=0;n<N;++n) norm+=q[j][n]*q[j][n];norm=std::sqrt(norm);
            if(!std::isfinite(norm) || norm<1e-10) return false;
            r[j][j]=norm;low=std::min(low,norm);high=std::max(high,norm);
            for(int n=0;n<N;++n) {q[j][n]/=norm;p[j]+=q[j][n]*target[n];}
        }
        for(int j=Columns-1;j>=0;--j) {double v=p[j];for(int k=j+1;k<Columns;++k) v-=r[j][k]*c[k];c[j]=v/r[j][j];}
        for(int j=0;j<3;++j) z[j]={c[j],-c[j+3]};
        ratio=high/low;
        for(int n=0;n<N;++n) {double v=-target[n];for(int j=0;j<Columns;++j) v+=q[j][n]*p[j];error[n]=v;}
        return true;
    }
};
inline double power(const double* x) {double sum=0;for(int n=0;n<N;++n) sum+=x[n]*x[n];return sum;}
inline AmFamily52 fit(const double* x,double seed,const double* sos) {
    AmFamily52 m;if(!std::isfinite(seed) || seed<25 || seed>190) return m;
    for(int n=0;n<N;++n) if(!std::isfinite(x[n])) return m;
    Solver solver(x);if(solver.energy<1e-14) return m;
    double e[N],df[N],dr[N],trial[N],ratio=0;std::complex<double> z[3];
    double f=seed,rate=4,best=1e100;
    for(int r=4;r<=24;r+=2) if(solver.solve(seed,r,e,z,ratio)) {const double cost=power(e);if(cost<best) {best=cost;rate=r;}}
    if(best==1e100) return m;
    for(int iteration=0;iteration<7;++iteration) {
        if(!solver.solve(f,rate,e,z,ratio)) return m;
        const double cost=power(e),h=.01;
        if(!solver.solve(f+h,rate,df,z,ratio) || !solver.solve(f,rate+h,dr,z,ratio)) return m;
        double ff=0,rr=0,fr=0,fe=0,re=0;
        for(int n=0;n<N;++n) {
            df[n]=(df[n]-e[n])/h;dr[n]=(dr[n]-e[n])/h;
            ff+=df[n]*df[n];rr+=dr[n]*dr[n];fr+=df[n]*dr[n];fe+=df[n]*e[n];re+=dr[n]*e[n];
        }
        const double det=ff*rr-fr*fr;if(det<1e-24) break;
        double sf=std::max(-.5,std::min(.5,(-rr*fe+fr*re)/det));
        double sr=std::max(-2.,std::min(2.,(fr*fe-ff*re)/det));bool moved=false;
        for(int line=0;line<3;++line) {
            const double nf=std::max(seed-2,std::min(seed+2,f+sf)),nr=std::max(2.,std::min(25.,rate+sr));
            if(solver.solve(nf,nr,trial,z,ratio) && power(trial)<cost) {f=nf;rate=nr;moved=true;break;}
            sf*=.5;sr*=.5;
        }
        if(!moved || (std::abs(sf)<1e-6 && std::abs(sr)<1e-6)) break;
    }
    if(!solver.solve(f,rate,e,z,ratio)) return m;
    m.residual=10*std::log10(std::max(power(e)/solver.energy,1e-30));m.qrRatio=ratio;
    const auto h0=bandResponse(f,sos),hl=bandResponse(f-rate,sos),hh=bandResponse(f+rate,sos);
    if(std::abs(h0)<1e-5 || std::abs(hl)<1e-5 || std::abs(hh)<1e-5 || std::abs(z[1])<1e-9) return m;
    const auto u0=z[1]/h0,lo=(z[0]/hl)/u0,hi=(z[2]/hh)/u0;
    m.coherence=std::abs(hi-std::conj(lo))/std::max(1e-12,std::abs(hi)+std::abs(lo));
    const auto modValue=hi+std::conj(lo);const double depth=std::abs(modValue);
    const double delta=.01;
    const double groupDelay=-std::arg(bandResponse(f+delta,sos)*std::conj(bandResponse(f-delta,sos)))/(4*modulation::Pi*delta);
    m.sourceModulation=modValue;
    const auto delayed=modValue*std::polar(1.,-2*modulation::Pi*rate*groupDelay);
    m.carrier=f;m.rate=rate;m.meanAmplitude=std::abs(z[1]);m.phase=std::arg(z[1]);m.cosine=delayed.real();m.sine=-delayed.imag();
    std::copy(z,z+3,m.observed);
    m.valid=m.residual<=-30 && ratio<1e3 && m.coherence<.1 && depth>=.08 && depth<=.95 && rate>=4 && rate<=24 && f>=25 && f<=190;
    return m;
}
inline double predictionResidual(const AmFamily52& m,const double* x) {
    double error=0,energy=0;
    for(int n=0;n<N;++n) {
        const double t=(n-N/2)/modulation::Fs;double predicted=0;
        for(int j=0;j<3;++j) predicted+=(m.observed[j]*std::polar(1.,2*modulation::Pi*(m.carrier+(j-1)*m.rate)*t)).real();
        const double w=.5-.5*std::cos(2*modulation::Pi*n/N);error+=w*(predicted-x[n])*(predicted-x[n]);energy+=w*x[n]*x[n];
    }
    return 10*std::log10(std::max(error/std::max(energy,1e-30),1e-30));
}
}
}

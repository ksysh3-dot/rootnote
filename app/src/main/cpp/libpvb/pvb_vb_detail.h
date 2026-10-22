#pragma once
#include "pvb_vb_modulation.h"
namespace pvb {
namespace detail {
// D2 initial expert: a32ms complex quadratic envelope around a carrier supplied
// by the128ms structural path. No extra future samples or source-count labels.
constexpr int N=96, Columns=6;
inline ModulationFit fit(const double* x,double carrier,double slope) {
    ModulationFit m;
    if(!std::isfinite(carrier) || !std::isfinite(slope) || carrier<25 || carrier>190 || std::abs(slope)>400) return m;
    constexpr double half=N/(2*modulation::Fs);
    double q[Columns][N],r[Columns][Columns]={},projection[Columns]={},y[N],energy=0,rms=0;
    for(int n=0;n<N;++n) {
        if(!std::isfinite(x[n])) return m;
        const double t=(n-N/2)/modulation::Fs,u=t/half;
        const double weight=std::sqrt(.5-.5*std::cos(2*modulation::Pi*n/N));
        const double phase=2*modulation::Pi*carrier*t+modulation::Pi*slope*t*t;
        const double co=std::cos(phase)*weight,si=std::sin(phase)*weight;
        q[0][n]=co;q[1][n]=co*u;q[2][n]=co*u*u;
        q[3][n]=si;q[4][n]=si*u;q[5][n]=si*u*u;
        y[n]=x[n]*weight;energy+=y[n]*y[n];rms+=x[n]*x[n];
    }
    if(energy<1e-14) return m;
    rms=std::sqrt(rms/N);double low=1e100,high=0;
    for(int j=0;j<Columns;++j) {
        for(int pass=0;pass<2;++pass) for(int k=0;k<j;++k) {
            double dot=0;for(int n=0;n<N;++n) dot+=q[k][n]*q[j][n];
            r[k][j]+=dot;for(int n=0;n<N;++n) q[j][n]-=dot*q[k][n];
        }
        double norm=0;for(int n=0;n<N;++n) norm+=q[j][n]*q[j][n];norm=std::sqrt(norm);
        if(!std::isfinite(norm) || norm<1e-10) return m;
        r[j][j]=norm;low=std::min(low,norm);high=std::max(high,norm);
        for(int n=0;n<N;++n) {q[j][n]/=norm;projection[j]+=q[j][n]*y[n];}
    }
    double c[Columns]={};
    for(int j=Columns-1;j>=0;--j) {
        double v=projection[j];for(int k=j+1;k<Columns;++k) v-=r[j][k]*c[k];c[j]=v/r[j][j];
    }
    const double scale=modulation::Half/half;
    m.z[0]={c[0],-c[3]};m.z[1]=std::complex<double>(c[1],-c[4])*scale;
    m.z[2]=std::complex<double>(c[2],-c[5])*scale*scale;
    if(std::abs(m.z[0])<1e-9) return m;
    const auto rate=m.z[1]/(modulation::Half*m.z[0]);
    const auto curve=2.*m.z[2]/(modulation::Half*modulation::Half*m.z[0])-rate*rate;
    m.carrier=carrier;m.slope=slope;m.amplitude=std::abs(m.z[0]);m.phase=std::arg(m.z[0]);
    m.frequency=carrier+rate.imag()/(2*modulation::Pi);
    m.amplitudeSlope=m.amplitude*rate.real();m.frequencySlope=slope+curve.imag()/(2*modulation::Pi);
    double error=0;
    for(int n=0;n<N;++n) {double v=y[n];for(int j=0;j<Columns;++j) v-=q[j][n]*projection[j];error+=v*v;}
    m.residual=10*std::log10(std::max(error/energy,1e-30));m.qrDiagonalRatio=high/low;
    m.valid=m.residual<=-20 && m.qrDiagonalRatio<1e4 && m.frequency>=25 && m.frequency<=190 &&
        std::abs(m.frequency-carrier)<=5 && std::abs(m.frequencySlope)<=400 && m.amplitude<4*rms;
    return m;
}
}
}

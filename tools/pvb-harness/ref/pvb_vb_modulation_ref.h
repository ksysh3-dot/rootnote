#pragma once
// Frozen copy of the original modulation fit (before the 2026-10-22 speed-up), for fit_equivalence.cpp only.
// Uses pvb::ModulationFit from the current header.
// P1 host research: 128-ms complex polynomial envelope, not source separation.
// Numerical fit acceptance is NOT an instrument/buzz/quality probability.
#include <algorithm>
#include <cmath>
#include <complex>
namespace pvb {
namespace modulation_ref {
constexpr int N=384, Columns=16;
constexpr double Fs=3000., Half=.064, Pi=3.14159265358979323846;
// Modified Gram-Schmidt with two orthogonalization passes. Fixed storage only.
// Diagonal ratio is a numerical guard, NOT the singular-value condition number.
struct Solver {
    double q[Columns][N], r[Columns][Columns], projected[Columns], weight[N], time[N], u[N], y[N];
    double energy=0, rms=0, ratio=0, residual=0;
    explicit Solver(const double* x) {
        for(int n=0;n<N;++n) {
            time[n]=(n-N/2)/Fs;u[n]=time[n]/Half;
            weight[n]=std::sqrt(.5-.5*std::cos(2*Pi*n/N));
            y[n]=x[n]*weight[n];energy+=y[n]*y[n];rms+=x[n]*x[n];
        }
        rms=std::sqrt(rms/N);
    }
    bool solve(double f,double slope,const double* neighbors,int count,double* c) {
        const int cols=10+2*count;
        for(int j=0;j<cols;++j) { projected[j]=0;for(int k=0;k<cols;++k) r[j][k]=0; }
        for(int n=0;n<N;++n) {
            const double ph=2*Pi*f*time[n]+Pi*slope*time[n]*time[n];
            double p=1;const double co=std::cos(ph)*weight[n],si=std::sin(ph)*weight[n];
            for(int j=0;j<5;++j) {q[j][n]=co*p;q[j+5][n]=si*p;p*=u[n];}
            for(int j=0;j<count;++j) {
                const double a=2*Pi*neighbors[j]*time[n];
                q[10+j][n]=std::cos(a)*weight[n];q[10+count+j][n]=std::sin(a)*weight[n];
            }
        }
        double low=1e100,high=0;
        for(int j=0;j<cols;++j) {
            for(int pass=0;pass<2;++pass) for(int k=0;k<j;++k) {
                double dot=0;for(int n=0;n<N;++n) dot+=q[k][n]*q[j][n];
                r[k][j]+=dot;for(int n=0;n<N;++n) q[j][n]-=dot*q[k][n];
            }
            double norm=0;for(int n=0;n<N;++n) norm+=q[j][n]*q[j][n];norm=std::sqrt(norm);
            if(!std::isfinite(norm) || norm<1e-10) return false;
            r[j][j]=norm;low=std::min(low,norm);high=std::max(high,norm);
            for(int n=0;n<N;++n) {q[j][n]/=norm;projected[j]+=q[j][n]*y[n];}
        }
        ratio=high/low;
        for(int j=cols-1;j>=0;--j) {
            double v=projected[j];for(int k=j+1;k<cols;++k) v-=r[j][k]*c[k];c[j]=v/r[j][j];
        }
        double err=0;
        for(int n=0;n<N;++n) {double v=y[n];for(int j=0;j<cols;++j) v-=q[j][n]*projected[j];err+=v*v;}
        residual=10*std::log10(std::max(err/energy,1e-30));return true;
    }
};
inline ModulationFit fit(const double* x,double seed,const double* neighbors=nullptr,int count=0) {
    ModulationFit m; if(!std::isfinite(seed)) return m; m.carrier=seed;count=neighbors?std::max(0,std::min(3,count)):0;
    for(int n=0;n<N;++n) if(!std::isfinite(x[n])) return m;
    Solver s(x);if(s.energy<1e-14 || seed<20 || seed>200) return m;
    double c[Columns]={};
    for(int it=0;it<4;++it) {
        if(!s.solve(m.carrier,m.slope,neighbors,count,c)) return m;
        const std::complex<double> z0(c[0],-c[5]),z1(c[1],-c[6]),z2(c[2],-c[7]);
        if(std::abs(z0)<1e-9) return m;
        const auto rate=z1/(Half*z0),curve=2.*z2/(Half*Half*z0)-rate*rate;
        const double df=std::max(-5.,std::min(5.,rate.imag()/(2*Pi)));
        const double ds=std::max(-100.,std::min(100.,curve.imag()/(2*Pi)));
        m.carrier+=df;m.slope=std::max(-400.,std::min(400.,m.slope+ds));
        if(!(m.carrier>20 && m.carrier<200)) return m;
        if(std::abs(df)<1e-5 && std::abs(ds)<.01) break;
    }
    if(!s.solve(m.carrier,m.slope,neighbors,count,c)) return m;
    for(int j=0;j<5;++j) m.z[j]={c[j],-c[j+5]};
    if(std::abs(m.z[0])<1e-9) return m;
    const auto rate=m.z[1]/(Half*m.z[0]),curve=2.*m.z[2]/(Half*Half*m.z[0])-rate*rate;
    m.amplitude=std::abs(m.z[0]);m.phase=std::arg(m.z[0]);m.frequency=m.carrier+rate.imag()/(2*Pi);
    m.amplitudeSlope=m.amplitude*rate.real();m.frequencySlope=m.slope+curve.imag()/(2*Pi);
    m.residual=s.residual;m.qrDiagonalRatio=s.ratio;
    m.valid=m.residual<=-20 && m.qrDiagonalRatio<1e4 && m.frequency>=25 && m.frequency<=190 && m.amplitude<4*s.rms;
    return m;
}
inline void local(const ModulationFit& m,double t,double& ratio,double& phase) {
    auto z=m.z[4];for(int j=3;j>=0;--j) z=z*(t/Half)+m.z[j];
    ratio=std::max(0.,std::min(3.,std::abs(z)/std::max(1e-12,m.amplitude)));
    phase=2*Pi*m.carrier*t+Pi*m.slope*t*t+std::arg(z/m.z[0]);
}
} // namespace modulation_ref
} // namespace pvb

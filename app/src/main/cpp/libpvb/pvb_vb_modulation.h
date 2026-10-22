#pragma once
// P1 host research: 128-ms complex polynomial envelope, not source separation.
// Numerical fit acceptance is NOT an instrument/buzz/quality probability.
//
// Cost (2026-10-22 profile): this fit runs once per vocoder frame (187.5 per second) and solves the least-squares
// problem 2 to 5 times, so it was about three quarters of the whole engine's CPU time with P1 on. The solver below is
// the same algorithm as before (the same columns in the same order, modified Gram-Schmidt with two passes, the same
// checks), arranged for speed:
//   - the window, time and polynomial axes are one shared table (they never change);
//   - sine and cosine come from fastmath::sincos (no library calls, so the column loops vectorise; within 0.8 ulp);
//   - the neighbour columns do not depend on the carrier or the slope: they are built once per frame, not per solve;
//   - every sum over the 384 samples uses several running partial sums in a fixed order, so the processor can
//     overlap them; sums that share an input are taken in one pass (dotsK, dots2K).
// Only the summation order of those sums differs from the straightforward loops, so results agree to rounding
// (tools/pvb-harness/fit_equivalence.cpp checks this against a frozen copy of the original).
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstring>
#include "pvb_fastmath.h"
#include "pvb_simd.h"
namespace pvb {
struct ModulationFit {
    bool valid=false;
    double frequency=0, amplitude=0, phase=0, amplitudeSlope=0, frequencySlope=0;
    double carrier=0, slope=0, residual=0, qrDiagonalRatio=0;
    std::complex<double> z[5]={};
};
namespace modulation {
constexpr int N=384, Columns=16;
constexpr double Fs=3000., Half=.064, Pi=3.14159265358979323846;

// Window, time and normalised time (u = t / Half) of the 384-sample frame, powers of u and the window moments
// sum(w^2 u^m); computed once.
struct Axes {
    double time[N], u[N], weight[N];
    alignas(64) double upow[9][N];
    double moment[9];
    Axes() {
        for(int n=0;n<N;++n) {
            time[n]=(n-N/2)/Fs;u[n]=time[n]/Half;
            weight[n]=std::sqrt(.5-.5*std::cos(2*Pi*n/N));
        }
        for(int n=0;n<N;++n) { double p=1; for(int m=0;m<9;++m) { upow[m][n]=p; p*=u[n]; } }
        for(int m=0;m<9;++m) { double s=0; for(int n=0;n<N;++n) s+=weight[n]*weight[n]*upow[m][n]; moment[m]=s; }
    }
};
inline const Axes& axes() { static const Axes a; return a; }

// Sums over N samples with eight partial sums (sample n goes to sum n mod 8), combined in a fixed order
// ((s0+s1)+(s2+s3))+((s4+s5)+(s6+s7)): deterministic for a given build. Written with two-lane vectors (pvb_simd.h)
// so they are vectorised on every compiler; lane l of vector j is partial sum 2j+l.
using simd::d2;
inline double sum8(d2 a0,d2 a1,d2 a2,d2 a3) {
    return ((a0[0]+a0[1])+(a1[0]+a1[1]))+((a2[0]+a2[1])+(a3[0]+a3[1]));
}
inline double dotN(const double* __restrict a,const double* __restrict b) {
    d2 s0={0,0},s1={0,0},s2={0,0},s3={0,0};
    for(int n=0;n<N;n+=8) {
        s0+=simd::load(a+n)*simd::load(b+n);s1+=simd::load(a+n+2)*simd::load(b+n+2);
        s2+=simd::load(a+n+4)*simd::load(b+n+4);s3+=simd::load(a+n+6)*simd::load(b+n+6);
    }
    return sum8(s0,s1,s2,s3);
}
// q -= d * k (element by element exactly as before), then returns <next, q>.
inline double axpyDot(double* __restrict q,const double* __restrict k,double d,const double* __restrict next) {
    const d2 dd=simd::splat(d);
    d2 s[4]={{0,0},{0,0},{0,0},{0,0}};
    for(int n=0;n<N;n+=8) for(int j=0;j<4;++j) {
        const d2 v=simd::load(q+n+2*j)-dd*simd::load(k+n+2*j);
        simd::store(q+n+2*j,v);
        s[j]+=simd::load(next+n+2*j)*v;
    }
    return sum8(s[0],s[1],s[2],s[3]);
}
// q -= d * k, then returns <q, q>.
inline double axpyNorm(double* __restrict q,const double* __restrict k,double d) {
    const d2 dd=simd::splat(d);
    d2 s[4]={{0,0},{0,0},{0,0},{0,0}};
    for(int n=0;n<N;n+=8) for(int j=0;j<4;++j) {
        const d2 v=simd::load(q+n+2*j)-dd*simd::load(k+n+2*j);
        simd::store(q+n+2*j,v);
        s[j]+=v*v;
    }
    return sum8(s[0],s[1],s[2],s[3]);
}
// q /= norm (element by element exactly as before), then returns <q, y>.
inline double scaleDot(double* __restrict q,double norm,const double* __restrict y) {
    const d2 nn=simd::splat(norm);
    d2 s[4]={{0,0},{0,0},{0,0},{0,0}};
    for(int n=0;n<N;n+=8) for(int j=0;j<4;++j) {
        const d2 v=simd::load(q+n+2*j)/nn;
        simd::store(q+n+2*j,v);
        s[j]+=v*simd::load(y+n+2*j);
    }
    return sum8(s[0],s[1],s[2],s[3]);
}

// out[k] = sum_n a[n] x[k][n] for k < K in one pass over the samples: two partial sums per output (even and odd n,
// added at the end), so every input is loaded once for all K outputs and the K chains run side by side.
template<int K> inline void dotsK(const double* __restrict a,const double* const* x,double* out) {
    d2 s[K];
    for(int k=0;k<K;++k) s[k]=d2{0,0};
    for(int n=0;n<N;n+=2) {
        const d2 va=simd::load(a+n);
        for(int k=0;k<K;++k) s[k]+=va*simd::load(x[k]+n);
    }
    for(int k=0;k<K;++k) out[k]=simd::sum(s[k]);
}
// The same for two rows a and b at once: outA[k] = sum a x[k], outB[k] = sum b x[k].
template<int K> inline void dots2K(const double* __restrict a,const double* __restrict b,const double* const* x,
                                   double* outA,double* outB) {
    d2 sa[K],sb[K];
    for(int k=0;k<K;++k) sa[k]=sb[k]=d2{0,0};
    for(int n=0;n<N;n+=2) {
        const d2 va=simd::load(a+n),vb=simd::load(b+n);
        for(int k=0;k<K;++k) { const d2 vx=simd::load(x[k]+n);sa[k]+=va*vx;sb[k]+=vb*vx; }
    }
    for(int k=0;k<K;++k) { outA[k]=simd::sum(sa[k]);outB[k]=simd::sum(sb[k]); }
}
inline void dotsAny(const double* a,const double* const* x,int k,double* out) {
    switch(k) {
        case 10: dotsK<10>(a,x,out); break;
        case 12: dotsK<12>(a,x,out); break;
        case 14: dotsK<14>(a,x,out); break;
        default: dotsK<16>(a,x,out); break;   // k == 16 (the only other column count)
    }
}
inline void dots2Any(const double* a,const double* b,const double* const* x,int k,double* outA,double* outB) {
    switch(k) {
        case 1: dots2K<1>(a,b,x,outA,outB); break;
        case 3: dots2K<3>(a,b,x,outA,outB); break;
        case 5: dots2K<5>(a,b,x,outA,outB); break;
        default: dots2K<7>(a,b,x,outA,outB); break;   // k == 7
    }
}

// The least-squares problem of one solve: y ~ A c, with A = [w u^p cos ph | w u^p sin ph (p = 0..4) | w cos / w sin of
// each neighbour], ph = 2 pi f t + pi slope t^2. Two ways to the same solution:
//   - normal equations (default): the Gram matrix A'A from window moments and dot products, Cholesky (its R is the R
//     of the QR factorisation, so the diagonal ratio is the same guard), and on the frame's last solve one step of
//     iterative refinement against A itself, which brings the solution back to QR accuracy;
//   - modified Gram-Schmidt with two passes (the original method): used whenever the Cholesky diagonal ratio exceeds
//     kGramRatioMax or a pivot is not clearly positive, so poorly conditioned frames and every failure decision get
//     exactly the original treatment.
// Diagonal ratio is a numerical guard, NOT the singular-value condition number.
struct Solver {
    // Typical music frames have a diagonal ratio near 30 (99% below 40); above 100 the normal equations would lose
    // more digits than the original method, so those solves use it (tools/pvb-harness/fit_equivalence.cpp).
    static constexpr double kGramRatioMax=100;
    alignas(64) double q[Columns][N];
    alignas(64) double y[N];
    alignas(64) double v[N];
    alignas(64) double neighbor[6][N];   // w cos / w sin of the neighbour columns, built on first use
    double r[Columns][Columns], projected[Columns];
    double gnn[6][6]={}, bn[6]={};       // neighbour block of A'A and A'y (per frame)
    double neighborHz[3]={}; int neighborCount=-1;
    double energy=0, rms=0, ratio=0, residual=0;
    bool usedGram=false;
    explicit Solver(const double* x) {
        const Axes& a=axes();
        for(int n=0;n<N;++n) {y[n]=x[n]*a.weight[n];energy+=y[n]*y[n];rms+=x[n]*x[n];}
        rms=std::sqrt(rms/N);
    }
    // final: the solve whose residual and ratio are used (the others only steer the carrier and the slope).
    bool solve(double f,double slope,const double* neighbors,int count,double* c,bool final=true) {
        const Axes& a=axes();
        const int cols=10+2*count;
        bool same=count==neighborCount;
        for(int j=0;same && j<count;++j) same=neighbors[j]==neighborHz[j];
        if(!same) {
            for(int j=0;j<count;++j) {
                neighborHz[j]=neighbors[j];
                double* nc=neighbor[j];double* ns=neighbor[count+j];
                const double hz=neighbors[j];
                for(int n=0;n<N;++n) {
                    const double ang=2*Pi*hz*a.time[n];
                    double sn,cs;fastmath::sincos(ang,sn,cs);
                    nc[n]=cs*a.weight[n];ns[n]=sn*a.weight[n];
                }
            }
            for(int i=0;i<2*count;++i) {
                bn[i]=dotN(neighbor[i],y);
                for(int k=0;k<=i;++k) gnn[i][k]=gnn[k][i]=dotN(neighbor[i],neighbor[k]);
            }
            neighborCount=count;
        }
        for(int n=0;n<N;++n) {
            const double t=a.time[n];
            const double ph=2*Pi*f*t+Pi*slope*t*t;
            double sn,cs;fastmath::sincos(ph,sn,cs);
            double p=1;const double co=cs*a.weight[n],si=sn*a.weight[n];
            for(int j=0;j<5;++j) {q[j][n]=co*p;q[j+5][n]=si*p;p*=a.u[n];}
        }
        usedGram=gram(cols,count,c,final);
        if(usedGram) return true;
        if(count>0) std::memcpy(q[10],neighbor[0],sizeof(double)*N*2*count);
        return mgs(cols,c);
    }
private:
    // Normal equations; false = use the original method for this solve (nothing is decided here).
    bool gram(int cols,int count,double* c,bool final) {
        const Axes& a=axes();
        double g[Columns][Columns];
        // carrier block from the moments of w^2 cos 2ph and w^2 sin 2ph: (w c)^2 = (w^2 + w^2 cos 2ph) / 2, ...
        double cm[9],sm[9];
        {
            d2 cs[9],ss[9];
            for(int m=0;m<9;++m) cs[m]=ss[m]=d2{0,0};
            const d2 two=simd::splat(2.0);
            for(int n=0;n<N;n+=2) {
                const d2 x=simd::load(q[0]+n),yv=simd::load(q[5]+n);
                const d2 dc=x*x-yv*yv,ds=two*x*yv;
                for(int m=0;m<9;++m) { const d2 um=simd::load(a.upow[m]+n);cs[m]+=dc*um;ss[m]+=ds*um; }
            }
            for(int m=0;m<9;++m) { cm[m]=simd::sum(cs[m]);sm[m]=simd::sum(ss[m]); }
        }
        for(int i=0;i<5;++i) for(int k=0;k<5;++k) {
            g[i][k]=.5*(a.moment[i+k]+cm[i+k]);
            g[i+5][k+5]=.5*(a.moment[i+k]-cm[i+k]);
            g[i][k+5]=g[k+5][i]=.5*sm[i+k];
        }
        // carrier columns against y and the neighbour columns (A'y and the carrier-neighbour block of A'A)
        double b[Columns];
        {
            const double* x[7]={y};
            for(int i=0;i<2*count;++i) x[1+i]=neighbor[i];
            const int k=1+2*count;
            for(int p=0;p<5;++p) {
                double outC[7],outS[7];
                dots2Any(q[p],q[p+5],x,k,outC,outS);
                b[p]=outC[0];b[p+5]=outS[0];
                for(int i=0;i<2*count;++i) { g[p][10+i]=g[10+i][p]=outC[1+i];g[p+5][10+i]=g[10+i][p+5]=outS[1+i]; }
            }
        }
        for(int i=0;i<2*count;++i) {
            b[10+i]=bn[i];
            for(int k=0;k<2*count;++k) g[10+i][10+k]=gnn[i][k];
        }
        // Cholesky g = R'R (R upper, positive diagonal) into r.
        double low=1e100,high=0;
        for(int j=0;j<cols;++j) {
            for(int k=0;k<j;++k) {
                double s=g[k][j];for(int i=0;i<k;++i) s-=r[i][k]*r[i][j];
                r[k][j]=s/r[k][k];
            }
            double d=g[j][j];for(int i=0;i<j;++i) d-=r[i][j]*r[i][j];
            if(!(d>0) || !std::isfinite(d)) return false;
            const double dj=std::sqrt(d);
            if(dj<1e-6) return false;      // the original fails below 1e-10: let it decide anywhere near that
            r[j][j]=dj;low=std::min(low,dj);high=std::max(high,dj);
        }
        if(!(high<=kGramRatioMax*low)) return false;
        cholSolve(cols,b,c);
        if(final) {
            // one step of iterative refinement against A, then the residual of the refined solution
            const double* cols_[Columns];
            for(int j=0;j<cols;++j) cols_[j]=j<10?q[j]:neighbor[j-10];
            residualVector(cols,cols_,c);
            double gr[Columns],dc[Columns];
            dotsAny(v,cols_,cols,gr);
            cholSolve(cols,gr,dc);
            for(int j=0;j<cols;++j) c[j]+=dc[j];
            residual=10*std::log10(std::max(residualVector(cols,cols_,c)/energy,1e-30));
            ratio=high/low;
        }
        return true;
    }
    void cholSolve(int cols,const double* b,double* x) const {
        double z[Columns];
        for(int j=0;j<cols;++j) { double s=b[j];for(int i=0;i<j;++i) s-=r[i][j]*z[i];z[j]=s/r[j][j]; }
        for(int j=cols-1;j>=0;--j) { double s=z[j];for(int k=j+1;k<cols;++k) s-=r[j][k]*x[k];x[j]=s/r[j][j]; }
    }
    // v = y - A c (per sample, columns ascending); returns sum v^2 (even and odd samples summed separately).
    double residualVector(int cols,const double* const* a,const double* c) {
        d2 e={0,0};
        for(int n=0;n<N;n+=2) {
            d2 t=simd::load(y+n);
            for(int j=0;j<cols;++j) t-=simd::load(a[j]+n)*simd::splat(c[j]);
            simd::store(v+n,t);e+=t*t;
        }
        return simd::sum(e);
    }
    // The original method: modified Gram-Schmidt with two passes on q (all columns).
    bool mgs(int cols,double* c) {
        for(int j=0;j<cols;++j) { projected[j]=0;for(int k=0;k<cols;++k) r[j][k]=0; }
        double low=1e100,high=0;
        for(int j=0;j<cols;++j) {
            double* qj=q[j];
            double norm;
            if(j==0) norm=dotN(qj,qj);
            else {
                // Two passes over k = 0 .. j-1; the axpy of each step is fused with the next step's dot product.
                double dot=dotN(q[0],qj);
                const int steps=2*j;
                norm=0;
                for(int s=0;s<steps;++s) {
                    const int k=s<j?s:s-j;
                    r[k][j]+=dot;
                    if(s+1<steps) { const int next=s+1<j?s+1:s+1-j; dot=axpyDot(qj,q[k],dot,q[next]); }
                    else norm=axpyNorm(qj,q[k],dot);
                }
            }
            norm=std::sqrt(norm);
            if(!std::isfinite(norm) || norm<1e-10) return false;
            r[j][j]=norm;low=std::min(low,norm);high=std::max(high,norm);
            projected[j]=scaleDot(qj,norm,y);
        }
        ratio=high/low;
        for(int j=cols-1;j>=0;--j) {
            double val=projected[j];for(int k=j+1;k<cols;++k) val-=r[j][k]*c[k];c[j]=val/r[j][j];
        }
        // Residual: the same per-sample subtraction order (columns ascending), then one sum.
        const double* qs[Columns];
        for(int j=0;j<cols;++j) qs[j]=q[j];
        residualVector(cols,qs,projected);
        residual=10*std::log10(std::max(dotN(v,v)/energy,1e-30));return true;
    }
};
inline ModulationFit fit(const double* x,double seed,const double* neighbors=nullptr,int count=0) {
    ModulationFit m; if(!std::isfinite(seed)) return m; m.carrier=seed;count=neighbors?std::max(0,std::min(3,count)):0;
    for(int n=0;n<N;++n) if(!std::isfinite(x[n])) return m;
    Solver s(x);if(s.energy<1e-14 || seed<20 || seed>200) return m;
    double c[Columns]={};
    for(int it=0;it<4;++it) {
        if(!s.solve(m.carrier,m.slope,neighbors,count,c,false)) return m;
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
} // namespace modulation
} // namespace pvb

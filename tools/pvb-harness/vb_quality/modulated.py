"""128ms polynomial complex-envelope AM/FM estimator; research, not source separation.

An amplitude-changing sinusoid and some nearby-tone mixtures can be identical.
The returned fit validity is numerical, never an instrument/buzz probability.
No samples outside the supplied384-sample frame are accessed.
"""
import time
import numpy as np

FS=3000
N=384
DEGREE=4
ITERATIONS=4
T=(np.arange(N)-N//2)/FS
HALF=N/(2*FS)
U=T/HALF
W=np.hanning(N+1)[:-1]**.5
POLY=np.column_stack([U**j for j in range(DEGREE+1)])


def seed_frequency(x):
    mag=abs(np.fft.rfft(np.asarray(x)*W**2,2048))
    first,last=int(np.ceil(25*2048/FS)),int(np.floor(190*2048/FS))
    b=first+int(np.argmax(mag[first:last+1]))
    a,v,c=np.log(mag[b-1:b+2]+1e-30)
    delta=np.clip(.5*(a-c)/(a-2*v+c),-1,1) if abs(a-2*v+c)>1e-12 else 0
    return (b+delta)*FS/2048


def fit(frame, seed=None, neighbors=()):
    x=np.asarray(frame,dtype=float)
    if x.shape!=(N,) or not np.isfinite(x).all(): raise ValueError('finite384-sample frame required')
    begin=time.perf_counter()
    energy=np.dot(x*W,x*W)
    if energy<1e-14: return {'accepted':False,'reason':'silence'}
    f=seed_frequency(x) if seed is None else float(seed)
    slope=0.
    seeds=tuple(float(v) for v in neighbors[:3])
    coef=None
    def solve(f,slope):
        ph=2*np.pi*f*T+np.pi*slope*T*T
        b=np.concatenate((POLY*np.cos(ph)[:,None],POLY*np.sin(ph)[:,None]),axis=1)
        if seeds:
            other=2*np.pi*T[:,None]*np.asarray(seeds)[None,:]
            b=np.concatenate((b,np.cos(other),np.sin(other)),axis=1)
        matrix=b*W[:,None]
        c,_,_,sv=np.linalg.lstsq(matrix,x*W,rcond=1e-10)
        return b,c,sv
    for iteration in range(ITERATIONS):
        b,c,sv=solve(f,slope)
        z=c[:5]-1j*c[5:10]
        if abs(z[0])<1e-9: return {'accepted':False,'reason':'vanishing_centre'}
        rate=z[1]/(HALF*z[0])
        curvature=2*z[2]/(HALF*HALF*z[0])-rate*rate
        df=np.clip(rate.imag/(2*np.pi),-5,5)
        ds=np.clip(curvature.imag/(2*np.pi),-100,100)
        f+=df;slope=np.clip(slope+ds,-400,400)
        if not 20<f<200: return {'accepted':False,'reason':'frequency_bounds'}
        if abs(df)<1e-5 and abs(ds)<.01: break
    b,c,sv=solve(f,slope)
    z=c[:5]-1j*c[5:10]
    phase_rate=z[1]/(HALF*z[0])
    phase_curve=2*z[2]/(HALF*HALF*z[0])-phase_rate*phase_rate
    predicted=b@c
    residual=10*np.log10(max(np.sum(((predicted-x)*W)**2)/energy,1e-30))
    condition=float(sv[0]/max(sv[-1],1e-30))
    # Positivity of |complex envelope| is not proof of one physical source.
    amplitude=float(abs(z[0]));frequency=float(f+phase_rate.imag/(2*np.pi))
    accepted=bool(residual<=-20 and condition<1e4 and 25<=frequency<=190 and amplitude<4*np.sqrt(np.mean(x*x)))
    return dict(accepted=accepted,reason='fit' if accepted else 'residual_or_condition',
        amplitude=amplitude,frequency_hz=frequency,phase_rad=float(np.angle(z[0])),
        amplitude_slope=float(amplitude*phase_rate.real),frequency_slope=float(slope+phase_curve.imag/(2*np.pi)),
        carrier_hz=float(f),carrier_slope=float(slope),coefficients=z,residual_db=float(residual),
        condition=condition,iterations=iteration+1,elapsed_ms=(time.perf_counter()-begin)*1000,
        predicted=predicted)


def evaluate(model,t,order=1):
    """Defined synthetic AM/FM rule; this is not an absent harmonic's unique truth."""
    t=np.asarray(t,dtype=float)
    z=np.polynomial.polynomial.polyval(t/HALF,model['coefficients'])
    phase=2*np.pi*model['carrier_hz']*t+np.pi*model['carrier_slope']*t*t+np.angle(z)
    return abs(z)*np.cos(order*phase)

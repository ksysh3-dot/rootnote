#!/usr/bin/env python3
"""Controls for the early-tail split in research_p1pp_impacts.score (bed-shaped vs not the bed).

Known changes against a known bed layer: a 40 ms gap and a slow step are bed-shaped; white noise is not; tones
between bed harmonics are only partly separable in an 80 ms window, so their leak is reported, not hidden.
"""
import numpy as np
from scipy.signal import hilbert

def split(z,bs,bq,tt):
    knots=np.arange(tt[0],tt[-1]+.01,.01);hats=np.clip(1-abs(tt[:,None]-knots[None,:])/.01,0,None)
    mod=np.column_stack([bs[:,None]*hats,bq[:,None]*hats]);other=z-mod@np.linalg.lstsq(mod,z,rcond=1e-10)[0]
    tot=np.sum(z**2);return 10*np.log10(np.sum(other**2)/tot+1e-30)

fs=48000;T=np.arange(int(.5*fs))/fs+1.1;w=(T>=1.3)&(T<1.38);tt=T[w];rows=[]
for f in (43.,60.,100.):
    full=sum(np.cos(2*np.pi*k*f*T+k)/k for k in range(2,9));bs=full[w];bq=np.imag(hilbert(full))[w]
    gap=-bs*(tt<1.34);step=-bs*np.clip((1.36-tt)/.02,0,1)*(tt>1.32)+.3*bq*(tt>1.35)
    noise=np.random.default_rng(1).normal(0,.3,len(tt))
    assert split(gap,bs,bq,tt)<-15 and split(step,bs,bq,tt)<-10, f
    assert split(noise,bs,bq,tt)>-.2, f
    rows.append((f,split(.5*np.cos(2*np.pi*1.5*f*tt+.3),bs,bq,tt),split(.5*np.cos(2*np.pi*(2*f+15)*tt),bs,bq,tt)))
print('tail split controls PASS (gap/step bed-shaped, noise not); share of an off-bed tone left as non-bed (dB):',
      ', '.join(f'{f:.0f} Hz: 1.5f {a:.1f}, 2f+15 {b:.1f}' for f,a,b in rows))

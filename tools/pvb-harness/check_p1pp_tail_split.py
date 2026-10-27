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

# Against the engine's real bed layer (100 Hz bed, P1+ flags 6, impact mode 8) the split is frequency dependent:
# a tone near a harmonic of the layer is mostly counted as bed-shaped. Reported, not hidden (worker review 2026-10-27).
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import research_p1plus as P
from p1plus_paths import default_library
lib=P.api(default_library().resolve());t=np.arange(int(2.5*fs))/fs
b=.018*np.cos(2*np.pi*100*t)*np.minimum(1,t/.05)
r=P.render(lib,np.r_[b,np.zeros(fs//2)],fs,6,impact_mode=8)
full=r['stem'][r['latency']:r['latency']+len(t),0].astype(float)
m=(t>=1.5)&(t<1.58);tt=t[m];bs,bq=full[m],np.imag(hilbert(full))[m]
share={f:10**(split(.001*np.cos(2*np.pi*f*tt+.4),bs,bq,tt)/10) for f in (150,215,330,437)}
gap=10**(split(-bs*(tt<1.54),bs,bq,tt)/10)
assert gap<.05 and share[437]>.9, (gap,share)
print('engine bed layer: share of an added tone left as non-bed:',', '.join(f'{f} Hz {100*v:.1f}%' for f,v in share.items()),
      f'| 40 ms gap left as non-bed {100*gap:.1f}%')

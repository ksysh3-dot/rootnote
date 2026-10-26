#!/usr/bin/env python3
"""Short-note generated-layer envelope diagnostic, separate from HPSS error.

The extraction filter is applied to both desired and observed waves; only one
constant scale is fitted, no time shift or per-frame normalization is allowed.
This is a controlled short-note objective, not a real-music preference score.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import firwin,fftconvolve,resample_poly
import research_p1plus as P
import research_p1hq as H


def envelope(wave,fs,center,cutoff):
    z=resample_poly(np.asarray(wave,float),3000,fs)
    t=np.arange(len(z))/3000
    taps=firwin(901,cutoff,fs=3000,window=('kaiser',8))
    return abs(fftconvolve(2*z*np.exp(-2j*np.pi*center*t),taps,mode='same'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();lib=P.api(a.library.resolve());fs=48000;rows=[]
    for held in (False,True):
        for name,h,noise,desc in H.mixtures(fs,held):
            if not desc['short_notes']:continue
            f=desc['frequency'];t=np.arange(len(h))/fs
            env=np.zeros(len(t))
            for start in (.55,1.3,2.25,3.4):
                dt=t-start;env+=np.where((dt>=0)&(dt<.12),np.sin(np.pi*np.clip(dt/.12,0,1))**2,0)
            env*=.09*(1+.35*np.sin(2*np.pi*desc['am_rate']*t))
            ideal=env*np.cos(2*np.pi*3*f*t)
            reference=envelope(ideal,fs,3*f,.35*f)
            use=slice(900,12000);ref=reference[use];modes={}
            for flag in (0,2,6,14):
                rendered=P.render(lib,np.r_[h+noise,np.zeros(fs)],fs,flag)
                y=rendered['stem'][rendered['latency']:rendered['latency']+len(h),0]
                measured=envelope(y,fs,3*f,.35*f)[use]
                scale=float(measured@ref/(ref@ref))
                if scale<1e-7:raise ValueError(('missing generated carrier',name,flag,scale))
                modes[str(flag)]=dict(one_constant_scale=scale,
                    shape_error_db=H.db_ratio(H.power(measured-scale*ref),H.power(scale*ref)),
                    correlation=float(np.corrcoef(measured,ref)[0,1]),
                    latency=rendered['latency'])
            rows.append(dict(name=name,frequency=f,variants=modes))
            print(name,{k:round(x['shape_error_db'],3) for k,x in modes.items()},flush=True)
    a.report.write_text(json.dumps(dict(schema='pvb.p1hq.envelopes.v1',cases=rows,
                          definition='Declared-latency aligned third-harmonic envelope; input-defined short-note objective; one constant scale.'),indent=2),encoding='utf-8')


if __name__=='__main__':main()

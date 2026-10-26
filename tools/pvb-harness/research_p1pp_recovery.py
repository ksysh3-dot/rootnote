#!/usr/bin/env python3
"""Confirmation-recovery ablations and a predeclared new impact cohort."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.signal import butter,sosfilt
import research_p1plus as P
from research_p1pp_impacts import fresh_fixtures,score,energy
from p1plus_paths import default_library


def new_fixtures(fs,seed=2026102609,count=12):
    rng=np.random.default_rng(seed);t=np.arange(round(3.8*fs))/fs;onset=1.25;u=t-onset
    for j in range(count):
        duration=float(rng.uniform(.08,.22) if j<4 else rng.uniform(.025,.095))
        active=(u>=0)&(u<duration);z=np.zeros_like(t)
        if j<4:
            end=float(rng.uniform(41,70));jump=float(rng.uniform(65,155));tau=float(rng.uniform(.015,.035));decay=float(rng.uniform(.02,.06))
            ph=2*np.pi*(end*u+jump*tau*(1-np.exp(-np.maximum(u,0)/tau)))
            env=(1-np.exp(-np.maximum(u,0)/.001))*np.exp(-np.maximum(u,0)/decay)
            env*=np.minimum(1,np.maximum(0,(duration-u)/.01))
            z[active]=env[active]*np.cos(ph[active])
            z[active]+=.12*rng.normal(size=len(t))[active]*np.exp(-u[active]/.004);kind='kick'
        else:
            noise=sosfilt(butter(2,[30,4000],btype='bandpass',fs=fs,output='sos'),rng.normal(size=len(t)))
            z[active]=noise[active]*np.sin(np.pi*u[active]/duration)**2;kind='broadband'
        z/=np.max(abs(z));bf=float(rng.uniform(43,105));phase=float(rng.uniform(-np.pi,np.pi));amp=float(rng.uniform(.012,.025))
        b=amp*np.cos(2*np.pi*bf*t+phase)*np.minimum(1,t/.05)
        desc=dict(duration=duration,bed_frequency=bf,bed_phase=phase,bed_amplitude=amp,kind=kind)
        yield f'new_{kind}_{j}',True,t,b,z,onset,duration,desc


def feature(z,fs):
    nz=z[abs(z)>1e-14];nfft=max(8192,1<<(len(nz)-1).bit_length())
    s=abs(np.fft.rfft(nz,n=nfft))**2;f=np.fft.rfftfreq(nfft,1/fs)
    m=(f>=25)&(f<=1000);band=s[m]
    return dict(input_spectral_flatness_25_1000=float(np.exp(np.mean(np.log(band+1e-30)))/np.mean(band)),
                input_centroid_25_4000=float(np.sum(f*s*((f>=25)&(f<=4000)))/np.sum(s*((f>=25)&(f<=4000)))),
                input_crest_db=float(20*np.log10(np.max(abs(nz))/np.sqrt(np.mean(nz*nz)))))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--out',type=Path,required=True);p.add_argument('--set',choices=('inspected','new','confirm'),default='new')
    p.add_argument('--modes',type=int,nargs='+',default=[0,2,3,4]);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);lib=P.api(a.library.resolve());fs=48000;rows=[];features=[]
    if a.set in ('new','confirm'):
        fixtures=new_fixtures(fs,2026102610 if a.set=='confirm' else 2026102609,8 if a.set=='confirm' else 12);levels=(-12,-6,-1)
    else:
        fixtures=(tuple(v)+(dict(duration=v[6],kind='kick' if 'kick' in v[0] else 'broadband'),) for v in fresh_fixtures(fs))
        levels=(-24,-12,-6,-1)
    for name,bed,t,b,z,onset,duration,desc in fixtures:
        features.append(dict(name=name,**desc,**feature(z,fs)))
        for mode in a.modes:
            base=P.render(lib,np.r_[b,np.zeros(fs//2)],fs,6,impact_mode=mode)
            for level in levels:
                impact=z*10**(level/20);x=b+impact;assert np.max(abs(x))<1
                r=P.render(lib,np.r_[x,np.zeros(fs//2)],fs,6,impact_mode=mode)
                v,y=score(r,base,x,impact,t,onset,duration,fs)
                samples=int(np.sum((t>=onset+duration+.08)&(t<onset+duration+.5)))
                v['late_absolute_residual_rms_dbfs']=v['late_tail_stationary_residual_per_input_db']+10*np.log10(energy(impact)/samples)
                rows.append(dict(name=name,mode=mode,input_level_dbfs=level,**v))
                if level==-1 and (a.set=='inspected' or name.endswith('_11')):
                    np.savez_compressed(a.out/f'{name}-mode{mode}.npz',t=t,x=x,impact=impact,stem_delta=y,hops=r['rows'],stages=r['stages'])
            print(name,'mode',mode,'last residual',round(v['late_tail_stationary_residual_per_input_db'],3),flush=True)
    result=dict(schema='pvb.p1pp.recovery.v1',cohort=a.set,seed=2026102610 if a.set=='confirm' else 2026102609 if a.set=='new' else 2026102608,
                library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),sample_rate=fs,
                independent_waveforms=len(features),levels_per_waveform=len(levels),modes=a.modes,
                features=features,cases=rows,note='Inspected cohort is development. New cohort is generated after mode rules were fixed; no DSP retuning afterward. Input features are descriptive, not an exception classifier.',
                device_validation=False,listening_validation=False)
    (a.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()

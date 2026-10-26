#!/usr/bin/env python3
"""Fresh short-note test on the input/table-defined strongest output harmonic.

The earlier fixed third-harmonic diagnostic is retained separately. At 43 Hz its
130 Hz channel lies below the output high-pass; it is not the main bass cue.
Selection here uses only source f and unchanged P1 tables/filter, never output.
"""
import argparse
import json
from pathlib import Path
import re
import numpy as np
from scipy.signal import sosfreqz
import research_p1plus as P
import research_p1hq as H
from check_p1hq_envelopes import envelope
from vb_quality import measurement as Q


def primary(f):
    path=Path(__file__).resolve().parents[2]/'app/src/main/cpp/libpvb/pvb_vb_tables.h'
    match=re.search(r'kOutSos\[18\]\s*=\s*\{(.*?)\};',path.read_text(),re.S)
    sos=np.fromstring(match[1].replace('\n',''),sep=',').reshape(3,6)
    k=np.arange(2,9);weights=Q.emission_weights(f,algorithm=4)
    _,response=sosfreqz(sos,worN=k*f,fs=3000)
    predicted=weights*abs(response)
    return int(k[np.argmax(predicted)])


def fixtures(fs):
    rng=np.random.default_rng(2026102606);t=np.arange(round(4.5*fs))/fs
    for j in range(6):
        f=float(rng.uniform(41,125));rate=float(rng.uniform(0,8));duration=float(rng.uniform(.08,.18))
        env=np.zeros(len(t))
        for start in (.55,1.3,2.25,3.4):
            dt=t-start;env+=np.where((dt>=0)&(dt<duration),np.sin(np.pi*np.clip(dt/duration,0,1))**2,0)
        env*=.09*(1+.35*np.sin(2*np.pi*rate*t));h=env*np.cos(2*np.pi*f*t+.3)
        p=np.zeros(len(t));noise=rng.normal(0,1,len(t));width=float(rng.uniform(.006,.028))
        for start in (.8,1.6,2.8,3.7):p+=.32*noise*np.exp(-.5*((t-start)/width)**2)
        yield f'fresh_note_{j}',h+p,env,dict(frequency=f,rate=rate,note_seconds=duration,noise_width=width)


def score(measured,ref):
    scale=float(measured@ref/(ref@ref))
    if scale<1e-7:raise ValueError('Expected harmonic is effectively missing')
    return dict(one_constant_scale=scale,shape_error_db=H.db_ratio(H.power(measured-scale*ref),H.power(scale*ref)),
                correlation=float(np.corrcoef(measured,ref)[0,1]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();lib=P.api(a.library.resolve());fs=48000;rows=[]
    for name,source,env,desc in fixtures(fs):
        f=desc['frequency'];k=primary(f);t=np.arange(len(source))/fs
        ideal=env*np.cos(2*np.pi*k*f*t)
        ref=envelope(ideal,fs,k*f,.35*f)[900:12000]
        control=score(.25*ref,ref);assert control['shape_error_db']<-240
        delayed=np.r_[np.zeros(150),ref[:-150]]
        assert score(delayed,ref)['shape_error_db']>control['shape_error_db']+20
        modes={}
        for flag in (0,2,6,14):
            result=P.render(lib,np.r_[source,np.zeros(fs)],fs,flag)
            wave=result['stem'][result['latency']:result['latency']+len(source),0]
            modes[str(flag)]=score(envelope(wave,fs,k*f,.35*f)[900:12000],ref)
        rows.append(dict(name=name,input=desc,primary_harmonic=k,variants=modes))
        print(name,'k',k,{n:round(v['shape_error_db']-modes['0']['shape_error_db'],3) for n,v in modes.items()},flush=True)
    a.report.write_text(json.dumps(dict(schema='pvb.p1hq.primary_envelopes.v1',
        seed=2026102606,selection='Input frequency, P1 gentle24 table, fixed output SOS only',
        one_constant_gain_allowed=True,no_fitted_delay=True,controls='gain invariance and known 50 ms error passed',
        cases=rows),indent=2),encoding='utf-8')


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Host-only native callback timing; not phone CPU, heat or battery evidence."""
import argparse
import json
from pathlib import Path
import numpy as np
import research_p1plus as P


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();lib=P.api(a.library.resolve());fs=48000;t=np.arange(6*fs)/fs
    rng=np.random.default_rng(2026102607)
    x=sum(.035*(1+.3*np.sin(2*np.pi*(j+2)*t))*np.cos(2*np.pi*f*t+.1*j) for j,f in enumerate((43,67,97,137)))
    for start in (.6,1.4,2.7,3.8,4.6):x+=.10*rng.normal(size=len(t))*np.exp(-((t-start)/.012)**2)
    flags=(0,2,6,14)
    for f in flags:P.render(lib,x[:fs],fs,f,capture=False)
    times={str(f):[] for f in flags}
    for repetition in range(5):
        order=flags[repetition%4:]+flags[:repetition%4]
        for f in order:
            r=P.render(lib,x,fs,f,capture=False)
            times[str(f)].append(r['callback_total_seconds']/6*1000)
    med={f:float(np.median(x)) for f,x in times.items()}
    result=dict(schema='pvb.p1hq.host_timing.v1',seconds_per_run=6,trials=5,capture=False,
                native_ms_per_audio_second=times,median_native_ms_per_audio_second=med,
                median_ratio_vs_p1={f:v/med['0'] for f,v in med.items()},
                phone_cpu_validated=False,performance_guarantee=False)
    a.report.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Disclose legitimate AM depth/rate, alongside the spectral residual diagnostic."""
import argparse,json
from pathlib import Path
import numpy as np
import research_p1plus as P
from vb_quality import measurement as Q


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();lib=P.api(a.library.resolve());fs=48000;t=np.arange(5*fs)/fs;rows=[]
    for rate in (3.,7.,11.):
        x=.12*(1+.7*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*55*t+.2);modes={}
        for flags in (0,2,6):
            r=P.render(lib,x,fs,flags)
            modes[str(flags)]=Q.am_metric(r['stem'],fs,55,3,rate,.7,1,start=1.25,stop=3.75,
                                          latency=r['latency']/fs,reference_peak=.12,temporal=True)
        rows.append(dict(rate=rate,variants=modes));print(rate,{k:round(v['depth'],4) for k,v in modes.items()},flush=True)
    a.report.write_text(json.dumps(dict(schema='pvb.p1hq.am.v1',expected_depth=.7,cases=rows),indent=2),encoding='utf-8')


if __name__=='__main__':main()

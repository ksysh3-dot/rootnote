#!/usr/bin/env python3
"""Render an actual P1/P1+ HQ file, with declared delay compensation and provenance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as P
import test_engine as T
from p1plus_paths import default_library, P1PLUS_FLAGS, P1PLUS_BASELINE_ID

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('p1','phase','p1plus','centered','hq','prominence'),default='p1plus')
    p.add_argument('--fs',type=int,choices=(44100,48000),default=48000)
    p.add_argument('--vb-db',type=float,default=6);p.add_argument('--out-db',type=float,default=-18)
    p.add_argument('--peak-target',type=float,default=None,
                   help='Optional single gain for the whole playback file, in dBTP; no frame-wise normalization.')
    p.add_argument('--tail-seconds',type=float,default=.25)
    a=p.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    if a.input.resolve()==a.output.resolve():p.error('Output must differ from original input')
    if a.output.exists():p.error('Output exists; choose a new name')
    if not 0<=a.tail_seconds<=.5:p.error('Tail must be 0..0.5 seconds')
    if a.peak_target is not None and a.peak_target>-.1:p.error('Playback peak target must be <= -0.1 dBTP')
    data,source_fs=sf.read(str(a.input),dtype='float32',always_2d=True)
    if data.shape[1]==1:data=np.repeat(data,2,axis=1)
    if data.shape[1]!=2:p.error('Only mono/stereo sources are supported')
    if source_fs!=a.fs:
        g=math.gcd(source_fs,a.fs);data=np.asarray(resample_poly(data,a.fs//g,source_fs//g,axis=0),np.float32)
    flags={'p1':0,'phase':2,'p1plus':P1PLUS_FLAGS,'centered':P1PLUS_FLAGS,'hq':P1PLUS_FLAGS,'prominence':14}[a.mode]
    lib=P.api(a.library.resolve());e=T.Engine(lib,a.fs,vb_on=1,vb_algo=6,vb_level_db=a.vb_db,out_db=a.out_db,ramp_ms=0)
    try:
        assert lib.pvb_set_p1plus_research(e.h,flags)==1
        padded=np.concatenate((data,np.zeros((a.fs,2),np.float32)))
        start=time.perf_counter();rendered=e.process(padded);elapsed=time.perf_counter()-start
        latency=e.latency();meters=e.meters()
    finally:e.close()
    wave=rendered[latency:latency+len(data)+round(a.tail_seconds*a.fs)]
    if not np.isfinite(wave).all():raise ValueError('Nonfinite engine output')
    raw_peak=float(T.true_peak_db(wave,4));gain_db=0 if a.peak_target is None else a.peak_target-raw_peak
    output=np.asarray(wave*10**(gain_db/20),np.float32)
    if np.max(abs(output))>=1:raise ValueError('PCM24 overflow; choose a lower output or peak target')
    a.output.parent.mkdir(parents=True,exist_ok=True);sf.write(str(a.output),output,a.fs,subtype='PCM_24')
    result=dict(schema='pvb.p1hq.render.v1',source=str(a.input.resolve()),source_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
                source_fs=source_fs,processing_fs=a.fs,source_seconds=len(data)/a.fs,mode=a.mode,flags=flags,
                model_name='P1+' if flags==P1PLUS_FLAGS else a.mode,
                research_baseline_id=P1PLUS_BASELINE_ID if flags==P1PLUS_FLAGS else None,
                settings=dict(algorithm=6,vb_db=a.vb_db,out_db=a.out_db,ramp_ms=0),
                latency_frames=latency,latency_ms=1000*latency/a.fs,latency_compensated_in_file=True,
                tail_seconds=a.tail_seconds,raw_true_peak_4x_dbtp=raw_peak,whole_file_playback_gain_db=gain_db,
                rendering_wall_seconds=elapsed,device_runtime_measured=False,
                library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
    a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

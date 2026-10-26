#!/usr/bin/env python3
"""Input-selected strong events; level/difference evidence has no noise labels."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter,sosfilt,resample_poly,find_peaks
import research_p1plus as P
import test_engine as T
from p1plus_paths import default_library
from research_p1pp_impacts import fixtures


def power(x):return float(np.mean(np.asarray(x,dtype=float)**2))
def db(a,b):return float(10*np.log10(max(a,1e-30)/max(b,1e-30)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--test-folder',type=Path,required=True);p.add_argument('--album-folder',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    lib=P.api(a.library.resolve());fs=48000;events=[]
    paths=[a.test_folder/'test 3.wav']
    paths += [next(a.album_folder.glob(pattern)) for pattern in ('* - Dream.flac','* - Fighting Spirit.flac','* - Mirage.flac')]
    for path in paths:
        source,sr=sf.read(path,dtype='float32',always_2d=True)
        if source.shape[1]==1:source=np.repeat(source,2,axis=1)
        if sr!=fs:
            g=math.gcd(sr,fs);source=resample_poly(source,fs//g,sr//g,axis=0).astype(np.float32)
        band=sosfilt(butter(2,[25,500],btype='bandpass',fs=fs,output='sos'),source.mean(axis=1))
        bins=np.sqrt(np.mean(band[:len(band)//240*240].reshape(-1,240)**2,axis=1))
        recent=np.convolve(bins,np.ones(20)/20,mode='full')[:len(bins)]
        novelty=np.maximum(0,bins-np.r_[0,recent[:-1]])*bins
        peaks,_=find_peaks(novelty,distance=150)
        peaks=[int(x) for x in peaks if x*.005>3.1 and x*.005<len(source)/fs-1.3]
        chosen=sorted(sorted(peaks,key=lambda x:novelty[x],reverse=True)[:2])
        for index,j in enumerate(chosen):
            at=(j+.5)*.005;start=at-3.;stop=at+1.2
            x=source[round(start*fs):round(stop*fs)];local=at-start;n=len(x);tt=np.arange(n)/fs
            modes={};waves={};record={}
            for mode in (0,1,2):
                r=P.render(lib,np.r_[x,np.zeros((fs//2,2),np.float32)],fs,6,impact_mode=mode)
                d=r['latency'];y=r['output'][d:d+n];stem=r['stem'][d:d+n]
                waves[mode]=y;v=dict(full_rms_dbfs=db(power(y),1),layer_rms_dbfs=db(power(stem),1),
                                    true_peak_4x_dbtp=T.true_peak_db(y,4),latency=d)
                for label,mask in dict(pre=(tt>=local-.15)&(tt<local-.02),attack=(tt>=local-.02)&(tt<local+.06),post=(tt>=local+.12)&(tt<local+.5)).items():
                    v[label+'_layer_power']=power(stem[mask])
                if mode:
                    v['full_difference_db']=db(power(y-waves[0]),power(waves[0]))
                    v['layer_rms_change_db']=v['layer_rms_dbfs']-modes['0']['layer_rms_dbfs']
                    for label in ('pre','attack','post'):
                        v[label+'_layer_change_db']=db(v[label+'_layer_power'],modes['0'][label+'_layer_power'])
                modes[str(mode)]=v
            number=len(events)+1
            common_gain_db=-1-max(T.true_peak_db(waves[m],4) for m in (0,2))
            excerpt=(tt>=local-.2)&(tt<local+.8)
            for mode,label in ((0,'P1plus'),(2,'guard_new_experimental')):
                sf.write(a.out/f'{number:02d}_{label}.wav',waves[mode][excerpt]*10**(common_gain_db/20),fs,subtype='PCM_24')
            events.append(dict(source=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               source_fs=sr,event_seconds=at,selection_score=float(novelty[j]),
                               context_start=start,context_stop=stop,common_playback_gain_db=common_gain_db,variants=modes))
            print(path.name,index,'at',round(at,3),'layer change',round(modes['2']['layer_rms_change_db'],3),flush=True)
    # Separate limiter stress at realistic app output settings. These are host
    # limits; the phone/OEM speaker protection is not modeled.
    stresses=[]
    shape,bed,t,b,z,onset,duration=list(fixtures(fs))[-1]
    for level in (-12,-6,-1):
        x=b+z*10**(level/20)
        for out_db in (-18,-3):
            for vb_db in (6,9):
                e=T.Engine(lib,fs,vb_on=1,vb_algo=6,vb_level_db=vb_db,out_db=out_db,ramp_ms=0)
                try:
                    assert lib.pvb_set_p1plus_research(e.h,6)==1
                    y,m=e.process_with_meters(T.stereo(np.r_[x,np.zeros(fs//2)]),block=240)
                    stresses.append(dict(input_peak_dbfs=level,out_db=out_db,vb_db=vb_db,
                                         limiter_max_gr_db=float(m[:,T.M['LIM_GR_DB']].max()),
                                         limiter_max_active_pct=float(m[:,T.M['LIM_ACTIVE_PCT']].max()),
                                         output_sample_peak=float(np.max(abs(y)))))
                finally:e.close()
    result=dict(schema='pvb.p1pp.impact_music.v1',library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                selection='Top two input-only low-band positive-energy novelty peaks per predeclared file, spaced 750 ms; 3 s preroll, not full-song state.',
                note='Music pre/post differences are not labeled noise reduction. PCM24 excerpts share one gain per pair.',
                events=events,limiter_stress=stresses,device_validation=False,listening_validation=False)
    (a.out/'music.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()

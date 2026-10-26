#!/usr/bin/env python3
"""User corpus comparison, aligned only by each engine's declared latency."""
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
import research_p1plus_music as M
import test_engine as T


def aligned(r,begin,length,fs):
    lo=round(begin*fs)+r['latency'];hi=lo+round(length*fs)
    assert hi<=len(r['output'])
    return r['output'][lo:hi],r['stem'][lo:hi]


def compare(base,candidate,begin,length,fs):
    a,sa=aligned(base,begin,length,fs);b,sb=aligned(candidate,begin,length,fs)
    return dict(full_mix_rms_change_db=M.db(M.rms(b))-M.db(M.rms(a)),
                layer_rms_change_db=M.db(M.rms(sb))-M.db(M.rms(sa)),
                full_mix_difference_db=M.db(M.rms(b-a)/max(M.rms(a),1e-30)),
                layer_difference_db=M.db(M.rms(sb-sa)/max(M.rms(sa),1e-30)),
                true_peak_4x_dbtp=float(T.true_peak_db(b,4)),
                latency_frames=candidate['latency'],
                output_bit_exact_after_declared_alignment=bool(np.array_equal(a,b)),
                native_capture_time_s=candidate['callback_total_seconds'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True)
    p.add_argument('--folder',type=Path,action='append',required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--clips',type=Path)
    p.add_argument('--resume',action='store_true');a=p.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    fs=48000;length=8.;fractions=(.15,.5,.85);lib=P.api(a.library.resolve())
    variants={0:'P1',2:'P1plus_phase',6:'P1HQ_centered',14:'P1HQ_prominence'}
    files=sorted(x for folder in a.folder for x in folder.rglob('*') if x.is_file() and x.suffix.lower() in ('.wav','.flac'))
    if not files:raise ValueError('No WAV/FLAC files')
    settings=dict(fs=fs,length_seconds=length,fractions=fractions,preroll=4.,postroll=.25,
                  algorithm=6,vb_level_db=6,out_db=-18,ramp_ms=0,variants=variants)
    report=dict(schema='pvb.p1hq.music.v1',library_sha256=M.digest(a.library),settings=settings,
                files=[],regions=[],clips=[],quality_verdict='not_inferred_from_unknown_music',
                listening_validated=False,device_validated=False)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    if a.clips:a.clips.mkdir(parents=True,exist_ok=True)
    if a.resume and a.report.exists():
        saved=json.loads(a.report.read_text(encoding='utf-8'))
        assert saved['library_sha256']==report['library_sha256']
        assert saved['settings']==json.loads(json.dumps(settings))
        report=saved
    finished={(r['file'],r['start']) for r in report['regions']};clock=time.perf_counter()
    for path in files:
        info=sf.info(str(path))
        if info.channels not in (1,2) or info.duration<8.5:raise ValueError(('unsupported source',str(path)))
        metadata=dict(path=str(path),sha256=M.digest(path),sample_rate=info.samplerate,
                      channels=info.channels,duration=info.duration,prior_processing='unknown')
        existing=[x for x in report['files'] if x['path']==str(path)]
        if existing:assert existing==[metadata]
        else:report['files'].append(metadata)
        for fraction in fractions:
            start=round(fraction*(info.duration-length-.25),3)
            if (str(path),start) in finished:continue
            frame_start=round(max(0,start-4)*info.samplerate)
            with sf.SoundFile(str(path)) as audio:
                audio.seek(frame_start)
                data=audio.read(round((start+length+.25)*info.samplerate)-frame_start,dtype='float32',always_2d=True)
            if info.channels==1:data=np.repeat(data,2,axis=1)
            if info.samplerate!=fs:
                g=math.gcd(info.samplerate,fs);data=np.asarray(resample_poly(data,fs//g,info.samplerate//g,axis=0),np.float32)
            begin=start-frame_start/info.samplerate
            base=P.render(lib,data,fs,0);rendered={0:base};values={}
            make_clip=bool(a.clips and fraction==.5 and (path.name=='test 3.wav' or path.name.startswith(('01 - ','06 - '))))
            for flags,name in variants.items():
                candidate=base if flags==0 else P.render(lib,data,fs,flags)
                values[name]=compare(base,candidate,begin,length,fs)
                if make_clip and flags in (0,2,6,14):rendered[flags]=candidate
            row=dict(file=str(path),source_sha256=metadata['sha256'],start=start,end=start+length,
                     decoded_input_sha256=hashlib.sha256(data.tobytes()).hexdigest(),variants=values)
            report['regions'].append(row)
            if make_clip:
                crops={k:aligned(r,begin,length,fs)[0].copy() for k,r in rendered.items()}
                peak=max(T.true_peak_db(x,4) for x in crops.values())
                gain_db=-1-float(peak);gain=10**(gain_db/20)
                clip=dict(source=str(path),source_sha256=metadata['sha256'],start=start,seconds=length,
                          fs=fs,common_playback_gain_db=gain_db,selection='preselected filename, middle excerpt',outputs=[])
                clip_index=len(report['clips'])+1
                for flags,wave in crops.items():
                    target=a.clips/f'{clip_index:02d}_{variants[flags]}.wav'
                    sf.write(str(target),wave*gain,fs,subtype='PCM_24')
                    clip['outputs'].append(dict(path=str(target),flags=flags,sha256=M.digest(target)))
                report['clips'].append(clip)
                (a.clips/'manifest.json').write_text(json.dumps(report['clips'],ensure_ascii=False,indent=2),encoding='utf-8')
            report['execution']='running';report['last_run_elapsed_s']=time.perf_counter()-clock
            a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            print(f"{len(report['regions']):02d}/{len(files)*3} {path.name} @ {start:.3f}s",flush=True)
    report['execution']='completed';assert len(report['regions'])==len(files)*3
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('Corpus study complete; listening/phone claims remain unmeasured.',flush=True)


if __name__=='__main__':main()

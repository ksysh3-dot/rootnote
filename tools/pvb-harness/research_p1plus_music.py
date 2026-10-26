#!/usr/bin/env python3
"""Fixed-window applicability/regression study on user-selected music.

There is no clean virtual-bass oracle for these mixes. Output differences,
phase-control activity and level changes are diagnostics, never noise labels.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import research_p1plus as P
import test_engine as T
import test_harmonic_continuity as H


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def rms(x):return float(np.sqrt(np.mean(np.asarray(x,float)**2)))
def db(x):return float(20*np.log10(max(x,1e-30)))


def compare(base,other,begin,end,fs=48000):
    lo=round(begin*fs)+base['latency'];hi=round(end*fs)+base['latency']
    a,b=base['output'][lo:hi],other['output'][lo:hi]
    sa,sb=base['stem'][lo:hi],other['stem'][lo:hi]
    assert len(a)==round((end-begin)*fs) and a.shape==b.shape
    # This constant whole-window match is a diagnostic only. Processing itself
    # uses identical input, level and limiter settings; no frame normalization.
    gain=rms(a)/max(rms(b),1e-30)
    rows_a,rows_b=base['rows'],other['rows']
    assert rows_a.shape==rows_b.shape
    window=(rows_a[:,0]>=lo)&(rows_a[:,0]<hi)
    ta,tb=H.tracks(rows_a[window]),H.tracks(rows_b[window])
    ha=ta[:,:,14:].reshape(-1,12,7,6);hb=tb[:,:,14:].reshape(-1,12,7,6)
    eligible=np.maximum(ha[:,:,:,1],hb[:,:,:,1])>1e-9
    changed=eligible & (np.abs(ha[:,:,:,3]-hb[:,:,:,3])>1e-7)
    return dict(full_mix_rms_change_db=db(rms(b))-db(rms(a)),
                generated_layer_rms_change_db=db(rms(sb))-db(rms(sa)),
                full_mix_difference_relative_db=db(rms(b-a)/max(rms(a),1e-30)),
                level_matched_difference_relative_db=db(rms(b*gain-a)/max(rms(a),1e-30)),
                generated_layer_difference_relative_db=db(rms(sb-sa)/max(rms(sa),1e-30)),
                baseline_true_peak_4x_dbtp=float(T.true_peak_db(a,4)),
                candidate_true_peak_4x_dbtp=float(T.true_peak_db(b,4)),
                phase_adjustment_changed_harmonic_hops=int(changed.sum()),
                eligible_harmonic_hops=int(eligible.sum()),
                phase_adjustment_changed_fraction=float(changed.sum()/max(1,eligible.sum())),
                analysis_and_track_fields_identical=bool(np.array_equal(ta[:,:,:14],tb[:,:,:14])),
                latency_equal=base['latency']==other['latency'],
                output_bit_exact=bool(np.array_equal(a,b)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--folder',type=Path,action='append',required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args();old=P.api(a.baseline.resolve());new=P.api(a.candidate.resolve())
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    fs=48000;length=8.;preroll=4.;fractions=(.15,.50,.85)
    files=sorted(p for folder in a.folder for p in folder.rglob('*')
                 if p.is_file() and p.suffix.lower() in ('.wav','.flac'))
    if not files:raise ValueError('No WAV/FLAC input found')
    result=dict(schema='pvb.p1plus.music.v1',processing_fs=fs,
                selection=dict(fractions_of_available_start=fractions,seconds=length,preroll_seconds=preroll),
                settings=dict(algorithm=6,vb_level_db=6,out_db=-18,ramp_ms=0),
                quality_verdict='not_established_no_clean_virtual_bass_reference',
                listening_validated=False,device_validated=False,
                baseline_sha256=digest(a.baseline),candidate_sha256=digest(a.candidate),
                files=[],regions=[])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    if a.resume and a.report.exists():
        saved=json.loads(a.report.read_text(encoding='utf-8'))
        for field in ('schema','processing_fs','settings','baseline_sha256','candidate_sha256'):
            assert saved[field]==result[field],('resume_context_changed',field)
        assert saved['selection']['seconds']==length and saved['selection']['preroll_seconds']==preroll
        assert tuple(saved['selection']['fractions_of_available_start'])==fractions
        result=saved
    result['difference_floor_db']=-600
    result['difference_floor_meaning']='Numerical reporting floor; output_bit_exact is authoritative for exact equality.'
    finished={(r['file'],r['start_seconds']) for r in result['regions']}
    prior_elapsed=result.get('elapsed_seconds',0.)
    start_time=time.perf_counter()
    for path in files:
        info=sf.info(str(path))
        if info.channels not in (1,2):raise ValueError(('unsupported_channels',str(path),info.channels))
        if info.duration<length+.25:raise ValueError(('input_too_short',str(path),info.duration))
        metadata=dict(path=str(path),sha256=digest(path),duration=info.duration,
                      samplerate=info.samplerate,channels=info.channels,subtype=info.subtype,
                      prior_processing='unknown')
        previous=[r for r in result['files'] if r['path']==str(path)]
        if previous:assert previous==[metadata],('input_changed_since_resume',str(path))
        else:result['files'].append(metadata)
        for fraction in fractions:
            begin=round(fraction*(info.duration-length-.25),3);end=begin+length
            if (str(path),begin) in finished:continue
            read_start=max(0.,begin-preroll)
            with sf.SoundFile(str(path)) as audio:
                frame_start=round(read_start*info.samplerate)
                audio.seek(frame_start)
                data=audio.read(round((end+.22)*info.samplerate)-frame_start,dtype='float32',always_2d=True)
            if data.shape[1]==1:data=np.repeat(data,2,axis=1)
            read_start=frame_start/info.samplerate
            if info.samplerate!=fs:
                gcd=math.gcd(info.samplerate,fs)
                data=np.asarray(resample_poly(data,fs//gcd,info.samplerate//gcd,axis=0),np.float32)
            local_begin=begin-read_start;local_end=local_begin+length
            baseline=P.render(old,data,fs,0)
            row=dict(file=str(path),start_seconds=begin,end_seconds=end,
                     actual_preroll_seconds=local_begin,decoded_input_sha256=hashlib.sha256(data.tobytes()).hexdigest(),
                     variants={})
            for flags,name in ((1,'residual_history'),(2,'phase_preservation')):
                candidate=P.render(new,data,fs,flags)
                row['variants'][name]=compare(baseline,candidate,local_begin,local_end,fs)
                if flags==2:assert row['variants'][name]['analysis_and_track_fields_identical']
                assert row['variants'][name]['latency_equal']
            result['regions'].append(row)
            result['elapsed_seconds']=prior_elapsed+time.perf_counter()-start_time
            a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            print(f"{len(result['regions']):02d}/{len(files)*3} {path.name} @ {begin:.3f}s phase_activity="
                  f"{row['variants']['phase_preservation']['phase_adjustment_changed_fraction']:.3f}",flush=True)
    print('Completed music applicability study; no perceptual-quality verdict inferred.',flush=True)


if __name__=='__main__':main()

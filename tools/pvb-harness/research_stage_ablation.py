#!/usr/bin/env python3
"""Q1 stage observations and explicit host ablations; never a buzz label."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import test_modulation_research as P
import test_engine as T
from vb_quality import measurement as Q
from vb_quality.stage_capture import COLUMNS,INDEX,core_indices

HERE=Path(__file__).resolve().parent
FLAGS={0:'baseline',1:'hpss_off',2:'gain_off',3:'hpss_gain_off',4:'permission_off',6:'permission_gain_off',
       8:'phase_frozen',10:'phase_gain_off'}

def summarize(r,start=1.25,stop=3.,am=False):
    stages=r['stages'];ix=core_indices(stages);sel=(ix>=int(start*3000))&(ix<int(stop*3000))
    assert np.array_equal(ix,np.arange(len(ix),dtype=np.uint64)),'noncontiguous stage clock'
    assert np.isfinite(stages).all()
    z=stages[sel];index=INDEX
    assert np.array_equal(stages[:,index['pre_filter']],stages[:,index['tonal_after_gain']]+stages[:,index['percussion']])
    stats=dict(core_samples=len(stages),stage_rms_dbfs={},host_peak_dbfs=T.true_peak_db(r['output']),
               limiter_gr_db=float(r['meters'][T.M['LIM_GR_DB']]),latency=r['latency'])
    for name in ('band_delayed191','original_h','selected_h','raw_grain','tonal_after_gain','pre_filter','post_filter'):
        stats['stage_rms_dbfs'][name]=float(20*np.log10(max(float(np.sqrt(np.mean(z[:,index[name]]**2))),1e-30)))
    stats['gain']=dict(min=float(z[:,index['applied_gain']].min()),mean=float(z[:,index['applied_gain']].mean()),
                       max=float(z[:,index['applied_gain']].max()))
    if am:
        metrics={}
        for name,order in (('band_delayed191',1),('original_h',1),('selected_h',1),('raw_grain',3),
                           ('tonal_after_gain',3),('post_filter',3)):
            metrics[name]=Q.am_metric(stages[:,index[name]],3000,55,order,7,.7,1,start=start,stop=stop)
        stats['am_stage_metrics']=metrics
        stats['output_am_harmonics']=Q.am_harmonics(r['stem'],48000,55,7,.7,start=start,stop=stop,
                                                   latency=r['latency']/48000,temporal=True)
    return stats

def invariance(lib,baseline=None):
    result=[]
    for fs in (44100,48000):
        t=np.arange(fs)/fs;x=.12*np.cos(2*np.pi*55*t)+.04*np.cos(2*np.pi*110*t+.3)
        for algo in range(6):
            a=P.render(lib,x,fs=fs,algo=algo)
            b=P.render(lib,x,fs=fs,algo=algo,stage_flags=0)
            assert np.array_equal(a['output'],b['output']) and np.array_equal(a['stem'],b['stem']),(fs,algo,'capture changed audio')
            if baseline:
                old=P.render(baseline,x,fs=fs,algo=algo)
                assert np.array_equal(a['output'],old['output']),(fs,algo,'default changed')
            result.append(dict(sample_rate=fs,algorithm=algo,capture_bit_exact=True,baseline_bit_exact=bool(baseline)))
    try:P.render(lib,x,stage_flags=0,stage_capacity=4)
    except ValueError as e:assert 'overflow' in str(e)
    else:raise AssertionError('stage overflow silently accepted')
    return result

def run(args):
    lib=P.api(args.lib);old=P.api(args.baseline) if args.baseline else None
    checks=invariance(lib,old);fs=48000;t=np.arange(int(3.4*fs))/fs
    signals=dict(am7=.15*(1+.7*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*55*t),steady=.15*np.cos(2*np.pi*55*t),
                 fm7=Q.fm_tone(fs,len(t),55,7,35),close_pair=.10*np.cos(2*np.pi*55*t)+.07*np.cos(2*np.pi*58*t+.6))
    result=dict(schema='pvb.phase2.stage_ablation.v1',stage_schema_version=3,columns=COLUMNS,
                clock='current3kHz core index; stage-specific source/filter delays differ; intermediate phase not gated',
                settings=dict(fs=fs,algo=4,layer_db=6,output_db=-18,tonal_only=True,mode=3,seconds=3.4),
                invariance=checks,cases={},listening='not_evaluated',device='not_evaluated')
    for name,x in signals.items():
        modes={}
        for c1 in ((False,True) if name=='am7' else (True,)):
            for flags in (FLAGS if name=='am7' else (0,1,2,3)):
                label=('c1_' if c1 else '')+FLAGS[flags]
                r=P.render(lib,x,3,c1,tonal=True,stage_flags=flags)
                modes[label]=summarize(r,am=name=='am7')
                print(name,label,modes[label].get('gain'),flush=True)
        result['cases'][name]=modes
    result['library_sha256']=hashlib.sha256(Path(args.lib).read_bytes()).hexdigest()
    result['source_sha256']={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('research_stage_ablation.py','vb_quality/measurement.py','vb_quality/stage_capture.py')}
    Path(args.report).write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lib',default=str(HERE/'build/libpvbcapi.so'));p.add_argument('--baseline');p.add_argument('--report',default='stage-ablation.json');run(p.parse_args())

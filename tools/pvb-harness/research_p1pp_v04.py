#!/usr/bin/env python3
"""P1++ v0.4 research variants (impact mode 8 plus v0.4 flags) against P1+ and P1++ v0.3.

Each variant is "label=impact_mode:v04_flags". Development uses every cohort seen so far (impact seeds 2026102608-11,
short notes 2026102606 and 2026102612); --final runs the holdout made for v0.4 (impact seed 2026102613, notes
2026102614) once. Counts use the 0.1 dB metric-change rule and always give the denominator; level repeats of one
waveform are not independent samples. The early-tail split (bed-shaped vs not the bed) is from
research_p1pp_impacts.score; its controls are check_p1pp_tail_split.py. Nothing here is a listening or device result.
"""
import argparse,collections,hashlib,json,os,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import research_p1plus as P
from check_p1hq_primary_envelopes import fixtures as notes,primary,score
from check_p1hq_envelopes import envelope
from p1plus_paths import default_library
HERE=Path(__file__).resolve().parent
KEYS=('pre_stationary_residual_per_input_db','early_tail_energy_per_input_db','early_tail_stationary_residual_per_input_db',
      'early_tail_bed_shaped_per_input_db','early_tail_nonbed_per_input_db','late_tail_stationary_residual_per_input_db')
SHORT=dict(zip(KEYS,('pre','early_energy','early_stat','early_bed','early_nonbed','late')))


def compare(a,b):
    """a, b: {(name, level): case}. Positive: b has less of the metric than a."""
    out={}
    common=sorted(set(a)&set(b))
    for k in KEYS:
        d=np.array([a[c][k]-b[c][k] for c in common])
        out[k]=dict(settings=len(d),better=int((d>.1).sum()),worse=int((d<-.1).sum()),small=int((abs(d)<=.1).sum()),
                    median_db=float(np.median(d)),best_db=float(d.max()),worst_db=float(d.min()))
    late={lab:[v[c]['late_absolute_residual_rms_dbfs'] for c in common] for lab,v in (('a',a),('b',b))}
    out['late_absolute_residual_rms_dbfs']={lab:dict(min=float(min(v)),median=float(np.median(v)),max=float(max(v))) for lab,v in late.items()}
    return out


def run_cohort(lib,out,cohort,mode,flags):
    d=out/f'{cohort}-{mode}-{flags}'
    if not (d/'results.json').is_file():
        env=dict(os.environ,P1PP_V04=str(flags),OPENBLAS_NUM_THREADS='1')
        subprocess.run([sys.executable,str(HERE/'research_p1pp_recovery.py'),'--library',str(lib),'--out',str(d),
                        '--set',cohort,'--modes',str(mode)],check=True,stdout=subprocess.DEVNULL,env=env)
        for f in d.glob('*.npz'):f.unlink()
    r=json.loads((d/'results.json').read_text())
    return r,{(c['name'],c['input_level_dbfs']):c for c in r['cases']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--out',type=Path,required=True);p.add_argument('--final',action='store_true')
    p.add_argument('--variant',action='append',required=True,help='label=impact_mode:v04_flags')
    p.add_argument('--jobs',type=int,default=8);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    variants={'P1+':(0,0),'P1++ v0.3':(8,0)}
    for v in a.variant:
        label,spec=v.split('=');m,f=spec.split(':');variants[label]=(int(m),int(f))
    cohorts=('holdout2',) if a.final else ('inspected','new','confirm','holdout')
    jobs={(c,lab):(c,*mf) for c in cohorts for lab,mf in variants.items()}
    with ThreadPoolExecutor(a.jobs) as ex:
        futures={k:ex.submit(run_cohort,a.library,a.out,*v) for k,v in jobs.items()}
        results={k:f.result() for k,f in futures.items()}
    impacts={}
    for c in cohorts:
        meta=results[(c,'P1+')][0];base=results[(c,'P1+')][1];v03=results[(c,'P1++ v0.3')][1]
        impacts[c]=dict(seed=meta['seed'],waveforms=meta['independent_waveforms'],levels=meta['levels_per_waveform'],
                        vs_p1plus={lab:compare(base,results[(c,lab)][1]) for lab in variants if lab!='P1+'},
                        vs_v03={lab:compare(v03,results[(c,lab)][1]) for lab in variants if lab not in ('P1+','P1++ v0.3')})
    lib=P.api(a.library.resolve());fs=48000;env=[]
    groups=((2026102614,12,'holdout2'),) if a.final else ((2026102606,6,'tuning'),(2026102612,12,'holdout_v03'))
    saved=os.environ.get('P1PP_V04')
    for seed,count,group in groups:
        for name,src,e,desc in notes(fs,seed,count):
            f=desc['frequency'];k=primary(f);t=np.arange(len(src))/fs
            ref=envelope(e*np.cos(2*np.pi*k*f*t),fs,k*f,.35*f)[900:12000];row=dict(group=group,seed=seed,name=name,frequency=f,harmonic=k)
            for label,(mode,flags) in variants.items():
                os.environ['P1PP_V04']=str(flags)
                r=P.render(lib,np.r_[src,np.zeros(fs)],fs,6,impact_mode=mode)
                w=r['stem'][r['latency']:r['latency']+len(src),0]
                row[label]=float(100*10**(score(envelope(w,fs,k*f,.35*f)[900:12000],ref)['shape_error_db']/20))
            env.append(row)
    if saved is None:os.environ.pop('P1PP_V04',None)
    else:os.environ['P1PP_V04']=saved
    summary=dict(schema='pvb.p1pp.v04.v1',library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                 variants={k:dict(impact_mode=m,v04_flags=f) for k,(m,f) in variants.items()},final=a.final,
                 change_rule='metric change > 0.1 dB counted better/worse; |change| <= 0.1 dB small. Not a hearing threshold.',
                 impacts=impacts,short_note_envelope_error_rms_percent=env,listening_validation=False,device_validation=False)
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for c,v in impacts.items():
        for ref in ('vs_p1plus','vs_v03'):
            for lab,x in v[ref].items():
                print(c,ref,lab,{SHORT[k]:(x[k]['better'],x[k]['worse'],x[k]['small'],round(x[k]['worst_db'],2)) for k in KEYS})
    labels=list(variants)
    for g in sorted({r['group'] for r in env}):
        rows=[r for r in env if r['group']==g]
        print(g,'note envelope error %:',' | '.join(f"{r['name'][-2:]} "+' '.join(f'{r[l]:.2f}' for l in labels) for r in rows))
        for l in labels[2:]:
            d=np.array([r['P1++ v0.3']-r[l] for r in rows])
            print(' ',l,'vs v0.3 lower/higher/same(0.1 pt):',int((d>.1).sum()),int((d<-.1).sum()),int((abs(d)<=.1).sum()),
                  'vs P1+:',int((np.array([r['P1+']-r[l] for r in rows])>.1).sum()),int((np.array([r['P1+']-r[l] for r in rows])<-.1).sum()))


if __name__=='__main__':main()

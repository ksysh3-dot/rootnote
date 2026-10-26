#!/usr/bin/env python3
"""P1++ v0.3 (impact mode 8) against P1+ (mode 0) and P1++ v0.2 (mode 4).

Runs the impact cohorts of research_p1pp_recovery.py (development seed 2026102608, selection 2026102609,
confirmation 2026102610; mode 8 was tuned while looking at all three) and the six short notes of
check_p1hq_primary_envelopes.py (also seen while tuning), then a holdout generated after the rule was fixed and
run once: impact seed 2026102611 (12 waveforms) and 12 short notes from seed 2026102612.
Counts use the same 0.1 dB metric-change rule as RESULTS_KO.md and always give the denominator; level repeats of
one waveform are not independent samples. Nothing here is a listening or device result.
"""
import argparse,collections,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
import research_p1plus as P
from check_p1hq_primary_envelopes import fixtures as notes,primary,score
from check_p1hq_envelopes import envelope
from p1plus_paths import default_library
HERE=Path(__file__).resolve().parent
KEYS=('pre_stationary_residual_per_input_db','early_tail_stationary_residual_per_input_db','late_tail_stationary_residual_per_input_db')


def compare(cases,a,b):
    rows=collections.defaultdict(dict)
    for c in cases:rows[(c['name'],c['input_level_dbfs'])][c['mode']]=c
    out={}
    for k in KEYS:
        d=np.array([m[a][k]-m[b][k] for m in rows.values()])  # positive: b has less residual than a
        out[k]=dict(settings=len(d),better=int((d>.1).sum()),worse=int((d<-.1).sum()),small=int((abs(d)<=.1).sum()),
                    median_db=float(np.median(d)),best_db=float(d.max()),worst_db=float(d.min()))
    late={m:[v[m]['late_absolute_residual_rms_dbfs'] for v in rows.values()] for m in (a,b)}
    out['late_absolute_residual_rms_dbfs']={str(m):dict(min=float(min(v)),median=float(np.median(v)),max=float(max(v))) for m,v in late.items()}
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cohorts={}
    for cohort in ('inspected','new','confirm','holdout'):
        d=a.out/cohort
        subprocess.run([sys.executable,str(HERE/'research_p1pp_recovery.py'),'--library',str(a.library),'--out',str(d),
                        '--set',cohort,'--modes','0','4','8'],check=True,stdout=subprocess.DEVNULL)
        r=json.loads((d/'results.json').read_text());cases=r['cases']
        cohorts[cohort]=dict(seed=r['seed'],waveforms=r['independent_waveforms'],levels=r['levels_per_waveform'],
                             v03_vs_p1plus=compare(cases,0,8),v03_vs_v02=compare(cases,4,8),v02_vs_p1plus=compare(cases,0,4))
        for f in d.glob('*.npz'):f.unlink()
    lib=P.api(a.library.resolve());fs=48000;env=[]
    for seed,count,group in ((2026102606,6,'tuning'),(2026102612,12,'holdout')):
      for name,src,e,desc in notes(fs,seed,count):
          f=desc['frequency'];k=primary(f);t=np.arange(len(src))/fs
          ref=envelope(e*np.cos(2*np.pi*k*f*t),fs,k*f,.35*f)[900:12000];row=dict(group=group,seed=seed,name=name,frequency=f,harmonic=k)
          for label,mode in (('P1+',0),('P1++ v0.2',4),('P1++ v0.3',8)):
              r=P.render(lib,np.r_[src,np.zeros(fs)],fs,6,impact_mode=mode)
              w=r['stem'][r['latency']:r['latency']+len(src),0]
              row[label]=float(100*10**(score(envelope(w,fs,k*f,.35*f)[900:12000],ref)['shape_error_db']/20))
          env.append(row)
    summary=dict(schema='pvb.p1pp.v03.v1',library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                 models={'P1+':'flags 6, impact 0','P1++ v0.2':'flags 6, impact 4','P1++ v0.3':'flags 6, impact 8 (steady 3 hops, amplitude >= 0.97 of the last hop, strength >= 0.4 of the hop maximum; own stationary fit still required)'},
                 change_rule='metric change > 0.1 dB counted better/worse; |change| <= 0.1 dB small. Not a hearing threshold.',
                 impacts=cohorts,short_note_envelope_error_rms_percent=env,
                 listening_validation=False,device_validation=False)
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for c,v in cohorts.items():
        for pair in ('v03_vs_p1plus','v03_vs_v02','v02_vs_p1plus'):
            print(c,pair,{k.split('_')[0]:(x['better'],x['worse'],x['small'],round(x['worst_db'],2)) for k,x in v[pair].items() if k in KEYS})
    for r in env:print(r['group'],r['name'],{k:round(v,2) for k,v in r.items() if k.startswith('P1')})


if __name__=='__main__':main()

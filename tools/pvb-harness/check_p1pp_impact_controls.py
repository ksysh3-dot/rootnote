import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
import research_p1plus as P
import check_p1hq_primary_envelopes as E
from vb_quality import measurement as Q
import test_engine as T

from p1plus_paths import default_library
p=argparse.ArgumentParser(description='P1++ impact engineering and legitimate-envelope controls')
p.add_argument('--library',type=Path,default=default_library());p.add_argument('--baseline',type=Path)
p.add_argument('--out',type=Path,required=True);args=p.parse_args()
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
lib=P.api(args.library.resolve());old=P.api(args.baseline.resolve()) if args.baseline else None
result=dict(schema='pvb.p1pp.impact_controls.v1',
            library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
            comparison_library_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,
            engineering=[],notes=[],am=[])
for fs in (44100,48000):
 t=np.arange(3*fs)/fs;x=.1*np.cos(2*np.pi*55*t)*(1+.7*np.sin(2*np.pi*7*t))
 a=P.render(lib,x,fs,6)
 if old is not None:
  b=P.render(old,x,fs,6);assert np.array_equal(a['output'],b['output'])
 for mode in (1,2):
  r=P.render(lib,x,fs,6,impact_mode=mode)
  chunk=P.render(lib,x,fs,6,block=1379,impact_mode=mode)
  assert np.array_equal(r['output'],chunk['output']) and r['latency']==a['latency']
  no_capture=P.render(lib,x,fs,6,capture=False,impact_mode=mode)
  assert np.array_equal(r['output'],no_capture['output'])
  future=x.copy();future[round(1.7*fs):]*=-1
  changed=P.render(lib,future,fs,6,impact_mode=mode)
  assert np.array_equal(r['output'][:round(1.7*fs)],changed['output'][:round(1.7*fs)])
  e=T.Engine(lib,fs,vb_on=1,vb_algo=6,ramp_ms=0)
  assert lib.pvb_set_p1pp_impact_research(e.h,mode)==1
  assert lib.pvb_set_p1pp_impact_research(e.h,3)==0
  e.process(T.stereo(x[:fs]));lib.pvb_reset(e.h)
  assert np.max(abs(e.process(np.zeros((fs,2),np.float32))))<1e-7;e.close()
  for algo in (7,8,9,10):
   x0=P.render(lib,x[:fs],fs,6,algo=algo)
   x1=P.render(lib,x[:fs],fs,6,algo=algo,impact_mode=mode)
   assert np.array_equal(x0['output'],x1['output'])
  result['engineering'].append(dict(fs=fs,mode=mode,mode0_bit_exact=True if old is not None else None,block_and_capture_invariant=True,prefix_causal=True,reset=True,other_profiles_unaffected=True,latency=r['latency']))
 print('engineering',fs,'PASS',flush=True)
fs=48000
for name,x,env,desc in E.fixtures(fs):
 f=desc['frequency'];k=E.primary(f);t=np.arange(len(x))/fs
 ref=E.envelope(env*np.cos(2*np.pi*k*f*t),fs,k*f,.35*f)[900:12000];v={}
 for mode in (0,1,2):
  r=P.render(lib,np.r_[x,np.zeros(fs)],fs,6,impact_mode=mode)
  y=r['stem'][r['latency']:r['latency']+len(x),0]
  measured=E.envelope(y,fs,k*f,.35*f)[900:12000]
  try: v[str(mode)]=E.score(measured,ref)
  except ValueError:v[str(mode)]=dict(status='missing_harmonic')
  v[str(mode)]['stem_energy']=float(np.sum(y.astype(float)**2))
 result['notes'].append(dict(name=name,variants=v));print(name,{m:round(q.get('shape_error_db',999),2) for m,q in v.items()},flush=True)
for rate in (3.,7.,11.):
 t=np.arange(5*fs)/fs;x=.12*(1+.7*np.sin(2*np.pi*rate*t))*np.sin(2*np.pi*55*t+.2);v={}
 for mode in (0,1,2):
  r=P.render(lib,x,fs,6,impact_mode=mode)
  v[str(mode)]=Q.am_metric(r['stem'],fs,55,3,rate,.7,1,start=1.25,stop=3.75,latency=r['latency']/fs,reference_peak=.12,temporal=True)
 result['am'].append(dict(rate=rate,variants=v));print('AM',rate,{m:q.get('depth') for m,q in v.items()},flush=True)
(OUT/'controls.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

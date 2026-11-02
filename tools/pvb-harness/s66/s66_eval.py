"""Native causal DEV87 evaluation. Originals read in place, no render audio saved."""
import sys,os
sys.dont_write_bytecode=True
from pathlib import Path
H=Path.home();O=H/'r3a-dev/plan16/s66';P=O.parent
sys.path.insert(0,str(O));from common66 import *
sys.path.insert(0,'/mnt/c/Users/ksysh/rootnote-duo/gpt-cli');import s66_phone_v2 as PH
import ctypes as C,gc,time,argparse
from concurrent.futures import ThreadPoolExecutor
from scipy.signal import periodogram
MODEL=json.loads((O/'PCM_PHONE.json').read_text());HIGH=json.loads((O/'C3_FROZEN.json').read_text())['high_half']
BASE=P/'s50/build_release/libpvbcapi.so';PRIME=49152;DETAIL=['Track00001','Track00016','Track00030']
def capture(x,name='B',block=256,path=LIB):
 lib=C55.bind(path);e=C55.T.Engine(lib,FS,vb_on=1,vb_algo=6,vb_level_db=0,out_db=-5,ramp_ms=0)
 if hasattr(lib,'pvb_set_allocation66'):
  lib.pvb_set_allocation66.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int];lib.pvb_set_allocation66.restype=C.c_int
  assert lib.pvb_set_allocation66(e.h,{'C1':1,'C2':2,'C3':3}.get(name,0),int(HIGH),20 if name=='T' else 100)==1
 else:assert name in ['P1','B']
 C55.setup(e,lib,name!='P1')
 xx=np.concatenate([np.zeros((PRIME,2),np.float32),x,np.zeros((FS,2),np.float32)])
 y=np.empty_like(xx);l=np.empty_like(xx);nf=32+lib.pvb_param_count();tr=np.empty(nf,np.float32)
 lb=np.empty(block*2,np.float32);fb=np.empty_like(lb);lib.pvb_set_diagnostic_capture(e.h,1);gr=0.;start=time.process_time()
 try:
  for a in range(0,len(xx),block):
   z=xx[a:a+block];lib.pvb_process(e.h,z.ctypes.data_as(C55.T.FP),len(z))
   assert lib.pvb_copy_diagnostic(e.h,lb.ctypes.data_as(C55.T.FP),fb.ctypes.data_as(C55.T.FP),2*len(z),tr.ctypes.data_as(C55.T.FP),nf)==1
   y[a:a+len(z)]=fb[:2*len(z)].reshape(-1,2);l[a:a+len(z)]=lb[:2*len(z)].reshape(-1,2);gr=max(gr,float(tr[22]))
  lat=e.latency()
 finally:e.close()
 pk=truepeak(y);meta=dict(latency=lat,tp8_dbfs=20*np.log10(max(pk,1e-30)),max_limiter_gr_db=gr,cpu_rtf=(time.process_time()-start)/(len(xx)/FS),pcm_sha256=hashlib.sha256(y.tobytes()).hexdigest(),raw_frames=len(y))
 return y,l,meta
def proof():
 t=np.arange(FS*3)/FS;rng=np.random.default_rng(66);x=np.column_stack([.12*np.sin(2*np.pi*63*t),.10*np.sin(2*np.pi*63*t+.2)]).astype(np.float32)
 x+=rng.normal(0,.005,x.shape).astype(np.float32);rows=[]
 for name in ['P1','B']:
  y,l,e=capture(x,name);yb,lb,eb=capture(x,name,path=BASE)
  assert np.array_equal(y,yb) and np.array_equal(l,lb) and e['latency']==eb['latency'];rows.append(dict(test='V0',name=name,pcm_equal=True,layer_equal=True,latency=e['latency']))
 for name in ['T','C1','C2','C3']:
  y,l,e=capture(x,name);yb,lb,eb=capture(x,name,block=37)
  assert np.array_equal(y,yb) and np.array_equal(l,lb) and e['latency']==eb['latency']==7140
  xx=x.copy();xx[2*FS:]*=-.5;yc,lc,ec=capture(xx,name)
  through=PRIME+2*FS
  assert np.array_equal(y[:through],yc[:through]);rows.append(dict(test='block37_256_and_prefix_causality',name=name,pcm_equal=True,layer_equal=True,latency=e['latency']))
 dump(O/'V0_AND_CAUSALITY.json',rows);print('V0/causality PASS',flush=True)
def thread_proof():
 t=np.arange(FS*3)/FS;rng=np.random.default_rng(6602);x=np.column_stack([.2*np.sin(2*np.pi*63*t),.1*np.sin(2*np.pi*79*t)]).astype(np.float32);x+=rng.normal(0,.01,x.shape).astype(np.float32)
 names=['P1','B','T','C1','C2','C3'];serial={n:capture(x,n) for n in names};results=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  jobs={n:pool.submit(capture,x,n) for n in names}
  for n in names:
   v=jobs[n].result();ref=serial[n];assert np.array_equal(v[0],ref[0]) and np.array_equal(v[1],ref[1]);results.append(dict(variant=n,pcm_equal=True,layer_equal=True,latency=v[2]['latency']))
 dump(O/'PREFETCH_BIT_PROOF.json',results);print('serial/prefetch bit identity PASS',flush=True)
def env(z,step=48):
 z=sosfilt(butter(3,[150,600],btype='bandpass',fs=FS,output='sos'),z,axis=0);pw=np.mean(z*z,axis=1);cs=np.r_[0.,np.cumsum(pw)];ii=np.arange(0,len(z),step);lo=np.maximum(0,ii-239)
 return np.maximum(0,(cs[ii+1]-cs[lo])/(ii-lo+1))
def extra_metrics(y,notes,reference=None):
 e=env(y);stable=np.zeros(len(e)//10,bool);events=onset_events(notes);att=timing(e,events,reference['attack_events'] if reference else None)
 mod=[[],[],[]]
 for s,en,f,_ in notes:
  a=max(200,int((s+.1)*100));b=min(2900,int((en-.1)*100))
  if b-a<50:continue
  stable[a:b]=True;v=np.sqrt(e[::10][a:b]);v=v/max(v.mean(),1e-30)-1
  hz,pp=periodogram(v,100,window='hann',scaling='density');df=100/len(v)
  for j,(lo,hi) in enumerate([(1,4),(4,10),(10,30)]):mod[j].append(float(pp[(hz>=lo)&(hz<hi)].sum()*df))
 er=e[::10][:len(stable)];ref=reference['env10'] if reference else er;gain=PH.db(er)-PH.db(ref)
 active=stable&(ref>max(float(np.percentile(ref[200:2900],95))*1e-3,1e-30))
 def run(mask):
  d=np.diff(np.r_[False,mask,False].astype(int));a=np.flatnonzero(d==1);b=np.flatnonzero(d==-1);return [(int(i),int(j)) for i,j in zip(a,b) if j-i>=3]
 runs=run(active&(gain<=-12));r6=run(active&(gain<=-6));loss=[]
 for s,en,f,_ in notes:
  a=max(200,int((s+.05)*100));b=min(2900,int((en-.05)*100))
  if b-a>=3:loss.append(float(np.median(gain[a:b]))<=-12)
 paired={}
 for k in ['local10_ms','fixed10_ms']:
  rr=reference['attack_events'] if reference else att;vs=[v[k]-r[k] for r,v in zip(rr,att) if r[k] is not None and v[k] is not None]
  paired[k]=dict(n=len(vs),median_ms=float(np.median(vs)) if vs else None,p95_ms=float(np.percentile(vs,95)) if vs else None)
 sl=y[2*FS:29*FS];rms=float(np.sqrt(np.mean(sl*sl)));pk=float(abs(sl).max())
 out=dict(N2_envelope=[float(np.median(v)) if v else None for v in mod],N2_segments=len(mod[0]),gap_pp=100*sum(b-a for a,b in runs)/int(active.sum()) if active.any() else None,gap6_pp=100*sum(b-a for a,b in r6)/int(active.sum()) if active.any() else None,loss_pp=100*float(np.mean(loss)) if loss else None,gap_events=len(runs),eligible_bins=int(active.sum()),attack=paired,rms_dbfs=20*np.log10(max(rms,1e-30)),crest_db=20*np.log10(max(pk,1e-30)/max(rms,1e-30)),body_power=float(np.mean(er[200:2900])))
 return out,dict(env10=er,attack_events=att)
def deltas(a,b):
 out={}
 for k in ['Qweak','Qwhole','family_power','family_layer_power','body_power']:
  out[k+'_db']=ratio(a.get(k),b.get(k))
 for k in ['F','N1_mixed_db','gap_pp','gap6_pp','loss_pp','rms_dbfs','crest_db']:
  out[k+'_delta']=a[k]-b[k] if a.get(k) is not None and b.get(k) is not None else None
 out['N2_envelope_db']=[ratio(x,y) for x,y in zip(a['N2_envelope'],b['N2_envelope'])]
 for k in ['local10_ms','fixed10_ms']:out['attack_'+k]=a['attack'][k]
 return out
def evaluate_one(key):
 tic=time.time();x,bass,notes,plan,masks,src=load_dev(key);rows={};refs={};reftime={}
 names=['P1','B','T','C1','C2','C3'];pool=ThreadPoolExecutor(max_workers=2);jobs={name:pool.submit(capture,x,name) for name in names}
 for name in names:
  raw,layer,eng=jobs.pop(name).result();a=PRIME+eng['latency'];y=raw[a:a+len(x)].copy();l=layer[a:a+len(x)].copy();del raw,layer
  if name=='P1':basepk=eng['tp8_dbfs']
  eng['tp_delta_P1_db']=eng['tp8_dbfs']-basepk;eng['tp_pass']=eng['tp_delta_P1_db']<=.5
  contexts={}
  for ctx,level in [('digital',0),('phone20H',0),('phone20L',-12)]:
   yy,ll=(y,l) if ctx=='digital' else PH.transfer2(y*10**(level/20),MODEL,layer=l*10**(level/20))
   v,_=Z.direct_metrics((yy-ll)/G,ll/G,plan,masks['good'],masks['family'],masks['band'],masks['weak'])
   # Frozen family/good bins are P1-only metadata; never reselected after phone transfer.
   v['correct_ratio']=v['Qwhole']/max(v['good_power']+v['bad_power'],1e-30)
   ex,et=extra_metrics(yy,notes,reftime.get(ctx));v.update(ex)
   if name=='P1':refs[ctx]=v;reftime[ctx]=et
   contexts[ctx]=dict(metrics=v,versus_P1=deltas(v,refs[ctx]))
   if name!='P1':contexts[ctx]['versus_B']=deltas(v,rows['B']['contexts'][ctx]['metrics']) if name!='B' else deltas(v,v)
   # Recompute attack vs B using the actual matched rise events, rather than subtract percentile summaries.
   if name=='B':reftime['B_'+ctx]=et
   if name not in ['P1','B']:
    for k in ['local10_ms','fixed10_ms']:contexts[ctx]['versus_B']['attack_'+k]=paired_timing(reftime['B_'+ctx]['attack_events'],et['attack_events'],k)
   del yy,ll
  rows[name]=dict(engine=eng,contexts=contexts);del y,l;gc.collect()
  wd=contexts['digital']['versus_P1']['Qweak_db'];print(key,name,'weak/P1',round(wd,4) if wd is not None else 'N/A','TP/P1',round(eng['tp_delta_P1_db'],4),flush=True)
 pool.shutdown()
 assert sha(src['item']['mix'])==src['mix_sha256']
 dump(O/'results'/(key+'.json'),dict(id=key,variants=rows,source=src,mask_sha256=sha(P/'s53/masks'/(key+'.npz')),elapsed_s=time.time()-tic,weak_frames=int(masks['weak'].sum())))
def main():
 pa=argparse.ArgumentParser();pa.add_argument('--proof',action='store_true');pa.add_argument('--thread-proof',action='store_true');pa.add_argument('--id');pa.add_argument('--rest',action='store_true');pa.add_argument('--shard',type=int,default=0);pa.add_argument('--shards',type=int,default=1);args=pa.parse_args()
 if args.proof:proof();return
 if args.thread_proof:thread_proof();return
 available=sorted(os.sched_getaffinity(0));chosen=available[args.shard*3:(args.shard+1)*3] if args.shards==2 else available[:6]
 os.sched_setaffinity(0,set(chosen))
 log=(O/('worker'+str(args.shard)+'.log')).open('a',encoding='utf-8',buffering=1)
 class Tee:
  def write(self,s):sys.__stdout__.write(s);log.write(s)
  def flush(self):sys.__stdout__.flush();log.flush()
 sys.stdout=Tee()
 if not (O/'EVALUATION_LOCK.json').exists():
  dump(O/'EVALUATION_LOCK.json',dict(utc=now(),registration_sha256=sha(O/'REGISTRATION.json'),amendment_sha256=sha(O/'MODEL_CORRECTION_v2_REGISTRATION.json'),domain_amendment_sha256=sha(O/'MODEL_DOMAIN_v21_REGISTRATION.json'),files={str(p):sha(p) for p in [Path(__file__),O/'PCM_PHONE.json',O/'C3_FROZEN.json',LIB,O/'engine.diff',O/'common66.py',Path(PH.__file__)]},model_gate=json.loads((O/'WAVEFORM_CLOSURE_v2.json').read_text())['usable20cm_exploratory'],v21_candidate_results_seen=False,earlier_candidate_results_seen=True,workers=2,blas_threads=1,total_affinity_cpus=6))
 for index,key in enumerate([args.id] if args.id else DETAIL+[v for v in IDS if v not in DETAIL]):
  if index%args.shards!=args.shard:continue
  if args.rest and (O/'results'/(key+'.json')).exists():continue
  evaluate_one(key);gc.collect()
 dump(O/('RUN_COMPLETE_'+str(args.shard)+'.json'),dict(utc=now(),result_files=len(list((O/'results').glob('*.json')))))
if __name__=='__main__':main()

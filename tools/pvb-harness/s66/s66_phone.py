"""PCM_PHONE: coarse causal envelope/history evaluator, no audio persistence."""
import os,sys
sys.dont_write_bytecode=True
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:6]))
import json,hashlib,datetime,csv
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter,sosfilt,periodogram
from scipy.optimize import lsq_linear
H=Path.home();P=H/'r3a-dev/plan16';O=P/'s66';ROOT=Path('/mnt/c/Users/ksysh/rootnote-duo');L=ROOT/'listen/s59'
FS=48000;STEP=480;BANDS=[(20,150),(150,300),(300,600),(600,3000),(3000,20000)]
SOS=[butter(1,f,fs=FS,output='sos') for f in (150,300,600,3000)]
def dump(n,v):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n',encoding='utf-8')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def db(x):return 10*np.log10(np.maximum(x,1e-30))
def split(x,states=None):
 if states is None:states=[np.zeros((1,2,x.shape[1])) for _ in SOS]
 lp=[];st=[]
 for s,z in zip(SOS,states):
  y,zz=sosfilt(s,x,axis=0,zi=z);lp.append(y);st.append(zz)
 return [lp[0],lp[1]-lp[0],lp[2]-lp[1],lp[3]-lp[2],x-lp[3]],st
def powers(x,states=None):
 bands,states=split(x,states);n=len(x)//STEP
 return np.array([np.mean(z[:n*STEP].reshape(n,STEP,-1)**2,axis=(1,2)) for z in bands]).T,states
def history(total,attack,release):
 target=np.maximum(0,db(np.r_[1e-12,total[:-1]])+35);state=0.;v=np.empty(len(target))
 aa=np.exp(-.01/attack);rr=np.exp(-.01/release)
 for i,t in enumerate(target):
  a=aa if t>state else rr;state=a*state+(1-a)*t;v[i]=state
 return v
def features(p,total,attack,release):
 prev=np.clip(db(np.vstack([np.full((1,5),1e-12),p[:-1]])),-80,0)
 dx=prev+30;hist=history(total,attack,release)
 return np.minimum(dx,0),np.maximum(dx,0),hist
def gains(p,total,model,distance='20cm'):
 lo,hi,h=features(p,total,model['attack_s'],model['release_s']);gg=[]
 for j,v in enumerate(model['bands']):
  z=v['intercept20_db']+(v['slope_low']-1)*lo[:,j]+(v['slope_high']-1)*hi[:,j]-v['history_coefficient']*h
  if distance=='50cm':z+=v['offset50_db']
  gg.append(np.clip(z,-100,-10))
 return np.array(gg).T
def transfer(x,model,distance='20cm',layer=None):
 # No signal delay. Frame gain depends only on the previous completed10ms frame.
 n=len(x);nn=(n+STEP-1)//STEP*STEP;xx=np.pad(np.asarray(x,float),((0,nn-n),(0,0)))
 bp,st=split(xx);pw=np.array([np.mean(v.reshape(-1,STEP,x.shape[1])**2,axis=(1,2)) for v in bp]).T
 total=np.mean(xx.reshape(-1,STEP,x.shape[1])**2,axis=(1,2));gd=gains(pw,total,model,distance)
 gs=10**(np.repeat(gd,STEP,axis=0)/20);y=sum(v*gs[:,j,None] for j,v in enumerate(bp))[:n]
 if layer is None:return y
 ll=np.pad(np.asarray(layer,float),((0,nn-n),(0,0)));lb,_=split(ll);ly=sum(v*gs[:,j,None] for j,v in enumerate(lb))[:n]
 return y,ly
def affine_read(f,sync,start,n):
 ix=(sync['offset_s']+sync['clock_ratio']*(start+np.arange(n)/FS))*FS
 a=int(np.floor(ix[0]));b=int(np.ceil(ix[-1]))+2;f.seek(a);z=f.read(b-a,dtype='float64',always_2d=True)
 q=ix-a;k=np.floor(q).astype(int);fr=q-k
 return z[k]*(1-fr[:,None])+z[k+1]*fr[:,None]
def extract():
 m=json.loads((L/'segment_map.json').read_text());n=m['samples']//STEP
 dp=[];total=[];st=None
 with sf.SoundFile(m['path']) as f:
  for a in range(0,m['samples'],FS*10):
   x=f.read(min(FS*10,m['samples']-a),dtype='float64',always_2d=True);p,st=powers(x,st);dp.append(p);total.extend(np.mean(x.reshape(-1,STEP,2)**2,axis=(1,2)))
 dp=np.vstack(dp);mp=[];noise=[];meta=[]
 for distance,cap in [('50cm','raw_153239'),('20cm','raw_155636')]:
  folder=ROOT/'listen/rew/log'/cap;an=json.loads((folder/'s59_analysis/analysis.json').read_text());sync=an['pcm_sync'];path=folder/'recording.wav';out=[];st=None
  with sf.SoundFile(path) as f:
   f.seek(0);z=f.read(round(4.5*FS),dtype='float64',always_2d=True);pp,_=powers(z);noise.append(np.percentile(pp,99,axis=0))
   for a in range(0,m['samples'],FS*10):
    x=affine_read(f,sync,a/FS,min(FS*10,m['samples']-a));p,st=powers(x,st);out.append(p)
  mp.append(np.vstack(out));meta.append(dict(distance=distance,path=str(path),sha256=sha(path),sync=sync))
  print('features',distance,flush=True)
 np.savez_compressed(O/'PHONE_FEATURES.npz',digital=dp,total=np.array(total),mic=np.array(mp),noise=np.array(noise))
 dump('INPUTS.json',dict(recordings=meta,digital=dict(path=m['path'],sha256=sha(m['path'])),map_sha256=sha(L/'segment_map.json')))
 return m,dp,np.array(total),np.array(mp),np.array(noise)
def mask_segments(m,n):
 train=np.zeros(n,bool);val=np.zeros(n,bool);music=np.zeros(n,bool);probe=np.zeros(n,bool);labels={}
 for s in m['segments']:
  ctl=('SENS' in s['condition'] or 'PLUS4' in s['condition'] or '+4' in s['condition'])
  tr=s['repeat']==1 and s['id']!='Track00030' and not ctl
  for kind,a,b in [('music',s['content_start_sample']//STEP+100,s['content_start_sample']//STEP+700),('probe',s['recovery_start_sample']//STEP+14,s['recovery_start_sample']//STEP+46)]:
   (train if tr else val)[a:b]=True;(music if kind=='music' else probe)[a:b]=True
  labels[s['index']]=dict(train=tr,heldout=not tr,control=ctl)
 return train,val,music,probe,labels
def fit():
 if not (O/'PHONE_FEATURES.npz').exists():m,dp,total,mp,noise=extract()
 else:
  m=json.loads((L/'segment_map.json').read_text());v=np.load(O/'PHONE_FEATURES.npz');dp,total,mp,noise=[v[k] for k in ['digital','total','mic','noise']]
 train,val,music,probe,labels=mask_segments(m,len(dp));support=mp>noise[:,None,:]*10
 # Tone observations carry probe history with strong1000Hz SNR; no heldout mic enters fit.
 rec=list(csv.DictReader((P/'s65b/RECOVERY_PROBES.csv').open()))
 extra={}
 for dist in ['50cm','20cm']:
  for row in rec:
   if row['distance']==dist and float(row['frequency_hz'])==1000:
    s=m['segments'][int(row['index'])-1];a=s['recovery_start_sample']//STEP+14;b=s['recovery_start_sample']//STEP+46
    extra[(dist,int(row['index']))]=(a,b,float(row['probe_mic_dbfs'])-float(row['probe_digital_dbfs']))
 fits=[]
 for attack in [.01,.03,.1]:
  for release in [.15,.4,1.2,3.]:
   lo,hi,hh=features(dp,total,attack,release);params=[];errs=[]
   for j in range(5):
    xx=[];yy=[];ww=[]
    for d,dist in enumerate(['50cm','20cm']):
     use=train&support[d,:,j];ix=np.flatnonzero(use)[::2]
     xx.append(np.column_stack([np.ones(len(ix)),lo[ix,j],hi[ix,j],-hh[ix],np.full(len(ix),int(d==0))]))
     yy.append(db(mp[d,ix,j])-db(dp[ix,j]));ww.append(np.where(probe[ix],np.sqrt(max(1,music.sum()/max(probe.sum(),1))),1.))
     if j==3:
      for (di,idx),(a,b,gain) in extra.items():
       if di!=dist or not labels[idx]['train']:continue
       ix=np.arange(a,b)
       xx.append(np.mean(np.column_stack([np.ones(len(ix)),lo[ix,j],hi[ix,j],-hh[ix],np.full(len(ix),int(d==0))]),axis=0)[None,:]);yy.append(np.array([gain]));ww.append(np.array([20.]))
    x=np.vstack(xx);y=np.concatenate(yy);w=np.concatenate(ww)
    sol=lsq_linear(x*w[:,None],y*w,([-100,-.9,-.9,0,-20],[0,.2,.2,2,0]),tol=1e-10).x if len(y) else np.array([-60.,0.,0.,0.,-8.])
    err=x@sol-y
    if len(y):errs.append(float(np.average(err**2,weights=w*w)))
    params.append(dict(band_hz=BANDS[j],intercept20_db=sol[0],slope_low=1+sol[1],slope_high=1+sol[2],history_coefficient=sol[3],offset50_db=sol[4],fit_observations=len(y),unsupported_fallback=not len(y)))
   fits.append(dict(attack_s=attack,release_s=release,bands=params,train_mse=np.mean(errs)))
 model=min(fits,key=lambda z:z['train_mse']);dump('FIT_GRID.json',fits);dump('PCM_PHONE.json',model);dump('SPLIT.json',labels)
 pred=[db(dp)+gains(dp,total,model,dist) for dist in ['50cm','20cm']];rows=[]
 for d,dist in enumerate(['50cm','20cm']):
  for j in range(5):
   for split,sel in [('train',train),('holdout',val)]:
    use=sel&support[d,:,j];e=pred[d][use,j]-db(mp[d,use,j]);rows.append(dict(distance=dist,band=BANDS[j],split=split,n=int(use.sum()),bias_db=float(np.mean(e)) if len(e) else None,mae_db=float(np.median(abs(e))) if len(e) else None,p90_abs_db=float(np.percentile(abs(e),90)) if len(e) else None,rms_db=float(np.sqrt(np.mean(e*e))) if len(e) else None))
 checks=[];segment=[]
 for s in m['segments']:
  a=s['content_start_sample']//STEP+100;b=s['content_start_sample']//STEP+700
  for d,dist in enumerate(['50cm','20cm']):
   obs=10**(pred[d][a:b,1:3]/10);actual=mp[d,a:b,1:3]
   segment.append(dict(index=s['index'],id=s['id'],condition=s['condition'],level=s['level'],repeat=s['repeat'],distance=dist,predicted_bass_db=float(db(np.mean(obs.sum(1)))),observed_bass_db=float(db(np.mean(actual.sum(1)))),heldout=labels[s['index']]['heldout']))
 # Paired controls and H-L response checks, every matched repeat.
 for kind in ['plus4','HL','probe']:
  values=[]
  for d,dist in enumerate(['50cm','20cm']):
   for s in m['segments']:
    if kind=='plus4':
     if not labels[s['index']]['control']:continue
     ref=next((v for v in m['segments'] if v['id']==s['id'] and v['repeat']==s['repeat'] and v['level']==s['level'] and v['condition']=='B'),None)
     if ref is None:ref=next((v for v in m['segments'] if v['id']==s['id'] and v['repeat']==s['repeat'] and v['level']==s['level'] and v['condition']=='B_ATT0'),None)
    else:
     if s['level']!='H':continue
     ref=next((v for v in m['segments'] if v['id']==s['id'] and v['repeat']==s['repeat'] and v['condition']==s['condition'] and v['level']=='L'),None)
    if ref is None:continue
    if kind!='probe':
     get=lambda ss:next(z for z in segment if z['index']==ss['index'] and z['distance']==dist)
     aa,bb=get(s),get(ref);pr=aa['predicted_bass_db']-bb['predicted_bass_db'];ob=aa['observed_bass_db']-bb['observed_bass_db']
    else:
     a,b,oa=extra[(dist,s['index'])];c,e,ob0=extra[(dist,ref['index'])]
     gg=gains(dp,total,model,dist);pr=float(gg[a:b,3].mean()-gg[c:e,3].mean());ob=oa-ob0
    values.append(dict(distance=dist,id=s['id'],condition=s['condition'],level=s['level'],repeat=s['repeat'],predicted_db=float(pr),observed_db=float(ob),error_db=float(pr-ob)))
  checks.append(dict(kind=kind,rows=values))
 usable=all(z['n']>0 and z['mae_db']<=2 and z['p90_abs_db']<=5 for z in rows if z['split']=='holdout' and z['band'] in BANDS[1:4])
 ctrl=[]
 for ck in checks:
  for level in (['H','L'] if ck['kind']=='plus4' else ['all']):
   vv=[v for v in ck['rows'] if v['distance']=='20cm' and (level=='all' or v['level']==level)]
   pr=float(np.median([v['predicted_db'] for v in vv])) if vv else None;ob=float(np.median([v['observed_db'] for v in vv])) if vv else None
   threshold={'plus4':.75,'HL':1.5,'probe':1}[ck['kind']];passed=pr is not None and abs(pr-ob)<=threshold and (ck['kind']!='probe' or pr<0)
   ctrl.append(dict(kind=ck['kind'],level=level,predicted_db=pr,observed_db=ob,error_db=pr-ob if pr is not None else None,threshold_db=threshold,pass_gate=passed));usable&=passed
 c3=1 if model['bands'][2]['slope_high']>=model['bands'][1]['slope_high'] else -1
 dump('C3_FROZEN.json',dict(high_half=c3==1,selection='larger static slope at -25dBFS before candidate rendering',model_sha256=sha(O/'PCM_PHONE.json')))
 dump('MODEL_VALIDATION.json',dict(model=model,errors=rows,controls=ctrl,all_control_pairs=checks,usable_for_ranking=bool(usable),split='repeat2/all DEV30/+4 heldout',segments=segment))
 print('MODEL',model,'controls',ctrl,'usable',usable,flush=True)
if __name__=='__main__':fit()

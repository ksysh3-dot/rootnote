"""Predeclared legacy DEV3 diagnostics,50cm sensitivity and true-harmonic gap bank."""
from s66_eval import *
from scipy.signal import sosfilt,sosfiltfilt
CORE=3000;S=X.S;db10=X.db10
exec('class Metric38:'+(P/'s50/metric50.py').read_text().split('class Metric38:',1)[1],globals())
def bank(y,notes):
 out=np.zeros(len(y)//480);support=np.zeros(len(out),bool)
 for start,end,f,_ in notes:
  if end<2 or start>=29:continue
  a=max(0,int((start-.3)*100))*480;b=min(len(y)//480,int((end+.1)*100))*480
  z=np.asarray(y[a:b],float);parts=[]
  for k in range(2,9):
   hz=k*f
   if 150<=hz<600:
    v=sosfilt(butter(2,[hz-25,hz+25],btype='bandpass',fs=FS,output='sos'),z,axis=0)
    parts.append(np.mean(v.reshape(-1,480,2)**2,axis=(1,2)))
  if not parts:continue
  power=np.sum(parts,axis=0);t=(np.arange(len(power))+.5)/100+a/FS
  use=(t>=max(2.,start+.08))&(t<min(29.,end-.05));out[a//480:b//480][use]+=power[use];support[a//480:b//480]|=use
 return out,support
def gaps(p,ref,support):
 use=support&(ref>np.max(ref)*1e-4);d=PH.db(p)-PH.db(ref);out={}
 for th in [6,12]:
  mask=use&(d<=-th);z=np.diff(np.r_[False,mask,False].astype(int));a=np.flatnonzero(z==1);b=np.flatnonzero(z==-1);rr=[(i,j) for i,j in zip(a,b) if j-i>=3]
  out['count_'+str(th)]=len(rr);out['duration_'+str(th)+'_ms']=int(sum(j-i for i,j in rr)*10)
 out['supported_bins']=int(use.sum());return out
def main():
 os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
 rows=[]
 for key in DETAIL:
  x,bass,notes,plan,masks,src=load_dev(key);truth,segs,_=X.B.D.proxy_truth(src['item'],bass.mean(1));X.S.R=X.B.R0;X.S.OUT=O
  ideal=X.S.capture(np.zeros_like(x),X.PARAMS['c'],libpath=X.B.ORACLE,mode=3,tape=X.truth_tape(truth,len(x)))[0]*X.TRIM
  ev=Metric38(G*ideal,truth);result={};refs={};times={};bankrefs={}
  with ThreadPoolExecutor(max_workers=2) as pool:
   jobs={n:pool.submit(capture,x,n) for n in ['P1','B','T','C1','C2','C3']}
   for name in ['P1','B','T','C1','C2','C3']:
    raw,lraw,eng=jobs.pop(name).result();a=PRIME+eng['latency'];y=raw[a:a+len(x)].copy();l=lraw[a:a+len(x)].copy();del raw,lraw
    nn,sb=ev.evaluate(l,segs);legacy=dict(N2=nn['J'],segments=nn['valid_segments'],N1=X.n1(l,plan,(masks['band'],masks['good']))['ratio'],**X.C29.endpoint_harms(l,bass.mean(1),notes));contexts={}
    for ctx,level,dist in [('digital',0,'20cm'),('phone20H',0,'20cm'),('phone20L',-12,'20cm'),('phone50H',0,'50cm')]:
     yy,ll=(y,l) if ctx=='digital' else PH.transfer2(y*10**(level/20),MODEL,dist,layer=l*10**(level/20))
     pp,ss=bank(yy,notes)
     if name=='P1':bankrefs[ctx]=pp
     gm=gaps(pp,bankrefs[ctx],ss);context=dict(harmonic_bank_gaps_vs_P1=gm)
     if ctx=='phone50H':
      met,_=Z.direct_metrics((yy-ll)/G,ll/G,plan,masks['good'],masks['family'],masks['band'],masks['weak']);ex,et=extra_metrics(yy,notes,times.get(ctx));met.update(ex)
      if name=='P1':refs[ctx]=met;times[ctx]=et
      context.update(metrics=met,versus_P1=deltas(met,refs[ctx]))
      if name=='B':refs['B_'+ctx]=met
      if name not in ['P1','B']:context['versus_B']=deltas(met,refs['B_'+ctx])
     contexts[ctx]=context
    result[name]=dict(legacy_layer=legacy,contexts=contexts);print('DETAIL',key,name,flush=True);del y,l;gc.collect()
  rows.append(dict(id=key,variants=result));dump(O/'DETAILED_DEV3.json',dict(rows=rows,scope='legacy layer and true-harmonic-bank diagnostic; model50cm sensitivity only; no new candidate or adoption gate'))
if __name__=='__main__':main()

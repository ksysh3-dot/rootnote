"""Validate corrected PCM_PHONE actual WOLA waveform, using full input history."""
import s66_phone_v2 as Q
from s66_phone_v2 import *
from scipy.signal import periodogram
def main():
 v=np.load(O/'PHONE_FEATURES.npz');dp,total,mp,noise=[v[k] for k in ['digital','total','mic','noise']];m=json.loads((L/'segment_map.json').read_text());model=json.loads((O/'PCM_PHONE.json').read_text());gd=gains(dp,total,model)
 predicted=[];originalg=Q.gains;closure=[];segments=[]
 with sf.SoundFile(m['path']) as f:
  for s in m['segments']:
   a=s['content_start_sample']-FS;start=a//STEP;f.seek(a);x=f.read(10*FS,dtype='float64',always_2d=True)
   Q.gains=lambda p,t,model,distance='20cm',start=start:gd[start:start+len(p)]
   y=Q.transfer2(x,model);pp,_=powers2(y);offset=s['content_start_sample']//STEP
   for j in range(5):
    obs=mp[1,offset+100:offset+700,j];pr=pp[200:800,j];use=obs>10*noise[1,j]
    if s['repeat']==2 or s['id']=='Track00030' or 'SENS' in s['condition']:
     closure.append(dict(band=j,level=s['level'],id=s['id'],error=db(pr[use])-db(obs[use])))
   pred=pp[200:800,1:3].sum(1);actual=mp[1,offset+100:offset+700,1:3].sum(1);r=db(actual)-db(pred);hz,ps=periodogram(r,100,window='hann',scaling='density');df=100/len(r)
   t=np.arange(round(.32*FS))/FS;probe=y[round(9.14*FS):round(9.46*FS)].mean(1);design=np.column_stack([np.sin(2*np.pi*250*t),np.cos(2*np.pi*250*t),np.sin(2*np.pi*1000*t),np.cos(2*np.pi*1000*t),np.ones(len(t))]);c=np.linalg.lstsq(design,probe,rcond=None)[0]
   segments.append(dict(index=s['index'],id=s['id'],condition=s['condition'],repeat=s['repeat'],level=s['level'],predicted_bass_db=float(db(pred.mean())),observed_bass_db=float(db(actual.mean())),predicted_probe1k_db=float(db((c[2]**2+c[3]**2)/2)),gain_residual_1_4_rms_db=float(np.sqrt(ps[(hz>=1)&(hz<4)].sum()*df))))
 Q.gains=originalg;errors=[]
 for j in range(5):
  e=np.concatenate([v['error'] for v in closure if v['band']==j]);errors.append(dict(band=BANDS[j],n=len(e),bias_db=float(e.mean()) if len(e) else None,median_abs_db=float(np.median(abs(e))) if len(e) else None,p90_abs_db=float(np.percentile(abs(e),90)) if len(e) else None))
 ctl=[]
 for kind in ['plus4','HL','probe']:
  for level in (['H','L'] if kind=='plus4' else ['all']):
   vals=[]
   for s in segments:
    if kind=='plus4':
     if s['condition']!='SENS_PLUS4' or s['level']!=level:continue
     ref=next((v for v in segments if v['id']==s['id'] and v['repeat']==s['repeat'] and v['level']==s['level'] and v['condition']=='B'),None)
    else:
     if s['level']!='H':continue
     ref=next((v for v in segments if v['id']==s['id'] and v['repeat']==s['repeat'] and v['condition']==s['condition'] and v['level']=='L'),None)
    if not ref:continue
    if kind=='probe':
     csvrows=list(csv.DictReader((P/'s65b/RECOVERY_PROBES.csv').open()));get=lambda z:float(next(r for r in csvrows if r['distance']=='20cm' and int(r['index'])==z['index'] and float(r['frequency_hz'])==1000)['probe_mic_dbfs']);pr=s['predicted_probe1k_db']-ref['predicted_probe1k_db'];ob=get(s)-get(ref)
    else:pr=s['predicted_bass_db']-ref['predicted_bass_db'];ob=s['observed_bass_db']-ref['observed_bass_db']
    vals.append((pr,ob))
   pr=float(np.median([v[0] for v in vals]));ob=float(np.median([v[1] for v in vals]));th={'plus4':.75,'HL':1.5,'probe':1}[kind];ctl.append(dict(kind=kind,level=level,n=len(vals),predicted_db=pr,observed_db=ob,error_db=pr-ob,pass_gate=abs(pr-ob)<=th and (kind!='probe' or pr<0)))
 usable=all(v['median_abs_db'] is not None and v['median_abs_db']<=2 and v['p90_abs_db']<=5 for v in errors[1:4]) and all(v['pass_gate'] for v in ctl)
 rng=np.random.default_rng(66);x=rng.normal(0,.01,(FS,2));zero=dict(model);zero['bands']=[dict(v,intercept20_db=0,slope_low=1,slope_high=1,history_coefficient=0,offset50_db=0) for v in model['bands']]
 # gains() normally clamps to measured acoustic range. For reconstruction fixture use exact unity.
 Q.gains=lambda p,t,m,distance='20cm':np.zeros((len(p),5));yx=Q.transfer2(x,zero);err=float(abs(yx-x).max());Q.gains=originalg;assert err<1e-12
 strata=[]
 for level in ['H','L']:
  for j in range(5):
   e=np.concatenate([v['error'] for v in closure if v['band']==j and v['level']==level]);strata.append(dict(level=level,band=BANDS[j],n=len(e),bias_db=float(e.mean()) if len(e) else None,median_abs_db=float(np.median(abs(e))) if len(e) else None,p90_abs_db=float(np.percentile(abs(e),90)) if len(e) else None))
 dump('WAVEFORM_CLOSURE_v2.json',dict(errors20cm=errors,errors_by_level=strata,controls=ctl,usable20cm_exploratory=usable,segments=segments,median_residual_1_4_rms_db=float(np.median([s['gain_residual_1_4_rms_db'] for s in segments])),unity_reconstruction_max_error=err,domain='150Hz+ only; <150Hz unidentifiable and censored, not physical prediction'))
 print('v2 waveform',errors,'controls',ctl,'usable',usable,flush=True)
if __name__=='__main__':main()

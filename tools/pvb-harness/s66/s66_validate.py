"""Independent waveform-closure validation and estimator fixtures; no audio writes."""
import sys,os
from pathlib import Path
sys.path.insert(0,'/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
import s66_phone as Q
from s66_phone import *
def main():
 v=np.load(O/'PHONE_FEATURES.npz');dp,total,mp,noise=[v[k] for k in ['digital','total','mic','noise']]
 m=json.loads((L/'segment_map.json').read_text());model=json.loads((O/'PCM_PHONE.json').read_text());train,held,music,probe,labels=mask_segments(m,len(dp))
 # Actual waveform composition followed by the SAME band analyzer as mic.
 # This specifically detects cross-band phase and overlap errors hidden by summing band powers.
 out=[];st=None;pst=None;offset=0;gd=gains(dp,total,model)
 with sf.SoundFile(m['path']) as f:
  for start in range(0,m['samples'],FS*10):
   x=f.read(min(FS*10,m['samples']-start),dtype='float64',always_2d=True);bp,st=split(x,st);n=len(x)//STEP
   gs=10**(np.repeat(gd[offset:offset+n],STEP,axis=0)/20);y=sum(b*gs[:,j,None] for j,b in enumerate(bp));pp,pst=powers(y,pst);out.append(pp);offset+=n
 pred=np.vstack(out);rows=[]
 for j in range(5):
  use=held&music&(mp[1,:,j]>10*noise[1,j]);err=db(pred[use,j])-db(mp[1,use,j])
  rows.append(dict(band=BANDS[j],n=int(use.sum()),bias_db=float(err.mean()) if len(err) else None,median_abs_db=float(np.median(abs(err))) if len(err) else None,p90_abs_db=float(np.percentile(abs(err),90)) if len(err) else None))
 residual=[]
 for s in m['segments']:
  if not labels[s['index']]['heldout']:continue
  a=s['content_start_sample']//STEP+100;b=a+600
  real=mp[1,a:b,1:3].sum(1);pp=pred[a:b,1:3].sum(1);r=db(real)-db(pp);hz,ps=periodogram(r,100,window='hann',scaling='density');df=100/len(r)
  residual.append(dict(index=s['index'],id=s['id'],level=s['level'],condition=s['condition'],gain_residual_1_4_rms_db=float(np.sqrt(ps[(hz>=1)&(hz<4)].sum()*df)),power_bias_db=float(db(pp.mean())-db(real.mean()))))
 rng=np.random.default_rng(66);x=rng.normal(0,.01,(FS,2));bp,_=split(x);recon=max(abs(sum(bp)-x).ravel());assert recon<1e-15
 # Equal gains reconstruct exactly; output has no audio delay.
 fixtures=dict(complementary_reconstruction_max_error=float(recon),history_zero_input_max=float(history(np.zeros(100),.1,1.2).max()),model_is_causal_previous_frame=True,known_limit='coarse complementary phase/overlap and room coloration evaluated below')
 dump('WAVEFORM_CLOSURE.json',dict(errors20cm=rows,holdout_modulation_residual=residual,median_residual_1_4_rms_db=float(np.median([r['gain_residual_1_4_rms_db'] for r in residual])),fixtures=fixtures))
 print('waveform closure',rows,'slow residual',np.median([r['gain_residual_1_4_rms_db'] for r in residual]),flush=True)
if __name__=='__main__':main()

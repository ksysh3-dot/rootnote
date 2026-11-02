"""Analyze a future recording with s59 affine chirp sync and tone regression."""
import os,sys,json,argparse
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0,'/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
from s59_analyze_capture import pcm_sync
def main():
 ap=argparse.ArgumentParser();ap.add_argument('recording');ap.add_argument('--out',required=True);ap.add_argument('--map',default=str(Path(__file__).with_name('segment_map.json')));ap.add_argument('--channel',type=int,default=0);a=ap.parse_args()
 m=json.loads(Path(a.map).read_text());o=Path(a.out);o.mkdir(parents=True,exist_ok=True);sync=pcm_sync(Path(a.recording),m);print('sync',sync)
 fs=m['fs'];mic,sr=sf.read(a.recording,always_2d=True,dtype='float64');assert 0<=a.channel<mic.shape[1];mic=mic[:,a.channel]
 if sr!=fs:
  from math import gcd
  g=gcd(sr,fs);mic=resample_poly(mic,fs//g,sr//g)
 def aligned(start,n):
  t=sync['offset_s']+sync['clock_ratio']*(start+np.arange(n)/fs);q=t*fs;k=np.floor(q).astype(np.int64);fraction=q-k;assert k[0]>=0 and k[-1]+1<len(mic);return mic[k]*(1-fraction)+mic[k+1]*fraction
 cache={}
 def amp(z,hz):
  freqs=hz if isinstance(hz,list) else [hz];key=(tuple(freqs),len(z))
  if key not in cache:
   t=np.arange(len(z))/fs;x=np.column_stack([v for f in freqs for v in (np.sin(2*np.pi*f*t),np.cos(2*np.pi*f*t))]+[np.ones(len(t))]);cache[key]=np.linalg.pinv(x)
  c=cache[key]@z;return [float(10*np.log10(max((c[2*j]**2+c[2*j+1]**2)/2,1e-30))) for j in range(len(freqs))]
 # Tone-fit noise99 uses fixed40ms windows from the independent pre-play noise.
 noise=mic[:min(len(mic),round(max(2.,sync['offset_s'])*fs))];floors={}
 for f in [80,200,250,400,1000,4000]:floors[f]=float(np.percentile([amp(noise[i:i+1920],[250,1000] if f in [250,1000] else f)[int(f==1000)] for i in range(0,len(noise)-1920,1920)],99))
 rows=[]
 for e in m['events']:
  if e['kind'] not in ['level_step','tone_burst','recovery_probe','whole_pcm_control']:continue
  hz=[80,200,400,1000,4000] if e['kind']=='whole_pcm_control' else e.get('frequencies_hz',[e.get('frequency_hz')]);dur=e['end_s']-e['start_s']
  for t in np.arange(.02,max(.0201,dur-.04),.02):
   vals=amp(aligned(e['start_s']+t,1920),hz)
   for f,db in zip(hz,vals):rows.append(dict(event=e['index'],kind=e['kind'],frequency_hz=f,condition=e.get('condition'),repeat=e.get('repeat'),source_time_s=e['start_s']+float(t),relative_s=float(t),mic_dbfs=db,noise99_dbfs=floors[f],snr_db=db-floors[f],supported=db-floors[f]>=10,digital_peak_dbfs=e.get('peak_dbfs',e.get('component_peak_dbfs'))))
 plateaus=[]
 for e in m['events']:
  if e['kind'] not in ['level_step','whole_pcm_control']:continue
  for f in ([80,200,400,1000,4000] if e['kind']=='whole_pcm_control' else [e['frequency_hz']]):
   rr=[r for r in rows if r['event']==e['index'] and r['frequency_hz']==f and r['relative_s']>=(e['end_s']-e['start_s']-.5) and r['supported']]
   plateaus.append(dict(event=e['index'],kind=e['kind'],condition=e.get('condition'),frequency_hz=f,input_peak_dbfs=e.get('peak_dbfs'),supported_frames=len(rr),mic_dbfs=float(np.median([r['mic_dbfs'] for r in rr])) if rr else None))
 controls=[]
 for f in [80,200,400,1000,4000]:
  q={r['condition']:r['mic_dbfs'] for r in plateaus if r['frequency_hz']==f and r['kind']=='whole_pcm_control'}
  for c in ['IDENTICAL_B','PLUS4']:
   controls.append(dict(frequency_hz=f,condition=c,relative_to='IDENTICAL_A',delta_db=q[c]-q['IDENTICAL_A'] if q[c] is not None and q['IDENTICAL_A'] is not None else None,expected_digital_db=4 if c=='PLUS4' else 0))
 recovery=[]
 from scipy.optimize import least_squares
 for e in m['events']:
  if e['kind']!='recovery_probe':continue
  for f in [250,1000]:
   rr=[r for r in rows if r['event']==e['index'] and r['frequency_hz']==f and r['supported'] and r['relative_s']>=.06]
   result=dict(event=e['index'],frequency_hz=f,condition=e['condition'],repeat=e['repeat'],supported_frames=len(rr),time_resolution_s=.02,tone_fit_window_s=.04)
   span=float(np.percentile([r['mic_dbfs'] for r in rr],90)-np.percentile([r['mic_dbfs'] for r in rr],10)) if rr else 0.;result['p90_p10_range_db']=span
   if len(rr)>=30 and rr[-1]['relative_s']-rr[0]['relative_s']>=2 and span>=.25:
    tt=np.array([r['relative_s'] for r in rr]);yy=np.array([r['mic_dbfs'] for r in rr]);fn=lambda p:p[0]-p[1]*np.exp(-tt/p[2])-yy
    fit=least_squares(fn,[yy[-10:].mean(),max(0.,yy[-10:].mean()-yy[:5].mean()),1.],bounds=([-200,-30,.02],[0,60,20]))
    result.update(late_dbfs=float(fit.x[0]),suppression_db=float(fit.x[1]),phenomenological_tau_s=float(fit.x[2]),fit_rms_db=float(np.sqrt(np.mean(fn(fit.x)**2))))
   else:result['reason']='no_identifiable_recovery_below_0_25dB' if len(rr)>=30 and span<.25 else 'insufficient_noise_supported_recovery'
   recovery.append(result)
 result=dict(sync=sync,clipped_samples=int(np.sum(abs(mic)>=1-2**-15)),channel=a.channel,noise99_dbfs=floors,rows=rows,plateaus=plateaus,controls=controls,recovery_fits=recovery,scope='relative response/history;40ms tone fits and20ms hop cannot resolve faster hardware attack; no device acquisition or subjective verdict')
 (o/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('rows',len(rows),'clipped',result['clipped_samples'])
if __name__=='__main__':main()

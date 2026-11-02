"""Exploratory corrected disjoint-STFT model. V1 is preserved, never relabelled."""
from pathlib import Path
import shutil,json,datetime,sys
import s66_phone as V
from s66_phone import *
NF=2048;WIN=np.hanning(NF);HZ=np.fft.rfftfreq(NF,1/FS)
MASKS=[(HZ>=a)&(HZ<b) for a,b in [(0,150),(150,300),(300,600),(600,3000),(3000,24001)]]
base_gains=gains
def gains(p,total,model,distance='20cm'):
 z=base_gains(p,total,model,distance)
 # <150Hz has only5 supported training observations and cannot identify a path.
 # Censor that unidentifiable input component rather than amplify its leakage.
 # No interpretation of fundamental preservation or LF phone output is allowed.
 z[:,0]=-100.
 return z
def spectrum(x,states=None):
 # Frames end at successive10ms boundaries and have42.67ms trailing support.
 # Preserve context between chunks. Disjoint frequency masks remove V1 overlap.
 if states is None:states=np.zeros((NF,x.shape[1]))
 z=np.concatenate([states,x]);n=len(x)//STEP
 view=np.lib.stride_tricks.sliding_window_view(z,NF,axis=0)[STEP:STEP*(n+1):STEP]
 zz=np.fft.rfft(view*WIN,axis=2).transpose(0,2,1)
 return zz,z[-NF:].copy()
def powers2(x,states=None):
 zz,states=spectrum(x,states);pp=np.mean(abs(zz)**2,axis=2)*2/(NF*np.sum(WIN*WIN))
 return np.column_stack([pp[:,m].sum(1) for m in MASKS]),states
def transfer2(x,model,distance='20cm',layer=None):
 n=len(x);nn=(n+NF+STEP-1)//STEP*STEP;xx=np.pad(np.asarray(x,float),((0,nn-n),(0,0)))
 zz,_=spectrum(xx);p=np.mean(abs(zz)**2,axis=2)*2/(NF*np.sum(WIN*WIN));pw=np.column_stack([p[:,m].sum(1) for m in MASKS]);total=np.mean(xx.reshape(-1,STEP,x.shape[1])**2,axis=(1,2))
 gd=gains(pw,total,model,distance);gs=np.zeros((len(zz),len(HZ)))
 for j,m in enumerate(MASKS):gs[:,m]=10**(gd[:,j,None]/20)
 def compose(z):
  frames=np.fft.irfft(z*gs[:,:,None],n=NF,axis=1)*WIN[None,:,None]
  out=np.zeros((nn+NF,x.shape[1]));norm=np.zeros(nn+NF)
  for i,f in enumerate(frames):
   a=(i+1)*STEP;out[a:a+NF]+=f;norm[a:a+NF]+=WIN*WIN
  return (out[NF:NF+n]/np.maximum(norm[NF:NF+n,None],1e-30))
 y=compose(zz)
 if layer is None:return y
 ll=np.pad(np.asarray(layer,float),((0,nn-n),(0,0)));lz,_=spectrum(ll);return y,compose(lz)
def setup():
 preserve=O/'v1_preserved';preserve.mkdir(exist_ok=True)
 names=['PHONE_FEATURES.npz','PCM_PHONE.json','FIT_GRID.json','SPLIT.json','MODEL_VALIDATION.json','C3_FROZEN.json','WAVEFORM_CLOSURE.json','EVALUATION_LOCK.json','results']
 for name in names:
  if (O/name).exists() and not (preserve/name).exists():shutil.move(O/name,preserve/name)
 pp=O/'MODEL_CORRECTION_v2.md'
 if not pp.exists():
  pp.write_text('''PCM_PHONE v2 exploratory correction after five DEV candidate results.
V1 waveform closure failed: overlapping first-order complementary band signals plus fitted unequal gains overpredicted bass by10-12dB; independent per-band fit was not an end-to-end waveform model. Preserve V1/model/DEV5 and original registration failure.
Replace the evaluator filterbank only with disjoint2048-point Hann STFT bands (0-150/150-300/300-600/600-3000/3000-Nyquist),10ms hop,42.67ms trailing analysis and normalized overlap-add. It is an offline phone evaluator; window reconstruction can smear envelope/attack by~21ms and is not engine latency. Candidate native code/digital outputs/parameters remain frozen. Keep V1 C3 high-half choice fixed even if corrected slopes differ; no fourth candidate and no retuning from new scores.
Same recording split, dynamics grid, constrained curves and gates as original. Zero noise-supported bands reported N/A. Validate actual reconstructed waveform, not summed component powers: primary20cm bass heldout median abs error<=2dB,p90<=5dB; +4/H-L/probe thresholds unchanged. Also report50cm as sensitivity, no primary veto from an unidentifiable50cm band. This narrower20cm usability gate is exploratory and cannot become an original-registration pass.
Freeze this amendment before V2 fitting or any V2 candidate result. V1 digital results remain valid and reproducible. No dataset validation/test/confirm, new candidate, extra engine delay, acquisition or playback.
''',encoding='utf-8')
  dump('MODEL_CORRECTION_v2_REGISTRATION.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan_sha256=sha(pp),script_sha256=sha(Path(__file__)),v1_candidates_seen=['Track00001','Track00016','Track00030','Track00002','Track00003'],fixed_C3_high_half=True,original_registration_pass=False))
def main():
 setup();V.powers=powers2;V.transfer=transfer2;V.fit()
 # Original C3 chosen before first candidate must remain fixed.
 dump('C3_FROZEN_v2_slope_suggestion_unused.json',json.loads((O/'C3_FROZEN.json').read_text()));shutil.copy2(O/'v1_preserved/C3_FROZEN.json',O/'C3_FROZEN.json')
 result=json.loads((O/'MODEL_VALIDATION.json').read_text());result['version']='v2_disjoint_exploratory';dump('MODEL_VALIDATION.json',result)
if __name__=='__main__':main()

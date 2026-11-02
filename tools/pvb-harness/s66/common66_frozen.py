import os,sys,json,hashlib,datetime,re
from pathlib import Path
sys.dont_write_bytecode=True
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:6]))
H=Path.home();O=H/'r3a-dev/plan16/s66';W=H/'r3-s66';P=O.parent
LISTEN=Path('/mnt/c/Users/ksysh/rootnote-duo/listen/s66')
sys.path.insert(0,str(P/'s55'));import common55 as C55
sys.path.insert(0,str(P/'s34'));import common34 as Z
from common55 import np,FS,decode,truepeak,sha
from scipy.signal import butter,sosfilt,resample_poly
X=Z.X;G=10**(-5/20);LIB=O/'build_host/libpvbcapi.so'
IDS=json.loads((O/'IDS.json').read_text());NAMES=['P1','B_MIX','B_STEM','WSOLA_MIX','WSOLA_STEM']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if hasattr(v,'item') else str(v))+'\n',encoding='utf-8')
def db(v):return float(10*np.log10(max(float(v),1e-30)))
def ratio(a,b):return db(a)-db(b) if a is not None and b is not None and a>1e-20 and b>1e-20 else None
def save(n,v):dump(O/n,v)
X.S.OUT=O;X.A.save=save
allowed=set(IDS);frozen=json.loads((P/'s44/SPLIT_FROZEN.json').read_text())
assert allowed<=set(frozen['dev'])
excluded=set(frozen['excluded_confirm_ids'])|set(json.loads((P/'s46/CONFIRM_IDS.json').read_text())['ids'])
assert not allowed&excluded
def pathcheck(p,write=False):
 if not isinstance(p,(str,bytes,os.PathLike)):return
 p=Path(os.fsdecode(p)).absolute();s=str(p)
 assert not s.startswith('/mnt/d/rootnote-data'),s
 if '/datasets/slakh2100' in s:
  ids=re.findall(r'Track\d{5}',s)
  assert '/train/' in s and ids and ids[0] in allowed and ids[0] not in excluded,s
 if write:
  assert p.is_relative_to(O) or p.is_relative_to(W) or p.is_relative_to(LISTEN) or s=='/dev/null',s
  assert p.suffix.lower() not in {'.wav','.flac','.mp3','.ogg','.pcm','.aiff'} or p.is_relative_to(LISTEN),s
def guard(event,args):
 if event not in ('open','os.listdir','os.scandir'):return
 if not isinstance(args[0],(str,bytes,os.PathLike)):return
 s=os.fsdecode(args[0])
 if event!='open':
  assert '/datasets/slakh2100' not in s,'No dataset enumeration';return
 mode,flags=args[1:3];wr=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
 pathcheck(args[0],wr)
sys.addaudithook(guard)
# libsndfile bypasses Python's open audit. Explicitly guard its path too.
import soundfile as sf
_SoundFile=sf.SoundFile
def checked_soundfile(file,mode='r',*a,**kw):
 pathcheck(file,mode!='r');return _SoundFile(file,mode,*a,**kw)
sf.SoundFile=checked_soundfile
def native(x,on=False,raw=False):return C55.capture(np.ascontiguousarray(x,np.float32),on=on,path=LIB,raw=raw)
def common_dry(x):
 # Same fixed linear v1.1 playback EQ as P1/B's normal engine path.
 return G*sosfilt(C55.T.ref_sos(FS,C55.T.V11),np.asarray(x,float),axis=0)
def load_dev(key):
 assert key in IDS
 item=X.C31.saved(key,'dev')['item']
 if 'bass_midis' not in item:item['bass_midis']=[str(Path(p).parent.parent/'MIDI'/(Path(p).stem+'.mid')) for p in item['bass_stems']]
 x=decode(item['mix'],duration=30);b=np.zeros_like(x,dtype=float)
 for p in item['bass_stems']:
  q=decode(p,duration=30);b[:min(len(b),len(q))]+=q[:len(b)]
 import research_gt_bass as GT
 parsed=sum((GT.midi_notes(Path(p)) for p in item['bass_midis']),[])
 assert sorted(parsed)==sorted([tuple(r) for r in item['notes']]),key
 notes=X.A.notes_hz(item);plan=X.A.q_plan(notes,len(x),(2.,29.))
 masks=np.load(P/'s53/masks'/(key+'.npz'))
 bins=int(masks['bins']);good=np.unpackbits(masks['good'],axis=1)[:,:bins].astype(bool)
 family=np.unpackbits(masks['family'],axis=1)[:,:bins].astype(bool)
 band=np.unpackbits(masks['band'])[:bins].astype(bool);weak=masks['weak'].astype(bool)
 assert np.array_equal(np.unpackbits(masks['q'],axis=1)[:,:bins].astype(bool),plan['masks'])
 assert weak.dtype==bool
 source=dict(item=item,mix_sha256=sha(item['mix']),stems={p:sha(p) for p in item['bass_stems']},midis={p:sha(p) for p in item['bass_midis']})
 return x,b,notes,plan,dict(good=good,family=family,band=band,weak=weak),source
def env_native(z):
 v=sosfilt(butter(3,[150,600],btype='bandpass',fs=FS,output='sos'),np.asarray(z,float),axis=0)
 pw=np.mean(v*v,axis=1);cs=np.r_[0.,np.cumsum(pw)];ii=np.arange(len(pw));lo=np.maximum(0,ii-239)
 return ((cs[ii+1]-cs[lo])/(ii-lo+1))[::48]
def onset_events(notes):
 out=[]
 for s,e,f,_ in sorted(notes):
  if not 2<=s<29 or e-s<.05:continue
  nxt=min([ns for ns,_,_,_ in notes if ns>s+.001]+[29.]);end=min(e,nxt,29.)
  if end-s>=.05:out.append(dict(start=s,end=end,f0=f))
 return out
def timing(env,events,reference=None):
 out=[]
 for i,event in enumerate(events):
  t=event['start'];a=max(0,int((t-.05)*1000));s=int(t*1000);b=min(len(env),int(min(event['end'],t+.25)*1000))
  base=float(np.median(env[a:max(a+1,s-5)]));peak=float(env[s:b].max());row=dict(**event,base=base,peak=peak)
  for label,ref in [('local',row),('fixed',reference[i] if reference is not None else row)]:
   th=ref['base']+.1*(ref['peak']-ref['base']);ix=np.flatnonzero(env[a:b]>=th) if ref['peak']>max(ref['base']*1.1,1e-9) else []
   row[label+'10_ms']=float(a+ix[0]-t*1000) if len(ix) else None
  out.append(row)
 return out
def paired_timing(p,v,k='fixed10_ms'):
 vals=[b[k]-a[k] for a,b in zip(p,v) if a[k] is not None and b[k] is not None]
 return dict(n=len(vals),median_ms=float(np.median(vals)) if vals else None,p95_ms=float(np.percentile(vals,95)) if vals else None)

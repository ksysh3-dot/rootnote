from s74_verify import *
import soundfile as sf,math,datetime,zipfile
from scipy.signal import firwin
from concurrent.futures import ProcessPoolExecutor,as_completed
WIN=Path('/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
COEFF=firwin(321,1/8,window=('kaiser',8.6))
def progress(s):
 line=datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+s;print(line,flush=True)
 with (WIN/'s74_progress.txt').open('a',encoding='utf-8') as f:f.write(line+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
class TP:
 def __init__(self):self.tail=np.empty((0,2));self.peak=0.;self.total=0;self.emitted=0
 def add(self,x,final=False):
  start=self.total-len(self.tail);z=np.concatenate([self.tail,x.astype(float)]);self.total+=len(x)
  lo=max(0,self.emitted-start);hi=len(z) if final else max(lo,len(z)-20)
  if hi>lo:self.peak=max(self.peak,float(np.max(abs(resample_poly(z,8,1,axis=0,window=COEFF)[lo*8:hi*8]))))
  self.emitted=max(self.emitted,start+hi);self.tail=z[-40:].copy()
def db(x):return float(20*np.log10(max(float(x),1e-30)))
def load(src):
 if src['group']=='MUSDB':
  import av
  chunks=[];available=0
  with zipfile.ZipFile('/mnt/d/rootnote-ml/musdb18/musdb18.s73_complete.zip') as zf,zf.open(src['member']) as f,av.open(f,mode='r',format='mp4') as container:
   st=container.streams.audio[0];conv=av.AudioResampler(format='fltp',layout='stereo',rate=44100)
   for frame in container.decode(st):
    for q in conv.resample(frame):
     a=q.to_ndarray().T.copy();pos=int(round(float(q.pts*q.time_base)*44100)) if q.pts is not None else available;chunks.append((pos,a));available=max(available,pos+len(a))
    if available>=30*44100:break
  raw=np.zeros((min(30*44100,available),2),np.float32)
  for pos,a in chunks:
   lo=max(0,pos);hi=min(len(raw),pos+len(a))
   if hi>lo:raw[lo:hi]=a[lo-pos:hi-pos]
  return resample_poly(raw,160,147,axis=0).astype(np.float32)[:1440000],44100
 with sf.SoundFile(src['path']) as f:
  rate=f.samplerate;raw=f.read(-1 if src['seconds'] is None else int(src['seconds']*rate),dtype='float32',always_2d=True)
 if raw.shape[1]==1:raw=np.repeat(raw,2,axis=1)
 assert raw.shape[1]==2
 if rate!=48000:g=math.gcd(rate,48000);raw=resample_poly(raw,48000//g,rate//g,axis=0).astype(np.float32)
 return raw,rate
def parity(src,x):
 # Add a second of declared silence to compare all30s, including right-edge WOLA support.
 # The source excerpt and s73 input are unchanged through30s; score2..29 stays exact.
 xp=np.pad(x,((0,48000),(0,0)));z=separate(xp);ry,rl=ref_native(xp,z);e=app(2)
 y,l,tr,cost=e.run(np.pad(xp,((0,12000),(0,0))),1024);lat=e.l.pvb_latency(e.h);e.close();n=len(x)
 a=y[3192:3192+n+7140];b=ry[:n+7140];aa=l[3192:3192+n+7140];bb=rl[:n+7140]
 pcm=error(a,b);layer=error(aa,bb)
 # Last native lookahead is compared with the same continuing-silence source contract.
 score=error(y[10332+2*48000:10332+29*48000],ry[7140+2*48000:7140+29*48000]) if n>=30*48000 else None
 tpA=TP();tpB=TP();tpA.add(a,True);tpB.add(b,True);delta=db(tpA.peak)-db(tpB.peak)
 return dict(pcm=pcm,layer=layer,score_pcm=score,tp8_delta_db=delta,latency=lat,
             passed=pcm['max_error']<=2e-6 and layer['max_error']<=2e-6 and pcm['relative_rms_db']<=-80 and layer['relative_rms_db']<=-80 and abs(delta)<=.01)
def music(src,x):
 rows=[]
 for mode in [1,2]:
  e=app(mode);b=Engine(BASE,preset=True) if mode==1 else None
  if mode==1:e.run(np.zeros((49152,2),np.float32),1024);b.run(np.zeros((49152,2),np.float32),1024)
  pk=TP();nonfinite=bad=zero=diag=0;baseline=True;gr=step=0.;last=np.zeros((1,2),np.float32)
  cpu=[];wall=[];budget=[];md=hashlib.sha256();n=0;features=[];lat=7140 if mode==1 else 10332;hist=np.zeros((lat,2),np.float32)
  data=np.pad(x,((0,24000),(0,0)));segment=[]
  for a in range(0,len(data),1024):
   q=data[a:a+1024];y,l,tr,cost=e.process(q);nf=int((~np.isfinite(y)).sum());nonfinite+=nf
   if b is not None:baseline=baseline and np.array_equal(y,b.process(q)[0])
   full=np.empty_like(y);lay=np.empty_like(y);trace=np.empty(90,np.float32)
   assert e.l.pvb_copy_diagnostic(e.h,lay.ctypes.data_as(FP),full.ctypes.data_as(FP),y.size,trace.ctypes.data_as(FP),90)==1
   diag+=int(not np.array_equal(full,y));meters=np.empty(28,np.float32);e.l.pvb_read_meters(e.h,meters.ctypes.data_as(FP),28)
   bad=max(bad,int(meters[9]));gr=max(gr,float(meters[2]));step=max(step,float(abs(np.diff(np.concatenate([last,y]),axis=0)).max()));last=y[-1:]
   delayed=np.concatenate([hist,q]);aligned=delayed[:len(q)];hist=delayed[len(q):]
   yr=float(np.sqrt(np.mean(y.astype(float)**2)));ir=float(np.sqrt(np.mean(aligned.astype(float)**2)))
   if a>48000 and ir>.01 and not np.any(y):zero+=1
   features.append([a/48000,ir,yr,float(np.sqrt(np.mean(l.astype(float)**2))),float(meters[2])])
   cpu.append(cost[0]/1e6);wall.append(cost[1]/1e6);budget.append(len(q)/48);md.update(y.tobytes());segment.append(y)
   if len(segment)==16 or a+len(q)==len(data):pk.add(np.concatenate(segment),a+len(q)==len(data));segment=[]
   n+=len(q)
  e.close()
  if b:b.close()
  name=src['key']+'_'+str(mode);np.savez_compressed(O/'music_features'/(name+'.npz'),features=np.asarray(features))
  rows.append(dict(mode=mode,frames=len(x),tp8_dbfs=db(pk.peak),nonfinite=nonfinite,nan_event_blocks=bad,zero_active_blocks=zero,diagnostic_mismatches=diag,baseline_bit_equal=baseline,max_gr_db=gr,max_sample_step=step,pcm_sha256=md.hexdigest(),callback_frames=1024,blocks=len(cpu),cpu_deadline_misses=int(np.sum(np.asarray(cpu)>budget)),wall_deadline_misses=int(np.sum(np.asarray(wall)>budget)),cpu_p999_ms=float(np.percentile(cpu,99.9)),cpu_max_ms=max(cpu),wall_max_ms=max(wall),latency=lat,passed=not(nonfinite or bad or zero or diag) and baseline))
 return rows
def one(src):
 dest=O/'music_rows'/(src['key']+'.json')
 if dest.exists():return json.loads(dest.read_text())
 started=time.monotonic();x,rate=load(src);result=dict(source=src,source_rate=rate,frames=len(x),input_pcm_sha256=hashlib.sha256(x.tobytes()).hexdigest())
 if src['group'] in ['DEV','MUSDB']:result['parity']=parity(src,x)
 if src['group']!='MUSDB':result['music']=music(src,x)
 result['passed']=all([result.get('parity',{}).get('passed',True)]+[r['passed'] for r in result.get('music',[])])
 result['elapsed_s']=time.monotonic()-started;dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');return result
def main():
 (O/'music_rows').mkdir(exist_ok=True);(O/'music_features').mkdir(exist_ok=True)
 sources=[]
 for i,s in enumerate(json.loads((O.parent/'s67/MUSIC_INPUTS.json').read_text())['sources']):sources.append(dict(**s,key=f'A{i:03d}'))
 inv=json.loads((O.parent/'s73/corrected_v2/SOURCE_INVENTORY_FROZEN.json').read_text())
 for key in inv['ids']:sources.append({**inv['tracks'][key],'key':key,'group':'MUSDB','seconds':30})
 allowed={s.get('path') for s in sources if 'path' in s}
 def guard(event,args):
  if event in ['open','os.listdir','os.scandir'] and isinstance(args[0],(str,bytes,os.PathLike)):
   p=os.fsdecode(args[0]);assert not p.startswith('/mnt/d/rootnote-data')
   if '/datasets/slakh2100' in p:assert event=='open' and p in allowed,p
 sys.addaudithook(guard)
 files={str(p):sha(p) for p in (W/'app/src/main/cpp/libpvb').glob('*') if p.is_file()}
 files[str(LIB)]=sha(LIB);files[str(W/'app/src/main/assets/stable_ab_1218.bin')]=sha(W/'app/src/main/assets/stable_ab_1218.bin')
 dump('MUSIC_EXECUTION_LOCK.json',dict(files=files,sources=sources,plan_sha256=sha(O/'PLAN.md'),audio_persistence=False,workers=12))
 progress('MUSIC/PARITY START 121 source songs + s73 MUSDB30; 12 workers; stats only')
 results=[]
 with ProcessPoolExecutor(max_workers=12) as pool:
  futures={pool.submit(one,s):s['key'] for s in sources}
  for f in as_completed(futures):
   result=f.result();results.append(result);progress(f'MUSIC/PARITY {len(results)}/{len(sources)} {futures[f]} pass={result["passed"]}')
 dump('MUSIC_RESULTS.json',dict(rows=results,n=len(results),passed=all(r['passed'] for r in results)))
 progress('MUSIC/PARITY COMPLETE passed='+str(all(r['passed'] for r in results)))
if __name__=='__main__':main()

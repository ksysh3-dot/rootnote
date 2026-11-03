"""Implementation parity only on the already-consumed S76 train30; no new inference."""
from pathlib import Path
import sys,os,ast,json,hashlib,zipfile,av,gc,time
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
H=Path.home();W=H/'r3-s77';O=H/'r3a-dev/plan16/s77'
sys.path.insert(0,str(W/'tools/research-s77'))
from s77_verify import app,separate,ref_native,error,np
from scipy.signal import resample_poly,firwin
FS=48000;ZIP=Path('/mnt/d/rootnote-ml/musdb18/musdb18.s73_complete.zip')
# Reuse source adapter decoding only. No training, tuning, or evaluator rerun.
source=H/'r3a-dev/plan16/s76/scripts/s76_source.py';text=source.read_text()
node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='decode')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard(event,args):
 if event in ['open','os.listdir','os.scandir'] and isinstance(args[0],(str,bytes,os.PathLike)):
  p=os.fsdecode(args[0]);assert '/rootnote-data' not in p and '/datasets/slakh' not in p,p
sys.addaudithook(guard)
def one(row):
 key=row['id'];x=decode(row['member'],0);xp=np.pad(x,((0,FS),(0,0)));z=separate(xp)
 e=app(2);y,l,_,_=e.run(np.pad(xp,((0,12000),(0,0))),257);lat=e.l.pvb_latency(e.h);e.close()
 ry,rl=ref_native(xp,z);n=len(xp)
 a=y[3192:3192+n];b=ry[:n];c=l[3192:3192+n];d=rl[:n]
 p=error(a,b);q=error(c,d)
 def tp(v):return float(20*np.log10(max(float(abs(resample_poly(v.astype(float),8,1,axis=0,window=firwin(321,1/8,window=('kaiser',8.6)))).max()),1e-30)))
 tp_delta=tp(a)-tp(b)
 result=dict(id=key,latency=lat,pcm=p,layer=q,tp_delta_db=tp_delta,audio_persisted=False,scope='implementation parity; previously exposed S76 source; not new efficacy confirmation')
 result['passed']=lat==8796 and p['max_error']<=2e-6 and q['max_error']<=2e-6 and p['relative_rms_db']<=-80 and q['relative_rms_db']<=-80 and abs(tp_delta)<=.01 and np.isfinite(y).all()
 result['passed']=bool(result['passed'])
 (O/'music_rows'/f'{key}.json').write_text(json.dumps(result,indent=2));print(key,result['passed'],p['max_error'],flush=True)
 return result
if __name__=='__main__':
 from concurrent.futures import ProcessPoolExecutor
 inv=H/'r3a-dev/plan16/s76/SOURCE_INVENTORY_FROZEN.json';rows=list(json.loads(inv.read_text())['tracks'].values());assert len(rows)==30
 (O/'music_rows').mkdir(exist_ok=True)
 assert not list((O/'music_rows').glob('*.json')),'Do not overwrite parity attempts'
 files={str(p):sha(p) for p in (W/'app/src/main/cpp/libpvb').glob('*') if p.is_file()}
 files[str(O/'build-host/libpvbcapi.so')]=sha(O/'build-host/libpvbcapi.so')
 (O/'MUSIC_LOCK.json').write_text(json.dumps(dict(files=files,inventory_sha256=sha(inv),max_error=2e-6,rms_db=-80,tp_db=.01),indent=2))
 with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,rows))
 for p,h in files.items():assert sha(Path(p))==h,p
 passed=all(r['passed'] for r in results)
 (O/'MUSIC_PARITY.json').write_text(json.dumps(dict(passed=passed,tracks=30,rows=results),indent=2))
 assert passed;print('MUSIC_PARITY PASS 30/30',flush=True)

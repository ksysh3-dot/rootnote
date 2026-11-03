from pathlib import Path
import sys,subprocess,shutil,json,ctypes as C
H=Path.home();O=H/'r3a-dev/plan16/s78';W=H/'r3-s78';B=Path('/mnt/c/Users/ksysh/rootnote-duo')
sys.path.insert(0,str(H/'r3-s77/tools/research-s77'))
from s77_verify import Engine,FP,np,stimulus,weights,BP,bind
BASE=O.parent/'s77/build-host/libpvbcapi.so';LIB=O/'build-host/libpvbcapi.so'
def engine(lib,mode,meter,rate=48000):
 e=Engine(lib,sr=rate,capture=False);bind(e.l);assert e.l.pvb_load_stable_weights(e.h,weights.ctypes.data_as(BP),len(weights))==1
 e.p[57]=mode;e.p[34]=meter;assert e.l.pvb_try_set_params(e.h,e.p.ctypes.data_as(FP),58)==1
 return e
rows=[]
for rate in [48000,44100,96000]:
 for mode in [0,1,2] if rate==48000 else [0]:
  for block in [37,256,1024]:
   x=stimulus(rate,2.)
   a=engine(BASE,mode,0,rate);b=engine(LIB,mode,1,rate)
   ya=a.run(x,block)[0];yb=b.run(x,block)[0]
   assert np.array_equal(ya,yb),(rate,mode,block,float(abs(ya-yb).max()))
   lib=b.l;lib.pvb_dev_meter_size.restype=C.c_int;size=lib.pvb_dev_meter_size();assert size==32+512*11
   lib.pvb_copy_dev_meters.argtypes=[C.c_void_p,FP,C.c_int]
   out=np.empty(size,np.float32);assert lib.pvb_copy_dev_meters(b.h,out.ctypes.data_as(FP),size)==size
   assert np.isfinite(out).all();st=out[1056:].reshape(512,9);st=st[-min(512,max(1,int(out[10]))):];assert st[:,7].min()>=0
   if mode==1 and rate==48000:assert abs(st[-100:,0]-st[-100:,1]).max()<1e-5
   rows.append(dict(rate=rate,mode=mode,block=block,bit_equal=True,finite=True))
   a.close();b.close()
(O/'TELEMETRY_VALIDATION.json').write_text(json.dumps(dict(passed=True,rows=rows),indent=2));print('TELEMETRY PASS',len(rows),flush=True)
# Existing Kotlin/JNI suite with updated meter ABI.
out=W/'tools/pvb-harness/build';out.mkdir(exist_ok=True)
for n in ['libpvbcapi.so','libpvbengine.so']:shutil.copy2(O/'build-host'/n,out/n)
s=(O.parent/'s74/kotlin-fast.py').read_text().replace('r3-s74','r3-s78').replace('plan16/s74','plan16/s78').replace('s74unit','s78unit')
(O/'kotlin-fast.py').write_text(s)
with (O/'jni.log').open('w') as f:r=subprocess.run([str(H/'venv-ml/bin/python'),'-B',str(O/'kotlin-fast.py')],stdout=f,stderr=subprocess.STDOUT)
print((O/'jni.log').read_text()[-1800:]);assert r.returncode==0



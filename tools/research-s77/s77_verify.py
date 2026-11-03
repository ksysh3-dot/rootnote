from pathlib import Path
import sys,os,ctypes as C,time,json,hashlib
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
H=Path.home();O=H/'r3a-dev/plan16/s77';W=H/'r3-s77';sys.path.insert(0,str(O.parent/'s50'))
from host50 import Engine,FP,np,stimulus
from scipy.signal import resample_poly
from scipy.fft import rfft,irfft
LIB=O/'build-host/libpvbcapi.so';BASE=O.parent/'s67/build-final/libpvbcapi.so';REF=O/'corrected-reference/libpvb_s75_1_corrected.so'
weights=np.frombuffer((W/'app/src/main/assets/stable_ab_1218.bin').read_bytes(),np.uint8).copy();BP=C.POINTER(C.c_ubyte)
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def bind(l):
 l.pvb_load_stable_weights.argtypes=[C.c_void_p,BP,C.c_int];l.pvb_load_stable_weights.restype=C.c_int
 l.pvb_stable_separator.argtypes=[BP,C.c_int,FP,FP,C.c_int];l.pvb_stable_separator.restype=C.c_int
 l.pvb_try_set_params.argtypes=[C.c_void_p,FP,C.c_int];l.pvb_try_set_params.restype=C.c_int
 l.pvb_read_meters.argtypes=[C.c_void_p,FP,C.c_int]
 return l
def app(mode,capture=True,rate=48000):
 e=Engine(LIB,sr=rate,capture=capture);bind(e.l)
 assert e.l.pvb_load_stable_weights(e.h,weights.ctypes.data_as(BP),len(weights))==1
 e.p[57]=mode;assert e.l.pvb_try_set_params(e.h,e.p.ctypes.data_as(FP),58)==1
 return e
def separate(x):
 l=C.CDLL(str(O.parent/'s71/libs71tcn.so'));l.s69_create.argtypes=[C.c_char_p];l.s69_create.restype=C.c_void_p
 l.s69_step.argtypes=[C.c_void_p,FP,FP];l.s69_destroy.argtypes=[C.c_void_p]
 h=l.s69_create(str(W/'app/src/main/assets/stable_ab_1218.bin').encode());mask=np.empty(514,np.float32)
 win=np.sqrt(np.hanning(513)[:-1]).astype(np.float32);z=resample_poly(x,1,6,axis=0);zp=np.pad(z,((448,512),(0,0)))
 count=(len(zp)-512)//64+1;y=np.zeros(((count-1)*64+512,2),np.float32);den=np.zeros(len(y),np.float32)
 for start in range(0,count,64):
  ids=np.arange(start,min(start+64,count))*64;sp=rfft(np.stack([zp[j:j+512].T for j in ids])*win,axis=-1);masks=[]
  for spec in sp:
   mono=spec.mean(0);feat=np.clip(np.log10(abs(mono)**2+1e-8),-8,4).astype(np.float32)/4
   l.s69_step(h,feat.ctypes.data_as(FP),mask.ctypes.data_as(FP));masks.append((mask[:257]+1j*mask[257:]).copy())
  rec=irfft(sp*np.asarray(masks)[:,None,:],n=512,axis=-1).transpose(0,2,1)*win[None,:,None]
  for j,frame in zip(ids,rec):y[j:j+512]+=frame;den[j:j+512]+=win*win
 l.s69_destroy(h);y/=np.maximum(den[:,None],1e-8);return resample_poly(y[448:448+len(z)],6,1,axis=0)[:len(x)].astype(np.float32)
def ref_native(x,z):
 e=Engine(REF,preset=True);l=e.l;l.pvb_set_separator_peak70.argtypes=[C.c_void_p,C.c_int];l.pvb_process_separator70.argtypes=[C.c_void_p,FP,FP,C.c_int]
 assert l.pvb_set_separator_peak70(e.h,1)==1
 xx=np.pad(x,((49152,48000),(0,0)));zz=np.pad(z,((49152,48000),(0,0)));y=np.empty_like(xx);lay=np.empty_like(xx)
 for a in range(0,len(xx),1024):
  q=zz[a:a+1024].copy();mix=np.ascontiguousarray(xx[a:a+1024]);l.pvb_process_separator70(e.h,q.ctypes.data_as(FP),mix.ctypes.data_as(FP),len(q));y[a:a+len(q)]=q
  ll=np.empty_like(q);ff=np.empty_like(q);tr=np.empty(90,np.float32);assert l.pvb_copy_diagnostic(e.h,ll.ctypes.data_as(FP),ff.ctypes.data_as(FP),q.size,tr.ctypes.data_as(FP),90)==1;lay[a:a+len(q)]=ll
 e.close();return y[49152:],lay[49152:]
def error(a,b):
 err=a.astype(float)-b.astype(float);return dict(max_error=float(abs(err).max()),relative_rms_db=float(20*np.log10(max(np.sqrt(np.mean(err**2)),1e-30)/max(np.sqrt(np.mean(b.astype(float)**2)),1e-30))))
def initial():
 rows=[]
 for rate in [48000,44100,96000]:
  for mode in [0,1]:
   for block in [64,257,1024]:
    a=Engine(LIB,sr=rate,preset=mode==1);b=Engine(BASE,sr=rate,preset=mode==1);x=stimulus(rate,1.)
    aa=a.run(x,block);bb=b.run(x,block);a.close();b.close();eq=np.array_equal(aa[0],bb[0]) and np.array_equal(aa[1],bb[1]);rows.append(dict(rate=rate,mode=mode,block=block,bit_equal=eq));assert eq,rows[-1]
 dump('V0.json',dict(rows=rows,passed=True));print('V0 PASS',len(rows),flush=True)
 x=stimulus(sec=3);xp=np.pad(x,((0,48000),(0,0)));z=separate(xp);e=app(2);out=np.empty_like(xp);assert e.l.pvb_stable_separator(weights.ctypes.data_as(BP),len(weights),xp.ctypes.data_as(FP),out.ctypes.data_as(FP),len(xp))==1
 sep=error(out[3192:],z[:-3192]);print('SEPARATOR',sep,flush=True)
 y,l,_,_=e.run(np.pad(xp,((0,12000),(0,0))),64);lat=e.l.pvb_latency(e.h);e.close();ry,rl=ref_native(xp,z);n=len(x)
 checks=dict(separator=sep,latency=lat,pcm=error(y[3192:3192+n],ry[:n]),layer=error(l[3192:3192+n],rl[:n]),nonfinite=int((~np.isfinite(y)).sum()))
 assert lat==8796,checks; assert checks['pcm']['max_error']<=2e-6 and checks['layer']['max_error']<=2e-6,checks; dump('INITIAL_PARITY.json',checks);print('INITIAL',checks,flush=True)
if __name__=='__main__':initial()

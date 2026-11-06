from pathlib import Path
import ctypes as C,json,hashlib,os
import numpy as np
H=Path.home();O=H/'r3a-dev/plan16/s91c';B=H/'r3-s91c'
F=C.POINTER(C.c_float);U=C.POINTER(C.c_ubyte)
def load(p):
 l=C.CDLL(str(p))
 l.pvb_create.argtypes=[C.c_int];l.pvb_create.restype=C.c_void_p
 l.pvb_destroy.argtypes=[C.c_void_p]
 l.pvb_default_params.argtypes=[F]
 l.pvb_set_params.argtypes=[C.c_void_p,F,C.c_int]
 l.pvb_process.argtypes=[C.c_void_p,F,C.c_int]
 l.pvb_load_stable_weights.argtypes=[C.c_void_p,U,C.c_int];l.pvb_load_stable_weights.restype=C.c_int
 l.s91_engine_enable.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int64];l.s91_engine_enable.restype=C.c_int
 return l
old=load(O/'baseline-build/libpvbcapi.so');new=load(B/'tools/pvb-harness/build/libpvbcapi.so')
t=np.arange(96000,dtype=np.float64)/48000
x=np.stack([.15*np.sin(2*np.pi*63*t)+.045*np.sin(2*np.pi*126*t),.14*np.sin(2*np.pi*79*t)+.03*np.sin(2*np.pi*158*t)],axis=1).astype('float32')
x+=np.random.default_rng(9103).normal(0,.003,x.shape).astype('float32')
x[12000:15000]*=.05
weights=(B/'app/src/main/assets/stable_ab_1218.bin').read_bytes();w=(C.c_ubyte*len(weights)).from_buffer_copy(weights)
def run(l,mode,block):
 e=l.pvb_create(48000);assert e
 try:
  p=np.zeros(58,'float32');l.pvb_default_params(p.ctypes.data_as(F));p[22]=1;p[23]=6;p[11]=0;p[57]=mode
  if mode==2:assert l.pvb_load_stable_weights(e,w,len(w))
  assert l.s91_engine_enable(e,0,0,0)
  l.pvb_set_params(e,p.ctypes.data_as(F),58)
  out=x.copy()
  for i in range(0,len(x),block):
   b=out[i:i+block];l.pvb_process(e,b.ctypes.data_as(F),len(b))
  assert np.isfinite(out).all()
  return out
 finally:l.pvb_destroy(e)
rows=[]
for mode,label in [(0,'P1'),(1,'P1+++'),(2,'epoch6')]:
 for block in [37,64,256,1024]:
  a=run(old,mode,block);b=run(new,mode,block)
  row=dict(mode=label,block=block,control_enabled=False,byte_identical=a.tobytes()==b.tobytes(),max_error=float(np.max(np.abs(a-b))),sha256=hashlib.sha256(b.tobytes()).hexdigest())
  rows.append(row);print(row,flush=True)
(O/'CONTROL_OFF_REGRESSION.json').write_text(json.dumps(dict(passed=all(r['byte_identical'] for r in rows),synthetic_host_only=True,baseline_commit='a87b687ef95fae3073ca4f8892d67c454c0a057d',rows=rows),indent=2))
assert all(r['byte_identical'] for r in rows)

"""Bit comparisons against an explicitly built archive/s50 library. Synthetic PCM stays in RAM."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"): os.environ[k]="1"
import ctypes as C, numpy as np, json, hashlib, argparse
from pathlib import Path
FP=C.POINTER(C.c_float); DP=C.POINTER(C.c_double)
def library(path):
 l=C.CDLL(str(Path(path).resolve()))
 for n,a,r in [("pvb_create",[C.c_int],C.c_void_p),("pvb_destroy",[C.c_void_p],None),("pvb_default_params",[FP],None),("pvb_set_params",[C.c_void_p,FP,C.c_int],None),("pvb_process",[C.c_void_p,FP,C.c_int],None),("pvb_set_diagnostic_capture",[C.c_void_p,C.c_int],None),("pvb_copy_diagnostic",[C.c_void_p,FP,FP,C.c_int,FP,C.c_int],C.c_int),("pvb_vb_create",[C.c_int,C.c_int],C.c_void_p),("pvb_vb_destroy",[C.c_void_p],None),("pvb_reset",[C.c_void_p],None),("pvb_set_resultant",[C.c_void_p,DP,C.c_int],C.c_int)]:
  f=getattr(l,n);f.argtypes=a;f.restype=r
 return l
class Engine:
 def __init__(self,path,sr=48000,on=False,algo=6,extra=None):
  self.l=library(path);self.h=self.l.pvb_create(sr);self.p=np.empty(58,np.float32);self.l.pvb_default_params(self.p.ctypes.data_as(FP));self.p[22:25]=[1,algo,0];self.p[11]=0;self.p[57]=on
  for k,v in (extra or {}).items(): self.p[k]=v
  self.l.pvb_set_params(self.h,self.p.ctypes.data_as(FP),58);self.l.pvb_set_diagnostic_capture(self.h,1)
 def close(self):
  if self.h:self.l.pvb_destroy(self.h);self.h=None
 def run(self,x,blocks):
  ys=[];ls=[];ts=[];i=0;k=0
  while i<len(x):
   n=blocks if isinstance(blocks,int) else blocks[k%len(blocks)];y=np.array(x[i:i+n],np.float32,order="C",copy=True);a=np.empty_like(y);b=np.empty_like(y);t=np.empty(90,np.float32)
   self.l.pvb_process(self.h,y.ctypes.data_as(FP),len(y));assert self.l.pvb_copy_diagnostic(self.h,a.ctypes.data_as(FP),b.ctypes.data_as(FP),y.size,t.ctypes.data_as(FP),90)==1
   ys.append(y);ls.append(a);ts.append(t);i+=n;k+=1
  return np.concatenate(ys),np.concatenate(ls),np.array(ts)
def stimulus(sr=48000,sec=.45):
 t=np.arange(round(sr*sec))/sr;rng=np.random.default_rng(50)
 return np.c_[.31*np.sin(2*np.pi*63*t)*(1+.4*np.sin(2*np.pi*8*t))+.02*rng.normal(size=len(t)),.27*np.sin(2*np.pi*78*t+.4)+.025*rng.normal(size=len(t))].astype(np.float32)
def digest(x):return hashlib.sha256(x.tobytes()).hexdigest()
def compare(base,current):
 rows=[]
 for sr in [48000,44100]:
  for on in [False,True]:
   for block in [64,128,256,512,1024,[37,64,128,256,512,1024]]:
    x=stimulus(sr);a=Engine(base,sr,on);b=Engine(current,sr,on);v=a.run(x,block);w=b.run(x,block);a.close();b.close()
    for label,va,wa in zip(["pcm","layer","trace"],v,w):
     if label=="trace":
      ignored=[2] # wall-time telemetry is nondeterministic
      if sr==44100 and on:
       assert np.all(va[:,55]==0) and np.all(wa[:,55]==6) # inactive default model, intentional ABI sanitization
       ignored.append(55)
      va=np.delete(va,ignored,axis=1);wa=np.delete(wa,ignored,axis=1)
     assert np.array_equal(va,wa),(sr,on,block,label,float(np.max(abs(va-wa))))
    rows.append(dict(sr=sr,p1ppp=on,block=block,pcm=digest(v[0]),layer=digest(v[1]),passed=True))
 return rows
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("baseline");p.add_argument("current");p.add_argument("--report",required=True);a=p.parse_args();rows=compare(a.baseline,a.current);Path(a.report).write_text(json.dumps(dict(passed=True,cases=len(rows),rows=rows),indent=2));print("P1/P1+++ archive V0:",len(rows),"passed")

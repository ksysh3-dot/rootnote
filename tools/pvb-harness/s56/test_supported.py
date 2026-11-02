"""Current app/native allowlist and reserved-slot contracts; no external audio or data."""
import argparse, json
from pathlib import Path
from compare import Engine, library, stimulus, np, FP, DP, C, digest

def verify(path):
 l=library(path);rows=[]
 assert l.pvb_param_count()==58 and l.pvb_meter_count()==28
 defaults=np.empty(58,np.float32);l.pvb_default_params(defaults.ctypes.data_as(FP))
 assert defaults[23]==6 and defaults[57]==0 and np.all(defaults[29:33]==0)
 for algo in list(range(-1,20))+[999]:
  h=l.pvb_vb_create(algo,48000)
  assert bool(h)==(algo==6),("factory allowlist",algo)
  if h:l.pvb_vb_destroy(h)
 for sr in [48000,44100]:
  x=stimulus(sr);r=Engine(path,sr);ref=r.run(x,256);r.close()
  for algo in list(range(18))+[-1,999,1e30,np.nan,np.inf,6.25]:
   if algo==6:continue
   e=Engine(path,sr,algo=algo,extra={29:1,30:1,31:1,32:1});v=e.run(x,256);e.close()
   assert np.array_equal(v[0],ref[0]) and np.array_equal(v[1],ref[1]),("fallback PCM",sr,algo)
   assert np.all(v[2][:,55]==6) and np.all(v[2][:,61:65]==0) and np.all(v[2][:,89]==0)
   rows.append(dict(test="fallback",sr=sr,requested=str(algo),pcm=digest(v[0]),passed=True))
  for on in [False,True]:
   for block in [64,256,1024,[37,64,256,1024]]:
    e=Engine(path,sr,on=on);v=e.run(x,block)
    assert np.all(np.isfinite(v[0])) and np.all(np.isfinite(v[1]))
    meters=np.zeros(28,np.float32);l.pvb_read_meters.argtypes=[C.c_void_p,FP,C.c_int];l.pvb_read_meters(e.h,meters.ctypes.data_as(FP),28)
    assert (int(meters[27])==(1 if sr==48000 else 0) if on else int(meters[27])==0),(sr,on,block,meters.tolist())
    e.close();rows.append(dict(test="rate/block",sr=sr,on=on,block=block,passed=True))
 return rows
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--lib",default=str(Path(__file__).resolve().parents[1]/"build/libpvbcapi.so"));p.add_argument("--report",required=True);a=p.parse_args();rows=verify(a.lib);Path(a.report).write_text(json.dumps(dict(passed=True,cases=len(rows),rows=rows),indent=2));print("Supported native contracts:",len(rows),"passed")

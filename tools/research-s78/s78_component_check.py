from pathlib import Path
import sys,ctypes as C,json
H=Path.home();O=H/'r3a-dev/plan16/s78'
sys.path.insert(0,str(H/'r3-s77/tools/research-s77'))
from s77_verify import Engine,FP,np,weights,BP,bind
rows=[]
for mode in [1,2]:
 e=Engine(O/'build-host/libpvbcapi.so',capture=True);bind(e.l)
 assert e.l.pvb_load_stable_weights(e.h,weights.ctypes.data_as(BP),len(weights))==1
 e.p[57]=mode;e.p[34]=1;assert e.l.pvb_try_set_params(e.h,e.p.ctypes.data_as(FP),58)==1
 t=np.arange(48000*3)/48000;x=np.repeat((.005*np.sin(2*np.pi*55*t))[:,None],2,axis=1).astype(np.float32)
 y,layer,trace,_=e.run(x,240)
 assert trace[-100:,22].max()<1e-5,trace[-1,:32] # no final limiter reduction for this fixture
 lib=e.l;lib.pvb_dev_meter_size.restype=C.c_int;n=lib.pvb_dev_meter_size();out=np.empty(n,np.float32)
 lib.pvb_copy_dev_meters.argtypes=[C.c_void_p,FP,C.c_int];assert lib.pvb_copy_dev_meters(e.h,out.ctypes.data_as(FP),n)==n
 # Actual layer is pre final limiter. This fixture has unity shared limiter and settled gate.
 want=20*np.log10(np.maximum(np.sqrt(2*np.mean(layer[-24000:].astype(float).reshape(100,240,2)**2,axis=(1,2))),1e-6))
 got=out[32:1056].reshape(512,2)[-100:,1]
 err=float(abs(want-got).max());assert err<2e-4,(mode,err)
 st=out[1056:].reshape(512,9)
 assert (st[-100:,3]>0).any(),mode
 rows.append(dict(mode=mode,actual_layer_rms_max_error_db=err,track_observations=True))
 e.close()
(O/'COMPONENT_CHECK.json').write_text(json.dumps(dict(passed=True,rows=rows),indent=2));print(rows)


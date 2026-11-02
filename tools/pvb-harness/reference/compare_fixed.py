import sys,json,argparse
from pathlib import Path
B=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('reference');p.add_argument('--report',required=True);args=p.parse_args()
sys.path.insert(0,str(B/'tools/pvb-harness/s56'))
from compare import *
base=Path(args.baseline);ref=Path(args.reference)
vector=np.array([0,0,0,15,22,6,8,30,.05,.1,1.,30,24,.03,0,200,1.5,16,2,150,8,1,0,10,0,0,1,1,1,0],float)
rows=[]
for sr in [48000,44100]:
 for bs in [64,256,1024]:
  a=Engine(base,sr,algo=15);b=Engine(ref,sr,algo=16)
  for e in [a,b]:e.run(np.zeros((64,2),np.float32),64)
  assert a.l.pvb_set_resultant(a.h,vector.ctypes.data_as(DP),30)==1
  assert b.l.pvb_set_resultant(b.h,vector.ctypes.data_as(DP),30)==0
  for e in [a,b]:e.l.pvb_reset(e.h)
  v=a.run(stimulus(sr,sec=.9),bs);w=b.run(stimulus(sr,sec=.9),bs)
  assert np.array_equal(v[0],w[0]) and np.array_equal(v[1],w[1]),(sr,bs,float(np.max(abs(v[0]-w[0]))))
  rows.append(dict(sr=sr,block=bs,pcm=digest(v[0]),layer=digest(v[1]),passed=True));a.close();b.close()
Path(args.report).write_text(json.dumps(dict(passed=True,baseline_algo=15,reference_algo=16,vector=vector.tolist(),cases=len(rows),rows=rows),indent=2));print('Fixed modified c:',len(rows),'bit exact to archive Resultant + full fixed vector (fixes27-29 ON)')
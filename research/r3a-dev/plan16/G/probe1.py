import sys
sys.path.insert(0,'/home/ksysh/r3a-dev/plan16/K')
from kcommon import *
import time
t0=time.time()
ctx=SongCtx('Track00024')
print('ctx',time.time()-t0)
d=ctx.sig.core_d
print({k:(v.shape,v.dtype) for k,v in d.items()})
print(np.unique(d['state'],return_counts=True), np.unique(d['coast'],return_counts=True))
print(np.unique(d['voice'])[:20], d['voice'][100], d['state'][100], d['coast'][100])
print(HOP_S, ctx.sig.core_tc[:3], ctx.sig.core_hop[:3], LAG, FSC, I_MIN)
v=ctx.voices[5]; print(v.keys()); print(len(v['T']), len(v['hs']), v['hs'][:5], v['T'][:3], ctx.sig.core_tc[v['hs'][:3]])
print(np.percentile(d['A']*d['c']*d['sig'],[50,95,99.9]))
print(d['sig'].max(), d['A'].max())

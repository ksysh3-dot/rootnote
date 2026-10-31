import numpy as np, sys, time
import soundfile as sf
from scipy.signal import resample_poly
import test_engine as T, research_p1plus as RP, test_harmonic_continuity as H
FS=48000
lib = RP.api(sys.argv[1])
x, fs = sf.read('/home/ksysh/datasets/slakh2100/train/Track00060/mix.flac', always_2d=True, frames=44100*30)
x = np.repeat(x,2,1) if x.shape[1]==1 else x
x = np.clip(resample_poly(x,160,147,axis=0),-1,1).astype(np.float32)
print(x.shape)
for cap in (False, True):
    t0=time.perf_counter()
    r = RP.render(lib, x, FS, 0, block=256, algo=6, capture=cap, stage_flags=0, out_db=-5)
    print('capture', cap, 'time', time.perf_counter()-t0, 'cb total', r['callback_total_seconds'])
e = T.Engine(lib, FS, vb_on=1, vb_algo=6)
t0=time.perf_counter(); y=e.process(x.copy(), block=256); print('plain process', time.perf_counter()-t0)
e = T.Engine(lib, FS, vb_on=0)
t0=time.perf_counter(); y=e.process(x.copy(), block=256); print('vb off process', time.perf_counter()-t0)

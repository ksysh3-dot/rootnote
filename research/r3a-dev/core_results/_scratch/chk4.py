import numpy as np, sys
import test_engine as T, research_p1plus as RP, test_harmonic_continuity as H
from vb_quality.stage_capture import StageCapture, core_indices, INDEX
FS=48000
lib = RP.api(sys.argv[1])
n = 5*FS
t = np.arange(n)/FS
x = .2*np.sin(2*np.pi*100*t)*(t>=1.0)
res={}
for label, lv in (('lvl0', 0), ('lvlm120', -120)):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, vb_level_db=lv, out_db=-5, ramp_ms=0)
    cap = StageCapture(lib, e.h, 0, int(n/FS*3000)+16)
    out = T.stereo(x).copy()
    for off in range(0,n,256):
        b = out[off:off+256]
        lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
    lat = e.latency(); st = cap.copy(); cap.close(); e.close()
    res[label]=(out.mean(axis=1), st, lat)
lay = res['lvl0'][0]-res['lvlm120'][0]
print('layer onset sample (48k):', np.argmax(np.abs(lay)>1e-3*np.abs(lay).max()), ' first >10%:', np.argmax(np.abs(lay)>0.1*np.abs(lay).max()))
st = res['lvl0'][1]
ci = core_indices(st)
for name in ('decimated','band','post_filter','pre_filter','raw_grain','applied_gain','env_a'):
    v = st[:, INDEX[name]]
    mx = np.max(np.abs(v))
    print(name, 'max', mx, 'first>1% core', ci[np.argmax(np.abs(v)>0.01*mx)] if mx>0 else None, 'first>10%', ci[np.argmax(np.abs(v)>0.1*mx)] if mx>0 else None)
# raw dry y onset in 48k and decimated onset core
y_dry = res['lvlm120'][0]
print('dry onset (>10%):', np.argmax(np.abs(y_dry)>0.1*np.abs(y_dry).max()))
dec = st[:, INDEX['decimated']]
print('decimated first >10% core', ci[np.argmax(np.abs(dec)>0.1*np.abs(dec).max())], 'x16 =', 16*ci[np.argmax(np.abs(dec)>0.1*np.abs(dec).max())])

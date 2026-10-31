import numpy as np, sys, ctypes as C
import test_engine as T, research_p1plus as RP, test_harmonic_continuity as H
from vb_quality.stage_capture import StageCapture, core_indices
FS=48000
lib = RP.api(sys.argv[1])
n = 5*FS
t = np.arange(n)/FS
x = .2*np.sin(2*np.pi*100*t)*(t>=1.0)
for label, lv in (('lvl0', 0), ('lvlm120', -120)):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=6, vb_level_db=lv, out_db=-5, ramp_ms=0)
    lib.pvb_set_diagnostic_capture(e.h, 1)
    cap = StageCapture(lib, e.h, 0, int(n/FS*3000)+16)
    out = T.stereo(x).copy()
    rows=[]; buf=np.empty(H.ROWS*H.FIELDS,np.float32)
    for off in range(0,n,256):
        b = out[off:off+256]
        lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        k = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
        if k>0:
            d = buf[:k*H.FIELDS].reshape(k,H.FIELDS).copy(); d[:,0]+=off; rows.append(d)
    lat = e.latency(); st = cap.copy(); cap.close(); e.close()
    R = np.vstack(rows); ts = H.tracks(R)
    tc = (R[:,0]+R[:,9])/FS
    a = np.array([ts[i, np.argmax(ts[i,:,4]), 4] for i in range(len(R))])
    print(label, 'lat', lat)
    final = a[-20:].mean()
    half = np.argmax(a>=0.5*final)
    print(' track amp final', final, 'tc at 50%:', tc[half], ' tc at 10%:', tc[np.argmax(a>=0.1*final)], ' at 90%', tc[np.argmax(a>=0.9*final)])
    # stage capture
    ci = core_indices(st)
    pf = st[:, 2+19]  # post_filter
    print(' stage rows', st.shape, 'first core', ci[:3], 'last', ci[-1])
    # find time the post_filter envelope first exceeds 10% of max
    env = np.abs(pf); mx = np.max(env)
    first = np.argmax(env>0.05*mx); 
    print(' post_filter first 5% at core', ci[first], ' -> core/3000 =', ci[first]/3000, 'max', mx)
    # where is dry output onset
    y = out.mean(axis=1)
    on = np.argmax(np.abs(y)>0.02)
    print(' output onset sample', on, 'time', on/FS, 'onset-lat', (on-lat)/FS)
    if lv==-120: np.save('/tmp/dry.npy', y)
    else: np.save('/tmp/wet.npy', y)

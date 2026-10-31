import numpy as np, sys
import test_engine as T, research_p1plus as RP
FS=48000
lib = RP.api(sys.argv[1])
n = 3*FS
t = np.arange(n)/FS
x = .2*np.sin(2*np.pi*100*t)+.1*np.sin(2*np.pi*200*t)
ys={}
for label, kw in (('off', dict(vb_on=0)), ('m120', dict(vb_on=1, vb_algo=6, vb_level_db=-120)), ('m60', dict(vb_on=1, vb_algo=6, vb_level_db=-60)), ('m24', dict(vb_on=1,vb_algo=6,vb_level_db=-24)), ('0', dict(vb_on=1, vb_algo=6, vb_level_db=0)), ('p12', dict(vb_on=1, vb_algo=6, vb_level_db=12)), ('p6', dict(vb_on=1, vb_algo=6, vb_level_db=6))):
    e = T.Engine(lib, FS, ramp_ms=0, **kw)
    print(label, 'param', e.params[T.P['VB_LEVEL_DB']])
    y = e.process(T.stereo(x), block=256); lat=e.latency(); e.close()
    ys[label]=(y[:,0].astype(float), lat)
for k in ys: print(k, 'lat', ys[k][1], 'rms', np.sqrt(np.mean(ys[k][0][FS:]**2)))
d = ys['m120'][0]-ys['off'][0]
print('m120 - off: max abs', np.abs(d).max(), ' rel to rms', np.abs(d).max()/np.sqrt(np.mean(ys['off'][0][FS:]**2)))
print('m24 - off rms', np.sqrt(np.mean((ys['m24'][0]-ys['off'][0])[FS:]**2)), ' m120', np.sqrt(np.mean(d[FS:]**2)), '0', np.sqrt(np.mean((ys['0'][0]-ys['off'][0])[FS:]**2)))

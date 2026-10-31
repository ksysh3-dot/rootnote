import numpy as np, sys, ctypes as C
import test_engine as T, research_p1plus as RP, test_harmonic_continuity as H
from vb_quality.stage_capture import StageCapture
FS=48000
lib = RP.api(sys.argv[1])
t = np.arange(int(4*FS))/FS
x = sum(a*np.sin(2*np.pi*k*100*t) for k,a in ((1,1),(2,.5),(3,.18)))
x = x*min(1,1)
x = .2512*x/np.abs(x).max()
x[:int(.008*FS)] *= np.linspace(0,1,int(.008*FS))
for lvl in (0,-120):
    r = RP.render(lib, x, FS, 0, block=256, algo=6, capture=True, stage_flags=0, out_db=-5)
    print('lat', r['latency'], 'rows', r['rows'].shape, 'stages', None if r['stages'] is None else r['stages'].shape)
    break
rows = r['rows']
print(rows[0,:28])
print(rows[100,:28])
ci = H.core_indices(rows)
print('core idx first', ci[:5], np.diff(ci)[:5])
print('R0 first', rows[:5,0], 'R9', rows[:5,9], 'R10', rows[:5,10])
ts = H.tracks(rows)
print('track fields at hop 100 (first 2 tracks)'); print(ts[100,:2,:14])
st = r['stages']; 
print(st[:3,:])

import numpy as np
import research_core_metrics as M, research_core_signals as S
FS=48000
# proj_power unit test
t=np.arange(FS)/FS; x=0.3*np.sin(2*np.pi*300*t+.7)
print('proj_power 0.3 sine ->', M.proj_power(x,[0.5],300.0)[0], 'expect', 0.3**2/4)
class Fake:
    algo=6; res=None; voice_mismatch=[]
    def __init__(self, gain=0.7): self.g=gain; self.cache={}
    def render(self, key, x2, level=0.0, out_db=-5.0, harmonic=False, stage=False, voice=False):
        x=np.asarray(x2,np.float64).mean(axis=1)
        if level>-100:
            lay=self.g*M.bandpass(x,150,600)           # oracle layer: follows the input's 2nd/3rd partial exactly
            y=x+lay
        else: y=x
        n=len(y)
        return dict(y=np.stack([y,y],1).astype(np.float32), lat=0, harm=np.empty((0,700),np.float32), stage=None, voice=None)
f=Fake()
r=M.v3_bare(f)
print('V3a', r['v3a'], ' V3b range', r['v3b']['range_db'], ' V3d median', r['v3d']['rise_db_median'], 'max', r['v3d']['rise_db_max'])
print('V3h bare', r['v3h_bare'])
print('V3h line', M.v3h(f))
# V3f oracle
print('V3f', M.v3f(f))

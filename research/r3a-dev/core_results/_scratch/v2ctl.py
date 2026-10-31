import numpy as np, research_core_metrics as M, research_core_signals as S
from scipy.signal import hilbert
class Fake:
    algo=6; res=None; voice_mismatch=[]
    def __init__(self, rot): self.rot=rot
    def render(self, key, x2, level=0.0, out_db=-5.0, harmonic=False, stage=False, voice=False):
        x=np.asarray(x2,np.float64).mean(axis=1)
        if level>-100:
            lay=M.bandpass(x,150,600); lay=0.7*np.real(hilbert(lay)*np.exp(1j*self.rot)); y=x+lay    # rotate the layer by rot rad
        else: y=x
        return dict(y=np.stack([y,y],1).astype(np.float32), lat=0, harm=np.empty((0,700),np.float32), stage=None, voice=None)
for rot in (0.0, 0.5, -0.8):
    r = M.v2(Fake(rot)); print('rot', rot, 'k2', round(r['k2']['dphi_mean_rad'],3), 'k3', round(r['k3']['dphi_mean_rad'],3))

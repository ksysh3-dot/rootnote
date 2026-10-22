"""Host-owned stage capture; must attach before process/detach before destroy."""
import ctypes as C
import numpy as np
DP=C.POINTER(C.c_double)
COLUMNS=('core_low32','core_high32','decimated','band','band_delayed191','original_h','original_p',
         'selected_h','selected_p','analytic_envelope','raw_grain','nominal_amplitude','env_a','env_p',
         'original_gain','applied_gain','tonal_after_gain','percussion','pre_filter','post_filter',
         'upper_blend','flags','modulation_mode','percussion_gate','detail_applied','family_applied','family_residual','family_coherence')
INDEX={name:i for i,name in enumerate(COLUMNS)}

class StageCapture:
    def __init__(self,lib,engine,flags,capacity):
        self.lib=lib;self.capacity=capacity
        lib.pvb_stage_attach.argtypes=[C.c_void_p,C.c_uint,C.c_int];lib.pvb_stage_attach.restype=C.c_void_p
        lib.pvb_stage_detach.argtypes=[C.c_void_p]
        lib.pvb_stage_copy.argtypes=[C.c_void_p,DP,C.c_int]
        assert lib.pvb_stage_fields()==len(COLUMNS)
        self.handle=lib.pvb_stage_attach(engine,flags,capacity)
        if not self.handle:raise ValueError('stage attach failed')
    def copy(self):
        data=np.empty(self.capacity*len(COLUMNS),np.float64)
        n=self.lib.pvb_stage_copy(self.handle,data.ctypes.data_as(DP),len(data))
        if n<0:raise ValueError('stage capture overflow/capacity',n)
        return data[:n*len(COLUMNS)].reshape(n,len(COLUMNS)).copy()
    def close(self):
        if self.handle:self.lib.pvb_stage_detach(self.handle);self.handle=None

def core_indices(rows):
    return rows[:,0].astype(np.uint64)+(rows[:,1].astype(np.uint64)<<np.uint64(32))

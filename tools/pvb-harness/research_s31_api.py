"""S31 optional host controls. Configure before processing, never on the audio thread."""
import ctypes as C
def set_s31(lib,engine,order=4,gain=1.,cap=0.):
    lib.pvb_set_dry_low_cut_order.argtypes=[C.c_void_p,C.c_int]
    lib.pvb_set_dry_low_cut_order.restype=C.c_int
    lib.pvb_set_layer_gain_research.argtypes=[C.c_void_p,C.c_double,C.c_double]
    lib.pvb_set_layer_gain_research.restype=C.c_int
    assert lib.pvb_set_dry_low_cut_order(engine.h,order)==1
    assert lib.pvb_set_layer_gain_research(engine.h,gain,cap)==1

"""Helpers for brief A5: vcommon plus the 21-value parameter vector (ampSlewDb, slewOnsetMode) and the 16c library."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
from vcommon import *   # noqa
import vcommon as _V
A5_DIR = HOME / 'r3a-dev/plan16/A5'
LIB16C = HOME / 'r3-work/tools/pvb-harness/build_core16c/libpvbcapi.so'   # 21 params (A5)


def make_params5(rho=0.0, creep=0.0, mode=0.0, slew=0.0, onset=0.0):
    return np.array(list(BASE16) + [float(rho), float(creep), float(mode), float(slew), float(onset)], np.float64)

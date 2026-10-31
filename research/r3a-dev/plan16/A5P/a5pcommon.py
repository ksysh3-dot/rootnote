"""Helpers for brief A5': vcommon (16b library, 19 params) plus a parameter vector with betaMin / betaMax / psiSlew overrides."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
from vcommon import *   # noqa
A5_DIR = HOME / 'r3a-dev/plan16/A5P'
LIB16B = HOME / 'r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so'


def make_vec(prm):
    """19-value Resultant vector in research_core_api.PARAMS order; prm = dict of overrides on DEFAULTS"""
    d = dict(CA.DEFAULTS); d.update(prm)
    return np.array([float(d[n]) for n in CA.PARAMS], np.float64)

#!/usr/bin/env python3
"""Host test of the JamesDSP -> PVB chain (JdspChain.kt, RootlessAudioProcessorService).

Drives the real JamesDSP engine (libjamesdsp submodule, built by build_host_jdsp.sh with jdsp_capi.c) and the real
PVB engine (build_host.sh) block by block, as the service does on float capture: JamesDSP processes a block, PVB
processes JamesDSP's output.

Checks:
- sealed JamesDSP output control (0 dB post gain, limiter at JdspChain.NEUTRAL_LIMITER_DB) is bit-transparent, so
  "JamesDSP with nothing on" never changes PVB's input;
- JamesDSP latency per module (EQ, compressor) and PVB latency (reported);
- level safety with typical JamesDSP settings (EQ +6 dB low shelf, compressor on) in front of the PVB defaults
  (virtual bass off and on): output never above -1 dBTP, no NaN, limiter gain reduction small; heavier settings are
  reported (true peak and NaN still checked).

    ./build_host.sh && ./build_host_jdsp.sh && python3 test_jdsp_chain.py [--report chain-report.json]
"""
import argparse
import ctypes
import json
import os
import sys

import numpy as np
from scipy.signal import lfilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_engine as T  # noqa: E402  (Engine wrapper, true-peak meter, check/RESULTS)

FP = ctypes.POINTER(ctypes.c_float)
DP = ctypes.POINTER(ctypes.c_double)
SR = 48000
NEUTRAL_LIMITER_DB = 24.0      # JdspChain.NEUTRAL_LIMITER_DB
EQ_FREQS = [25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000]
LOW_SHELF_6 = [6, 6, 6, 6, 4, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]       # "+6 dB low shelf" on the 15-band EQ
LOW_SHELF_12 = [12, 12, 12, 12, 8, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0]
COMP_FREQS = [95, 200, 400, 800, 1600, 3400, 7500]                 # default compander response axis


def load_jdsp(path):
    lib = ctypes.CDLL(path)
    lib.jdsp_create.restype = ctypes.c_void_p
    lib.jdsp_create.argtypes = [ctypes.c_int]
    lib.jdsp_destroy.argtypes = [ctypes.c_void_p]
    lib.jdsp_set_output.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float]
    lib.jdsp_set_eq.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, DP]
    lib.jdsp_set_compander.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_int, DP]
    lib.jdsp_set_bass.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float]
    lib.jdsp_process.argtypes = [ctypes.c_void_p, FP, FP, ctypes.c_int]
    return lib


class Jdsp:
    """One JamesDSP instance. sealed=True sends what JdspChain.output sends while PVB processes."""

    def __init__(self, lib, sealed=True, eq=None, comp=None, user_output=(-0.1, 60.0, 0.0)):
        self.lib, self.h = lib, lib.jdsp_create(SR)
        thr, rel, gain = user_output
        if sealed:
            lib.jdsp_set_output(self.h, NEUTRAL_LIMITER_DB, rel, 0.0)
        else:
            lib.jdsp_set_output(self.h, thr, rel, gain)
        if eq is not None:
            b = np.array(EQ_FREQS + list(eq), np.float64)
            lib.jdsp_set_eq(self.h, 1, 0, 0, b.ctypes.data_as(DP))
        if comp is not None:
            c = np.array(COMP_FREQS + list(comp), np.float64)
            lib.jdsp_set_compander(self.h, 1, 0.22, 0, 0, c.ctypes.data_as(DP))

    def block(self, x):
        x = np.ascontiguousarray(x, np.float32)
        y = np.zeros_like(x)
        self.lib.jdsp_process(self.h, x.ctypes.data_as(FP), y.ctypes.data_as(FP), x.shape[0])
        return y

    def close(self):
        self.lib.jdsp_destroy(self.h)


def music(sec=12, seed=1):
    """Deterministic loud 'master': pink noise, a decaying bass line (37-55 Hz), kicks; soft-clipped, -1 dBFS peak."""
    rng = np.random.default_rng(seed)
    n = SR * sec
    t = np.arange(n) / SR
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    pink = lfilter(b, a, rng.standard_normal((n, 2)), axis=0)
    bass = np.zeros(n)
    notes = [41.2, 55.0, 49.0, 36.7]
    half = SR // 2
    for i in range(sec * 2):
        f, s = notes[i % 4], i * half
        tt = t[:half]
        bass[s:s + half] = np.sin(2 * np.pi * f * tt) * np.exp(-2 * tt) + 0.3 * np.sin(4 * np.pi * f * tt) * np.exp(-3 * tt)
    kick = np.zeros(n)
    tk = t[:SR // 4]
    k = np.sin(2 * np.pi * (50 + 80 * np.exp(-30 * tk)) * tk) * np.exp(-12 * tk)
    for s in range(0, n - len(k), half):
        kick[s:s + len(k)] += k
    x = 0.5 * pink / np.std(pink) + 0.8 * bass[:, None] + 0.9 * kick[:, None]
    x = np.tanh(3.0 * x / np.max(np.abs(x)))
    return (x * (10 ** (-1 / 20)) / np.max(np.abs(x))).astype(np.float32)


def run_chain(pvb_lib, jd, x, block, **pvb_params):
    """Block by block, like the service: JamesDSP (if any) then PVB. Returns output and per-block PVB meters."""
    e = T.Engine(pvb_lib, SR, ramp_ms=0.0, **pvb_params)
    y = np.zeros_like(x)
    rows = []
    for i in range(0, len(x), block):
        b = x[i:i + block]
        if jd is not None:
            b = jd.block(b)
        out = np.ascontiguousarray(b, np.float32).copy()
        pvb_lib.pvb_process(e.h, out.ctypes.data_as(FP), out.shape[0])
        y[i:i + block] = out
        rows.append(e.meters())
    lat = e.latency()
    e.close()
    return y, np.array(rows), lat


def t_neutral(jlib, pvb_lib):
    """Sealed, nothing on: JamesDSP output == input bit for bit, also above full scale (float path)."""
    rng = np.random.default_rng(3)
    x = (rng.standard_normal((SR * 2, 2)) * 0.8).astype(np.float32)
    x[1000:1010] = 3.5   # +10.9 dBFS: a float signal above full scale must pass unchanged
    jd = Jdsp(jlib, sealed=True)
    y = np.concatenate([jd.block(x[i:i + 4096]) for i in range(0, len(x), 4096)])
    jd.close()
    T.check('jdsp sealed with nothing on is bit-transparent (incl. +10.9 dBFS)', np.array_equal(x, y),
            max_diff=float(np.max(np.abs(x - y))))
    # and therefore the chain equals PVB alone when JamesDSP has nothing to do
    m = music(4)
    jd = Jdsp(jlib, sealed=True)
    ya, _, _ = run_chain(pvb_lib, jd, m, 4096, vb_on=1.0, vb_algo=6.0, vb_level_db=6.0)
    jd.close()
    yb, _, _ = run_chain(pvb_lib, None, m, 4096, vb_on=1.0, vb_algo=6.0, vb_level_db=6.0)
    T.check('chain with neutral JamesDSP == PVB alone (bit exact)', np.array_equal(ya, yb))
    # unsealed default output control (limiter at -0.1 dBFS, no look-ahead) clamps the same burst: why it is sealed
    jd = Jdsp(jlib, sealed=False)
    yu = jd.block(x[:4096])
    jd.close()
    T.check('unsealed JamesDSP limiter (-0.1 dBFS) would clamp it (reason for sealing)',
            float(np.max(np.abs(yu))) <= 10 ** (-0.1 / 20) + 1e-6, peak=float(np.max(np.abs(yu))))


def t_latency(jlib, pvb_lib):
    imp = np.zeros((SR, 2), np.float32)
    imp[1000] = 0.5
    out = {}
    for name, kw in [('eq', dict(eq=LOW_SHELF_6)), ('compressor', dict(comp=[0.6] * 7))]:
        lags = []
        for block in (4096, 1024, 480):
            jd = Jdsp(jlib, sealed=True, **kw)
            y = np.concatenate([jd.block(imp[i:i + block]) for i in range(0, len(imp), block)])
            jd.close()
            lags.append(int(np.argmax(np.abs(y[:, 0]))) - 1000)
        out[name] = lags
        # EQ: none. Compressor (STFT compander): 1792 frames for power-of-two blocks, a little more for other block
        # sizes (480 frames: 2016); the service reads whatever block the recorder returns.
        expected = (lambda v: v == 0) if name == 'eq' else (lambda v: 1792 <= v <= 2048)
        T.check(f'jdsp {name} latency (blocks 4096/1024/480)', all(expected(v) for v in lags),
                frames=','.join(str(v) for v in lags), ms_4096=lags[0] * 1000.0 / SR)
    e = T.Engine(pvb_lib, SR)
    pvb_eq = e.latency()
    e.set(vb_on=1.0, vb_algo=6.0, vb_level_db=6.0)
    e.process(np.zeros((4096, 2), np.float32))
    pvb_vb = e.latency()
    e.close()
    T.check('PVB latency (reported; unchanged by the chain)', pvb_eq == 88, pvb_eq_frames=pvb_eq, pvb_vb_p1_frames=pvb_vb)
    return dict(jdsp_eq=out['eq'], jdsp_compressor=out['compressor'], pvb_eq_only=pvb_eq, pvb_vb_p1=pvb_vb)


def t_levels(jlib, pvb_lib):
    x = music()
    rows = []
    typical = [
        ('EQ +6 dB low shelf', dict(eq=LOW_SHELF_6)),
        ('compressor +0.6', dict(comp=[0.6] * 7)),
        ('EQ +6 dB low shelf + compressor +0.6', dict(eq=LOW_SHELF_6, comp=[0.6] * 7)),
        ('EQ +6 dB low shelf + compressor (default curve)', dict(eq=LOW_SHELF_6, comp=[0.0] * 7)),
    ]
    heavy = [
        ('EQ +12 dB low shelf', dict(eq=LOW_SHELF_12)),
        ('EQ +6 dB low shelf + compressor +1.2 (max)', dict(eq=LOW_SHELF_6, comp=[1.2] * 7)),
    ]
    for group, cases in (('typical', typical), ('heavy', heavy)):
        for name, kw in cases:
            for out_db in (-5.0, -3.0):        # PVB default; general build maximum
                for vb in (False, True):
                    for block in (4096, 1024):
                        jd = Jdsp(jlib, sealed=True, **kw)
                        y, m, _ = run_chain(pvb_lib, jd, x, block, out_db=out_db, vb_on=1.0 if vb else 0.0,
                                            vb_algo=6.0, vb_level_db=6.0)
                        jd.close()
                        # per block: the deepest gain reduction of that block (so smaller blocks give lower means)
                        gr = m[3:, T.M['LIM_GR_DB']]          # skip the first blocks (fade-in)
                        tp = T.true_peak_db(y[SR // 2:])
                        nan = int(np.sum(~np.isfinite(y)))
                        r = dict(group=group, jdsp=name, pvb_out_db=out_db, vb=vb, block=block, true_peak_dbtp=tp,
                                 nan=nan, gr_mean_db=float(np.mean(gr)), gr_p95_db=float(np.percentile(gr, 95)),
                                 gr_max_db=float(np.max(gr)))
                        rows.append(r)
                        label = f'{group}: {name}, PVB out {out_db:+.0f} dB, vb {"on" if vb else "off"}, block {block}'
                        ok = tp <= -1.0 and nan == 0
                        if group == 'typical' and out_db == -5.0:
                            ok = ok and r['gr_mean_db'] <= 0.5 and r['gr_p95_db'] <= 2.0
                        T.check(label, ok, tp=tp, nan=nan, gr_mean=r['gr_mean_db'], gr_p95=r['gr_p95_db'],
                                gr_max=r['gr_max_db'])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pvb', default=os.path.join(HERE, 'build', 'libpvbcapi.so'))
    ap.add_argument('--jdsp', default=os.path.join(HERE, 'build', 'libjdspcapi.so'))
    ap.add_argument('--report', default=None)
    a = ap.parse_args()
    pvb_lib = T.load_lib(a.pvb)
    jlib = load_jdsp(a.jdsp)
    t_neutral(jlib, pvb_lib)
    lat = t_latency(jlib, pvb_lib)
    rows = t_levels(jlib, pvb_lib)
    n_fail = sum(not r['ok'] for r in T.RESULTS)
    if a.report:
        with open(a.report, 'w') as f:
            json.dump(dict(results=T.RESULTS, latency_frames=lat, levels=rows), f, indent=1)
    print(f'\n{len(T.RESULTS) - n_fail}/{len(T.RESULTS)} checks passed')
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()

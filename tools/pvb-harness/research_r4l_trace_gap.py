"""Why is the P1 sustained layer nearly absent 20-150 ms after a note onset? Harmonic trace (pvb_copy_harmonic) of the
bare 100 Hz bass, P1 defaults (vb_algo 6); one note (input 2.0-2.5 s), per hop: header onset hold / falling flag /
harmonic and percussion power / envelope compensation, and for the track near 100 Hz: state, a, fade, life, age,
missing, reason bits, then k2/k3/k4 target amp, actual amp, mask weight, reason bits, evidence.
Usage: trace_gap.py <lib> [r4l]"""
import ctypes as C, sys
import numpy as np
import test_engine as T
import research_p1plus as RP
from vb_quality.stage_capture import StageCapture
FS = 48000; FIELDS, HEADER, TRACK, TRACKS, ROWS = 700, 28, 56, 12, 72
lib = RP.api(sys.argv[1]); r4l = len(sys.argv) > 2
lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]; lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]
lib.pvb_set_r4_level.argtypes = [C.c_void_p, C.c_double]
assert lib.pvb_harmonic_fields() == FIELDS and lib.pvb_harmonic_rows() == ROWS
t = np.arange(4 * FS) / FS; u = t % .5; env = np.minimum(u / .008, 1) * np.exp(-u / .35)
bass = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in ((1, 1), (2, .5), (3, .18))); bass = .25 * bass / np.abs(bass).max()
x = np.ascontiguousarray(np.stack([bass, bass], 1), np.float32)
e = T.Engine(lib, FS, vb_on=1, vb_algo=6); cap = None
if r4l:
    assert lib.pvb_set_r4_level(e.h, 6.) == 1; cap = StageCapture(lib, e.h, 16777216 | 67108864, int(len(x) / FS * 3000) + 16)
lib.pvb_set_diagnostic_capture(e.h, 1)
rows = []; buf = np.empty(ROWS * FIELDS, np.float32); blk = 256
for off in range(0, len(x), blk):
    b = x[off:off + blk].copy(); lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
    n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
    if n > 0:
        d = buf[:n * FIELDS].reshape(n, FIELDS).copy(); d[:, 0] += off; rows.append(d)
e.close(); R = np.vstack(rows); ts = R[:, HEADER:].reshape(-1, TRACKS, TRACK)
# analysis time of a hop: the source centre offset (host samples) when present, else the callback offset
tsrc = R[:, 9] if np.any(R[:, 9] != 0) else R[:, 0]
print('hops', len(R), '| header cols: 9 src centre, 10 grain centre; using', 'src centre' if np.any(R[:, 9] != 0) else 'callback')
sel = np.flatnonzero((R[:, 0] >= 2.0 * FS) & (R[:, 0] < 2.5 * FS))
print(' t(ms)  hold fall  harmP  percP envC | st     f      a   fade  life  age miss  rsn | k2 tgt/act/mask/rsn/ev | k3 ... | k4 ...')
last = -99
for i in sel:
    tm = (R[i, 0] - 2.0 * FS) / FS * 1000
    if tm - last < 9.5: continue
    last = tm
    j = np.argmin(np.where(ts[i, :, 1] > 0, np.abs(ts[i, :, 2] - 100), 1e9))
    tr = ts[i, j]; s = ''
    for k in (2, 3, 4):
        h = tr[14 + 6 * (k - 2):20 + 6 * (k - 2)]
        s += f' | {h[0]:.3f}/{h[1]:.3f}/{h[2]:.2f}/{int(h[4]):3d}/{h[5]:.1f}'
    print(f'{tm:6.0f} {R[i, 24]:5.0f} {R[i, 25]:4.0f} {R[i, 15]:6.3f} {R[i, 16]:6.3f} {R[i, 17]:4.2f} | {int(tr[1]):2d} {tr[2]:6.1f} {tr[4]:6.3f} {tr[7]:5.2f} {tr[11]:5.2f} {tr[8]:4.0f} {tr[9]:4.0f} {int(tr[10]):4d}' + s)

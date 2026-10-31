"""D-local signal patches: extra audio keys for data.Sig (new synthetic guard signals, confirmation tracks), caches in plan16/D/cache.  Does not edit la0/data.py (monkey-patch at import)."""
import sys, shutil
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
import data as DATA
from data import X, FS, guard, HOME, CACHE as LA0_CACHE
import proxy16 as PX

D_CACHE = HOME / 'r3a-dev/plan16/D/cache'; D_CACHE.mkdir(exist_ok=True)
for p in LA0_CACHE.glob('s_*.npz'):
    if not (D_CACHE / p.name).exists():
        shutil.copy(p, D_CACHE / p.name)
for p in LA0_CACHE.glob('p1_*.npz'):
    if not (D_CACHE / p.name).exists():
        shutil.copy(p, D_CACHE / p.name)
DATA.CACHE = D_CACHE

TPK = PX.TPK
SC = .25 / TPK


def _harm(f_t, amp_t):
    ph = 2 * np.pi * np.cumsum(f_t) / FS
    return amp_t * (np.sin(ph) + .5 * np.sin(2 * ph) + .18 * np.sin(3 * ph))


def sig_gapbkp(secs=8.0):
    n = int(secs * FS); t = np.arange(n) / FS
    f = np.zeros(n); env = np.zeros(n)
    for a, b, fn in ((0.0, 2.5, 98.0), (2.5, 5.0, 82.4068892282175), (5.0, 7.5, 110.0)):
        i0, i1 = int(a * FS), int(b * FS); u = t[i0:i1] - a
        f[i0:i1] = fn
        env[i0:i1] = np.minimum(np.minimum(u / .008, 1.0), (b - a - u) / .008) * np.exp(-u / 1.5)
    x = _harm(f, env)
    x = x * (.25 / np.abs(x).max())
    return (x + .2 * X.kick_sig(secs) + X.pink_gf(secs)).astype(np.float64)


def sig_vib(cent, rate, secs=6.0, snr=20.0):
    n = int(secs * FS); t = np.arange(n) / FS
    f = 98.0 * 2 ** (cent * np.sin(2 * np.pi * rate * t) / 1200.0)
    env = np.minimum(t / .008, 1.0)
    x = _harm(f, env) * SC
    return x + PX.pink_for(x, snr)


def sig_glide(secs=6.4, snr=20.0):
    n = int(secs * FS); t = np.arange(n) / FS
    cents = np.zeros(n); level = 0.0
    for k in range(8):
        t0 = 0.5 + k * 0.8                                   # glide start
        i0, i1 = int(t0 * FS), int((t0 + 0.1) * FS)
        target = 100.0 if k % 2 == 0 else 0.0
        cents[i0:i1] = level + (target - level) * (np.arange(i1 - i0) / (i1 - i0))
        cents[i1:] = target; level = target
    f = 98.0 * 2 ** (cents / 1200.0)
    env = np.minimum(t / .008, 1.0)
    x = _harm(f, env) * SC
    return x + PX.pink_for(x, snr)


GLIDE_T0 = [0.5 + k * 0.8 for k in range(8)]
NEW = {'gapbkp': lambda: sig_gapbkp(), 'glide': lambda: sig_glide()}
for c in (30, 100):
    for r in (5, 6):
        NEW[f'vib_{c}_{r}'] = (lambda c=c, r=r: sig_vib(float(c), float(r)))
CONF = ['Track00094', 'Track00095', 'Track00096', 'Track00099', 'Track00101']
_orig_audio = DATA.audio


def audio2(key):
    if key in NEW:
        return NEW[key]()
    if key in CONF:
        p = X.SLAKH / key / 'mix.flac'; guard(p)
        return X.read_excerpt(p, 0.0, 30.0)
    return _orig_audio(key)


DATA.audio = audio2

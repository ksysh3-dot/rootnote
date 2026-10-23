"""Where does the virtual-bass layer drop out while the bass it is made from is still playing?

Uses the developer meters (5 ms ring: dry low band below the generator edge, and the layer). For each test signal it
reports, per note, the share of 5 ms bins where the source bass is present but the layer is (near) silent, and the
longest such gap. Host harness only; the app is not involved.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from test_devmode import setup, FP, P1, HERE  # noqa: E402
from test_engine import Engine, load_lib  # noqa: E402
from scipy.signal import butter, sosfilt

SR = 48000
RING = 512

def bed(n, seed=1, db=-34):
    rng = np.random.default_rng(seed)
    return sosfilt(butter(4, [500, 4000], 'bandpass', fs=SR, output='sos'), rng.standard_normal(n)) * 10 ** (db / 20)

def tone(f, dur, amp=0.25, harm=(1, .5, .3), vib=0.0, attack=0.01, decay=None):
    t = np.arange(int(dur * SR)) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR
    x = sum(a * np.sin((k + 1) * ph) for k, a in enumerate(harm))
    env = np.minimum(1, t / attack)
    if decay: env *= np.exp(-t / decay)
    env[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return amp * env * x

def stereo(x): return np.column_stack([x, x]).astype(np.float32)

def run(x, vb_db=4, block=960, **kw):
    lib = run.lib
    n = lib.pvb_dev_meter_size(); fields = lib.pvb_dev_meter_fields()
    out = np.zeros(n, np.float32)
    e = Engine(lib, SR, vb_on=1, vb_algo=P1, vb_level_db=vb_db, dev_on=1, dev_meter=1, **kw)
    dry, lay = [], []
    step = RING * int(0.005 * SR) // 2      # read well before the ring wraps
    step -= step % block
    pos = 0
    last = 0
    while pos < len(x):
        e.process(np.ascontiguousarray(x[pos:pos + step]), block=block)
        pos += step
        lib.pvb_copy_dev_meters(e.h, out.ctypes.data_as(FP), n)
        cnt = int(out[10]); new = cnt - last; last = cnt
        ring = out[fields:].reshape(-1, 2)
        dry.append(ring[-new:, 0].copy()); lay.append(ring[-new:, 1].copy())
    e.close()
    return np.concatenate(dry), np.concatenate(lay)

def gaps(dry, lay, segs, latency_bins=0, present_db=-45, silent_db=-80):
    """segs: list of (label, t0, t1) seconds. Skip the first 40 ms of each note (attack) and allow for latency."""
    rows = []
    for label, t0, t1 in segs:
        a = int((t0 + 0.04) / 0.005) + latency_bins; b = int(t1 / 0.005) + latency_bins
        d, l = dry[a:b], lay[a:b]
        pres = d > present_db
        miss = pres & (l < silent_db)
        run_, best = 0, 0
        for m in miss:
            run_ = run_ + 1 if m else 0; best = max(best, run_)
        rel = np.median(l[pres] - d[pres]) if pres.any() else np.nan
        rows.append((label, int(pres.sum()), float(miss.sum() / max(1, pres.sum())), best * 5, float(rel)))
    return rows

def report(name, rows):
    print(f'== {name}')
    for label, npres, share, longest, rel in rows:
        flag = '  <-- GAPS' if share > 0.05 or longest >= 50 else ''
        print(f'  {label:28s} bins {npres:4d}  silent {100*share:5.1f}%  longest {longest:4d} ms  layer-dry {rel:6.1f} dB{flag}')

def main():
    run.lib = setup(load_lib(os.path.join(HERE, 'build/libpvbcapi.so')))
    lat = 0
    # 1) sustained single notes across the range (1.2 s each, 0.2 s rest)
    fs = [41, 55, 73, 98, 110, 131, 147, 165, 175, 185]
    x, segs, t = [], [], 0.0
    for f in fs:
        x.append(tone(f, 1.2)); segs.append((f'{f} Hz sustained', t, t + 1.2)); t += 1.2
        x.append(np.zeros(int(0.2 * SR))); t += 0.2
    x = np.concatenate(x); x = x + bed(len(x))
    d, l = run(stereo(x))
    # latency: lag that best aligns layer onsets with dry onsets
    best = max(range(0, 60), key=lambda k: np.corrcoef((d[:-60] > -45).astype(float), (l[k:len(d) - 60 + k] > -80).astype(float))[0, 1])
    lat = best
    print(f'layer latency estimate: {lat * 5} ms')
    report('1 sustained notes', gaps(d, l, segs, lat))
    # 2) legato bass line (no rests), with slides between notes
    line = [55, 62, 73, 65, 49, 55, 82, 73, 98, 87, 65, 55]
    x, segs, t = [], [], 0.0
    for f in line:
        x.append(tone(f, 0.5, attack=0.003)); segs.append((f'legato {f} Hz', t, t + 0.5)); t += 0.5
    x = np.concatenate(x); x = x + bed(len(x))
    d, l = run(stereo(x)); report('2 legato line', gaps(d, l, segs, lat))
    # 3) two notes at once (octave apart and a fifth apart)
    x = np.concatenate([tone(55, 1.5) + tone(110, 1.5, amp=.18), tone(55, 1.5) + tone(82.4, 1.5, amp=.2)])
    x = x + bed(len(x))
    d, l = run(stereo(x)); report('3 two notes', gaps(d, l, [('55+110', 0, 1.5), ('55+82.4', 1.5, 3.0)], lat))
    # 4) vibrato and a pitch slide
    t2 = np.arange(int(2 * SR)) / SR
    slide = 0.25 * np.sin(2 * np.pi * np.cumsum(55 * 2 ** (t2 / 2)) / SR)
    x = np.concatenate([tone(73, 1.5, vib=0.02), slide]); x = x + bed(len(x))
    d, l = run(stereo(x)); report('4 vibrato / slide', gaps(d, l, [('73 Hz vibrato 2%', 0, 1.5), ('slide 55->110', 1.5, 3.5)], lat))
    # 5) bass under a loud low-mid part (vocal/piano 200-400 Hz)
    mid = tone(262, 3.0, amp=.25, harm=(1, .6, .4, .3)) + tone(330, 3.0, amp=.2, harm=(1, .5, .3))
    x = tone(65, 3.0) + mid; x = x + bed(len(x))
    d, l = run(stereo(x)); report('5 bass under loud low-mids', gaps(d, l, [('65 Hz + 262/330 Hz', 0, 3.0)], lat))
    # 6) quiet bass (-20 dB) under the same bed
    x = tone(55, 2.0, amp=.025); x = x + bed(len(x), db=-30)
    d, l = run(stereo(x)); report('6 quiet bass', gaps(d, l, [('55 Hz at -20 dB', 0, 2.0)], lat, present_db=-60))

if __name__ == '__main__':
    main()

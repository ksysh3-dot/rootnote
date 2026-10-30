"""Resultant redesign feasibility: without the fit gate, a confident wrong pitch would render wrong harmonics at the
input envelope. How often is P1's tracker wrong where the bass is loud? Slakh train tracks (validation split untouched),
first 30 s: per analysis hop (source centre time), the MIDI bass f0 (octave from the stem's YIN, research_gt_bass),
the bass stem 40-220 Hz level; on hops with a MIDI note and the stem within 10 dB of its p95 ("loud bass"): the
strongest 40-220 Hz P1 track vs MIDI (> 50 cents = wrong; octave errors separately), and whether any track is right.
Usage: pitch_truth.py <lib> <slakh train dir> <track> ..."""
import ctypes as C, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, resample_poly
import test_engine as T
import research_p1plus as RP
import research_gt_bass as G
FS = 48000; FIELDS, HEADER, TRACK, TRACKS, ROWS = 700, 28, 56, 12, 72
lib = RP.api(sys.argv[1]); root = Path(sys.argv[2])
lib.pvb_set_diagnostic_capture.argtypes = [C.c_void_p, C.c_int]; lib.pvb_copy_harmonic.argtypes = [C.c_void_p, T.FP, C.c_int]
def trace(x):
    x = np.ascontiguousarray(x, np.float32); e = T.Engine(lib, FS, vb_on=1, vb_algo=6); lib.pvb_set_diagnostic_capture(e.h, 1)
    rows = []; buf = np.empty(ROWS * FIELDS, np.float32)
    for off in range(0, len(x), 256):
        b = x[off:off + 256].copy(); lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        n = lib.pvb_copy_harmonic(e.h, buf.ctypes.data_as(T.FP), len(buf))
        if n > 0: d = buf[:n * FIELDS].reshape(n, FIELDS).copy(); d[:, 0] += off; rows.append(d)
    e.close(); R = np.vstack(rows); return R, R[:, HEADER:].reshape(-1, TRACKS, TRACK)
tot = dict(n=0, wrong=0, octave=0, none=0, anyright=0)
for name in sys.argv[3:]:
    d = root / name
    import re
    meta = (d / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
    stems = [p for p in (next((d / 'stems' / f'{i}{x}' for x in ('.wav', '.flac') if (d / 'stems' / f'{i}{x}').exists()), None) for i in ids) if p]
    midis = [m for m in (d / 'MIDI' / f'{s.stem}.mid' for s in stems) if m.exists()]
    if not stems or not midis: print(name, 'no bass stem / MIDI'); continue
    mix, fs = sf.read(str(next(d / n for n in ('mix.wav', 'mix.flac') if (d / n).exists())), always_2d=True)
    bz = sum(sf.read(str(s), always_2d=True)[0].mean(axis=1) for s in stems)
    notes = sum((G.midi_notes(m) for m in midis), [])
    mix = mix[:30 * fs]; bz = bz[:30 * fs]
    if mix.shape[1] == 1: mix = np.repeat(mix, 2, 1)
    x = np.clip(resample_poly(mix, 160, 147, axis=0) if fs == 44100 else mix, -1, 1)
    bzr = resample_poly(bz, 160, 147) if fs == 44100 else bz
    R, ts = trace(x)
    # octave of the MIDI reference from the stem (as research_gt_bass does), on its own frame grid
    try:
        ty, fy = G.yin(G.to_rate(bzr, FS, G.CORE))
        agree = {}
        for t in (-24, -12, 0, 12):
            fm = G.midi_f0(ty, notes, 0, t); both = np.isfinite(fm) & np.isfinite(fy)
            agree[t] = float(np.mean(np.abs(1200 * np.log2(fm[both] / fy[both])) < 50)) if both.sum() >= 20 else -1
        tp = max(agree, key=agree.get)
    except Exception as ex:
        print(name, 'octave failed', ex); continue
    lo = sosfiltfilt(butter(4, [40, 220], btype='band', fs=FS, output='sos'), bzr)
    def score(lag):
        tc = R[:, 0] / FS - lag   # callback time minus the analysis lag = input time of the estimate
        fm = G.midi_f0(tc, notes, 0, tp)
        win = 2048; lev = np.array([10 * np.log10(np.mean(lo[max(0, int(c * FS) - win // 2):max(1, int(c * FS) + win // 2)] ** 2) + 1e-20) for c in tc])
        act = np.isfinite(fm) & (tc > .5); loud = act & (lev > np.percentile(lev[act], 95) - 10) if act.any() else act
        n = wrong = octv = none = anyr = 0
        for i in np.flatnonzero(loud):
            v = [(ts[i, j, 4], ts[i, j, 2]) for j in range(TRACKS) if ts[i, j, 1] > 0 and 40 <= ts[i, j, 2] <= 220]
            n += 1
            if not v: none += 1; continue
            f = max(v)[1]; c = 1200 * np.log2(f / fm[i])
            if abs(c) > 50:
                wrong += 1
                if abs(abs(c) - 1200) < 50 or abs(abs(c) - 1902) < 50: octv += 1
            if any(abs(1200 * np.log2(ff / fm[i])) <= 50 for _, ff in v): anyr += 1
        return n, wrong, octv, none, anyr
    lags = np.arange(0, .32, .02); res = [score(l) for l in lags]
    k = int(np.argmin([r[1] / max(r[0], 1) for r in res])); n, wrong, octv, none, anyr = res[k]
    print(f'{name}: octave shift {tp:+d} (agree {agree[tp]:.2f}), lag {lags[k] * 1000:.0f} ms | loud-bass hops {n}: strongest track wrong {100 * wrong / max(n, 1):.1f} % '
          f'(octave/12th {100 * octv / max(n, 1):.1f} %), no track {100 * none / max(n, 1):.1f} %, some track right {100 * anyr / max(n, 1):.1f} %')
    for k, v in zip(('n', 'wrong', 'octave', 'none', 'anyright'), (n, wrong, octv, none, anyr)): tot[k] += v
N = max(tot['n'], 1)
print(f'ALL: {tot["n"]} hops, strongest wrong {100 * tot["wrong"] / N:.1f} % (octave/12th {100 * tot["octave"] / N:.1f} %), '
      f'no track {100 * tot["none"] / N:.1f} %, some track right {100 * tot["anyright"] / N:.1f} %')

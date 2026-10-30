"""Fixed test signals and data helpers for research_core_metrics.py (Resultant core acceptance metrics V1-V9,
docs/RESULTANT_CORE.md v1.2). Everything here is deterministic (seeded) and carries a one-line definition in DEFS, which
the metrics script copies into its JSON. Mono signals are 1-D float64 at 48 kHz; stereo() turns them into the 2-channel
float32 the engine needs.

Conventions fixed here (the spec leaves them open):
  dBFS of a tone/waveform = PEAK (a 3-partial 1:0.5:0.18 sine-phase waveform scaled so its peak is the stated level);
  dBFS of noise = RMS (amplitude 10^(dB/20) of a full-scale sine's RMS-free scale, i.e. rms = 10^(dB/20));
  every note has a linear attack of 8 ms from zero (and, where a note ends inside a signal, a linear 8 ms release).
"""
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

FS = 48000
HOME = Path.home()
SLAKH_TRAIN = HOME / 'datasets/slakh2100/train'          # train split ONLY; validation/test are never opened
SLAKH_MIDI_ALL = HOME / 'datasets/slakh2100_midi/train'   # all-instrument MIDI + metadata of the 10 V6 train tracks (v1.4)
MUSDB_ROOT = HOME / 'datasets/musdb7/extracted/train'    # the MUSDB18 7 s excerpts used by the R4 development runs
LOGOFF = HOME / 'r3a-dev/songs/logoff.mp3'
PARTIALS = ((1, 1.0), (2, 0.5), (3, 0.18))               # the bass spectrum of every earlier R4-L script
DB = lambda a: 10 ** (a / 20.0)
DEFS = {}


def _peak_of_triple():
    ph = np.linspace(0, 2 * np.pi, 400001)
    return float(np.abs(sum(a * np.sin(k * ph) for k, a in PARTIALS)).max())


TRIPLE_PEAK = _peak_of_triple()       # peak of sin + 0.5 sin2 + 0.18 sin3 (all in sine phase)


def stereo(x):
    return np.ascontiguousarray(np.repeat(np.asarray(x, np.float32)[:, None], 2, axis=1))


def _guard(path):
    p = str(path)
    if re.search(r'slakh2100/(validation|test)(/|$)', p):
        raise RuntimeError('refusing to open the Slakh validation/test split: ' + p)


def pink(seconds, rms, seed=1, gen_seconds=10.0):
    """1/f noise (power ~ 1/max(f, 20 Hz)); the recipe of research_r4l_gate_flicker.py: generate gen_seconds, scale the
    WHOLE to `rms`, then cut `seconds` (so a cut shorter than gen_seconds has an rms close to, not exactly, `rms`)."""
    n = max(int(round(gen_seconds * FS)), int(round(seconds * FS)))
    n += n % 2
    rng = np.random.default_rng(seed)
    w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(np.fft.rfftfreq(n, 1 / FS), 20)), n)
    w = rms * w / np.sqrt(np.mean(w ** 2))
    return w[:int(round(seconds * FS))]


def _ramp(m, attack=0.008, release=None):
    k = np.arange(m)
    env = np.minimum(k / (attack * FS), 1.0)
    if release:
        env = np.minimum(env, (m - k) / (release * FS))
    return np.clip(env, 0.0, 1.0)


# ------------------------------------------------------------------------------------------------ V1 / V2
def tone_steady(seconds=4.0, f=100.0):
    """V1/V2 steady tone: partials 1:0.5:0.18 of f (sine phase 0), peak -12 dBFS, 8 ms linear attack, no release."""
    t = np.arange(int(round(seconds * FS))) / FS
    x = sum(a * np.sin(2 * np.pi * k * f * t) for k, a in PARTIALS)
    x = x * (DB(-12) / TRIPLE_PEAK)
    x *= _ramp(len(x))
    return x


DEFS['tone_steady'] = ('V1/V2: 4 s, 100 Hz + 200 + 300 Hz (amplitudes 1:0.5:0.18, sine phase 0), waveform peak -12 dBFS, '
                       '8 ms linear attack, steady until the end')


# ------------------------------------------------------------------------------------------------ V3 a/b/d, V4
def bass_notes(seconds):
    """The earlier R4-L bass: a note every 0.5 s on 100 Hz, partials 1:0.5:0.18, 8 ms attack x exp(-u/0.35 s) decay,
    peak 0.25 (-12 dBFS). Identical to research_r4l_timing_layer.py (9 s) / research_r4l_gate_flicker.py (8 s)."""
    t = np.arange(int(round(seconds * FS))) / FS
    u = t % .5
    env = np.minimum(u / .008, 1) * np.exp(-u / .35)
    b = env * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in PARTIALS)
    return .25 * b / np.abs(b).max()


def flicker_signals(seconds=8.0):
    """research_r4l_gate_flicker.py signals: bass, bass + pink (rms 0.03, seed 1), bass + 0.2 kick + pink. Kick: 50 Hz
    +40 Hz*exp(-u/20 ms) sweep, exp(-u/120 ms), every 0.5 s."""
    t = np.arange(int(round(seconds * FS))) / FS
    u = t % .5
    pk = pink(seconds, .03, seed=1, gen_seconds=10.0)
    kick = np.exp(-u / .12) * np.sin(2 * np.pi * np.cumsum(50 + 40 * np.exp(-u / .02)) / FS)
    b = bass_notes(seconds)
    return {'bass': b, 'bass+pink': b + pk, 'bass+kick+pink': b + .2 * kick + pk}


DEFS['bass_notes'] = ('bare bass: a note every 0.5 s on 100 Hz (partials 1:0.5:0.18), 8 ms attack, exp(-u/0.35 s) decay, '
                      'peak 0.25; 9 s for V3a/b/d, 8 s for V4 (research_r4l_timing_layer / gate_flicker recipe)')
DEFS['flicker'] = ('V4 signals (research_r4l_gate_flicker.py): bass+pink = bare bass + pink noise rms 0.03 (-30.5 dBFS, '
                   'seed 1, 1/max(f,20 Hz) power); bass+kick+pink = bare bass + 0.2*kick + the same pink. 8 s, notes 2..15 used')


# ------------------------------------------------------------------------------------------------ V3c stepwise line
STEP_NOTES = [98.0, 104.0] * 10 + [98.0, 110.0] * 10     # 40 notes of 125 ms = 5.0 s: a semitone, then a whole tone
STEP_DUR = 0.125


def band_power(x, lo=80.0, hi=200.0, mask=None):
    """Mean square of x restricted to lo..hi Hz (FFT mask), over the samples where `mask` is true (all if None)."""
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / FS)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, len(x))
    return float(np.mean(y[mask] ** 2) if mask is not None else np.mean(y ** 2))


def pink_for_band_snr(clean, snr_db, on_mask=None, seed=1):
    """Pink noise (the pink() recipe) scaled so that bass power / noise power in 80-200 Hz = snr_db (v1.3 definition of the noise
    level: the clean signal's power is taken over `on_mask` samples only, the noise over the whole length)."""
    unit = pink(len(clean) / FS, 1.0, seed=seed, gen_seconds=max(10.0, len(clean) / FS))
    g = np.sqrt(band_power(clean, mask=on_mask) / (band_power(unit) * 10 ** (snr_db / 10.0)))
    return unit * g


def stepwise_line(snr_db=25.0, seed=1):
    scale = .25 / TRIPLE_PEAK
    n_notes = len(STEP_NOTES)
    clean = np.zeros(int(round(n_notes * STEP_DUR * FS)))
    for i, f in enumerate(STEP_NOTES):
        n0 = int(round(i * STEP_DUR * FS)); n1 = int(round((i + 1) * STEP_DUR * FS)); m = n1 - n0
        u = np.arange(m) / FS
        clean[n0:n1] = scale * _ramp(m, .008, .008) * sum(a * np.sin(2 * np.pi * k * f * u) for k, a in PARTIALS)
    noisy = clean + (pink_for_band_snr(clean, snr_db, seed=seed) if snr_db is not None else 0.0)
    return dict(clean=clean, noisy=noisy, notes=list(STEP_NOTES), dur=STEP_DUR, snr_db=snr_db,
                t0=[i * STEP_DUR for i in range(n_notes)])


def gated_line(snr_db=25.0, seed=1):
    """V3h variant of the stepwise line: the same 40 notes (98/104 then 98/110 Hz) but each 125 ms note is followed by 125 ms
    without a note (the pink bed continues), so the rise after an attack and the tail after a note end are not masked by the
    next note. Period 250 ms, 10 s."""
    scale = .25 / TRIPLE_PEAK
    per = 2 * STEP_DUR; n_notes = len(STEP_NOTES)
    clean = np.zeros(int(round(n_notes * per * FS))); on = np.zeros(len(clean), bool)
    for i, f in enumerate(STEP_NOTES):
        n0 = int(round(i * per * FS)); m = int(round(STEP_DUR * FS)); u = np.arange(m) / FS
        clean[n0:n0 + m] = scale * _ramp(m, .008, .008) * sum(a * np.sin(2 * np.pi * k * f * u) for k, a in PARTIALS)
        on[n0:n0 + m] = True
    noisy = clean + (pink_for_band_snr(clean, snr_db, on_mask=on, seed=seed) if snr_db is not None else 0.0)
    return dict(clean=clean, noisy=noisy, notes=list(STEP_NOTES), dur=STEP_DUR, snr_db=snr_db, t0=[i * per for i in range(n_notes)])


def chatter_tone(seconds=10.0, snr_db=8.0, seed=1):
    """V3i: the V1 tone (100 Hz, 1:0.5:0.18, peak -12 dBFS) for 10 s on pink noise at in-band (80-200 Hz) SNR 8 dB."""
    clean = tone_steady(seconds)
    return dict(clean=clean, noisy=clean + pink_for_band_snr(clean, snr_db, seed=seed), snr_db=snr_db)


DEFS['stepwise_line'] = ('V3c: 40 notes of 125 ms, 98<->104 Hz (notes 0-19) then 98<->110 Hz (notes 20-39); each note restarts at '
                         'sine phase 0, partials 1:0.5:0.18, peak 0.25, linear 8 ms attack AND 8 ms release (flat sustain); plus pink '
                         'noise (seed 1) scaled so bass power / noise power in 80-200 Hz = 25 dB (base) or 6 dB. Evaluated notes: 2..39 except 20')
DEFS['gated_line'] = ('V3h: the stepwise line with 125 ms of no-note after every 125 ms note (period 250 ms, 10 s); same notes, same pink '
                      'bed scaled to in-band SNR 25 / 6 dB, the bass power taken over the note-on samples')
DEFS['chatter_tone'] = 'V3i: the V1 tone for 10 s on pink (seed 1) at in-band (80-200 Hz) SNR 8 dB'


def tail_note(seconds=3.5):
    """V3d tail report: one 100 Hz note [0.5, 1.5) s (partials 1:0.5:0.18, peak 0.25, 8 ms attack/release), then silence."""
    x = np.zeros(int(round(seconds * FS)))
    n0, n1 = int(.5 * FS), int(1.5 * FS)
    t = np.arange(n1 - n0) / FS
    x[n0:n1] = (.25 / TRIPLE_PEAK) * _ramp(n1 - n0, .008, .008) * sum(a * np.sin(2 * np.pi * k * 100 * t) for k, a in PARTIALS)
    return x


DEFS['tail_note'] = 'V3d tail (reported only): one 100 Hz note on [0.5, 1.5) s, 1:0.5:0.18, peak 0.25, 8 ms attack and release, then 2 s of silence'


# ------------------------------------------------------------------------------------------------ V3e close pairs
def close_pair(df, seconds=4.0, f1=100.0):
    """Two steady tones f1 and f1+df, each = the V1 tone (partials 1:0.5:0.18, sine phase 0) scaled by 0.5 (so the sum peaks
    at most at -12 dBFS), 8 ms attack, `seconds` long. Returns (pair, alone_1, alone_2) with the same per-tone level."""
    n = int(round(seconds * FS)); t = np.arange(n) / FS; r = _ramp(n)
    tone = lambda f: .5 * DB(-12) / TRIPLE_PEAK * sum(a * np.sin(2 * np.pi * k * f * t) for k, a in PARTIALS) * r
    a1, a2 = tone(f1), tone(f1 + df)
    return a1 + a2, a1, a2


DEFS['close_pair'] = ('V3e: 100 Hz + (100+df) Hz, df = 4 and 10 Hz; each tone = 0.5 x the V1 tone (partials 1:0.5:0.18, sine phase 0), '
                      '4 s, 8 ms attack, no noise; the "alone" references are the single tones at the same level')


# ------------------------------------------------------------------------------------------------ V3f weak tail + attack
def _hann_floor_and_peak(noise_unit, f, N=6144, hop=1536):
    """In the engine's SNR convention (5.4): 128 ms Hann magnitude spectrum, floor = median magnitude of the bins 22-45 Hz away
    from f (both sides), per frame, then the median over frames; peak gain = max magnitude within +-2 bins of f for a unit
    sine at f. Returns (floor for rms-1 noise, peak per unit sine amplitude)."""
    w = np.hanning(N); fr = np.fft.rfftfreq(N, 1 / FS)
    ring = (np.abs(fr - f) >= 22) & (np.abs(fr - f) <= 45)
    meds = []
    for s in range(0, len(noise_unit) - N, hop):
        X = np.abs(np.fft.rfft(noise_unit[s:s + N] * w)); meds.append(np.median(X[ring]))
    t = np.arange(N) / FS
    X = np.abs(np.fft.rfft(np.sin(2 * np.pi * f * t + .3) * w))
    near = np.abs(fr - f) <= 2 * FS / N
    return float(np.median(meds)), float(X[near].max())


def weak_tail_attack(seed=3, a_new=0.1, snr_old_db=7.0, snr_new_db=25.0):
    """V3f: 3.0 s over a pink noise bed. An 80 Hz note (partials 1:0.5:0.18) attacks at 0.2 s, sustains at the same fundamental
    level as the later note until 0.9 s, then decays exponentially so that its fundamental's SNR is `snr_old_db` at the
    moment T_a = 1.4 s when a 110 Hz note (fundamental amplitude a_new, partials 1:0.5:0.18, 8 ms attack) starts; the new
    note's SNR is `snr_new_db`. SNR = the engine's 5.4 definition applied to the INPUT (128 ms Hann magnitude spectrum
    peak vs median magnitude of the bins 22-45 Hz away). The 110 Hz note sustains to 2.9 s (8 ms release); the 80 Hz note
    keeps decaying to the end."""
    n = int(round(3.0 * FS)); t = np.arange(n) / FS
    unit = pink(3.0, 1.0, seed=seed, gen_seconds=10.0)
    fl80, pk80 = _hann_floor_and_peak(unit, 80.0); fl110, pk110 = _hann_floor_and_peak(unit, 110.0)
    rms_n = a_new * pk110 / (fl110 * DB(snr_new_db))
    noise = unit * rms_n
    a80_T = rms_n * fl80 * DB(snr_old_db) / pk80                    # old note's fundamental amplitude at T_a
    Ta, t_dec = 1.4, 0.9
    if not a80_T < a_new:
        raise ValueError('calibration: the old note would have to be louder than the new one')
    tau = (Ta - t_dec) / np.log(a_new / a80_T)
    part = lambda f: sum(a * np.sin(2 * np.pi * k * f * t) for k, a in PARTIALS)    # 80*0.2 and 110*1.4 are whole cycles: sine phase 0 at the starts
    g80 = a_new * np.where(t < t_dec, 1.0, np.exp(-(t - t_dec) / tau))
    k80 = int(round(.2 * FS)); env80 = np.zeros(n); env80[k80:] = _ramp(n - k80, .008)
    n80 = g80 * env80 * part(80.0)
    k0 = int(round(Ta * FS)); k1 = int(round(2.9 * FS))
    n110 = np.zeros(n); n110[k0:k1] = a_new * _ramp(k1 - k0, .008, .008) * part(110.0)[k0:k1]
    x = noise + n80 + n110
    return dict(x=x, Ta=Ta, f_old=80.0, f_new=110.0, tau=float(tau), rms_noise=float(rms_n), a_old_at_Ta=float(a80_T), a_new=a_new,
                steady_win=(Ta + 0.3, Ta + 1.2), peak=float(np.abs(x).max()))


DEFS['weak_tail_attack'] = ('V3f: 3.0 s; pink bed (seed 3) whose rms makes the 110 Hz note SNR 25 dB; 80 Hz note (1:0.5:0.18) from 0.2 s, '
                            'steady (fundamental 0.1) to 0.9 s, then exp decay so its SNR is 7 dB at T_a = 1.4 s; 110 Hz note (fundamental '
                            '0.1, 1:0.5:0.18, 8 ms attack/release) on [1.4, 2.9). SNR measured on the input as in spec 5.4')


# ------------------------------------------------------------------------------------------------ V3g low notes
LOW_NOTES = ((35.0, 0.3, 2.3), (45.0, 2.8, 4.8))


def low_notes(amp=0.1):
    """V3g: a steady 35 Hz note on [0.3, 2.3) s and a steady 45 Hz note on [2.8, 4.8) s, total 5.3 s; each = fundamental + 2nd
    harmonic at EQUAL amplitude `amp` (sine phase 0), 8 ms linear attack and release, no noise."""
    n = int(round(5.3 * FS)); x = np.zeros(n)
    for f, a, b in LOW_NOTES:
        n0, n1 = int(round(a * FS)), int(round(b * FS)); t = np.arange(n1 - n0) / FS
        x[n0:n1] = _ramp(n1 - n0, .008, .008) * amp * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * 2 * f * t))
    return x


DEFS['low_notes'] = 'V3g: 35 Hz on [0.3,2.3) s and 45 Hz on [2.8,4.8) s; fundamental and 2nd harmonic both amplitude 0.1 (sine phase 0), 8 ms attack/release, no noise'


# ------------------------------------------------------------------------------------------------ V9
def pink_only(seconds=10.0, dbfs=-30.0, seed=1):
    return pink(seconds, DB(dbfs), seed=seed)


DEFS['pink_only'] = 'V9: 10 s pink noise rms 10^(-30/20) (-30 dBFS), seed 1'


def music_silence_noise(music_a, music_b):
    """V9 composite (stereo): music_a (3 s) | 2 s digital silence | 4 s pink noise rms -30 dBFS (mono -> both channels) | 2 s
    digital silence | music_b (3 s). 14 s."""
    z = lambda s: np.zeros((int(s * FS), 2), np.float32)
    nz = stereo(pink(4.0, DB(-30), seed=1))
    return np.concatenate([music_a[:3 * FS], z(2), nz, z(2), music_b[:3 * FS]], axis=0).astype(np.float32)


DEFS['music_silence_noise'] = ('V9 composite (14 s): Track00060 song time 40-43 s | 2 s silence | 4 s pink -30 dBFS rms | 2 s silence | '
                               'Track00060 43-46 s; scored on input time 4-10.9 s (after the first music ends, before the second begins)')


# ------------------------------------------------------------------------------------------------ audio loading
def load_excerpt(path, start_s, dur_s, pad_s=0.3):
    """Stereo float32 at 48 kHz, clipped to +-1, of [start_s, start_s+dur_s). Reads pad_s more on each side before the polyphase
    resampler (160/147 for 44.1 kHz) so the filter edge never reaches the excerpt."""
    _guard(path)
    info = sf.info(str(path)); fs = info.samplerate
    s0 = max(0, int(round((start_s - pad_s) * fs))); s1 = min(info.frames, int(round((start_s + dur_s + pad_s) * fs)))
    try:
        x, _ = sf.read(str(path), start=s0, frames=s1 - s0, always_2d=True, dtype='float64')
    except Exception:
        x, _ = sf.read(str(path), always_2d=True, dtype='float64'); x = x[s0:s1]
    x = np.repeat(x, 2, 1) if x.shape[1] == 1 else x[:, :2]
    if fs != FS:
        g = np.gcd(fs, FS); x = resample_poly(x, FS // g, fs // g, axis=0)
    off = int(round((start_s - s0 / fs) * FS))
    y = x[off:off + int(round(dur_s * FS))]
    return np.clip(y, -1, 1).astype(np.float32)


# ------------------------------------------------------------------------------------------------ Slakh (train only)
def slakh_item(name):
    d = SLAKH_TRAIN / name
    _guard(d)
    meta = (d / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
    stems = [p for p in (next((d / 'stems' / f'{i}{x}' for x in ('.wav', '.flac') if (d / 'stems' / f'{i}{x}').exists()), None) for i in ids) if p]
    midis = [m for m in (d / 'MIDI' / f'{s.stem}.mid' for s in stems) if m.exists()]
    mix = next((d / n for n in ('mix.wav', 'mix.flac') if (d / n).exists()), None)
    # v1.4: the MIDI of EVERY instrument of the 10 V6 train tracks (copied from the original archive, train only)
    md = SLAKH_MIDI_ALL / name
    allm = sorted((md / 'MIDI').glob('*.mid')) if (md / 'MIDI').is_dir() else (sorted((d / 'MIDI').glob('*.mid')) if (d / 'MIDI').is_dir() else [])
    drum_ids = []
    if (md / 'metadata.yaml').exists():
        pm = re.split(r'\n\s{2}(S\d+):\s*\n', (md / 'metadata.yaml').read_text(encoding='utf-8', errors='replace'))
        drum_ids = [pm[i] for i in range(1, len(pm) - 1, 2) if re.search(r'is_drum:\s*true', pm[i + 1])]
    drums = [m for m in allm if m.stem in drum_ids]
    return dict(name=name, dir=d, mix=mix, bass_stems=stems, bass_midis=midis, all_midis=allm, drum_midis=drums)


V6_FIXED = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020']


def v6_tracks(extra=4):
    """The six tracks of research_resultant_pitch_truth.py plus the next `extra` train tracks numerically after Track00020 that
    have a Bass stem file with its MIDI (and a mix)."""
    out = list(V6_FIXED); k = 21; found = 0
    while found < extra and k < 400:
        name = f'Track{k:05d}'
        try:
            it = slakh_item(name)
            if it['mix'] and it['bass_stems'] and it['bass_midis']:
                out.append(name); found += 1
        except Exception:
            pass
        k += 1
    return out


def musdb_items(n=8):
    """Every 12th item (alphabetical) of the MUSDB18 7 s train excerpts: [(name, mixture.wav path)]."""
    names = sorted(p.name for p in MUSDB_ROOT.iterdir() if (p / 'mixture.wav').exists())
    return [(nm, MUSDB_ROOT / nm / 'mixture.wav') for nm in names[::12][:n]]

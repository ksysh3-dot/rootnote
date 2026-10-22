"""Validate the inherited six-section fit against the stored speaker + approximate K target.

This restores a reproducible coefficient check, not the missing original optimizer. The target is a
research proxy from study/phone_model.py, NOT a conformant BS.1770 meter or a new phone measurement.
Run directly for errors at 44.1/48 kHz. No audio files are needed.
"""
import json
import pathlib
import sys
import numpy as np
from scipy.signal import sosfreqz

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'study'))
import phone_model as phone

SECTIONS = [(0, 60.7, 0, .40), (0, 343.8, 0, .986), (2, 2726, 8.83, 1.454),
            (2, 5119, 11.29, 1.449), (2, 432.3, -8.67, 1.170), (1, 7436, 0, 2.082)]


def weighting_sos(fs):
    rows = []
    for kind, f, db, q in SECTIONS:
        a = 10 ** (db / 40); w = 2 * np.pi * min(f, .45 * fs) / fs
        c, al = np.cos(w), np.sin(w) / (2 * q)
        if kind == 0:
            b, d = [(1+c)/2, -(1+c), (1+c)/2], [1+al, -2*c, 1-al]
        elif kind == 1:
            b, d = [(1-c)/2, 1-c, (1-c)/2], [1+al, -2*c, 1-al]
        else:
            b, d = [1+al*a, -2*c, 1-al*a], [1+al/a, -2*c, 1-al/a]
        rows.append(np.r_[b, d] / d[0])
    return np.array(rows)


def proxy_db(x, fs):
    """Independent frequency-domain target; sums stereo powers, never folds channels to mono."""
    x = np.asarray(x, float)
    if x.ndim == 1: x = x[:, None]
    f = np.fft.rfftfreq(len(x), 1 / fs)
    p = np.sum(abs(np.fft.rfft(x, axis=0)) ** 2, axis=1)
    w = phone._k_weight(f) * 10 ** (phone.speaker_db(f) / 10)
    return float(10 * np.log10(np.sum(p * w) / len(x)**2 + 1e-30))


def validate():
    rows = []
    f = np.geomspace(125, 12500, 400)
    target = phone.speaker_db(f) + 10 * np.log10(phone._k_weight(f))
    for fs in (44100, 48000):
        _, h = sosfreqz(weighting_sos(fs), worN=f, fs=fs)
        err = 20 * np.log10(abs(h)) - target
        # A constant offset cancels in E_out/E_in. Report it separately; assess spectral shape after removal.
        offset = float(err.mean())
        err -= offset
        rows.append(dict(fs=fs, offset_db=offset, rms_db=float(np.sqrt(np.mean(err**2))), max_db=float(max(abs(err)))))
    return rows


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))

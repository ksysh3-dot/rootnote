#!/usr/bin/env python3
"""Ground-truth bass benchmark (#4 follow-up): how well does a model's generated layer follow the real bass of a full
mix, when the bass is known from its own isolated track? Local datasets only (MUSDB18 7 s WAV excerpts, BabySlakh);
no audio is committed and nothing here is a listening score.

Truth: the isolated bass stem, mono, at 3 kHz, low-passed at 400 Hz; YIN f0 (28-300 Hz, 85 ms frames, hop 10 ms,
CMNDF threshold 0.15) where the frame is within 35 dB of the stem's loudest frame; unvoiced otherwise.
Each mix (48 kHz) is rendered by the model; the first 1 s (warm-up) and the last 0.2 s are left out.
  tracked       share of voiced frames where a live model track (amplitude >= 10 % of the hop's strongest) lies within
                50 cents of the true f0 (track time = analysis-window centre, core index - 383)
  octave        share of voiced frames whose nearest strong track is within 50 cents of 2 f0 or f0 / 2 instead
  cents         median |cents| of the nearest strong track to f0 where tracked
  bass_share    over 128 ms frames (hop 32 ms) with a steady true f0 (spread < 1.5 %): share of the layer energy
                (120-1450 Hz) within max(3 Hz, 1.5 %) of k f0, k = 2..8 (the layer reinforcing the real bass)
  idle_layer_db layer energy in frames with no bass (unvoiced 128 ms frames) relative to frames with bass
"""
import argparse
import json
import re
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfiltfilt
import research_p1plus as P
import test_harmonic_continuity as H
from p1plus_paths import default_library

FS, CORE = 48000, 3000
LP = butter(4, 400, fs=CORE, output='sos')
MODELS = {'p1': (0, 0), 'p1_c1': (0, 8192), 'p1_s3': (0, 32768 | 131072), 'p1plus': (6, 0),
          'p1_r3': (0, 2097152), 'p1_r3s': (0, 4194304), 'p1_c1_r3': (0, 8192 | 2097152)}


def to_rate(x, fs, target):
    g = np.gcd(int(fs), target); return resample_poly(x, target // g, int(fs) // g, axis=0)


def yin(z, w=256, hop=30, fmin=28, fmax=300, th=.15):
    tmin, tmax = int(CORE / fmax), int(CORE / fmin) + 1
    starts = range(0, len(z) - w - tmax, hop); f0 = []; rms = []
    for s in starts:
        x = z[s:s + w + tmax]; seg = x[:w]
        d = np.array([np.sum((seg - x[t:t + w]) ** 2) for t in range(tmax + 1)])
        c = np.cumsum(d[1:]); cm = np.r_[1, d[1:] * np.arange(1, tmax + 1) / np.maximum(c, 1e-20)]
        cand = [t for t in range(tmin, tmax) if cm[t] < th and cm[t] <= cm[t - 1] and cm[t] <= cm[t + 1]]
        if cand:
            t = cand[0]; a, b, c2 = cm[t - 1], cm[t], cm[t + 1]; den = a - 2 * b + c2
            f0.append(CORE / (t + (.5 * (a - c2) / den if abs(den) > 1e-12 else 0)))
        else: f0.append(np.nan)
        rms.append(np.sqrt(np.mean(seg ** 2)))
    t = (np.array(list(starts)) + w / 2) / CORE; f0 = np.array(f0); rms = np.array(rms)
    f0[rms < rms.max() * 10 ** (-35 / 20)] = np.nan
    return t, f0


def items(root):
    """(name, mix 48 kHz stereo, bass stem mono at its rate, rate) from MUSDB-style or Slakh-style folders."""
    for d in sorted(p for p in root.rglob('*') if p.is_dir()):
        if (d / 'mixture.wav').exists() and (d / 'bass.wav').exists():
            mix, fs = sf.read(str(d / 'mixture.wav'), always_2d=True); bass, _ = sf.read(str(d / 'bass.wav'), always_2d=True)
            yield d.name, mix, bass.mean(axis=1), fs
        elif (d / 'metadata.yaml').exists() and (d / 'stems').is_dir():
            meta = (d / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
            parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)   # [head, id, block, id, block, ...]
            ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
            mixf = next((d / n for n in ('mix.wav', 'mix.flac') if (d / n).exists()), None)
            stems = [d / 'stems' / f'{i}.wav' for i in ids]; stems = [s for s in stems if s.exists()]
            if mixf is None or not stems: continue
            mix, fs = sf.read(str(mixf), always_2d=True)
            bass = sum(sf.read(str(s), always_2d=True)[0].mean(axis=1) for s in stems)
            yield d.name, mix, bass, fs


def evaluate(lib, flags, stage, mix48, bz, tt, f0):
    r = P.render(lib, mix48 if mix48.shape[1] == 2 else np.repeat(mix48, 2, axis=1), FS, flags, stage_flags=stage)
    rows = r['rows']; tr = H.tracks(rows); tin = (H.core_indices(rows).astype(float) - 383) / CORE
    lat = r['latency']; lay = resample_poly(r['stem'][lat:, :].astype(float).mean(axis=1), 1, 16)
    t_end = len(bz) / CORE - .2
    tracked = octave = voiced = 0; cents = []
    bands = {b: [0, 0, 0, 0] for b in ('<41', '41-55', '55-82', '>=82')}   # voiced, tracked, octave up, octave down
    for t, f in zip(tt, f0):
        if not (1.0 <= t <= t_end) or not np.isfinite(f): continue
        bk = '<41' if f < 41 else '41-55' if f < 55 else '55-82' if f < 82 else '>=82'; bands[bk][0] += 1
        k = np.searchsorted(tin, t); k = min(max(k, 0), len(tin) - 1)
        fr, a, st = tr[k, :, 2], tr[k, :, 4], tr[k, :, 1]
        live = (st > 0) & (st < 5) & (a > 0)
        if not live.any(): voiced += 1; continue
        live &= a >= .1 * a[live].max(); fl = fr[live]
        c = 1200 * np.abs(np.log2(fl / f)); voiced += 1
        if c.min() <= 50: tracked += 1; cents.append(float(c.min())); bands[bk][1] += 1
        elif (np.abs(1200 * np.log2(fl / (2 * f))) <= 50).any(): octave += 1; bands[bk][2] += 1
        elif (np.abs(1200 * np.log2(fl / (f / 2))) <= 50).any(): octave += 1; bands[bk][3] += 1
    n = 384; hop = 96; win = np.hanning(n); fr = np.fft.rfftfreq(n * 8, 1 / CORE); band = (fr >= 120) & (fr <= 1450)
    share_num = share_den = 0.; e_bass = []; e_idle = []
    for s in range(int(1.0 * CORE), min(len(lay), int(t_end * CORE)) - n, hop):
        sel = (tt >= s / CORE) & (tt <= (s + n) / CORE); fs_ = f0[sel]
        S = np.abs(np.fft.rfft(lay[s:s + n] * win, n * 8)) ** 2; tot = S[band].sum()
        if np.all(~np.isfinite(fs_)) and sel.any(): e_idle.append(tot); continue
        good = fs_[np.isfinite(fs_)]
        if len(good) < max(3, .8 * sel.sum()) or np.ptp(good) > .015 * np.median(good): continue
        fm = float(np.median(good)); e_bass.append(tot)
        near = np.zeros(len(fr), bool)
        for kk in range(2, 9):
            near |= np.abs(fr - kk * fm) <= max(3., .015 * kk * fm)
        share_num += S[band & near].sum(); share_den += tot
    if share_den:   # absolute layer energies in the steady-bass frames (per frame), for model-to-model changes
        bass_e, other_e = share_num / max(len(e_bass), 1), (share_den - share_num) / max(len(e_bass), 1)
    else: bass_e = other_e = None
    return dict(bass_energy=bass_e, other_energy=other_e,voiced_frames=voiced, bands=bands, tracked=tracked / voiced if voiced else None, octave=octave / voiced if voiced else None,
                cents=float(np.median(cents)) if cents else None, bass_share=share_num / share_den if share_den else None,
                idle_layer_db=float(10 * np.log10(np.mean(e_idle) / np.mean(e_bass))) if e_idle and e_bass and np.mean(e_bass) > 0 and np.mean(e_idle) > 0 else None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--models', default='p1,p1_c1,p1_s3,p1plus')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--crop', default='', help='start,seconds: evaluate only this part of each item (long songs)')
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []
    for j, (name, mix, bass, fs) in enumerate(items(a.root)):
        if a.limit and j >= a.limit: break
        if a.crop:
            s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs))
            mix, bass = mix[sl], bass[sl]
            if len(bass) < 5 * fs: continue
        bz = sosfiltfilt(LP, to_rate(bass, fs, CORE)); tt, f0 = yin(bz)
        if np.sum(np.isfinite(f0)) < 20: continue
        mix48 = to_rate(mix, fs, FS).astype(np.float32)
        for m in a.models.split(','):
            fl, st = MODELS[m]; res = evaluate(lib, fl, st, mix48, bz, tt, f0)
            rows.append(dict(item=j, model=m, bass_f0_median=float(np.nanmedian(f0)), **res))
        q = [x for x in rows if x['item'] == j]
        print('ROW', j, f"f0~{np.nanmedian(f0):.0f}Hz", ' '.join(
            f"{x['model']}:{'-' if x['tracked'] is None else round(100 * x['tracked'])}%/{'-' if x['bass_share'] is None else round(100 * x['bass_share'])}%"
            for x in q), flush=True)
    summary = {}
    for m in a.models.split(','):
        sub = [x for x in rows if x['model'] == m]
        agg = lambda k: float(np.median([x[k] for x in sub if x[k] is not None])) if any(x[k] is not None for x in sub) else None
        summary[m] = dict(items=len(sub), tracked=agg('tracked'), octave=agg('octave'), cents=agg('cents'),
                          bass_share=agg('bass_share'), idle_layer_db=agg('idle_layer_db'))
        base = {x['item']: x for x in rows if x['model'] == a.models.split(',')[0]}
        for key in ('bass_energy', 'other_energy'):
            ch = [10 * np.log10(x[key] / base[x['item']][key]) for x in sub
                  if x[key] and base.get(x['item']) and base[x['item']][key]]
            summary[m][key + '_change_db'] = float(np.median(ch)) if ch else None
        pooled = {b: np.sum([x['bands'][b] for x in sub], axis=0).tolist() for b in sub[0]['bands']} if sub else {}
        summary[m]['by_f0_band'] = {b: dict(voiced=v[0], tracked=v[1] / v[0] if v[0] else None, octave_up=v[2] / v[0] if v[0] else None,
                                            octave_down=v[3] / v[0] if v[0] else None) for b, v in pooled.items()}
        print('SUMMARY', m, json.dumps(summary[m]), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.gt_bass.v1', issue=4, root_name=a.root.name, summary=summary,
                                        rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

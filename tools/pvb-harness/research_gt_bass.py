#!/usr/bin/env python3
"""Bass reference benchmark (#4 follow-up): how well does a model's generated layer follow the bass of a full mix,
measured against a reference taken from the bass alone? Local datasets only (MUSDB18 7 s WAV excerpts, BabySlakh);
no audio is committed and nothing here is a listening score.

Reference (--reference):
  yin   the isolated bass stem(s), mono, 3 kHz, low-passed at 400 Hz; YIN f0 (28-300 Hz, 85 ms frames, hop 10 ms,
        CMNDF threshold 0.15) within 35 dB of the stem's loudest frame. An estimate, not an annotation: a fundamental
        or octave error of YIN, and the sum of several bass stems, can still bias it.
  midi  BabySlakh only: the lowest sounding note of the bass stems' MIDI files at each frame time (tempo map applied),
        on the same frame grid, moved by --midi-transpose semitones. BabySlakh renders its bass an octave below the
        written MIDI (stem check without YIN: MIDI / 2 within 20 dB of MIDI in 100 % of note frames, an odd partial at
        1.5 x MIDI in 92 %; with -12 the YIN estimate agrees in 100 % of frames, track median), so -12 is the sounding
        pitch there.
Each mix (48 kHz) is rendered by each model; the first 1 s (warm-up) and the last 0.2 s are left out.
Per model and item:
  tracked       share of reference frames where a live model track (amplitude >= 10 % of the hop's strongest) lies
                within 50 cents of the reference f0 (track time = analysis-window centre, core index - 383)
  octave        share whose nearest strong track is within 50 cents of 2 f0 or f0 / 2 instead
  cents         median |cents| where tracked (each model's own frames; see cents_common for the paired measure)
  bass_share    over 128 ms frames with a steady reference f0 (spread < 1.5 %): share of the layer energy (120-1450 Hz)
                within max(3 Hz, 1.5 %) of k f0, k = 2..8; bass_energy / other_energy: those energies per frame
  idle_layer_db layer energy in frames with no reference f0 relative to frames with one
Paired, each model against the first (same items):
  primary          median over items of (tracked_model - tracked_base)
  octave_change    median over items of (octave_model - octave_base)
  cents_common     median |cents| of each model over the frames both track within 50 cents (pooled over items)
  cents_all        median over all reference frames of min(|cents|, 100) of the nearest strong track (100 without one)
  band_pooled      per f0 band, pooled frames: tracked share of both models and the difference
  low_items        items with at least 50 frames under 55 Hz: their low-band tracked share for both models
Decision (--decide; pre-registration in docs/RESULTANT_R3.md, second model = candidate): adopt when primary >= 0.05,
octave_change < 0, the >= 82 Hz pooled tracked share falls by at most 0.05 and cents_common rises by at most 2 cents;
fail when primary < 0.05; hold otherwise.
"""
import argparse
import hashlib
import json
import re
import struct
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
BANDS = ('<41', '41-55', '55-82', '>=82')
W_YIN, HOP_YIN, FMIN, FMAX = 256, 30, 28, 300


def to_rate(x, fs, target):
    g = np.gcd(int(fs), target); return resample_poly(x, target // g, int(fs) // g, axis=0)


def grid(n):
    """Frame centres (s) of the YIN frame grid for n samples at 3 kHz."""
    tmax = int(CORE / FMIN) + 1
    return (np.arange(0, n - W_YIN - tmax, HOP_YIN) + W_YIN / 2) / CORE


def yin(z, th=.15):
    tmin, tmax = int(CORE / FMAX), int(CORE / FMIN) + 1
    starts = range(0, len(z) - W_YIN - tmax, HOP_YIN); f0 = []; rms = []
    for s in starts:
        x = z[s:s + W_YIN + tmax]; seg = x[:W_YIN]
        d = np.array([np.sum((seg - x[t:t + W_YIN]) ** 2) for t in range(tmax + 1)])
        c = np.cumsum(d[1:]); cm = np.r_[1, d[1:] * np.arange(1, tmax + 1) / np.maximum(c, 1e-20)]
        cand = [t for t in range(tmin, tmax) if cm[t] < th and cm[t] <= cm[t - 1] and cm[t] <= cm[t + 1]]
        if cand:
            t = cand[0]; a, b, c2 = cm[t - 1], cm[t], cm[t + 1]; den = a - 2 * b + c2
            f0.append(CORE / (t + (.5 * (a - c2) / den if abs(den) > 1e-12 else 0)))
        else: f0.append(np.nan)
        rms.append(np.sqrt(np.mean(seg ** 2)))
    f0 = np.array(f0); rms = np.array(rms)
    f0[rms < rms.max() * 10 ** (-35 / 20)] = np.nan
    return grid(len(z)), f0


def midi_notes(path):
    """(start s, end s, pitch) of a Standard MIDI File (format 0/1, PPQ timing, tempo map from any track)."""
    data = Path(path).read_bytes()
    if data[:4] != b'MThd': raise ValueError('not a MIDI file')
    hlen = int.from_bytes(data[4:8], 'big'); fmt, ntrk, div = struct.unpack('>HHH', data[8:14])
    if div & 0x8000: raise ValueError('SMPTE timing is not supported')
    pos = 8 + hlen; tempo = []; ev = []

    def varlen(p):
        v = 0
        while True:
            b = data[p]; p += 1; v = (v << 7) | (b & 0x7F)
            if b < 0x80: return v, p
    for _ in range(ntrk):
        if data[pos:pos + 4] != b'MTrk': raise ValueError('bad track chunk')
        ln = int.from_bytes(data[pos + 4:pos + 8], 'big'); p = pos + 8; end = p + ln; pos = end; tick = 0; status = 0
        while p < end:
            dt, p = varlen(p); tick += dt; b = data[p]
            if b == 0xFF:
                typ = data[p + 1]; n, p = varlen(p + 2)
                if typ == 0x51: tempo.append((tick, int.from_bytes(data[p:p + 3], 'big')))
                p += n
            elif b in (0xF0, 0xF7):
                n, p = varlen(p + 1); p += n
            else:
                if b & 0x80: status = b; p += 1
                hi = status & 0xF0
                if hi in (0xC0, 0xD0): d1 = data[p]; d2 = 0; p += 1
                else: d1, d2 = data[p], data[p + 1]; p += 2
                if hi == 0x90 and d2 > 0: ev.append((tick, 1, d1))
                elif hi == 0x80 or (hi == 0x90 and d2 == 0): ev.append((tick, 0, d1))
    tempo = sorted(tempo) or [(0, 500000)]
    if tempo[0][0] > 0: tempo.insert(0, (0, 500000))
    seg = []; sec = 0.
    for i, (tk, us) in enumerate(tempo):
        if i: sec += (tk - tempo[i - 1][0]) * tempo[i - 1][1] / 1e6 / div
        seg.append((tk, sec, us))

    def seconds(tk):
        j = max(i for i, s in enumerate(seg) if s[0] <= tk); t0, s0, us = seg[j]
        return s0 + (tk - t0) * us / 1e6 / div
    on = {}; notes = []
    for tk, kind, pitch in sorted(ev, key=lambda e: (e[0], e[1])):
        if kind: on.setdefault(pitch, []).append(tk)
        elif on.get(pitch): notes.append((seconds(on[pitch].pop(0)), seconds(tk), pitch))
    return notes


def midi_f0(tt, notes, offset, transpose=0):
    f0 = np.full(len(tt), np.nan)
    for i, t in enumerate(tt):
        act = [pn for s, e, pn in notes if s <= t + offset < e]
        if act: f0[i] = 440 * 2 ** ((min(act) + transpose - 69) / 12)
    return f0


def items(root):
    """(name, mix stereo, bass mono, rate, bass MIDI paths, source files) from MUSDB-style or Slakh-style folders."""
    for d in sorted(p for p in root.rglob('*') if p.is_dir()):
        if (d / 'mixture.wav').exists() and (d / 'bass.wav').exists():
            mix, fs = sf.read(str(d / 'mixture.wav'), always_2d=True); bass, _ = sf.read(str(d / 'bass.wav'), always_2d=True)
            yield d.name, mix, bass.mean(axis=1), fs, [], [d / 'mixture.wav', d / 'bass.wav']
        elif (d / 'metadata.yaml').exists() and (d / 'stems').is_dir():
            meta = (d / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
            parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)   # [head, id, block, id, block, ...]
            ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
            mixf = next((d / n for n in ('mix.wav', 'mix.flac') if (d / n).exists()), None)
            stems = [d / 'stems' / f'{i}.wav' for i in ids]; stems = [s for s in stems if s.exists()]
            if mixf is None or not stems: continue
            midis = [d / 'MIDI' / f'{s.stem}.mid' for s in stems]; midis = [m for m in midis if m.exists()]
            mix, fs = sf.read(str(mixf), always_2d=True)
            bass = sum(sf.read(str(s), always_2d=True)[0].mean(axis=1) for s in stems)
            yield d.name, mix, bass, fs, midis, [mixf] + stems + midis


def evaluate(lib, flags, stage, mix48, bz, tt, f0):
    r = P.render(lib, mix48 if mix48.shape[1] == 2 else np.repeat(mix48, 2, axis=1), FS, flags, stage_flags=stage)
    rows = r['rows']; tr = H.tracks(rows); tin = (H.core_indices(rows).astype(float) - 383) / CORE
    lat = r['latency']; lay = resample_poly(r['stem'][lat:, :].astype(float).mean(axis=1), 1, 16)
    t_end = len(bz) / CORE - .2
    fr_idx, fr_cents, fr_up, fr_down, fr_band = [], [], [], [], []
    for i, (t, f) in enumerate(zip(tt, f0)):
        if not (1.0 <= t <= t_end) or not np.isfinite(f): continue
        bk = 0 if f < 41 else 1 if f < 55 else 2 if f < 82 else 3
        k = min(max(np.searchsorted(tin, t), 0), len(tin) - 1)
        fr, a, st = tr[k, :, 2], tr[k, :, 4], tr[k, :, 1]
        live = (st > 0) & (st < 5) & (a > 0)
        c = np.inf; up = down = False
        if live.any():
            live &= a >= .1 * a[live].max(); fl = fr[live]
            c = float(np.min(1200 * np.abs(np.log2(fl / f))))
            if c > 50:
                up = bool((np.abs(1200 * np.log2(fl / (2 * f))) <= 50).any())
                down = (not up) and bool((np.abs(1200 * np.log2(fl / (f / 2))) <= 50).any())
        fr_idx.append(i); fr_cents.append(c); fr_up.append(up); fr_down.append(down); fr_band.append(bk)
    cents = np.array(fr_cents); ok = cents <= 50; up = np.array(fr_up, bool); down = np.array(fr_down, bool); band = np.array(fr_band, int)
    n = 384; hop = 96; win = np.hanning(n); fr = np.fft.rfftfreq(n * 8, 1 / CORE); bandmask = (fr >= 120) & (fr <= 1450)
    share_num = share_den = 0.; e_bass = []; e_idle = []
    for s in range(int(1.0 * CORE), min(len(lay), int(t_end * CORE)) - n, hop):
        sel = (tt >= s / CORE) & (tt <= (s + n) / CORE); fs_ = f0[sel]
        S = np.abs(np.fft.rfft(lay[s:s + n] * win, n * 8)) ** 2; tot = S[bandmask].sum()
        if np.all(~np.isfinite(fs_)) and sel.any(): e_idle.append(tot); continue
        good = fs_[np.isfinite(fs_)]
        if len(good) < max(3, .8 * sel.sum()) or np.ptp(good) > .015 * np.median(good): continue
        fm = float(np.median(good)); e_bass.append(tot)
        near = np.zeros(len(fr), bool)
        for kk in range(2, 9):
            near |= np.abs(fr - kk * fm) <= max(3., .015 * kk * fm)
        share_num += S[bandmask & near].sum(); share_den += tot
    nv = len(cents)
    res = dict(voiced_frames=nv, tracked=float(ok.mean()) if nv else None, octave=float((up | down).mean()) if nv else None,
               cents=float(np.median(cents[ok])) if ok.any() else None,
               bass_share=share_num / share_den if share_den else None,
               bass_energy=share_num / len(e_bass) if share_den else None,
               other_energy=(share_den - share_num) / len(e_bass) if share_den else None,
               idle_layer_db=float(10 * np.log10(np.mean(e_idle) / np.mean(e_bass))) if e_idle and e_bass and np.mean(e_bass) > 0 and np.mean(e_idle) > 0 else None,
               bands={BANDS[b]: [int((band == b).sum()), int((ok & (band == b)).sum()), int((up & (band == b)).sum()), int((down & (band == b)).sum())] for b in range(4)})
    frames = dict(idx=np.array(fr_idx, int), cents=cents, band=band)
    return res, frames


def paired(rows, frames, base, cand):
    b = {x['item']: x for x in rows if x['model'] == base}; c = {x['item']: x for x in rows if x['model'] == cand}
    common = sorted(set(b) & set(c))
    d_tr = [c[i]['tracked'] - b[i]['tracked'] for i in common if b[i]['tracked'] is not None and c[i]['tracked'] is not None]
    d_oc = [c[i]['octave'] - b[i]['octave'] for i in common if b[i]['octave'] is not None and c[i]['octave'] is not None]
    cb, cc, ab, ac = [], [], [], []
    bp = {k: [0, 0, 0] for k in BANDS}   # frames, tracked base, tracked cand
    low = []
    for i in common:
        fb, fc = frames[(i, base)], frames[(i, cand)]
        assert np.array_equal(fb['idx'], fc['idx'])
        both = (fb['cents'] <= 50) & (fc['cents'] <= 50)
        cb += fb['cents'][both].tolist(); cc += fc['cents'][both].tolist()
        ab += np.minimum(fb['cents'], 100).tolist(); ac += np.minimum(fc['cents'], 100).tolist()
        for k, name in enumerate(BANDS):
            m = fb['band'] == k
            bp[name][0] += int(m.sum()); bp[name][1] += int((fb['cents'][m] <= 50).sum()); bp[name][2] += int((fc['cents'][m] <= 50).sum())
        lm = fb['band'] <= 1
        if lm.sum() >= 50:
            low.append(dict(item=i, frames=int(lm.sum()), base=float((fb['cents'][lm] <= 50).mean()), cand=float((fc['cents'][lm] <= 50).mean())))
    return dict(items=len(common), items_used=len(d_tr), excluded=[i for i in common if b[i]['tracked'] is None or c[i]['tracked'] is None],
                primary=float(np.median(d_tr)) if d_tr else None, primary_per_item=d_tr,
                octave_change=float(np.median(d_oc)) if d_oc else None,
                cents_common=[float(np.median(cb)) if cb else None, float(np.median(cc)) if cc else None, len(cb)],
                cents_all=[float(np.median(ab)) if ab else None, float(np.median(ac)) if ac else None],
                band_pooled={k: dict(frames=v[0], base=v[1] / v[0] if v[0] else None, cand=v[2] / v[0] if v[0] else None,
                                     change=(v[2] - v[1]) / v[0] if v[0] else None) for k, v in bp.items()},
                low_items=low)


def decide(pr):
    hi = pr['band_pooled']['>=82']['change']; cc = pr['cents_common']
    checks = dict(primary=pr['primary'] is not None and pr['primary'] >= .05,
                  octave=pr['octave_change'] is not None and pr['octave_change'] < 0,
                  high_band=hi is not None and hi >= -.05,
                  cents=None not in cc[:2] and cc[1] - cc[0] <= 2)
    # A missing measurement is neither adoption nor rejection evidence: it holds, and the report names it.
    unmeasured = [k for k, v in dict(primary=pr['primary'], octave=pr['octave_change'], high_band=hi,
                                     cents=None if None in cc[:2] else 0).items() if v is None]
    verdict = 'adopt' if all(checks.values()) else 'fail' if pr['primary'] is not None and not checks['primary'] else 'hold'
    reason = 'unmeasured: ' + ', '.join(unmeasured) if verdict == 'hold' and unmeasured else None
    return dict(verdict=verdict, checks=checks, unmeasured=unmeasured, reason=reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--models', default='p1,p1_c1,p1_s3,p1plus')
    p.add_argument('--reference', choices=('yin', 'midi'), default='yin')
    p.add_argument('--midi-transpose', type=int, default=0)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--crop', default='', help='start,seconds: evaluate only this part of each item (long songs)')
    p.add_argument('--decide', action='store_true')
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []; frames = {}; inventory = []
    models = a.models.split(',')
    for j, (name, mix, bass, fs, midis, sources) in enumerate(items(a.root)):
        if a.limit and j >= a.limit: break
        s0 = 0.
        if a.crop:
            s0, du = (float(v) for v in a.crop.split(',')); sl = slice(int(s0 * fs), int((s0 + du) * fs))
            mix, bass = mix[sl], bass[sl]
            if len(bass) < 5 * fs: inventory.append(dict(item=j, excluded='shorter than the crop')); continue
        bz = sosfiltfilt(LP, to_rate(bass, fs, CORE))
        if a.reference == 'midi':
            if not midis: inventory.append(dict(item=j, excluded='no bass MIDI')); continue
            notes = [n for m in midis for n in midi_notes(m)]; tt = grid(len(bz)); f0 = midi_f0(tt, notes, s0, a.midi_transpose)
        else: tt, f0 = yin(bz)
        inventory.append(dict(item=j, sha256={f.name if f.parent.name != 'stems' and f.parent.name != 'MIDI' else f'{f.parent.name}/{f.name}':
                                                hashlib.sha256(f.read_bytes()).hexdigest()[:16] for f in sources}))
        if np.sum(np.isfinite(f0)) < 20: inventory[-1]['excluded'] = 'under 20 reference frames'; continue
        mix48 = to_rate(mix, fs, FS).astype(np.float32)
        for m in models:
            fl, st = MODELS[m]; res, fr = evaluate(lib, fl, st, mix48, bz, tt, f0)
            rows.append(dict(item=j, model=m, bass_f0_median=float(np.nanmedian(f0)), **res)); frames[(j, m)] = fr
        q = [x for x in rows if x['item'] == j]
        print('ROW', j, f"f0~{np.nanmedian(f0):.0f}Hz", ' '.join(
            f"{x['model']}:{'-' if x['tracked'] is None else round(100 * x['tracked'])}%" for x in q), flush=True)
    summary = {}
    for m in models:
        sub = [x for x in rows if x['model'] == m]
        agg = lambda k: float(np.median([x[k] for x in sub if x[k] is not None])) if any(x[k] is not None for x in sub) else None
        summary[m] = dict(items=len(sub), tracked=agg('tracked'), octave=agg('octave'), cents=agg('cents'),
                          bass_share=agg('bass_share'), idle_layer_db=agg('idle_layer_db'))
        base = {x['item']: x for x in rows if x['model'] == models[0]}
        for key in ('bass_energy', 'other_energy'):
            ch = [10 * np.log10(x[key] / base[x['item']][key]) for x in sub
                  if x[key] and base.get(x['item']) and base[x['item']][key]]
            summary[m][key + '_change_db'] = float(np.median(ch)) if ch else None
        pooled = {b: np.sum([x['bands'][b] for x in sub], axis=0).tolist() for b in BANDS} if sub else {}
        summary[m]['by_f0_band'] = {b: dict(voiced=v[0], tracked=v[1] / v[0] if v[0] else None, octave_up=v[2] / v[0] if v[0] else None,
                                            octave_down=v[3] / v[0] if v[0] else None) for b, v in pooled.items()}
        print('SUMMARY', m, json.dumps({k: v for k, v in summary[m].items() if k != 'by_f0_band'}), flush=True)
    pairs = {m: paired(rows, frames, models[0], m) for m in models[1:]}
    for m, pr in pairs.items():
        print('PAIRED', m, json.dumps({k: v for k, v in pr.items() if k not in ('primary_per_item', 'low_items')}), flush=True)
    decision = decide(pairs[models[1]]) if a.decide and len(models) > 1 else None
    if decision: print('DECISION', models[1], json.dumps(decision), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.gt_bass.v2', issue=4, root_name=a.root.name, reference=a.reference,
                                        midi_transpose=a.midi_transpose, crop=a.crop, models=models,
                                        library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                                        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), inventory=inventory, summary=summary, paired=pairs,
                                        decision=decision, rows=rows), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

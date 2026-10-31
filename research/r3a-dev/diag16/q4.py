"""Q4: V3g - why do the 35 Hz and 45 Hz notes need ~10 hops to ON? Per hop: voice state/SNR/prom, and the peaks of src[0] U src[1] (the engine's full-band
spectrum peak lists, re-computed offline from the captured 'decimated' stream with the engine's own recipe: md2(j) = d(j-191), periodic Hann 384, FFT 2048,
band 0 20-200 Hz / -50 dB, band 1 140-620 Hz / -60 dB, local maximum, >= sqrt(10) over the median of +-27 bins, parabolic offset) near k*f, k=1..4,
tolerance max(4 Hz, 3 % k f).  The emulation is validated against the engine's own 'prominent' flag at every hop."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X
import research_core_metrics as M
import test_harmonic_continuity as H
from vb_quality.stage_capture import INDEX as SI

FS = X.FS
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


NFFT, N = 2048, 384
BIN = 3000.0 / NFFT
win = np.hanning(N + 1)[:-1]


def sm_at(dstream, ih):
    s0 = ih - (N - 1)
    idx = s0 + np.arange(N) - 191
    fr = np.where(idx >= 0, dstream[np.maximum(idx, 0)], 0.0) * win
    return np.abs(np.fft.rfft(fr, NFFT))


def offset(a, b, c):
    den = a - 2 * b + c
    return float(np.clip(0.5 * (a - c) / den, -1, 1)) if abs(den) > 1e-12 else 0.0


def src_peaks(sm, detail=False):
    res = [[], []]; rej = [[], []]
    for band in range(2):
        lb = int(np.ceil((140 if band else 20) / BIN)); hb = int(np.floor((620 if band else 200) / BIN))
        maxmag = sm[lb:hb + 1].max()
        for b in range(lb + 1, hb):
            v = sm[b]
            if not (v >= sm[b - 1] and v > sm[b + 1]):
                continue
            med = np.median(sm[np.clip(np.arange(b - 27, b + 28), lb, hb)])
            rel = 20 * np.log10(v / maxmag + 1e-30); over = 20 * np.log10(v / (med + 1e-20))
            f = (b + offset(np.log(sm[b - 1] + 1e-30), np.log(v + 1e-30), np.log(sm[b + 1] + 1e-30))) * BIN
            floor_db = -60. if band else -50.
            ok = rel >= floor_db and v >= (med + 1e-20) * np.sqrt(10.)
            (res if ok else rej)[band].append((f, rel, over))
    return res, rej


def evid(res, f):
    for k in range(1, 5):
        fk = k * f; tol = max(4.0, .03 * fk)
        for band in range(2):
            for (pf, _, _) in res[band]:
                if abs(pf - fk) <= tol:
                    return True
    return False


x = X.low_notes_sig()
ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
x2 = np.stack([x, x], 1).astype(np.float32)
r0 = ctx.render('low', x2, 0.0, harmonic=True, voice=True, stage=True)
st = r0['stage']; rows = r0['harm']
core_st = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
dstream = np.zeros(core_st.max() + 1); dstream[core_st] = st[:, SI['decimated']]
d, hop, tc = X.hops_of(r0['voice'])
raw = np.asarray(r0['voice']).reshape(-1, 8, 22)
hop_i = hop.astype(np.int64)
hcore = M.hop_table(rows)[0]; ts = H.tracks(rows)
hh_ = np.searchsorted(hcore, hop_i)
STATE = {0: '-', 1: 'CAND', 2: 'ON', 3: 'REL'}
summary = {}
nmatch = nall = 0
for f0, a in ((35.0, 0.3), (45.0, 2.8)):
    P(f'\n================ note {f0:.0f} Hz starting {a} s (fundamental and 2nd harmonic at equal level 0.1, 8 ms ramps)')
    first_voice = None; first_track = None; on_hop = None
    for h in range(len(tc)):
        if tc[h] < a - 0.05 or tc[h] > a + 0.40:
            continue
        # tracker tracks near f0 at this hop
        k = hh_[h] if hh_[h] < len(hcore) and hcore[hh_[h]] == hop_i[h] else None
        trk = [] if k is None else [(ts[k][j][0] + 65536 * ts[k][j][13], ts[k][j][2], ts[k][j][8], ts[k][j][6]) for j in range(ts.shape[1]) if ts[k][j][1] > 0 and abs(ts[k][j][2] - f0) <= .12 * f0 or (ts[k][j][1] > 0 and abs(ts[k][j][2] - 2 * f0) <= .06 * 2 * f0)]
        vo = [j for j in range(8) if d['state'][h][j] > 0 and (abs(raw[h, j, X.F_FTR] - f0) <= .12 * f0 or abs(raw[h, j, X.F_FOSC] - f0) <= .12 * f0)]
        if trk and first_track is None:
            first_track = h
        if vo and first_voice is None:
            first_voice = h
        if first_track is None and first_voice is None:
            continue
        h_ref = first_track if first_track is not None else first_voice
        if on_hop is not None and h > on_hop + 3:
            break
        sm = sm_at(dstream, int(hop_i[h]))
        res, rej = src_peaks(sm)
        line_head = f'hop {h - h_ref:+3d} (tc {1000*(tc[h]-a):+6.1f} ms rel. note start)'
        tr_txt = ' '.join(f'[trk {int(t[0])} f{t[1]:.1f} age{t[2]:.0f} res{t[3]:.0f}]' for t in trk) or '[no tracker track near f0 or 2f0]'
        P(line_head + ' ' + tr_txt)
        if not vo:
            P('      no voice yet')
        for j in vo:
            u = dict(st=STATE[int(d['state'][h][j])], f=raw[h, j, X.F_FTR], fosc=raw[h, j, X.F_FOSC], snr=d['snr'][h][j], prom=int(raw[h, j, X.F_PROM]), A=d['A'][h][j], c=d['c'][h][j],
                     trk=int(raw[h, j, X.F_TRACK]), np_=int(raw[h, j, X.F_NP]))
            ev = evid(res, u['f']); nall += 1; nmatch += int(ev == bool(u['prom']))
            P(f'      voice {int(d["voice"][h][j])} {u["st"]} f_track {u["f"]:.2f} snr {u["snr"]:.1f} dB prom(engine) {u["prom"]} prom(emulated) {int(ev)} A {u["A"]:.4f} c {u["c"]:.2f} N {u["np_"]}')
            if u['st'] == 'ON' and on_hop is None:
                on_hop = h
            for kk in range(1, 5):
                fk = kk * u['f']; tol = max(4.0, .03 * fk)
                found = [(pf, rel, ov) for b in range(2) for (pf, rel, ov) in res[b] if abs(pf - fk) <= tol]
                rejd = [(pf, rel, ov) for b in range(2) for (pf, rel, ov) in rej[b] if abs(pf - fk) <= tol]
                ft = ', '.join(f'{pf:.1f} Hz ({rel:+.0f} dB re band max, {ov:+.0f} dB over local median)' for pf, rel, ov in found) or 'none'
                rt = ('; local maxima rejected: ' + ', '.join(f'{pf:.1f} Hz ({rel:+.0f} re max, {ov:+.0f} over median; needs >= {10:.0f})' for pf, rel, ov in rejd)) if rejd else ''
                P(f'         k={kk} target {fk:6.1f} Hz tol +-{tol:.1f}: peaks in src: {ft}{rt}')
    # resolution check: spectrum around f0 and 2f0 at the hop where the voice first appears (magnitudes in sine units)
    if first_voice is not None:
        for hh in (first_voice, first_voice + 4, first_voice + 8):
            sm = sm_at(dstream, int(hop_i[hh]))
            Wsum = win.sum()
            def pk(f, w=6):
                lo = int((f - w) / BIN); hi = int((f + w) / BIN) + 1
                b = lo + int(np.argmax(sm[lo:hi])); return b * BIN, sm[b] * 2 / Wsum
            f1, m1 = pk(f0); f2, m2 = pk(2 * f0); f3, m3 = pk(3 * f0)
            lowflo = np.median(sm[int(20 / BIN):int(200 / BIN)]) * 2 / Wsum
            P(f'   spectrum at hop first_voice+{hh - first_voice}: peak near f0 {f1:.1f} Hz amp {m1:.4f}; near 2f0 {f2:.1f} Hz amp {m2:.4f}; near 3f0 {f3:.1f} Hz {m3:.4f}; median 20-200 Hz {lowflo:.4f}; (true: 0.1 at f0 and 2f0 after ramp)')
    summary[f0] = dict(first_track=first_track, first_voice=first_voice, on_hop=on_hop)
    if on_hop is not None and first_track is not None:
        P(f'   => tracker track first seen at hop {first_track}, first voice at hop {first_voice}, ON at hop {on_hop} (= +{on_hop - first_track} hops after the first track = {(on_hop - first_track) * 16 / 3:.1f} ms)')
P(f'\nemulation check: prom(emulated) == prom(engine) at {nmatch}/{nall} voice-hops printed')
open(C.D16 / 'q4_report.txt', 'w').write('\n'.join(out))

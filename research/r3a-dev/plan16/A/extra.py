"""Post-run information (CHOICES.md "post-run additions"):
 X1 R3 without the engine front end: the stem sum band-limited and decimated to 3 kHz (no HPSS / band selection), placed on the bh index axis; same LS, same synthesis; V5a + right energy.
 X2 core v1.5 voice list through the same k = 2..8 synthesis: V5a (calibration of the V5a failure of R3).
 X3 V5a drops of R2 / R3 / core / P1 vs polyphony (second bass note sounding) and V5a restricted to single-note bins.
 X4 leak test T40: was a layer active in [T-L-64 ms, T-L]?
usage (from diag16): ./run.sh ../plan16/A/extra.py"""
import sys, json, pickle
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A'); sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from scipy.signal import butter, sosfiltfilt, resample_poly
from data import *
import metrics as MT, rows as R, evaluate as E
import ladder as Ld
import stems as St
import synth16 as S

OUT = {}
y3s = pickle.load(open(Ld.OUTD / 'cache' / 'ladder_y3.pkl', 'rb'))
raw = json.load(open(Ld.OUTD / 'ladder_raw.json'))


def raw_stem_stream(key, nlen):
    x = St.stem_audio(key)[:, 0].astype(float)
    y3 = resample_poly(x, 1, 16)                                    # 3 kHz, anti-aliased (default Kaiser FIR, zero phase)
    sos = butter(2, [32, 190], btype='band', fs=3000.0, output='sos')
    y3 = sosfiltfilt(sos, y3)
    tn = np.arange(len(y3)) / 3000.0
    tj = stream_time(np.arange(nlen))
    return np.interp(tj, tn, y3, left=0.0, right=0.0)


# ---------------------------------------------------------------- X1
Er3 = Ld_E = 0.0
raw_r3 = {}
E_right_raw = 0.0; E_right_r3 = 0.0
for key in Ld.KEYS:
    sig = Sig(key); segs, rf = Ld.segments(key); dur = Ld.dur_of(key)
    xr = raw_stem_stream(key, len(sig.bh))
    v = Ld.oracle_voices(sig, xr, segs)
    y3 = S.render_layer16(v, dur + 0.3)
    raw_r3[key] = y3
    if key == 't60_36_48':
        OUT['X1_R3raw_v5a'] = Ld.v5a_of(y3, dur)
        OUT['X1_R3engine_v5a'] = raw['res'][key]['R3']['v5a']
    else:
        E_right_raw += float(np.sum(y3[Ld.I_MIN:] ** 2)); E_right_r3 += raw['res'][key]['R3']['v6b']['E_right']
OUT['X1_R3raw_right_dB_vs_R3engine'] = 10 * np.log10(E_right_raw / E_right_r3)
# amplitude scale of bh vs raw (information)
sig = Sig('Track00001'); xr = raw_stem_stream('Track00001', len(sig.bh)); xs = St.stem_streams('Track00001')[0]
seg_mask = slice(int(stream_index(8.0)), int(stream_index(12.0)))
OUT['X1_rms_ratio_raw_over_enginestem_T1_8_12s'] = float(np.sqrt(np.mean(xr[seg_mask] ** 2) / np.mean(xs[seg_mask] ** 2)))

# ---------------------------------------------------------------- X2 core v1.5 reference with the k = 2..8 synthesis
key = 't60_36_48'; sig = Sig(key); dur = 12.0
vc = E.shift(R.voices_core(sig), E.load_lags()['core'])
y3c = S.render_layer16(vc, dur + 0.3)
OUT['X2_core_k2to8_v5a'] = Ld.v5a_of(y3c, dur)
y3c23 = R.render_layer(vc, dur + 0.3)
OUT['X2_core_k2k3_v5a_(14.1_synthesis)'] = Ld.v5a_of(y3c23, dur)
y3s[(key, 'core')] = y3c

# ---------------------------------------------------------------- X3 drops vs polyphony
segs, rf = Ld.segments(key)
ss, es = rf['ss'] - 36.0, rf['es'] - 36.0
S_ = MT.v5_setup(); B, K, i0 = S_['B'], S_['K'], S_['i0']
idx, tcen = S_['idx'], S_['tcen']
t_ex = 3.0 + tcen
poly = np.array([int(((ss <= t) & (t < es)).sum()) for t in t_ex])
OUT['X3_present_bins'] = int(len(idx)); OUT['X3_present_bins_with_2plus_bass_notes'] = int((poly[idx] >= 2).sum())
bounds = np.array(sorted({s['s'] for s in segs} | {s['e'] for s in segs}))
X3 = {}
for rn in ('P1', 'R0', 'R1', 'R2', 'R3', 'core'):
    y = R.up48(y3s[(key, rn)]); n = int(12.3 * FS); y = np.pad(y, (0, max(0, n - len(y))))[:n]
    lay = MT.X.band_fft(y[:min(len(y), 12 * FS + 1000)], 150, 600)
    lay = np.pad(lay, (0, max(0, i0 + K * B - len(lay))))
    el = np.array([np.sum(lay[i0 + k * B:i0 + (k + 1) * B] ** 2) for k in range(K)])
    ratio = 10 * np.log10(el + 1e-20) - S_['es_db']
    drops = []
    for i in idx:
        m = idx[np.abs(tcen[idx] - tcen[i]) <= .25]
        if ratio[i] < np.median(ratio[m]) - 6:
            drops.append(i)
    drops = np.array(drops, int)
    near = np.array([np.min(np.abs(bounds - t_ex[i])) < 0.05 for i in drops]) if len(drops) else np.zeros(0, bool)
    single = idx[poly[idx] <= 1]
    X3[rn] = dict(drops=int(len(drops)), n=int(len(idx)), drops_with_2plus_bass_notes=int((poly[drops] >= 2).sum()), drops_near_boundary_50ms=int(near.sum()),
                  drops_neither=int(((poly[drops] < 2) & ~near).sum()),
                  n_single_note_bins=int(len(single)), drops_in_single_note_bins=int((poly[drops] <= 1).sum()),
                  v5a_single_note_bins=float((poly[drops] <= 1).sum() / max(len(single), 1)))
OUT['X3'] = X3
json.dump(OUT, open(Ld.OUTD / 'extra.json', 'w'), indent=1, default=float)
print(json.dumps(OUT, indent=1, default=float))

# ---------------------------------------------------------------- X4 leak T40 window activity
for tag, Tsec in (('Track00040_10_7', 7.0), ('Track00060_20_7', 7.0)):
    z = np.load(Ld.OUTD / 'cache_leak' / f'res_{tag}_orig.npz', allow_pickle=True)['d'].item()
    for k in ('bh-64-clf', 'bh-217-clf', 'det-217-clf'):
        L = int(k.split('-')[1]) / 1000.0
        y = z['layers'][k]
        win = lambda a, b: float(np.max(np.abs(y[int(a * 3000):int(b * 3000)])))
        print(tag, k, 'max|layer| in [T-L-64ms, T-L]: %.3e   in [T-L-300ms, T-L-64ms]: %.3e   (layer peak %.3e)' % (win(Tsec - L - .064, Tsec - L), win(Tsec - L - .3, Tsec - L - .064), np.max(np.abs(y))))

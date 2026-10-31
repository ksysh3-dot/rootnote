"""Q5: V3h tail on the gated step line (band SNR 25 dB, config A). Per note end: per hop dominant voice A, c, N_v, state, SNR from the note end to +80 ms; what sets the tail."""
import json
import numpy as np
import common16 as C
import research_core_xcheck as X

FS = X.FS
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


STEP_NOTES, STEP_DUR = X.STEP_NOTES, X.STEP_DUR
ph = np.linspace(0, 2 * np.pi, 400001); tpk = float(np.abs(np.sin(ph) + .5 * np.sin(2 * ph) + .18 * np.sin(3 * ph)).max()); scale = .25 / tpk
m = int(round(STEP_DUR * FS)); per = 2 * STEP_DUR; nn = len(STEP_NOTES)
clean = np.zeros(int(round(nn * per * FS))); on = np.zeros(len(clean), bool)
for i, f in enumerate(STEP_NOTES):
    n0 = int(round(i * per * FS)); clean[n0:n0 + m] = X._note(f, m, scale); on[n0:n0 + m] = True
n = max(10 * FS, len(clean)); n += n % 2
rng = np.random.default_rng(1); fr = np.fft.rfftfreq(n, 1 / FS)
w = np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) / np.sqrt(np.maximum(fr, 20)), n); w = (w / np.sqrt(np.mean(w ** 2)))[:len(clean)]
bp = lambda s, mask=None: float(np.mean((X.band_fft(s, 80, 200) ** 2)[mask] if mask is not None else X.band_fft(s, 80, 200) ** 2))
snr = 25.0
g = np.sqrt(bp(clean, on) / (bp(w) * 10 ** (snr / 10.0))); sig = clean + g * w
cand = X.open_lib(X.CAND)
r0 = X.render(cand, sig, 15, 0.0, out_db=-5.0, cfg=X.CFG['A'], trace=True); rd = X.render(cand, sig, 15, -120.0, out_db=-5.0, cfg=X.CFG['A'])
lay = X.layer(r0, rd)
env = X._box_rms(lay, 5.0)
d, hop, tc = X.hops_of(r0['trace'])
raw = r0['trace'].reshape(-1, 8, 22)
notes = list(range(2, 40))

# ---- reproduce the suite tail (rms5): -20 dB of the 60-110 ms mean
tails = []; refs = []
for i in notes:
    t0 = i * per; refv = float(np.mean(env[int((t0 + .06) * FS):int((t0 + .11) * FS)]))
    sg = env[int((t0 + .125) * FS):int((t0 + .125) * FS) + int(.12 * FS)]
    ok = sg <= .1 * refv
    tails.append(float(np.argmax(ok) / FS * 1000) if ok.any() else np.inf); refs.append(refv)
tails = np.array(tails)
P(f'suite tail (rms5, -20 dB re mean 60-110 ms, from note end), median over notes {np.median(tails):.1f} ms (reference 44.2), p10/p90 {np.percentile(tails,10):.1f}/{np.percentile(tails,90):.1f}, min/max {tails.min():.1f}/{tails.max():.1f}')

# ---- time alignment of the trace to the layer on this signal: correlate layer energy (1 ms) with the trace-predicted sum a2^2 + a3^2 (hop values)
pred = np.nansum(np.where(d['state'] > 0, d['a2'] ** 2 + d['a3'] ** 2, 0.0), axis=1)
tt = np.arange(0, 9.8, 0.001)
pred_i = np.interp(tt, tc, pred)
Lb = X.band_fft(lay, 150, 600)
Eb = np.array([np.sum(Lb[int(t * FS):int(t * FS) + 48] ** 2) for t in tt])
best = None
for lag in range(-30, 31):
    a_ = 10 * np.log10(pred_i[100:9000] + 1e-12); b_ = 10 * np.log10(np.roll(Eb, -lag)[100:9000] + 1e-12)
    c_ = np.corrcoef(a_, b_)[0, 1]
    if best is None or c_ > best[1]:
        best = (lag, c_)
LAGMS = best[0]
P(f'alignment on this signal: layer energy follows the trace-predicted harmonic energy best with layer(t + {LAGMS} ms) <-> trace(t), corr {best[1]:.3f}  (so a trace event at hop-centre time t appears in the layer at t {LAGMS:+d} ms)')

# ---- per note end, per hop table (dominant voice = largest A*c*sigma among voices with state>0)
STATE = {0: '-', 1: 'CAND', 2: 'ON', 3: 'REL'}
per_note = {}
for i in notes:
    t_e = i * per + STEP_DUR
    f0 = STEP_NOTES[i]
    rows = []
    for h in np.flatnonzero((tc >= t_e - 0.03) & (tc <= t_e + 0.10)):
        wv = np.where(d['state'][h] > 0, d['A'][h] * d['c'][h] * d['sig'][h], 0.0)
        # dominant: the voice nearest to the note frequency (+-12 %) with the largest weight; else largest weight
        near = [j for j in range(8) if d['state'][h][j] > 0 and abs(d['fosc'][h][j] - f0) <= .12 * f0]
        j = max(near, key=lambda q: wv[q]) if near else (int(np.argmax(wv)) if wv.max() > 0 else None)
        if j is None:
            rows.append(dict(dt=1000 * (tc[h] - t_e), none=True)); continue
        rows.append(dict(dt=1000 * (tc[h] - t_e), vid=int(d['voice'][h][j]), st=int(d['state'][h][j]), f=float(d['fosc'][h][j]), A=float(d['A'][h][j]), c=float(d['c'][h][j]), sig=float(d['sig'][h][j]),
                         np=int(raw[h, j, X.F_NP]), snr=float(d['snr'][h][j]), near=bool(near)))
    per_note[i] = rows

# three example notes printed in full
for i in (6, 13, 30):
    P(f'\n== note {i}: f0 {STEP_NOTES[i]} Hz, ends at t = {i*per+STEP_DUR:.3f} s (input time); suite tail {tails[notes.index(i)]:.1f} ms. rows: hop-centre time rel. to note end (ms) | dominant voice (id) state | f_osc | A | c | A*c | N_v | SNR dB | A/A_ref dB')
    refA = np.median([r['A'] for r in per_note[i] if not r.get('none') and -45 <= r['dt'] <= -8] or [np.nan])
    for r in per_note[i]:
        if r.get('none'):
            P(f'  {r["dt"]:+7.1f} | no voice'); continue
        P(f'  {r["dt"]:+7.1f} | v{r["vid"]} {STATE[r["st"]]:3s} | f{r["f"]:6.1f} | A {r["A"]:.4f} | c {r["c"]:.3f} | Ac {r["A"]*r["c"]*r["sig"]:.4f} | N {r["np"]:3d} | snr {r["snr"]:5.1f} | {20*np.log10(max(r["A"],1e-9)/refA):+6.1f}')

# ---- median across the 38 note ends, by hop offset (bins of one hop = 5.333 ms)
P('\n== median over the 38 note ends, by hop offset from the note end (dB re the mean of the last 8 hops before the note end; fraction of notes in each state):')
P('| offset ms | A dB | c | A*c*sigma dB | N_v median (p10-p90) | SNR dB | frac ON | frac REL | frac no voice | layer env dB re ref |')
P('|---|---|---|---|---|---|---|---|---|---|')
HM = 16 / 3000 * 1000
offs = np.arange(-6, 20)
ref_ac = {}; ref_A = {}
for i in notes:
    rr = [r for r in per_note[i] if not r.get('none') and -45 <= r['dt'] <= -8]
    ref_ac[i] = np.mean([r['A'] * r['c'] * r['sig'] for r in rr]) if rr else np.nan
    ref_A[i] = np.mean([r['A'] for r in rr]) if rr else np.nan
res_tab = []
for k in offs:
    A_, c_, ac_, np_, snr_, st_, none_, ev_ = [], [], [], [], [], [], 0, []
    for i in notes:
        t_e = i * per + STEP_DUR
        sel = [r for r in per_note[i] if abs(r['dt'] - k * HM) <= HM / 2]
        if not sel:
            continue
        r = sel[0]
        if r.get('none'):
            none_ += 1; st_.append(0); continue
        A_.append(20 * np.log10(max(r['A'], 1e-9) / ref_A[i])); c_.append(r['c']); ac_.append(20 * np.log10(max(r['A'] * r['c'] * r['sig'], 1e-9) / ref_ac[i])); np_.append(r['np']); snr_.append(r['snr']); st_.append(r['st'])
    # layer envelope at the corresponding time (trace time -> layer time via LAGMS)
    for i in notes:
        t_e = i * per + STEP_DUR
        ev_.append(20 * np.log10(env[int((t_e + k * HM / 1000 + LAGMS / 1000) * FS)] / refs[notes.index(i)] + 1e-12))
    st_ = np.array(st_)
    row = dict(k=int(k), off=float(k * HM), A=float(np.median(A_)) if A_ else np.nan, c=float(np.median(c_)) if c_ else np.nan, ac=float(np.median(ac_)) if ac_ else np.nan,
               np_med=float(np.median(np_)) if np_ else np.nan, np_p10=float(np.percentile(np_, 10)) if np_ else np.nan, np_p90=float(np.percentile(np_, 90)) if np_ else np.nan,
               snr=float(np.median(snr_)) if snr_ else np.nan, fON=float(np.mean(st_ == 2)), fREL=float(np.mean(st_ == 3)), fnone=float(np.mean(st_ == 0)), env=float(np.median(ev_)))
    res_tab.append(row)
    P(f'| {row["off"]:+6.1f} | {row["A"]:+6.1f} | {row["c"]:.2f} | {row["ac"]:+6.1f} | {row["np_med"]:.0f} ({row["np_p10"]:.0f}-{row["np_p90"]:.0f}) | {row["snr"]:.1f} | {row["fON"]:.2f} | {row["fREL"]:.2f} | {row["fnone"]:.2f} | {row["env"]:+.1f} |')

# ---- first crossings per note: A below -20 dB, A*c*sigma below -20 dB, REL start, and the same on the layer
def first_cross(rows, key, thr_db, ref):
    for r in rows:
        if r.get('none') or r['dt'] < 0:
            continue
        v = 20 * np.log10(max(key(r), 1e-9) / ref)
        if v <= thr_db:
            return r['dt']
    return np.inf


cr = dict(A=[], Ac=[], rel=[], none=[], layer=[])
for i in notes:
    rows = per_note[i]
    cr['A'].append(first_cross(rows, lambda r: r['A'], -20, ref_A[i]))
    cr['Ac'].append(first_cross(rows, lambda r: r['A'] * r['c'] * r['sig'], -20, ref_ac[i]))
    rel = [r['dt'] for r in rows if not r.get('none') and r['dt'] >= 0 and r['st'] == 3]
    cr['rel'].append(rel[0] if rel else np.inf)
    nn_ = [r['dt'] for r in rows if r.get('none') and r['dt'] >= 0]
    cr['none'].append(nn_[0] if nn_ else np.inf)
    cr['layer'].append(tails[notes.index(i)])
P('\nfirst crossing times after the note end (ms, trace hop-centre time; the layer tail is in layer time = trace time ' + f'{LAGMS:+d} ms), median [p10, p90] over 38 notes:')
for k_, lab in (('A', 'A (LS amplitude of the dominant voice) <= -20 dB re pre-end level'), ('Ac', 'A*c*sigma <= -20 dB'), ('rel', 'dominant voice enters REL (any voice of the note)'), ('none', 'no voice left near the note'), ('layer', 'LAYER envelope -20 dB (suite tail)')):
    v = np.array(cr[k_]); vv = v[np.isfinite(v)]
    if not len(vv):
        P(f'  {lab}: never within 100 ms'); continue
    P(f'  {lab}: median {np.median(vv):.1f} [{np.percentile(vv,10):.1f}, {np.percentile(vv,90):.1f}]  (finite for {len(vv)}/{len(v)} notes)')
# predicted c-only: if A dropped instantly at REL start, c(t) = exp(-t/tau_off) reaches -20 dB after
P(f'  reference: c = exp(-t/30 ms) alone reaches -20 dB after {30*np.log(10):.1f} ms; the LS past window of N samples (Hann, 3 kHz) has its centre of mass ~0.3 N before the hop centre ({0.3*30/3:.1f} ms for N=30, {0.3*100/3:.1f} ms for N=100)')

# ---- isolate the window-length effect: offline single-voice LS on the engine's own bh stream with a FIXED past window N (the note's own f_osc from the trace)
import research_core_metrics as M
from vb_quality.stage_capture import INDEX as SI
ctx = M.Ctx(X.CAND, 15, dict(voicing=0, ampSource=0))
rs = ctx.render('line25', np.stack([sig, sig], 1).astype(np.float32), 0.0, stage=True)
st = rs['stage']
core_st = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
bh = np.zeros(core_st.max() + 1); bh[core_st] = st[:, SI['selected_h']]
hop_i = hop.astype(np.int64)


def ls_fixed(h, f, Np, Nf=24):
    ms = np.arange(-Np, min(Np, Nf) + 1)
    wv = np.where(ms <= 0, 0.5 * (1 + np.cos(np.pi * ms / (Np + 1))), 0.5 * (1 + np.cos(np.pi * ms / (min(Np, Nf) + 1))))
    t = ms / 3000.0; ph_ = 2 * np.pi * f * t
    Bc, Bs = np.cos(ph_), np.sin(ph_)
    xs = bh[hop_i[h] - 191 + ms]
    G = np.array([[np.sum(wv * Bc * Bc), np.sum(wv * Bc * Bs)], [np.sum(wv * Bc * Bs), np.sum(wv * Bs * Bs)]]); G += 1e-4 * np.trace(G) / 2 * np.eye(2)
    a_, b_ = np.linalg.solve(G, np.array([np.sum(wv * Bc * xs), np.sum(wv * Bs * xs)]))
    return float(np.hypot(a_, b_))


P('\n== offline single-voice LS on the captured bh stream with a FIXED past window (note frequency = the trace f_osc of the note voice); crossing times of -20 dB after the note end (median [p10,p90] over notes), and dB re pre-end level at selected offsets')
fixed = {}
for Np in (31, 60, 100, 200, 320):
    cross = []; at = {k: [] for k in (10.7, 21.3, 32.0, 42.7, 64.0)}
    for i in notes:
        t_e = i * per + STEP_DUR; f0 = STEP_NOTES[i]
        hs = np.flatnonzero((tc >= t_e - 0.05) & (tc <= t_e + 0.12))
        ser = []
        for h in hs:
            near = [j for j in range(8) if d['state'][h][j] > 0 and abs(d['fosc'][h][j] - f0) <= .12 * f0]
            if not near:
                ser.append((1000 * (tc[h] - t_e), np.nan)); continue
            j = max(near, key=lambda q: d['A'][h][q]); ser.append((1000 * (tc[h] - t_e), ls_fixed(h, float(d['fosc'][h][j]), Np)))
        ser = np.array(ser)
        pre = np.nanmean(ser[(ser[:, 0] >= -45) & (ser[:, 0] <= -8), 1])
        db = 20 * np.log10(np.maximum(ser[:, 1], 1e-9) / pre)
        cx = [ser[q, 0] for q in range(len(ser)) if ser[q, 0] >= 0 and db[q] <= -20]
        cross.append(cx[0] if cx else np.inf)
        for k in at:
            q = np.argmin(np.abs(ser[:, 0] - k)); at[k].append(db[q])
    cv = np.array(cross); cf = cv[np.isfinite(cv)]
    P(f'  N_past = {Np:3d} ({Np/3:.0f} ms): -20 dB at {np.median(cf):.1f} ms [{np.percentile(cf,10):.1f}, {np.percentile(cf,90):.1f}] (finite {len(cf)}/{len(cv)}); dB re pre-end at +10.7/+21.3/+32/+42.7/+64 ms: ' + ' / '.join(f'{np.nanmedian(at[k]):+.1f}' for k in at))
    fixed[Np] = float(np.median(cf))

# ---- the same crossing on the trace-predicted total harmonic amplitude sqrt(sum_v a2^2 + a3^2) (all voices), mapped to layer time
amp_pred = np.sqrt(np.maximum(pred, 0))
cr_pred = []; cr_pred_nodip = []
for i in notes:
    t_e = i * per + STEP_DUR
    pre = (tc >= t_e - .045) & (tc <= t_e - .008)
    refp = amp_pred[pre].mean()
    post = np.flatnonzero((tc >= t_e) & (tc <= t_e + .12))
    ok = [q for q in post if amp_pred[q] <= .1 * refp]
    cr_pred.append(1000 * (tc[ok[0]] - t_e) + LAGMS if ok else np.inf)
    # last crossing: after which it stays below (the "settled" tail)
    below = amp_pred[post] <= .1 * refp
    last_above = np.flatnonzero(~below)
    cr_pred_nodip.append(1000 * (tc[post[last_above[-1] + 1]] - t_e) + LAGMS if len(last_above) and last_above[-1] + 1 < len(post) else (0.0 if not len(last_above) else np.inf))
cp = np.array(cr_pred); cn = np.array(cr_pred_nodip)
P(f'\ntrace-predicted layer amplitude sqrt(sum a2^2+a3^2), first -20 dB crossing mapped to layer time (trace time {LAGMS:+d} ms): median {np.median(cp[np.isfinite(cp)]):.1f} ms [{np.percentile(cp[np.isfinite(cp)],10):.1f}, {np.percentile(cp[np.isfinite(cp)],90):.1f}] vs layer 44.2 ms;')
P(f'   same but the LAST time it is above -20 dB (settled tail): median {np.median(cn[np.isfinite(cn)]):.1f} ms [{np.percentile(cn[np.isfinite(cn)],10):.1f}, {np.percentile(cn[np.isfinite(cn)],90):.1f}]')
# the layer -20 dB as last-above too
cl_last = []
for i in notes:
    t_e = i * per + STEP_DUR; refv = refs[notes.index(i)]
    seg = env[int((t_e) * FS):int((t_e + .12) * FS)]
    above = np.flatnonzero(seg > .1 * refv)
    cl_last.append((above[-1] + 1) / FS * 1000 if len(above) else 0.0)
P(f'   layer envelope: last time above -20 dB (settled tail) median {np.median(cl_last):.1f} ms [{np.percentile(cl_last,10):.1f}, {np.percentile(cl_last,90):.1f}]; first crossing 44.2')
# how many notes show the rebound
reb = []
for i in notes:
    rows = [r for r in per_note[i] if not r.get('none') and 0 <= r['dt'] <= 50]
    if len(rows) < 4:
        continue
    A_ = np.array([r['A'] for r in rows]); k_ = int(np.argmin(A_));
    reb.append(20 * np.log10(A_[k_:].max() / max(A_[k_], 1e-9)))
reb = np.array(reb)
P(f'A rebound after its minimum within 0-50 ms of the note end: median {np.median(reb):.1f} dB, notes with a rebound > 6 dB: {(reb>6).sum()}/{len(reb)}')
json.dump(dict(table=res_tab, crossings={k: [float(x) for x in v] for k, v in cr.items()}, tails=tails.tolist(), lag_ms=LAGMS), open(C.D16 / 'q5.json', 'w'), indent=1, default=float)
open(C.D16 / 'q5_report.txt', 'w').write('\n'.join(out))

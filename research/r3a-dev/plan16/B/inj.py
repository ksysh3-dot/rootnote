"""Brief B / spec 16.4: error-injection blind set. Reference layer = R3-style oracle layer (MIDI lowest bass note, YIN octave rule,
single-voice LS amplitude/phase of the clean bass stem at the true f, engine harmonic set k=2..8 <= 700 Hz, lookup() weights,
voicing-0 24 dB/oct rolloff above 220 Hz) added to the original mix. Slakh TRAIN only.
Usage: inj.py <outdir_listen> <keyfile> <seed>"""
import sys, json, hashlib, re
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfiltfilt
for p in ('/home/ksysh/r3-work/tools/pvb-harness', '/home/ksysh/r3a-dev/la0'):
    sys.path.insert(0, p)
import research_core_xcheck as X
import research_gt_bass as G
import tables as TB

FS = 48000
EXC = 9.0                       # excerpt length (s)
TRACKS = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
outdir, keyfile, seed = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
rng = np.random.default_rng(seed)
LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)

# ------------------------------------------------------------------ track data
def kick_times(tr):
    d = X.SLAKH_MIDI / tr
    meta = (d / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Drums\b', parts[i + 1])]
    ks = []
    for sid in ids:
        p = d / 'MIDI' / f'{sid}.mid'
        if p.exists(): ks += [s for s, e, pn in X.read_midi(p) if pn in (35, 36)]
    return np.array(sorted(ks))

def segments(notes, tp, t0, t1):
    """Monophonic lowest-note segmentation of the MIDI notes inside [t0,t1): list of dict(s,e,f,onset)."""
    notes = sorted((s, e, p, i) for i, (s, e, p) in enumerate(notes) if e > t0 and s < t1 and e - s > 0.02)
    bp = sorted({min(max(x, t0), t1) for s, e, p, i in notes for x in (s, e)} | {t0, t1})
    raw = []
    for a, b in zip(bp[:-1], bp[1:]):
        act = [(p, s, i) for s, e, p, i in notes if s <= a + 1e-9 and e >= b - 1e-9]
        if act: p, s, i = min(act); raw.append([a, b, p, i, s])
    out = []
    for a, b, p, i, s in raw:
        if out and out[-1]['id'] == i and abs(out[-1]['e'] - a) < 1e-9: out[-1]['e'] = b
        else: out.append(dict(s=a, e=b, p=p, id=i, f=440 * 2 ** ((p + tp - 69) / 12), onset=(s >= t0 - 1e-9), note_s=s))
    return [g for g in out if g['e'] - g['s'] >= max(0.05, 1.5 / g['f'])]

def load_track(tr):
    p = X.SLAKH / tr
    assert not re.search(r'slakh2100/(validation|test)(/|$)', str(p))
    bz, notes = X.bass_stems_and_notes(tr)
    n = min(len(bz), 150 * FS); bz = bz[:n]
    mix = X.read_excerpt(p / 'mix.flac', 0.0, n / FS)
    try:
        ty, fy = G.yin(G.to_rate(bz[:120 * FS], FS, G.CORE))
    except Exception as ex:
        log(tr, 'yin failed', ex); return None
    agree = {}
    for t in (-24, -12, 0, 12):
        fm = G.midi_f0(ty, notes, 0, t); both = np.isfinite(fm) & np.isfinite(fy)
        agree[t] = float(np.mean(np.abs(1200 * np.log2(fm[both] / fy[both])) < 50)) if both.sum() >= 20 else -1
    tp = max(agree, key=agree.get)
    log(tr, 'octave shift', tp, 'agree', round(agree[tp], 2))
    if agree[tp] < .5: return None
    return dict(tr=tr, bz=bz.astype(np.float64), mix=mix[:n], notes=notes, tp=tp, kicks=kick_times(tr))

def score_windows(T):
    res = []
    for w0 in np.arange(2.0, min(120.0, len(T['bz']) / FS - EXC - 1), 1.0):
        sg = segments(T['notes'], T['tp'], w0, w0 + EXC)
        if not sg: continue
        cov = sum(g['e'] - g['s'] for g in sg) / EXC
        ons = [g for g in sg if g['onset']]
        long_ = [g for g in sg if g['e'] - g['s'] >= 1.3]
        ks = T['kicks'][(T['kicks'] > w0 + .2) & (T['kicks'] < w0 + EXC - .2)]
        kb = sum(1 for k in ks if any(g['s'] - .05 <= k <= g['e'] for g in sg))
        lev = np.sqrt(np.mean(T['bz'][int(w0 * FS):int((w0 + EXC) * FS)] ** 2))
        if lev < 1e-3 or cov < .55: continue
        res.append(dict(tr=T['tr'], w0=float(w0), cov=cov, nons=len(ons), nlong=len(long_), kb=kb, lev=lev))
    return res

def type_score(r, t):
    base = r['cov']
    if t == 'E1': return base + .1 * min(r['nons'], 10) - (5 if r['nons'] < 6 else 0)
    if t == 'E2': return base + (1 if r['nlong'] >= 1 else -5) + .2 * min(r['nlong'], 2)
    if t == 'E4': return base + .3 * min(r['kb'], 8) - (5 if r['kb'] < 4 else 0)
    return base + .05 * min(r['kb'], 6) + .02 * min(r['nons'], 8)

# ------------------------------------------------------------------ reference layer
def ls_track(bz, s, e, f, hop=.005):
    """Sliding single-voice LS of the stem at the true f over [s,e): A(t), phi(t) with x ~ A cos(w t - phi), windows clipped to the note."""
    w = 2 * np.pi * f; W = max(3 / f, .04)
    th = np.arange(s, e, hop); th = np.r_[th, e] if len(th) else np.array([s, e])
    A = np.zeros(len(th)); ph = np.zeros(len(th)); ok = np.zeros(len(th), bool)
    for j, tc in enumerate(th):
        a, b = max(s, tc - W / 2), min(e, tc + W / 2)
        i0, i1 = int(round(a * FS)), int(round(b * FS))
        if i1 - i0 < 0.5 * FS / f: continue
        t = np.arange(i0, i1) / FS; x = bz[i0:i1]; wt = np.hanning(len(t) + 2)[1:-1] + 1e-3
        c, sn = np.cos(w * t), np.sin(w * t)
        M = np.array([[np.sum(wt * c * c), np.sum(wt * c * sn)], [np.sum(wt * c * sn), np.sum(wt * sn * sn)]])
        v = np.array([np.sum(wt * x * c), np.sum(wt * x * sn)])
        try: a_, b_ = np.linalg.solve(M, v)
        except np.linalg.LinAlgError: continue
        A[j] = np.hypot(a_, b_); ph[j] = np.arctan2(b_, a_); ok[j] = True
    if not ok.any(): return th, np.zeros_like(th), np.zeros_like(th)
    idx = np.flatnonzero(ok)
    A = np.interp(th, th[idx], A[idx]); ph = np.interp(th, th[idx], np.unwrap(ph[idx]))
    return th, A, ph

def harm_amps(f):
    w, g = TB.lookup(np.array([f]))
    out = np.zeros(7)
    for k in range(2, 9):
        fk = k * f
        if fk > 700: break
        r = 1.0
        if fk > 220:
            g12 = 10 ** (-12 * np.log2(fk / 220.) / 20); r = g12 * g12     # upperBlend 1 (24 dB/oct), the P1/voicing-0 profile
        out[k - 2] = g[0] * w[k - 2, 0] * r
    return out

def build_params(T, w0):
    sg = segments(T['notes'], T['tp'], w0, w0 + EXC)
    for g in sg:
        th, A, ph = ls_track(T['bz'], g['s'], g['e'], g['f'])
        g['th'], g['A'], g['ph'] = th, A, ph; g['ha'] = harm_amps(g['f'])
    return sg

def render_layer(sg, w0, n, delay=0., fscale=1., wrong=None, gain_fn=None, only=None):
    """Sum of segment oscillators. delay: amplitude/gate shifted later (phase unshifted). fscale/wrong: oscillators at f*fscale for the
    segments in 'only' (free running). gain_fn(t) multiplies the result."""
    y = np.zeros(n); tt = np.arange(n) / FS + w0
    for q, g in enumerate(sg):
        if only is not None and q not in only: continue
        fo = g['f'] * fscale; ha = harm_amps(fo) if fscale != 1 else g['ha']
        i0 = max(0, int(round((g['s'] - w0 + delay) * FS))); i1 = min(n, int(round((g['e'] - w0 + delay) * FS)))
        if i1 <= i0: continue
        t = tt[i0:i1]
        A = np.interp(t - delay, g['th'], g['A'])
        ph = np.interp(t, g['th'], g['ph']) if fscale == 1 else g['ph'][0]
        th_ = 2 * np.pi * fo * t - ph
        ramp = np.minimum(1, np.minimum(np.arange(i1 - i0), np.arange(i1 - i0)[::-1]) / (.003 * FS))
        s = np.zeros(len(t))
        for k in range(2, 9):
            if ha[k - 2] > 0: s += ha[k - 2] * np.cos(k * th_)
        y[i0:i1] += s * A * ramp
    if gain_fn is not None: y *= gain_fn(tt)
    return y

def rms(x): return float(np.sqrt(np.mean(np.asarray(x, float) ** 2))) if len(x) else 0.0
def bp(x, lo, hi): return sosfiltfilt(butter(4, [lo, hi], btype='band', fs=FS, output='sos'), x)

def smooth_box(mask, ramp):
    k = np.hanning(int(2 * ramp) + 1); k /= k.sum(); return np.convolve(mask.astype(float), k, 'same')

def calibrate(err, mask, ref, db=-6.0):
    """scale err so rms(err[mask]) = ref_rms * 10^(db/20), ref_rms = rms of the reference layer over the same mask (or over its active samples if tiny)"""
    act = np.abs(ref) > 1e-9; rr = rms(ref[mask]); ra = rms(ref[act])
    if rr < .1 * ra: rr = ra
    e = rms(err[mask])
    return err * (rr * 10 ** (db / 20) / max(e, 1e-12)), mask

# ------------------------------------------------------------------ error variants (layer-level)
def variants(T, w0, sg, ref, n):
    t = np.arange(n) / FS + w0; V = {}; M = {}      # layer variant, active mask (error-affected samples)
    # E1: 100 ms gap (-20 dB) at every re-attack (note onset inside the excerpt, after the first 0.1 s)
    gap = np.zeros(n)
    for g in sg:
        if g['onset'] and g['s'] - w0 > .1:
            i0 = int(round((g['s'] - w0) * FS)); gap[i0:min(n, i0 + int(.1 * FS))] = 1
    gs = smooth_box(gap, .005 * FS); V['E1'] = ref * (1 - gs * (1 - .1)); M['E1'] = gap > 0
    # E2: sustained wrong note, a semitone below the lowest note, on segments > 1 s (up to 3 longest)
    lng = sorted([q for q, g in enumerate(sg) if g['e'] - g['s'] > 1.0], key=lambda q: sg[q]['s'] - sg[q]['e'])[:3]
    w = render_layer(sg, w0, n, fscale=2 ** (-1 / 12), only=set(lng)); mk = np.abs(w) > 1e-9
    w, _ = calibrate(w, mk, ref); V['E2'] = ref + w; M['E2'] = mk
    # E3: intermodulation products (layer x mix content 80-1000 Hz: sum and difference tones), 60-1400 Hz
    mixm = T['mixseg'].mean(1); im = bp(ref * bp(mixm, 80, 1000), 60, 1400); mk = np.abs(ref) > 1e-9
    im, _ = calibrate(im, mk, ref); V['E3'] = ref + im; M['E3'] = mk
    # E4: 30 ms burst (100-700 Hz noise, Hann) at every kick inside the excerpt
    ks = T['kicks'][(T['kicks'] > w0 + .15) & (T['kicks'] < w0 + EXC - .15)]
    nz = bp(rng.standard_normal(n), 100, 700); b = np.zeros(n); mk = np.zeros(n, bool); L = int(.03 * FS)
    for k in ks:
        i0 = int(round((k - w0) * FS)); b[i0:i0 + L] += nz[i0:i0 + L] * np.hanning(L); mk[i0:i0 + L] = True
    b, _ = calibrate(b, mk, ref) if len(ks) else (b, mk)
    V['E4'] = ref + b; M['E4'] = mk
    # E5: attack (amplitude/gate) 30 ms late
    V['E5'] = render_layer(sg, w0, n, delay=.03); M['E5'] = np.abs(V['E5'] - ref) > 1e-4 * max(np.abs(ref).max(), 1e-9)
    # E6: 5 Hz AM, 6 dB peak to peak
    V['E6'] = ref * 10 ** (3 * np.sin(2 * np.pi * 5 * t) / 20); M['E6'] = np.abs(ref) > 1e-9
    V['E0'] = ref.copy(); M['E0'] = np.abs(ref) > 1e-9
    return V, M, ks

def spots(err, ref, n, k=3, win=1.0):
    """top non-overlapping windows (1 s, hop .25) of the error (or, for the null, of the reference layer) energy"""
    x = err if rms(err) > 0 else ref
    hop = int(.25 * FS); wn = int(win * FS)
    en = np.array([np.sum(x[i:i + wn] ** 2) for i in range(0, n - wn + 1, hop)])
    out = []
    for i in np.argsort(en)[::-1]:
        if en[i] <= 0.02 * en.max(): break
        if all(abs(i - j) * .25 >= win for j in out): out.append(int(i))
        if len(out) == k: break
    return sorted((i * .25, i * .25 + win) for i in out)

# ------------------------------------------------------------------ main
log('loading tracks')
D = {}
for tr in TRACKS:
    T = load_track(tr)
    if T: D[tr] = T
cands = {tr: score_windows(T) for tr, T in D.items()}
for tr, c in cands.items(): log(tr, 'windows', len(c), 'best cov', round(max([r['cov'] for r in c], default=0), 2), 'max kb', max([r['kb'] for r in c], default=0), 'max ons', max([r['nons'] for r in c], default=0))
TYPES = ['E2', 'E1', 'E4', 'E3', 'E5', 'E6']
assign = {}; used = set()
for t in TYPES:
    best = max(((type_score(r, t), r) for tr, c in cands.items() if tr not in used for r in c), key=lambda x: x[0])
    assign[t] = best[1]; used.add(best[1]['tr']); log('assign', t, best[1]['tr'], best[1]['w0'], 'score', round(best[0], 2))
# stem-to-mix scale check (low band)
pairs = []
nulls = [rng.choice([a for a in TYPES])] ; nulls = list(rng.permutation(TYPES)[:2])
for t in TYPES + ['N1', 'N2']:
    pairs.append(t)
built = {}
for t in TYPES + ['N1', 'N2']:
    src = assign[t] if t in assign else assign[nulls[int(t[1]) - 1]]
    T = D[src['tr']]; w0 = src['w0']; n = int(EXC * FS)
    T['mixseg'] = T['mix'][int(w0 * FS):int(w0 * FS) + n]
    key = (src['tr'], w0)
    if key not in built:
        sg = build_params(T, w0); ref = render_layer(sg, w0, n)
        # stem to mix check on the fundamental region
        lp = lambda x: sosfiltfilt(butter(4, 250, fs=FS, output='sos'), x)
        zb = lp(T['bz'][int(w0 * FS):int(w0 * FS) + n]); zm = lp(T['mixseg'].mean(1)); c = float(np.dot(zm, zb) / np.dot(zb, zb))
        log(src['tr'], 'stem->mix low-band coefficient', round(c, 3), '(', round(20 * np.log10(abs(c) + 1e-9), 2), 'dB )')
        V, M, ks = variants(T, w0, sg, ref, n); built[key] = (sg, ref, V, M, ks)
    sg, ref, V, M, ks = built[key]
    act = np.abs(ref) > 1e-9
    log(t, src['tr'], 'w0', src['w0'], 'layer active', round(act.mean(), 2), 'layer rms re mix (active) dB', round(20 * np.log10(rms(ref[act]) / rms(T['mixseg'][act.nonzero()[0]])), 1),
        'segments', len(sg), 'kicks', len(ks))

# ------------------------------------------------------------------ package
outdir.mkdir(parents=True, exist_ok=True)
for p in outdir.glob('inj_*.wav'): p.unlink()
order = [int(i) for i in rng.permutation(len(pairs))]
key = {}; sheet = []
fade = np.minimum(1, np.minimum(np.arange(int(EXC * FS)), np.arange(int(EXC * FS))[::-1]) / 480)[:, None]
for no, j in enumerate(order, 1):
    t = pairs[j]; src = assign[t] if t in assign else assign[nulls[int(t[1]) - 1]]
    T = D[src['tr']]; w0 = src['w0']; n = int(EXC * FS); sg, ref, V, M, ks = built[(src['tr'], w0)]
    mixs = T['mixseg']; var = V['E0'] if t.startswith('N') else V[t]
    mk = M['E0'] if t.startswith('N') else M[t]
    A_ref = mixs + ref[:, None]; A_var = mixs + var[:, None]
    errdb = 20 * np.log10(max(rms((var - ref)[mk]), 1e-12) / max(rms(ref[mk]), 1e-12)) if mk.any() else float('nan')
    g_match = rms(A_ref) / rms(A_var)                 # same loudness within the pair
    A_var = A_var * g_match
    sc = min(10 ** (-20 / 20) / rms(A_ref), .95 / max(np.abs(A_ref).max(), np.abs(A_var).max()))
    A_ref, A_var = A_ref * sc, A_var * sc
    swap = bool(rng.random() < .5)
    a, b = (A_var, A_ref) if swap else (A_ref, A_var)
    names = ('err', 'ref') if swap else ('ref', 'err')
    if t.startswith('N'): names = ('null', 'null')
    pk = np.abs(np.r_[a, b]).max()
    wav = np.r_[a * fade, np.zeros((FS, 2)), b * fade].astype(np.float32)
    sf.write(str(outdir / f'inj_{no}.wav'), wav, FS, subtype='PCM_16')
    sp = spots(var - ref, ref, n)
    key[f'inj_{no}'] = dict(type=t, A=names[0], B=names[1], track=src['tr'], start_s=w0, err_db_re_ref=round(errdb, 2), loudness_match_db=round(20 * np.log10(g_match), 3),
                           scale=float(sc), spots=sp)
    log(f'inj_{no}: err energy re ref layer over active {errdb:+.1f} dB, loud-match {20*np.log10(g_match):+.2f} dB, peak {pk:.3f}, spots {sp}')
    sheet.append((no, sp, EXC + 1.0))
blob = json.dumps(dict(key=key, seed=seed), sort_keys=True).encode()
keyfile.parent.mkdir(parents=True, exist_ok=True); keyfile.write_bytes(blob)
h = hashlib.sha256(blob).hexdigest(); log('key sha256', h)

L = ['# 오류 주입 블라인드 (해악 순위) — 청감 시트', '',
     f'열쇠(정답) 파일의 sha256 (듣기 전에 고정): `{h}`', '',
     '## 방법', '',
     '- 파일은 `inj_1.wav` ~ `inj_8.wav` 8개다. 한 파일 = A (9 초) + 1 초 무음 + B (9 초)이고, A와 B는 같은 곡 구간이다.',
     '- 쌍마다 A와 B 중 한쪽이 기준(깨끗한 층)이고 다른 쪽에 오류가 하나 들어 있을 수 있다. 둘 다 같은 쌍도 있다.',
     '- 같은 기기, 같은 음량으로 듣는다. A/B 음량은 이미 맞춰 두었다.',
     '- 아래 "들을 곳"은 A와 B에 똑같이 적용되는 시각이다. 그 부분을 먼저 들어 보고, 나머지는 자유롭게 들어도 된다.',
     '- 답: 어느 쪽이 더 거슬리나 (A / B / 같음) + 거슬림 1–5 (1 = 거의 안 거슬림, 5 = 매우 거슬림).',
     '- 이 결과는 해악 순위로만 쓰고, 채택 판정에는 쓰지 않는다.', '',
     '## 들을 곳', '', '| 쌍 | 파일 | 들을 곳 (A 안의 시각, 초) | 같은 곳 (B 안의 시각, 초 = A 시각 + 10) | 질문 |', '|---|---|---|---|---|']
for no, sp, off in sheet:
    a_ = ', '.join(f'{x:.2f}–{y:.2f}' for x, y in sp); b_ = ', '.join(f'{x + off:.2f}–{y + off:.2f}' for x, y in sp)
    L.append(f'| {no} | inj_{no}.wav | {a_} | {b_} | 어느 쪽이 더 거슬리나 (A/B/같음) + 거슬림 1–5 |')
L += ['', '## 답 적는 곳', '', '| 쌍 | 더 거슬리는 쪽 (A/B/같음) | 거슬림 1–5 | 메모 |', '|---|---|---|---|'] + [f'| {i} |  |  |  |' for i in range(1, 9)]
(outdir / 'listen.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
Path(str(keyfile.parent / 'build.log')).write_text('\n'.join(LOG) + '\n', encoding='utf-8')
log('done')

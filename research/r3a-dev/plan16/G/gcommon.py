"""Plan16 G common code (16.13 + 16.13.1; readings in CHOICES.md).  Causal stable-voice detector, context P(h), gain curve, bass-sounding helpers, energies."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/K')
from kcommon import *            # noqa (SongCtx, params, note_energy, ... ; D helpers)

G_DIR = HOME / 'r3a-dev/plan16/G'
T4 = int(4.0 * FSC)              # render sample index of t = 4 s (3 kHz)
HOPS_S = HOP_S                   # 16/3000 s = 5.3333 ms
SIL_IDS = (3, 4, 5, 6, 7)        # silence-class sa-wrong components (cause 1..5)


def nsteps(ds):                  # N_s: ceil(D_s / hop)
    return int(np.ceil(ds / HOPS_S - 1e-9))


# ------------------------------------------------------------------------------------------ causal stable-voice detector (16.13.1 B2)
def stable_scan(d, ds, q_db=-30.0, minrows=400, tol_cent=30.0):
    """d = sig.core_d (hops x 8 slots).  Returns dict: stable[h] (any voice stable at h), onset[h] (number of voices that become stable at h),
    nstable[h] (voices stable at h), maxread[h] (largest trace hop index read for the decision at h; must be <= h).
    Per hop h only rows with hop index <= h are read; the amp percentile uses rows with hop < h (histogram updated AFTER the decision)."""
    nh = d['state'].shape[0]; Ns = nsteps(ds)
    st, co, vo, ft = d['state'], d['coast'], d['voice'], d['ftr']
    amp = d['A'] * d['c'] * d['sig']
    NB = 400; OFF = 300                                   # 1 dB bins, bin = floor(20 log10 amp) + OFF, clipped to [0, NB-1]
    hist = np.zeros(NB); nrows = 0
    win = {}                                              # voice id -> list of (hop index, cent) over the current uninterrupted ON/non-coast run
    stable = np.zeros(nh, bool); onset = np.zeros(nh, int); nstable = np.zeros(nh, int); maxread = np.zeros(nh, int)
    prev_stable_ids = set()
    for h in range(nh):
        rd = h                                             # hop of the rows read now
        if nrows >= minrows:
            c = np.cumsum(hist); k = int(np.searchsorted(c, 0.95 * nrows))
            q95_db = float(k - OFF)                       # lower edge of the bin holding the 95th percentile
        else:
            q95_db = -np.inf
        new = {}; cur_ids = set(); rows = []
        for j in range(8):
            if st[h, j] == 2 and co[h, j] == 0 and ft[h, j] > 0:
                v = int(vo[h, j]); a = float(amp[h, j]); rows.append(a)
                w = win.get(v, [])
                w = (w + [(h, 1200.0 * np.log2(ft[h, j]))])[-Ns:]
                new[v] = w
                if len(w) == Ns:
                    cs = [x[1] for x in w]
                    mr = max(x[0] for x in w); rd = max(rd, mr)
                    amp_ok = True if q95_db == -np.inf else (a > 0 and 20 * np.log10(a) >= q95_db + q_db)
                    if max(cs) - min(cs) <= tol_cent and amp_ok:
                        cur_ids.add(v)
        win = new
        maxread[h] = rd
        stable[h] = len(cur_ids) > 0; nstable[h] = len(cur_ids); onset[h] = len(cur_ids - prev_stable_ids)
        prev_stable_ids = cur_ids
        for a in rows:                                     # histogram update after the decision
            b = int(np.clip(np.floor(20 * np.log10(max(a, 1e-15))) + OFF, 0, NB - 1)); hist[b] += 1; nrows += 1
    return dict(stable=stable, onset=onset, nstable=nstable, maxread=maxread, Ns=Ns)


def p_context(stable, H):
    """P(h) = 1 iff a stable voice at some hop in (h - nH, h]  (nH = round(H/hop)); uses hops <= h only"""
    nH = int(round(H / HOPS_S)); n = len(stable); P = np.zeros(n, bool); last = -10 ** 9
    for h in range(n):
        if stable[h]:
            last = h
        P[h] = (h - last) < nH
    return P


def gain_curve(P, gcap_db, up=0.010, down=0.030, start_low=True):
    """linear-amplitude gain per hop: P=1 -> ramp up to 1 in `up` s; P=0 -> fade down to g_cap in `down` s; both start at the hop of the change (no look-ahead)"""
    gc = 10 ** (gcap_db / 20.0); n = len(P); G = np.zeros(n); g = gc if start_low else 1.0
    su = (1 - gc) * HOPS_S / up; sd = (1 - gc) * HOPS_S / down
    for h in range(n):
        g = min(1.0, g + su) if P[h] else max(gc, g - sd)
        G[h] = g
    return G


def gate_events(ctx, Ghop):
    """per-voice gain knots = the gain of the trace hop of each voice hop (hop resolution, linear between hops).  returns events_by_voice for SongCtx.render"""
    by = {}
    for vi, v in enumerate(ctx.voices):
        if not v['ok'] or len(v['T']) == 0:
            continue
        by[vi] = [dict(tk=v['T'], gk=Ghop[v['hs'].astype(int)])]
    return by


# ------------------------------------------------------------------------------------------ stem-aware bass sounding
def bass_intervals(ctx):
    """merged intervals (layer time) where the bass stem sounds: -15 dB activity [on, off] of each MIDI segment (D act15), MIDI [s, e] if inactive"""
    iv = []
    for sg, a in zip(ctx.segs, ctx.act):
        iv.append((a['on'], a['off']) if a['active'] else (sg['s'], sg['e']))
    iv = sorted(iv); out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return np.array(out, float).reshape(-1, 2)


def silence_len(iv, t):
    """time since the end of the latest sounding interval (0 inside an interval; t itself if none before; inf for songs without bass)"""
    t = np.asarray(t, float)
    if len(iv) == 0:
        return np.full(len(t), np.inf)
    k = np.searchsorted(iv[:, 0], t, 'right') - 1                   # last interval starting at/before t
    out = np.where(k < 0, t, 0.0)
    kk = np.clip(k, 0, None)
    inside = (k >= 0) & (t <= iv[kk, 1])
    out = np.where((k >= 0) & ~inside, t - iv[kk, 1], out)
    return np.where(inside, 0.0, out)


def hop_layer_time(ctx):
    return ctx.sig.tc1 + LAG


def sample_hops(ctx, tt):
    return np.clip(np.rint((tt - LAG - ctx.tc[0]) / HOP_S).astype(int), 0, len(ctx.tc) - 1)


# ------------------------------------------------------------------------------------------ energies
def En(x, a=I_MIN):
    return float(np.sum(x[..., a:] ** 2))


def sil_energy(Y, a=I_MIN):
    return En(Y[list(SIL_IDS)].sum(0), a)


def right_energy(Y, a=I_MIN):
    return En(Y[0] + Y[1], a)


def override_by(ctx, fn):
    """comp_override: fn(vi, v, tt-hop index array h) -> new comp array for silence samples (comp in 3..7), others unchanged"""
    ov = {}
    for vi, v in enumerate(ctx.voices):
        if not v['ok']:
            continue
        c = v['comp']; m = (c >= 3) & (c <= 7)
        if not m.any():
            continue
        c2 = c.copy(); c2[m] = fn(vi, v, m)[m]; ov[vi] = c2
    return ov

"""Stage 0 (0a, 0b, 0c, 0d) on the 10 development songs.  usage: bash ../D/runpy.sh ~/r3a-dev/plan16/G/stage0.py -> stage0_raw.json"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/G')
from gcommon import *
import multiprocessing as mp

HS = (1.0, 2.0, 4.0)
DSS = (0.100, 0.150)
GCS = (-24.0, -12.0)
EDGES = np.array([0.25, 1.0, 2.0, 4.0])


def both(Y, ids):
    x = Y[list(ids)].sum(0)
    return [En(x, I_MIN) / R3R, En(x, T4) / R3R]


def one(key):
    t0 = time.time()
    ctx = SongCtx(key, probe_nobass=False)
    iv = bass_intervals(ctx) if not ctx.nobass else np.zeros((0, 2))
    d = ctx.sig.core_d; nh = d['state'].shape[0]
    thl = hop_layer_time(ctx)[:nh]
    out = dict(key=key, nobass=ctx.nobass, dur=ctx.dur, n_notes=int(len(ctx.segs)), iv=iv.tolist())
    Y0 = ctx.render(None)
    out['core'] = dict(sil=both(Y0, SIL_IDS), right=both(Y0, (0, 1)))
    # ---- 0a: bins by stem-aware silence length (sample level)
    def binfn(vi, v, m):
        sl = silence_len(iv, v['tt'])
        b = np.searchsorted(EDGES, sl, 'right')               # 0: <0.25, 1: .25-1, 2: 1-2, 3: 2-4, 4: >4  (inf -> 4)
        return np.where(ctx.nobass, 8, 3 + b)
    Yb = ctx.render(None, comp_override=override_by(ctx, binfn))
    out['bins'] = [both(Yb, (i,)) for i in (3, 4, 5, 6, 7, 8)]    # last = no-bass song
    # ---- 0b: oracle
    slh = silence_len(iv, thl) if not ctx.nobass else np.full(nh, np.inf)
    gc24 = 10 ** (-24 / 20)
    orc = {}
    for H in HS:
        Gh = np.where(slh >= H, gc24, 1.0)
        Yo = ctx.render(gate_events(ctx, Gh))
        orc[str(H)] = dict(sil=both(Yo, SIL_IDS), right=both(Yo, (0, 1)))
    out['oracle'] = orc
    # ---- 0c / 0d: the real gate
    bsound = np.zeros(nh, bool)
    for a, b in iv:
        bsound |= (thl >= a) & (thl <= b)
    span = thl >= 4.0
    s_all = np.sort(np.asarray(ctx.rf['ss'], float)); s_notes = s_all[(s_all >= 0.5) & (s_all <= ctx.dur - 0.1)]
    hon = sample_hops(ctx, s_notes) if len(s_notes) else np.zeros(0, int)
    e_core_note = note_energy(Y0[0] + Y0[1], s_notes, 0.200) if len(s_notes) else np.zeros(0)
    real = {}; leak = {}
    for ds in DSS:
        sc = stable_scan(d, ds)
        leak[str(ds)] = dict(max_excess=int((sc['maxread'] - np.arange(nh)).max()), n_stable_hops=int(sc['stable'].sum()), n_onsets=int(sc['onset'].sum()))
        for H in HS:
            P = p_context(sc['stable'], H)
            def pfn(vi, v, m):
                hh = sample_hops(ctx, v['tt'])
                return np.where(P[hh], 3, 8)
            Yp = ctx.render(None, comp_override=override_by(ctx, pfn))
            e_in, e_out = both(Yp, (8,)), both(Yp, (3,))
            tdur = max(float(thl[span].size) * HOPS_S, 1e-9)
            nobs = span & ~bsound
            dP = np.diff(P.astype(int))
            ent = dict(p0_frac=float(1 - P[span].mean()), p0_frac_all=float(1 - P.mean()),
                       rp=[e_in[0] / max(e_in[0] + e_out[0], 1e-30), e_in[1] / max(e_in[1] + e_out[1], 1e-30)], e_p0=e_in, e_p1=e_out,
                       onset_per_s_nobass=float(sc['onset'][nobs].sum() / max(nobs.sum() * HOPS_S, 1e-9)), onset_per_s_all=float(sc['onset'][span].sum() / tdur),
                       stable_hop_frac=float(sc['stable'][span].mean()),
                       trans_per_min=float((np.abs(dP)[span[1:]]).sum() / (tdur / 60.0)),
                       bass_hops=int((bsound & span).sum()), bass_p1=int((P & bsound & span).sum()),
                       trans10_bass=int(((dP == -1) & bsound[1:] & span[1:]).sum()), nobass_hops=int(nobs.sum()))
            for gcd in GCS:
                G = gain_curve(P, gcd)
                Yg = ctx.render(gate_events(ctx, G))
                r = dict(sil=both(Yg, SIL_IDS), right=both(Yg, (0, 1)))
                if len(s_notes):
                    e_g = note_energy(Yg[0] + Yg[1], s_notes, 0.200)
                    first = ~P[hon]
                    okn = first & (e_core_note > 1e-3 * np.median(e_core_note[e_core_note > 0])) if (e_core_note > 0).any() else first
                    ratio = (e_g[okn] + 1e-30) / (e_core_note[okn] + 1e-30)
                    r['first'] = dict(n_notes=int(len(s_notes)), n_first=int(first.sum()), n_ok=int(okn.sum()),
                                      db=float(10 * np.log10((e_g[okn].sum() + 1e-30) / (e_core_note[okn].sum() + 1e-30))) if okn.any() else None,
                                      frac_gt6=float(np.mean(ratio < 0.25)) if okn.any() else None,
                                      note_db=(10 * np.log10(ratio)).tolist())
                ent[f'g{int(gcd)}'] = r
            real[f'{H:g}_{int(ds * 1000)}'] = ent
    out['real'] = real; out['leak'] = leak
    out['secs'] = time.time() - t0
    print('stage0', key, round(out['secs'], 1), flush=True)
    return key, out


if __name__ == '__main__':
    with mp.get_context('fork').Pool(10) as pool:
        res = dict(pool.map(one, SONGS, chunksize=1))
    json.dump(res, open(G_DIR / 'stage0_raw.json', 'w'), default=float)
    print('done')

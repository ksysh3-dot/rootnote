#!/usr/bin/env python3
"""Study 1 phase A (#4): where does the non-additive part of bed + impact first appear?

Every case is rendered three times with identical settings: the mixture x = bed + impact, the bed alone and the
impact alone. For the generated layer, the output and each captured internal stage s,
    I_s = S_s(x) - S_s(bed) - S_s(impact)
keeps only what exists because the two sounds met (bed gaps, track stealing, leftovers, limiter interaction, but
also legitimate interaction of nonlinear stages such as HPSS). It is an upper-bound candidate for impact error,
not noise truth. No DSP is changed: P1+ (flags 6) and P1++ v0.3 (impact mode 8) are frozen; this is the
development cohort only (the confirmation seed 2026102801 is not opened here).
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.signal import hilbert
import research_p1pp_impacts as I
import research_p1plus as P
from p1plus_paths import default_library
from vb_quality.stage_capture import COLUMNS

FS = 48000
CORE = 3000
# continuous stage signals in pipeline order (discrete/mode columns are left out)
STAGES = ('decimated', 'band', 'original_h', 'original_p', 'selected_h', 'selected_p', 'analytic_envelope',
          'nominal_amplitude', 'env_a', 'env_p', 'original_gain', 'applied_gain', 'raw_grain', 'tonal_after_gain',
          'percussion', 'pre_filter', 'post_filter', 'upper_blend')
MODELS = (('p1plus', 6, 0), ('p1pp_v03', 6, 8))
LEVELS = (-24, -12, -6)


def energy(x): return float(np.sum(np.asarray(x, dtype=float) ** 2))
def db(a, b=1.0): return float(10 * np.log10(max(a, 1e-30) / max(b, 1e-30)))


def windows(t, onset, duration):
    return dict(pre=(t >= onset - .15) & (t < onset - .005), attack=(t >= onset) & (t < onset + duration),
                early=(t >= onset + duration) & (t < onset + duration + .08),
                late=(t >= onset + duration + .08) & (t < onset + duration + .5))


def aligned(r, n, key):
    d = r['latency']
    return r[key][d:d + n, 0].astype(float)


def stage_table(r):
    s = r['stages']
    idx = (s[:, 0].astype(np.int64) + (s[:, 1].astype(np.int64) << 32))
    return idx, s


def stage_interaction(rx, rb, ri, onset, duration, impact_energy):
    """Per stage: window energy of I_s relative to the additive reference, and first exceedance time."""
    ix, sx = stage_table(rx); ib, sb = stage_table(rb); ii, si = stage_table(ri)
    common = np.intersect1d(np.intersect1d(ix, ib), ii)
    px, pb, pi = (np.searchsorted(a, common) for a in (ix, ib, ii))
    t = common / CORE
    # stage clocks run at the analysis position; report core time as is (no per-stage delay model)
    w = windows(t, onset, duration)
    out = {}
    for name in STAGES:
        c = COLUMNS.index(name)
        a, b, i = sx[px, c], sb[pb, c], si[pi, c]
        inter = a - b - i
        ref = np.abs(b) + np.abs(i)
        row = {}
        for k, m in w.items():
            row[k + '_interaction_db'] = db(energy(inter[m]), energy(ref[m]) + 1e-30)
        # first time after onset-150 ms where |I| in a 10 ms window exceeds 10% of the additive reference RMS
        hop = 30
        n = len(inter) // hop * hop
        ri_ = np.sqrt(np.mean(inter[:n].reshape(-1, hop) ** 2, axis=1))
        rr_ = np.sqrt(np.mean(ref[:n].reshape(-1, hop) ** 2, axis=1))
        tb = t[:n].reshape(-1, hop)[:, 0]
        hit = np.where((tb >= onset - .15) & (ri_ > .1 * rr_) & (rr_ > 0))[0]
        row['first_exceed_ms_from_onset'] = float((tb[hit[0]] - onset) * 1000) if len(hit) else None
        row['peak_abs_interaction'] = float(np.max(np.abs(inter))) if len(inter) else 0.0
        # phase A.1: state view. Gains, envelopes and blend ratios are not additive; measure how far the
        # mixture's state departs from the bed-only state, and when it comes back after the impact.
        dev = a - b
        for k in ('pre', 'early', 'late'):
            m = w[k]
            row[k + '_state_dev_db'] = db(energy(dev[m]), energy(b[m]) + 1e-30)
        rd = np.sqrt(np.mean(dev[:n].reshape(-1, hop) ** 2, axis=1))
        rb_ = np.sqrt(np.mean(b[:n].reshape(-1, hop) ** 2, axis=1))
        end = onset + duration
        back = None
        for j in np.where(tb >= end)[0]:
            if j + 3 <= len(rd) and np.all(rd[j:j + 3] <= .1 * np.maximum(rb_[j:j + 3], 1e-12)):
                back = float((tb[j] - end) * 1000); break
        row['state_recover_ms_after_impact'] = back
        out[name] = row
    return out


def output_interaction(rx, rb, ri, n, t, onset, duration, impact_energy):
    res = {}
    for key in ('stem', 'output'):
        y = aligned(rx, n, key) - aligned(rb, n, key) - aligned(ri, n, key)
        w = windows(t, onset, duration)
        res[key] = {k + '_db_per_input': db(energy(y[m]), impact_energy) for k, m in w.items()}
        if key == 'stem':
            # share of the early window explained by the bed's own generated layer (gap/step/phase slip)
            full = aligned(rb, n, 'stem'); m = w['early']; tt = t[m]
            bs, bq = full[m], np.imag(hilbert(full))[m]
            knots = np.arange(tt[0], tt[-1] + .01, .01)
            hats = np.clip(1 - abs(tt[:, None] - knots[None, :]) / .01, 0, None)
            mod = np.column_stack([bs[:, None] * hats, bq[:, None] * hats])
            z = y[m]
            other = z - mod @ np.linalg.lstsq(mod, z, rcond=1e-10)[0]
            res[key]['early_bed_shaped_db_per_input'] = db(max(energy(z) - energy(other), 0), impact_energy)
            res[key]['early_nonbed_db_per_input'] = db(energy(other), impact_energy)
    # what the limiter/mix adds on top of the generated layer
    # difference of two dB values, not the energy of the limiter's difference waveform (see limiter_gr_db, A.2)
    res['limiter_minus_stem_early_db'] = res['output']['early_db_per_input'] - res['stem']['early_db_per_input']
    return res


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--floor', action='store_true', help='also render the numeric-floor controls')
    p.add_argument('--out-db', type=float, default=-18, help='engine output level (app general build allows up to -3)')
    p.add_argument('--controls', action='store_true',
                   help='phase A.2: input-rounding sensitivity of I and the limiter gain of all three renders')
    a = p.parse_args()
    render = lambda *args, **kw: P.render(*args, out_db=a.out_db, **kw)
    lib = P.api(a.library.resolve())
    fixtures = [f for f in I.fixtures(FS) if f[1]] + list(I.fresh_fixtures(FS))
    cases = []
    pad = np.zeros(FS // 2)
    for shape, _bed, t, b, z, onset, duration in fixtures:
        n = len(t)
        for model, flags, mode in MODELS:
            rb = render(lib, np.r_[b, pad], FS, flags, impact_mode=mode)
            levels = LEVELS + ((-60,) if a.floor else ())
            for level in levels:
                impact = z * 10 ** (level / 20); x = b + impact
                assert np.max(abs(x)) < 1, 'no input clipping'
                rx = render(lib, np.r_[x, pad], FS, flags, impact_mode=mode)
                ri = render(lib, np.r_[impact, pad], FS, flags, impact_mode=mode)
                e = energy(impact)
                row = dict(shape=shape, model=model, flags=flags, impact_mode=mode, impact_peak_dbfs=level,
                           output=output_interaction(rx, rb, ri, n, t, onset, duration, e),
                           stages=stage_interaction(rx, rb, ri, onset, duration, e))
                if a.controls:
                    # Rounding: the three renders take float32(bed+impact), float32(bed) and float32(impact). Render
                    # the float32 sum of the two separate inputs and compare with the mixture: the stem difference is
                    # the part of I that input rounding alone can produce. Raw energies, no 1e-30 clamp.
                    w = windows(t, onset, duration)
                    x32 = b.astype(np.float32) + impact.astype(np.float32)
                    rr = render(lib, np.r_[x32.astype(np.float64), pad], FS, flags, impact_mode=mode)
                    dstem = aligned(rx, n, 'stem') - aligned(rr, n, 'stem')
                    inter = aligned(rx, n, 'stem') - aligned(rb, n, 'stem') - aligned(ri, n, 'stem')
                    row['rounding'] = dict(
                        input_mismatch_energy=energy(x.astype(np.float32).astype(np.float64) - x32.astype(np.float64)),
                        impact_energy=e,
                        **{k + '_I_energy': energy(inter[m]) for k, m in w.items()},
                        **{k + '_rounding_energy': energy(dstem[m]) for k, m in w.items()})
                    # Limiter: LIM_GR_DB holds the minimum limiter gain since the previous meters() read, and render()
                    # reads the meters once at the end, so 0 means the gain stayed 1 for the whole render.
                    import test_engine as T
                    row['limiter_gr_db'] = {name: float(r['meters'][T.M['LIM_GR_DB']])
                                            for name, r in (('mixture', rx), ('bed', rb), ('impact', ri))}
                if a.floor and level == LEVELS[0]:
                    # block-size drift control: same mixture at block 1379
                    rx2 = render(lib, np.r_[x, pad], FS, flags, block=1379, impact_mode=mode)
                    d = aligned(rx, n, 'stem') - aligned(rx2, n, 'stem')
                    row['block_drift_stem_db_per_input'] = db(energy(d), e)
                cases.append(row)
                o = row['output']['stem']
                first = sorted(((v['first_exceed_ms_from_onset'], k) for k, v in row['stages'].items()
                                if v['first_exceed_ms_from_onset'] is not None))[:3]
                print(shape, model, level, 'early', round(o['early_db_per_input'], 2),
                      'late', round(o['late_db_per_input'], 2), 'first', first, flush=True)
    result = dict(schema='rootnote.study1.phaseA.v2', issue=4, out_db=a.out_db, dsp_changed=False, confirmation_opened=False,
                  library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                  seeds=dict(fixtures=2026102607, fresh=2026102608), sample_rate=FS, core_rate=CORE,
                  models=[dict(name=m, flags=f, impact_mode=i) for m, f, i in MODELS],
                  definition='I = S(bed+impact) - S(bed) - S(impact), engine-reported latency, no fitted shift/gain',
                  caveat='Nonlinear stages (HPSS, limiter) also produce legitimate interaction; I is an upper-bound '
                         'candidate, not noise truth. Stage times are core-clock positions without a per-stage '
                         'delay model, so first-exceedance order across stages is indicative only.',
                  cases=cases)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

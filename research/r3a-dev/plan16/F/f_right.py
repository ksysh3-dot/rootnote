"""Right-layer F on the 10 dev (V6) songs, TRACE-BASED exactly as plan16/D/ref_rows.py 'core' row (16.9 table: core v1.5 right vs R3 = +0.49 dB, wrong_sa F 0.3604).
Core voice trace + bh/det streams are re-rendered with the library under test (research_core_metrics.Ctx, voice+stage capture, same recipe as la0/data.streams)
and cached in plan16/F/cache/<label>_<key>.npz;  then data.streams is pointed at that cache and the D-tools measure_row() is run.
usage: f_right.py LABEL LIB [rho]    (rho given -> 17-parameter call, new lib)"""
import sys, json, time, multiprocessing as mp
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F')
from pathlib import Path
label, lib_path = sys.argv[1], sys.argv[2]
rho = float(sys.argv[3]) if len(sys.argv) > 3 else None
import numpy as np
import dcommon as DC
from dcommon import *
import data as DATA
import research_core_metrics as M
import research_core_api as CA
import research_core_xcheck as X
from vb_quality.stage_capture import INDEX as SI

CDIR = Path('/home/ksysh/r3a-dev/plan16/F/cache'); CDIR.mkdir(exist_ok=True)
if rho is not None:
    M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0)]
    CA.PARAMS = CA.PARAMS + ('capRho',)
    CA.DEFAULTS = dict(CA.DEFAULTS, capRho=0)


def render_streams(key):
    p = CDIR / f'{label}_{key}.npz'
    if p.exists():
        return
    res = dict(voicing=0, ampSource=0)
    if rho is not None:
        res['capRho'] = rho
    ctx = M.Ctx(lib_path, 15, res)
    x2 = DATA._stereo(DATA.audio(key))
    r = ctx.render(key, x2, 0.0, voice=True, stage=True)
    st = r['stage']
    core = st[:, SI['core_low32']].astype(np.int64) + (st[:, SI['core_high32']].astype(np.int64) << 32)
    bh = np.zeros(core.max() + 1); det = np.zeros_like(bh)
    bh[core] = st[:, SI['selected_h']]; det[core] = st[:, SI['band_delayed191']]
    np.savez_compressed(p, trace=np.asarray(r['voice'], float), bh=bh, det=det)
    print('rendered', key, flush=True)


def my_streams(key):
    z = np.load(CDIR / f'{label}_{key}.npz')
    return dict(trace=z['trace'], bh=z['bh'], det=z['det'])


def one_song(key):
    DATA.streams = my_streams
    sig = Sig(key); dur = LD.dur_of(key)
    segs, rf = LD.segments(key)
    act = act15(segs, rf['bz'], dur)
    truth = SATruth(key, sig.tc1, segs, act)
    cv = R.voices_core(sig)
    annotate(cv, segs)
    out = measure_row(cv, LAG, sig, truth, dur, segs)
    out['n_voices'] = len(cv)
    return key, out


def main():
    t0 = time.time()
    with mp.get_context('fork').Pool(10) as pool:
        pool.map(render_streams, SONGS)
        res = dict(pool.map(one_song, SONGS))
    R3r = r3_right(SONGS)
    g = lambda f, ks=SONGS: sum(res[k][f] for k in ks)
    summ = {}
    for name, ks in (('all10', SONGS), ('noT40', [k for k in SONGS if k != 'Track00040'])):
        r3 = r3_right(ks)
        summ[name] = dict(R3_right=r3, right_vs_R3_dB_sa=float(10 * np.log10(g('E_right_sa', ks) / r3)), right_vs_R3_dB_v6b=float(10 * np.log10(g('E_right_v6b', ks) / r3)),
                          wrong_sa_F=g('E_wrong_sa', ks) / r3, wrong_v6b_F=g('E_wrong_v6b', ks) / r3,
                          wrong_sa_M=g('E_wrong_sa', ks) / r3 * r3 / g('E_right_sa', ks))
    per = {}
    for k in SONGS:
        r3k = RAW_A['res'][k]['R3']['v6b']['E_right']
        per[k] = dict(right_dB=(float(10 * np.log10(res[k]['E_right_sa'] / r3k)) if r3k > 0 else None), wrong_sa_F=(res[k]['E_wrong_sa'] / r3k if r3k > 0 else None),
                      E_right_sa=res[k]['E_right_sa'], E_wrong_sa=res[k]['E_wrong_sa'])
    json.dump(dict(label=label, lib=lib_path, rho=rho, summary=summ, per_song=per, raw=res), open(Path('/home/ksysh/r3a-dev/plan16/F') / f'f_right_{label}.json', 'w'), default=float, indent=1)
    print(label, json.dumps(summ, default=float))
    print('secs', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()

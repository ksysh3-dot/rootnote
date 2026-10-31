"""Right-layer F on the 10 dev (V6) songs, trace-based exactly as plan16/V16A/right16b.py, for the A5 rows. The library is the diagnostic build A5/dbgsrc/F, whose trace
carries A = rendered amplitude (A c sigma after the slew limit), c = sigma = 1, so that la0/rows.py voices_core (amp = A c sigma) measures what is rendered.
usage: right_a5.py LABEL   (a5prows.ROWS parameters, diagnostic F library)"""
import sys, json, time, multiprocessing as mp
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/NF')
from pathlib import Path
label = sys.argv[1]
import a5prows as AR
import numpy as np
import dcommon as DC
from dcommon import *
import data as DATA
import research_core_metrics as M
import research_core_xcheck as X
from vb_quality.stage_capture import INDEX as SI

lib_path = str(AR.AC.LIB16B)
res_params = dict(AR.ROWS[label][2])
CDIR = Path('/home/ksysh/r3a-dev/plan16/S19/NF/cache'); CDIR.mkdir(exist_ok=True)
M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0)]


def render_streams(key):
    p = CDIR / f'{label}_{key}.npz'
    if p.exists():
        return
    ctx = M.Ctx(lib_path, 15, res_params)
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
    g = lambda f, ks=SONGS: sum(res[k][f] for k in ks)
    r3 = r3_right(SONGS)
    summ = dict(R3_right=r3, right_vs_R3_dB_sa=float(10 * np.log10(g('E_right_sa') / r3)), right_vs_R3_dB_v6b=float(10 * np.log10(g('E_right_v6b') / r3)),
                wrong_sa_F=g('E_wrong_sa') / r3, wrong_v6b_F=g('E_wrong_v6b') / r3)
    json.dump(dict(label=label, lib=lib_path, params=res_params, summary=dict(all10=summ), raw=res), open(Path('/home/ksysh/r3a-dev/plan16/S19/NF') / f'right_{label}.json', 'w'), default=float, indent=1)
    print(label, json.dumps(summ, default=float))
    print('secs', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()

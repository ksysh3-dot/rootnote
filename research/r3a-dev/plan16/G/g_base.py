"""core v1.5 baseline per song: silent wrong_sa (all causes), with and without t<4 s; right layer.  -> base_raw.json"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/G')
from gcommon import *
import multiprocessing as mp


def one(key):
    ctx = SongCtx(key, probe_nobass=False)
    Y = ctx.render(None)
    o = dict(key=key, nobass=ctx.nobass, sil=sil_energy(Y) / R3R, sil4=sil_energy(Y, T4) / R3R, right=right_energy(Y) / R3R, right4=right_energy(Y, T4) / R3R,
             cause=[En(Y[i]) / R3R for i in SIL_IDS], n_notes=int(len(ctx.segs)), nvoice=len(ctx.voices))
    print(key, o['sil'], o['sil4'], flush=True)
    return key, o


if __name__ == '__main__':
    with mp.get_context('fork').Pool(10) as pool:
        res = dict(pool.map(one, SONGS, chunksize=1))
    json.dump(res, open(G_DIR / 'base_raw.json', 'w'), default=float)
    print('sum sil', sum(r['sil'] for r in res.values()), 'sum sil4', sum(r['sil4'] for r in res.values()))

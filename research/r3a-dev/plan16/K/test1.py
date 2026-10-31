import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/K')
from kcommon import *
import multiprocessing as mp


def one(key):
    t0 = time.time()
    ctx = SongCtx(key)
    Y = ctx.render(None)
    y = Y[:, I_MIN:]
    e = lambda x: float(np.sum(x ** 2))
    return key, dict(drum=e(y[4]) / R3R, sil=e(y[3:8].sum(0)) / R3R, secs=time.time() - t0, init=ctx.secs_init, right=e(y[0] + y[1]))


if __name__ == '__main__':
    with mp.get_context('fork').Pool(10) as pool:
        res = pool.map(one, SONGS)
    for k, r in res:
        print(k, r)
    print('sum drum', sum(r['drum'] for k, r in res))

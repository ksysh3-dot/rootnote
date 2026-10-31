"""APP16 verification: V0 (algorithms 0-15 unchanged), E1 (16 == 15 + v1.6-b set), E2 (16 -> other restores v1.5), latency.
NEW = build_app16 (this tree), REF = build_app16c_ref (pre-change HEAD daf9bba). Slakh TRAIN excerpts and synthetic signals only."""
import sys, json, time
from pathlib import Path
HOME = Path.home()
H = HOME / 'r3-app/tools/pvb-harness'
sys.path.insert(0, str(H))
import numpy as np
import research_core_api as CA
import research_core_signals as S
import test_engine as T

NEW = CA.load(H / 'build_app16c/libpvbcapi.so')
REF = CA.load(HOME / 'r3a-dev/plan16/APP16/ref_wt/tools/pvb-harness/build_app16c_ref/libpvbcapi.so')
FS = 48000
V16B = dict(capRho=1.5, windowCreep=16, creepMode=2, betaMin=0.05, betaMax=0.1, psiSlew=0.03)
V16C = dict(V16B, layerHpHz=150, layerHpOrder=8, layerHpComp=1)

sigs = {
    'T01_10_4': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 4.0),
    'T20_0_4': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 4.0),
    'T60_36_5': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 5.0),
    'gated25_pink': S.stereo(S.gated_line(25.0)['noisy'])[:int(4 * FS)],
    'low_notes': S.stereo(S.low_notes()),
}


def run(lib, x, seq, block=256, params=None, trace=False, level=6.0, sr=FS):
    """seq: [(start_sample, algo)] sorted, first start 0; algo -1 = virtual bass off. params: kwargs for set_resultant
    applied right after creation (the research flow). Returns output, trace (or None), latency list per segment."""
    e = T.Engine(lib, sr, vb_on=1, vb_algo=max(seq[0][1], 0), vb_level_db=level, ramp_ms=0)
    if seq[0][1] < 0:
        e.set(vb_on=0)
    try:
        if params is not None:
            CA.set_resultant(lib, e, **params)
        hops = 0
        if trace:
            hops = int(len(x) * CA.CORE_FS / sr / CA.HOP) + 64
            CA.trace_enable(lib, e, hops)
        y = np.ascontiguousarray(x, np.float32).copy()
        cuts = sorted({0, len(y)} | {s for s, _ in seq if s < len(y)})
        lats = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            for s, al in seq:
                if s == a and a > 0:
                    if al < 0:
                        e.set(vb_on=0)
                    else:
                        e.set(vb_on=1, vb_algo=al)
            for i in range(a, b, block):
                blk = y[i:min(i + block, b)]
                lib.pvb_process(e.h, blk.ctypes.data_as(T.FP), len(blk))
            lats.append(int(lib.pvb_latency(e.h)))
        tr = CA.trace_copy(lib, e, hops * CA.SLOTS) if trace else None
    finally:
        e.close()
    return y, tr, lats


rows = []
ok_all = True


def rec(group, name, same, extra=''):
    global ok_all
    ok_all &= bool(same)
    rows.append((group, name, bool(same), extra))
    print(('PASS ' if same else 'FAIL ') + group, name, extra, flush=True)


def eq(a, b):
    return a.shape == b.shape and np.array_equal(a, b)


t0 = time.time()
# ---------------------------------------------------------------- V0: algorithms 0-15, NEW == REF
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(1.5 * FS)] if blk == 1 else x
        for a in range(0, 16):
            yn, tn, ln = run(NEW, xx, [(0, a)], blk, trace=(a == 15))
            yr, tr, lr = run(REF, xx, [(0, a)], blk, trace=(a == 15))
            same = eq(yn, yr) and (a != 15 or eq(tn, tr)) and ln == lr
            rec('V0', f'algo{a} {nm} blk{blk}', same, f'lat={ln[0]}' if not same else '')
print('V0 single-algorithm time', time.time() - t0, flush=True)

# switch sequences (blocks 256 / 480); switch points on block boundaries by construction (cuts split blocks)
seqs = {
    '15-6-15': [(0, 15), (FS * 1, 6), (FS * 2, 15)],
    '15-4-15': [(0, 15), (FS * 1, 4), (FS * 2, 15)],
    '15-off-15': [(0, 15), (FS * 1, -1), (FS * 2, 15)],
    '6-15-14-15-3': [(0, 6), (24000, 15), (FS * 1, 14), (FS * 2, 15), (FS * 3, 3)],
    '15-11-12-13-15': [(0, 15), (FS * 1, 11), (FS * 2, 12), (FS * 3, 13), (FS * 4 - 5000, 15)],
}
for nm in ('T01_10_4', 'T60_36_5', 'low_notes'):
    x = sigs[nm]
    for blk in (256, 480):
        for sn, sq in seqs.items():
            sq = [(s, a) for s, a in sq if s < len(x)]
            yn, tn, ln = run(NEW, x, sq, blk, trace=True)
            yr, tr, lr = run(REF, x, sq, blk, trace=True)
            rec('V0sw', f'{sn} {nm} blk{blk}', eq(yn, yr) and eq(tn, tr) and ln == lr)
# research flow: select 15, then pvb_set_resultant (v1.5 defaults, a research set, and the v1.6-b set), also across a switch
research_sets = {'defaults': {}, 'v16b': V16B, 'v16c': V16C, 'research2': dict(capRho=2.0, windowCreep=8, creepMode=1, betaMin=.1, betaMax=.5, kappa=1.2, nMin=40)}
for nm in ('T01_10_4', 'T60_36_5', 'gated25_pink'):
    x = sigs[nm]
    for rn, rp in research_sets.items():
        for blk in (256, 1, 480):
            xx = x[:int(1.5 * FS)] if blk == 1 else x
            yn, tn, ln = run(NEW, xx, [(0, 15)], blk, params=rp, trace=True)
            yr, tr, lr = run(REF, xx, [(0, 15)], blk, params=rp, trace=True)
            rec('V0res', f'15+set[{rn}] {nm} blk{blk}', eq(yn, yr) and eq(tn, tr) and ln == lr)
        if blk and rn != 'defaults':
            sq = [(0, 15), (FS * 1, 6), (FS * 2, 15)]
            sq = [(s, a) for s, a in sq if s < len(x)]
            yn, tn, ln = run(NEW, x, sq, 256, params=rp, trace=True)
            yr, tr, lr = run(REF, x, sq, 256, params=rp, trace=True)
            rec('V0res', f'15+set[{rn}] then 15-6-15 {nm}', eq(yn, yr) and eq(tn, tr))
print('V0 done', time.time() - t0, flush=True)

# ---------------------------------------------------------------- E1: 16 == 15 + set(v1.6-b)
for nm, x in sigs.items():
    for blk in (256, 1, 480):
        xx = x[:int(1.5 * FS)] if blk == 1 else x
        y16, t16, l16 = run(NEW, xx, [(0, 16)], blk, trace=True)
        y15, t15, l15 = run(NEW, xx, [(0, 15)], blk, params=V16C, trace=True)
        y15r, t15r, l15r = run(REF, xx, [(0, 15)], blk, params=V16C, trace=True)
        y15d, _, _ = run(NEW, xx, [(0, 15)], blk, trace=True)
        y15b, _, _ = run(NEW, xx, [(0, 15)], blk, params=V16B, trace=True)
        rec('E1', f'16 vs NEW15+set {nm} blk{blk}', eq(y16, y15) and eq(t16, t15) and l16 == l15, f'lat {l16} {l15}')
        rec('E1', f'16 vs REF15+set {nm} blk{blk}', eq(y16, y15r) and eq(t16, t15r) and l16 == l15r)
        # the parameters matter: 16 differs from plain 15 (otherwise the comparison would be vacuous)
        if blk == 256:
            rec('E1', f'16 != 15+set(v1.6-b) (HP really on) {nm}', not eq(y16, y15b), f'max|d|={float(np.max(np.abs(y16 - y15b))):.3g}')
            rec('E1', f'16 != plain 15 (sanity) {nm}', not eq(y16, y15d), f'max|d|={float(np.max(np.abs(y16 - y15d))):.3g}')
# 16 reached through a switch == 15 + set reached through the same switch
for nm in ('T01_10_4', 'T60_36_5'):
    x = sigs[nm]
    a, _, _ = run(NEW, x, [(0, 6), (FS, 16)], 256, trace=True)
    b, _, _ = run(NEW, x, [(0, 6), (FS, 15)], 256, params=V16C, trace=True)
    rec('E1sw', f'6->16 vs 6->15+set {nm}', eq(a, b))
    a, _, _ = run(NEW, x, [(0, 4), (FS, 16), (FS * 2, 16)], 256, trace=True)
    b, _, _ = run(NEW, x, [(0, 4), (FS, 15)], 256, params=V16C, trace=True)
    rec('E1sw', f'4->16(->16) vs 4->15+set {nm}', eq(a, b))

# ---------------------------------------------------------------- E2: 16 -> other restores the v1.5 defaults
SETTLE = int(0.6 * FS)
for nm in ('T01_10_4', 'T60_36_5', 'low_notes'):
    x = sigs[nm]
    for blk in (256, 480):
        for mid, label in ((None, '16-15'), (4, '16-4-15'), (6, '16-6-15'), (-1, '16-off-15')):
            t1 = FS
            if mid is None:
                sa = [(0, 16), (t1, 15)]; sb = [(0, 6), (t1, 15)]; tcmp = t1
            else:
                sa = [(0, 16), (t1, mid), (t1 + 12000, 15)]; sb = [(0, 6), (t1, mid), (t1 + 12000, 15)]; tcmp = t1 + 12000
            sa = [(s, a) for s, a in sa if s < len(x)]; sb = [(s, a) for s, a in sb if s < len(x)]
            ya, ta, la = run(NEW, x, sa, blk, trace=True)
            yb, tb, lb = run(NEW, x, sb, blk, trace=True)
            yr, trr, lrr = run(REF, x, sb, blk, trace=True)
            # after the switch fade the module starts clean with the defaults in both runs
            seg = slice(tcmp + SETTLE, None)
            same = eq(ya[seg], yb[seg]) and eq(yb[seg], yr[seg])
            first = int(np.argmax(np.any(ya != yb, axis=1))) if not eq(ya, yb) else -1
            rec('E2', f'{label} {nm} blk{blk}', same and la[-1] == lb[-1], f'whole-signal equal={eq(ya, yb)} first diff sample={first} (switch {tcmp})')
    # strongest form: a fresh 15 engine fed the audio from the switch point equals 16 -> 15 after the same switch
# defaults actually restored: 16 -> 15 differs from 16 held (sanity) and from 15+v16b on the same tail
x = sigs['T60_36_5']
ya, _, _ = run(NEW, x, [(0, 16), (FS, 15)], 256)
yh, _, _ = run(NEW, x, [(0, 16)], 256)
yc, _, _ = run(NEW, x, [(0, 6), (FS, 15)], 256, params=V16C)
rec('E2', 'sanity: 16->15 tail differs from 16 held', not eq(ya[FS + SETTLE:], yh[FS + SETTLE:]))
rec('E2', 'sanity: 16->15 tail differs from 15 with v1.6-b set', not eq(ya[FS + SETTLE:], yc[FS + SETTLE:]))

# ---------------------------------------------------------------- latency
for sr in (44100, 48000):
    ls = {}
    for a in (6, 15, 16):
        e = T.Engine(NEW, sr, vb_on=1, vb_algo=a, ramp_ms=0)
        ls[a] = int(NEW.pvb_latency(e.h)); e.close()
    er = T.Engine(REF, sr, vb_on=1, vb_algo=15, ramp_ms=0); l15r = int(REF.pvb_latency(er.h)); er.close()
    rec('LAT', f'sr {sr}: P1 {ls[6]} v15 {ls[15]} v16 {ls[16]} ref15 {l15r}', ls[16] == ls[15] == ls[6] == l15r)


print('TOTAL', len(rows), 'rows; ALL PASS' if ok_all else 'SOME FAIL', 'time', time.time() - t0)
json.dump(rows, open(HOME / 'r3a-dev/plan16/APP16/v0_app16c.json', 'w'))

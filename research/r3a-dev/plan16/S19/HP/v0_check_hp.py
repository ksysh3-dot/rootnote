"""V0 for 19.7 (params 20-22). HEAD library (19 params) vs the 19.7 build:
 A. params 20-22 at 0 / omitted (19, 20, 21, 22 values; order 4 and 8, comp 0 and 1 with layerHpHz = 0) are bit identical to HEAD (output + 22-field trace), several signals, block sizes 256 / 1 / 480, for v1.5 params, v1.6-b params and the P1 algo (6).
 B. layerHpHz > 0 changes the output; comp 0 leaves the whole 22-field trace identical to HEAD, comp 1 changes only psi_2 / psi_3 (fields 18, 19).
 C. refused: layerHpHz in (0, 20) or > 1000, order 6, comp 2, NaN."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/HP')
import numpy as np
import hpcommon as H
import research_core_signals as S

lh = H.CA.load(str(H.LIB_HEAD)); l19 = H.CA.load(str(H.LIB19))
sigs = {
    'logoff_37_49': S.load_excerpt(S.LOGOFF, 37.0, 12.0),
    'T60_36_48': S.load_excerpt(S.SLAKH_TRAIN / 'Track00060' / 'mix.flac', 36.0, 12.0),
    'T01_10_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00001' / 'mix.flac', 10.0, 8.0),
    'T20_0_8': S.load_excerpt(S.SLAKH_TRAIN / 'Track00020' / 'mix.flac', 0.0, 8.0),
}
sg = S.gated_line(25.0)
sigs['gated25_pink'] = S.stereo(sg['noisy'])[:int(8 * 48000)]
sigs['low_notes'] = S.stereo(S.low_notes())
okA = okB1 = okB2 = True
rows = []
for pname, prm in (('v15', H.V15), ('v16b', H.B3P2)):
    for nm, x in sigs.items():
        for blk in (256, 1, 480):
            xx = x[:int(2.5 * 48000)] if blk == 1 else x
            y0, t0, _ = H.render(lh, xx, H.vec(prm, 19), block=blk)
            for tag, extra in (('19vals', None), ('20vals_0', dict(layerHpHz=0)), ('21vals_0_4', dict(layerHpHz=0, layerHpOrder=4)),
                               ('22vals_0_8_0', dict(layerHpHz=0)), ('22vals_0_4_1', dict(layerHpHz=0, layerHpOrder=4, layerHpComp=1)),
                               ('22vals_0_8_1', dict(layerHpHz=0, layerHpComp=1))):
                n = {'19vals': 19, '20vals_0': 20, '21vals_0_4': 21}.get(tag, 22)
                y1, t1, _ = H.render(l19, xx, H.vec(dict(prm, **(extra or {})), n), block=blk)
                same = bool(np.array_equal(y0, y1) and np.array_equal(t0, t1)); okA &= same
                rows.append(('A', pname, nm, blk, tag, same, float(np.max(np.abs(y0 - y1)))))
                print(rows[-1], flush=True)
        if pname == 'v16b':
            xx = x
            y0, t0, _ = H.render(lh, xx, H.vec(prm, 19))
            for tag, hz, order, comp in (('bw8_150c0', 150, 8, 0), ('bw8_150c1', 150, 8, 1), ('bw4_135c1', 135, 4, 1)):
                y1, t1, _ = H.render(l19, xx, H.vec(dict(prm, layerHpHz=hz, layerHpOrder=order, layerHpComp=comp)))
                keep = [i for i in range(t0.shape[1]) if i not in (18, 19)]
                idt_all = bool(np.array_equal(t0, t1)); idt_keep = bool(np.array_equal(t0[:, keep], t1[:, keep]))
                differs = not np.array_equal(y0, y1)
                if comp == 0:
                    okB1 &= idt_all
                okB2 &= idt_keep and differs
                rows.append(('B', nm, tag, differs, idt_all, idt_keep)); print(rows[-1], flush=True)
# P1 algo unaffected
x = sigs['T60_36_48'][:int(4 * 48000)]
for blk in (256, 480):
    ya, _, _ = H.render(lh, x, None, algo=6, block=blk, trace=False); yb, _, _ = H.render(l19, x, None, algo=6, block=blk, trace=False)
    s = bool(np.array_equal(ya, yb)); okA &= s; rows.append(('A_p1', blk, s)); print(rows[-1])
e = H.T.Engine(l19, 48000, vb_on=1, vb_algo=15, ramp_ms=0)
ref = {}
for tag, kw in (('hz10', dict(layerHpHz=10)), ('hz19.9', dict(layerHpHz=19.9)), ('hz1001', dict(layerHpHz=1001)), ('order6', dict(layerHpHz=150, layerHpOrder=6)),
                ('comp2', dict(layerHpHz=150, layerHpComp=2)), ('hzNaN', dict(layerHpHz=float('nan'))), ('ok150_8', dict(layerHpHz=150)), ('ok20_4', dict(layerHpHz=20, layerHpOrder=4)),
                ('ok1000_4', dict(layerHpHz=1000, layerHpOrder=4)), ('off', dict(layerHpHz=0)), ('23vals', None)):
    v = H.vec(dict(H.B3P2, **(kw or {})))
    if kw is None:
        v = np.append(v, 0.0)
    ref[tag] = H.try_vec(l19, e, v); print('refuse test', tag, '->', ref[tag])
e.close()
okC = all(ref[k] == 0 for k in ('hz10', 'hz19.9', 'hz1001', 'order6', 'comp2', 'hzNaN', '23vals')) and all(ref[k] == 1 for k in ('ok150_8', 'ok20_4', 'ok1000_4', 'off'))
print('V0 A (params 20-22 off = HEAD) ALL BIT-IDENTICAL:', okA)
print('V0 B1 (comp 0 -> full trace = HEAD):', okB1, ' B2 (comp 1: only psi fields differ, output differs):', okB2)
print('V0 C (validation):', okC)
json.dump(dict(rows=rows, okA=okA, okB1=okB1, okB2=okB2, okC=okC, refuse=ref), open(H.HP_DIR / 'v0_check_hp.json', 'w'))

"""E2 exact rule: first sample after the switch from which 16->X->15 equals 6->X->15 (and REF) for the rest of the signal; and
the latency after processing (a latency read before the first block is not meaningful)."""
import sys
sys.argv = ['x']
exec(open('/home/ksysh/r3a-dev/plan16/APP16/v0_app16c.py').read().split('rows = []')[0])
for nm in ('T01_10_4', 'T60_36_5', 'low_notes'):
    x = sigs[nm]
    for label, sa, sb, tsw in (('16-15', [(0, 16), (FS, 15)], [(0, 6), (FS, 15)], FS),
                               ('16-4-15', [(0, 16), (FS, 4), (FS + 12000, 15)], [(0, 6), (FS, 4), (FS + 12000, 15)], FS + 12000)):
        ya, _, _ = run(NEW, x, sa, 256, trace=True)
        yb, _, _ = run(NEW, x, sb, 256, trace=True)
        yr, _, _ = run(REF, x, sb, 256, trace=True)
        for tag, y2 in (('NEW 6-path', yb), ('REF 6-path', yr)):
            d = np.any(ya != y2, axis=1)
            idx = np.nonzero(d[tsw:])[0]
            last = int(idx[-1]) if len(idx) else -1
            print(nm, label, tag, 'last differing sample after switch:', last, f'({1000 * last / FS:.1f} ms)' if last >= 0 else '(none: identical from the switch)')
for sr in (44100, 48000):
    out = {}
    for a in (6, 15, 16):
        e = T.Engine(NEW, sr, vb_on=1, vb_algo=a, ramp_ms=0)
        e.process(np.zeros((4096, 2), np.float32)); out[a] = int(NEW.pvb_latency(e.h)); e.close()
    e = T.Engine(REF, sr, vb_on=1, vb_algo=15, ramp_ms=0); e.process(np.zeros((4096, 2), np.float32)); r = int(REF.pvb_latency(e.h)); e.close()
    print('latency sr', sr, out, 'ref15', r, 'EQUAL' if out[16] == out[15] == out[6] == r else 'DIFFER')

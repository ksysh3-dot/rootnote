"""V3g: why does the 35/45 Hz voice need ~10 hops from first appearance to ON? Print the voice trace around the onset."""
import sys
sys.path.insert(0, '.'); sys.path.insert(0, 'study')
import numpy as np
import research_core_xcheck as X
cand = X.open_lib(X.CAND)
x = X.low_notes_sig()
r = X.render(cand, x, 15, 0.0, out_db=-5.0, cfg=X.CFG['A'], trace=True)
d, hop, tc = X.hops_of(r['trace'])
tr = r['trace'].reshape(-1, 8, 22)
for f0, a in ((35.0, 0.3), (45.0, 2.8)):
    print(f'--- note {f0} Hz starting {a} s: rows of voices with f_track or f_osc within 12 % of the fundamental')
    first = None
    for h in range(len(tc)):
        if tc[h] < a - 0.05 or tc[h] > a + 0.25:
            continue
        for s in range(8):
            row = tr[h, s]
            if row[X.F_STATE] == 0:
                continue
            f = row[X.F_FTR] if row[X.F_FTR] > 0 else row[X.F_FOSC]
            if abs(f - f0) <= .12 * f0:
                if first is None:
                    first = h
                print(f'  hop+{h-first:2d} tc={tc[h]-a:+.3f}s id={int(row[1])} trk={int(row[2])} st={int(row[3])} coast={int(row[4])} f_trk={row[5]:6.2f} f_osc={row[6]:6.2f} A={row[8]:.4f} c={row[9]:.2f} snr={row[12]:5.1f} prom={int(row[13])} sub={int(row[16])}')

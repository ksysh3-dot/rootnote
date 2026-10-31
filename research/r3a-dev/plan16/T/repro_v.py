"""re-run V's own one_song (unmodified import) for T26/T24 and print cause-1 energy / R3R"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import v_run as V
from dcommon import *
R3R = r3_right(SONGS)
for k in ('Track00026', 'Track00024'):
    key, out, arr = V.one_song(k)
    print(f'V one_song {k}: E_sil/R3R {out["E_sil"] / R3R:.5f}  cause1 {out["E_cause"][0] / R3R:.5f}  (spec 16.14: T26 0.0516, T24 0.0146)  nobass {out["nobass"]}', flush=True)

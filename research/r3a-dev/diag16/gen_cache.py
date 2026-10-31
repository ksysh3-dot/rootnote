import sys, time
import common16 as C
for n in sys.argv[1:]:
    t = time.time()
    tr = C.get_core(n); print(n, 'core', tr.shape, round(time.time() - t, 1), flush=True)
    t = time.time()
    tc1, ts = C.get_p1(n); print(n, 'p1', ts.shape, round(time.time() - t, 1), flush=True)

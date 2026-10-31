import sys, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import guards as G
th = G.th_grid()[0]
for key in G.BASE_KEYS:
    t0 = time.time()
    try:
        a = G.guard_metrics(key, None)
        b = G.guard_metrics(key, th)
        print(key, round(time.time() - t0, 1), '\n  core', a, '\n  det ', b, flush=True)
    except Exception as ex:
        import traceback; traceback.print_exc()
        print(key, 'FAIL', ex)

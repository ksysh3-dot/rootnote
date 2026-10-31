"""Cap activity rate: acted / evaluated, where evaluated = voice-hops of LS sets with >= 2 voices (a single voice is its own block, cap not evaluated).
10 dev songs (0-30 s) + LOGOFF 37-49 s, rho 1.5 / 2 / 3, voice-hop counts from the library's research counters."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F')
import numpy as np
import fcommon as FC
import data as DATA
import ladder as LD
import research_core_signals as S
lib = FC.load(str(FC.LIB151))
keys = list(LD.SONGS) + ['logoff_37_49']
out = {}
for rho in (1.5, 2.0, 3.0):
    tot = np.zeros(2)
    for k in keys:
        x = DATA._stereo(DATA.audio(k))
        FC.cap_stats(lib)
        FC.render(lib, x, FC.make_params(rho), trace=False)
        st = FC.cap_stats(lib)
        out[f'{rho}|{k}'] = [float(st[0]), float(st[1])]
        if k != 'logoff_37_49':
            tot += st
        print(rho, k, st, f'{st[1] / max(st[0], 1):.3f}', flush=True)
    out[f'{rho}|dev10'] = [float(tot[0]), float(tot[1])]
    print(rho, 'dev10 pooled', tot, f'{tot[1] / tot[0]:.4f}', flush=True)
json.dump(out, open(FC.F_DIR / 'f_caprate.json', 'w'), indent=1)

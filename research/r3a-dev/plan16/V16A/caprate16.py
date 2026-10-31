"""Cap activity rate (acted / evaluated; evaluated = voice-hops of LS sets with >= 2 voices) for the rows with capRho > 0.
10 dev songs (0-30 s) + LOGOFF 37-49 s. usage: caprate16.py rho:creep ..."""
import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import data as DATA
import ladder as LD
lib = VC.load(str(VC.LIB16A))
keys = list(LD.SONGS) + ['logoff_37_49']
out = {}
for spec in sys.argv[1:]:
    rho, cr = (float(v) for v in spec.split(':'))
    tot = np.zeros(2)
    for k in keys:
        x = DATA._stereo(DATA.audio(k))
        VC.cap_stats(lib)
        VC.render(lib, x, VC.make_params(rho, cr), trace=False)
        st = VC.cap_stats(lib)
        out[f'{spec}|{k}'] = [float(st[0]), float(st[1])]
        if k != 'logoff_37_49':
            tot += st
    out[f'{spec}|dev10'] = [float(tot[0]), float(tot[1])]
    print(spec, 'dev10 pooled evaluated/acted', tot, f'rate {tot[1] / max(tot[0], 1):.4f}', 'LOGOFF', out[f'{spec}|logoff_37_49'], flush=True)
json.dump(out, open(VC.V_DIR / 'caprate16.json', 'w'), indent=1)

"""Diagnostic (information only): what the voices do around the LOGOFF 4.12 s hit (render time 7.12 s), v1.5 vs rho 1.5 / 3."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F')
import numpy as np
import fcommon as FC
import research_core_signals as S
import research_core_api as CA
lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
l15 = FC.load(str(FC.LIB15)); l151 = FC.load(str(FC.LIB151))
res = {}
for nm, lib, pv in (('v15', l15, FC.make_params(None)), ('rho1.5', l151, FC.make_params(1.5)), ('rho3', l151, FC.make_params(3.0))):
    FC.cap_stats(l151)
    y, tr, lat = FC.render(lib, lg, pv, vb_level_db=0.0, out_db=-5.0)
    res[nm] = CA.trace_dict(tr)
    print(nm, 'cap stats', FC.cap_stats(l151) if lib is l151 else None)
tc, _ = CA.hop_time(res['v15']['hop'][:, 0])
# input time of the hit = 3.0 + 4.12 (render time within excerpt)
c = 3.0 + 4.12
sel = np.flatnonzero((tc > c - .06) & (tc < c + .08))
np.set_printoptions(linewidth=250, precision=3, suppress=True)
for h in sel[::3]:
    line = f't={tc[h]:.3f} '
    for nm in res:
        d = res[nm]
        on = [(int(s)) for s in range(8) if d['state'][h, s] >= 1]
        line += f'| {nm}: ' + ' '.join(f"[f{d['f_osc'][h, s]:.0f} s{int(d['state'][h, s])} A{d['A'][h, s]:.3f} snr{d['snr_db'][h, s]:.0f} N{int(d['Np'][h, s])}]" for s in on)
    print(line)

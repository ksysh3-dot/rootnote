"""Report-only diagnostic (brief A1'): the 35 Hz synthetic note of V3g (on [0.3, 2.3) s) in the first 300 ms after onset: N_v (trace Np), N_J held / applied (debug library:
per-hop log inside solveLs, NOT part of the diff), SNR, state and the ON-loss hops over the whole note, for v1.5, A1 8 unconditional (+A2 1.5, the reference row of 18.5)
and the A1' rows. Debug library = build_dbg.sh (same sources as build_core16b + one log line)."""
import sys, json, ctypes as C
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')
import numpy as np
import vcommon as VC
import research_core_signals as S

lib = VC.load('/home/ksysh/r3a-dev/plan16/V16A/dbgsrc/libpvbcapi_dbg.so')
lib.a1p_dbg_n.restype = C.c_int
lib.a1p_dbg_copy.argtypes = [C.POINTER(C.c_double)]
x = S.stereo(S.low_notes())
F0, A0, B0 = 35.0, 0.3, 2.3
ROWS = [('v1.5', (0, 0, 0)), ('A1 8 uncond (+A2)', (1.5, 8, 0)), ('A1p (i) 8', (1.5, 8, 1)), ('A1p (ii) 8', (1.5, 8, 2)), ('A1p (i) 16', (1.5, 16, 1)), ('A1p (ii) 16', (1.5, 16, 2))]
res = {}
for name, par in ROWS:
    n = lib.a1p_dbg_n(); buf = (C.c_double * (6 * max(n, 1)))(); lib.a1p_dbg_copy(buf)   # clear
    y, tr, _ = VC.render(lib, x, VC.make_params(*par))
    n = lib.a1p_dbg_n(); buf = (C.c_double * (6 * max(n, 1)))(); lib.a1p_dbg_copy(buf)
    dbg = np.array(buf[:6 * n]).reshape(-1, 6)
    t = VC.CA.trace_dict(tr)
    tc, _ = VC.CA.hop_time(t['hop'][:, 0])
    nh = len(tc)
    near = (np.abs(t['f_osc'] - F0) <= .05 * F0) & (t['state'] > 0)
    on = ((t['state'] == 2) & near)
    # per hop: the slot of the voice at the note (ON preferred, else any)
    slot = np.where(on.any(1), on.argmax(1), np.where(near.any(1), near.argmax(1), -1))
    # join N_J log by hop number (offset chosen by the larger agreement N_J == Np on hops where the voice is the only one and no stage 2 reduction)
    djh = {int(r[0]): r for r in dbg}
    best = None
    for off in (0, -1, 1):
        m = 0
        for h in range(nh):
            r = djh.get((int(t['hop'][h, 0]) - 383) // 16 + 1 + off)
            if r is not None and slot[h] >= 0 and r[5] == 1 and int(t['Np'][h, slot[h]]) == int(r[2]): m += 1
        best = (m, off) if best is None or m > best[0] else best
    off = best[1]
    sel = np.flatnonzero((tc >= A0 - .01) & (tc <= A0 + .30))
    rows = []
    for h in sel:
        s = slot[h]; r = djh.get((int(t['hop'][h, 0]) - 383) // 16 + 1 + off)
        rows.append(dict(ms=round(float((tc[h] - A0) * 1000), 1), state=int(t['state'][h, s]) if s >= 0 else -1, Nv=int(t['Np'][h, s]) if s >= 0 else -1,
                         snr=round(float(t['snr_db'][h, s]), 1) if s >= 0 else None, A=round(float(t['A'][h, s]), 4) if s >= 0 else None,
                         NJ_held=int(r[1]) if r is not None else None, NJ=int(r[2]) if r is not None else None, nv=int(r[5]) if r is not None else None,
                         fallJ=int(r[4]) if r is not None else None))
    w = np.flatnonzero((tc >= A0) & (tc <= B0))
    onw = on.any(1)[w]; first = int(np.argmax(onw)) if onw.any() else 0
    noREL = int((~onw[first:]).sum())
    firstON_ms = float((tc[w][first] - A0) * 1000) if onw.any() else None
    res[name] = dict(par=par, join_offset=off, join_match=best[0], first_ON_ms=firstON_ms, noREL_hops=noREL, rows=rows)
    print(f'\n== {name} {par} join offset {off} (matches {best[0]}), first ON {firstON_ms:.1f} ms after onset, hops without ON after first ON: {noREL}', flush=True)
    print('  ms    st   Nv   NJheld   NJ   nvox  snr     A     fallJ')
    for r in rows[::2]:
        print(f"  {r['ms']:6.1f} {r['state']:3d} {r['Nv']:4d} {str(r['NJ_held']):>6s} {str(r['NJ']):>5s} {str(r['nv']):>4s} {str(r['snr']):>6s} {str(r['A']):>8s} {str(r['fallJ']):>3s}")
json.dump(res, open(VC.V_DIR / 'diag35.json', 'w'), indent=1)

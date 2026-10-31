"""gate16 E7: the 13.3 V7d redefinition on LOGOFF (37-49 s excerpt, hits at 4.12 / 4.73 s of the 40 s+ window i.e. render time 3.0 + hit).
Old: 150-600 Hz layer energy within +-50 ms (dB).  New (13.3): burst = E(+-50 ms) - reference, reference = median of the 10 ms box energies over [-300,-100] U [+100,+300] ms.
The text does not say how a 100 ms energy and a 10 ms box energy are put on one scale, so three readings are computed:
  R1: 100 ms energy minus 10x ... i.e. 10log10(E100/10) - 10log10(median box)   (power per 10 ms vs power per 10 ms)
  R2: 10log10(E100) - 10log10(median box)                                       (literal: unnormalised)
  R3: peak 10 ms box inside +-50 ms - median box
for P1 (algo 6, reference build) and the v1.5 core (algo 15, build_core).  Limit (13.3): core <= max(+3 dB, P1 + 1 dB)."""
import sys
import numpy as np
import research_core_metrics as M
import research_core_signals as S
import research_p1plus as RP

FS = 48000


def burst(lay, c, mode):
    Lb = M.bandpass(lay, 150, 600)
    box = int(.010 * FS)
    def boxE(t0):
        i = int(round(t0 * FS)); return float(np.sum(Lb[i:i + box] ** 2))
    ref_t = list(np.arange(c - .300, c - .100, .010)) + list(np.arange(c + .100, c + .300, .010))
    ref = np.median([boxE(t) for t in ref_t])
    i0, i1 = int((c - .05) * FS), int((c + .05) * FS)
    E100 = float(np.sum(Lb[i0:i1] ** 2))
    bx = [boxE(t) for t in np.arange(c - .05, c + .05, .010)]
    old = 10 * np.log10(E100 + 1e-30)
    if mode == 'R1': new = 10 * np.log10(E100 / 10 + 1e-30) - 10 * np.log10(ref + 1e-30)
    elif mode == 'R2': new = 10 * np.log10(E100 + 1e-30) - 10 * np.log10(ref + 1e-30)
    else: new = 10 * np.log10(max(bx) + 1e-30) - 10 * np.log10(ref + 1e-30)
    return old, new, 10 * np.log10(ref + 1e-30)


def main():
    lg = S.load_excerpt(S.LOGOFF, 37.0, 12.0)
    out = {}
    for label, path, algo in (('P1', str(M.REF_LIB), 6), ('core v1.5', str(M.HOME / 'r3-work/tools/pvb-harness/build_core/libpvbcapi.so'), 15)):
        ctx = M.Ctx(path, algo, dict(voicing=0, ampSource=0) if algo == 15 else None)
        r0 = ctx.render('lg', lg, 0.0); rd = ctx.render('lg', lg, -120.0)
        lay = M.layer_of(r0, rd)
        for hit in (4.12, 4.73):
            c = 3.0 + hit
            for mode in ('R1', 'R2', 'R3'):
                out[(label, hit, mode)] = burst(lay, c, mode)
    for hit in (4.12, 4.73):
        print(f'--- hit {hit} s')
        for mode in ('R1', 'R2', 'R3'):
            p1 = out[('P1', hit, mode)]; co = out[('core v1.5', hit, mode)]
            lim = max(3.0, p1[1] + 1.0)
            print(f'  {mode}: P1 old {p1[0]:7.2f} dB / burst {p1[1]:7.2f} dB (ref box {p1[2]:7.2f})   core old {co[0]:7.2f} dB / burst {co[1]:7.2f} dB (ref box {co[2]:7.2f})   '
                  f'limit max(3, P1+1) = {lim:6.2f} -> core {"PASS" if co[1] <= lim else "FAIL"} by {co[1]-lim:+.2f} dB;  old criterion core - P1 = {co[0]-p1[0]:+.2f} dB')


if __name__ == '__main__':
    main()

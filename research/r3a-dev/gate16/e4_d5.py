"""gate16 E4: D5 evidence (b') on the V3g low notes. bh 128 ms magnitude spectrum (the one the core uses for SNR: Hann 384 of bhRing_, FFT 2048,
bins loBin=18 .. hiBin=137 = 25..200 Hz), k in 1..4 within max(4 Hz, 3 % k f), local maximum (>= left, > right), compared with the median of +-27 bins
(two edge conventions: 'clamp' = like the src code (repeat the edge bin), 'trunc' = truncate the neighbourhood at the grid edge)."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import streams16 as S

NFFT, N = 2048, 384
BIN = 3000.0 / NFFT
win = np.hanning(N + 1)[:-1]
LO, HI = 18, 137            # loBin_, hiBin_ (first bin >= 25 Hz; first bin >= 200 Hz exclusive)


def bh_mag(bh, ih):
    s0 = ih - (N - 1)
    fr = bh[s0:s0 + N] * win
    return np.abs(np.fft.rfft(fr, NFFT))[LO:HI]


def bprime(mag, f, edge):
    """returns (best over-median dB over k=1..4 and per-k list) for the voice frequency f"""
    out = []
    nb = len(mag)
    for k in range(1, 5):
        fk = k * f; tol = max(4.0, .03 * fk)
        b0 = int(np.floor((fk - tol) / BIN)) - LO; b1 = int(np.ceil((fk + tol) / BIN)) - LO
        best = None
        for b in range(max(b0, 1), min(b1, nb - 2) + 1):
            if mag[b] >= mag[b - 1] and mag[b] > mag[b + 1]:
                if edge == 'clamp':
                    med = np.median(mag[np.clip(np.arange(b - 27, b + 28), 0, nb - 1)])
                else:
                    med = np.median(mag[max(0, b - 27):min(nb, b + 28)])
                ov = 20 * np.log10(mag[b] / (med + 1e-20))
                best = ov if best is None else max(best, ov)
        out.append(best)
    vals = [v for v in out if v is not None]
    return (max(vals) if vals else None), out


def main():
    x = X.low_notes_sig()
    s = S.get('lowgate', x)
    d, hop, tc = X.hops_of(s['trace']); raw = np.asarray(s['trace']).reshape(-1, 8, 22)
    bh = s['bh']
    for f0, a in ((35.0, 0.3), (45.0, 2.8)):
        print(f'\n===== note {f0:.0f} Hz starting {a} s')
        first = None
        for h in range(len(tc)):
            if tc[h] < a - 0.06 or tc[h] > a + 0.12: continue
            vo = [j for j in range(8) if d['state'][h][j] > 0 and (abs(raw[h, j, X.F_FTR] - f0) <= .12 * f0 or abs(raw[h, j, X.F_FOSC] - f0) <= .12 * f0)]
            if not vo: continue
            if first is None: first = h
            mag = bh_mag(bh, int(hop[h]))
            for j in vo:
                f = raw[h, j, X.F_FTR] if raw[h, j, X.F_FTR] > 0 else raw[h, j, X.F_FOSC]
                bc, perk_c = bprime(mag, f, 'clamp'); bt, perk_t = bprime(mag, f, 'trunc')
                fmt = lambda v: ' none' if v is None else f'{v:5.1f}'
                print(f'hop {h-first:+3d} tc {1000*(tc[h]-a):+6.1f} ms  voice {int(d["voice"][h][j])} st {int(d["state"][h][j])} f_trk {f:5.1f} SNR {d["snr"][h][j]:5.1f} dB '
                      f'engine-prom {int(raw[h, j, X.F_PROM])}  (b\') best over-median dB: clamp {fmt(bc)} trunc {fmt(bt)}  per-k(clamp) ' + ' '.join(fmt(v) for v in perk_c))


if __name__ == '__main__':
    main()

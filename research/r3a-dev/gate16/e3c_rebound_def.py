"""gate16 E3c: sensitivity of the V3h.rebound statistic to its window and definition (13.3: 'min of A*c within 0-80 ms after the note end, then the rise after it, median over
notes <= 6 dB').  Uses the emulation of e3_d4 for the A series of the v1.5 core ('base') and of the v1.6 D4 variants, and prints per-statistic medians.
Definitions: W50/W80 = max after the min / min with the min searched in 0..50 / 0..80 ms (Q9 and 13.3);  W120;  RERISE = (max over 0..120 ms of A after its first
crossing below -20 dB re the pre-end level) in dB above that -20 dB level (0 if it never re-rises)."""
import numpy as np
import e3_d4 as E
import proxy16 as PX

tc, st, d = E.tc, E.st, E.d


def series(scale, i, lo=-0.045, hi=0.13):
    t_e = i * PX.PER + PX.STEP_DUR; f0 = PX.STEP_NOTES[i]
    hs = np.flatnonzero((tc >= t_e + lo) & (tc <= t_e + hi)); ser = []
    for h in hs:
        near = [j for j in range(8) if st[h][j] > 0 and abs(d['fosc'][h][j] - f0) <= .12 * f0]
        if not near: continue
        j = max(near, key=lambda q: d['A'][h][q]); ser.append((tc[h] - t_e, d['A'][h][j] * scale[h, j]))
    return np.array(ser)


def stats(scale):
    out = {k: [] for k in ('W50', 'W80', 'W120', 'RERISE')}
    for i in range(2, 40):
        ser = series(scale, i)
        if len(ser) < 8: continue
        pre = ser[(ser[:, 0] >= -.045) & (ser[:, 0] <= -.008), 1].mean()
        for nm, w in (('W50', .05), ('W80', .08), ('W120', .12)):
            post = ser[(ser[:, 0] >= 0) & (ser[:, 0] <= w + 1e-9)]
            k = int(np.argmin(post[:, 1]))
            out[nm].append(20 * np.log10(post[k:, 1].max() / max(post[k, 1], 1e-9)))
        post = ser[(ser[:, 0] >= 0) & (ser[:, 0] <= .12)]
        thr = pre * 10 ** (-20 / 20)
        below = np.flatnonzero(post[:, 1] < thr)
        if len(below):
            k = below[0]; m = post[k:, 1].max()
            out['RERISE'].append(max(0.0, 20 * np.log10(m / thr)))
        else:
            out['RERISE'].append(0.0)
    return {k: np.array(v) for k, v in out.items()}


def main():
    print('statistic medians (dB) and counts > 6 dB over the 38 notes of the 25 dB gated line')
    for mode in ('base', 'cap', 'arm', 'v16', 'N57', 'N120', 'N320'):
        scale, Nmap, fires = E.emulate(mode)
        s = stats(scale)
        print(f'{mode:6s}: ' + ' | '.join(f'{k} median {np.median(v):5.1f} (>{6}: {int((v>6).sum()):2d}/{len(v)})' for k, v in s.items()))
        if mode == 'base':
            print('   base per-note W50:', ' '.join(f'{x:4.0f}' for x in s['W50'])); print('   base per-note W80:', ' '.join(f'{x:4.0f}' for x in s['W80']))


if __name__ == '__main__':
    main()

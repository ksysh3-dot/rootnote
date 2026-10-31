"""gate16 E5b: which note onsets would D3 fire on?  D3 triggers: CAND->ON, REL->ON, transition entry (not observable in the 22-field trace).
(1) V3a signal (bare repeated 100 Hz bass, 0.5 s period, notes 1..15 are scored): per note, is there a CAND->ON / REL->ON in [t0-30, t0+60] ms?  state of the 100 Hz voice at t0.
(2) V3h gated step line at 25 dB (cached step25): the same count per note."""
import numpy as np
import research_core_metrics as M
import research_core_signals as S
import research_core_xcheck as X
import common16 as C
import proxy16 as PX

FS = 48000


def events(d, tc, st):
    ev = []
    H = len(tc); V = st.shape[1]
    for h in range(1, H):
        prev = {int(d['voice'][h - 1][q]): int(st[h - 1][q]) for q in range(V) if st[h - 1][q] > 0}
        for j in range(V):
            if st[h][j] == 2:
                p = prev.get(int(d['voice'][h][j]), 0)
                if p in (0, 1): ev.append((tc[h], 'birth'))
                elif p == 3: ev.append((tc[h], 'revive'))
    return ev


def main():
    # (1) V3a signal
    x = S.stereo(S.bass_notes(9.0))
    ctx = M.Ctx(M.HOME / 'r3-work/tools/pvb-harness/build_core/libpvbcapi.so', 15, dict(voicing=0, ampSource=0))
    r = ctx.render('bass9', x, 0.0, harmonic=True, voice=True)
    vs = M.voices(ctx, r)
    d = dict(voice=vs.vid.astype(float)); st = vs.st; tc = vs.tc
    ev = events(d, tc, st)
    # input time of a note start n*0.5 s corresponds to tc (analysis centre) ~ n*0.5 s; use +-
    print('V3a bass9 (notes 1..15 scored): events in [t0-60, t0+60] ms of each note start')
    for n in range(0, 16):
        t0 = 0.5 * n
        e = [(round(t - t0, 3), k) for (t, k) in ev if t0 - .06 <= t <= t0 + .06]
        on100 = [int(vs.st[h][j]) for h in [int(np.searchsorted(tc, t0))] for j in range(vs.st.shape[1]) if vs.valid[h][j] and abs(vs.ftr[h][j] - 100) < 8]
        print(f'  note {n:2d}: voice state(s) of the 100 Hz track at t0: {on100}; trigger events: {e}')
    tot = sum(1 for n in range(1, 16) if any(t0 - .06 <= t <= t0 + .06 for t0 in [0.5 * n] for (t, k) in ev))
    print(f'  notes 1..15 with a D3 trigger near the onset: {tot}/15')
    # (2) gated step line, cached
    sig, onsets = PX.sig_step_line(25.0)
    D = PX.load('step25', sig)
    dd, tcc, stt = D['d'], D['tc'], D['st']
    ev2 = events(dd, tcc, stt)
    cnt_b = cnt_r = cnt_n = 0
    for i in range(2, 40):
        t0 = i * PX.PER
        e = [k for (t, k) in ev2 if t0 - .03 <= t <= t0 + .06]
        if 'birth' in e: cnt_b += 1
        elif 'revive' in e: cnt_r += 1
        else: cnt_n += 1
    print(f'\nV3h gated line 25 dB (notes 2..39): onset with CAND->ON {cnt_b}, REL->ON only {cnt_r}, no trigger event {cnt_n}  of 38')


if __name__ == '__main__':
    main()

"""gate16 E4b: what would D5 admit? Real music (10 Slakh train tracks, v1.5 core traces cached by diag16): CAND episodes that were NEVER born (never reached
ON) but had >= 2 consecutive hops with SNR_v >= 25 dB and engine evidence (b) = 0 (the voices D5 releases when (b') ~ SNR >= 25 dB holds).  Labelled with the V6b
rule (within 50 cent of 0.5/1/2/3 x any sounding MIDI note).  Compared with the born voices (CAND -> ON) and with the REL/ON wrong share of the core."""
import numpy as np
import common16 as C
import research_core_xcheck as X
import q7

F_PROM = X.F_PROM


def main():
    tot = dict(ep=0, ep_wrong=0, hops=0, dur_s=0.0)
    born = dict(ep=0, ep_wrong=0)
    rows = []
    for name in C.TRACKS:
        rf = C.ref(name)
        tr = C.get_core(name); d, hop, tc = X.hops_of(tr); raw = tr.reshape(-1, 8, 22)
        H = len(tc); st = d['state']
        dur = (tc[-1] - 0.5)
        # per voice id: series
        vid = d['voice']
        hs, js = np.nonzero(st > 0)
        ids = vid[hs, js]
        order = np.lexsort((hs, ids)); hs, js, ids = hs[order], js[order], ids[order]
        cuts = np.r_[0, np.flatnonzero(np.diff(ids) != 0) + 1, len(ids)]
        n_ep = n_wrong = 0; n_born = n_born_wrong = 0; hop_cnt = 0
        for a, b in zip(cuts[:-1], cuts[1:]):
            h_, j_ = hs[a:b], js[a:b]
            s_ = st[h_, j_]
            if tc[h_[0]] <= 0.5: continue
            reached_on = bool(np.any(s_ == 2))
            # CAND rows
            cm = s_ == 1
            snr = d['snr'][h_, j_]; prom = raw[h_, j_, F_PROM]
            f = raw[h_, j_, X.F_FTR]
            cond = cm & (snr >= 25.0) & (prom == 0)
            # two consecutive CAND rows satisfying the condition
            two = np.flatnonzero(cond[1:] & cond[:-1])
            if len(two) == 0: continue
            k = two[0]
            h0 = h_[k]
            fn = C.targets_at(rf, tc[h0], 'a'); tgt = np.outer(fn, [.5, 1, 2, 3]).ravel() if len(fn) else np.array([])
            wrong = (not len(tgt)) or np.min(C.cents(f[k], tgt)) > 50
            if reached_on:
                n_born += 1; n_born_wrong += int(wrong)
            else:
                n_ep += 1; n_wrong += int(wrong); hop_cnt += int(cond.sum())
                rows.append((name, tc[h0], f[k], snr[k], bool(wrong), int(len(h_))))
        print(f'{name}: never-born CAND episodes with >=2 consecutive hops SNR>=25 & (b)=0: {n_ep} ({n_ep/dur:.2f}/s), wrong {n_wrong} ({100*n_wrong/max(n_ep,1):.0f} %); '
              f'(for comparison: voices that were later born and also had such 2 hops: {n_born}, wrong {n_born_wrong})')
        tot['ep'] += n_ep; tot['ep_wrong'] += n_wrong; tot['dur_s'] += dur; born['ep'] += n_born; born['ep_wrong'] += n_born_wrong
    print(f"\nPOOLED: {tot['ep']} episodes in {tot['dur_s']:.0f} s ({tot['ep']/tot['dur_s']:.2f}/s), wrong share {100*tot['ep_wrong']/max(tot['ep'],1):.0f} %"
          f" | born-later voices with the same 2-hop pattern {born['ep']}, wrong {100*born['ep_wrong']/max(born['ep'],1):.0f} %")
    fr = np.array([r[2] for r in rows]); lens = np.array([r[5] for r in rows])
    print(f'episode lengths (CAND hops until it vanished): median {np.median(lens):.0f}, p90 {np.percentile(lens,90):.0f}; f median {np.median(fr):.1f} Hz, below 60 Hz {100*np.mean(fr<60):.0f} %')


if __name__ == '__main__':
    main()

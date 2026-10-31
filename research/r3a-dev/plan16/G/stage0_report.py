"""stage 0 report from stage0_raw.json -> stage0_report.txt (stdout)"""
import json, numpy as np
R = json.load(open('/home/ksysh/r3a-dev/plan16/G/stage0_raw.json'))
ORDER = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012', 'Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
NOB = [k for k in ORDER if R[k]['nobass']]
BASS = [k for k in ORDER if not R[k]['nobass']]
BASS_X25 = [k for k in BASS if k != 'Track00025']
SH = lambda k: k[-2:]
BN = ['<0.25', '.25-1', '1-2', '2-4', '>4', 'nobass']
flags = []
print('# G stage 0 (16.13 + 16.13.1), dev 10 songs, core v1.5, decision span t >= 4 s (unrestricted in brackets)')
print('units: energy / R3R (59.3507)\n')

# leak
mx = max(v['max_excess'] for k in R for v in R[k]['leak'].values())
print(f'## leak log: max over hops, songs, D_s of (max trace hop index read - h) = {mx}  (must be <= 0)\n')

# 0a
print('## 0a  silent wrong_sa by stem-aware bass-silence length before the sample (core), t >= 4 s  [all t > 0.5 s]')
print('song | total | ' + ' | '.join(BN) + ' | R_long')
tot = np.zeros((6, 2))
rl = {}
for k in ORDER:
    b = np.array(R[k]['bins'])               # 6 x 2 ([all, >=4])
    tot += b
    for idx, nm in ((1, 't>=4'), (0, 'all')):
        t_ = b[:, idx].sum()
        rl[(k, idx)] = (b[2:, idx].sum() / t_) if t_ > 1e-6 else float('nan')
    print(f"{SH(k)}{' (nb)' if R[k]['nobass'] else ''} | {b[:,1].sum():.4f} [{b[:,0].sum():.4f}] | " + ' | '.join(f'{b[i,1]:.4f}' for i in range(6)) + f" | {rl[(k,1)]*100:.1f}% [{rl[(k,0)]*100:.1f}%]")


def rlong(keys, idx):
    b = sum(np.array(R[k]['bins'])[:, idx] for k in keys)
    return float(b[2:].sum() / max(b.sum(), 1e-30)), float(b.sum())


for nm, keys in (('pooled all 10', ORDER), ('bass songs excl T25', BASS_X25), ('T25', ['Track00025']), ('no-bass songs', NOB), ('bass songs incl T25', BASS)):
    a, s = rlong(keys, 1); a0, s0 = rlong(keys, 0)
    print(f'R_long {nm}: {a*100:.1f}%  (sum {s:.4f})   [unrestricted {a0*100:.1f}%  (sum {s0:.4f})]')
R_all, _ = rlong(ORDER, 1); R_bx, _ = rlong(BASS_X25, 1); R_25, _ = rlong(['Track00025'], 1)
R_all0, _ = rlong(ORDER, 0); R_bx0, _ = rlong(BASS_X25, 0); R_250, _ = rlong(['Track00025'], 0)
f0a = R_all < 0.40; fM5 = (R_bx < 0.10) and (R_25 < 0.20)
f0a0 = R_all0 < 0.40; fM50 = (R_bx0 < 0.10) and (R_250 < 0.20)
print(f'STOP 0a (pooled R_long < 40%): {f0a}  [unrestricted {f0a0}]')
print(f'STOP M5 (bass excl T25 R_long < 10% AND T25 R_long < 20%): {fM5}  [unrestricted {fM50}]')
four = ['Track00001', 'Track00005', 'Track00012', 'Track00020']
rl4 = [rl[(k, 1)] for k in four]
print('M2 four bass songs R_long (t>=4): ' + ', '.join(f'{SH(k)} {x*100:.1f}%' for k, x in zip(four, rl4)) + f"  -> all < 10%: {all(x < 0.10 for x in rl4 if not np.isnan(x))} ('not testable' if True)\n")
if f0a or fM5:
    flags.append('0a/M5')

# 0b
print('## 0b  oracle (stem silence >= H or no-bass song -> x -24 dB): R_max = 1 - E_oracle/E_core of silent wrong_sa, t >= 4 s [all t > 0.5 s]')
rmaxH = {}
for H in ('1.0', '2.0', '4.0'):
    ec = {k: R[k]['core']['sil'] for k in ORDER}; eo = {k: R[k]['oracle'][H]['sil'] for k in ORDER}
    def red(keys, i):
        c = sum(ec[k][i] for k in keys); o = sum(eo[k][i] for k in keys)
        return 1 - o / c if c > 1e-12 else float('nan')
    rmaxH[H] = red([k for k in ORDER if k != 'Track00025'], 1)
    print(f'H={H}s: pooled excl T25 {rmaxH[H]*100:.1f}% [{red([k for k in ORDER if k!="Track00025"],0)*100:.1f}%] | pooled all {red(ORDER,1)*100:.1f}% | T25 {red(["Track00025"],1)*100:.1f}% | no-bass {red(NOB,1)*100:.1f}% | ' +
          ' '.join(f"{SH(k)} {red([k],1)*100:.0f}%" for k in ORDER if ec[k][1] > 1e-5))
f0b = all(v < 0.50 for v in rmaxH.values())
print(f'STOP 0b (R_max pooled excl T25 < 50% for every H): {f0b}')
if f0b:
    flags.append('0b')
print()

# 0c
print('## 0c  real gate on the core trace, g_cap -24 dB, per (H, D_s)   [t >= 4 s]')
RP = {}; IV = {}
keys_hd = [f'{H}_{d}' for d in (100, 150) for H in ('1', '2', '4')]
print('(H,D_s) | R_P T24+T26 | R_P T24 | T26 | T23 | T25 | P=0 time T24 | T26 | T23 | T25 | bass songs (iv) P=1 in bass hops | P=0 bass-hop time | stable onsets/s no-bass hops: T24 | T26 | T23')
for kh in keys_hd:
    def rp(keys):
        i_ = sum(R[k]['real'][kh]['e_p0'][1] for k in keys); o_ = sum(R[k]['real'][kh]['e_p1'][1] for k in keys)
        return i_ / max(i_ + o_, 1e-30)
    bh = sum(R[k]['real'][kh]['bass_hops'] for k in BASS); b1 = sum(R[k]['real'][kh]['bass_p1'] for k in BASS)
    RP[kh] = rp(['Track00024', 'Track00026']); IV[kh] = b1 / max(bh, 1)
    g = lambda k, f: R[k]['real'][kh][f]
    print(f"{kh} | {RP[kh]*100:.1f}% | {rp(['Track00024'])*100:.1f}% | {rp(['Track00026'])*100:.1f}% | {rp(['Track00023'])*100:.1f}% | {rp(['Track00025'])*100:.1f}% | " +
          ' | '.join(f"{g(k,'p0_frac')*100:.1f}%" for k in ('Track00024', 'Track00026', 'Track00023', 'Track00025')) +
          f" | {IV[kh]*100:.2f}% | {(1-IV[kh])*100:.2f}% | " + ' | '.join(f"{g(k,'onset_per_s_nobass'):.2f}" for k in ('Track00024', 'Track00026', 'Track00023')))
print('\nbass songs: per-song P=1 fraction in bass-sounding hops (t>=4) and P=0 time fraction (all hops), stable onsets/s (no-bass hops / all hops), P transitions per min, P 1->0 while bass sounds (count)')
for kh in keys_hd:
    row = []
    for k in BASS:
        e = R[k]['real'][kh]
        row.append(f"{SH(k)} {100*e['bass_p1']/max(e['bass_hops'],1):.1f}%/{e['p0_frac']*100:.0f}%/{e['onset_per_s_nobass']:.2f},{e['onset_per_s_all']:.2f}/{e['trans_per_min']:.0f}/{e['trans10_bass']}")
    print(kh + ' | ' + ' | '.join(row))
print('no-bass songs: stable-hop fraction, P transitions per min:')
for kh in keys_hd:
    print(kh + ' | ' + ' | '.join(f"{SH(k)} {R[k]['real'][kh]['stable_hop_frac']*100:.1f}%/{R[k]['real'][kh]['trans_per_min']:.0f}" for k in NOB))
fR = all(RP[kh] < 0.50 for kh in keys_hd)
fIV = all(IV[kh] < 0.98 for kh in keys_hd)
print(f'STOP 0c-R (R_P T24+T26 < 50% for every (H,D_s)): {fR}')
print(f'STOP 0c-IV (bass-hop P=1 < 98% for every (H,D_s)): {fIV}   (settings with R_P >= 50% AND (iv) >= 98%: {[kh for kh in keys_hd if RP[kh] >= .5 and IV[kh] >= .98]})')
if fR or fIV:
    flags.append('0c')
print()

# INFO: real-gate silent reduction
print('## INFO (not a decision): real-gate preview, silent wrong_sa reduction and right-layer change, t >= 4 s')
for gcd in ('g-24', 'g-12'):
    print(f'g_cap {gcd[1:]} dB:  (H,D_s) | silent sum excl T25 | T24 | T26 | T25 | T01 | T05 | T12 | T20 | F pooled dB | worst bass-song F dB')
    for kh in keys_hd:
        def rd(keys):
            c = sum(R[k]['core']['sil'][1] for k in keys); o = sum(R[k]['real'][kh][gcd]['sil'][1] for k in keys)
            return (1 - o / c) * 100 if c > 1e-12 else float('nan')
        fc = sum(R[k]['core']['right'][1] for k in BASS); fg = sum(R[k]['real'][kh][gcd]['right'][1] for k in BASS)
        worst = min(10 * np.log10(R[k]['real'][kh][gcd]['right'][1] / R[k]['core']['right'][1]) for k in BASS if R[k]['core']['right'][1] > 0)
        print(f"{kh} | {rd([k for k in ORDER if k != 'Track00025']):.1f}% | {rd(['Track00024']):.0f}% | {rd(['Track00026']):.0f}% | {rd(['Track00025']):.0f}% | " + ' | '.join(f"{rd([k]):.0f}%" for k in four) + f" | {10*np.log10(fg/fc):+.2f} | {worst:+.2f}")
print()

# 0d
print('## 0d  first-note cost (report only): first 200 ms right-layer energy of bass notes whose onset hop has P=0; per song dB (sum) / fraction of first notes with > 6 dB loss / n first notes (n counted)')
print('M1 fixed thresholds: song >= -5 dB, <= 35% notes > 6 dB loss, songs with < 5 first notes excluded')
for gcd in ('g-24', 'g-12'):
    print(f'g_cap {gcd[1:]} dB:')
    for kh in keys_hd:
        cells = []
        for k in BASS:
            f = R[k]['real'][kh][gcd]['first']
            if f['n_ok'] >= 5 and f['db'] is not None:
                cells.append(f"{SH(k)} {f['db']:+.1f}/{f['frac_gt6']*100:.0f}%/{f['n_ok']}")
            else:
                cells.append(f"{SH(k)} n={f['n_ok']}(<5)" + (f" {f['db']:+.1f}" if f['db'] is not None else ''))
        print(f'  {kh} | ' + ' | '.join(cells))
print()
print('FLAGS:', flags if flags else 'none')
print('STAGE 0 RESULT:', 'STOP ' + ','.join(flags) if flags else 'PASS (no stop flag fired)')

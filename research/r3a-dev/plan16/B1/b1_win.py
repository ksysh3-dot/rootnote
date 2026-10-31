"""Per-window trace/spectrum analysis of Apparition. usage: b1_win.py t0 [t1=t0+2]  (prints a report)"""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
import soundfile as sf
from scipy.signal import resample_poly, find_peaks, butter, sosfiltfilt
import api084 as CA
FS = 48000
SONG = [p for p in MUSIC if '08. Apparition' in p][0]
_x = None


def mm(t):
    return f'{int(t // 60)}:{t % 60:05.2f}'


def inp(t0, t1):
    global _x
    if _x is None:
        x, fs = sf.read(SONG, always_2d=True, dtype='float64')
        g = np.gcd(fs, FS)
        _x = resample_poly(x[:, :2].mean(1), FS // g, fs // g)
    return _x[int(t0 * FS):int(t1 * FS)]


def peaks_over_time(x, t0, fr=0.5, hop=0.25):
    n = int(fr * FS); w = np.hanning(n); nf = 1 << 17
    fq = np.fft.rfftfreq(nf, 1 / FS); sel = (fq >= 25) & (fq <= 1200)
    out = []
    for s in range(0, len(x) - n + 1, int(hop * FS)):
        P = np.abs(np.fft.rfft(x[s:s + n] * w, nf))[sel]; f = fq[sel]
        db = 20 * np.log10(P + 1e-12); db -= db.max()
        pk, _ = find_peaks(db, height=-30, distance=int(3 / (fq[1])))
        pk = pk[np.argsort(-db[pk])][:12]
        out.append((t0 + s / FS + fr / 2, [(round(float(f[k]), 1), round(float(db[k]), 0)) for k in sorted(pk)]))
    return out


def analyse(tag, t0, t1, tr, layer_env, peaks_in, layer_env_full=None):
    r = []
    P = r.append
    hop = tr['hop'][:, 0]
    tc = CA.hop_time(hop)[0]
    m = (tc >= t0) & (tc < t1)
    idx = np.where(m)[0]
    st = tr['state'][idx]; vid = tr['voice'][idx]; A = tr['A'][idx]; fo = tr['f_osc'][idx]; ft = tr['f_track'][idx]; co = tr['coasting'][idx]
    sound = ((st == 2) | (st == 3)) & (A > 1e-5)
    nh = len(idx); dt = 16 / 3000
    P(f'--- {tag}: {mm(t0)}-{mm(t1)}  hops={nh}')
    # per voice id
    ids = np.unique(vid[sound])
    rows = []
    for v in ids:
        mk = (vid == v) & sound
        hh = mk.sum()
        a = np.where(mk, A, 0.0)
        e = (a ** 2).sum() * dt
        s_on = ((st == 2) & (vid == v)).sum(); s_rel = ((st == 3) & (vid == v)).sum()
        fm = np.nanmean(np.where(mk, fo, np.nan)); fr_ = np.nanmax(np.where(mk, fo, np.nan)) - np.nanmin(np.where(mk, fo, np.nan))
        rows.append((e, v, hh * dt, fm, fr_, 20 * np.log10(a[mk].max()), 20 * np.log10(np.median(a[mk])), s_on * dt, s_rel * dt, co[(vid == v)].max()))
    rows.sort(reverse=True)
    etot = sum(r_[0] for r_ in rows) or 1
    P('voices sounding (state ON/REL, A>1e-5), sorted by energy share: id | share | dur s | f_osc mean Hz | f range Hz | A max dB | A med dB | ON s | REL s | coasting max')
    for r_ in rows[:10]:
        P(f'  {int(r_[1]):5d} | {r_[0] / etot:.2f} | {r_[2]:.2f} | {r_[3]:6.1f} | {r_[4]:5.1f} | {r_[5]:6.1f} | {r_[6]:6.1f} | {r_[7]:.2f} | {r_[8]:.2f} | {int(r_[9])}')
    P(f'  number of distinct voice ids sounding: {len(ids)}')
    # births and REL entries per slot (state transitions in the full trace so that the first hop is covered)
    j0 = max(idx[0] - 1, 0)
    stf = tr['state'][j0:idx[-1] + 1]
    prev = stf[:-1]; cur = stf[1:]
    births = ((cur == 2) & (prev != 2) & (prev != 3)).sum()      # CAND/EMPTY -> ON
    relin = ((cur == 3) & (prev == 2)).sum()                       # ON -> REL
    revive = ((cur == 2) & (prev == 3)).sum()                      # REL -> ON
    dies = ((cur == 0) & ((prev == 3) | (prev == 2))).sum()        # leaves
    T = (t1 - t0)
    P(f'  births (->ON from CAND/EMPTY) {births} = {births / T:.1f}/s ; ON->REL {relin} = {relin / T:.1f}/s ; REL->ON {revive} = {revive / T:.1f}/s ; voices ending {dies} = {dies / T:.1f}/s')
    # pairs within 14 Hz among loud voices (within 20 dB of the loudest at that hop)
    npair = 0; hp = 0; dfs = []; pairlev = []
    for k in range(nh):
        s = np.where(sound[k])[0]
        if len(s) < 2: continue
        a = A[k, s]; ok = a > a.max() * 0.1
        s = s[ok]
        found = False
        for p_ in range(len(s)):
            for q in range(p_ + 1, len(s)):
                d = abs(fo[k, s[p_]] - fo[k, s[q]])
                if d < 14 and d > 0.0:
                    found = True; npair += 1; dfs.append(d)
        hp += found
    P(f'  hops with a pair within 14 Hz (both within 20 dB of the loudest): {hp}/{nh} = {hp / max(nh, 1):.2f}; pair-hops {npair}; df median {np.median(dfs) if dfs else float("nan"):.1f} Hz, df<=12 share {(np.array(dfs) <= 12).mean() if dfs else float("nan"):.2f}')
    # the layer-pulse rate
    seg = layer_env
    P(f'  layer 150-600 envelope (v15) pulsing: {seg}')
    # amplitude series: total sounding amplitude sum(A) and its dB modulation
    atot = np.where(sound, A, 0.0).sum(1)
    adb = 20 * np.log10(atot + 1e-7)
    adb = adb - adb.mean()
    n = len(adb); ww = np.hanning(n); f2 = np.fft.rfftfreq(4096, dt); Pw = np.abs(np.fft.rfft(adb * ww, 4096)) ** 2
    bb = (f2 >= 2) & (f2 <= 12)
    P(f'  sum(A) dB modulation: peak at {f2[bb][np.argmax(Pw[bb])]:.1f} Hz, rms in 2-12 Hz band {np.sqrt(Pw[bb].sum() / (4096 * (ww ** 2).sum()) * 2):.2f} dB, p-p {np.ptp(adb):.1f} dB')
    # per-voice A modulation of the top 3 voices
    for r_ in rows[:3]:
        v = r_[1]; mk = (vid == v) & sound
        if mk.sum() < 40: continue
        a = np.where(mk, A, np.nan); ii = np.where(mk.any(1))[0]
        aa = 20 * np.log10(np.nanmax(np.where(mk, A, np.nan)[ii], 1)); fv = np.nanmax(np.where(mk, ft, np.nan)[ii], 1)
        aa = aa - aa.mean(); n2 = len(aa); w2 = np.hanning(n2)
        PA = np.abs(np.fft.rfft(aa * w2, 4096)) ** 2
        fvd = fv - np.polyval(np.polyfit(np.arange(n2), fv, 2), np.arange(n2))
        cents = 1200 * np.log2(1 + fvd / np.mean(fv))
        PF = np.abs(np.fft.rfft((cents - cents.mean()) * w2, 4096)) ** 2
        P(f'  voice {int(v)} (f~{np.mean(fv):.0f} Hz): A-dB mod peak {f2[bb][np.argmax(PA[bb])]:.1f} Hz p-p {np.ptp(aa):.1f} dB | f_track mod peak {f2[bb][np.argmax(PF[bb])]:.1f} Hz, p-p {np.ptp(cents):.0f} cents')
    # dominant-voice diagnostics: f_osc vs f_track mismatch, A dips, f_osc jumps; relation to the layer envelope
    if rows:
        v = rows[0][1]; mk = (vid == v) & sound
        ii = np.where(mk.any(1))[0]
        if len(ii) > 40:
            sl = mk[ii].argmax(1)
            aA = np.array([A[i, s_] for i, s_ in zip(ii, sl)]); aF = np.array([fo[i, s_] for i, s_ in zip(ii, sl)]); aT = np.array([ft[i, s_] for i, s_ in zip(ii, sl)])
            adB = 20 * np.log10(aA + 1e-9)
            dev = 1200 * np.log2(aF / aT)
            P(f'  dominant voice {int(v)}: f_osc vs f_track |dev|>100 cents in {np.mean(np.abs(dev) > 100):.2f} of its hops, >50 cents {np.mean(np.abs(dev) > 50):.2f}; median dev {np.median(dev):+.0f} cents; f_osc range {aF.min():.1f}-{aF.max():.1f} Hz vs f_track {aT.min():.1f}-{aT.max():.1f} Hz')
            from scipy.ndimage import median_filter
            base = median_filter(adB, size=57, mode='nearest')    # ~0.3 s
            low = adB < base - 8
            ev_n = int(((low[1:] & ~low[:-1])).sum() + low[0])
            P(f'  dominant voice A dips (>8 dB below its 0.3 s median): {ev_n} events = {ev_n / T:.1f}/s, dip hops share {low.mean():.2f}; A p-p {np.ptp(adB):.1f} dB; A std {adB.std():.1f} dB')
            jf = np.abs(np.diff(aF)) > 4.0
            P(f'  f_osc jumps (>4 Hz between consecutive hops): {int(jf.sum())} = {jf.sum() / T:.1f}/s')
            tt = tc[idx][ii]; li = np.clip((tt * ER).astype(int), 0, len(layer_env_full) - 1)
            lev = layer_env_full[li].astype(float)
            P(f'  corr(layer env dB, dom. voice A dB) = {np.corrcoef(lev, adB)[0, 1]:.2f}; corr(layer env dB, |dev| cents) = {np.corrcoef(lev, np.abs(dev))[0, 1]:.2f}; corr(A dB, |dev|) = {np.corrcoef(adB, np.abs(dev))[0, 1]:.2f}')
            if len(ii) > 40:
                aD = np.array([tr['dfdt_s'][idx][i, s_] for i, s_ in zip(ii, sl)])
                from scipy.ndimage import uniform_filter1d
                dsm = aT - uniform_filter1d(aT, 75, mode='nearest')      # vibrato displacement vs ~0.4 s mean
                n3 = len(adB); w3 = np.hanning(n3)
                PAv = np.abs(np.fft.rfft((adB - adB.mean()) * w3, 4096)) ** 2; PFv = np.abs(np.fft.rfft((aT - aT.mean()) * w3, 4096)) ** 2
                fa = f2[bb][np.argmax(PAv[bb])]; ff = f2[bb][np.argmax(PFv[bb])]
                P(f'  (c) test, dominant voice: A-dB modulation peak {fa:.1f} Hz vs f_track modulation peak {ff:.1f} Hz (ratio {fa / ff:.2f}); corr(A dB, |dfdt|) = {np.corrcoef(adB, np.abs(aD))[0, 1]:.2f}; corr(A dB, |f_track - 0.4 s mean|) = {np.corrcoef(adB, np.abs(dsm))[0, 1]:.2f}; |dfdt| median {np.median(np.abs(aD)):.1f} Hz/s; input 40-600 modulation M in window = see registered line')
    # event times
    ev = []
    for k in range(1, len(stf)):
        for s_ in range(8):
            if stf[k, s_] == 2 and stf[k - 1, s_] not in (2, 3): ev.append((tc[j0 + k], 'B', int(tr['voice'][j0 + k, s_]), float(tr['f_osc'][j0 + k, s_])))
            if stf[k, s_] == 3 and stf[k - 1, s_] == 2: ev.append((tc[j0 + k], 'R', int(tr['voice'][j0 + k, s_]), float(tr['f_osc'][j0 + k, s_])))
    P('  events (B=birth to ON, R=release): ' + ', '.join(f'{e[1]}{e[2]}@{e[0] - t0:.2f}s/{e[3]:.0f}Hz' for e in ev[:40]))
    # (d) pitch check vs input peaks of the nearest frame
    sup = []; sup_t = []
    for k in np.where(sound.any(1))[0][::6]:
        tk = tc[idx[k]]
        fr = min(peaks_in, key=lambda pr: abs(pr[0] - tk))[1]
        pf = np.array([p_[0] for p_ in fr]) if fr else np.array([1e9])
        for s_ in np.where(sound[k])[0]:
            if A[k, s_] > A[k, sound[k]].max() * 0.3:
                nm_ = 0
                for kk in range(1, 9):
                    h = fo[k, s_] * kk
                    if h <= 1200 and np.min(np.abs(1200 * np.log2(h / pf))) < 40: nm_ += 1
                sup.append(nm_)
                sup_t.append(np.min(np.abs(1200 * np.log2(fo[k, s_] / pf))))
    sup = np.array(sup); sup_t = np.array(sup_t)
    P(f'  (d) pitch support, loud voices (>=-10 dB of loudest): harmonics k=1..8 of f_osc within 40 cents of an input spectral peak (top 12 peaks 25-1200 Hz, within 30 dB): share with >=2 matching harmonics {np.mean(sup >= 2):.2f}, with 0 or 1 match {np.mean(sup < 2):.2f}, with 0 matches {np.mean(sup == 0):.2f}; (fundamental itself present as a peak: {np.mean(sup_t < 40):.2f})')
    return '\n'.join(r)


def layer_stats(t0, t1, which, suf=''):
    from b1_mod import mod_series
    out = []
    for e in ('P1', 'v15', 'v16a'):
        env = np.load(C / f's09_{e}{suf}.npz')['env']
        s = env[int(t0 * ER):int(t1 * ER)].astype(float)
        x = (s - s.mean()) * np.hanning(len(s))
        Pw = np.abs(np.fft.rfft(x, NFFT)) ** 2
        Mv = np.sqrt((Pw / (NFFT * np.sum(np.hanning(len(s)) ** 2)) * 2)[band].sum())
        out.append(f'{e}: M={Mv:.2f} dB-rms, peak {freqs[band][np.argmax(Pw[band])]:.1f} Hz, p-p {np.ptp(s):.1f} dB, mean {10 * np.log10(np.mean(10 ** (s / 10))):.1f} dBFS')
    return ' | '.join(out)


if __name__ == '__main__':
    t0 = float(sys.argv[1]); t1 = float(sys.argv[2]) if len(sys.argv) > 2 else t0 + 2
    x = inp(t0 - 1, t1 + 1)
    pk = peaks_over_time(x, t0 - 1)
    print(f'=== window {mm(t0)}-{mm(t1)} ===')
    print('input low-band spectral peaks (STFT 0.5 s, Hz/dB-rel), time|peaks:')
    for tt, p_ in pk:
        if t0 - 0.3 <= tt <= t1 + 0.3: print(f'  {mm(tt)}: {p_}')
    for e in ('v15', 'v16a'):
        tr = {k: v for k, v in np.load(C / f'app_trace_{e}.npz').items()}
        print(analyse(e, t0, t1, tr, layer_stats(t0, t1, e), pk, np.load(C / f's09_{e}.npz')['env']))
    print('layer envelope stats (registered measure, 150-600 Hz, window as given):', layer_stats(t0, t1, ''))
    print('layer envelope stats (SUPPLEMENTARY 20-150 Hz band):', layer_stats(t0, t1, '', '_lo'))

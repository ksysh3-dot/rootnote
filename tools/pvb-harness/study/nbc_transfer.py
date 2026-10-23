"""NotebookCheck pink-noise tables -> estimated speaker response in OUR measurement frame.

Method (difference transfer): NotebookCheck measures every phone the same way, so the difference between a phone
and the Galaxy S26 Ultra in NotebookCheck's data is added to OUR S26 Ultra UMIK-1 curve. The site's own method
offset (room, distance, A-weighting, volume) cancels in that difference; only what differs between the phones stays.
All curves are referenced to the mean of 630-2000 Hz ("mids"), not a single 1 kHz band (single bands ripple).
Inputs: nbc_raw.txt (numbers copied from NotebookCheck's own tables) in a PRIVATE data folder given as the first
argument; third-party measurement tables are not kept in this public repository. Output: nbc_transfer.csv there.
"""
import csv, os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'private')
BANDS = np.array([100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500.])
OURS_HZ = np.array([125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500.])
OURS_DB = np.array([-20.2,-14.0,-8.9,-4.9,-6.0,-5.6,-4.7,-2.8,1.0,0.3,3.0,2.3,5.3,10.7,11.1,10.9,15.7,13.3,7.9,-1.6,-12.0])
MID = (BANDS >= 630) & (BANDS <= 2000)

def load():
    rows = []
    for line in open(os.path.join(DATA, 'nbc_raw.txt')):
        if line.startswith('#') or not line.strip(): continue
        name, role, art, vals = line.strip().split('|')
        rows.append((name, role, art, np.array([float(v) for v in vals.split(',')])))
    return rows

def rel(v): return v - v[MID].mean()

def main():
    rows = load()
    ref = [v for n, r, a, v in rows if n == 'Samsung Galaxy S26 Ultra'][0]
    ours = np.interp(np.log(BANDS[1:]), np.log(OURS_HZ), OURS_DB)
    ours = np.concatenate([[np.nan], ours])
    ours_rel = ours - np.nanmean(ours[MID])
    out = []
    for name, role, art, v in rows:
        d = rel(v) - rel(ref)                 # phone minus S26U, NotebookCheck frame
        est = ours_rel + d                    # in our frame
        bass = np.mean(rel(v)[(BANDS >= 125) & (BANDS <= 250)]) - np.mean(rel(ref)[(BANDS >= 125) & (BANDS <= 250)])
        lowmid = np.mean(d[(BANDS >= 200) & (BANDS <= 400)])
        treble = np.mean(d[(BANDS >= 2500) & (BANDS <= 6300)])
        # -10 dB point re mids on the estimated curve: highest band under 1 kHz below -10 whose lower neighbour is too
    # (a single dip in the mids is not a roll-off)
        f10 = np.nan
        for i in range(len(BANDS) - 1, 0, -1):
            if BANDS[i] > 1000: continue
            if est[i] < -10 and not np.isnan(est[i]) and (i < 2 or np.isnan(est[i-1]) or est[i-1] < -10):
                j = i + 1
                f10 = float(np.exp(np.interp(-10, [est[i], est[j]], [np.log(BANDS[i]), np.log(BANDS[j])])))
                break
        out.append(dict(device=name, role=role, nbc_article=art, bass_125_250_vs_s26u_db=round(bass, 1),
                        lowmid_200_400_vs_s26u_db=round(lowmid, 1), treble_2k5_6k3_vs_s26u_db=round(treble, 1),
                        est_minus10db_hz=round(f10) if not np.isnan(f10) else '',
                        **{f'est_{int(b)}': (round(float(e), 1) if not np.isnan(e) else '') for b, e in zip(BANDS, est)}))
    with open(os.path.join(DATA, 'nbc_transfer.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    return out

if __name__ == '__main__':
    for r in sorted(main(), key=lambda r: r['bass_125_250_vs_s26u_db']):
        print(f"{r['device'][:30]:30s} {r['role']} bass {r['bass_125_250_vs_s26u_db']:6.1f} lowmid {r['lowmid_200_400_vs_s26u_db']:6.1f} "
              f"treble {r['treble_2k5_6k3_vs_s26u_db']:6.1f} -10dB@ {r['est_minus10db_hz']}")

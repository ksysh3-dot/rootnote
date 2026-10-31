import json
import numpy as np
d = json.load(open('/home/ksysh/r3a-dev/plan16/V16A/diag35.json'))
print('row | hops 0-300ms | voice absent (slot -1) | hops nv>=2 | of those: NJ applied < 0.75*held | median held/applied(nv>=2) | falling flag hops | min SNR when present, hops with snr<30 dB | whole-note noREL')
for k, v in d.items():
    r = v['rows']
    n = len(r)
    absent = sum(1 for x in r if x['state'] == -1)
    two = [x for x in r if x['nv'] is not None and x['nv'] >= 2]
    lag = sum(1 for x in two if x['NJ'] < .75 * x['NJ_held'])
    med = float(np.median([x['NJ_held'] / x['NJ'] for x in two])) if two else None
    fall = sum(1 for x in r if x['fallJ'])
    snrs = [x['snr'] for x in r if x['snr'] is not None]
    print(f"{k:20s} {n:4d} {absent:4d} {len(two):4d} {lag:4d} {med if med is None else round(med, 2)} {fall:4d} {min(snrs):6.1f} {sum(1 for s in snrs if s < 30):3d}   noREL {v['noREL_hops']}  firstON {v['first_ON_ms']:.1f} ms")
# absent hops: SNR of the 35 Hz voice is unavailable; show the SNR just before the loss for A1 8
for k in ('A1 8 uncond (+A2)',):
    r = d[k]['rows']
    print(k, 'N_v / N_J held / N_J applied / nv over the absent hops:')
    print([(x['ms'], x['NJ_held'], x['NJ'], x['nv']) for x in r if x['state'] == -1][:30])

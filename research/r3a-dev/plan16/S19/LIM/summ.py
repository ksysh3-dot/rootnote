import json
import numpy as np
rows = ['p1', 'v15', 'v16b', 'v16c']
D = '/home/ksysh/r3a-dev/plan16/S19/LIM/'
print('whole rendered span (start to window/excerpt end): [s6 max GR dB / pre-limiter peak dBFS | off max GR / peak]  per song index')
for r in rows:
    out = []
    for i in range(14):
        d = json.load(open(D + f'res/{r}_s{i:02d}.json'))['log']
        out.append(f"{i}:{d['s6']['gr_max']:.2f}/{20*np.log10(d['s6']['pre_peak']):.1f}|{d['off']['gr_max']:.2f}/{20*np.log10(d['off']['pre_peak']):.1f}")
    print(r, ' '.join(out))
print('s0:')
for r in rows:
    out = []
    for i in range(14):
        d = json.load(open(D + f'res/{r}_s{i:02d}.json'))['log']
        out.append(f"{i}:{d['s0']['gr_max']:.2f}/{20*np.log10(d['s0']['pre_peak']):.1f}")
    print(r, ' '.join(out))

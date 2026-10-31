import json, sys
V = '/home/ksysh/r3a-dev/verify_core/'
x = json.load(open(V + 'xcheck_v7d.json'))['v7d']
for od, d in x.items():
    print('=====', od)
    t = d['t_start_s']
    print('  time(s)  dryHF   P1     A      B     (25 ms bins; layer 150-600 Hz energy dB; dryHF = dry output >2 kHz energy dB)')
    for i, tt in enumerate(t):
        if 6.9 <= tt <= 8.1:
            print(f'  {tt:6.3f} {d["hf_dry_db"][i]:7.1f} {d["P1"][i]:6.1f} {d["A"][i]:6.1f} {d["B"][i]:6.1f}')
    for k, v in d.items():
        if '_hit' in k:
            print('  ', k, round(v, 2))

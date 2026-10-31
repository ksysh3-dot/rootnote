import json
V = '/home/ksysh/r3a-dev/verify_core/'
x = json.load(open(V + 'xcheck_sanity.json'))['sanity']
print('layer peak re dry peak (dB) [layer = out(0)-out(-120), out_db -18], and HF (>2 kHz) peak of the layer in dBFS-at-out_db-18:')
for sn, d in x.items():
    row = []
    for k in ('P1', 'A', 'B', 'C', 'D'):
        r = d[k]
        row.append(f'{k}: {20*__import__("math").log10(max(r["layer_peak"],1e-12)) - r["peak_dry_dbfs"]:6.1f} / {20*__import__("math").log10(max(r["hf_peak"],1e-12)):6.1f}')
    print(f'  {sn:32s}', ' | '.join(row))

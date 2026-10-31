import json, sys
x = json.load(open('/home/ksysh/r3a-dev/verify_core/xcheck_v4.json'))
for sig in ('bass+pink', 'bass+kick+pink'):
    print('V4b low bins (of 280, limit 5 = 2 %) by bin definition:', sig)
    keys = None
    for k, v in x['v4'].items():
        var = v['signals'][sig]['b_variants_low_bins_of_280']
        if keys is None:
            keys = list(var.keys()); print('      ' + ' '.join(f'{q:>16s}' for q in keys))
        print(f'  {k:3s} ' + ' '.join(f'{var[q]:16d}' for q in keys))

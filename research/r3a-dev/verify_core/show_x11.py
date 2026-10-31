import json
x = json.load(open('/home/ksysh/r3a-dev/verify_core/xcheck_v3h.json'))['v3h']
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
print('V3h  (ms)  xcheck rms5 | xcheck hilbert-bp-rms5 | suite     limits: SNR>=20: rise90<=25, tail<=40 ; SNR 6: rise90<=70, tail<=90')
for k, v in x.items():
    s = suite[smap[k]]['V3h']; sb = suite[smap[k]]['V3bare']['v3h_bare']
    for sn, lab in (('bare', 'bare note'), ('line25', 'line 25 dB'), ('line6', 'line 6 dB')):
        a, b = v[sn]['rms5'], v[sn]['hilbert_bp_rms5']
        if sn == 'bare':
            su = f'suite rise90 {sb["tailnote_rise90_ms"]:.1f} tail {sb["tail_ms"]:.1f}'
        else:
            q = s['snr25' if sn == 'line25' else 'snr6']; su = f'suite rise50 {q["rise50_ms"]:.1f} rise90 {q["rise90_ms"]:.1f} tail {q["tail_ms"]:.1f}'
        print(f'  {k:3s} {lab:10s} rms5: r50 {a["rise50"]:6.1f} r90 {a["rise90"]:6.1f} tail {a["tail"]:6.1f} | hilb: r50 {b["rise50"]:6.1f} r90 {b["rise90"]:6.1f} tail {b["tail"]:6.1f} | {su}')

import json, sys
V = '/home/ksysh/r3a-dev/verify_core/'
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
try:
    x = json.load(open(V + 'xcheck_v5.json'))['v5']
    print('V5: n_present', x['n_present'], '(suite', suite['verify_A']['V5']['n_present'], ') n_sounding', x['n_sounding'], 'p95', round(x['p95_db'], 2), 'allowed drops at 5 %:', x['allowed_drops_at_5pct'])
    for k in ('P1', 'A', 'B', 'C', 'D'):
        v = x[k]; s = suite[smap[k]]['V5']
        print(f'  {k:3s} drops(local=present bins) {v["drops_local_present"]:3d} = {v["frac_local_present"]:.4f} | local=all bins {v["drops_local_allbins"]:3d} = {v["frac_local_allbins"]:.4f} | suite {s["drop_frac"]:.4f} ({round(s["drop_frac"]*s["n_present"])} bins)' + (f' | V5b median {v["v5b_median_db"]:+.2f} dB (n={v["v5b_n"]})' if 'v5b_median_db' in v else ''))
except Exception as e:
    print('no v5', e)
try:
    x = json.load(open(V + 'xcheck_v3c.json'))['v3c']
    print('V3c (stepwise 25 dB):')
    for k in ('P1', 'A', 'B', 'C', 'D'):
        v = x[k]; s = suite[smap[k]]['V3c']
        line = f'  {k:3s} range median rect {v["range_rect_median_db"]:.2f} / hann {v["range_hann_median_db"]:.2f} dB (suite {s["range_db_median"]:.2f}) | lowbin notes rect {v["lowbin_notes_rect"]} / hann {v["lowbin_notes_hann"]} (suite {s["notes_with_low_bin"]}) | worst notes {v["worst_notes_rect"]}'
        if 'enter_dom_median_ms' in v:
            line += f'\n       enter median dominant {v["enter_dom_median_ms"]:.1f} ms (suite {s["enter_ms_median"]:.1f}) any-voice {v["enter_any_median_ms"]:.1f} (suite {s["enter_ms_median_anyvoice"]:.1f}) | minus one hop {v["enter_dom_median_ms_minus_one_hop"]:.1f} | semitone {v["enter_dom_semitone_median_ms"]:.1f} wholetone {v["enter_dom_wholetone_median_ms"]:.1f} | p90 {v["enter_dom_p90_ms"]:.1f} miss {v["enter_miss"]}'
        print(line)
except Exception as e:
    print('no v3c', e)

import json, sys
x = json.load(open(sys.argv[1]))
suite = {lab: json.load(open(f'/home/ksysh/r3a-dev/core_results/{lab}/results.json'))['metrics'] for lab in ('verify_A', 'verify_B', 'verify_C', 'verify_D', 'p1_baseline')}
smap = {'A': 'verify_A', 'B': 'verify_B', 'C': 'verify_C', 'D': 'verify_D', 'P1': 'p1_baseline'}
if 'v3b' in x:
    print('V3b  range of layer/input at 300 Hz over 40-440 ms (dB):  xcheck (pooled | per-note median | per-note max)  vs suite')
    for k, v in x['v3b'].items():
        s = suite[smap[k]]['V3bare']['v3b']['range_db']
        print(f'  {k:3s} {v["range_pooled_db"]:7.3f} | {v["per_note_range_median_db"]:7.3f} | {v["per_note_range_max_db"]:7.3f}    suite {s:7.3f}   mean ratio {v["mean_ratio_db"]:.2f} dB  lat {v["lat"]}')
if 'v4' in x:
    for sig in ('bass+pink', 'bass+kick+pink'):
        print(f'V4 {sig}:  (a) std between note means dB | (b) low-bin frac [count/280] | (c) std A: global-mean / per-note-mean-removed / spread of note means / abs offset vs truth')
        for k, v in x['v4'].items():
            r = v['signals'][sig]; s = suite[smap[k]]['V4'][sig]
            c = '' if 'c_std_global_mean_db' not in r else f'  (c) {r["c_std_global_mean_db"]:.3f} / {r["c_std_per_note_mean_removed_db"]:.3f} / {r["c_note_mean_spread_db"]:.3f} / {r["c_abs_offset_vs_true_db"]:+.2f}  miss {r["c_missing_hops"]}'
            print(f'  {k:3s} (a) {r["a_std_between_notes_db"]:.3f} (suite {s["std_between_notes_db"]:.3f})  (b) {r["b_low_frac"]:.4f} [{r["b_low_bins"]}] (suite {s["low_bin_frac"]:.4f})' + c + f'  suite(c) {s["a_std_db"]}')

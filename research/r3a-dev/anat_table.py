"""Compact table of band_anatomy.py results (stem levels shifted to app defaults: +7 dB stem->app layer, native
harmonics taken at the app's dry gain of about -4 dB above 150 Hz, so layer/native at app = stem ratio + 11 dB)."""
import json, sys
import numpy as np
OFF = 11.0
for path in sys.argv[1:]:
    d = json.load(open(path)); print(f'== {path} items {d["items"]}')
    for b, v in d.items():
        if b == 'items': continue
        r = np.array(v['layer_over_native_db_k1_8']) + OFF
        add = 10 * np.log10(1 + 10 ** (r / 10))
        print(f'{b:>8} frames {v["frames"]:5d} tracked {v["tracked"]:.3f} bass_share {v["bass_share"]:.2f} (bass alone {v["bass_alone_bass_share"]:.2f}) '
              f'mix/alone {v["layer_mix_over_bass_alone_db"]:+.1f} dB')
        print('         layer share k2..5', v['layer_share_k1_8'][1:5], '| layer/native at app k2..5', [round(x, 1) for x in r[1:5]],
              '| added dB k2..5', [round(x, 2) for x in add[1:5]])
        print('         native k1..6 re mix', v['native_db_k1_8'][:6], '| bass stem k2..6 re k1', v['bass_stem_k_over_k1_db'][1:6])

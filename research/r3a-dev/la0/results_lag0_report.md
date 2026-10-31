# LA stage-0 results (/home/ksysh/r3a-dev/la0/results_lag0.json); evaluation songs = ['Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
Inputs: bh / band streams and the core v1.5 trace from the CANDIDATE lib capture (algo 15, config A); LA and P1-row tracks from the P1 REFERENCE build harmonic trace. Slakh TRAIN only.
MEASURED numbers; all rows go through the same synthesis (k=2,3 oscillators, P1 voicing-0 weights, kOutSos). core/P1 rows carry the calibrated trace-to-layer lag.
engine-row lags (s): {'core': -0.012, 'p1': -0.011}   model/features: ['logf', 'jit_c', 'dfdt_rel', 'slope_dbs', 'raw', 'res', 'ev2', 'ev3', 'len', 'has_lower', 'lower_ratio', 'near_c', 'near_ratio', 'ntr']

## E1 attack (ms)
| row | V3a peak (layer) | V3h rise90 bare | V3h rise90 25dB line | V3c.enter | onset lead10 (info) |
|---|---|---|---|---|---|
| core | 53 | 31.6 | 26.9 | 31.3 | 0.3 |
| p1 | 254 | 43.1 | 31.0 | 3.3 | -9.8 |
| LA-bh-0 | 110 | 95.7 | 60.8 | 16.6 | 16.5 |
| LA-bh-64 | 91 | 28.7 | 45.9 | 4.6 | -8.2 |
| LA-bh-120 | 81 | 37.1 | 29.4 | 21.3 | -14.4 |
| LA-bh-217 | 81 | 37.0 | 31.9 | 26.0 | 23.9 |
| LA-det-0 | 80 | inf | 24.2 | inf | -40.0 |
| LA-det-64 | 86 | 17.0 | 33.4 | 4.6 | -23.6 |
| LA-det-120 | 86 | 18.3 | 17.9 | 10.6 | -37.4 |
| LA-det-217 | 66 | 18.3 | 17.9 | 11.3 | 10.2 |
| ORA-bh-0 | 100 | 95.7 | 67.8 | 4.6 | 20.7 |
| ORA-bh-64 | 91 | 28.6 | 53.8 | 4.6 | -8.7 |
| ORA-bh-120 | 91 | 37.1 | 30.0 | 21.3 | 17.9 |
| ORA-bh-217 | 81 | 37.0 | 31.9 | 26.0 | 23.9 |
| ORA-det-0 | 90 | 47.8 | 61.9 | 4.0 | 12.8 |
| ORA-det-64 | 86 | 17.0 | 49.3 | 4.6 | -22.9 |
| ORA-det-120 | 76 | 18.3 | 18.4 | 10.6 | 8.5 |
| ORA-det-217 | 66 | 18.3 | 17.8 | 11.3 | 10.2 |

## E2 tail
| row | V3h tail settled (last >-20dB) | tail first -20dB | RERISE dB (A1) | notes RERISE>6 dB (of 38) |
|---|---|---|---|---|
| core | 59.2 | 46.7 | 5.3 | 18 |
| p1 | 120.0 | 8.2 | 7.2 | 22 |
| LA-bh-0 | 56.3 | 20.1 | 0.5 | 3 |
| LA-bh-64 | 120.0 | 53.1 | 2.4 | 7 |
| LA-bh-120 | 119.5 | 16.0 | 3.3 | 15 |
| LA-bh-217 | 14.3 | 14.3 | 0.0 | 0 |
| LA-det-0 | 120.0 | 16.1 | 0.5 | 9 |
| LA-det-64 | 120.0 | 15.3 | 7.6 | 26 |
| LA-det-120 | 120.0 | 13.9 | 4.0 | 17 |
| LA-det-217 | 12.9 | 12.9 | 0.0 | 0 |
| ORA-bh-0 | 18.3 | 18.3 | 0.0 | 0 |
| ORA-bh-64 | 120.0 | 55.2 | 1.5 | 2 |
| ORA-bh-120 | 61.6 | 15.3 | 0.6 | 13 |
| ORA-bh-217 | 14.3 | 14.3 | 0.0 | 0 |
| ORA-det-0 | 16.5 | 16.1 | 0.0 | 1 |
| ORA-det-64 | 120.0 | 13.7 | 6.3 | 20 |
| ORA-det-120 | 59.2 | 13.5 | 0.2 | 13 |
| ORA-det-217 | 12.9 | 12.9 | 0.0 | 0 |

## E3 / E4 / E5
| row | V5a T60 % | V6b wrong % | V6b wrong % (no T24) | right kept % (vs own all-on) | right weight vs core % | V7d burst 4.12 dB | V7d burst 4.73 dB |
|---|---|---|---|---|---|---|---|
| core | 5.2 | 50.6 | 47.8 | - | 100.0 | 9.8 | 3.2 |
| p1 | 16.0 | 28.0 | 23.2 | - | 83.9 | 3.2 | -34.8 |
| LA-bh-0 | 8.8 | 44.8 | 43.0 | 83.4 | 109.0 | 9.6 | 2.4 |
| LA-bh-64 | 9.8 | 33.4 | 29.7 | 96.0 | 96.2 | -0.1 | 3.0 |
| LA-bh-120 | 11.3 | 29.9 | 27.0 | 97.0 | 92.2 | -4.2 | 1.5 |
| LA-bh-217 | 10.3 | 26.4 | 24.9 | 94.8 | 83.3 | 1.3 | -1.2 |
| LA-det-0 | 10.8 | 51.1 | 49.7 | 67.2 | 151.6 | 19.4 | 6.4 |
| LA-det-64 | 6.2 | 54.4 | 44.3 | 89.4 | 137.0 | 3.5 | 3.1 |
| LA-det-120 | 8.2 | 47.4 | 40.7 | 88.3 | 131.8 | 1.6 | 0.5 |
| LA-det-217 | 11.9 | 40.8 | 35.8 | 78.6 | 111.0 | 0.2 | -2.1 |
| ORA-bh-0 | 15.5 | 9.9 | 9.7 | 95.5 | 124.8 | - | - |
| ORA-bh-64 | 11.3 | 15.3 | 15.2 | 97.9 | 98.2 | - | - |
| ORA-bh-120 | 11.9 | 14.8 | 14.5 | 97.8 | 93.0 | - | - |
| ORA-bh-217 | 13.4 | 15.8 | 15.5 | 96.9 | 85.1 | - | - |
| ORA-det-0 | 11.3 | 10.9 | 10.5 | 94.1 | 212.2 | - | - |
| ORA-det-64 | 9.3 | 19.3 | 19.0 | 94.7 | 145.1 | - | - |
| ORA-det-120 | 10.3 | 18.5 | 18.6 | 94.1 | 140.6 | - | - |
| ORA-det-217 | 13.9 | 19.0 | 19.7 | 94.6 | 133.5 | - | - |

## guards
| row | V3d bass dB | V3d line dB | V4b % | V9 births/s | V9 energy dB | V3i-sub flips/s |
|---|---|---|---|---|---|---|
| core | 0.50 | -30.0 | 1.8 | 0.0 | -140.0 | 0.00 |
| p1 | -0.51 | -11.7 | 31.1 | 57.7 | -56.2 | 7.31 |
| LA-bh-0 | 3.03 | -23.7 | 17.5 | 107.8 | -51.1 | 2.81 |
| LA-bh-64 | 1.01 | -19.0 | 22.5 | 31.0 | -55.5 | 0.00 |
| LA-bh-120 | 3.15 | -15.6 | 21.1 | 28.8 | -55.8 | 0.00 |
| LA-bh-217 | 1.53 | -54.9 | 20.7 | 27.0 | -56.2 | 0.00 |
| LA-det-0 | 3.08 | -10.7 | 20.0 | 82.1 | -48.2 | 2.81 |
| LA-det-64 | 1.89 | -12.6 | 20.7 | 30.5 | -50.3 | 0.00 |
| LA-det-120 | 3.81 | -12.0 | 20.7 | 27.9 | -50.6 | 0.00 |
| LA-det-217 | 1.27 | -54.3 | 20.0 | 25.0 | -51.2 | 0.00 |
| ORA-bh-0 | 0.05 | -50.5 | 29.6 | 0.0 | -140.0 | 2.81 |
| ORA-bh-64 | 1.01 | -20.0 | 22.1 | 0.0 | -140.0 | 0.00 |
| ORA-bh-120 | 3.15 | -28.2 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-bh-217 | 1.53 | -55.0 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-0 | 0.05 | -26.9 | 25.0 | 0.0 | -140.0 | 2.81 |
| ORA-det-64 | 1.89 | -13.7 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-120 | 3.81 | -22.4 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-217 | 1.27 | -54.8 | 17.9 | 0.0 | -140.0 | 0.00 |

## Calibration of the synthesis path (core v1.5 / P1 rows)
V6b core pooled over the 10 songs: 34.49 %  (known v1.5: 34.5 % on 10 songs);  eval-5: 50.58 %
V6b p1 pooled over the 10 songs: 17.84 %  (known P1: 17.8 %);  eval-5: 28.04 %
offsets (trace stamp -> real layer), ms: {'core': {'lag': -12, 'corr': 0.7306571930516103}, 'p1': {'lag': -11, 'corr': 0.8569911545822391}}
| row | version | bare_rise90 | line_rise90 | line_tail | line_tail_settled | rerise_db | v3a_layer_ms | v4b_low_frac | v5a_frac | v7d_4.12 | v7d_4.73 | v3d_line_median | v3d_line_suite | v3d_bass_median | v9_energy_db |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core | real | 29.7 | 28.1 | 44.2 | 60.2 | 4.8 | 52.0 | 0.03 | 0.06 | 8.0 | 2.4 | -31.7 | -7.2 | 0.4 | -111.7 |
| core | proxy_lag | 31.6 | 26.9 | 46.7 | 59.2 | 5.3 | 53.0 | 0.02 | 0.05 | 9.8 | 3.2 | -30.0 | -6.1 | 0.5 | -140.0 |
| core | proxy_nolag | 43.6 | 40.3 | 58.7 | 70.9 | 4.2 | 65.0 | 0.03 | 0.09 | 10.5 | 4.4 | -31.3 | -9.6 | 0.2 | -140.0 |
| p1 | real | 39.8 | 33.5 | 3.2 | 4.9 | 0.0 | 4.0 | 0.31 | 0.19 | -12.1 | -46.5 | -25.8 | 50.2 | -0.5 | -75.6 |
| p1 | proxy_lag | 43.1 | 31.0 | 8.2 | 120.0 | 7.2 | 254.0 | 0.31 | 0.16 | 3.2 | -34.8 | -11.7 | 33.6 | -0.5 | -56.2 |
| p1 | proxy_nolag | 54.2 | 47.2 | 16.8 | 22.7 | 0.6 | 265.0 | 0.29 | 0.17 | 2.2 | -34.7 | -23.6 | 23.2 | 0.2 | -56.3 |
(real = metric code applied to the REAL engine layer, latency compensated; proxy_lag = synthesized from the trace with the calibrated offset; the V3i values 0 / 7.3 flips/s of the suite are reproduced in the table above.)

## classifier (decision) quality, evaluation songs: weighted AUC (weights = interval A^2 sum) / unweighted AUC / fraction of right weight / fraction ON weight; joint/single ratio before the cap
| stream-L | AUC w | AUC unw | right-weight frac | ON weight frac | n intervals | joint/single p95 | p50 | frac capped (>2) |
|---|---|---|---|---|---|---|---|---|
| bh-0 | 0.766 | 0.724 | 0.437 | 0.630 | 14821 | 12.53 | 1.04 | 0.266 |
| bh-64 | 0.734 | 0.639 | 0.712 | 0.891 | 3946 | 2.39 | 1.00 | 0.068 |
| bh-120 | 0.816 | 0.640 | 0.729 | 0.881 | 3967 | 2.37 | 1.00 | 0.066 |
| bh-217 | 0.867 | 0.669 | 0.715 | 0.800 | 4037 | 2.44 | 1.00 | 0.069 |
| band-0 | 0.751 | 0.786 | 0.315 | 0.416 | 15110 | 11.97 | 1.06 | 0.262 |
| band-64 | 0.732 | 0.652 | 0.466 | 0.787 | 4032 | 2.28 | 1.00 | 0.063 |
| band-120 | 0.808 | 0.651 | 0.471 | 0.682 | 4087 | 2.31 | 1.00 | 0.062 |
| band-217 | 0.830 | 0.669 | 0.420 | 0.474 | 4226 | 2.38 | 1.00 | 0.065 |

## Decision rule (section 14 + amendment A1), applied mechanically

### (i) guards: which guard each LA row fails (limits: V3d <= 1 dB (bass: suite form, gated line: plain form), V4b <= 2 %, V9 births <= P1 proxy, V9 energy <= P1 proxy + 3 dB, V3i-sub <= 1/s, right weight kept >= 90 %)
| row | failing guards |
|---|---|
| core | none |
| LA-bh-0 | V3d bass <=1 dB, V4b <=2 %, V9 births <= P1, V9 energy <= P1+3 dB, V3i <=1 /s, right weight kept >=90 % |
| LA-bh-64 | V3d bass <=1 dB, V4b <=2 % |
| LA-bh-120 | V3d bass <=1 dB, V4b <=2 % |
| LA-bh-217 | V3d bass <=1 dB, V4b <=2 % |
| LA-det-0 | V3d bass <=1 dB, V4b <=2 %, V9 births <= P1, V9 energy <= P1+3 dB, V3i <=1 /s, right weight kept >=90 % |
| LA-det-64 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, right weight kept >=90 % |
| LA-det-120 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, right weight kept >=90 % |
| LA-det-217 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, right weight kept >=90 % |
(core: the guard list is shown for reference; right weight kept is n/a for core.)  Real-P1 references for V9 energy / V7d are in the calibration table.
stream choice, per endpoint: bh wins 5, band wins 8 -> band;   per group (E1..E5 at L=64 and 217): bh 3, band 4 (L64/E1:band L64/E2:tie L64/E3:band L64/E4:bh L64/E5:bh L217/E1:band L217/E2:tie L217/E3:tie L217/E4:bh L217/E5:band) -> band
(either counting unit gives STOP below; band wins E1 on the pre-HPSS stream, whose rows carry 114-140 % of the core right weight (table above) and fail the V9-energy guard and, at L = 120/217, the right-weight-kept guard)
V9 energy on the real-P1 basis: real P1 layer on pink -30 dBFS = -75.6 dB, limit -72.6; the proxy-P1 basis gives -53.2.  Rows failing on the REAL basis: LA-bh-0, LA-bh-64, LA-bh-120, LA-bh-217, LA-det-0, LA-det-64, LA-det-120, LA-det-217 (LA rows put 19 to 27 dB more layer on pure pink than the real P1 outputs)
V7d limit both ways: proxy-P1 basis max(+3, 4.2) / max(+3, -33.8) dB; real-P1 basis (layer burst of the real P1 -12.1 / -46.5 dB): +3.0 dB.
oracle diagnostic (section 14): V6b of the per-interval MIDI oracle 9.9-19.3 % vs P1 proxy + 2 %p = 30.0 % -> the oracle REACHES P1 + 2 %p: the limit is the classifier (the interval unit is not the limit)

### stream bh
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: False)
   guards: V3d bass <=1 dB: 1.525 FAIL; V3d line <=1 dB: -54.869 ok; V4b <=2 %: 0.207 FAIL; V9 births <= P1: 27.021 ok; V9 energy <= P1+3 dB: -56.174 ok; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.948 ok
   (a) V6b delta -7.03 %p (noT24 -4.84), songs negative 3/5 (noT24 3/4), CI95 [-11.77, -3.97] %p -> value met True, with evidence False
   (b) dV5a 0.52 %p, d rise90 bare 8.3 ms, line -13.9 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -105.7 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -38.8 ms, d RERISE -2.4 dB -> met False
   right-weight retention delta -1.20 %p, per song {'Track00020': 0.0054, 'Track00023': -0.0004, 'Track00024': -0.4102, 'Track00025': -0.0066, 'Track00026': -0.0042}, songs up 1 / down 4 of 5, CI95 [-4.18, 1.88]
   V6b per-song deltas (%p): 20: -6.66, 23: -1.05, 24: +0.71, 25: +0.28, 26: -10.38
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.009 FAIL; V3d line <=1 dB: -19.014 ok; V4b <=2 %: 0.225 FAIL; V9 births <= P1: 30.957 ok; V9 energy <= P1+3 dB: -55.498 ok; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.960 ok
   (a) V6b delta -11.37 %p (noT24 -13.29), songs negative 4/5 (noT24 4/4), CI95 [-16.34, -4.37] %p -> value met True, with evidence True
   (b) dV5a 1.03 %p, d rise90 bare -67.0 ms, line -14.9 ms -> met (AND) False  [OR variant False]
   (c) d tail settled 63.7 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing 33.0 ms, d RERISE 1.9 dB -> met False
   right-weight retention delta 12.58 %p, per song {'Track00020': 0.0867, 'Track00023': 0.0793, 'Track00024': -0.1015, 'Track00025': 0.2036, 'Track00026': 0.0952}, songs up 4 / down 1 of 5, CI95 [5.16, 20.68]
   V6b per-song deltas (%p): 20: -16.41, 23: -35.00, 24: +7.42, 25: -20.39, 26: -1.66
LA(64) vs core v1.5 proxy, groups: E1: wins 1 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 1 -; E4: wins 2 losses 0 BETTER; E5: wins 1 losses 0 BETTER  -> 2 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False
   (ii) endpoints alone, guards ignored: 300 ms condition False, 150 ms condition False

### stream band
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.269 FAIL; V3d line <=1 dB: -54.331 ok; V4b <=2 %: 0.200 FAIL; V9 births <= P1: 25.000 ok; V9 energy <= P1+3 dB: -51.210 FAIL; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.786 FAIL
   (a) V6b delta -13.68 %p (noT24 -8.46), songs negative 5/5 (noT24 4/4), CI95 [-19.67, -9.04] %p -> value met True, with evidence True
   (b) dV5a 5.67 %p, d rise90 bare 1.3 ms, line -15.5 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -107.1 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -2.5 ms, d RERISE -7.6 dB -> met True  (met only through the contaminated settled tail; with the first-crossing tail it would be False)
   right-weight retention delta -10.77 %p, per song {'Track00020': -0.056, 'Track00023': -0.0037, 'Track00024': -0.4443, 'Track00025': -0.0546, 'Track00026': -0.0052}, songs up 0 / down 5 of 5, CI95 [-18.14, -4.03]
   V6b per-song deltas (%p): 20: -13.95, 23: -1.79, 24: -3.71, 25: -2.33, 26: -12.36
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: False)
   guards: V3d bass <=1 dB: 1.891 FAIL; V3d line <=1 dB: -12.597 ok; V4b <=2 %: 0.207 FAIL; V9 births <= P1: 30.532 ok; V9 energy <= P1+3 dB: -50.283 FAIL; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.894 FAIL
   (a) V6b delta 3.34 %p (noT24 -5.42), songs negative 3/5 (noT24 3/4), CI95 [-3.20, 11.98] %p -> value met False, with evidence False
   (b) dV5a -4.64 %p, d rise90 bare inf ms, line 9.2 ms -> met (AND) False  [OR variant True]
   (c) d tail settled 0.0 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -0.8 ms, d RERISE 7.1 dB -> met False
   right-weight retention delta 22.20 %p, per song {'Track00020': 0.1293, 'Track00023': 0.0826, 'Track00024': 0.3415, 'Track00025': 0.2842, 'Track00026': 0.1523}, songs up 5 / down 0 of 5, CI95 [15.96, 27.79]
   V6b per-song deltas (%p): 20: -2.94, 23: -35.11, 24: +17.69, 25: -10.78, 26: +3.16
LA(64) vs core v1.5 proxy, groups: E1: wins 2 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 0 -; E4: wins 0 losses 0 -; E5: wins 1 losses 0 BETTER  -> 1 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False
   (ii) endpoints alone, guards ignored: 300 ms condition True, 150 ms condition False

### E4 versus core v1.5 (LA with the classifier minus core; V6b = wrong share)
bh-64: V6b delta -17.17 %p CI95 [-21.41, -11.47]; without T24 -18.12 [-22.55, -11.85]; per song 20: -11.26, 23: -19.67, 24: -2.44, 25: -19.39, 26: -17.38; songs negative 5/5; right weight vs core per song 20: -11.3%, 23: -30.1%, 24: +45.7%, 25: -2.3%, 26: +1.8%
bh-217: V6b delta -24.20 %p CI95 [-29.01, -18.59]; without T24 -22.97 [-27.98, -16.80]; per song 20: -17.91, 23: -20.72, 24: -1.73, 25: -19.11, 26: -27.76; songs negative 5/5; right weight vs core per song 20: -14.2%, 23: -38.1%, 24: -63.1%, 25: -23.4%, 26: -7.8%
band-64: V6b delta +3.86 %p CI95 [-2.31, 12.38]; without T24 -3.54 [-8.07, 3.45]; per song 20: +14.70, 23: -18.20, 24: -4.05, 25: -5.80, 26: -9.63; songs negative 4/5; right weight vs core per song 20: +32.0%, 23: -12.2%, 24: +1367.4%, 25: +35.6%, 26: +36.5%
band-217: V6b delta -9.82 %p CI95 [-14.59, -3.98]; without T24 -12.01 [-16.84, -6.01]; per song 20: +0.75, 23: -19.99, 24: -7.77, 25: -8.14, 26: -21.99; songs negative 4/5; right weight vs core per song 20: +22.2%, 23: -22.5%, 24: +536.8%, 25: -4.0%, 26: +21.1%

OUTCOME: STOP the lookahead direction; review v1.6 (section 13) and the v2 estimator   (chosen stream band; the other stream alone would give: stop)
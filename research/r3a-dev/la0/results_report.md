# LA stage-0 results (/home/ksysh/r3a-dev/la0/results.json); evaluation songs = ['Track00020', 'Track00023', 'Track00024', 'Track00025', 'Track00026']
Inputs: bh / band streams and the core v1.5 trace from the CANDIDATE lib capture (algo 15, config A); LA and P1-row tracks from the P1 REFERENCE build harmonic trace. Slakh TRAIN only.
MEASURED numbers; all rows go through the same synthesis (k=2,3 oscillators, P1 voicing-0 weights, kOutSos). core/P1 rows carry the calibrated trace-to-layer lag.
engine-row lags (s): {'core': -0.012, 'p1': -0.011}   model/features: ['logf', 'jit_c', 'dfdt_rel', 'slope_dbs', 'raw', 'res', 'ev2', 'ev3', 'len', 'has_lower', 'lower_ratio', 'near_c', 'near_ratio', 'ntr']

## E1 attack (ms)
| row | V3a peak (layer) | V3h rise90 bare | V3h rise90 25dB line | V3c.enter | onset lead10 (info) |
|---|---|---|---|---|---|
| core | 53 | 31.6 | 26.9 | 31.3 | 0.3 |
| p1 | 254 | 43.1 | 31.0 | 3.3 | -9.8 |
| LA-bh-0 | 52 | 64.7 | 41.9 | 66.0 | 15.5 |
| LA-bh-64 | 91 | 28.6 | 45.7 | 4.6 | -7.8 |
| LA-bh-120 | 81 | 37.1 | 29.5 | 21.3 | -14.4 |
| LA-bh-217 | 71 | 37.0 | 31.9 | 26.0 | 23.9 |
| LA-det-0 | 54 | 32.9 | 21.2 | inf | -40.0 |
| LA-det-64 | 86 | 17.0 | 33.2 | 4.6 | -23.6 |
| LA-det-120 | 86 | 18.3 | 18.3 | 10.6 | -35.2 |
| LA-det-217 | 56 | 18.3 | 17.9 | 11.3 | 10.2 |
| ORA-bh-0 | 113 | 64.8 | 68.6 | 34.0 | 21.4 |
| ORA-bh-64 | 91 | 28.6 | 52.9 | 4.6 | -8.6 |
| ORA-bh-120 | 91 | 37.1 | 30.0 | 21.3 | 17.9 |
| ORA-bh-217 | 81 | 37.0 | 31.9 | 26.0 | 23.9 |
| ORA-det-0 | 103 | 32.9 | 54.2 | 36.6 | 13.3 |
| ORA-det-64 | 86 | 17.0 | 46.3 | 4.6 | -20.7 |
| ORA-det-120 | 76 | 18.3 | 18.4 | 10.6 | 8.5 |
| ORA-det-217 | 66 | 18.3 | 17.8 | 11.3 | 10.2 |

## E2 tail
| row | V3h tail settled (last >-20dB) | tail first -20dB | RERISE dB (A1) | notes RERISE>6 dB (of 38) |
|---|---|---|---|---|
| core | 59.2 | 46.7 | 5.3 | 18 |
| p1 | 120.0 | 8.2 | 7.2 | 22 |
| LA-bh-0 | 45.7 | 24.1 | 0.1 | 4 |
| LA-bh-64 | 120.0 | 50.3 | 2.0 | 5 |
| LA-bh-120 | 119.5 | 16.1 | 3.1 | 15 |
| LA-bh-217 | 14.3 | 14.3 | 0.0 | 0 |
| LA-det-0 | 120.0 | 38.1 | 0.0 | 9 |
| LA-det-64 | 120.0 | 14.8 | 7.1 | 24 |
| LA-det-120 | 120.0 | 14.2 | 4.4 | 17 |
| LA-det-217 | 12.9 | 12.9 | 0.0 | 0 |
| ORA-bh-0 | 19.0 | 18.7 | 0.0 | 0 |
| ORA-bh-64 | 120.0 | 50.2 | 1.3 | 1 |
| ORA-bh-120 | 61.7 | 15.4 | 0.7 | 13 |
| ORA-bh-217 | 14.3 | 14.3 | 0.0 | 0 |
| ORA-det-0 | 16.1 | 16.0 | 0.0 | 0 |
| ORA-det-64 | 120.0 | 13.6 | 5.5 | 17 |
| ORA-det-120 | 59.3 | 13.5 | 0.3 | 13 |
| ORA-det-217 | 12.9 | 12.9 | 0.0 | 0 |

## E3 / E4 / E5
| row | V5a T60 % | V6b wrong % | V6b wrong % (no T24) | right kept % (vs own all-on) | right weight vs core % | V7d burst 4.12 dB | V7d burst 4.73 dB |
|---|---|---|---|---|---|---|---|
| core | 5.2 | 50.6 | 47.8 | - | 100.0 | 9.8 | 3.2 |
| p1 | 16.0 | 28.0 | 23.2 | - | 83.9 | 3.2 | -34.8 |
| LA-bh-0 | 16.0 | 51.3 | 50.2 | 77.4 | 99.5 | 7.2 | 5.3 |
| LA-bh-64 | 12.4 | 33.1 | 29.5 | 95.5 | 93.8 | -2.4 | 3.1 |
| LA-bh-120 | 9.8 | 30.3 | 27.2 | 97.6 | 92.7 | -4.1 | 1.4 |
| LA-bh-217 | 10.8 | 27.2 | 25.8 | 96.0 | 84.3 | 1.3 | -1.2 |
| LA-det-0 | 9.3 | 53.3 | 52.1 | 60.7 | 131.0 | 18.0 | 4.1 |
| LA-det-64 | 12.4 | 54.4 | 44.9 | 90.5 | 140.3 | 2.2 | 2.8 |
| LA-det-120 | 7.2 | 49.0 | 41.8 | 87.9 | 131.3 | 1.4 | 0.5 |
| LA-det-217 | 11.9 | 43.2 | 38.5 | 81.1 | 114.5 | 0.1 | -2.3 |
| ORA-bh-0 | 18.0 | 12.1 | 12.0 | 94.0 | 120.9 | - | - |
| ORA-bh-64 | 14.9 | 14.1 | 13.9 | 97.4 | 95.6 | - | - |
| ORA-bh-120 | 11.9 | 14.9 | 14.7 | 98.1 | 93.2 | - | - |
| ORA-bh-217 | 13.4 | 15.8 | 15.5 | 96.9 | 85.1 | - | - |
| ORA-det-0 | 9.8 | 13.1 | 12.5 | 88.2 | 190.3 | - | - |
| ORA-det-64 | 14.4 | 17.8 | 17.5 | 94.1 | 145.8 | - | - |
| ORA-det-120 | 9.8 | 18.4 | 18.6 | 93.9 | 140.2 | - | - |
| ORA-det-217 | 13.9 | 19.0 | 19.7 | 94.6 | 133.5 | - | - |

## guards
| row | V3d bass dB | V3d line dB | V4b % | V9 births/s | V9 energy dB | V3i-sub flips/s |
|---|---|---|---|---|---|---|
| core | 0.50 | -30.0 | 1.8 | 0.0 | -140.0 | 0.00 |
| p1 | -0.51 | -11.7 | 31.1 | 57.7 | -56.2 | 7.31 |
| LA-bh-0 | -0.00 | -26.7 | 24.6 | 100.9 | -51.4 | 2.92 |
| LA-bh-64 | 1.01 | -19.6 | 25.4 | 39.8 | -55.6 | 2.81 |
| LA-bh-120 | 3.15 | -15.6 | 21.1 | 29.1 | -55.8 | 0.00 |
| LA-bh-217 | 1.53 | -54.8 | 20.7 | 25.5 | -56.2 | 0.00 |
| LA-det-0 | 0.01 | -9.8 | 21.8 | 64.7 | -49.7 | 2.92 |
| LA-det-64 | 1.89 | -13.4 | 23.6 | 40.7 | -50.2 | 3.26 |
| LA-det-120 | 3.81 | -12.0 | 20.7 | 27.4 | -50.6 | 0.00 |
| LA-det-217 | 1.27 | -54.3 | 20.0 | 24.7 | -51.2 | 0.00 |
| ORA-bh-0 | -0.00 | -55.5 | 29.6 | 0.0 | -140.0 | 2.92 |
| ORA-bh-64 | 1.01 | -20.7 | 26.1 | 0.0 | -140.0 | 2.81 |
| ORA-bh-120 | 3.15 | -28.1 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-bh-217 | 1.53 | -55.0 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-0 | 0.01 | -35.3 | 25.7 | 0.0 | -140.0 | 2.92 |
| ORA-det-64 | 1.89 | -14.8 | 25.4 | 0.0 | -140.0 | 3.26 |
| ORA-det-120 | 3.81 | -22.5 | 21.4 | 0.0 | -140.0 | 0.00 |
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
| bh-0 | 0.785 | 0.779 | 0.343 | 0.518 | 15111 | 11.51 | 1.05 | 0.270 |
| bh-64 | 0.723 | 0.624 | 0.688 | 0.870 | 4813 | 2.45 | 1.00 | 0.071 |
| bh-120 | 0.744 | 0.626 | 0.732 | 0.892 | 3967 | 2.37 | 1.00 | 0.065 |
| bh-217 | 0.864 | 0.646 | 0.715 | 0.820 | 4037 | 2.43 | 1.00 | 0.069 |
| band-0 | 0.784 | 0.783 | 0.222 | 0.286 | 15532 | 11.44 | 1.09 | 0.277 |
| band-64 | 0.725 | 0.649 | 0.438 | 0.766 | 4954 | 2.32 | 1.00 | 0.064 |
| band-120 | 0.787 | 0.647 | 0.469 | 0.701 | 4087 | 2.30 | 1.00 | 0.062 |
| band-217 | 0.823 | 0.653 | 0.420 | 0.510 | 4226 | 2.38 | 1.00 | 0.065 |

## Decision rule (section 14 + amendment A1), applied mechanically

### (i) guards: which guard each LA row fails (limits: V3d <= 1 dB (bass: suite form, gated line: plain form), V4b <= 2 %, V9 births <= P1 proxy, V9 energy <= P1 proxy + 3 dB, V3i-sub <= 1/s, right weight kept >= 90 %)
| row | failing guards |
|---|---|
| core | none |
| LA-bh-0 | V4b <=2 %, V9 births <= P1, V9 energy <= P1+3 dB, V3i <=1 /s, right weight kept >=90 % |
| LA-bh-64 | V3d bass <=1 dB, V4b <=2 %, V3i <=1 /s |
| LA-bh-120 | V3d bass <=1 dB, V4b <=2 % |
| LA-bh-217 | V3d bass <=1 dB, V4b <=2 % |
| LA-det-0 | V4b <=2 %, V9 births <= P1, V9 energy <= P1+3 dB, V3i <=1 /s, right weight kept >=90 % |
| LA-det-64 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, V3i <=1 /s |
| LA-det-120 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, right weight kept >=90 % |
| LA-det-217 | V3d bass <=1 dB, V4b <=2 %, V9 energy <= P1+3 dB, right weight kept >=90 % |
(core: the guard list is shown for reference; right weight kept is n/a for core.)  Real-P1 references for V9 energy / V7d are in the calibration table.
stream choice, per endpoint: bh wins 5, band wins 8 -> band;   per group (E1..E5 at L=64 and 217): bh 3, band 3 (L64/E1:band L64/E2:tie L64/E3:tie L64/E4:bh L64/E5:bh L217/E1:band L217/E2:tie L217/E3:tie L217/E4:bh L217/E5:band) -> bh
(either counting unit gives STOP below; band wins E1 on the pre-HPSS stream, whose rows carry 114-140 % of the core right weight (table above) and fail the V9-energy guard and, at L = 120/217, the right-weight-kept guard)
V9 energy on the real-P1 basis: real P1 layer on pink -30 dBFS = -75.6 dB, limit -72.6; the proxy-P1 basis gives -53.2.  Rows failing on the REAL basis: LA-bh-0, LA-bh-64, LA-bh-120, LA-bh-217, LA-det-0, LA-det-64, LA-det-120, LA-det-217 (LA rows put 19 to 26 dB more layer on pure pink than the real P1 outputs)
V7d limit both ways: proxy-P1 basis max(+3, 4.2) / max(+3, -33.8) dB; real-P1 basis (layer burst of the real P1 -12.1 / -46.5 dB): +3.0 dB.
oracle diagnostic (section 14): V6b of the per-interval MIDI oracle 12.1-19.0 % vs P1 proxy + 2 %p = 30.0 % -> the oracle REACHES P1 + 2 %p: the limit is the classifier (the interval unit is not the limit)

### stream bh
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.525 FAIL; V3d line <=1 dB: -54.806 ok; V4b <=2 %: 0.207 FAIL; V9 births <= P1: 25.532 ok; V9 energy <= P1+3 dB: -56.223 ok; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.960 ok
   (a) V6b delta -5.89 %p (noT24 -3.72), songs negative 4/5 (noT24 4/4), CI95 [-9.30, -3.33] %p -> value met True, with evidence True
   (b) dV5a -1.55 %p, d rise90 bare 8.3 ms, line -13.8 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -105.7 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -35.9 ms, d RERISE -2.0 dB -> met False
   right-weight retention delta 0.44 %p, per song {'Track00020': 0.038, 'Track00023': -0.0002, 'Track00024': -0.4054, 'Track00025': 0.0173, 'Track00026': -0.0009}, songs up 2 / down 3 of 5, CI95 [-1.70, 2.31]
   V6b per-song deltas (%p): 20: -5.74, 23: -2.78, 24: +1.66, 25: -2.49, 26: -2.46
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.009 FAIL; V3d line <=1 dB: -19.601 ok; V4b <=2 %: 0.254 FAIL; V9 births <= P1: 39.787 ok; V9 energy <= P1+3 dB: -55.571 ok; V3i <=1 /s: 2.812 FAIL; right weight kept >=90 %: 0.955 ok
   (a) V6b delta -18.24 %p (noT24 -20.67), songs negative 4/5 (noT24 4/4), CI95 [-23.21, -11.49] %p -> value met True, with evidence True
   (b) dV5a -3.61 %p, d rise90 bare -36.1 ms, line 3.8 ms -> met (AND) False  [OR variant True]
   (c) d tail settled 74.3 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing 26.2 ms, d RERISE 1.8 dB -> met False
   right-weight retention delta 18.16 %p, per song {'Track00020': 0.1037, 'Track00023': 0.081, 'Track00024': -0.0931, 'Track00025': 0.2913, 'Track00026': 0.1533}, songs up 4 / down 1 of 5, CI95 [12.22, 23.73]
   V6b per-song deltas (%p): 20: -22.80, 23: -33.09, 24: +11.89, 25: -27.27, 26: -11.30
LA(64) vs core v1.5 proxy, groups: E1: wins 1 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 1 -; E4: wins 2 losses 0 BETTER; E5: wins 1 losses 0 BETTER  -> 2 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False
   (ii) endpoints alone, guards ignored: 300 ms condition True, 150 ms condition False

### stream band
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.269 FAIL; V3d line <=1 dB: -54.339 ok; V4b <=2 %: 0.200 FAIL; V9 births <= P1: 24.681 ok; V9 energy <= P1+3 dB: -51.177 FAIL; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.811 FAIL
   (a) V6b delta -11.14 %p (noT24 -6.39), songs negative 5/5 (noT24 4/4), CI95 [-15.44, -8.03] %p -> value met True, with evidence True
   (b) dV5a -0.52 %p, d rise90 bare 1.3 ms, line -15.3 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -107.1 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -1.9 ms, d RERISE -7.1 dB -> met True  (met only through the contaminated settled tail; with the first-crossing tail it would be False)
   right-weight retention delta -9.42 %p, per song {'Track00020': -0.0517, 'Track00023': -0.0032, 'Track00024': -0.4625, 'Track00025': -0.0195, 'Track00026': 0.0061}, songs up 1 / down 4 of 5, CI95 [-17.74, -2.70]
   V6b per-song deltas (%p): 20: -12.80, 23: -4.01, 24: -1.99, 25: -3.52, 26: -3.60
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: False)
   guards: V3d bass <=1 dB: 1.891 FAIL; V3d line <=1 dB: -13.439 ok; V4b <=2 %: 0.236 FAIL; V9 births <= P1: 40.745 ok; V9 energy <= P1+3 dB: -50.215 FAIL; V3i <=1 /s: 3.262 FAIL; right weight kept >=90 %: 0.905 ok
   (a) V6b delta 1.10 %p (noT24 -7.16), songs negative 4/5 (noT24 4/4), CI95 [-5.74, 8.88] %p -> value met False, with evidence False
   (b) dV5a 3.09 %p, d rise90 bare -16.0 ms, line 12.0 ms -> met (AND) False  [OR variant False]
   (c) d tail settled 0.0 ms [window ends 5 ms before the next onset: contaminated by pre-echo when 120], d tail first-crossing -23.4 ms, d RERISE 7.1 dB -> met False
   right-weight retention delta 29.82 %p, per song {'Track00020': 0.1324, 'Track00023': 0.2304, 'Track00024': 0.1989, 'Track00025': 0.4567, 'Track00026': 0.2641}, songs up 5 / down 0 of 5, CI95 [20.71, 36.18]
   V6b per-song deltas (%p): 20: -5.46, 23: -32.55, 24: +23.85, 25: -15.02, 26: -1.75
LA(64) vs core v1.5 proxy, groups: E1: wins 2 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 1 -; E4: wins 0 losses 0 -; E5: wins 1 losses 0 BETTER  -> 1 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False
   (ii) endpoints alone, guards ignored: 300 ms condition True, 150 ms condition False

### E4 versus core v1.5 (LA with the classifier minus core; V6b = wrong share)
bh-64: V6b delta -17.48 %p CI95 [-21.74, -12.14]; without T24 -18.34 [-22.80, -12.54]; per song 20: -11.77, 23: -18.28, 24: -3.13, 25: -17.81, 26: -20.57; songs negative 5/5; right weight vs core per song 20: -14.2%, 23: -32.9%, 24: +58.4%, 25: -6.5%, 26: +1.7%
bh-217: V6b delta -23.37 %p CI95 [-28.22, -17.45]; without T24 -22.06 [-27.22, -15.46]; per song 20: -17.51, 23: -21.06, 24: -1.47, 25: -20.31, 26: -23.03; songs negative 5/5; right weight vs core per song 20: -14.2%, 23: -38.1%, 24: -66.2%, 25: -21.1%, 26: -7.4%
band-64: V6b delta +3.77 %p CI95 [-2.11, 11.95]; without T24 -2.92 [-7.93, 4.66]; per song 20: +16.27, 23: -16.54, 24: -5.48, 25: -5.31, 26: -11.37; songs negative 4/5; right weight vs core per song 20: +34.6%, 23: -15.9%, 24: +1674.8%, 25: +42.6%, 26: +34.2%
band-217: V6b delta -7.37 %p CI95 [-11.52, -1.81]; without T24 -9.32 [-13.61, -3.36]; per song 20: +3.47, 23: -20.55, 24: -7.47, 25: -8.83, 26: -14.98; songs negative 4/5; right weight vs core per song 20: +13.0%, 23: -22.4%, 24: +562.2%, 25: +9.5%, 26: +21.1%

OUTCOME: STOP the lookahead direction; review v1.6 (section 13) and the v2 estimator   (chosen stream band; the other stream alone would give: stop)
# LA stage-0 results (/home/ksysh/r3a-dev/la0/dev3.json); evaluation songs = ['Track00060', 'Track00040', 'Track00001', 'Track00005', 'Track00012']  [DEV: in-sample train songs, sanity only]
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
| core | 5.2 | 21.1 | 21.1 | - | 100.0 | 9.8 | 3.2 |
| p1 | 16.0 | 11.8 | 11.8 | - | 90.6 | 3.2 | -34.8 |
| LA-bh-0 | 16.0 | 28.6 | 28.6 | 72.5 | 105.2 | 7.2 | 5.3 |
| LA-bh-64 | 12.4 | 11.9 | 11.9 | 99.2 | 108.5 | -2.4 | 3.1 |
| LA-bh-120 | 9.8 | 10.1 | 10.1 | 99.1 | 105.7 | -4.1 | 1.4 |
| LA-bh-217 | 10.8 | 9.4 | 9.4 | 99.0 | 100.1 | 1.3 | -1.2 |
| LA-det-0 | 9.3 | 30.1 | 30.1 | 58.2 | 138.5 | 18.0 | 4.1 |
| LA-det-64 | 12.4 | 23.5 | 23.5 | 95.0 | 138.9 | 2.2 | 2.8 |
| LA-det-120 | 7.2 | 20.5 | 20.5 | 96.9 | 135.4 | 1.4 | 0.5 |
| LA-det-217 | 11.9 | 16.9 | 16.9 | 94.6 | 124.1 | 0.1 | -2.3 |
| ORA-bh-0 | 18.0 | 8.5 | 8.5 | 97.2 | 141.0 | - | - |
| ORA-bh-64 | 14.9 | 6.3 | 6.3 | 99.0 | 108.4 | - | - |
| ORA-bh-120 | 11.9 | 6.7 | 6.7 | 99.2 | 105.8 | - | - |
| ORA-bh-217 | 13.4 | 7.3 | 7.3 | 99.3 | 100.4 | - | - |
| ORA-det-0 | 9.8 | 10.2 | 10.2 | 94.2 | 224.0 | - | - |
| ORA-det-64 | 14.4 | 10.1 | 10.1 | 96.4 | 141.0 | - | - |
| ORA-det-120 | 9.8 | 10.3 | 10.3 | 97.9 | 136.7 | - | - |
| ORA-det-217 | 13.9 | 10.5 | 10.5 | 98.1 | 128.6 | - | - |

## guards
| row | V3d bass dB | V3d line dB | V4b % | V9 births/s | V9 energy dB | V3i-sub flips/s |
|---|---|---|---|---|---|---|
| core | 0.50 | -6.1 | 1.8 | 0.0 | -140.0 | 0.00 |
| p1 | -0.51 | 33.6 | 31.1 | 57.7 | -56.2 | 7.31 |
| LA-bh-0 | -0.00 | 15.5 | 24.6 | 100.9 | -51.4 | 2.92 |
| LA-bh-64 | 1.01 | 9.8 | 25.4 | 39.8 | -55.6 | 2.81 |
| LA-bh-120 | 3.15 | 25.2 | 21.1 | 29.1 | -55.8 | 0.00 |
| LA-bh-217 | 1.53 | 45.0 | 20.7 | 25.5 | -56.2 | 0.00 |
| LA-det-0 | 0.01 | -0.8 | 21.8 | 64.7 | -49.7 | 2.92 |
| LA-det-64 | 1.89 | 30.5 | 23.6 | 40.7 | -50.2 | 3.26 |
| LA-det-120 | 3.81 | 28.9 | 20.7 | 27.4 | -50.6 | 0.00 |
| LA-det-217 | 1.27 | 45.4 | 20.0 | 24.7 | -51.2 | 0.00 |
| ORA-bh-0 | -0.00 | 44.6 | 29.6 | 0.0 | -140.0 | 2.92 |
| ORA-bh-64 | 1.01 | 10.8 | 26.1 | 0.0 | -140.0 | 2.81 |
| ORA-bh-120 | 3.15 | 39.8 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-bh-217 | 1.53 | 45.4 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-0 | 0.01 | 55.2 | 25.7 | 0.0 | -140.0 | 2.92 |
| ORA-det-64 | 1.89 | 40.5 | 25.4 | 0.0 | -140.0 | 3.26 |
| ORA-det-120 | 3.81 | 35.9 | 21.4 | 0.0 | -140.0 | 0.00 |
| ORA-det-217 | 1.27 | 46.0 | 17.9 | 0.0 | -140.0 | 0.00 |

## Calibration of the synthesis path (core v1.5 / P1 rows)
offsets (trace stamp -> real layer), ms: {'core': {'lag': -12, 'corr': 0.7306571930516103}, 'p1': {'lag': -11, 'corr': 0.8569911545822391}}
| row | version | bare_rise90 | line_rise90 | line_tail | line_tail_settled | rerise_db | v3a_layer_ms | v4b_low_frac | v5a_frac | v7d_4.12 | v7d_4.73 | v3d_line_median | v3d_bass_median |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core | real | 29.7 | 28.1 | 44.2 | 60.2 | 4.8 | 52.0 | 0.03 | 0.06 | 8.0 | 2.4 | -7.2 | 0.4 |
| core | proxy_lag | 31.6 | 26.9 | 46.7 | 59.2 | 5.3 | 53.0 | 0.02 | 0.05 | 9.8 | 3.2 | -6.1 | 0.5 |
| core | proxy_nolag | 43.6 | 40.3 | 58.7 | 70.9 | 4.2 | 65.0 | 0.03 | 0.09 | 10.5 | 4.4 | -9.6 | 0.2 |
| p1 | real | 39.8 | 33.5 | 3.2 | 4.9 | 0.0 | 4.0 | 0.31 | 0.19 | -12.1 | -46.5 | 50.2 | -0.5 |
| p1 | proxy_lag | 43.1 | 31.0 | 8.2 | 120.0 | 7.2 | 254.0 | 0.31 | 0.16 | 3.2 | -34.8 | 33.6 | -0.5 |
| p1 | proxy_nolag | 54.2 | 47.2 | 16.8 | 22.7 | 0.6 | 265.0 | 0.29 | 0.17 | 2.2 | -34.7 | 23.2 | 0.2 |
(real = metric code applied to the REAL engine layer, latency compensated; proxy_lag = synthesized from the trace with the calibrated offset; the V3i values 0 / 7.3 flips/s of the suite are reproduced in the table above.)

## classifier (decision) quality, evaluation songs: weighted AUC (weights = interval A^2 sum) / unweighted AUC / fraction of right weight / fraction ON weight; joint/single ratio before the cap
| stream-L | AUC w | AUC unw | right-weight frac | ON weight frac | n intervals | joint/single p95 | p50 | frac capped (>2) |
|---|---|---|---|---|---|---|---|---|
| bh-0 | 0.820 | 0.801 | 0.527 | 0.515 | 14619 | 9.37 | 1.00 | 0.231 |
| bh-64 | 0.867 | 0.708 | 0.881 | 0.940 | 5185 | 2.39 | 1.00 | 0.068 |
| bh-120 | 0.893 | 0.743 | 0.901 | 0.935 | 4227 | 2.29 | 1.00 | 0.062 |
| bh-217 | 0.958 | 0.767 | 0.907 | 0.925 | 4233 | 2.27 | 1.00 | 0.062 |
| band-0 | 0.810 | 0.794 | 0.404 | 0.323 | 15235 | 9.42 | 1.02 | 0.244 |
| band-64 | 0.838 | 0.732 | 0.686 | 0.795 | 5185 | 2.21 | 1.00 | 0.060 |
| band-120 | 0.890 | 0.750 | 0.731 | 0.815 | 4231 | 2.05 | 1.00 | 0.052 |
| band-217 | 0.942 | 0.738 | 0.727 | 0.751 | 4236 | 2.07 | 1.00 | 0.053 |

## Decision rule (section 14 + amendment A1), applied mechanically
stream choice: bh wins 5, band wins 8 -> band

### stream bh
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: False)
   guards: V3d bass <=1 dB: 1.525 FAIL; V3d line <=1 dB: 44.956 FAIL; V4b <=2 %: 0.207 FAIL; V9 births <= P1: 25.532 ok; V9 energy <= P1+3 dB: -56.223 ok; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.990 ok
   (a) V6b delta -2.41 %p (noT24 -2.41), songs negative 5/5 (noT24 5/4), CI95 [-3.51, -1.53] %p -> value met False, with evidence False
   (b) dV5a -1.55 %p, d rise90 bare 8.3 ms, line -13.8 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -105.7 ms, d RERISE -2.0 dB -> met False
   right-weight retention delta -0.18 %p, per song {'Track00060': -0.0014, 'Track00040': 0.0071, 'Track00001': -0.0029, 'Track00005': -0.0115, 'Track00012': -0.0019}, CI95 [-0.48, 0.14]
   V6b per-song deltas (%p): 60: -1.46, 40: -3.71, 01: -0.79, 05: -6.85, 12: -4.65
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: False)
   guards: V3d bass <=1 dB: 1.009 FAIL; V3d line <=1 dB: 9.805 FAIL; V4b <=2 %: 0.254 FAIL; V9 births <= P1: 39.787 ok; V9 energy <= P1+3 dB: -55.571 ok; V3i <=1 /s: 2.812 FAIL; right weight kept >=90 %: 0.992 ok
   (a) V6b delta -16.71 %p (noT24 -16.71), songs negative 5/5 (noT24 5/4), CI95 [-19.17, -14.57] %p -> value met True, with evidence False
   (b) dV5a -3.61 %p, d rise90 bare -36.1 ms, line 3.8 ms -> met (AND) False  [OR variant True]
   (c) d tail settled 74.3 ms, d RERISE 1.8 dB -> met False
   right-weight retention delta 26.65 %p, per song {'Track00060': 0.2127, 'Track00040': 0.157, 'Track00001': 0.3745, 'Track00005': 0.2199, 'Track00012': 0.1121}, CI95 [17.94, 34.59]
   V6b per-song deltas (%p): 60: -12.35, 40: -21.19, 01: -15.79, 05: -10.54, 12: -19.35
LA(64) vs core v1.5 proxy, groups: E1: wins 1 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 1 -; E4: wins 2 losses 0 BETTER; E5: wins 1 losses 0 BETTER  -> 2 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False

### stream band
LA(217) vs LA(64): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.269 FAIL; V3d line <=1 dB: 45.431 FAIL; V4b <=2 %: 0.200 FAIL; V9 births <= P1: 24.681 ok; V9 energy <= P1+3 dB: -51.177 FAIL; V3i <=1 /s: 0.000 ok; right weight kept >=90 %: 0.946 ok
   (a) V6b delta -6.63 %p (noT24 -6.63), songs negative 5/5 (noT24 5/4), CI95 [-8.45, -4.88] %p -> value met True, with evidence False
   (b) dV5a -0.52 %p, d rise90 bare 1.3 ms, line -15.3 ms -> met (AND) False  [OR variant False]
   (c) d tail settled -107.1 ms, d RERISE -7.1 dB -> met True
   right-weight retention delta -0.37 %p, per song {'Track00060': -0.0495, 'Track00040': -0.0219, 'Track00001': 0.0222, 'Track00005': -0.0272, 'Track00012': -0.0081}, CI95 [-2.62, 2.84]
   V6b per-song deltas (%p): 60: -4.68, 40: -14.94, 01: -4.56, 05: -3.66, 12: -6.18
LA(64) vs LA(0): clearly better = False  (guards of the candidate ok: False; any criterion: True)
   guards: V3d bass <=1 dB: 1.891 FAIL; V3d line <=1 dB: 30.515 FAIL; V4b <=2 %: 0.236 FAIL; V9 births <= P1: 40.745 ok; V9 energy <= P1+3 dB: -50.215 FAIL; V3i <=1 /s: 3.262 FAIL; right weight kept >=90 %: 0.950 ok
   (a) V6b delta -6.59 %p (noT24 -6.59), songs negative 4/5 (noT24 4/4), CI95 [-9.21, -3.98] %p -> value met True, with evidence True
   (b) dV5a 3.09 %p, d rise90 bare -16.0 ms, line 12.0 ms -> met (AND) False  [OR variant False]
   (c) d tail settled 0.0 ms, d RERISE 7.1 dB -> met False
   right-weight retention delta 36.80 %p, per song {'Track00060': 0.2701, 'Track00040': 0.3306, 'Track00001': 0.4669, 'Track00005': 0.3354, 'Track00012': 0.2952}, CI95 [30.14, 43.13]
   V6b per-song deltas (%p): 60: -4.79, 40: +0.92, 01: -12.09, 05: -0.02, 12: -9.98
LA(64) vs core v1.5 proxy, groups: E1: wins 2 losses 2 -; E2: wins 0 losses 1 -; E3: wins 0 losses 1 -; E4: wins 0 losses 0 -; E5: wins 1 losses 0 BETTER  -> 1 of 5 groups better
=> 300 ms model condition: False;  150 ms preview-core condition: False

### E4 versus core v1.5 (LA with the classifier minus core; V6b = wrong share)
bh-64: V6b delta -9.20 %p CI95 [-11.84, -6.32]; without T24 -9.20 [-11.80, -6.18]; per song 60: -13.64, 40: +1.06, 01: -11.01, 05: -10.90, 12: -6.15; songs negative 4/5; right weight vs core per song 60: +5.7%, 40: +5.9%, 01: +10.7%, 05: +14.4%, 12: +0.4%
bh-217: V6b delta -11.61 %p CI95 [-13.84, -9.21]; without T24 -11.61 [-13.79, -9.24]; per song 60: -15.10, 40: -2.66, 01: -11.80, 05: -17.75, 12: -10.81; songs negative 5/5; right weight vs core per song 60: -8.5%, 40: +7.1%, 01: +0.4%, 05: +3.8%, 12: -4.0%
band-64: V6b delta +2.44 %p CI95 [-1.19, 6.54]; without T24 +2.44 [-1.23, 6.53]; per song 60: -6.03, 40: +24.74, 01: -2.06, 05: -2.60, 12: +2.27; songs negative 3/5; right weight vs core per song 60: +75.8%, 40: +33.6%, 01: +26.9%, 05: +68.1%, 12: +35.0%
band-217: V6b delta -4.19 %p CI95 [-7.03, -1.04]; without T24 -4.19 [-7.04, -0.98]; per song 60: -10.70, 40: +9.80, 01: -6.63, 05: -6.26, 12: -3.90; songs negative 4/5; right weight vs core per song 60: +37.7%, 40: +28.1%, 01: +16.2%, 05: +44.2%, 12: +22.7%

OUTCOME: STOP the lookahead direction; review v1.6 (section 13) and the v2 estimator   (chosen stream band; the other stream alone would give: stop)
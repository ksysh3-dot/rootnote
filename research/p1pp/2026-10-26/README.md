# P1++ first attribution study

Baseline: [P1+ 8bec71f](https://github.com/ksysh3-dot/rootnote/commit/8bec71f47bc1e85dcfddfcf362411347490c5119).
No DSP coefficients or algorithms changed. This investigates a known development
failure; it is not a new P1++ model or independent validation set.

## Question and result

The earlier short-note condition at 45.4609 Hz had a relative main-harmonic
envelope error RMS of 82.7775% even with P1+. Removing the separate percussive
noise leaves **82.7769%**. The noise is therefore not necessary for this failure
in this fixture. A stronger noise suppressor is not justified as the first fix.

| Existing condition / ablation | Relative envelope error RMS |
|---|---:|
| Original short note + AM + separate percussive noise | 82.7775% |
| Same note + AM, no percussive noise | 82.7769% |
| Short note without AM or noise | 112.7704% |
| Same note without AM, with percussive noise | 112.7713% |

The AM removal also changes the instantaneous input amplitude; it does not show
that normal AM is universally beneficial or that the failure belongs to one DSP
stage. A note of this duration can fail even without either added component.

Keeping the unmodulated envelope and changing only the source frequency gives
147.1%, 35.9%, 17.6%, 14.7% and 9.1% at 41, 55, 65, 81 and 106 Hz respectively.
The primary harmonic order and extraction bandwidth follow the original metric
and change with frequency. This is a lead for investigating lower-frequency
short-note behavior, not a stage-isolating proof or a universal frequency curve.

The next step is to inspect the input filtering, HPSS, detected tracks, target
amplitudes, synthesis and output filtering on these exact inputs. Preserve the
already improved P1+ cases and assess any new change against P1+ directly.

## Reproduce

```sh
python3 tools/pvb-harness/research_p1pp_attribution.py --library /path/to/P1plus/library --report attribution.json
```

`attribution.json` contains all ten conditions, metric definitions, harmonic
orders, library hash and the non-independence caveat. Original fixture seed:
2026102606, condition `fresh_note_3`. One constant scale and the declared engine
latency are used; no fitted time shift. These are numerical diagnostics, not
whole-music distortion percentages or listening preferences.

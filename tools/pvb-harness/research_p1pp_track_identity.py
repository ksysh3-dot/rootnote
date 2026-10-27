#!/usr/bin/env python3
"""Development-only diagnostic: does a descending kick capture an established bass track?

Replays ONE previously inspected selection case (new_kick_2, seed 2026102609,
-12 dB input impact). This case was already used for diagnosis, NOT a holdout.
Compare the stock greedy 10%-frequency matcher with the existing host-only
StageGlobalTrack assignment and its linear predictor. The DSP and released app
profiles are not modified.

Pass/fail means the trace and output are valid, not that either assignment is
better. The measured differences and their denominators are written to JSON.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

import research_p1plus as P
import test_harmonic_continuity as H
from research_p1pp_impacts import score
from research_p1pp_recovery import new_fixtures
from p1plus_paths import default_library

# These are defined in app/src/main/cpp/libpvb/pvb_vb_stage.h.
STAGE_GLOBAL_TRACK = 256
STAGE_TRACK_LINEAR = 512
SEED = 2026102609
CASE = 'new_kick_2'
IMPACT_DB = -12
# tuple: label, impact mode, stage research, v0.4 research flags.
VARIANTS = (
    ('P1+ greedy', 0, 0, 0),
    ('P1++ v0.3 greedy', 8, 0, 0),
    ('P1++ v0.3 global', 8, STAGE_GLOBAL_TRACK, 0),
    ('P1++ v0.3 global+linear', 8, STAGE_GLOBAL_TRACK | STAGE_TRACK_LINEAR, 0),
    ('R01 stable-track lock', 8, 0, 64),
    ('R01 stable lock + local peaks', 8, 0, 65),
)


def track_identity(rows, fs, onset, duration, bed_hz):
    """Measured trace IDs, not an inferred musical source or instrument label."""
    tr = H.tracks(rows)
    time = (rows[:, 0] + rows[:, 9]) / fs  # same trace-alignment convention as score()
    live = (tr[:, :, 1] >= 1) & (tr[:, :, 1] <= 4)
    ids = (tr[:, :, 0].astype(np.int64) +
           (tr[:, :, 13].astype(np.int64) << 16))
    near = np.abs(tr[:, :, 2] - bed_hz) <= .03 * bed_hz
    confirmed = live & (tr[:, :, 7] >= .5)
    pre = (time >= onset - .25) & (time < onset - .03)
    candidates = ids[pre[:, None] & confirmed & near]
    candidates = candidates[candidates > 0]
    if len(candidates):
        unique, counts = np.unique(candidates, return_counts=True)
        original = int(unique[np.argmax(counts)])
    else:
        original = None

    window = (time >= onset) & (time < onset + duration + .25)
    original_obs = window[:, None] & live & (ids == original) if original is not None else np.zeros_like(live)
    peak_deviation_pct = (float(100 * np.max(np.abs(tr[:, :, 2][original_obs] - bed_hz)) / bed_hz)
                          if np.any(original_obs) else None)
    # Evidence of track theft: the original ID follows a peak >5% away from
    # the known bed frequency. This is a symptom, not ground-truth separation.
    stolen_hops = (int(np.sum(original_obs & (np.abs(tr[:, :, 2] - bed_hz) > .05 * bed_hz)))
                   if original is not None else 0)
    near_confirmed = np.any(confirmed & near, axis=1)
    win_hops = int(np.count_nonzero(window))
    missing_near = int(np.count_nonzero(window & ~near_confirmed))
    born = (tr[:, :, 1] == 1) & near & window[:, None]
    later_births = int(np.count_nonzero(born & (ids != original))) if original is not None else int(np.count_nonzero(born))
    return dict(pre_impact_confirmed_id=original, pre_impact_confirmed_id_observations=int(len(candidates)),
                event_hops=win_hops, original_id_observed_hops=int(np.count_nonzero(original_obs)),
                original_id_max_deviation_percent=peak_deviation_pct,
                original_id_stolen_hops_over_5_percent=stolen_hops,
                missing_confirmed_near_bed_hops=missing_near,
                later_bed_near_births_other_ids=later_births)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=default_library())
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    fs = 48000
    entries = list(new_fixtures(fs, seed=SEED, count=12))
    match = [entry for entry in entries if entry[0] == CASE]
    assert len(match) == 1
    name, has_bed, t, bed, impact, onset, duration, desc = match[0]
    assert has_bed and desc['kind'] == 'kick'
    source = bed + impact * 10 ** (IMPACT_DB / 20)
    assert np.max(np.abs(source)) < 1.
    x = np.r_[source, np.zeros(fs // 2)]
    lib = P.api(args.library.resolve())
    results = []

    saved = os.environ.get('P1PP_V04')
    for label, mode, stages, v04 in VARIANTS:
        os.environ['P1PP_V04'] = str(v04)
        reference = P.render(lib, np.r_[bed, np.zeros(fs // 2)], fs=fs,
                             flags=6, impact_mode=mode, stage_flags=stages)
        measured = P.render(lib, x, fs=fs, flags=6, impact_mode=mode,
                            stage_flags=stages)
        scores, _ = score(measured, reference, source, source - bed, t, onset, duration, fs)
        assert np.isfinite(measured['stem']).all()
        assert len(measured['rows']) > 0
        assert measured['stages'] is not None and len(measured['stages']) > 0
        # Prevent a false comparison if a stage flag was silently ignored.
        assert np.all(measured['stages'][:, 21] == stages), (label, stages)
        ident = track_identity(measured['rows'], fs, onset, duration, desc['bed_frequency'])
        diagnostic=(measured['rows'][:, 27].astype(np.int64) // 65536)
        row = dict(variant=label, impact_mode=mode, stage_flags=stages, v04_flags=v04,
                   strong_onset_hops=int(np.count_nonzero(diagnostic & 1)),
                   percussion_context_hops=int(np.count_nonzero(diagnostic & 2)),
                   mature_track_hops=int(np.count_nonzero(diagnostic & 4)),
                   onset_and_percussion_hops=int(np.count_nonzero((diagnostic & 3)==3)),
                   onset_and_mature_hops=int(np.count_nonzero((diagnostic & 5)==5)),
                   percussive_and_mature_hops=int(np.count_nonzero((diagnostic & 6)==6)),
                   all_three_hops=int(np.count_nonzero((diagnostic & 7)==7)),
                   protected_onsets=int(np.count_nonzero(diagnostic & 8)),
                   **ident,
                   early_tail_energy_per_input_db=scores['early_tail_energy_per_input_db'],
                   early_tail_stationary_residual_per_input_db=scores['early_tail_stationary_residual_per_input_db'],
                   late_tail_energy_per_input_db=scores['late_tail_energy_per_input_db'],
                   late_tail_stationary_residual_per_input_db=scores['late_tail_stationary_residual_per_input_db'],
                   births=scores['births'], recovery_ms=scores['recovery_ms'],
                   onset_raw_mismatch_accepted_track_hops=scores['onset_raw_mismatch_accepted_track_hops'],
                   latency_frames=int(measured['latency']))
        results.append(row)
        print(f"{label}: onset={row['strong_onset_hops']} perc={row['percussion_context_hops']} mature={row['mature_track_hops']} O&P={row['onset_and_percussion_hops']} O&M={row['onset_and_mature_hops']} P&M={row['percussive_and_mature_hops']} all={row['all_three_hops']} armed={row['protected_onsets']} captured={row['original_id_stolen_hops_over_5_percent']}/"
              f"{row['original_id_observed_hops']} missing_bed="
              f"{row['missing_confirmed_near_bed_hops']}/{row['event_hops']} "
              f"early={row['early_tail_energy_per_input_db']:.3f}dB", flush=True)

    if saved is None: os.environ.pop('P1PP_V04', None)
    else: os.environ['P1PP_V04'] = saved
    report = dict(schema='pvb.p1pp.track_identity.v2', study_type='previously_inspected_development_case',
                  seed=SEED, case=name, input_impact_db=IMPACT_DB,
                  independent_waveforms=1, levels_per_waveform=1,
                  study_limitations=['No new holdout', 'Track ID does not establish musical source identity',
                                     'Output delta is not a perceptual quality metric',
                                     'Do not infer a device or listening outcome'],
                  source_library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  source_bed_frequency_hz=desc['bed_frequency'], source_bed_amplitude=desc['bed_amplitude'],
                  impact_duration_s=duration, variants=results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                           encoding='utf-8')
    print(f"trace diagnostic PASS: {len(results)}/{len(VARIANTS)} variants, 1 waveform, 1 input level",
          flush=True)


if __name__ == '__main__':
    main()

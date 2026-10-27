#!/usr/bin/env python3
"""Known transfer/held-out failures and acoustic floor controls, not phone measurements."""
import copy
import math
import unittest
import acoustic_lab as lab


def capture(source=9, levels=None, epoch=1, key="fixed"):
    meta = dict(path_key=key, actual_source=source, silenced=False, active_mics=[{"id": 1}],
                stream_effects=[], client_effect_requests=[])
    return dict(source=source, path_start=copy.deepcopy(meta), path_end=copy.deepcopy(meta),
                frequencies_hz=lab.BANDS, levels_dbfs=levels, epoch_ms=epoch, clipped_samples=0)


def calibration_fixture():
    room, fit, val = [-90.] * 14, [], []
    refs = {}
    for hz in lab.BANDS:
        response = 3 * math.log2(hz / 1000)
        target_fit = 65 + 2 * math.log2(hz / 1000)
        target_val = 58 - 3 * math.log2(hz / 1000)  # different spectrum and level, not a reused fit
        def measured(spl):
            return 10 * math.log10(10 ** ((spl - 125 + response) / 10) + 1e-9)
        fit.append(measured(target_fit)); val.append(measured(target_val))
        def with_room(spl):
            return 10 * math.log10(10 ** (spl / 10) + 10 ** (20 / 10))
        refs[(9, hz)] = dict(room_db_spl=20, fit_db_spl=with_room(target_fit), validation_db_spl=with_room(target_val))
    return dict(phases={"room": [capture(levels=room)], "fit": [capture(levels=fit, epoch=2)],
                        "validation": [capture(levels=val, epoch=3)]}), refs


def impact_fixture():
    rows = []
    for model in [6, 11, 12, 13]:
        for level in [-12, 0]:
            for repeat in [0, 1, 2]:
                for impact in [False, True]:
                    r = capture()
                    p = 10 ** ((-40 + level) / 10)
                    r.update(model_id=model, input_db=level, repeat=repeat, impact=impact, valid=True,
                        marker_correlation=.9, render_sha256="0" * 64, recovery_ms=200 if impact else 160,
                        ambient_power=1e-10, window_powers={"before": p + 1e-10, "pre": p + 1e-10, "attack": p * (4 if impact else 1) + 1e-10,
                        "early": p * (2 if impact else 1) + 1e-10, "late": p * (1.5 if impact else 1) + 1e-10})
                    rows.append(r)
    return dict(band_hz=[150, 2000], complete=True, trials=rows)


class CalibrationTests(unittest.TestCase):
    def test_known_tilt_is_removed_on_different_validation_spectrum(self):
        p, r = calibration_fixture(); a = lab.calibrate(p, r)["profiles"][0]
        self.assertGreater(a["validation_rmse_before_db"], 4)
        self.assertLess(a["validation_rmse_after_db"], 1e-8)
        self.assertAlmostEqual(a["offset_at_1khz_band_db"], 125, places=8)
        self.assertFalse(a["applied_to_app"])

    def test_validation_is_not_fitted_away(self):
        p, r = calibration_fixture()
        for row in p["phases"]["validation"]:
            row["levels_dbfs"] = [v + 4 for v in row["levels_dbfs"]]
        a = lab.calibrate(p, r)["profiles"][0]
        self.assertGreater(a["validation_rmse_after_db"], 3.9)
        self.assertFalse(a["engineering_screen_pass"])

    def test_rejects_changed_source_path(self):
        p, r = calibration_fixture()
        for k in ["path_start", "path_end"]:
            p["phases"]["validation"][0][k]["path_key"] = "other"
        with self.assertRaisesRegex(ValueError, "Different"):
            lab.calibrate(p, r)

    def test_rejects_missing_reference_and_holdout(self):
        p, r = calibration_fixture(); del r[(9, 100)]
        with self.assertRaisesRegex(ValueError, "Reference missing"): lab.calibrate(p, r)
        p, r = calibration_fixture(); del p["phases"]["validation"]
        with self.assertRaisesRegex(ValueError, "independent validation"): lab.calibrate(p, r)

    def test_low_snr_is_excluded_not_interpolated(self):
        p, r = calibration_fixture()
        p["phases"]["fit"][0]["levels_dbfs"][0] = -86
        a = lab.calibrate(p, r)["profiles"][0]
        self.assertEqual(a["valid_bands"], 13)
        self.assertFalse(a["bands"][0]["valid"])

    def test_clipping_silencing_enabled_effect_and_reused_holdout_rejected(self):
        for kind in ["clip", "silence", "effect", "reuse"]:
            p, r = calibration_fixture(); row = p["phases"]["validation"][0]
            if kind == "clip": row["clipped_samples"] = 1
            if kind == "silence": row["path_start"]["silenced"] = True
            if kind == "effect": row["path_start"]["client_effect_requests"] = [{"enabled": True}]
            if kind == "reuse": row["epoch_ms"] = 2
            with self.assertRaises(ValueError): lab.calibrate(p, r)


class ImpactTests(unittest.TestCase):
    def test_first_trial_failure_remains_an_empty_incomplete_attempt(self):
        report = impact_fixture(); report.update(trials=[], complete=False)
        result = lab.analyze_impact(report)
        self.assertFalse(result["run_complete"])
        self.assertEqual(result["accepted_pairs"], 0)
        self.assertIsNone(result["automatic_winner"])

    def test_complete_pairs_and_known_window_ratios(self):
        result = lab.analyze_impact(impact_fixture())
        self.assertEqual(result["accepted_pairs"], 24)
        self.assertTrue(result["run_complete"])
        self.assertAlmostEqual(result["summary"][0]["windows"]["attack"]["median_delta_to_bed_db"], 10 * math.log10(4), places=4)
        self.assertAlmostEqual(result["level_dependence"][0]["loop_compression_db"], 0, places=3)
        self.assertIsNone(result["automatic_winner"])

    def test_floor_is_not_large_negative_improvement(self):
        report = impact_fixture()
        for r in report["trials"]: r["window_powers"]["late"] = 1.01e-10
        result = lab.analyze_impact(report)
        self.assertTrue(all(c["windows"]["late"]["median_delta_to_bed_db"] is None for c in result["summary"]))

    def test_pre_impact_energy_is_not_hidden_in_the_steady_baseline(self):
        report = impact_fixture()
        for row in report["trials"]:
            if row["impact"]: row["window_powers"]["pre"] *= 2
        result = lab.analyze_impact(report)
        self.assertTrue(all(c["windows"]["pre"]["median_delta_to_bed_db"] > 3 for c in result["summary"]))
        self.assertTrue(all(p["gain_control_pass"] for p in result["pairs"]))

    def test_global_attenuation_fails_gain_control_and_is_reported(self):
        report = impact_fixture()
        for r in report["trials"]:
            if r["impact"]: r["window_powers"] = {k: p / 4 for k, p in r["window_powers"].items()}
        result = lab.analyze_impact(report)
        self.assertTrue(all(c["gain_control_failures"] == 3 for c in result["summary"]))

    def test_pumping_is_signed_not_zeroed(self):
        report = impact_fixture()
        for r in report["trials"]:
            if r["impact"]: r["window_powers"]["late"] *= .2
        result = lab.analyze_impact(report)
        self.assertTrue(all(p["windows"]["late"]["signed_excess_power"] < 0 for p in result["pairs"]))

    def test_partial_clipped_and_duplicate_not_success(self):
        report = impact_fixture(); report["trials"].pop()
        self.assertFalse(lab.analyze_impact(report)["run_complete"])
        report = impact_fixture(); report["trials"][0]["clipped_samples"] = 1
        self.assertEqual(lab.analyze_impact(report)["accepted_pairs"], 23)
        report = impact_fixture(); report["trials"].append(report["trials"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"): lab.analyze_impact(report)

    def test_mixed_paths_not_compared(self):
        report = impact_fixture()
        for k in ["path_start", "path_end"]: report["trials"][0][k]["path_key"] = "other"
        with self.assertRaisesRegex(ValueError, "mix recording paths"): lab.analyze_impact(report)


if __name__ == "__main__":
    unittest.main()

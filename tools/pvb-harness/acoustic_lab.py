#!/usr/bin/env python3
"""Analyze explicit, band-only phone experiments. No audio upload or inferred calibration input.

calibrate: app JSON + simultaneous REW 1/3-octave band SPL -> per-path offsets + held-out validation.
impact: app JSON -> paired bed/impact windows, gain controls, recovery, level dependence.
prepare: original PC signals + reference CSV template (not measurements).
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

BANDS = [100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000]
SCHEMA = "rootnote.acoustic_lab.v1"


def db(power):
    return 10 * math.log10(power) if power is not None and power > 0 else None


def clean(total_db, room_db, snr_db=15):
    if not all(math.isfinite(v) for v in (total_db, room_db)) or total_db - room_db < snr_db:
        return None
    return 10 * math.log10(10 ** (total_db / 10) - 10 ** (room_db / 10))


def load_report(path, kind):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if data.get("schema") != SCHEMA or data.get("protocol_version") != 1 or data.get("kind") != kind:
        raise ValueError("Unknown report schema/protocol/kind; do not reinterpret another result")
    if data.get("audio_saved") is not False:
        raise ValueError("Expected the band-only measurement export")
    return data


def path_key(row):
    a, b = row["path_start"], row["path_end"]
    if a.get("silenced") or b.get("silenced"):
        raise ValueError("Recording was silenced")
    if not a.get("path_key") or a["path_key"] != b.get("path_key"):
        raise ValueError("Recording path changed or is missing")
    if a.get("actual_source") not in (None, row["source"]):
        raise ValueError("Actual recording source differs from requested source")
    if any(e.get("enabled") for e in a.get("client_effect_requests", [])):
        raise ValueError("A requested client effect remains enabled")
    if row.get("clipped_samples", 0):
        raise ValueError("Microphone clipped")
    return a["path_key"]


def refs_from_csv(path):
    # These are integrated third-octave RTA levels, not interpolated points on an FR curve.
    result = {}
    required = {"source", "frequency_hz", "room_db_spl", "fit_db_spl", "validation_db_spl"}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Reference CSV needs " + ",".join(sorted(required)))
        for row in reader:
            source, hz = int(row["source"]), float(row["frequency_hz"])
            if hz not in BANDS:
                raise ValueError("Reference must contain the app's exact third-octave centers")
            key = source, int(hz)
            if key in result:
                raise ValueError("Duplicate reference band/source")
            values = {k: float(row[k]) for k in ("room_db_spl", "fit_db_spl", "validation_db_spl")}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError("Non-finite reference value")
            result[key] = values
    return result


def calibrate(phone, reference):
    phases = phone.get("phases", {})
    if set(phases) != {"room", "fit", "validation"}:
        raise ValueError("Need room, fit and independent validation captures")
    by_phase = {}
    for phase, rows in phases.items():
        by_phase[phase] = {}
        for row in rows:
            if row["source"] in by_phase[phase]:
                raise ValueError("Duplicate source in phase")
            if row["frequencies_hz"] != BANDS or len(row["levels_dbfs"]) != len(BANDS):
                raise ValueError("Mismatched phone bands")
            path_key(row)
            by_phase[phase][row["source"]] = row
    sources = set(by_phase["room"])
    if not sources or any(set(rows) != sources for rows in by_phase.values()):
        raise ValueError("Do not silently drop a missing source/phase")
    profiles = []
    for source in sorted(sources):
        rows = {p: by_phase[p][source] for p in by_phase}
        if len({path_key(row) for row in rows.values()}) != 1:
            raise ValueError("Different microphone/OS source paths cannot share a calibration")
        if rows["fit"].get("epoch_ms", 0) >= rows["validation"].get("epoch_ms", 0):
            raise ValueError("Validation must be a separate capture after the fixed calibration")
        bands = []
        for i, hz in enumerate(BANDS):
            ref = reference.get((source, hz))
            if ref is None:
                raise ValueError(f"Reference missing source {source}, band {hz}")
            values = [row["levels_dbfs"][i] for row in rows.values()]
            if any(v is None for v in values):
                bands.append({"hz": hz, "valid": False, "reason": "missing_phone_band"}); continue
            room = rows["room"]["levels_dbfs"][i]
            fit = clean(rows["fit"]["levels_dbfs"][i], room)
            val = clean(rows["validation"]["levels_dbfs"][i], room)
            rf, rv = clean(ref["fit_db_spl"], ref["room_db_spl"]), clean(ref["validation_db_spl"], ref["room_db_spl"])
            if any(v is None for v in (fit, val, rf, rv)):
                bands.append({"hz": hz, "valid": False, "reason": "snr_below_15_db"}); continue
            offset = rf - fit
            bands.append({"hz": hz, "valid": True, "offset_db": offset, "validation_error_after_db": val + offset - rv,
                          "validation_phone_signal_dbfs": val, "validation_reference_signal_db_spl": rv})
        valid = [b for b in bands if b["valid"]]
        anchor = next((b for b in valid if b["hz"] == 1000), None)
        if anchor is None or len(valid) < 10:
            raise ValueError("Need at least 10 high-SNR bands, including the 1 kHz anchor")
        for b in valid:
            b["response_re_1khz_db"] = anchor["offset_db"] - b["offset_db"]
            b["validation_error_before_db"] = (b["validation_phone_signal_dbfs"] + anchor["offset_db"] -
                                                 b["validation_reference_signal_db_spl"])
        before = math.sqrt(statistics.mean(b["validation_error_before_db"] ** 2 for b in valid))
        after = math.sqrt(statistics.mean(b["validation_error_after_db"] ** 2 for b in valid))
        drift = statistics.mean(b["validation_error_after_db"] for b in valid)
        profiles.append({"source": source, "path_key": path_key(rows["fit"]), "valid_bands": len(valid), "bands": bands,
            "offset_at_1khz_band_db": anchor["offset_db"], "before_definition": "one-point 1 kHz calibration; no FR correction",
            "validation_rmse_before_db": before, "validation_rmse_after_db": after, "validation_gain_drift_db": drift,
            "engineering_screen_pass": after <= 2 and abs(drift) <= 1 and after <= before + 0.25,
            "applied_to_app": False, "qualification": "paired-position transfer estimate, 100-2000 Hz only; no extrapolation",
            "stream_effects": rows["fit"]["path_start"].get("stream_effects", []),
            "active_microphones_known": bool(rows["fit"]["path_start"].get("active_mics")),
            "configuration_known": not rows["fit"]["path_start"].get("configuration_unknown", False)})
    return {"schema": "rootnote.mic_calibration_analysis.v1", "device": {k: phone.get(k) for k in
            ("model", "device", "os_build", "app_version", "sample_rate_hz")}, "profiles": profiles,
            "validation_is_independent_capture": True, "reference_definition": "simultaneous calibrated REW third-octave RTA SPL",
            "limits": "Same source, placement and level range only. Shared ambient assumed stable. No proof of microphone linearity or generalization to another phone."}


def quantified_power(row, window):
    p = row["window_powers"][window]
    noise = row["ambient_power"]
    if p is None or noise is None or not all(math.isfinite(v) for v in (p, noise)) or noise < 0:
        return None
    # No artificial -150 dB win when the measurement hits its noise floor.
    return p - noise if p > 0 and p >= noise * 10 else None


def analyze_impact(report):
    rows = report.get("trials", [])
    if report.get("band_hz") != [150, 2000]:
        raise ValueError("Unknown acoustic integration band")
    if len({(r["model_id"], r["input_db"], r["repeat"], r["impact"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate trial identity")
    groups, excluded, paths, accepted_rows = {}, [], set(), []
    for r in rows:
        key = r["model_id"], r["input_db"], r["repeat"]
        if r["model_id"] not in [6, 11, 12, 13] or r["input_db"] not in [-12, 0] or r["repeat"] not in [0, 1, 2]:
            raise ValueError("Unknown trial condition")
        try:
            p = path_key(r)
            if not r.get("valid") or r["marker_correlation"] < 0.35:
                raise ValueError("alignment, clipping or coverage invalid")
            if len(r.get("render_sha256", "")) != 64:
                raise ValueError("missing render provenance")
            paths.add(p)
            accepted_rows.append(r)
            groups.setdefault(key, {})[bool(r["impact"])] = r
        except ValueError as e:
            excluded.append({"condition": list(key), "impact": r["impact"], "reason": str(e)})
    if len(paths) > 1:
        raise ValueError("A comparison cannot mix recording paths; run separate sessions")
    pairs = []
    for key, g in sorted(groups.items()):
        if set(g) != {False, True}:
            excluded.append({"condition": list(key), "reason": "unpaired"}); continue
        bed, hit = g[False], g[True]
        before_bed, before_hit = quantified_power(bed, "before"), quantified_power(hit, "before")
        gain_db = db(before_hit / before_bed) if before_hit and before_bed else None
        windows = {}
        for window in ("pre", "attack", "early", "late"):
            bp, hp = quantified_power(bed, window), quantified_power(hit, window)
            ratio = db(hp / bp) if bp and hp else None
            windows[window] = {"bed_dbfs": db(bed["window_powers"][window]), "impact_dbfs": db(hit["window_powers"][window]),
                "delta_to_bed_db": ratio, "before_matched_delta_db": ratio - gain_db if ratio is not None and gain_db is not None else None,
                "signed_excess_power": hp - bp if hp is not None and bp is not None else None,
                "quantified": bp is not None and hp is not None}
        pairs.append({"model_id": key[0], "input_db": key[1], "repeat": key[2], "before_gain_difference_db": gain_db,
                      "windows": windows, "recovery_ms": hit.get("recovery_ms"),
                      "gain_control_pass": gain_db is not None and abs(gain_db) <= 1})
    summary = []
    for model in [6, 11, 12, 13]:
        for level in [-12, 0]:
            group = [p for p in pairs if p["model_id"] == model and p["input_db"] == level]
            if not group:
                continue
            cell = {"model_id": model, "input_db": level, "paired_repeats": len(group),
                    "gain_control_failures": sum(not p["gain_control_pass"] for p in group), "windows": {}}
            for window in ("pre", "attack", "early", "late"):
                values = [p["windows"][window]["delta_to_bed_db"] for p in group if p["windows"][window]["quantified"]]
                cell["windows"][window] = {"quantified_repeats": len(values), "median_delta_to_bed_db":
                    statistics.median(values) if values else None, "range_db": [min(values), max(values)] if values else None}
            recovery = [p["recovery_ms"] for p in group if p["recovery_ms"] is not None]
            cell.update(recovery_median_ms=statistics.median(recovery) if recovery else None,
                        recovery_unresolved=len(group) - len(recovery))
            summary.append(cell)
    compression = []
    for model in [6, 11, 12, 13]:
        a = [quantified_power(r, "before") for r in accepted_rows if r["model_id"] == model and r["input_db"] == -12 and not r["impact"]]
        b = [quantified_power(r, "before") for r in accepted_rows if r["model_id"] == model and r["input_db"] == 0 and not r["impact"]]
        a, b = [v for v in a if v is not None], [v for v in b if v is not None]
        increase = db(statistics.median(b) / statistics.median(a)) if a and b else None
        compression.append({"model_id": model, "input_increase_db": 12, "recorded_bed_increase_db": increase,
                            "loop_compression_db": 12 - increase if increase is not None else None})
    return {"schema": "rootnote.impact_analysis.v1", "run_complete": report.get("complete") is True and len(rows) == 48,
            "accepted_pairs": len(pairs), "excluded": excluded, "pairs": pairs, "summary": summary, "level_dependence": compression,
            "source": rows[0]["source"] if rows else None, "path_key": next(iter(paths), None),
            "automatic_winner": None, "interpretation": "Energy change of the recorded loop, not isolated noise. Keep attack, bed gain, late energy and unresolved recovery together.",
            "noise_floor_rule": "Window total >= ambient +10 dB; otherwise difference is unquantified, not a tiny residual win."}


def prepare(directory):
    import numpy as np
    import soundfile as sf
    from scipy.signal import butter, sosfilt
    directory.mkdir(parents=True, exist_ok=False)
    rate, seconds = 48000, 40
    t = np.arange(rate * seconds) / rate
    for name, seed, cutoff in [("fit", 20261027, 2500), ("validation", 20261028, 3500)]:
        x = sosfilt(butter(3, [70, cutoff], btype="band", fs=rate, output="sos"), np.random.default_rng(seed).normal(size=t.size))
        if name == "validation":
            x = x * (0.75 + 0.2 * np.sin(2 * np.pi * 0.4 * t)) + 0.04 * np.sin(2 * np.pi * 315 * t)
        x *= 0.15 / max(abs(x))
        x *= np.minimum(1, t / 0.2) * np.minimum(1, (seconds - t) / 0.2)
        sf.write(directory / (name + ".wav"), np.column_stack([x, x]), rate, subtype="PCM_24")
    with open(directory / "reference.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f); writer.writerow(["source", "frequency_hz", "room_db_spl", "fit_db_spl", "validation_db_spl"])
        for source in [9, 6]:
            for hz in BANDS:
                writer.writerow([source, hz, "", "", ""])
    (directory / "README.txt").write_text("Original generated PC signals; NOT measurements.\nPlay each for both sequential phone sources.\nSave simultaneous REW third-octave RTA SPL per source/capture.\nFill reference.csv; delete source 9 rows only if UNPROCESSED was unavailable.\nDo not substitute an FR magnitude export or one snapshot for differently timed reference captures.\n", encoding="utf-8")


def write_outputs(out, result, inputs):
    out.mkdir(parents=True, exist_ok=True)
    result["input_sha256"] = {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs}
    (out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# 자동 음향 측정 분석", "", "실제 입력 파일을 분석한 결과입니다. 측정 경로와 조건의 범위에서 해석하세요.", ""]
    if "profiles" in result:
        lines += ["보정 전: 같은 보정 녹음의 1 kHz 한 점으로 레벨만 맞춘 상태. 보정 후: 대역별 오프셋 적용.",
                  "확인 녹음은 보정값 계산에 사용하지 않았습니다. 앱 설정에는 적용하지 않습니다.", "",
                  "| 녹음 방식 | 대역 수 | 확인 RMSE 전 dB | 후 dB | 확인 이득 이동 dB | 공학적 선별 |", "|---|---:|---:|---:|---:|---|"]
        for p in result["profiles"]:
            lines.append(f"| {p['source']} | {p['valid_bands']} | {p['validation_rmse_before_db']:.3f} | {p['validation_rmse_after_db']:.3f} | {p['validation_gain_drift_db']:.3f} | {p['engineering_screen_pass']} |")
    else:
        lines += [f"완료된 시험: {result['run_complete']} · 유효한 짝: {result['accepted_pairs']} · 제외 기록: {len(result['excluded'])}",
                  "", "공간·몸체·마이크를 포함한 녹음 에너지입니다. 타격 직후의 원하는 소리와 잡음을 분리하지 못합니다.",
                  "null은 측정 하한·회복 미확인 또는 결측이며 0으로 해석하지 않습니다. 자동 우승 모델은 고르지 않습니다.", "",
                  "| 모델 ID | 입력 dB | 반복 | 직전/지속음 dB | 어택/지속음 dB | 초기/지속음 dB | 후기/지속음 dB | 회복 중앙값 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for c in result["summary"]:
            vals = [c["windows"][w]["median_delta_to_bed_db"] for w in ("pre", "attack", "early", "late")]
            fmt = lambda v: "미확인" if v is None else f"{v:.3f}"
            lines.append(f"| {c['model_id']} | {c['input_db']} | {c['paired_repeats']} | " + " | ".join(map(fmt, vals + [c['recovery_median_ms']])) + " |")
    (out / "RESULTS_KO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["calibrate", "impact"]:
        p = sub.add_parser(name); p.add_argument("phone"); p.add_argument("--out", type=Path, required=True)
        if name == "calibrate":
            p.add_argument("--reference", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.out); return
    phone = load_report(args.phone, "calibration" if args.command == "calibrate" else "impact")
    inputs = [args.phone]
    if args.command == "calibrate":
        result = calibrate(phone, refs_from_csv(args.reference)); inputs.append(args.reference)
    else:
        result = analyze_impact(phone)
    write_outputs(args.out, result, inputs)
    print(args.out / "RESULTS_KO.md")


if __name__ == "__main__":
    main()

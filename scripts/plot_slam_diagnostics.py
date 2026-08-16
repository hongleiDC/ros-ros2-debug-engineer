#!/usr/bin/env python3
"""Generate hypothesis-driven SLAM diagnostic plots from a normalized diagnostics CSV."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


X_LABELS = {
    "distance_m": "Distance [m]",
    "reference_distance_m": "Reference distance [m]",
    "relative_time_s": "Relative time [s]",
    "timestamp": "Timestamp [s]",
    "sample_index": "Sample index",
}

PLOT_SPECS = [
    {
        "category": "estimator",
        "file": "02_estimator/velocity_state.png",
        "columns": ["velocity_x_mps", "velocity_y_mps", "velocity_z_mps", "velocity_longitudinal_mps", "velocity_lateral_mps", "reference_velocity_longitudinal_mps", "reference_velocity_lateral_mps"],
        "ylabel": "Velocity [m/s]",
        "title": "Estimator Velocity State",
        "question": "Does the propagated velocity state diverge before the pose error grows?",
    },
    {
        "category": "estimator",
        "file": "02_estimator/velocity_error.png",
        "columns": ["velocity_error_x_mps", "velocity_error_y_mps", "velocity_error_z_mps", "velocity_error_longitudinal_mps", "velocity_error_lateral_mps"],
        "ylabel": "Velocity error [m/s]",
        "title": "Velocity Error",
        "question": "Is velocity error, especially longitudinal error, the earliest estimator failure?",
        "zero": True,
    },
    {
        "category": "estimator",
        "file": "02_estimator/gyro_bias.png",
        "columns": ["gyro_bias_x_rad_s", "gyro_bias_y_rad_s", "gyro_bias_z_rad_s"],
        "ylabel": "Gyro bias [rad/s]",
        "title": "Gyroscope Bias",
        "question": "Does gyro bias drift correlate with attitude or trajectory degradation?",
        "zero": True,
    },
    {
        "category": "estimator",
        "file": "02_estimator/accel_bias.png",
        "columns": ["accel_bias_x_mps2", "accel_bias_y_mps2", "accel_bias_z_mps2"],
        "ylabel": "Accel bias [m/s^2]",
        "title": "Accelerometer Bias",
        "question": "Does accelerometer bias drift precede velocity or position error growth?",
        "zero": True,
    },
    {
        "category": "matching",
        "file": "03_matching/translation_correction.png",
        "columns": ["scan_match_correction_longitudinal_m", "scan_match_correction_lateral_m", "scan_match_correction_vertical_m"],
        "ylabel": "Scan-match correction [m]",
        "title": "Scan Matching Translation Correction",
        "question": "Does the measurement update inject a directional pose correction that explains the drift?",
        "zero": True,
    },
    {
        "category": "matching",
        "file": "03_matching/yaw_correction.png",
        "columns": ["scan_match_correction_yaw_deg"],
        "ylabel": "Yaw correction [deg]",
        "title": "Scan Matching Yaw Correction",
        "question": "Do heading corrections change before lateral or longitudinal error growth?",
        "zero": True,
    },
    {
        "category": "matching",
        "file": "03_matching/residual.png",
        "columns": ["scan_match_residual_m"],
        "ylabel": "Residual [m]",
        "title": "Scan Matching Residual",
        "question": "Does front-end residual degrade where trajectory error starts increasing?",
    },
    {
        "category": "matching",
        "file": "03_matching/correspondence_count.png",
        "columns": ["correspondence_count", "effective_feature_count"],
        "ylabel": "Count",
        "title": "Matching Support",
        "question": "Does matching support collapse or change when the estimator becomes inaccurate?",
    },
    {
        "category": "matching",
        "file": "03_matching/optimization_iterations.png",
        "columns": ["optimization_iterations"],
        "ylabel": "Iterations",
        "title": "Optimization Iterations",
        "question": "Does optimizer effort or convergence behavior change at the failure point?",
    },
    {
        "category": "observability",
        "file": "04_observability/directional_information.png",
        "columns": ["longitudinal_information", "lateral_information", "yaw_information"],
        "ylabel": "Directional information [native scale]",
        "title": "Directional Observability",
        "question": "Does directional information loss precede the corresponding pose error growth?",
    },
    {
        "category": "observability",
        "file": "04_observability/hessian_eigenvalues.png",
        "columns": ["hessian_min_eigenvalue", "hessian_max_eigenvalue"],
        "ylabel": "Eigenvalue [native scale]",
        "title": "Hessian Eigenvalues",
        "question": "Does the optimization information spectrum collapse in degraded sections?",
    },
    {
        "category": "observability",
        "file": "04_observability/condition_number.png",
        "columns": ["hessian_condition_number"],
        "ylabel": "Condition number",
        "title": "Hessian Condition Number",
        "question": "Does numerical/geometric conditioning worsen before the estimator drifts?",
    },
    {
        "category": "observability",
        "file": "04_observability/degeneracy_flag.png",
        "columns": ["degeneracy_flag"],
        "ylabel": "Flag",
        "title": "Degeneracy Flag",
        "question": "Do explicit degeneracy decisions align with the actual degraded route sections?",
    },
    {
        "category": "fusion",
        "file": "05_fusion/innovation_gate.png",
        "columns": ["rtk_innovation_m", "gnss_innovation_m", "rtk_gate_m", "gnss_gate_m"],
        "ylabel": "Innovation / gate [m]",
        "title": "GNSS/RTK Innovation and Gate",
        "question": "Are external-position innovations rejected, accepted, or growing before estimator failure?",
    },
    {
        "category": "fusion",
        "file": "05_fusion/measurement_acceptance.png",
        "columns": ["rtk_accepted", "gnss_accepted"],
        "ylabel": "Accepted [0/1]",
        "title": "External Measurement Acceptance",
        "question": "Do acceptance decisions explain when external aiding stops constraining drift?",
    },
    {
        "category": "fusion",
        "file": "05_fusion/measurement_age.png",
        "columns": ["measurement_age_ms"],
        "ylabel": "Measurement age [ms]",
        "title": "External Measurement Age",
        "question": "Does timing age or publish delay correlate with fusion error or rejection?",
    },
    {
        "category": "loop",
        "file": "06_loop_map/loop_correction.png",
        "columns": ["loop_correction_m"],
        "ylabel": "Loop correction [m]",
        "title": "Loop Closure Translation Correction",
        "question": "How large are loop-closure corrections and where do they occur?",
        "zero": True,
    },
    {
        "category": "loop",
        "file": "06_loop_map/loop_yaw_correction.png",
        "columns": ["loop_correction_yaw_deg"],
        "ylabel": "Loop yaw correction [deg]",
        "title": "Loop Closure Yaw Correction",
        "question": "Are loop closures correcting heading drift or injecting heading jumps?",
        "zero": True,
    },
    {
        "category": "loop",
        "file": "06_loop_map/loop_quality.png",
        "columns": ["loop_residual_m", "revisit_error_m"],
        "ylabel": "Loop/revisit error [m]",
        "title": "Loop and Revisit Consistency",
        "question": "Do loop/revisit consistency metrics support the claimed map quality?",
    },
    {
        "category": "loop",
        "file": "06_loop_map/loop_acceptance.png",
        "columns": ["loop_accepted"],
        "ylabel": "Accepted [0/1]",
        "title": "Loop Closure Acceptance",
        "question": "Where are loop closures accepted or rejected relative to map inconsistency?",
    },
    {
        "category": "runtime",
        "file": "07_runtime/stage_runtime.png",
        "columns": ["frame_runtime_ms", "scan_match_runtime_ms", "optimization_runtime_ms", "map_update_runtime_ms"],
        "ylabel": "Runtime [ms]",
        "title": "Runtime by Stage",
        "question": "Which stage causes runtime growth or loss of real-time margin?",
    },
    {
        "category": "runtime",
        "file": "07_runtime/cpu_percent.png",
        "columns": ["cpu_percent"],
        "ylabel": "CPU [%]",
        "title": "CPU Usage",
        "question": "Does the candidate consume materially more CPU in the relevant sections?",
    },
    {
        "category": "runtime",
        "file": "07_runtime/rss_mb.png",
        "columns": ["rss_mb"],
        "ylabel": "RSS [MB]",
        "title": "Resident Memory",
        "question": "Does memory usage grow or regress during the run?",
    },
]

CATEGORIES = sorted({str(spec["category"]) for spec in PLOT_SPECS})


def read_series(path: Path) -> tuple[dict[str, list[float]], int]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        rows = list(reader)
    data: dict[str, list[float]] = {name: [] for name in reader.fieldnames}
    for row in rows:
        for name in data:
            try:
                value = float(row.get(name, "nan"))
            except (TypeError, ValueError):
                value = float("nan")
            data[name].append(value)
    return data, len(rows)


def choose_x(data: dict[str, list[float]], rows: int, requested: str | None) -> tuple[str, list[float]]:
    if requested:
        if requested not in data:
            raise ValueError(f"missing requested x column: {requested}")
        return requested, data[requested]
    for name in ("distance_m", "reference_distance_m", "relative_time_s", "timestamp"):
        if name in data:
            return name, data[name]
    return "sample_index", [float(i) for i in range(rows)]


def finite_pairs(x: list[float], y: list[float]) -> tuple[list[float], list[float]]:
    pairs = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def relative_plot_path(plot: Path, manifest: Path) -> str:
    return Path(os.path.relpath(plot.resolve(), manifest.parent.resolve())).as_posix()


def update_plot_manifest(manifest: Path, entries: list[dict[str, str]]) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {"schema_version": 1, "plots": []}
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("plots"), list):
                data = loaded
        except (json.JSONDecodeError, OSError):
            pass
    existing = {
        item.get("file"): item
        for item in data.get("plots", [])
        if isinstance(item, dict) and isinstance(item.get("file"), str)
    }
    for entry in entries:
        existing[entry["file"]] = entry
    data["schema_version"] = 1
    data["plots"] = list(existing.values())
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_plot(data: dict[str, list[float]], x: list[float], x_name: str, spec: dict[str, object], output_root: Path) -> Path | None:
    available = [name for name in spec["columns"] if isinstance(name, str) and name in data and any(math.isfinite(v) for v in data[name])]
    if not available:
        return None
    path = output_root / str(spec["file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name in available:
        px, py = finite_pairs(x, data[name])
        if px:
            ax.plot(px, py, label=name)
    if bool(spec.get("zero")):
        ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel(X_LABELS.get(x_name, x_name))
    ax.set_ylabel(str(spec["ylabel"]))
    ax.set_title(str(spec["title"]))
    ax.grid(True, alpha=0.25)
    if len(available) > 1:
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--x-column")
    parser.add_argument("--category", action="append", choices=CATEGORIES, help="Repeat to select only hypothesis-relevant categories. Omit to plot all recognized categories.")
    args = parser.parse_args()

    source = Path(args.input_csv)
    data, rows = read_series(source)
    x_name, x = choose_x(data, rows, args.x_column)
    selected = set(args.category or CATEGORIES)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = Path(args.manifest) if args.manifest else output_root / "plot_manifest.json"

    entries: list[dict[str, str]] = []
    generated: list[str] = []
    for spec in PLOT_SPECS:
        if spec["category"] not in selected:
            continue
        plot = make_plot(data, x, x_name, spec, output_root)
        if plot is None:
            continue
        generated.append(str(plot))
        entries.append(
            {
                "file": relative_plot_path(plot, manifest),
                "group": str(spec["category"]),
                "question": str(spec["question"]),
                "source": str(source),
            }
        )

    if not generated:
        known = sorted(data)
        raise ValueError(
            "no recognized diagnostic columns for selected categories; "
            f"available columns: {', '.join(known)}"
        )

    update_plot_manifest(manifest, entries)
    print(json.dumps({"x_column": x_name, "categories": sorted(selected), "generated": generated, "manifest": str(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

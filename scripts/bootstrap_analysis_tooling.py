#!/usr/bin/env python3
"""Install self-contained result-analysis tooling and contracts into a target ROS project."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict

import yaml

TOOL_FILES = (
    "analyze_run.py",
    "plot_localization_result.py",
    "plot_slam_diagnostics.py",
    "plot_series.py",
    "compare_result_metrics.py",
    "result_bundle.py",
    "ros_noetic_run_logger.py",
)


def section(section_id: str, title: str, group: str, required: bool, question: str, guidance: str, enabled: bool = True) -> Dict[str, object]:
    return {
        "id": section_id,
        "title": title,
        "groups": [group],
        "required": required,
        "enabled": enabled,
        "question": question,
        "guidance": guidance,
    }


def build_profile(system: str) -> Dict[str, object]:
    is_lio = system in {"lio", "slam"}
    is_slam = system == "slam"
    sections = [
        section("overall", "1. Overall", "core", True, "Is the global trajectory quality acceptable, and where does it start to degrade?", "Start here. Do not inspect internal states before locating the external symptom."),
        section("estimator", "2. Estimator / prediction", "estimator", is_lio, "Does prediction state or bias become abnormal before pose error grows?", "If prediction fails first, inspect IMU propagation, velocity, bias, timing, and state modeling."),
        section("matching", "3. Frontend / matching", "matching", is_lio, "Does the measurement update inject the error or lose matching support?", "Inspect correction, residual, correspondence support, and convergence around the first degraded segment."),
        section("observability", "4. Observability", "observability", is_lio, "Does directional information or conditioning collapse before the corresponding error grows?", "Keep the same time or distance axis as the error plot."),
        section("fusion", "5. External fusion", "fusion", False, "Does external measurement quality, timing, gating, or acceptance explain the estimator response?", "Enable and make required only when GNSS, RTK, wheel odometry, or another external aid is part of the formal system."),
        section("loop", "6. Loop / map", "loop", is_slam, "Do loop closures or map feedback correct drift or introduce inconsistency?", "Enable only for systems with loop closure, pose graph, submaps, or recursive map feedback.", enabled=is_slam),
        section("runtime", "7. Runtime", "runtime", is_lio, "Does the system preserve real-time margin and acceptable resource cost?", "Treat runtime as part of the engineering result, not as an optional appendix."),
    ]
    categories = [str(item["groups"][0]) for item in sections if item.get("enabled") is not False and item["groups"][0] != "core"]
    return {
        "schema_version": 1,
        "title": "%s Run Analysis" % system.upper(),
        "system": system,
        "observation_contract": "observation_contract.yaml",
        "core": {"csv_candidates": ["series/aligned_errors.csv", "series/errors.csv"]},
        "diagnostics": {"file": "series/diagnostics.csv", "categories": categories},
        "sections": sections,
    }


def signal(layer: str, file_name: str, column: str, meaning: str, unit: str, frame: str, required: bool) -> Dict[str, object]:
    return {
        "layer": layer,
        "meaning": meaning,
        "unit": unit,
        "frame": frame,
        "required": required,
        "source": {"file": file_name, "column": column},
    }


def build_observation_contract(system: str) -> Dict[str, object]:
    is_lio = system in {"lio", "slam"}
    is_slam = system == "slam"
    return {
        "schema_version": 1,
        "system": system,
        "purpose": "Stable observability contract for human analysis; customize source mappings once during system design.",
        "signals": {
            "horizontal_error_m": signal("core", "series/aligned_errors.csv", "err_horizontal", "Formal horizontal position error against the chosen reference and alignment method", "m", "evaluation_frame", True),
            "longitudinal_error_m": signal("core", "series/aligned_errors.csv", "err_longitudinal", "Signed error along the local/reference travel direction", "m", "route_tangent", False),
            "lateral_error_m": signal("core", "series/aligned_errors.csv", "err_lateral", "Signed cross-track error", "m", "route_normal", False),
            "velocity_error_longitudinal_mps": signal("estimator", "series/diagnostics.csv", "velocity_error_longitudinal_mps", "Longitudinal velocity error used to distinguish prediction failure from update failure", "m/s", "vehicle_or_route_tangent", is_lio),
            "scan_match_correction_longitudinal_m": signal("matching", "series/diagnostics.csv", "scan_match_correction_longitudinal_m", "Longitudinal translation correction introduced by the frontend update", "m", "vehicle_or_route_tangent", is_lio),
            "longitudinal_information": signal("observability", "series/diagnostics.csv", "longitudinal_information", "Directional information or an explicitly documented observability score", "native", "estimator_definition", is_lio),
            "rtk_innovation_m": signal("fusion", "series/diagnostics.csv", "rtk_innovation_m", "RTK/GNSS innovation before gating", "m", "fusion_measurement_frame", False),
            "loop_correction_m": signal("loop", "series/diagnostics.csv", "loop_correction_m", "Translation correction introduced by a loop closure or pose-graph update", "m", "map", is_slam),
            "frame_runtime_ms": signal("runtime", "series/diagnostics.csv", "frame_runtime_ms", "End-to-end processing time per frame", "ms", "not_applicable", is_lio),
        },
    }


def write_text(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError("refusing to overwrite existing file: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_root")
    parser.add_argument("--system", choices=["localization", "lio", "slam"], default="slam")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    target = Path(args.target_root).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    source_dir = Path(__file__).resolve().parent
    tools_dir = target / "tools" / "analysis"
    analysis_dir = target / "analysis"
    tools_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in TOOL_FILES:
        source = source_dir / name
        if not source.is_file():
            raise SystemExit("missing bundled tool: %s" % source)
        destination = tools_dir / name
        if destination.exists() and not args.force:
            raise SystemExit("refusing to overwrite existing file: %s" % destination)
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(target)))

    write_text(
        analysis_dir / "analysis_profile.yaml",
        yaml.safe_dump(build_profile(args.system), sort_keys=False, allow_unicode=True),
        args.force,
    )
    write_text(
        analysis_dir / "observation_contract.yaml",
        yaml.safe_dump(build_observation_contract(args.system), sort_keys=False, allow_unicode=True),
        args.force,
    )
    write_text(
        tools_dir / "requirements.txt",
        "PyYAML>=6.0\nmatplotlib>=3.5\n",
        args.force,
    )
    readme = """# Project-local ROS Noetic run analysis

This directory is intentionally usable without an AI assistant.

## 1. Customize once

Edit `analysis/observation_contract.yaml` so each result signal has the correct source column, unit, frame and time semantics. Edit `analysis/analysis_profile.yaml` so the reading order matches the actual system.

## 2. Create one RUN bundle

```bash
python3 tools/analysis/result_bundle.py init reports EXP-0001 --run-id RUN-001 --workspace .
```

## 3. Capture native ROS evidence

```bash
python3 tools/analysis/ros_noetic_run_logger.py snapshot RUN_DIR --roswtf
python3 tools/analysis/ros_noetic_run_logger.py record RUN_DIR --topic /your/result_topic
python3 tools/analysis/ros_noetic_run_logger.py copy-logs RUN_DIR
```

Use rosbag1 for high-rate ROS messages. Keep normalized continuous values in `series/`, scalar metrics in `metrics.json`, and execution evidence in `logs/`. The logger registers created ROS artifacts into `manifest.yaml` when the RUN bundle exists.

## 4. Generate or adapt plots offline

For common localization/SLAM results use the bundled specialized plotting scripts. For a project-specific CSV:

```bash
python3 tools/analysis/plot_series.py RUN_DIR/series/diagnostics.csv \\
  --x distance_m --y frame_runtime_ms \\
  --output RUN_DIR/plots/runtime.png \\
  --title "Runtime vs distance" --ylabel ms
```

If the project needs a custom plot or log adapter, keep the adapter source under `tools/analysis/` with a CLI input/output contract. Do not leave the only working analysis code inside an AI conversation.

## 5. Generate the static human report

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
python3 tools/analysis/result_bundle.py validate RUN_DIR --closure --human-analysis
```

For runs that are expected to include native ROS runtime evidence, add `--ros-audit` to validation.

Open `RUN_DIR/report/index.html` in any browser. No database, service or AI session is required.
"""
    write_text(analysis_dir / "README.md", readme, args.force)
    print(json.dumps({
        "target_root": str(target),
        "system": args.system,
        "copied_tools": copied,
        "profile": "analysis/analysis_profile.yaml",
        "observation_contract": "analysis/observation_contract.yaml",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

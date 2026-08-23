#!/usr/bin/env python3
"""Install self-contained result-analysis tooling and contracts into a target ROS project."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml


TOOL_FILES = (
    "analyze_run.py",
    "plot_localization_result.py",
    "plot_slam_diagnostics.py",
    "compare_result_metrics.py",
    "result_bundle.py",
    "ros_noetic_run_logger.py",
)


def write_text(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_root")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = Path(args.target_root).expanduser().resolve()
    source_dir = Path(__file__).resolve().parent
    tools_dir = target / "tools" / "analysis"
    tools_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in TOOL_FILES:
        source = source_dir / name
        if not source.is_file():
            raise SystemExit(f"missing bundled tool: {source}")
        destination = tools_dir / name
        if destination.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite existing file: {destination}")
        shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(target)))
    analysis = target / "analysis"
    write_text(analysis / "README.md", """# Human-auditable ROS Noetic analysis\n\nThis analysis directory must remain usable without an AI assistant.\n\nCapture native ROS evidence:\n\n```bash\npython3 tools/analysis/ros_noetic_run_logger.py snapshot RUN_DIR\npython3 tools/analysis/ros_noetic_run_logger.py record RUN_DIR --topic /your/result_topic\npython3 tools/analysis/ros_noetic_run_logger.py copy-logs RUN_DIR\n```\n\nKeep normalized metrics in `metrics.json`, continuous diagnostics in `series/`, figures in `plots/`, and explanation in `report/`. Use rosbag1 as the raw high-rate record, not text logs.\n\nGenerate a standalone report:\n\n```bash\npython3 tools/analysis/analyze_run.py RUN_DIR --strict\n```\n""", args.force)
    print(json.dumps({"target_root": str(target), "copied_tools": copied}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

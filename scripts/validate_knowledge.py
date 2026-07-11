#!/usr/bin/env python3
"""Validate a project knowledge directory used by this skill."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

STATUS = {"candidate", "measured", "verified", "deprecated", "accepted", "open", "mitigated"}


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path}: invalid yaml: {exc}") from exc


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_dir():
        return [f"project directory not found: {path}"]
    required = ["README.md", "active_configuration.yaml", "topics.yaml", "timing.yaml", "CHANGELOG.md"]
    for name in required:
        if not (path / name).exists():
            errors.append(f"missing required file: {name}")

    yaml_files = sorted(path.rglob("*.yaml"))
    for yf in yaml_files:
        try:
            data = load_yaml(yf)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(data, dict):
            errors.append(f"{yf}: top level must be a mapping")
            continue
        status = data.get("status")
        if status is not None and status not in STATUS:
            errors.append(f"{yf}: unsupported status {status!r}")
        if "translation_m" in data and isinstance(data["translation_m"], dict):
            vals = data["translation_m"]
            if vals != "unknown" and not all(k in vals for k in ("x", "y", "z")):
                errors.append(f"{yf}: translation_m must include x/y/z")

    incident_dir = path / "incidents"
    if incident_dir.exists():
        for md in incident_dir.glob("*.md"):
            text = md.read_text(encoding="utf-8").lower()
            for sec in ("symptom", "root_cause", "fix", "regression"):
                if sec not in text:
                    errors.append(f"{md}: missing section {sec}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()
    errors = validate(args.project_dir)
    if errors:
        print("knowledge validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1
    count = len(list(args.project_dir.rglob("*")))
    print(f"knowledge validation passed: {args.project_dir} ({count} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

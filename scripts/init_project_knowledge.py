#!/usr/bin/env python3
"""Initialize a validated project-owned ROS knowledge directory."""
from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import shutil
import tempfile

import yaml

from schema_utils import validate_knowledge

DIRS = ["devices", "calibrations", "bags", "incidents", "decisions", "goals", "experiments", "formulas", "variable_mappings", "reasoning_chains", "audits", "regression_tests"]


def dump(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--knowledge-dir", default="project_knowledge")
    args = parser.parse_args()

    repository = args.repository.resolve()
    repository.mkdir(parents=True, exist_ok=True)
    relative = Path(args.knowledge_dir)
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("knowledge-dir must be repository-relative and cannot contain '..'")
    knowledge = (repository / relative).resolve()
    if repository != knowledge and repository not in knowledge.parents:
        raise SystemExit("knowledge-dir escapes repository")
    marker = repository / ".ros_debug_project.yaml"
    if marker.exists():
        raise SystemExit(".ros_debug_project.yaml already exists")
    if knowledge.exists():
        raise SystemExit(f"knowledge directory already exists: {knowledge}")

    staging_root = Path(tempfile.mkdtemp(prefix=".ros-knowledge-init-", dir=repository))
    staging = staging_root / "knowledge"
    try:
        staging.mkdir()
        for name in DIRS:
            (staging / name).mkdir()
        (staging / "README.md").write_text(
            f"# {args.project_id} project knowledge\n\n"
            "This knowledge base stores project facts, goals, experiments, formulas, formula-to-code variable mappings, "
            "stepwise reasoning chains, and logic audit reports. Verified conclusions must remain traceable to code, "
            "formula versions, units, frames, time bases, tests, and evidence.\n",
            encoding="utf-8",
        )
        (staging / "project.yaml").write_text(dump({
            "schema_version": 1,
            "project_id": args.project_id,
            "status": "candidate",
            "ros": {"families": [], "distributions": [], "build_tools": []},
            "repository": {"branch": "unknown", "commit": "unknown", "dirty": None},
            "evidence": [],
        }), encoding="utf-8")
        (staging / "project_model.yaml").write_text(dump({
            "schema_version": 1,
            "status": "candidate",
            "generated_at": None,
            "repository": {},
            "environment": {},
            "packages": [],
            "artifacts": {},
            "capabilities": {},
            "coverage": {
                "understanding_level": "L0", "static_scan": False, "build_verified": False,
                "runtime_snapshot": False, "reproduction": False, "regression_verified": False,
            },
            "limitations": ["Project evidence has not been collected yet."],
        }), encoding="utf-8")
        (staging / "active_configuration.yaml").write_text(dump({
            "schema_version": 1,
            "status": "candidate",
            "configuration": {},
            "active_devices": [],
            "active_calibrations": [],
            "verification": {"evidence": []},
        }), encoding="utf-8")
        (staging / "topics.yaml").write_text(dump({
            "schema_version": 1, "status": "candidate", "topics": {},
        }), encoding="utf-8")
        (staging / "timing.yaml").write_text(dump({
            "schema_version": 1, "status": "candidate", "clock_domains": {},
            "topic_time_sources": {}, "offsets": [],
        }), encoding="utf-8")
        (staging / "CHANGELOG.md").write_text(
            f"# Knowledge Changelog\n\n## {date.today().isoformat()} - initialized\n",
            encoding="utf-8",
        )
        schema_dir = Path(__file__).resolve().parents[1] / "references" / "schemas"
        errors = validate_knowledge(staging, schema_dir)
        if errors:
            for error in errors:
                print(f"- {error}")
            return 1
        knowledge.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, knowledge)
        try:
            marker.write_text(dump({
                "schema_version": 1,
                "project_id": args.project_id,
                "knowledge_dir": relative.as_posix(),
            }), encoding="utf-8")
        except Exception:
            shutil.rmtree(knowledge, ignore_errors=True)
            raise
        print(f"initialized {knowledge}")
        return 0
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

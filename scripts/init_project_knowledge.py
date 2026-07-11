#!/usr/bin/env python3
"""Initialize a complete project-owned ROS knowledge directory."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import yaml

from schema_utils import validate_knowledge

DIRS = ["devices", "calibrations", "bags", "incidents", "decisions", "regression_tests"]


def dump(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def write_new(path: Path, text: str) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--knowledge-dir", default="project_knowledge")
    args = parser.parse_args()

    repository = args.repository.resolve()
    relative = Path(args.knowledge_dir)
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("knowledge-dir must be repository-relative and cannot contain '..'")
    knowledge = (repository / relative).resolve()
    if repository != knowledge and repository not in knowledge.parents:
        raise SystemExit("knowledge-dir escapes repository")
    if (repository / ".ros_debug_project.yaml").exists():
        raise SystemExit(".ros_debug_project.yaml already exists")
    if knowledge.exists() and any(knowledge.iterdir()):
        raise SystemExit(f"knowledge directory is not empty: {knowledge}")

    repository.mkdir(parents=True, exist_ok=True)
    knowledge.mkdir(parents=True, exist_ok=True)
    for name in DIRS:
        (knowledge / name).mkdir(exist_ok=True)

    write_new(repository / ".ros_debug_project.yaml", dump({
        "schema_version": 1,
        "project_id": args.project_id,
        "knowledge_dir": args.knowledge_dir,
    }))
    write_new(knowledge / "README.md", f"# {args.project_id} project knowledge\n")
    write_new(knowledge / "project.yaml", dump({
        "schema_version": 1,
        "project_id": args.project_id,
        "status": "candidate",
        "ros": {"distributions": []},
        "repository": {"branch": "unknown", "commit": "unknown"},
    }))
    write_new(knowledge / "active_configuration.yaml", dump({
        "schema_version": 1,
        "status": "candidate",
        "configuration": {},
        "verification": {"evidence": []},
    }))
    write_new(knowledge / "topics.yaml", dump({
        "schema_version": 1,
        "status": "candidate",
        "topics": {},
    }))
    write_new(knowledge / "timing.yaml", dump({
        "schema_version": 1,
        "status": "candidate",
        "clock_domains": {},
        "topic_time_sources": {},
        "offsets": [],
    }))
    write_new(knowledge / "CHANGELOG.md", f"# Knowledge Changelog\n\n## {date.today().isoformat()} - initialized\n")

    schema_dir = Path(__file__).resolve().parents[1] / "references" / "schemas"
    errors = validate_knowledge(knowledge, schema_dir)
    if errors:
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"initialized {knowledge}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

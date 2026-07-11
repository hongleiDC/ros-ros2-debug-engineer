#!/usr/bin/env python3
"""Shared validation helpers for project-owned ROS knowledge."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

ROOT_FILES = ["README.md", "project.yaml", "active_configuration.yaml", "topics.yaml", "timing.yaml", "CHANGELOG.md"]
ROOT_DIRS = ["devices", "calibrations", "bags", "incidents", "decisions", "regression_tests"]
SCHEMA_BY_ROOT = {
    "project.yaml": None,
    "active_configuration.yaml": None,
    "topics.yaml": None,
    "timing.yaml": None,
}
SCHEMA_BY_DIR = {
    "devices": "device.schema.yaml",
    "calibrations": "calibration.schema.yaml",
    "bags": "bag.schema.yaml",
}
INCIDENT_SECTIONS = ["symptom", "root_cause", "evidence", "fix", "regression", "forbidden_regressions"]
INCIDENT_STATUSES = {"open", "mitigated", "verified", "deprecated"}


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path}: invalid yaml: {exc}") from exc


def validate_simple_schema(data: dict[str, Any], schema: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in data:
            errors.append(f"{path}: missing required field {key}")
    allowed = schema.get("status_values")
    if allowed and "status" in data and data["status"] not in allowed:
        errors.append(f"{path}: unsupported status {data['status']!r}")
    return errors


def validate_incident(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for section in INCIDENT_SECTIONS:
        if f"## {section}" not in lowered:
            errors.append(f"{path}: missing section {section}")
    status = None
    for line in text.splitlines():
        if line.strip().lower().startswith("- status:"):
            status = line.split(":", 1)[1].strip().lower()
            break
    if status is None:
        errors.append(f"{path}: missing '- status:' metadata")
    elif status not in INCIDENT_STATUSES:
        errors.append(f"{path}: unsupported incident status {status!r}")
    return errors


def validate_knowledge(knowledge_dir: Path, schema_dir: Path) -> list[str]:
    knowledge_dir = knowledge_dir.resolve()
    errors: list[str] = []
    if not knowledge_dir.is_dir():
        return [f"knowledge directory not found: {knowledge_dir}"]
    for name in ROOT_FILES:
        if not (knowledge_dir / name).is_file():
            errors.append(f"missing required file: {name}")
    for name in ROOT_DIRS:
        if not (knowledge_dir / name).is_dir():
            errors.append(f"missing required directory: {name}/")
    for yaml_path in sorted(knowledge_dir.rglob("*.yaml")):
        try:
            data = load_yaml(yaml_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(data, dict):
            errors.append(f"{yaml_path}: top level must be a mapping")
            continue
        rel = yaml_path.relative_to(knowledge_dir)
        schema_name = SCHEMA_BY_ROOT.get(rel.name) if len(rel.parts) == 1 else SCHEMA_BY_DIR.get(rel.parts[0])
        if schema_name:
            schema = load_yaml(schema_dir / schema_name)
            if isinstance(schema, dict):
                errors.extend(validate_simple_schema(data, schema, yaml_path))
    incident_dir = knowledge_dir / "incidents"
    if incident_dir.is_dir():
        for path in sorted(incident_dir.glob("*.md")):
            errors.extend(validate_incident(path))
    return errors

#!/usr/bin/env python3
"""JSON Schema validation helpers for project-owned ROS knowledge."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import re

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ROOT_FILES = [
    "README.md", "project.yaml", "project_model.yaml", "active_configuration.yaml",
    "topics.yaml", "timing.yaml", "CHANGELOG.md",
]
ROOT_DIRS = ["devices", "calibrations", "bags", "incidents", "decisions", "regression_tests"]
SCHEMA_BY_ROOT = {
    "project.yaml": "project.schema.yaml",
    "project_model.yaml": "project_model.schema.yaml",
    "active_configuration.yaml": "active_configuration.schema.yaml",
    "topics.yaml": "topics.schema.yaml",
    "timing.yaml": "timing.schema.yaml",
}
SCHEMA_BY_DIR = {
    "devices": "device.schema.yaml",
    "calibrations": "calibration.schema.yaml",
    "bags": "bag.schema.yaml",
    "incidents": "incident.schema.yaml",
    "decisions": "decision.schema.yaml",
    "regression_tests": "regression_test.schema.yaml",
}
ID_FIELD_BY_DIR = {
    "devices": "device_id",
    "calibrations": "calibration_id",
    "bags": "bag_id",
    "incidents": "incident_id",
    "decisions": "decision_id",
    "regression_tests": "test_id",
}
LEGACY_INCIDENT_SECTIONS = ["symptom", "root_cause", "evidence", "fix", "regression", "forbidden_regressions"]


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path}: invalid yaml: {exc}") from exc


def validate_schema(data: Any, schema_path: Path, path: Path) -> list[str]:
    try:
        schema = load_yaml(schema_path)
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"{schema_path}: invalid JSON Schema: {exc}"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{path}: {location}: {error.message}")
    return errors


def validate_legacy_incident(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    errors: list[str] = []
    for section in LEGACY_INCIDENT_SECTIONS:
        if f"## {section}" not in text:
            errors.append(f"{path}: missing legacy section {section}")
    if not re.search(r"^-\s*status:\s*(open|mitigated|verified|deprecated)\s*$", text, re.MULTILINE):
        errors.append(f"{path}: missing or invalid legacy incident status")
    return errors


def is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def collect_records(knowledge_dir: Path) -> tuple[dict[str, list[tuple[Path, dict[str, Any]]]], list[str]]:
    records: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    errors: list[str] = []
    for directory in ROOT_DIRS:
        folder = knowledge_dir / directory
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
            try:
                data = load_yaml(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if isinstance(data, dict):
                records[directory].append((path, data))
    return records, errors


def validate_cross_references(knowledge_dir: Path, records: dict[str, list[tuple[Path, dict[str, Any]]]]) -> list[str]:
    errors: list[str] = []
    ids: dict[str, set[str]] = {}
    for directory, items in records.items():
        field = ID_FIELD_BY_DIR[directory]
        seen: dict[str, Path] = {}
        ids[directory] = set()
        for path, data in items:
            value = data.get(field)
            if not isinstance(value, str):
                continue
            if value in seen:
                errors.append(f"{path}: duplicate {field} {value!r}; first defined in {seen[value]}")
            else:
                seen[value] = path
                ids[directory].add(value)

    config_path = knowledge_dir / "active_configuration.yaml"
    if config_path.is_file():
        try:
            config = load_yaml(config_path)
        except ValueError:
            config = None
        if isinstance(config, dict):
            for value in config.get("active_devices", []) or []:
                if value not in ids.get("devices", set()):
                    errors.append(f"{config_path}: active device {value!r} does not exist")
            for value in config.get("active_calibrations", []) or []:
                if value not in ids.get("calibrations", set()):
                    errors.append(f"{config_path}: active calibration {value!r} does not exist")

    incident_ids = ids.get("incidents", set())
    for path, data in records.get("regression_tests", []):
        for incident_id in data.get("incident_ids", []) or []:
            if incident_id not in incident_ids:
                errors.append(f"{path}: referenced incident {incident_id!r} does not exist")
    return errors


def validate_knowledge(knowledge_dir: Path, schema_dir: Path, allow_transaction: bool = False) -> list[str]:
    knowledge_dir = knowledge_dir.resolve()
    schema_dir = schema_dir.resolve()
    errors: list[str] = []
    if not knowledge_dir.is_dir():
        return [f"knowledge directory not found: {knowledge_dir}"]
    if (knowledge_dir / ".knowledge-transaction.json").exists() and not allow_transaction:
        errors.append("unfinished knowledge transaction exists; run update_knowledge.py to recover before validating")

    for path in knowledge_dir.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlink is not allowed in knowledge directory: {path}")
        try:
            resolved = path.resolve()
        except OSError as exc:
            errors.append(f"cannot resolve {path}: {exc}")
            continue
        if not is_inside(resolved, knowledge_dir):
            errors.append(f"path escapes knowledge directory: {path}")

    for name in ROOT_FILES:
        if not (knowledge_dir / name).is_file():
            errors.append(f"missing required file: {name}")
    for name in ROOT_DIRS:
        if not (knowledge_dir / name).is_dir():
            errors.append(f"missing required directory: {name}/")

    for name, schema_name in SCHEMA_BY_ROOT.items():
        path = knowledge_dir / name
        if not path.is_file():
            continue
        try:
            data = load_yaml(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_schema(data, schema_dir / schema_name, path))

    records, record_errors = collect_records(knowledge_dir)
    errors.extend(record_errors)
    for directory, items in records.items():
        schema_name = SCHEMA_BY_DIR[directory]
        for path, data in items:
            errors.extend(validate_schema(data, schema_dir / schema_name, path))

    incident_dir = knowledge_dir / "incidents"
    if incident_dir.is_dir():
        for path in sorted(incident_dir.glob("*.md")):
            errors.extend(validate_legacy_incident(path))

    errors.extend(validate_cross_references(knowledge_dir, records))
    return errors

#!/usr/bin/env python3
"""JSON Schema validation helpers for project-owned ROS knowledge."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import re

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from goal_utils import contract_hash

ROOT_FILES = [
    "README.md", "project.yaml", "project_model.yaml", "active_configuration.yaml",
    "topics.yaml", "timing.yaml", "CHANGELOG.md",
]
ROOT_DIRS = ["devices", "calibrations", "bags", "incidents", "decisions", "goals", "experiments", "formulas", "variable_mappings", "reasoning_chains", "audits", "regression_tests"]
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
    "goals": "goal.schema.yaml",
    "experiments": "experiment.schema.yaml",
    "formulas": "formula.schema.yaml",
    "variable_mappings": "variable_mapping.schema.yaml",
    "reasoning_chains": "reasoning_chain.schema.yaml",
    "audits": "logic_audit.schema.yaml",
    "regression_tests": "regression_test.schema.yaml",
}
ID_FIELD_BY_DIR = {
    "devices": "device_id",
    "calibrations": "calibration_id",
    "bags": "bag_id",
    "incidents": "incident_id",
    "decisions": "decision_id",
    "goals": "goal_id",
    "experiments": "experiment_id",
    "formulas": "formula_id",
    "variable_mappings": "mapping_id",
    "reasoning_chains": "reasoning_id",
    "audits": "audit_id",
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

    active_goals = [
        (path, data) for path, data in records.get("goals", [])
        if data.get("status") == "active"
    ]
    if len(active_goals) > 1:
        active_ids = ", ".join(str(data.get("goal_id")) for _, data in active_goals)
        errors.append(f"multiple active goals are not allowed: {active_ids}")

    goal_ids = ids.get("goals", set())
    goal_criteria: dict[str, set[str]] = {}
    goal_milestones: dict[str, set[str]] = {}
    goal_records_by_id: dict[str, dict[str, Any]] = {}
    for path, data in records.get("goals", []):
        goal_id = data.get("goal_id")
        if not isinstance(goal_id, str):
            continue
        goal_records_by_id[goal_id] = data
        if data.get("contract_hash") != contract_hash(data):
            errors.append(f"{path}: contract_hash does not match the current goal contract")
        contract = data.get("contract", {}) if isinstance(data.get("contract"), dict) else {}
        progress = data.get("progress", {}) if isinstance(data.get("progress"), dict) else {}
        goal_criteria[goal_id] = {
            item.get("criterion_id") for item in contract.get("success_criteria", []) or []
            if isinstance(item, dict) and isinstance(item.get("criterion_id"), str)
        }
        goal_milestones[goal_id] = {
            item.get("milestone_id") for item in progress.get("milestones", []) or []
            if isinstance(item, dict) and isinstance(item.get("milestone_id"), str)
        }

    incident_ids = ids.get("incidents", set())
    experiment_ids = ids.get("experiments", set())
    for path, data in records.get("regression_tests", []):
        for incident_id in data.get("incident_ids", []) or []:
            if incident_id not in incident_ids:
                errors.append(f"{path}: referenced incident {incident_id!r} does not exist")
        for experiment_id in data.get("experiment_ids", []) or []:
            if experiment_id not in experiment_ids:
                errors.append(f"{path}: referenced experiment {experiment_id!r} does not exist")

    formula_ids = ids.get("formulas", set())
    mapping_ids = ids.get("variable_mappings", set())
    formula_versions: dict[str, str] = {}
    formula_symbols: dict[str, set[str]] = {}
    for path, data in records.get("formulas", []):
        formula_id = data.get("formula_id")
        if not isinstance(formula_id, str):
            continue
        formula_versions[formula_id] = str(data.get("version", ""))
        formula_symbols[formula_id] = {
            item.get("symbol_id") for item in data.get("symbols", []) or []
            if isinstance(item, dict) and isinstance(item.get("symbol_id"), str)
        }
        alignment = data.get("goal_alignment", {}) if isinstance(data.get("goal_alignment"), dict) else {}
        aligned_goal_id = alignment.get("goal_id")
        if aligned_goal_id is not None:
            if aligned_goal_id not in goal_ids:
                errors.append(f"{path}: referenced goal {aligned_goal_id!r} does not exist")
            for criterion_id in alignment.get("criterion_ids", []) or []:
                if criterion_id not in goal_criteria.get(aligned_goal_id, set()):
                    errors.append(f"{path}: referenced criterion {criterion_id!r} does not exist in {aligned_goal_id}")

    for path, data in records.get("variable_mappings", []):
        formula_id = data.get("formula_id")
        if formula_id not in formula_ids:
            errors.append(f"{path}: referenced formula {formula_id!r} does not exist")
            continue
        if data.get("formula_version") != formula_versions.get(formula_id):
            errors.append(f"{path}: formula version does not match {formula_id}")
        seen_entries: set[str] = set()
        for entry in data.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("entry_id")
            if isinstance(entry_id, str):
                if entry_id in seen_entries:
                    errors.append(f"{path}: duplicate mapping entry {entry_id!r}")
                seen_entries.add(entry_id)
            symbol_id = entry.get("symbol_id")
            if symbol_id not in formula_symbols.get(formula_id, set()):
                errors.append(f"{path}: referenced symbol {symbol_id!r} does not exist in {formula_id}")
        alignment = data.get("goal_alignment", {}) if isinstance(data.get("goal_alignment"), dict) else {}
        aligned_goal_id = alignment.get("goal_id")
        if aligned_goal_id is not None:
            if aligned_goal_id not in goal_ids:
                errors.append(f"{path}: referenced goal {aligned_goal_id!r} does not exist")
            for criterion_id in alignment.get("criterion_ids", []) or []:
                if criterion_id not in goal_criteria.get(aligned_goal_id, set()):
                    errors.append(f"{path}: referenced criterion {criterion_id!r} does not exist in {aligned_goal_id}")

    for path, data in records.get("reasoning_chains", []):
        alignment = data.get("goal_alignment", {}) if isinstance(data.get("goal_alignment"), dict) else {}
        aligned_goal_id = alignment.get("goal_id")
        if aligned_goal_id not in goal_ids:
            errors.append(f"{path}: referenced goal {aligned_goal_id!r} does not exist")
        else:
            for criterion_id in alignment.get("criterion_ids", []) or []:
                if criterion_id not in goal_criteria.get(aligned_goal_id, set()):
                    errors.append(f"{path}: referenced criterion {criterion_id!r} does not exist in {aligned_goal_id}")
            milestone_id = alignment.get("milestone_id")
            if milestone_id not in goal_milestones.get(aligned_goal_id, set()):
                errors.append(f"{path}: referenced milestone {milestone_id!r} does not exist in {aligned_goal_id}")
        for ref in data.get("formula_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            formula_id = ref.get("formula_id")
            if formula_id not in formula_ids:
                errors.append(f"{path}: referenced formula {formula_id!r} does not exist")
            elif ref.get("version") != formula_versions.get(formula_id):
                errors.append(f"{path}: formula version does not match {formula_id}")
        for mapping_id in data.get("mapping_ids", []) or []:
            if mapping_id not in mapping_ids:
                errors.append(f"{path}: referenced mapping {mapping_id!r} does not exist")

    for path, data in records.get("experiments", []):
        alignment = data.get("goal_alignment", {}) if isinstance(data.get("goal_alignment"), dict) else {}
        goal_id = alignment.get("goal_id")
        if goal_id is not None:
            if goal_id not in goal_ids:
                errors.append(f"{path}: referenced goal {goal_id!r} does not exist")
            else:
                goal_record = goal_records_by_id.get(goal_id, {})
                if alignment.get("contract_hash") != goal_record.get("contract_hash"):
                    errors.append(f"{path}: goal contract hash does not match {goal_id}")
                primary_goal = goal_record.get("contract", {}).get("primary_goal") if isinstance(goal_record.get("contract"), dict) else None
                if alignment.get("primary_goal_snapshot") != primary_goal:
                    errors.append(f"{path}: primary goal snapshot does not match {goal_id}")
                for criterion_id in alignment.get("criterion_ids", []) or []:
                    if criterion_id not in goal_criteria.get(goal_id, set()):
                        errors.append(f"{path}: referenced criterion {criterion_id!r} does not exist in {goal_id}")
                milestone_id = alignment.get("milestone_id")
                if milestone_id not in goal_milestones.get(goal_id, set()):
                    errors.append(f"{path}: referenced milestone {milestone_id!r} does not exist in {goal_id}")
        scope = data.get("scope", {}) if isinstance(data.get("scope"), dict) else {}
        duplicate_check = data.get("duplicate_check", {}) if isinstance(data.get("duplicate_check"), dict) else {}
        references = []
        references.extend(scope.get("parent_experiment_ids", []) or [])
        references.extend(scope.get("compare_to_experiment_ids", []) or [])
        references.extend(duplicate_check.get("exact_match_ids", []) or [])
        references.extend(duplicate_check.get("similar_match_ids", []) or [])
        for experiment_id in references:
            if experiment_id not in experiment_ids:
                errors.append(f"{path}: referenced experiment {experiment_id!r} does not exist")
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

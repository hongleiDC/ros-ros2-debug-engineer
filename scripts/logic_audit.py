#!/usr/bin/env python3
"""Audit persisted reasoning, formulas, and formula-to-code mappings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml

from goal_utils import atomic_write_yaml
from lock_utils import file_lock
from schema_utils import load_yaml, validate_knowledge, validate_schema

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "references" / "schemas"
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit(workspace: Path | None) -> str | None:
    if workspace is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            text=True, capture_output=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def load_records(folder: Path, id_field: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if not folder.is_dir():
        return records, errors
    for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
        try:
            data = load_yaml(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(data, dict):
            errors.append(f"{path}: record must be a mapping")
            continue
        record_id = data.get(id_field)
        if not isinstance(record_id, str):
            errors.append(f"{path}: missing {id_field}")
            continue
        data["__path__"] = path
        records[record_id] = data
    return records, errors


def explicit_unit_conflict(identifier: str, code_unit: str) -> str | None:
    name = identifier.lower()
    unit = code_unit.strip().lower().replace(" ", "")
    conflicts = [
        (("rad", "rad/s", "rad/s^2"), ("_deg", "_deg_s", "_degree")),
        (("deg", "deg/s", "deg/s^2"), ("_rad", "_rad_s", "_radian")),
        (("s", "second", "seconds"), ("_ms", "_us", "_ns")),
        (("ms", "millisecond", "milliseconds"), ("_sec", "_seconds")),
        (("m", "meter", "metre", "meters", "metres"), ("_mm", "_cm")),
        (("mm", "millimeter", "millimetre"), ("_m", "_meter")),
    ]
    for units, suffixes in conflicts:
        if unit in units and any(name.endswith(suffix) for suffix in suffixes):
            return f"identifier {identifier!r} suggests a unit that conflicts with {code_unit!r}"
    return None


def add_finding(findings: list[dict[str, Any]], severity: str, category: str,
                record_id: str | None, path: str | None, message: str, remediation: str) -> None:
    findings.append({
        "finding_id": f"FIND-{len(findings) + 1}",
        "severity": severity,
        "category": category,
        "record_id": record_id,
        "path": path,
        "message": message,
        "remediation": remediation,
    })


def audit(knowledge: Path, workspace: Path | None, audit_id: str, allow_empty: bool = False) -> dict[str, Any]:
    formulas, load_formula_errors = load_records(knowledge / "formulas", "formula_id")
    mappings, load_mapping_errors = load_records(knowledge / "variable_mappings", "mapping_id")
    reasoning, load_reasoning_errors = load_records(knowledge / "reasoning_chains", "reasoning_id")
    findings: list[dict[str, Any]] = []
    formula_paths = {record_id: str(record.get("__path__")) for record_id, record in formulas.items()}
    mapping_paths = {record_id: str(record.get("__path__")) for record_id, record in mappings.items()}
    reasoning_paths = {record_id: str(record.get("__path__")) for record_id, record in reasoning.items()}
    for message in validate_knowledge(knowledge, SCHEMA_DIR):
        add_finding(findings, "error", "knowledge_validation", None, str(knowledge), message,
                    "Repair the project knowledge structure and cross references before logic auditing.")
    if not allow_empty:
        if not formulas:
            add_finding(findings, "error", "no_formula_records", None, str(knowledge / "formulas"),
                        "no formula records exist", "Create FORM records for every formula-bearing implementation before auditing.")
        if not mappings:
            add_finding(findings, "error", "no_mapping_records", None, str(knowledge / "variable_mappings"),
                        "no formula-to-code mapping records exist", "Create MAP records that bind formula symbols to code variables and parameters.")
        if not reasoning:
            add_finding(findings, "error", "no_reasoning_records", None, str(knowledge / "reasoning_chains"),
                        "no persisted reasoning chains exist", "Create REAS records for the claims used to justify the code logic.")

    for message in load_formula_errors + load_mapping_errors + load_reasoning_errors:
        add_finding(findings, "error", "invalid_record", None, None, message, "Fix YAML syntax and required identifiers.")

    formula_symbols: dict[str, dict[str, dict[str, Any]]] = {}
    formula_versions: dict[str, str] = {}
    required_symbols: dict[str, set[str]] = {}
    for formula_id, record in formulas.items():
        path = str(record.pop("__path__"))
        schema_errors = validate_schema(record, SCHEMA_DIR / "formula.schema.yaml", Path(path))
        for message in schema_errors:
            add_finding(findings, "error", "formula_schema", formula_id, path, message, "Make the formula record conform to formula.schema.yaml.")
        symbols: dict[str, dict[str, Any]] = {}
        for symbol in record.get("symbols", []) or []:
            symbol_id = symbol.get("symbol_id")
            if not isinstance(symbol_id, str):
                continue
            if symbol_id in symbols:
                add_finding(findings, "error", "duplicate_symbol", formula_id, path,
                            f"duplicate symbol_id {symbol_id}", "Use one unique symbol_id per formula version.")
            symbols[symbol_id] = symbol
        formula_symbols[formula_id] = symbols
        formula_versions[formula_id] = str(record.get("version", ""))
        required_symbols[formula_id] = {
            sid for sid, symbol in symbols.items() if symbol.get("required_in_code") is True
        }
        assumption_ids = {item.get("assumption_id") for item in record.get("assumptions", []) or []}
        if record.get("status") == "verified":
            unverified_assumptions = [
                item.get("assumption_id") for item in record.get("assumptions", []) or []
                if isinstance(item, dict) and item.get("status") != "verified"
            ]
            if unverified_assumptions:
                add_finding(findings, "error", "verified_formula_with_unverified_assumptions", formula_id, path,
                            f"verified formula has unverified assumptions: {', '.join(map(str, unverified_assumptions))}",
                            "Verify the assumptions or downgrade the formula status.")
        for step in record.get("derivation", []) or []:
            for symbol_id in (step.get("input_symbol_ids", []) or []) + (step.get("output_symbol_ids", []) or []):
                if symbol_id not in symbols:
                    add_finding(findings, "error", "unknown_formula_symbol", formula_id, path,
                                f"derivation {step.get('step_id')} references unknown symbol {symbol_id}",
                                "Define the symbol or correct the derivation reference.")
            for assumption_id in step.get("assumption_refs", []) or []:
                if assumption_id not in assumption_ids:
                    add_finding(findings, "error", "unknown_assumption", formula_id, path,
                                f"derivation {step.get('step_id')} references unknown assumption {assumption_id}",
                                "Define the assumption or remove the invalid reference.")

    mapped_symbols: dict[str, set[str]] = {formula_id: set() for formula_id in formulas}
    identifier_semantics: dict[str, tuple[str, str, str, str, str, str]] = {}
    for mapping_id, record in mappings.items():
        path = str(record.pop("__path__"))
        schema_errors = validate_schema(record, SCHEMA_DIR / "variable_mapping.schema.yaml", Path(path))
        for message in schema_errors:
            add_finding(findings, "error", "mapping_schema", mapping_id, path, message, "Make the mapping record conform to variable_mapping.schema.yaml.")
        formula_id = record.get("formula_id")
        if formula_id not in formulas:
            add_finding(findings, "error", "missing_formula", mapping_id, path,
                        f"referenced formula {formula_id!r} does not exist", "Create the formula record or correct formula_id.")
            continue
        if record.get("formula_version") != formula_versions.get(formula_id):
            add_finding(findings, "error", "formula_version_mismatch", mapping_id, path,
                        f"mapping version {record.get('formula_version')!r} does not match formula version {formula_versions.get(formula_id)!r}",
                        "Update the mapping and re-audit the implementation against the current formula version.")
        implementation_file = record.get("implementation", {}).get("file")
        if record.get("status") == "verified":
            if any(entry.get("status") != "verified" for entry in record.get("entries", []) or [] if isinstance(entry, dict)):
                add_finding(findings, "error", "verified_mapping_with_unverified_entries", mapping_id, path,
                            "mapping is verified but one or more entries are not verified",
                            "Verify each symbol-to-code correspondence or downgrade the mapping status.")
            verification = record.get("verification", {}) if isinstance(record.get("verification"), dict) else {}
            if not verification.get("test_refs") or not verification.get("hand_calculation_refs"):
                add_finding(findings, "error", "verified_mapping_without_tests", mapping_id, path,
                            "verified mapping lacks test references or hand-calculation references",
                            "Attach unit tests and at least one independently checkable calculation.")
        for entry in record.get("entries", []) or []:
            symbol_id = entry.get("symbol_id")
            if symbol_id not in formula_symbols.get(formula_id, {}):
                add_finding(findings, "error", "unknown_mapping_symbol", mapping_id, path,
                            f"entry {entry.get('entry_id')} references unknown symbol {symbol_id}",
                            "Map only symbols defined by the referenced formula version.")
            else:
                mapped_symbols.setdefault(formula_id, set()).add(symbol_id)
                symbol = formula_symbols[formula_id][symbol_id]
                for field, symbol_field in (("physical_meaning", "meaning"), ("formula_unit", "canonical_unit"),
                                            ("frame", "frame"), ("direction", "direction"),
                                            ("time_basis", "time_basis"), ("shape", "shape")):
                    if entry.get(field) != symbol.get(symbol_field):
                        add_finding(findings, "error", "semantic_mismatch", mapping_id, path,
                                    f"{entry.get('entry_id')} field {field}={entry.get(field)!r} does not match {formula_id}/{symbol_id} {symbol_field}={symbol.get(symbol_field)!r}",
                                    "Make the mapping semantics identical to the formula symbol definition or create a new formula version.")
            code_identifier = str(entry.get("code_identifier", ""))
            if re.fullmatch(r"(?:tmp|temp|val|value|data|data[0-9]+|x[0-9]+|y[0-9]+|a|b|c)", code_identifier, re.IGNORECASE):
                add_finding(findings, "error", "opaque_identifier", mapping_id, path,
                            f"key formula variable uses semantically opaque identifier {code_identifier!r}",
                            "Rename it to encode the physical quantity and, where practical, its unit or frame.")
            semantics = (
                str(entry.get("physical_meaning", "")), str(entry.get("code_unit", "")),
                str(entry.get("frame", "")), str(entry.get("direction", "")),
                str(entry.get("time_basis", "")), str(entry.get("shape", "")),
            )
            previous = identifier_semantics.get(code_identifier)
            if previous is not None and previous != semantics:
                add_finding(findings, "error", "identifier_semantic_collision", mapping_id, path,
                            f"code identifier {code_identifier!r} is mapped to conflicting semantics", "Rename or split the variable so one identifier has one physical meaning.")
            identifier_semantics[code_identifier] = semantics
            conflict = explicit_unit_conflict(code_identifier, str(entry.get("code_unit", "")))
            if conflict:
                add_finding(findings, "error", "name_unit_conflict", mapping_id, path, conflict,
                            "Rename the variable or correct the recorded code unit.")
            conversion = entry.get("conversion", {}) if isinstance(entry.get("conversion"), dict) else {}
            if entry.get("formula_unit") != entry.get("code_unit"):
                if not conversion.get("required") or not str(conversion.get("expression", "")).strip():
                    add_finding(findings, "error", "missing_unit_conversion", mapping_id, path,
                                f"{code_identifier!r} uses {entry.get('code_unit')!r} while the formula uses {entry.get('formula_unit')!r} without an explicit conversion",
                                "Record the exact conversion expression, direction, and conversion tests.")
                if not conversion.get("test_refs"):
                    add_finding(findings, "error", "untested_unit_conversion", mapping_id, path,
                                f"unit conversion for {code_identifier!r} has no test reference", "Add a hand-calculation or unit test covering the conversion.")
            source = entry.get("source", {}) if isinstance(entry.get("source"), dict) else {}
            source_file = source.get("file") or implementation_file
            if workspace is not None and isinstance(source_file, str):
                code_path = (workspace / source_file).resolve()
                if workspace != code_path and workspace not in code_path.parents:
                    add_finding(findings, "error", "source_path_escape", mapping_id, path,
                                f"source path escapes workspace: {source_file}", "Use a repository-relative source path.")
                elif not code_path.is_file():
                    add_finding(findings, "error", "missing_source_file", mapping_id, path,
                                f"source file not found: {source_file}", "Update the mapping after moving or deleting code.")
                else:
                    text = code_path.read_text(encoding="utf-8", errors="replace")
                    if not re.search(rf"\b{re.escape(code_identifier)}\b", text):
                        add_finding(findings, "error", "identifier_not_found", mapping_id, path,
                                    f"identifier {code_identifier!r} was not found in {source_file}",
                                    "Correct the code location or update the formula-to-code mapping.")
                    line_start = source.get("line_start")
                    line_end = source.get("line_end")
                    if isinstance(line_start, int) and isinstance(line_end, int):
                        if line_end < line_start:
                            add_finding(findings, "error", "invalid_line_range", mapping_id, path,
                                        f"line_end {line_end} precedes line_start {line_start}", "Correct the source line range.")
                        lines = text.splitlines()
                        snippet = "\n".join(lines[max(0, line_start - 1):min(len(lines), line_end)])
                        if snippet and not re.search(rf"\b{re.escape(code_identifier)}\b", snippet):
                            add_finding(findings, "warning", "stale_line_range", mapping_id, path,
                                        f"identifier {code_identifier!r} exists in the file but not in recorded lines {line_start}-{line_end}",
                                        "Refresh line_start and line_end for the current commit.")

    for formula_id, required in required_symbols.items():
        missing = sorted(required - mapped_symbols.get(formula_id, set()))
        for symbol_id in missing:
            add_finding(findings, "error", "required_symbol_unmapped", formula_id,
                        formula_paths.get(formula_id),
                        f"required formula symbol {symbol_id} has no code mapping", "Create or update a MAP record before accepting the implementation.")

    goal_records, _ = load_records(knowledge / "goals", "goal_id")
    goal_criteria: dict[str, set[str]] = {}
    goal_milestones: dict[str, set[str]] = {}
    for goal_id, goal in goal_records.items():
        goal_criteria[goal_id] = {
            item.get("criterion_id") for item in goal.get("contract", {}).get("success_criteria", []) or []
            if isinstance(item, dict)
        }
        goal_milestones[goal_id] = {
            item.get("milestone_id") for item in goal.get("progress", {}).get("milestones", []) or []
            if isinstance(item, dict)
        }

    for reasoning_id, record in reasoning.items():
        path = str(record.pop("__path__"))
        schema_errors = validate_schema(record, SCHEMA_DIR / "reasoning_chain.schema.yaml", Path(path))
        for message in schema_errors:
            add_finding(findings, "error", "reasoning_schema", reasoning_id, path, message, "Make the reasoning chain conform to reasoning_chain.schema.yaml.")
        alignment = record.get("goal_alignment", {}) if isinstance(record.get("goal_alignment"), dict) else {}
        goal_id = alignment.get("goal_id")
        if goal_id not in goal_records:
            add_finding(findings, "error", "missing_goal", reasoning_id, path,
                        f"referenced goal {goal_id!r} does not exist", "Link the reasoning chain to an existing goal contract.")
        else:
            for criterion_id in alignment.get("criterion_ids", []) or []:
                if criterion_id not in goal_criteria.get(goal_id, set()):
                    add_finding(findings, "error", "missing_goal_criterion", reasoning_id, path,
                                f"criterion {criterion_id!r} does not exist in {goal_id}", "Use a criterion defined by the active goal contract.")
            milestone_id = alignment.get("milestone_id")
            if milestone_id not in goal_milestones.get(goal_id, set()):
                add_finding(findings, "error", "missing_goal_milestone", reasoning_id, path,
                            f"milestone {milestone_id!r} does not exist in {goal_id}", "Use a milestone defined by the goal record.")
        for ref in record.get("formula_refs", []) or []:
            formula_id = ref.get("formula_id") if isinstance(ref, dict) else None
            if formula_id not in formulas:
                add_finding(findings, "error", "missing_reasoning_formula", reasoning_id, path,
                            f"reasoning references missing formula {formula_id!r}", "Create the formula record or remove the invalid reference.")
            elif ref.get("version") != formula_versions.get(formula_id):
                add_finding(findings, "error", "reasoning_formula_version_mismatch", reasoning_id, path,
                            f"reasoning formula version for {formula_id} is stale", "Re-derive the chain against the current formula version.")
        for mapping_id in record.get("mapping_ids", []) or []:
            if mapping_id not in mappings:
                add_finding(findings, "error", "missing_reasoning_mapping", reasoning_id, path,
                            f"reasoning references missing mapping {mapping_id!r}", "Create the mapping record or correct the reference.")
        conditions = {item.get("condition_id") for item in record.get("known_conditions", []) or [] if isinstance(item, dict)}
        assumptions = {item.get("assumption_id") for item in record.get("assumptions", []) or [] if isinstance(item, dict)}
        seen_steps: set[str] = set()
        step_statuses: list[str] = []
        for step in record.get("steps", []) or []:
            step_id = step.get("step_id")
            for premise in step.get("premise_refs", []) or []:
                if premise.startswith("STEP-") and premise not in seen_steps:
                    add_finding(findings, "error", "reasoning_forward_or_missing_step", reasoning_id, path,
                                f"{step_id} references {premise} before it is established", "Order steps topologically and reference only prior steps.")
                elif premise.startswith("COND-") and premise not in conditions:
                    add_finding(findings, "error", "reasoning_missing_condition", reasoning_id, path,
                                f"{step_id} references unknown condition {premise}", "Define the condition or fix the premise reference.")
                elif premise.startswith("ASM-") and premise not in assumptions:
                    add_finding(findings, "error", "reasoning_missing_assumption", reasoning_id, path,
                                f"{step_id} references unknown assumption {premise}", "Define the assumption or fix the premise reference.")
            seen_steps.add(str(step_id))
            step_statuses.append(str(step.get("verification_status")))
            if not step.get("evidence_refs") and step.get("verification_status") in {"measured", "verified"}:
                add_finding(findings, "error", "verified_step_without_evidence", reasoning_id, path,
                            f"{step_id} is {step.get('verification_status')} but has no evidence", "Attach code, log, test, bag, or hand-calculation evidence.")
            if not str(step.get("counterexample_check", "")).strip():
                add_finding(findings, "error", "missing_counterexample_check", reasoning_id, path,
                            f"{step_id} has no counterexample or boundary check", "Record how the inference could fail and what was checked.")
        conclusion = record.get("conclusion", {}) if isinstance(record.get("conclusion"), dict) else {}
        if conclusion.get("status") == "verified":
            unverified_conditions = [
                item.get("condition_id") for item in record.get("known_conditions", []) or []
                if isinstance(item, dict) and item.get("status") != "verified"
            ]
            unverified_assumptions = [
                item.get("assumption_id") for item in record.get("assumptions", []) or []
                if isinstance(item, dict) and item.get("status") != "verified"
            ]
            if unverified_conditions or unverified_assumptions:
                add_finding(findings, "error", "verified_with_unverified_premises", reasoning_id, path,
                            f"verified conclusion relies on unverified premises: {unverified_conditions + unverified_assumptions}",
                            "Verify every known condition and assumption or downgrade the conclusion.")
            if record.get("unresolved"):
                add_finding(findings, "error", "verified_with_unresolved", reasoning_id, path,
                            "reasoning is verified while unresolved items remain", "Resolve the unknowns or downgrade the conclusion status.")
            if any(status != "verified" for status in step_statuses):
                add_finding(findings, "error", "verified_with_unverified_steps", reasoning_id, path,
                            "reasoning is verified but not every step is verified", "Verify every premise and transformation before verifying the conclusion.")
            if not conclusion.get("evidence_refs"):
                add_finding(findings, "error", "verified_conclusion_without_evidence", reasoning_id, path,
                            "verified conclusion has no evidence", "Attach direct evidence to the conclusion.")

    error_count = sum(item["severity"] == "error" for item in findings)
    warning_count = sum(item["severity"] == "warning" for item in findings)
    status = "fail" if error_count else "warning" if warning_count else "pass"
    checks = [
        {"check_id": "CHK-1", "name": "formula schema and derivation references", "status": "fail" if any(f["category"] in {"formula_schema", "duplicate_symbol", "unknown_formula_symbol", "unknown_assumption", "verified_formula_with_unverified_assumptions", "no_formula_records"} for f in findings) else "pass", "evidence": [f"checked {len(formulas)} formula records"]},
        {"check_id": "CHK-2", "name": "formula-to-code variable correspondence", "status": "fail" if any(f["category"] in {"mapping_schema", "missing_formula", "formula_version_mismatch", "unknown_mapping_symbol", "semantic_mismatch", "identifier_semantic_collision", "name_unit_conflict", "missing_unit_conversion", "untested_unit_conversion", "required_symbol_unmapped", "opaque_identifier", "verified_mapping_with_unverified_entries", "verified_mapping_without_tests", "no_mapping_records"} for f in findings) else "warning" if any(f["category"] == "stale_line_range" for f in findings) else "pass", "evidence": [f"checked {len(mappings)} mapping records"]},
        {"check_id": "CHK-3", "name": "source identifier existence", "status": "fail" if any(f["category"] in {"source_path_escape", "missing_source_file", "identifier_not_found", "invalid_line_range"} for f in findings) else "warning" if any(f["category"] == "stale_line_range" for f in findings) else "pass", "evidence": ["workspace source scan enabled" if workspace else "workspace source scan not requested"]},
        {"check_id": "CHK-4", "name": "reasoning chain completeness and proof status", "status": "fail" if any(f["category"].startswith("reasoning_") or f["category"].startswith("missing_reasoning") or f["category"] in {"missing_goal", "missing_goal_criterion", "missing_goal_milestone", "verified_step_without_evidence", "missing_counterexample_check", "verified_with_unresolved", "verified_with_unverified_steps", "verified_conclusion_without_evidence", "verified_with_unverified_premises", "no_reasoning_records"} for f in findings) else "pass", "evidence": [f"checked {len(reasoning)} reasoning chains"]},
    ]
    return {
        "schema_version": 1,
        "audit_id": audit_id,
        "created_at": now(),
        "target": {
            "knowledge_dir": str(knowledge),
            "workspace": str(workspace) if workspace else None,
            "commit": git_commit(workspace),
        },
        "scope": {
            "formula_ids": sorted(formulas),
            "mapping_ids": sorted(mappings),
            "reasoning_ids": sorted(reasoning),
        },
        "checks": checks,
        "findings": findings,
        "summary": {
            "status": status,
            "errors": error_count,
            "warnings": warning_count,
            "checked_formulas": len(formulas),
            "checked_mappings": len(mappings),
            "checked_reasoning_chains": len(reasoning),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--audit-id", default="AUD-0001")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    args = parser.parse_args()
    if not re.fullmatch(r"AUD-[0-9]{4,}", args.audit_id):
        raise SystemExit("audit-id must match AUD-0001")
    knowledge = args.knowledge.resolve()
    workspace = args.workspace.resolve() if args.workspace else None
    report = audit(knowledge, workspace, args.audit_id, allow_empty=args.allow_empty)
    schema_errors = validate_schema(report, SCHEMA_DIR / "logic_audit.schema.yaml", Path(f"{args.audit_id}.yaml"))
    if schema_errors:
        raise SystemExit("\n".join(schema_errors))
    if args.write_report:
        folder = knowledge / "audits"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{args.audit_id}.yaml"
        with file_lock(folder / ".logic-audit.lock"):
            if target.exists():
                raise SystemExit(f"refusing to overwrite {target}")
            atomic_write_yaml(target, report)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), end="")
    if report["summary"]["errors"]:
        return 1
    if args.strict_warnings and report["summary"]["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

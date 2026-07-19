#!/usr/bin/env python3
"""Safely register a reasoning, formula, mapping, or audit YAML record."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import yaml

from schema_utils import validate_knowledge, validate_schema

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "references" / "schemas"
RECORD_TYPES = {
    "formula_id": ("formulas", "formula.schema.yaml"),
    "mapping_id": ("variable_mappings", "variable_mapping.schema.yaml"),
    "reasoning_id": ("reasoning_chains", "reasoning_chain.schema.yaml"),
    "audit_id": ("audits", "logic_audit.schema.yaml"),
}
PROTECTED = {"verified", "deprecated"}


def load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("source record must be a YAML mapping")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--replace-draft", action="store_true")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    knowledge = args.knowledge.resolve()
    source = args.source.resolve()
    record = load(source)
    id_field = next((field for field in ("mapping_id", "reasoning_id", "audit_id", "formula_id") if isinstance(record.get(field), str)), None)
    if id_field is None:
        raise SystemExit("record must contain formula_id, mapping_id, reasoning_id, or audit_id")
    directory, schema_name = RECORD_TYPES[id_field]
    record_id = record[id_field]
    schema_errors = validate_schema(record, SCHEMA_DIR / schema_name, source)
    if schema_errors:
        raise SystemExit("\n".join(schema_errors))
    target_dir = knowledge / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{record_id}.yaml"
    if target.exists():
        existing = load(target)
        if not args.replace_draft:
            raise SystemExit(f"refusing to overwrite {target}; use --replace-draft only for non-verified records")
        if existing.get("status") in PROTECTED:
            raise SystemExit(f"refusing to replace protected {existing.get('status')} record {record_id}")
    staging_root = Path(tempfile.mkdtemp(prefix=".reasoning-register-", dir=knowledge.parent))
    staged_knowledge = staging_root / knowledge.name
    try:
        shutil.copytree(knowledge, staged_knowledge)
        staged_target = staged_knowledge / directory / target.name
        staged_target.parent.mkdir(parents=True, exist_ok=True)
        staged_target.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
        errors = validate_knowledge(staged_knowledge, SCHEMA_DIR)
        if errors:
            raise SystemExit("\n".join(errors))
        temp_target = target.with_suffix(".yaml.tmp")
        temp_target.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
        os.replace(temp_target, target)
        changelog = knowledge / "CHANGELOG.md"
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with changelog.open("a", encoding="utf-8") as stream:
            stream.write(f"\n## {timestamp} - registered {record_id}\n- reason: {args.reason}\n- path: {directory}/{target.name}\n")
        print(target)
        return 0
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

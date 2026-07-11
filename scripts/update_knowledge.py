#!/usr/bin/env python3
"""Safely update YAML knowledge and append an auditable changelog."""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml

from schema_utils import validate_knowledge

ALLOWED = {"candidate", "measured", "verified", "deprecated"}


def get_nested(data: dict[str, Any], keys: list[str]) -> tuple[bool, Any]:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


def set_nested(data: dict[str, Any], keys: list[str], value: Any) -> None:
    current = data
    for key in keys[:-1]:
        if not isinstance(current.get(key), dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge_dir", type=Path)
    parser.add_argument("relative_yaml")
    parser.add_argument("key")
    parser.add_argument("value")
    parser.add_argument("--status", choices=sorted(ALLOWED), required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--bag-id", default="none")
    parser.add_argument("--allow-replace-verified", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    knowledge = args.knowledge_dir.resolve()
    target = (knowledge / args.relative_yaml).resolve()
    if knowledge != target and knowledge not in target.parents:
        raise SystemExit("target must stay inside knowledge_dir")
    if target.suffix not in {".yaml", ".yml"}:
        raise SystemExit("target must be yaml")

    data: dict[str, Any] = {}
    old_text = None
    if target.exists():
        old_text = target.read_text(encoding="utf-8")
        loaded = yaml.safe_load(old_text)
        if loaded is not None and not isinstance(loaded, dict):
            raise SystemExit("top-level YAML must be a mapping")
        data = loaded or {}

    old_document = copy.deepcopy(data)
    old_status = data.get("status")
    if old_status == "verified" and not args.allow_replace_verified:
        raise SystemExit("refusing to modify verified record without --allow-replace-verified")
    if old_status == "verified" and args.status not in {"verified", "deprecated"}:
        raise SystemExit("verified record may only remain verified or become deprecated")

    keys = [part for part in args.key.split(".") if part]
    if not keys:
        raise SystemExit("key must not be empty")
    existed, old_value = get_nested(data, keys)
    new_value = yaml.safe_load(args.value)
    set_nested(data, keys, new_value)
    data["status"] = args.status

    summary = {
        "file": args.relative_yaml,
        "field": args.key,
        "old_value": old_value if existed else "<missing>",
        "new_value": new_value,
        "old_status": old_status,
        "new_status": args.status,
        "reason": args.reason,
        "evidence": args.evidence,
        "code_commit": args.code_commit,
        "bag_id": args.bag_id,
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 0

    atomic_write(target, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    schema_dir = Path(__file__).resolve().parents[1] / "references" / "schemas"
    errors = validate_knowledge(knowledge, schema_dir)
    if errors:
        if old_text is None:
            target.unlink(missing_ok=True)
        else:
            atomic_write(target, old_text)
        print("update rolled back because validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    entry = (
        f"\n## {stamp} - knowledge update\n\n"
        f"- file: `{args.relative_yaml}`\n"
        f"- field: `{args.key}`\n"
        f"- old value: `{old_value if existed else '<missing>'}`\n"
        f"- new value: `{new_value}`\n"
        f"- status: `{old_status}` -> `{args.status}`\n"
        f"- reason: {args.reason}\n"
        f"- evidence: {args.evidence}\n"
        f"- code commit: `{args.code_commit}`\n"
        f"- bag: `{args.bag_id}`\n"
    )
    with (knowledge / "CHANGELOG.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

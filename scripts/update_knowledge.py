#!/usr/bin/env python3
"""Update YAML knowledge with locking, recovery journal, validation, and rollback."""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import yaml

from schema_utils import validate_knowledge

ALLOWED = {"candidate", "measured", "verified", "deprecated"}
JOURNAL_NAME = ".knowledge-transaction.json"
LOCK_NAME = ".knowledge.lock"


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
        existing = current.get(key)
        if existing is None:
            current[key] = {}
        elif not isinstance(existing, dict):
            raise ValueError(f"cannot descend through non-mapping key {key!r}")
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


def encode_text(value: str | None) -> str | None:
    return None if value is None else base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_text(value: str | None) -> str | None:
    return None if value is None else base64.b64decode(value.encode("ascii")).decode("utf-8")


def restore_file(path: Path, existed: bool, content: str | None) -> None:
    if existed:
        atomic_write(path, content or "")
    else:
        path.unlink(missing_ok=True)


def recover_if_needed(knowledge: Path) -> bool:
    journal_path = knowledge / JOURNAL_NAME
    if not journal_path.exists():
        return False
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    target = (knowledge / payload["target_relative"]).resolve()
    if knowledge != target and knowledge not in target.parents:
        raise RuntimeError("transaction journal target escapes knowledge directory")
    changelog = knowledge / "CHANGELOG.md"
    restore_file(target, payload["target_existed"], decode_text(payload.get("target_old")))
    restore_file(changelog, payload["changelog_existed"], decode_text(payload.get("changelog_old")))
    journal_path.unlink(missing_ok=True)
    return True


def one_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str).replace("\n", "\\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge_dir", type=Path)
    parser.add_argument("relative_yaml")
    parser.add_argument("key", help="dot-separated mapping keys")
    parser.add_argument("value", help="YAML scalar or structure")
    parser.add_argument("--status", choices=sorted(ALLOWED), required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--bag-id", default="none")
    parser.add_argument("--allow-replace-verified", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    knowledge = args.knowledge_dir.resolve()
    if not knowledge.is_dir():
        raise SystemExit(f"knowledge directory not found: {knowledge}")
    target = (knowledge / args.relative_yaml).resolve()
    if knowledge != target and knowledge not in target.parents:
        raise SystemExit("target must stay inside knowledge_dir")
    if target.suffix not in {".yaml", ".yml"}:
        raise SystemExit("target must be yaml")
    if target.is_symlink():
        raise SystemExit("refusing to update a symlink")

    keys = [part for part in args.key.split(".") if part]
    if not keys:
        raise SystemExit("key must not be empty")

    lock_path = knowledge / LOCK_NAME
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        recovered = recover_if_needed(knowledge)
        if recovered:
            print("recovered unfinished knowledge transaction", file=os.sys.stderr)

        old_text = target.read_text(encoding="utf-8") if target.exists() else None
        loaded = yaml.safe_load(old_text) if old_text is not None else {}
        if loaded is not None and not isinstance(loaded, dict):
            raise SystemExit("top-level YAML must be a mapping")
        data: dict[str, Any] = copy.deepcopy(loaded or {})
        old_status = data.get("status")
        if old_status == "verified" and not args.allow_replace_verified:
            raise SystemExit("refusing to modify verified record without --allow-replace-verified")
        if old_status == "verified" and args.status not in {"verified", "deprecated"}:
            raise SystemExit("verified record may only remain verified or become deprecated")

        existed, old_value = get_nested(data, keys)
        new_value = yaml.safe_load(args.value)
        try:
            set_nested(data, keys, new_value)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
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

        changelog = knowledge / "CHANGELOG.md"
        changelog_old = changelog.read_text(encoding="utf-8") if changelog.exists() else None
        journal = {
            "target_relative": target.relative_to(knowledge).as_posix(),
            "target_existed": old_text is not None,
            "target_old": encode_text(old_text),
            "changelog_existed": changelog_old is not None,
            "changelog_old": encode_text(changelog_old),
        }
        journal_path = knowledge / JOURNAL_NAME
        atomic_write(journal_path, json.dumps(journal, ensure_ascii=False, indent=2))

        try:
            atomic_write(target, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
            schema_dir = Path(__file__).resolve().parents[1] / "references" / "schemas"
            errors = validate_knowledge(knowledge, schema_dir, allow_transaction=True)
            if errors:
                raise ValueError("\n".join(errors))

            stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            entry = (
                f"\n## {stamp} - knowledge update\n\n"
                f"- file: `{args.relative_yaml}`\n"
                f"- field: `{args.key}`\n"
                f"- old value: `{one_line(old_value if existed else '<missing>')}`\n"
                f"- new value: `{one_line(new_value)}`\n"
                f"- status: `{old_status}` -> `{args.status}`\n"
                f"- reason: {one_line(args.reason)}\n"
                f"- evidence: {one_line(args.evidence)}\n"
                f"- code commit: `{one_line(args.code_commit)}`\n"
                f"- bag: `{one_line(args.bag_id)}`\n"
            )
            atomic_write(changelog, (changelog_old or "") + entry)
            journal_path.unlink(missing_ok=True)
        except Exception as exc:
            restore_file(target, old_text is not None, old_text)
            restore_file(changelog, changelog_old is not None, changelog_old)
            journal_path.unlink(missing_ok=True)
            print("update rolled back:")
            print(str(exc))
            return 1

        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

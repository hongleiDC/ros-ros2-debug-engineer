#!/usr/bin/env python3
"""Apply a YAML update and append an auditable changelog entry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

ALLOWED = {"candidate", "measured", "verified", "deprecated"}


def set_nested(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    keys = dotted_key.split(".")
    cur = data
    for key in keys[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[keys[-1]] = value


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("project_dir", type=Path)
    p.add_argument("relative_yaml")
    p.add_argument("key", help="dotted key path")
    p.add_argument("value", help="YAML scalar/list/mapping")
    p.add_argument("--status", choices=sorted(ALLOWED), required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", default="not provided")
    args = p.parse_args()

    target = (args.project_dir / args.relative_yaml).resolve()
    project = args.project_dir.resolve()
    if project not in target.parents:
        raise SystemExit("target must stay inside project_dir")
    if target.suffix not in {".yaml", ".yml"}:
        raise SystemExit("target must be yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if target.exists():
        loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
        if loaded is not None and not isinstance(loaded, dict):
            raise SystemExit("top-level YAML must be a mapping")
        data = loaded or {}
    old = data
    parsed = yaml.safe_load(args.value)
    set_nested(data, args.key, parsed)
    data["status"] = args.status
    target.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    log = args.project_dir / "CHANGELOG.md"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {stamp} — knowledge update\n\n")
        fh.write(f"- file: `{args.relative_yaml}`\n")
        fh.write(f"- field: `{args.key}`\n")
        fh.write(f"- status: `{args.status}`\n")
        fh.write(f"- reason: {args.reason}\n")
        fh.write(f"- evidence: {args.evidence}\n")
    print(f"updated {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

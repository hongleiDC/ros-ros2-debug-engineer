#!/usr/bin/env python3
"""Plan and record incremental ROS 1 Noetic evidence updates using hashes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

DOMAINS = ("launch", "runtime", "hardware", "tf_time", "bag", "topic_probe")
AFFECTED = {"launch": ["drivers", "ros_graph", "hardware"], "runtime": ["ros_graph", "topics"], "hardware": ["hardware", "machine"], "tf_time": ["coordinates", "time"], "bag": ["topics", "data"], "topic_probe": ["topics"]}


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"path": str(path.expanduser().resolve()), "sha256": sha(path), "size_bytes": stat.st_size}


def plan_update(previous: dict[str, Any], current: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    old = previous.get("entries", {}) if isinstance(previous.get("entries"), dict) else {}
    changed, unchanged = [], []
    for domain, entries in current.items():
        old_sha = sorted(x.get("sha256") for x in old.get(domain, []))
        new_sha = sorted(x.get("sha256") for x in entries)
        (unchanged if old_sha == new_sha and old_sha else changed).append(domain)
    affected = []
    for domain in changed:
        for item in AFFECTED[domain]:
            if item not in affected:
                affected.append(item)
    return {"schema_version": 1, "changed_domains": changed, "unchanged_domains": unchanged, "affected_profile_domains": affected, "rule": "Refresh changed domains only."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "update"])
    parser.add_argument("--cache", type=Path, default=Path(".ros_noetic_cache"))
    for name in DOMAINS:
        parser.add_argument("--" + name.replace("_", "-"), action="append", default=[], dest=name, type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    current = {domain: [fingerprint(p) for p in getattr(args, domain)] for domain in DOMAINS if getattr(args, domain)}
    previous = load(args.cache / "manifest.yaml")
    result = plan_update(previous, current)
    if args.command == "update":
        args.cache.mkdir(parents=True, exist_ok=True)
        manifest = {"schema_version": 1, "cache_kind": "ros_noetic_incremental_evidence_cache", "target": {"ros_version": "1", "ros_distro": "noetic"}, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "entries": current}
        (args.cache / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        if args.profile:
            (args.cache / "latest_profile.yaml").write_text(args.profile.read_text(encoding="utf-8"), encoding="utf-8")
        result["cache_updated"] = True
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

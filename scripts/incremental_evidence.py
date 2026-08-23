#!/usr/bin/env python3
"""Plan and record incremental ROS 1 Noetic evidence updates using content hashes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, List

import yaml

DOMAINS = ("launch", "runtime", "hardware", "tf_time", "bag", "topic_probe")
AFFECTED = {
    "launch": ["drivers", "ros_graph", "hardware"],
    "runtime": ["ros_graph", "topics"],
    "hardware": ["hardware", "machine"],
    "tf_time": ["coordinates", "time"],
    "bag": ["topics", "data"],
    "topic_probe": ["topics"],
}


def load(path: Path) -> Dict[str, object]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path: Path) -> Dict[str, object]:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    return {"path": str(resolved), "sha256": sha(resolved), "size_bytes": stat.st_size}


def _old_entries(previous: Dict[str, object]) -> Dict[str, List[Dict[str, object]]]:
    raw = previous.get("entries")
    return raw if isinstance(raw, dict) else {}


def plan_update(previous: Dict[str, object], current: Dict[str, List[Dict[str, object]]]) -> Dict[str, object]:
    old = _old_entries(previous)
    changed = []
    unchanged = []
    for domain in DOMAINS:
        if domain not in current:
            continue
        old_sha = sorted(str(item.get("sha256")) for item in old.get(domain, []) if isinstance(item, dict))
        new_sha = sorted(str(item.get("sha256")) for item in current[domain])
        if old_sha and old_sha == new_sha:
            unchanged.append(domain)
        else:
            changed.append(domain)
    preserved = [domain for domain in DOMAINS if domain in old and domain not in current]
    affected = []
    for domain in changed:
        for item in AFFECTED[domain]:
            if item not in affected:
                affected.append(item)
    return {
        "schema_version": 2,
        "changed_domains": changed,
        "unchanged_domains": unchanged,
        "preserved_cached_domains": preserved,
        "affected_profile_domains": affected,
        "requires_full_rescan": not bool(old),
        "rule": "Refresh changed domains only; preserve cached domains that were not supplied.",
    }


def merge_entries(previous: Dict[str, object], current: Dict[str, List[Dict[str, object]]]) -> Dict[str, List[Dict[str, object]]]:
    merged = {}
    old = _old_entries(previous)
    for domain in DOMAINS:
        if domain in current:
            merged[domain] = current[domain]
        elif domain in old:
            merged[domain] = old[domain]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "update"])
    parser.add_argument("--cache", type=Path, default=Path(".ros_noetic_cache"))
    for name in DOMAINS:
        parser.add_argument("--" + name.replace("_", "-"), action="append", default=[], dest=name, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--summary", type=Path, help="compact session summary to cache after validation")
    args = parser.parse_args()

    try:
        current = {
            domain: [fingerprint(path) for path in getattr(args, domain)]
            for domain in DOMAINS
            if getattr(args, domain)
        }
    except OSError as exc:
        raise SystemExit("cannot fingerprint evidence: %s" % exc)

    previous = load(args.cache / "manifest.yaml")
    result = plan_update(previous, current)
    if args.command == "update":
        args.cache.mkdir(parents=True, exist_ok=True)
        entries = merge_entries(previous, current)
        manifest = {
            "schema_version": 2,
            "cache_kind": "ros_noetic_incremental_evidence_cache",
            "target": {"ros_version": "1", "ros_distro": "noetic"},
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "entries": entries,
        }
        (args.cache / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        if args.profile:
            (args.cache / "latest_profile.yaml").write_text(args.profile.read_text(encoding="utf-8"), encoding="utf-8")
        if args.summary:
            (args.cache / "session_summary.yaml").write_text(args.summary.read_text(encoding="utf-8"), encoding="utf-8")
        result["cache_updated"] = True
        result["cached_domains"] = [domain for domain in DOMAINS if domain in entries]
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compare two ROS Noetic system profiles."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def compare(before: dict, after: dict) -> dict:
    changes = []
    if before.get("hardware", {}).get("observed_endpoints") != after.get("hardware", {}).get("observed_endpoints"):
        changes.append({"domain": "hardware", "kind": "endpoint"})
    old = {x.get("name"): x for x in before.get("topics", [])}
    new = {x.get("name"): x for x in after.get("topics", [])}
    for name in sorted(set(old) | set(new)):
        if old.get(name, {}).get("live_type") != new.get(name, {}).get("live_type"):
            changes.append({"domain": "topics", "topic": name, "kind": "message_contract"})
    return {
        "schema_version": 1,
        "diff_kind": "ros_noetic_system_profile_diff",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "status": "changed" if changes else "unchanged",
        "changes": changes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(yaml.safe_dump(compare(load(args.before), load(args.after)), sort_keys=False), encoding="utf-8")

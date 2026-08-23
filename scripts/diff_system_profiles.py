#!/usr/bin/env python3
"""Compare two ROS Noetic system profiles and plan a targeted evidence refresh."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List

import yaml

DOMAIN_ORDER = ("hardware", "drivers", "ros_graph", "topics", "coordinates", "time", "data")


def load(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("expected mapping: %s" % path)
    return data


def _hardware_view(profile: Dict[str, object]) -> object:
    hardware = profile.get("hardware")
    if not isinstance(hardware, dict):
        return hardware
    observed = hardware.get("observed_device_paths")
    if observed is None:
        observed = hardware.get("observed_endpoints")
    return {
        "expected_device_paths": hardware.get("expected_device_paths"),
        "observed_device_paths": observed,
        "candidates": hardware.get("candidates"),
    }


def _topic_map(profile: Dict[str, object]) -> Dict[str, object]:
    result = {}
    topics = profile.get("topics")
    if not isinstance(topics, list):
        return result
    for item in topics:
        if isinstance(item, dict) and item.get("name"):
            result[str(item["name"])] = item
    return result


def _domain_value(profile: Dict[str, object], domain: str) -> object:
    if domain == "hardware":
        return _hardware_view(profile)
    if domain == "topics":
        return _topic_map(profile)
    return profile.get(domain)


def _refresh_plan(changed_domains: List[str], affected_topics: List[str]) -> List[Dict[str, object]]:
    plan = []
    actions = set()

    def add(action: str, tool: str, domains: List[str], reason: str, topics: List[str] = None) -> None:
        if action in actions:
            return
        item = {"action": action, "tool": tool, "domains": domains, "reason": reason}
        if topics:
            item["topics"] = topics
        plan.append(item)
        actions.add(action)

    if "hardware" in changed_domains:
        add("inspect_system_hardware", "scripts/inspect_system_hardware.py", ["hardware"], "Observed or expected hardware endpoints changed.")
    if "drivers" in changed_domains:
        add("inspect_launch", "scripts/inspect_launch.py", ["drivers"], "Driver declarations changed.")
    if "ros_graph" in changed_domains:
        add("collect_runtime_snapshot", "scripts/collect_runtime_snapshot.py", ["ros_graph"], "Live graph expectations or observations changed.")
    if "topics" in changed_domains:
        add("probe_topic", "scripts/probe_topic.py", ["topics"], "Topic presence or message contract changed.", affected_topics)
    if "coordinates" in changed_domains or "time" in changed_domains:
        domains = [name for name in ("coordinates", "time") if name in changed_domains]
        add("inspect_tf_time", "scripts/inspect_tf_time.py", domains, "Frame or time semantics changed.")
    if "data" in changed_domains:
        add("inspect_rosbag", "scripts/inspect_rosbag.py", ["data"], "Recorded-data contract changed.")
    return plan


def compare(before: Dict[str, object], after: Dict[str, object]) -> Dict[str, object]:
    changes = []
    changed_domains = []
    unchanged_domains = []
    affected_topics = []

    for domain in DOMAIN_ORDER:
        old_value = _domain_value(before, domain)
        new_value = _domain_value(after, domain)
        if old_value == new_value:
            unchanged_domains.append(domain)
            continue
        changed_domains.append(domain)
        if domain == "topics":
            old_topics = _topic_map(before)
            new_topics = _topic_map(after)
            for name in sorted(set(old_topics) | set(new_topics)):
                if old_topics.get(name) != new_topics.get(name):
                    affected_topics.append(name)
                    changes.append({"domain": "topics", "topic": name, "kind": "topic_contract", "before": old_topics.get(name), "after": new_topics.get(name)})
        else:
            changes.append({"domain": domain, "kind": "domain_change", "before": old_value, "after": new_value})

    return {
        "schema_version": 2,
        "diff_kind": "ros_noetic_system_profile_diff",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "status": "changed" if changed_domains else "unchanged",
        "changed_domains": changed_domains,
        "unchanged_domains": unchanged_domains,
        "affected_topics": affected_topics,
        "change_count": len(changes),
        "changes": changes,
        "refresh_plan": _refresh_plan(changed_domains, affected_topics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(load(args.before), load(args.after))
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SystemExit("cannot compare profiles: %s" % exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a conservative ROS 1 Noetic system profile from merged evidence."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def classify_topic(name: str, msg_type: str = "") -> str:
    text = (name + " " + msg_type).lower()
    if "pointcloud" in text or "lidar" in text or "points_raw" in text:
        return "lidar"
    if "imu" in text:
        return "imu"
    if "gnss" in text or "gps" in text or "rtk" in text or "navsat" in text:
        return "gnss"
    if "image" in text or "camera" in text:
        return "camera"
    if "odom" in text:
        return "odometry"
    if "joint" in text:
        return "joint_state"
    if "cmd" in text or "control" in text:
        return "control"
    return "other"


def build_profile(merged: dict[str, Any]) -> dict[str, Any]:
    target = merged.get("target", {})
    if target.get("ros_version") != "1" or target.get("ros_distro") != "noetic":
        raise ValueError("only ROS 1 Noetic evidence is supported")
    topics = []
    for item in merged.get("topics", []):
        if isinstance(item, dict):
            live = item.get("live", {}) if isinstance(item.get("live"), dict) else {}
            topics.append({
                "name": item.get("name"),
                "status": item.get("status"),
                "role": classify_topic(str(item.get("name", "")), str(live.get("type", ""))),
                "live_type": live.get("type"),
                "recorded_types": sorted({str(x.get("type")) for x in item.get("recorded", []) if isinstance(x, dict) and x.get("type")}),
                "conflicts": item.get("conflicts", []),
            })
    return {
        "schema_version": 1,
        "profile_kind": "ros_noetic_system_profile",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "status": merged.get("status", "partial"),
        "completeness": {
            "available_evidence": sorted({x.get("kind") for x in merged.get("sources", []) if isinstance(x, dict)}),
        },
        "machine": {},
        "hardware": merged.get("hardware", {}),
        "drivers": merged.get("nodes_expected", []),
        "ros_graph": {
            "expected_nodes": merged.get("nodes_expected", []),
            "observed_live_nodes": merged.get("nodes_observed_live", []),
        },
        "topics": topics,
        "coordinates": {"frames_seen": []},
        "time": merged.get("time", {}),
        "data": {"topic_roles": sorted({x["role"] for x in topics})},
        "risk": {
            "conflicts": merged.get("conflicts", []),
            "differences": merged.get("differences", []),
            "unknowns": merged.get("unknowns", []),
        },
        "provenance": merged.get("sources", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merged", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    profile = build_profile(load_mapping(args.merged))
    args.output.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

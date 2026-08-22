#!/usr/bin/env python3
"""Inspect a ROS 1 Noetic rosbag1 file without replaying it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml


def run(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    except FileNotFoundError as exc:
        raise SystemExit(f"required command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"command timed out: {' '.join(command)}") from exc


def parse_rosbag_info_yaml(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("rosbag info YAML must contain a mapping")
    topics = data.get("topics")
    if topics is None:
        data["topics"] = []
    elif not isinstance(topics, list):
        raise ValueError("rosbag info YAML topics must be a list")
    return data


def topic_index(info: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in info.get("topics", []):
        if not isinstance(item, dict):
            continue
        result.append({
            "topic": item.get("topic"),
            "type": item.get("type"),
            "messages": item.get("messages"),
            "frequency": item.get("frequency"),
        })
    return result


def select_topics(index: list[dict[str, Any]], requested: list[str], limit: int) -> list[str]:
    known = [str(item["topic"]) for item in index if item.get("topic")]
    if requested:
        missing = [topic for topic in requested if topic not in known]
        if missing:
            raise SystemExit("topics not present in bag: " + ", ".join(missing))
        return requested[:limit]
    priority_fragments = (
        "/imu", "/points", "/velodyne", "/livox", "/ouster", "/fix", "/gps", "/gnss",
        "/odom", "/tf", "/clock", "/camera", "/image", "/diagnostics",
    )
    prioritized = [topic for topic in known if any(fragment in topic.lower() for fragment in priority_fragments)]
    others = [topic for topic in known if topic not in prioritized]
    return (prioritized + others)[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--topic", action="append", default=[], help="Inspect one topic sample; repeat as needed.")
    parser.add_argument("--sample-limit", type=int, default=8, help="Maximum topics sampled with rostopic echo -b -n 1.")
    parser.add_argument("--metadata-only", action="store_true", help="Do not sample messages.")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    bag = args.bag.expanduser().resolve()
    if not bag.is_file():
        raise SystemExit(f"bag not found: {bag}")
    if bag.suffix.lower() != ".bag":
        raise SystemExit("this tool only accepts ROS 1 rosbag1 .bag files")
    if args.sample_limit < 0 or args.sample_limit > 50:
        raise SystemExit("--sample-limit must be between 0 and 50")

    metadata = run(["rosbag", "info", "-y", str(bag)], args.timeout)
    if metadata.returncode != 0:
        raise SystemExit(metadata.stderr.strip() or "rosbag info failed")
    try:
        info = parse_rosbag_info_yaml(metadata.stdout)
    except (yaml.YAMLError, ValueError) as exc:
        raise SystemExit(f"cannot parse rosbag info YAML: {exc}") from exc

    index = topic_index(info)
    selected = [] if args.metadata_only else select_topics(index, args.topic, args.sample_limit)
    samples: list[dict[str, Any]] = []
    for topic in selected:
        result = run(["rostopic", "echo", "-b", str(bag), "-n", "1", topic], args.timeout)
        samples.append({
            "topic": topic,
            "returncode": result.returncode,
            "stdout": result.stdout[:50_000],
            "stderr": result.stderr[:10_000],
        })

    payload = {
        "schema_version": 1,
        "target": {"ros_version": "1", "ros_distro": "noetic", "bag_format": "rosbag1"},
        "bag": str(bag),
        "metadata": {
            "path": info.get("path", str(bag)),
            "version": info.get("version"),
            "duration": info.get("duration"),
            "start": info.get("start"),
            "end": info.get("end"),
            "size": info.get("size"),
            "messages": info.get("messages"),
            "compression": info.get("compression"),
            "types": info.get("types", []),
        },
        "topics": index,
        "samples": samples,
        "analysis_hints": [
            "Compare expected sensor topics against the bag inventory before replay.",
            "For header-bearing messages inspect stamp and frame_id; do not infer time quality from bag metadata alone.",
            "For PointCloud2 inspect fields before assuming ring/time field names.",
            "Check /tf, /tf_static and /clock presence separately because they change replay semantics.",
            "A topic present in the bag does not prove its data are physically valid or correctly calibrated.",
        ],
    }

    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

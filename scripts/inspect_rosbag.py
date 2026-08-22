#!/usr/bin/env python3
"""Inspect ROS 1 Noetic rosbag1 metadata and bounded per-topic samples."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml

MAX_METADATA_BYTES = 5_000_000


def run_command(command: list[str], timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:MAX_METADATA_BYTES],
            "stderr": result.stderr[:100_000],
            "truncated": len(result.stdout) > MAX_METADATA_BYTES,
        }
    except FileNotFoundError:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "command not found", "truncated": False}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {"command": command, "returncode": None, "stdout": stdout[:MAX_METADATA_BYTES], "stderr": (stderr + "\ncommand timed out").strip()[:100_000], "truncated": len(stdout) > MAX_METADATA_BYTES}


def noetic_environment(timeout: float) -> dict[str, Any]:
    probe = run_command(["rosversion", "-d"], timeout)
    probe_distro = probe["stdout"].strip() if probe["returncode"] == 0 else None
    version = os.environ.get("ROS_VERSION")
    distro = os.environ.get("ROS_DISTRO")
    return {
        "match": version == "1" and distro == "noetic" and probe_distro == "noetic",
        "ROS_VERSION": version,
        "ROS_DISTRO": distro,
        "rosversion_d": probe_distro,
        "probe": probe,
    }


def classify_topic(topic: str, msg_type: str) -> str:
    name = topic.lower()
    if topic == "/tf_static":
        return "tf_static"
    if topic == "/tf" or msg_type in {"tf/tfMessage", "tf2_msgs/TFMessage"}:
        return "tf"
    if topic == "/clock" or msg_type == "rosgraph_msgs/Clock":
        return "clock"
    if msg_type in {"sensor_msgs/PointCloud2", "sensor_msgs/LaserScan"} or any(token in name for token in ("lidar", "velodyne", "ouster", "points_raw", "pointcloud")):
        return "lidar"
    if msg_type == "sensor_msgs/Imu" or "imu" in name:
        return "imu"
    if msg_type == "sensor_msgs/NavSatFix" or any(token in name for token in ("gnss", "gps", "rtk", "navsat", "nmea")):
        return "gnss"
    if msg_type in {"sensor_msgs/Image", "sensor_msgs/CompressedImage", "sensor_msgs/CameraInfo"} or any(token in name for token in ("camera", "image_raw", "camera_info")):
        return "camera"
    if msg_type in {"nav_msgs/Odometry", "nav_msgs/Path"} or any(token in name for token in ("odom", "odometry")):
        return "odometry"
    if msg_type == "sensor_msgs/JointState" or "joint_states" in name:
        return "joint_state"
    if msg_type == "diagnostic_msgs/DiagnosticArray" or "diagnostic" in name:
        return "diagnostics"
    if any(token in name for token in ("cmd_vel", "command", "actuator", "trajectory", "controller", "motor")):
        return "control"
    return "other"


def number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_info(info: dict[str, Any]) -> dict[str, Any]:
    duration = number(info.get("duration"))
    md5_by_type = {
        str(item.get("type")): item.get("md5")
        for item in info.get("types", [])
        if isinstance(item, dict) and item.get("type")
    }
    topics: list[dict[str, Any]] = []
    for raw in info.get("topics", []) or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("topic", ""))
        msg_type = str(raw.get("type", ""))
        messages = int(raw.get("messages") or 0)
        frequency = number(raw.get("frequency"))
        topics.append({
            "topic": name,
            "type": msg_type,
            "md5": md5_by_type.get(msg_type),
            "messages": messages,
            "connections": int(raw.get("connections") or 0),
            "reported_frequency_hz": frequency,
            "bag_average_hz": (messages / duration) if duration and duration > 0 else None,
            "role": classify_topic(name, msg_type),
        })
    role_counts = dict(Counter(item["role"] for item in topics))
    return {
        "path": info.get("path"),
        "version": info.get("version"),
        "duration_s": duration,
        "start_s": number(info.get("start")),
        "end_s": number(info.get("end")),
        "size_bytes": info.get("size"),
        "messages": int(info.get("messages") or 0),
        "indexed": info.get("indexed"),
        "compression": info.get("compression"),
        "topic_count": len(topics),
        "role_counts": role_counts,
        "topics": topics,
    }


def to_sec(value: Any) -> float | None:
    if value is None:
        return None
    method = getattr(value, "to_sec", None)
    if callable(method):
        try:
            return float(method())
        except Exception:
            return None
    return number(value)


def message_sample(msg: Any, bag_stamp: Any, msg_type: str, connection_header: dict[str, Any] | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "bag_time_s": to_sec(bag_stamp),
        "fields": list(getattr(msg, "__slots__", []) or []),
    }
    if connection_header:
        record["connection"] = {
            "callerid": connection_header.get("callerid"),
            "latching": connection_header.get("latching"),
            "md5sum": connection_header.get("md5sum"),
            "type": connection_header.get("type"),
        }
    header = getattr(msg, "header", None)
    if header is not None:
        header_stamp = to_sec(getattr(header, "stamp", None))
        record["header"] = {
            "seq": getattr(header, "seq", None),
            "stamp_s": header_stamp,
            "frame_id": getattr(header, "frame_id", None),
        }
        if record["bag_time_s"] is not None and header_stamp is not None:
            record["bag_minus_header_ms"] = (record["bag_time_s"] - header_stamp) * 1000.0
    if msg_type == "sensor_msgs/PointCloud2":
        record["pointcloud"] = {
            "width": getattr(msg, "width", None),
            "height": getattr(msg, "height", None),
            "point_step": getattr(msg, "point_step", None),
            "row_step": getattr(msg, "row_step", None),
            "is_dense": getattr(msg, "is_dense", None),
            "fields": [getattr(field, "name", "") for field in getattr(msg, "fields", [])],
        }
    elif msg_type in {"sensor_msgs/Image", "sensor_msgs/CompressedImage"}:
        record["image"] = {
            "width": getattr(msg, "width", None),
            "height": getattr(msg, "height", None),
            "encoding": getattr(msg, "encoding", None),
            "format": getattr(msg, "format", None),
        }
    elif msg_type == "sensor_msgs/NavSatFix":
        status = getattr(msg, "status", None)
        record["navsat"] = {
            "status": getattr(status, "status", None),
            "service": getattr(status, "service", None),
            "position_covariance_type": getattr(msg, "position_covariance_type", None),
        }
    elif msg_type == "nav_msgs/Odometry":
        record["odometry"] = {"child_frame_id": getattr(msg, "child_frame_id", None)}
    elif msg_type in {"tf/tfMessage", "tf2_msgs/TFMessage"}:
        pairs = []
        for transform in list(getattr(msg, "transforms", []) or [])[:50]:
            transform_header = getattr(transform, "header", None)
            pairs.append({
                "parent": getattr(transform_header, "frame_id", None),
                "child": getattr(transform, "child_frame_id", None),
                "stamp_s": to_sec(getattr(transform_header, "stamp", None)),
            })
        record["transforms"] = pairs
    return record


def summarize_topic_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    frame_ids: set[str] = set()
    header_stamps: list[float] = []
    deltas: list[float] = []
    zero_header_stamps = 0
    non_monotonic = 0
    previous: float | None = None
    tf_pairs: set[tuple[str, str]] = set()
    point_fields: set[str] = set()
    callerids: set[str] = set()
    latching_values: set[str] = set()
    for item in samples:
        header = item.get("header") or {}
        frame = header.get("frame_id")
        if frame:
            frame_ids.add(str(frame))
        stamp = header.get("stamp_s")
        if isinstance(stamp, (int, float)):
            header_stamps.append(float(stamp))
            if stamp == 0:
                zero_header_stamps += 1
            if previous is not None and stamp < previous:
                non_monotonic += 1
            previous = float(stamp)
        delta = item.get("bag_minus_header_ms")
        if isinstance(delta, (int, float)):
            deltas.append(float(delta))
        connection = item.get("connection") or {}
        if connection.get("callerid"):
            callerids.add(str(connection["callerid"]))
        if connection.get("latching") is not None:
            latching_values.add(str(connection["latching"]))
        for pair in item.get("transforms", []) or []:
            parent, child = pair.get("parent"), pair.get("child")
            if parent and child:
                tf_pairs.add((str(parent), str(child)))
        for field in (item.get("pointcloud") or {}).get("fields", []) or []:
            if field:
                point_fields.add(str(field))
    return {
        "sample_count": len(samples),
        "frame_ids": sorted(frame_ids),
        "header_stamp_min_s": min(header_stamps) if header_stamps else None,
        "header_stamp_max_s": max(header_stamps) if header_stamps else None,
        "zero_header_stamps": zero_header_stamps,
        "non_monotonic_header_stamps": non_monotonic,
        "bag_minus_header_ms_min": min(deltas) if deltas else None,
        "bag_minus_header_ms_max": max(deltas) if deltas else None,
        "bag_minus_header_ms_mean": sum(deltas) / len(deltas) if deltas else None,
        "tf_pairs": [{"parent": parent, "child": child} for parent, child in sorted(tf_pairs)],
        "point_fields": sorted(point_fields),
        "callerids": sorted(callerids),
        "latching_values": sorted(latching_values),
    }


def sample_bag(path: Path, topic_types: dict[str, str], targets: list[str], per_topic: int) -> dict[str, Any]:
    if per_topic <= 0 or not targets:
        return {"available": True, "sample_per_topic": per_topic, "topics": {}}
    try:
        import rosbag  # type: ignore
    except Exception as exc:
        return {"available": False, "error": f"cannot import rosbag Python API: {exc}", "topics": {}}
    collected: dict[str, list[dict[str, Any]]] = {topic: [] for topic in targets}
    try:
        with rosbag.Bag(str(path), "r") as bag:
            for item in bag.read_messages(topics=targets, return_connection_header=True):
                topic = item.topic
                msg = item.message
                stamp = item.timestamp
                connection_header = item.connection_header
                bucket = collected.get(topic)
                if bucket is None or len(bucket) >= per_topic:
                    continue
                bucket.append(message_sample(msg, stamp, topic_types.get(topic, getattr(msg, "_type", "")), connection_header))
                if all(len(collected[name]) >= per_topic for name in targets):
                    break
    except Exception as exc:
        return {"available": False, "error": f"rosbag sampling failed: {exc}", "topics": {}}
    return {
        "available": True,
        "sample_per_topic": per_topic,
        "topics": {
            topic: {"summary": summarize_topic_samples(samples), "samples": samples}
            for topic, samples in collected.items()
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--sample-per-topic", type=int, default=1)
    parser.add_argument("--max-topics", type=int, default=80)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--hash", action="store_true", help="Compute SHA-256; this reads the entire bag file.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--allow-non-noetic", action="store_true")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()

    path = args.bag.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".bag":
        raise SystemExit(f"expected an existing rosbag1 .bag file: {path}")
    if args.sample_per_topic < 0 or args.sample_per_topic > 20:
        raise SystemExit("--sample-per-topic must be between 0 and 20")
    if args.max_topics < 1 or args.max_topics > 500:
        raise SystemExit("--max-topics must be between 1 and 500")

    environment = noetic_environment(min(args.timeout, 5.0))
    if not environment["match"] and not args.allow_non_noetic:
        payload = {
            "schema_version": 1,
            "status": "environment_mismatch",
            "expected": {"ROS_VERSION": "1", "ROS_DISTRO": "noetic", "rosversion_d": "noetic"},
            "observed": {key: environment.get(key) for key in ("ROS_VERSION", "ROS_DISTRO", "rosversion_d")},
            "bag": {"path": str(path), "size_bytes": path.stat().st_size},
            "limitations": ["Noetic-specific bag inspection stopped before decoding the bag."],
        }
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, indent=2, ensure_ascii=False)
        print(text)
        return 2

    info_result = run_command(["rosbag", "info", "--yaml", str(path)], args.timeout)
    if info_result["returncode"] != 0:
        raise SystemExit(f"rosbag info failed: {info_result['stderr'] or info_result['stdout']}")
    try:
        raw_info = yaml.safe_load(info_result["stdout"])
    except yaml.YAMLError as exc:
        raise SystemExit(f"cannot parse rosbag info --yaml output: {exc}") from exc
    if not isinstance(raw_info, dict):
        raise SystemExit("rosbag info --yaml did not return a mapping")
    metadata = normalize_info(raw_info)
    topic_types = {item["topic"]: item["type"] for item in metadata["topics"]}
    known_topics = list(topic_types)
    if args.topic:
        missing = [topic for topic in args.topic if topic not in topic_types]
        targets = [topic for topic in args.topic if topic in topic_types]
    else:
        missing = []
        targets = known_topics[: args.max_topics]
    sampling = {"available": True, "sample_per_topic": 0, "topics": {}}
    if not args.metadata_only:
        sampling = sample_bag(path, topic_types, targets, args.sample_per_topic)

    payload = {
        "schema_version": 1,
        "status": "measured",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic", "bag_format": "rosbag1"},
        "environment": {key: environment.get(key) for key in ("ROS_VERSION", "ROS_DISTRO", "rosversion_d", "match")},
        "bag": {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path) if args.hash else None,
        },
        "metadata": metadata,
        "requested_topics_missing": missing,
        "sampling": sampling,
        "limitations": [
            "reported_frequency_hz comes from rosbag metadata when available; bag_average_hz is messages divided by whole-bag duration and is not a replacement for interval statistics.",
            "bounded samples are evidence about sampled messages only; use a dedicated full timing analysis before claiming complete gap or ordering statistics.",
            "large array payloads are not serialized into this report.",
        ],
    }
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

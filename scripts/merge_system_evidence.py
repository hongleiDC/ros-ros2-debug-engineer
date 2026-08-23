#!/usr/bin/env python3
"""Merge provenance-aware ROS 1 Noetic evidence into one conservative system model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

ABSOLUTE_DEV_RE = re.compile(r"/dev/[A-Za-z0-9_./:+-]+")
TYPE_RE = re.compile(r"^Type:\s*(\S+)", re.MULTILINE)


def _truthy(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return None


def _unique(values: Iterable[Any]) -> List[Any]:
    result = []
    seen = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def _command_key(command: Any) -> Tuple[str, ...]:
    if isinstance(command, list):
        return tuple(str(item) for item in command)
    if isinstance(command, str):
        return tuple(command.split())
    return ()


def _command_results(runtime: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for key in ("commands", "detail_commands"):
        for item in runtime.get(key, []) or []:
            if isinstance(item, dict):
                results.append(item)
    return results


def _successful_stdout(runtime: Dict[str, Any], prefix: Sequence[str]) -> List[str]:
    wanted = tuple(prefix)
    outputs = []
    for item in _command_results(runtime):
        command = _command_key(item.get("command"))
        if command[: len(wanted)] == wanted and item.get("returncode") == 0:
            outputs.append(str(item.get("stdout", "")))
    return outputs


def _names_from_output(output: str) -> List[str]:
    names = []
    for line in output.splitlines():
        name = line.strip().split(" ", 1)[0]
        if name.startswith("/") and name not in names:
            names.append(name)
    return names


def runtime_names(runtime: Dict[str, Any], kind: str) -> List[str]:
    command_by_kind = {
        "node": ("rosnode", "list"),
        "topic": ("rostopic", "list"),
        "service": ("rosservice", "list"),
        "param": ("rosparam", "list"),
    }
    prefix = command_by_kind[kind]
    names = []
    for output in _successful_stdout(runtime, prefix):
        names.extend(_names_from_output(output))
    return _unique(names)


def runtime_topic_types(runtime: Dict[str, Any]) -> Dict[str, str]:
    result = {}
    for item in _command_results(runtime):
        command = _command_key(item.get("command"))
        if len(command) >= 3 and command[:2] == ("rostopic", "info") and item.get("returncode") == 0:
            match = TYPE_RE.search(str(item.get("stdout", "")))
            if match:
                result[command[2]] = match.group(1)
        elif len(command) >= 3 and command[:2] == ("rostopic", "type") and item.get("returncode") == 0:
            text = str(item.get("stdout", "")).strip()
            if text:
                result[command[2]] = text.splitlines()[0]
    return result


def launch_use_sim_time(launch: Dict[str, Any]) -> Optional[bool]:
    values = []
    for param in launch.get("params", []) or []:
        if not isinstance(param, dict):
            continue
        name = str(param.get("name", ""))
        if name in {"/use_sim_time", "use_sim_time"} or name.endswith("/use_sim_time"):
            parsed = _truthy(param.get("value"))
            if parsed is not None:
                values.append(parsed)
    return values[-1] if values else None


def launch_nodes(launch: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    for node in launch.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        records.append({
            "name": node.get("name"),
            "namespace": node.get("ns"),
            "package": node.get("pkg"),
            "executable": node.get("type"),
            "machine": node.get("machine"),
            "args": node.get("args"),
            "remaps": node.get("remaps", []),
            "params": node.get("params", []),
        })
    return records


def launch_expected_device_paths(launch: Dict[str, Any]) -> List[str]:
    candidates = []
    for hint in launch.get("hardware_hints", []) or []:
        if isinstance(hint, dict):
            candidates.append(str(hint.get("value", "")))
    for node in launch.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        candidates.append(str(node.get("args", "")))
        for param in node.get("params", []) or []:
            if isinstance(param, dict):
                for key in ("name", "value", "textfile", "binfile", "command"):
                    candidates.append(str(param.get(key, "")))
    paths = []
    for text in candidates:
        for match in ABSOLUTE_DEV_RE.findall(text):
            paths.append(match.rstrip(",;)]}"))
    return _unique(paths)


def bag_topics(bag: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = bag.get("metadata")
    raw = metadata.get("topics") if isinstance(metadata, dict) else None
    if raw is None:
        raw = bag.get("topics", [])
    result = []
    for item in raw or []:
        if isinstance(item, dict) and item.get("topic"):
            result.append(dict(item))
    return result


def bag_sample_summary(bag: Dict[str, Any], topic: str) -> Dict[str, Any]:
    sampling = bag.get("sampling")
    if not isinstance(sampling, dict):
        return {}
    topics = sampling.get("topics")
    if not isinstance(topics, dict):
        return {}
    entry = topics.get(topic)
    if not isinstance(entry, dict):
        return {}
    summary = entry.get("summary")
    return dict(summary) if isinstance(summary, dict) else {}


def hardware_observed_paths(hardware: Dict[str, Any]) -> List[str]:
    paths = []
    for item in hardware.get("devices", []) or []:
        if isinstance(item, dict) and item.get("exists") and item.get("path"):
            paths.append(str(item["path"]))
    candidates = hardware.get("hardware_candidates")
    if isinstance(candidates, dict):
        for key in ("serial", "video"):
            for value in candidates.get(key, []) or []:
                paths.append(str(value))
    return _unique(paths)


def _probe_type(probe: Dict[str, Any]) -> Optional[str]:
    results = probe.get("results")
    if not isinstance(results, dict):
        return None
    value = results.get("type")
    if isinstance(value, dict) and value.get("returncode") == 0:
        text = str(value.get("stdout", "")).strip()
        if text:
            return text.splitlines()[0]
    return None


def _source_summary(kind: str, payload: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "kind": kind,
        "index": index,
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "target": payload.get("target"),
        "source_path": payload.get("_source_path"),
    }


def merge_evidence(
    launches: List[Dict[str, Any]],
    bags: List[Dict[str, Any]],
    runtimes: List[Dict[str, Any]],
    hardwares: List[Dict[str, Any]],
    tf_times: List[Dict[str, Any]],
    topic_probes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sources = []
    for kind, group in (
        ("launch", launches),
        ("bag", bags),
        ("runtime", runtimes),
        ("hardware", hardwares),
        ("tf_time", tf_times),
        ("topic_probe", topic_probes),
    ):
        sources.extend(_source_summary(kind, payload, index) for index, payload in enumerate(group))

    nodes_expected = _unique(node for launch in launches for node in launch_nodes(launch))
    nodes_observed_live = _unique(name for runtime in runtimes for name in runtime_names(runtime, "node"))
    services_observed_live = _unique(name for runtime in runtimes for name in runtime_names(runtime, "service"))
    parameters_observed_live = _unique(name for runtime in runtimes for name in runtime_names(runtime, "param"))
    live_topics = _unique(name for runtime in runtimes for name in runtime_names(runtime, "topic"))
    live_types = {}
    for runtime in runtimes:
        live_types.update(runtime_topic_types(runtime))
    for probe in topic_probes:
        topic = probe.get("topic")
        probe_type = _probe_type(probe)
        if topic and probe_type:
            live_types[str(topic)] = probe_type
        if topic and str(topic) not in live_topics:
            live_topics.append(str(topic))

    recorded_by_topic = {}
    for bag_index, bag in enumerate(bags):
        for item in bag_topics(bag):
            topic = str(item["topic"])
            entry = dict(item)
            entry["bag_index"] = bag_index
            sample_summary = bag_sample_summary(bag, topic)
            if sample_summary:
                entry["sample_summary"] = sample_summary
            recorded_by_topic.setdefault(topic, []).append(entry)

    topics = []
    conflicts = []
    for topic in sorted(set(live_topics) | set(recorded_by_topic)):
        recorded = recorded_by_topic.get(topic, [])
        recorded_types = sorted({str(item.get("type")) for item in recorded if item.get("type")})
        live_type = live_types.get(topic)
        live_present = topic in live_topics
        recorded_present = bool(recorded)
        topic_conflicts = []
        if live_type and recorded_types and any(recorded_type != live_type for recorded_type in recorded_types):
            topic_conflicts.append({
                "kind": "topic_type",
                "topic": topic,
                "observed_live": live_type,
                "recorded": recorded_types,
                "message": "Live and recorded message types differ for the same topic name.",
            })
        if len(recorded_types) > 1:
            topic_conflicts.append({
                "kind": "recorded_topic_type",
                "topic": topic,
                "recorded": recorded_types,
                "message": "Multiple bags report different message types for the same topic name.",
            })
        conflicts.extend(topic_conflicts)
        if topic_conflicts:
            status = "conflict"
        elif live_present and recorded_present:
            status = "matched_presence"
        elif live_present:
            status = "live_only"
        elif recorded_present:
            status = "recorded_only"
        else:
            status = "unknown"
        topics.append({
            "name": topic,
            "status": status,
            "live": {"present": live_present, "type": live_type},
            "recorded": recorded,
            "conflicts": topic_conflicts,
        })

    expected_sim_values = [launch_use_sim_time(launch) for launch in launches]
    expected_sim_values = [value for value in expected_sim_values if value is not None]
    observed_sim_values = []
    tf_summaries = []
    for payload in tf_times:
        summary = payload.get("summary")
        if isinstance(summary, dict):
            tf_summaries.append(summary)
            value = _truthy(summary.get("use_sim_time"))
            if value is not None:
                observed_sim_values.append(value)

    time_conflicts = []
    if expected_sim_values and observed_sim_values:
        expected_value = expected_sim_values[-1]
        if any(value != expected_value for value in observed_sim_values):
            item = {
                "kind": "use_sim_time",
                "expected": expected_value,
                "observed_live": observed_sim_values,
                "message": "Launch/static expectation and live /use_sim_time differ.",
            }
            time_conflicts.append(item)
            conflicts.append(item)
    time_model = {
        "expected_use_sim_time": expected_sim_values[-1] if expected_sim_values else None,
        "observed_live": tf_summaries,
        "conflicts": time_conflicts,
    }

    expected_devices = _unique(path for launch in launches for path in launch_expected_device_paths(launch))
    observed_devices = _unique(path for hardware in hardwares for path in hardware_observed_paths(hardware))
    differences = []
    if hardwares:
        for path in expected_devices:
            if path not in observed_devices:
                differences.append({
                    "kind": "hardware_endpoint",
                    "expected": path,
                    "observed_live": observed_devices,
                    "message": "Expected device path was not present in the hardware snapshot; verify deployment or mapping before treating it as a failure.",
                })
    hardware_model = {
        "expected_device_paths": expected_devices,
        "observed_device_paths": observed_devices,
        "candidates": [hardware.get("hardware_candidates", {}) for hardware in hardwares if isinstance(hardware.get("hardware_candidates"), dict)],
    }

    unknowns = []
    required_groups = {
        "launch": launches,
        "runtime": runtimes,
        "hardware": hardwares,
        "tf_time": tf_times,
        "bag": bags,
    }
    for kind, group in required_groups.items():
        if not group:
            unknowns.append({"kind": kind, "message": "No %s evidence was supplied; that domain remains unknown." % kind})

    next_evidence = []
    if not runtimes:
        next_evidence.append({"priority": 1, "action": "collect_runtime_snapshot", "tool": "scripts/collect_runtime_snapshot.py", "reason": "Current ROS graph is unknown."})
    if not tf_times:
        next_evidence.append({"priority": 2, "action": "inspect_tf_time", "tool": "scripts/inspect_tf_time.py", "reason": "TF/time semantics are unknown."})
    if not hardwares:
        next_evidence.append({"priority": 3, "action": "inspect_system_hardware", "tool": "scripts/inspect_system_hardware.py", "reason": "Current hardware endpoints are unknown."})
    if not bags:
        next_evidence.append({"priority": 4, "action": "inspect_rosbag", "tool": "scripts/inspect_rosbag.py", "reason": "Recorded-data provenance is unavailable if a bag is part of the incident."})
    if any(item.get("kind") in {"topic_type", "recorded_topic_type"} for item in conflicts):
        next_evidence.append({"priority": 1, "action": "verify_message_provenance", "reason": "Resolve message/overlay provenance before debugging algorithm behavior."})
    if time_conflicts:
        next_evidence.append({"priority": 1, "action": "verify_time_configuration", "reason": "Expected and live time configuration conflict."})
    if differences:
        next_evidence.append({"priority": 2, "action": "verify_device_mapping", "reason": "Expected hardware endpoint is absent from the snapshot."})
    next_evidence = sorted(_unique(next_evidence), key=lambda item: (item.get("priority", 99), str(item.get("action", ""))))

    if conflicts:
        status = "conflict"
    elif not sources or unknowns:
        status = "partial"
    else:
        status = "consistent_so_far"

    return {
        "schema_version": 1,
        "evidence_kind": "merged_system_evidence",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "sources": sources,
        "nodes_expected": nodes_expected,
        "nodes_observed_live": nodes_observed_live,
        "services_observed_live": services_observed_live,
        "parameters_observed_live": parameters_observed_live,
        "topics": topics,
        "hardware": hardware_model,
        "time": time_model,
        "conflicts": conflicts,
        "differences": differences,
        "unknowns": unknowns,
        "next_evidence": next_evidence,
        "interpretation_rules": [
            "expected, observed-live and recorded are different evidence classes.",
            "unknown is not an error condition.",
            "matched presence does not prove equivalent payload quality, frame, timing or calibration.",
            "A hardware path difference may be a deployment change; verify udev/container/device mapping before calling it a failure.",
            "This aggregator preserves provenance and conflicts; it does not claim automatic root cause.",
        ],
    }


def load_payload(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("expected mapping in %s" % path)
    payload = dict(data)
    payload["_source_path"] = str(path)
    return payload


def _load_many(paths: List[Path]) -> List[Dict[str, Any]]:
    return [load_payload(path.expanduser().resolve()) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("launch", "bag", "runtime", "hardware", "tf-time", "topic-probe"):
        parser.add_argument("--" + name, action="append", type=Path, default=[])
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        payload = merge_evidence(
            _load_many(args.launch),
            _load_many(args.bag),
            _load_many(args.runtime),
            _load_many(args.hardware),
            _load_many(args.tf_time),
            _load_many(args.topic_probe),
        )
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SystemExit("cannot load evidence: %s" % exc)

    if args.format == "yaml":
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

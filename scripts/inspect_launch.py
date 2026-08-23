#!/usr/bin/env python3
"""Statically inspect a ROS 1 Noetic roslaunch XML file without starting ROS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any

import yaml

SUBSTITUTION_RE = re.compile(r"\$\([^)]*\)")
HARDWARE_HINT_RE = re.compile(r"(?:/dev/|tty(?:USB|ACM|S)?\d*|serial|baud|device|port|sensor_ip|host_ip|ip_address|ethernet|can\d*|frame(?:_id)?|calib|extrinsic|intrinsic|pps|ptp|gps|gnss|imu|lidar|camera)", re.IGNORECASE)
STACK_HINTS = {
    "nodelet": ("nodelet",),
    "pluginlib": ("pluginlib",),
    "ros_control": ("controller_manager", "spawner", "joint_state_controller", "hardware_interface"),
    "gazebo": ("gazebo", "gazebo_ros"),
    "rviz": ("rviz",),
    "pcl": ("pcl_ros", "pointcloud", "point_cloud"),
    "navigation": ("move_base", "amcl", "costmap"),
    "robot_state": ("robot_state_publisher", "joint_state_publisher"),
}


def _attrs(element: ET.Element, names: tuple[str, ...]) -> dict[str, str]:
    return {name: element.attrib[name] for name in names if name in element.attrib}


def _condition(element: ET.Element) -> dict[str, str]:
    return _attrs(element, ("if", "unless"))


def _record(element: ET.Element, names: tuple[str, ...]) -> dict[str, str]:
    record = _attrs(element, names)
    record.update(_condition(element))
    return record


def _child_records(element: ET.Element, tag: str, names: tuple[str, ...]) -> list[dict[str, str]]:
    records = []
    for child in element.findall(tag):
        records.append(_record(child, names))
    return records


def _node_record(element: ET.Element) -> dict[str, Any]:
    record: dict[str, Any] = _attrs(element, ("pkg", "type", "name", "ns", "args", "machine", "respawn", "respawn_delay", "required", "output", "cwd", "launch-prefix", "clear_params"))
    record.update(_condition(element))
    record["remaps"] = _child_records(element, "remap", ("from", "to"))
    record["params"] = _child_records(element, "param", ("name", "value", "type", "textfile", "binfile", "command"))
    record["rosparams"] = _child_records(element, "rosparam", ("command", "file", "param", "ns", "subst_value"))
    record["env"] = _child_records(element, "env", ("name", "value"))
    return record


def _hardware_hints(root: ET.Element) -> list[dict[str, str]]:
    hints = []
    seen = set()
    for element in root.iter():
        for key, value in element.attrib.items():
            if HARDWARE_HINT_RE.search(f"{key}={value}"):
                item = (element.tag, key, value)
                if item not in seen:
                    seen.add(item)
                    hints.append({"tag": element.tag, "attribute": key, "value": value})
        if element.text:
            compact = " ".join(element.text.split())
            if compact and HARDWARE_HINT_RE.search(compact):
                item = (element.tag, "text", compact[:500])
                if item not in seen:
                    seen.add(item)
                    hints.append({"tag": element.tag, "attribute": "text", "value": compact[:500]})
    return hints


def _stack_hints(root: ET.Element) -> list[str]:
    parts = []
    for element in root.iter():
        parts.append(element.tag)
        parts.extend(element.attrib.values())
        if element.text:
            parts.append(element.text)
    haystack = "\n".join(parts).lower()
    return [stack for stack, needles in STACK_HINTS.items() if any(needle.lower() in haystack for needle in needles)]


def inspect_launch(path: Path) -> dict[str, Any]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError(f"invalid launch XML: {exc}") from exc
    root = tree.getroot()
    if root.tag != "launch":
        raise ValueError(f"expected <launch> root, got <{root.tag}>")

    nodes = [_node_record(e) for e in root.iter("node")]
    tests = [_node_record(e) for e in root.iter("test")]
    args = []
    for e in root.iter("arg"):
        args.append(_record(e, ("name", "default", "value", "doc")))
    includes = []
    for e in root.iter("include"):
        r: dict[str, Any] = _record(e, ("file", "ns", "pass_all_args", "clear_params"))
        r["args"] = _child_records(e, "arg", ("name", "default", "value", "doc"))
        includes.append(r)
    groups = [_record(e, ("ns", "clear_params")) for e in root.iter("group")]
    params = [_record(e, ("name", "value", "type", "textfile", "binfile", "command")) for e in root.iter("param")]
    rosparams = [_record(e, ("command", "file", "param", "ns", "subst_value")) for e in root.iter("rosparam")]
    machines = [_attrs(e, ("name", "address", "env-loader", "default", "user", "password", "timeout")) for e in root.iter("machine")]
    packages = sorted({r.get("pkg", "") for r in nodes + tests if r.get("pkg")})
    text = path.read_text(encoding="utf-8", errors="replace")

    return {
        "schema_version": 1,
        "target": {"ros_version": "1", "ros_distro": "noetic", "format": "roslaunch_xml"},
        "file": str(path),
        "summary": {"args": len(args), "nodes": len(nodes), "tests": len(tests), "includes": len(includes), "params": len(params), "rosparams": len(rosparams), "machines": len(machines), "packages": packages},
        "args": args, "nodes": nodes, "tests": tests, "includes": includes, "groups": groups, "params": params, "rosparams": rosparams, "machines": machines,
        "hardware_hints": _hardware_hints(root),
        "stack_hints": _stack_hints(root),
        "nodelet_records": [r for r in nodes if r.get("pkg") == "nodelet" or str(r.get("type", "")).lower() == "nodelet"],
        "controller_records": [r for r in nodes if "controller_manager" in str(r.get("pkg", "")).lower() or "spawner" in str(r.get("type", "")).lower() or "controller" in str(r.get("name", "")).lower()],
        "substitutions": sorted(set(SUBSTITUTION_RE.findall(text))),
        "limitations": [
            "Static XML inspection does not resolve roslaunch substitutions.",
            "Included launch files are listed but not recursively expanded.",
            "if/unless conditions are recorded but not evaluated.",
            "Declared configuration is expected state, not runtime proof.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("launch", type=Path)
    p.add_argument("--format", choices=["json", "yaml"], default="json")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    path = a.launch.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"launch file not found: {path}")
    if path.suffix.lower() not in {".launch", ".xml", ".test"}:
        raise SystemExit("expected .launch, .xml, or .test")
    try:
        payload = inspect_launch(path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if a.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

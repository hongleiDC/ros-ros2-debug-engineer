#!/usr/bin/env python3
"""Collect a bounded, read-only ROS runtime snapshot."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess
import threading
from typing import Any

import yaml

MAX_OUTPUT = 100_000
ENV_KEYS = (
    "ROS_VERSION", "ROS_DISTRO", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY", "ROS_AUTOMATIC_DISCOVERY_RANGE", "ROS_DISCOVERY_SERVER",
    "FASTRTPS_DEFAULT_PROFILES_FILE", "CYCLONEDDS_URI",
)

ROS2_BASIC_COMMANDS = [
    ["ros2", "doctor", "--report"],
    ["ros2", "node", "list"],
    ["ros2", "topic", "list", "-t"],
]
ROS2_COMMUNICATION_COMMANDS = [
    ["ros2", "service", "list", "-t"],
    ["ros2", "action", "list", "-t"],
]
ROS2_FULL_COMMANDS = [
    ["ros2", "component", "list"],
    ["ros2", "lifecycle", "nodes"],
    ["ros2", "param", "list"],
]
ROS1_BASIC_COMMANDS = [
    ["rosversion", "-d"],
    ["rosnode", "list"],
    ["rostopic", "list"],
]
ROS1_COMMUNICATION_COMMANDS = [
    ["rosservice", "list"],
]
ROS1_FULL_COMMANDS = [
    ["rosparam", "list"],
]


def execute(command: list[str], timeout: float) -> dict[str, Any]:
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}

    def drain(stream: Any, name: str) -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                room = MAX_OUTPUT - len(buffers[name])
                if room > 0:
                    buffers[name].extend(chunk[:room])
                if len(chunk) > room:
                    truncated[name] = True
        finally:
            stream.close()

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None and process.stderr is not None
        threads = [
            threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
        ]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = process.wait()
        for thread in threads:
            thread.join(timeout=1.0)
        stdout = buffers["stdout"].decode("utf-8", errors="replace")
        stderr = buffers["stderr"].decode("utf-8", errors="replace")
        if timed_out:
            stderr = (stderr + "\ncommand timed out").strip()[:MAX_OUTPUT]
        return {
            "command": command,
            "returncode": None if timed_out else returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated["stdout"] or truncated["stderr"],
        }
    except FileNotFoundError:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "command not found", "truncated": False}


def detect_ros_version(requested: str) -> str:
    if requested in {"1", "2"}:
        return requested
    env = os.environ.get("ROS_VERSION")
    if env in {"1", "2"}:
        return env
    if shutil.which("ros2"):
        return "2"
    if shutil.which("rosversion"):
        return "1"
    return "unknown"


def result_for(results: list[dict[str, Any]], command: list[str]) -> dict[str, Any] | None:
    return next((item for item in results if item["command"] == command), None)


def listed_names(result: dict[str, Any] | None, limit: int) -> list[str]:
    if not result or result["returncode"] != 0:
        return []
    names = []
    for line in result["stdout"].splitlines():
        name = line.strip().split(" ", 1)[0]
        if name.startswith("/") and name not in names:
            names.append(name)
    return names[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros-version", choices=["auto", "1", "2"], default="auto")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--profile", choices=["basic", "communication", "full"], default="basic")
    parser.add_argument("--detail-limit", type=int, default=20)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()

    version = detect_ros_version(args.ros_version)
    if args.detail_limit < 0 or args.detail_limit > 200:
        raise SystemExit("--detail-limit must be between 0 and 200")
    if version == "2":
        commands = list(ROS2_BASIC_COMMANDS)
        if args.profile in {"communication", "full"}:
            commands += ROS2_COMMUNICATION_COMMANDS
        if args.profile == "full":
            commands += ROS2_FULL_COMMANDS
    elif version == "1":
        commands = list(ROS1_BASIC_COMMANDS)
        if args.profile in {"communication", "full"}:
            commands += ROS1_COMMUNICATION_COMMANDS
        if args.profile == "full":
            commands += ROS1_FULL_COMMANDS
    else:
        commands = []
    results = [execute(command, args.timeout) for command in commands]
    detail_results: list[dict[str, Any]] = []
    if version == "2" and args.profile in {"communication", "full"}:
        topic_list = result_for(results, ["ros2", "topic", "list", "-t"])
        for topic in listed_names(topic_list, args.detail_limit):
            detail_results.append(execute(["ros2", "topic", "info", topic, "--verbose"], args.timeout))
    if version == "2" and args.profile == "full":
        node_list = result_for(results, ["ros2", "node", "list"])
        for node in listed_names(node_list, args.detail_limit):
            detail_results.append(execute(["ros2", "node", "info", node], args.timeout))
            detail_results.append(execute(["ros2", "param", "dump", node], args.timeout))
    if version == "1" and args.profile == "full":
        detail_results.append(execute(["rosparam", "get", "/"], args.timeout))
    successful = sum(1 for item in results if item["returncode"] == 0)
    detailed_successful = sum(1 for item in detail_results if item["returncode"] == 0)
    command_ok = {" ".join(item["command"]): item["returncode"] == 0 for item in results}
    full_requirements = (
        ["ros2 node list", "ros2 topic list -t", "ros2 param list"]
        if version == "2"
        else ["rosnode list", "rostopic list", "rosparam list"]
    )
    full_coverage = args.profile == "full" and all(command_ok.get(name, False) for name in full_requirements)
    if detail_results:
        full_coverage = full_coverage and detailed_successful == len(detail_results)
    runtime_observed = successful > 0
    topic_details = [item for item in detail_results if item["command"][1:3] == ["topic", "info"]]
    snapshot = {
        "schema_version": 1,
        "status": "measured" if runtime_observed else "candidate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ros_version": version,
        "profile": args.profile,
        "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        "commands": results,
        "detail_commands": detail_results,
        "coverage": {
            "understanding_level": "L3" if full_coverage else "L1",
            "runtime_observed": runtime_observed,
            "full_runtime_coverage": full_coverage,
            "successful_commands": successful,
            "total_commands": len(results),
            "successful_detail_commands": detailed_successful,
            "total_detail_commands": len(detail_results),
            "domains": {
                "graph": command_ok.get("ros2 node list", False) or command_ok.get("rosnode list", False),
                "topics": command_ok.get("ros2 topic list -t", False) or command_ok.get("rostopic list", False),
                "topic_qos": version == "2" and bool(topic_details) and all(item["returncode"] == 0 for item in topic_details),
                "parameters": command_ok.get("ros2 param list", False) or command_ok.get("rosparam list", False),
            },
        },
        "limitations": [
            "This is a point-in-time, read-only snapshot.",
            "Commands that are unavailable, unsupported by the installed distro, or timed out are retained as missing evidence.",
            "No topic data was published, echoed, or modified.",
            "L3 is assigned only by the full profile when graph, topic, parameter, and requested detail commands succeed.",
            "The full profile requests parameter dumps, but secrets and very large values may be exposed or truncated; review before sharing.",
            "TF topology and transform freshness still require dedicated /tf and /tf_static analysis.",
        ],
    }
    text = yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Collect a bounded, read-only ROS runtime snapshot."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess
from typing import Any

import yaml

MAX_OUTPUT = 100_000
ENV_KEYS = (
    "ROS_VERSION", "ROS_DISTRO", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY", "ROS_AUTOMATIC_DISCOVERY_RANGE", "ROS_DISCOVERY_SERVER",
    "FASTRTPS_DEFAULT_PROFILES_FILE", "CYCLONEDDS_URI",
)

ROS2_COMMANDS = [
    ["ros2", "doctor", "--report"],
    ["ros2", "node", "list"],
    ["ros2", "topic", "list", "-t"],
    ["ros2", "service", "list", "-t"],
    ["ros2", "action", "list", "-t"],
    ["ros2", "component", "list"],
    ["ros2", "lifecycle", "nodes"],
    ["ros2", "param", "list"],
]
ROS1_COMMANDS = [
    ["rosversion", "-d"],
    ["rosnode", "list"],
    ["rostopic", "list"],
    ["rosservice", "list"],
    ["rosparam", "list"],
]


def execute(command: list[str], timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:MAX_OUTPUT],
            "stderr": result.stderr[:MAX_OUTPUT],
            "truncated": len(result.stdout) > MAX_OUTPUT or len(result.stderr) > MAX_OUTPUT,
        }
    except FileNotFoundError:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "command not found", "truncated": False}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": command,
            "returncode": None,
            "stdout": stdout[:MAX_OUTPUT],
            "stderr": (stderr + "\ncommand timed out").strip()[:MAX_OUTPUT],
            "truncated": len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT,
        }


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros-version", choices=["auto", "1", "2"], default="auto")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()

    version = detect_ros_version(args.ros_version)
    commands = ROS2_COMMANDS if version == "2" else ROS1_COMMANDS if version == "1" else []
    results = [execute(command, args.timeout) for command in commands]
    successful = sum(1 for item in results if item["returncode"] == 0)
    snapshot = {
        "schema_version": 1,
        "status": "measured" if successful else "candidate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ros_version": version,
        "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        "commands": results,
        "coverage": {
            "understanding_level": "L3" if successful else "L1",
            "successful_commands": successful,
            "total_commands": len(results),
        },
        "limitations": [
            "This is a point-in-time, read-only snapshot.",
            "Commands that are unavailable, unsupported by the installed distro, or timed out are retained as missing evidence.",
            "No topic data was published, echoed, or modified.",
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

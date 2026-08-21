#!/usr/bin/env python3
"""Collect a bounded, read-only ROS 1 Noetic runtime snapshot."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import threading
from typing import Any

import yaml

MAX_OUTPUT = 100_000
ENV_KEYS = (
    "ROS_VERSION", "ROS_DISTRO", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME",
    "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH",
)

BASIC_COMMANDS = [
    ["rosversion", "-d"],
    ["rosnode", "list"],
    ["rostopic", "list"],
]
COMMUNICATION_COMMANDS = [
    ["rosservice", "list"],
    ["rosparam", "list"],
]
FULL_COMMANDS = [
    ["roswtf"],
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
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


def listed_names(result: dict[str, Any] | None, limit: int) -> list[str]:
    if not result or result["returncode"] != 0:
        return []
    names: list[str] = []
    for line in result["stdout"].splitlines():
        name = line.strip().split(" ", 1)[0]
        if name.startswith("/") and name not in names:
            names.append(name)
    return names[:limit]


def result_for(results: list[dict[str, Any]], command: list[str]) -> dict[str, Any] | None:
    return next((item for item in results if item["command"] == command), None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--profile", choices=["basic", "communication", "full"], default="basic")
    parser.add_argument("--detail-limit", type=int, default=20)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output")
    parser.add_argument("--allow-non-noetic", action="store_true", help="Collect evidence even when the environment is not ROS Noetic; status remains mismatched.")
    args = parser.parse_args()

    if args.detail_limit < 0 or args.detail_limit > 200:
        raise SystemExit("--detail-limit must be between 0 and 200")

    env_version = os.environ.get("ROS_VERSION")
    env_distro = os.environ.get("ROS_DISTRO")
    distro_probe = execute(["rosversion", "-d"], args.timeout)
    probe_distro = distro_probe["stdout"].strip() if distro_probe["returncode"] == 0 else None
    is_noetic = env_version == "1" and env_distro == "noetic" and probe_distro == "noetic"

    if not is_noetic and not args.allow_non_noetic:
        snapshot = {
            "schema_version": 2,
            "status": "environment_mismatch",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "expected": {"ROS_VERSION": "1", "ROS_DISTRO": "noetic", "rosversion_d": "noetic"},
            "observed": {"ROS_VERSION": env_version, "ROS_DISTRO": env_distro, "rosversion_d": probe_distro},
            "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
            "probe": distro_probe,
            "commands": [],
            "detail_commands": [],
            "limitations": ["This branch is intentionally locked to ROS 1 Noetic. Runtime collection stopped before applying Noetic assumptions."],
        }
        text = yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(snapshot, ensure_ascii=False, indent=2)
        if args.output:
            from pathlib import Path
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 2

    commands = list(BASIC_COMMANDS)
    if args.profile in {"communication", "full"}:
        commands += COMMUNICATION_COMMANDS
    if args.profile == "full":
        commands += FULL_COMMANDS

    results = [execute(command, args.timeout) for command in commands]
    detail_results: list[dict[str, Any]] = []
    if args.profile in {"communication", "full"}:
        topic_list = result_for(results, ["rostopic", "list"])
        for topic in listed_names(topic_list, args.detail_limit):
            detail_results.append(execute(["rostopic", "info", topic], args.timeout))
    if args.profile == "full":
        node_list = result_for(results, ["rosnode", "list"])
        for node in listed_names(node_list, args.detail_limit):
            detail_results.append(execute(["rosnode", "info", node], args.timeout))

    successful = sum(1 for item in results if item["returncode"] == 0)
    detailed_successful = sum(1 for item in detail_results if item["returncode"] == 0)
    command_ok = {" ".join(item["command"]): item["returncode"] == 0 for item in results}
    full_requirements = ["rosversion -d", "rosnode list", "rostopic list", "rosparam list"]
    full_coverage = args.profile == "full" and all(command_ok.get(name, False) for name in full_requirements)
    if detail_results:
        full_coverage = full_coverage and detailed_successful == len(detail_results)

    snapshot = {
        "schema_version": 2,
        "status": "measured" if successful > 0 else "candidate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ros_version": "1",
        "ros_distro": "noetic" if is_noetic else probe_distro,
        "environment_match": is_noetic,
        "profile": args.profile,
        "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        "commands": results,
        "detail_commands": detail_results,
        "coverage": {
            "understanding_level": "L3" if full_coverage else "L1",
            "runtime_observed": successful > 0,
            "full_runtime_coverage": full_coverage,
            "successful_commands": successful,
            "total_commands": len(results),
            "successful_detail_commands": detailed_successful,
            "total_detail_commands": len(detail_results),
            "domains": {
                "master_graph": command_ok.get("rosnode list", False),
                "topics": command_ok.get("rostopic list", False),
                "services": command_ok.get("rosservice list", False),
                "parameters": command_ok.get("rosparam list", False),
            },
        },
        "limitations": [
            "This is a point-in-time, read-only ROS 1 Noetic snapshot.",
            "ROS master registration does not prove TCPROS data-path reachability.",
            "No topic data was published, echoed, or modified.",
            "TF topology and transform freshness require dedicated tf/tf2 analysis.",
            "ROS 2 DDS/QoS/lifecycle/executor concepts are intentionally excluded.",
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

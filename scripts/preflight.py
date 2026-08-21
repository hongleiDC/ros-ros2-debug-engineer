#!/usr/bin/env python3
"""Check skill dependencies and ROS 1 Noetic command availability without third-party imports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any

PROFILES = {
    "none": {"modules": [], "commands": []},
    "core": {"modules": ["yaml"], "commands": ["git"]},
    "knowledge": {"modules": ["yaml", "jsonschema"], "commands": ["git"]},
    "ros-runtime": {"modules": ["yaml"], "commands": ["git", "rosversion", "rosnode", "rostopic", "rosservice", "rosparam"]},
}


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def rosversion_d() -> str | None:
    if not command_available("rosversion"):
        return None
    try:
        result = subprocess.run(["rosversion", "-d"], text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def report(profile: str) -> dict[str, Any]:
    required = PROFILES[profile]
    modules = {name: module_available(name) for name in sorted({"yaml", "jsonschema"})}
    command_names = [
        "git", "rosversion", "roscore", "roslaunch", "rosnode", "rostopic", "rosservice",
        "rosparam", "rosbag", "roswtf", "catkin_make", "catkin",
    ]
    commands = {name: command_available(name) for name in command_names}
    missing_modules = [name for name in required["modules"] if not modules[name]]
    missing_commands = [name for name in required["commands"] if not commands[name]]

    distro_probe = rosversion_d() if profile == "ros-runtime" else None
    env_version = os.environ.get("ROS_VERSION")
    env_distro = os.environ.get("ROS_DISTRO")
    noetic_match = True
    mismatch_reasons: list[str] = []
    if profile == "ros-runtime":
        noetic_match = env_version == "1" and env_distro == "noetic" and distro_probe == "noetic"
        if env_version != "1":
            mismatch_reasons.append(f"ROS_VERSION={env_version!r}, expected '1'")
        if env_distro != "noetic":
            mismatch_reasons.append(f"ROS_DISTRO={env_distro!r}, expected 'noetic'")
        if distro_probe != "noetic":
            mismatch_reasons.append(f"rosversion -d={distro_probe!r}, expected 'noetic'")

    ok = not missing_modules and not missing_commands and noetic_match
    actions: list[str] = []
    if missing_modules:
        actions.append("Install Python dependencies: python -m pip install -r requirements.txt")
    if missing_commands:
        actions.append("Source a ROS Noetic environment or install the missing ROS 1 command-line tools")
    if profile == "ros-runtime" and not noetic_match:
        actions.append("Source /opt/ros/noetic/setup.bash and the intended catkin workspace, then verify ROS_VERSION=1 and ROS_DISTRO=noetic")

    return {
        "ok": ok,
        "profile": profile,
        "target": {"ROS_VERSION": "1", "ROS_DISTRO": "noetic"},
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "platform": platform.platform(),
        "modules": modules,
        "commands": commands,
        "environment": {
            key: os.environ.get(key)
            for key in ("ROS_VERSION", "ROS_DISTRO", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME", "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH")
            if os.environ.get(key) is not None
        },
        "rosversion_d": distro_probe,
        "noetic_match": noetic_match,
        "mismatch_reasons": mismatch_reasons,
        "missing": {"modules": missing_modules, "commands": missing_commands},
        "next_actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require", choices=sorted(PROFILES), default="knowledge")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    result = report(args.require)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        state = "PASS" if result["ok"] else "BLOCKED"
        print(f"[{state}] profile={args.require} python={result['python']['version']} platform={result['platform']}")
        if args.require == "ros-runtime":
            print(f"target: ROS_VERSION=1 ROS_DISTRO=noetic rosversion_d={result['rosversion_d']!r}")
        for group in ("modules", "commands"):
            values = ", ".join(f"{name}={'ok' if value else 'missing'}" for name, value in result[group].items())
            print(f"{group}: {values}")
        for reason in result["mismatch_reasons"]:
            print(f"mismatch: {reason}")
        for action in result["next_actions"]:
            print(f"next: {action}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

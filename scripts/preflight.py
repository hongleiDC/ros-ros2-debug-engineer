#!/usr/bin/env python3
"""Check skill dependencies and ROS command availability without third-party imports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from typing import Any

PROFILES = {
    "none": {"modules": [], "commands": []},
    "core": {"modules": ["yaml"], "commands": ["git"]},
    "knowledge": {"modules": ["yaml", "jsonschema"], "commands": ["git"]},
    "ros-runtime": {"modules": ["yaml"], "commands": ["git", "ros2|rosversion"]},
}


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def command_available(name: str) -> bool:
    return any(shutil.which(option) for option in name.split("|"))


def report(profile: str) -> dict[str, Any]:
    required = PROFILES[profile]
    modules = {name: module_available(name) for name in sorted({"yaml", "jsonschema"})}
    commands = {name: command_available(name) for name in ["git", "ros2", "rosversion", "colcon"]}
    missing_modules = [name for name in required["modules"] if not modules[name]]
    missing_commands = [name for name in required["commands"] if not command_available(name)]
    ok = not missing_modules and not missing_commands
    actions: list[str] = []
    if missing_modules:
        actions.append("Install Python dependencies: python -m pip install -r requirements.txt")
    if missing_commands:
        actions.append("Source the intended ROS environment or install the missing command-line tools")
    return {
        "ok": ok,
        "profile": profile,
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "platform": platform.platform(),
        "modules": modules,
        "commands": commands,
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
        for group in ("modules", "commands"):
            values = ", ".join(f"{name}={'ok' if value else 'missing'}" for name, value in result[group].items())
            print(f"{group}: {values}")
        for action in result["next_actions"]:
            print(f"next: {action}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

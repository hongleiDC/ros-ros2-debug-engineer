#!/usr/bin/env python3
"""Manage versioned ROS 1 Noetic system profiles."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["save", "list"])
    parser.add_argument("--profiles", type=Path, default=Path(".ros_noetic_profiles"))
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    args.profiles.mkdir(parents=True, exist_ok=True)
    if args.command == "list":
        for item in sorted(args.profiles.glob("v*")):
            print(item.name)
        return 0

    if not args.profile:
        raise SystemExit("--profile is required")
    versions = [int(p.name[1:]) for p in args.profiles.glob("v*") if p.name[1:].isdigit()]
    version = max(versions, default=0) + 1
    target = args.profiles / f"v{version:04d}"
    target.mkdir()
    shutil.copy2(args.profile, target / "robot_profile.yaml")
    if args.summary:
        shutil.copy2(args.summary, target / "session_summary.yaml")
    (target / "metadata.yaml").write_text(yaml.safe_dump({
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
    }, sort_keys=False), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

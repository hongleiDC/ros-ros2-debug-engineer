#!/usr/bin/env python3
"""Capture user-auditable ROS 1 Noetic run evidence with native ROS tools."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
from typing import Dict, List, Optional, Sequence


ENV_NAMES = (
    "ROS_VERSION",
    "ROS_DISTRO",
    "ROS_MASTER_URI",
    "ROS_IP",
    "ROS_HOSTNAME",
    "ROS_HOME",
    "ROS_LOG_DIR",
    "ROS_PACKAGE_PATH",
    "CMAKE_PREFIX_PATH",
)

DEFAULT_BAG_TOPICS = (
    "/rosout",
    "/rosout_agg",
    "/diagnostics",
    "/tf",
    "/tf_static",
    "/clock",
)

SNAPSHOT_COMMANDS = (
    ("rosversion", "rosversion", "-d"),
    ("rosnode_list", "rosnode", "list"),
    ("rostopic_list", "rostopic", "list", "-v"),
    ("rosservice_list", "rosservice", "list"),
    ("rosparam_list", "rosparam", "list"),
    ("use_sim_time", "rosparam", "get", "/use_sim_time"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_run_dirs(run_dir: Path) -> Dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "logs": run_dir / "logs",
        "bags": run_dir / "bags",
        "series": run_dir / "series",
        "plots": run_dir / "plots",
        "report": run_dir / "report",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def command_text(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def run_capture(command: Sequence[str], timeout: float) -> Dict[str, object]:
    started = utc_now()
    try:
        completed = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": list(command),
            "started_utc": started,
            "finished_utc": utc_now(),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except FileNotFoundError as exc:
        return {
            "command": list(command),
            "started_utc": started,
            "finished_utc": utc_now(),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "started_utc": started,
            "finished_utc": utc_now(),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\ncommand timed out",
        }


def save_result(log_dir: Path, name: str, result: Dict[str, object]) -> None:
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    (log_dir / (name + ".txt")).write_text(stdout, encoding="utf-8")
    if stderr:
        (log_dir / (name + ".stderr.txt")).write_text(stderr, encoding="utf-8")


def snapshot(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    dirs = ensure_run_dirs(run_dir)
    log_dir = dirs["logs"] / "ros_native"
    log_dir.mkdir(parents=True, exist_ok=True)

    planned = [list(item[1:]) for item in SNAPSHOT_COMMANDS]
    planned.append(["rosparam", "dump", str(log_dir / "rosparams.yaml")])
    if args.roswtf:
        planned.append(["roswtf"])
    if args.dry_run:
        print(json.dumps({"run_dir": str(run_dir), "commands": planned}, indent=2))
        return 0

    results: List[Dict[str, object]] = []
    for item in SNAPSHOT_COMMANDS:
        name = item[0]
        result = run_capture(item[1:], args.timeout)
        save_result(log_dir, name, result)
        results.append({key: value for key, value in result.items() if key not in {"stdout", "stderr"}})

    params_result = run_capture(("rosparam", "dump", str(log_dir / "rosparams.yaml")), args.timeout)
    results.append({key: value for key, value in params_result.items() if key not in {"stdout", "stderr"}})
    if params_result.get("returncode") != 0:
        save_result(log_dir, "rosparam_dump", params_result)

    if args.roswtf:
        roswtf_result = run_capture(("roswtf",), max(args.timeout, 30.0))
        save_result(log_dir, "roswtf", roswtf_result)
        results.append({key: value for key, value in roswtf_result.items() if key not in {"stdout", "stderr"}})

    manifest = {
        "schema_version": 1,
        "kind": "ros_noetic_native_snapshot",
        "created_utc": utc_now(),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "environment": {name: os.getenv(name) for name in ENV_NAMES},
        "commands": results,
    }
    write_json(log_dir / "snapshot_manifest.json", manifest)
    print(log_dir)
    return 0


def ros_log_source() -> Optional[Path]:
    raw_log_dir = os.getenv("ROS_LOG_DIR")
    if raw_log_dir:
        root = Path(raw_log_dir).expanduser()
    else:
        ros_home = Path(os.getenv("ROS_HOME", str(Path.home() / ".ros"))).expanduser()
        root = ros_home / "log"
    latest = root / "latest"
    if latest.exists():
        try:
            return latest.resolve()
        except OSError:
            return latest
    if root.is_dir():
        candidates = [path for path in root.iterdir() if path.is_dir()]
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
    return None


def copy_logs(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    dirs = ensure_run_dirs(run_dir)
    source = ros_log_source()
    destination = dirs["logs"] / "roslaunch_latest"
    if source is None:
        print("ROS log directory was not found", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"source": str(source), "destination": str(destination)}, indent=2))
        return 0
    if destination.exists():
        if not args.force:
            print("destination exists; use --force to replace: %s" % destination, file=sys.stderr)
            return 3
        shutil.rmtree(str(destination))
    shutil.copytree(str(source), str(destination))
    write_json(dirs["logs"] / "roslaunch_log_copy.json", {
        "copied_utc": utc_now(),
        "source": str(source),
        "destination": str(destination),
    })
    print(destination)
    return 0


def build_bag_command(args: argparse.Namespace, bag_path: Path) -> List[str]:
    command = ["rosbag", "record", "-O", str(bag_path)]
    if args.all:
        command.append("-a")
        return command

    topics: List[str] = []
    if not args.no_default_topics:
        topics.extend(DEFAULT_BAG_TOPICS)
    topics.extend(args.topic)
    deduped: List[str] = []
    seen = set()
    for topic in topics:
        if topic and topic not in seen:
            seen.add(topic)
            deduped.append(topic)
    if not deduped:
        raise ValueError("provide --topic, use --all, or keep the default Noetic audit topics")
    command.extend(deduped)
    return command


def record(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    dirs = ensure_run_dirs(run_dir)
    bag_path = dirs["bags"] / (args.name + ".bag")
    try:
        command = build_bag_command(args, bag_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    (dirs["logs"] / "rosbag_record_command.txt").write_text(command_text(command) + "\n", encoding="utf-8")
    if args.dry_run:
        print(command_text(command))
        return 0

    started = utc_now()
    try:
        process = subprocess.Popen(command)
    except FileNotFoundError:
        print("rosbag command was not found; source the ROS Noetic environment first", file=sys.stderr)
        return 127

    returncode = 0
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        process.send_signal(signal.SIGINT)
        try:
            returncode = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            returncode = process.wait(timeout=5)

    write_json(dirs["logs"] / "rosbag_record_result.json", {
        "started_utc": started,
        "finished_utc": utc_now(),
        "command": command,
        "bag_path": str(bag_path),
        "returncode": returncode,
    })
    return int(returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    snap = sub.add_parser("snapshot", help="save ROS graph, parameters and Noetic environment into RUN_DIR/logs")
    snap.add_argument("run_dir")
    snap.add_argument("--timeout", type=float, default=10.0)
    snap.add_argument("--roswtf", action="store_true", help="also capture roswtf output")
    snap.add_argument("--dry-run", action="store_true")
    snap.set_defaults(func=snapshot)

    bag = sub.add_parser("record", help="record a rosbag1 result log into RUN_DIR/bags until Ctrl-C")
    bag.add_argument("run_dir")
    bag.add_argument("--topic", action="append", default=[], help="project result/input topic to record; repeat as needed")
    bag.add_argument("--all", action="store_true", help="record all topics instead of an explicit allowlist")
    bag.add_argument("--no-default-topics", action="store_true", help="omit rosout/diagnostics/TF/clock audit topics")
    bag.add_argument("--name", default="run", help="bag base name inside RUN_DIR/bags")
    bag.add_argument("--dry-run", action="store_true")
    bag.set_defaults(func=record)

    logs = sub.add_parser("copy-logs", help="copy the current ROS launch/node log directory into RUN_DIR/logs")
    logs.add_argument("run_dir")
    logs.add_argument("--force", action="store_true")
    logs.add_argument("--dry-run", action="store_true")
    logs.set_defaults(func=copy_logs)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Collect a bounded, read-only Linux and hardware inventory for ROS 1 Noetic adaptation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any

import yaml

try:
    import grp
except ImportError:  # pragma: no cover - Windows CI import compatibility
    grp = None
try:
    import pwd
except ImportError:  # pragma: no cover - Windows CI import compatibility
    pwd = None

MAX_OUTPUT = 100_000
ENV_KEYS = (
    "ROS_VERSION", "ROS_DISTRO", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME",
    "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH",
)
BASE_COMMANDS = [
    ["uname", "-a"],
    ["lsb_release", "-ds"],
    ["python3", "--version"],
    ["gcc", "--version"],
    ["cmake", "--version"],
    ["groups"],
    ["ip", "-br", "addr"],
    ["ip", "route"],
    ["lsusb"],
    ["lsusb", "-t"],
    ["lspci", "-nn"],
    ["timedatectl", "status"],
    ["rosversion", "-d"],
]


def execute(command: list[str], timeout: float) -> dict[str, Any]:
    if shutil.which(command[0]) is None:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "command not found", "truncated": False}
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
        stdout = result.stdout
        stderr = result.stderr
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": stdout[:MAX_OUTPUT],
            "stderr": stderr[:MAX_OUTPUT],
            "truncated": len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {"command": command, "returncode": None, "stdout": stdout[:MAX_OUTPUT], "stderr": (stderr + "\ncommand timed out").strip()[:MAX_OUTPUT], "truncated": len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT}


def classify_device_path(path: str) -> str:
    name = Path(path).name.lower()
    if name.startswith(("ttyusb", "ttyacm")) or "/serial/by-id/" in path.lower():
        return "serial"
    if name.startswith("video"):
        return "video"
    if "input/event" in path.lower():
        return "input"
    return "other"


def owner_name(uid: int) -> str | None:
    if pwd is None:
        return None
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return None


def group_name(gid: int) -> str | None:
    if grp is None:
        return None
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return None


def path_record(raw: str) -> dict[str, Any]:
    path = Path(raw)
    record: dict[str, Any] = {"path": raw, "exists": path.exists() or path.is_symlink(), "kind": classify_device_path(raw)}
    if not record["exists"]:
        return record
    try:
        info = path.stat()
        record.update({
            "mode": stat.filemode(info.st_mode),
            "uid": info.st_uid,
            "gid": info.st_gid,
            "owner": owner_name(info.st_uid),
            "group": group_name(info.st_gid),
            "major": os.major(info.st_rdev) if stat.S_ISCHR(info.st_mode) or stat.S_ISBLK(info.st_mode) else None,
            "minor": os.minor(info.st_rdev) if stat.S_ISCHR(info.st_mode) or stat.S_ISBLK(info.st_mode) else None,
        })
    except OSError as exc:
        record["stat_error"] = str(exc)
    if path.is_symlink():
        try:
            record["symlink_target"] = str(path.resolve())
        except OSError:
            record["symlink_target"] = None
    return record


def discovered_device_paths() -> list[str]:
    patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/video*", "/dev/input/event*"]
    paths: list[str] = []
    for pattern in patterns:
        paths.extend(glob.glob(pattern))
    serial_by_id = Path("/dev/serial/by-id")
    if serial_by_id.is_dir():
        paths.extend(str(path) for path in serial_by_id.iterdir())
    return sorted(dict.fromkeys(paths))


def network_interfaces() -> list[str]:
    root = Path("/sys/class/net")
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir())


def interface_role(name: str) -> str:
    lower = name.lower()
    if lower == "lo":
        return "loopback"
    if lower.startswith(("can", "slcan", "vcan")):
        return "can"
    if lower.startswith(("wl", "wlan")):
        return "wifi"
    if lower.startswith(("en", "eth")):
        return "ethernet"
    return "other"


def noetic_match(commands: list[dict[str, Any]]) -> tuple[bool, str | None]:
    distro = None
    for item in commands:
        if item["command"] == ["rosversion", "-d"] and item["returncode"] == 0:
            distro = item["stdout"].strip()
            break
    return os.environ.get("ROS_VERSION") == "1" and os.environ.get("ROS_DISTRO") == "noetic" and distro == "noetic", distro


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", action="append", default=[], help="Focus on a device path such as /dev/ttyUSB0.")
    parser.add_argument("--interface", action="append", default=[], help="Focus on a network interface such as eth0 or can0.")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()

    commands = [execute(command, args.timeout) for command in BASE_COMMANDS]
    match, probe_distro = noetic_match(commands)
    discovered = discovered_device_paths()
    requested_devices = list(dict.fromkeys(args.device))
    all_device_paths = list(dict.fromkeys(discovered + requested_devices))
    devices = [path_record(path) for path in all_device_paths]

    device_details: dict[str, Any] = {}
    for raw in requested_devices:
        detail: list[dict[str, Any]] = []
        if Path(raw).exists() or Path(raw).is_symlink():
            detail.append(execute(["udevadm", "info", "--query=property", "--name", raw], args.timeout))
            if classify_device_path(raw) == "serial":
                detail.append(execute(["stty", "-F", raw, "-a"], args.timeout))
        device_details[raw] = detail

    interfaces = network_interfaces()
    requested_interfaces = list(dict.fromkeys(args.interface))
    interface_records = [{"name": name, "role": interface_role(name), "requested": name in requested_interfaces} for name in interfaces]
    interface_details: dict[str, Any] = {}
    for name in requested_interfaces:
        interface_details[name] = [
            execute(["ip", "-details", "link", "show", "dev", name], args.timeout),
            execute(["ethtool", name], args.timeout),
        ]

    candidates = {
        "serial": [item["path"] for item in devices if item["kind"] == "serial"],
        "video": [item["path"] for item in devices if item["kind"] == "video"],
        "can_interfaces": [item["name"] for item in interface_records if item["role"] == "can"],
        "ethernet_interfaces": [item["name"] for item in interface_records if item["role"] == "ethernet"],
        "wifi_interfaces": [item["name"] for item in interface_records if item["role"] == "wifi"],
    }
    payload = {
        "schema_version": 1,
        "status": "measured",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic", "os_family": "linux"},
        "environment": {
            "match_noetic": match,
            "rosversion_d": probe_distro,
            "variables": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        },
        "system_commands": commands,
        "devices": devices,
        "device_details": device_details,
        "interfaces": interface_records,
        "interface_details": interface_details,
        "hardware_candidates": candidates,
        "limitations": [
            "Device paths and interface names identify transport candidates, not the physical sensor model by themselves.",
            "A hardware adaptation claim still requires driver package, firmware, transport parameters, topic type/rate, frame, timestamp, units, and calibration evidence.",
            "All commands in this script are read-only; unavailable utilities are reported instead of installed automatically.",
        ],
    }
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

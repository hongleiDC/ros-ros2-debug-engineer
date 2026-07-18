#!/usr/bin/env python3
"""Build a read-only static fact model for a ROS workspace or repository."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

import yaml

EXCLUDED_DIRS = {
    ".git", ".github", ".idea", ".vscode", "build", "install", "log",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules",
}
TEXT_SUFFIXES = {".cpp", ".cc", ".cxx", ".c", ".hpp", ".h", ".py", ".xml", ".yaml", ".yml", ".launch", ".xacro", ".urdf"}
MAX_TEXT_BYTES = 2 * 1024 * 1024


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def parse_package(path: Path, root: Path) -> dict[str, Any]:
    package_root = path.parent
    data: dict[str, Any] = {
        "name": package_root.name,
        "path": rel(package_root, root),
        "format": "unknown",
        "build_type": "unknown",
        "version": "unknown",
        "dependencies": [],
        "languages": [],
        "executables": [],
        "components": [],
        "parse_errors": [],
    }
    try:
        tree = ET.parse(path)
        pkg = tree.getroot()
        data["format"] = pkg.attrib.get("format", "1")
        name = pkg.findtext("name")
        version = pkg.findtext("version")
        if name:
            data["name"] = name.strip()
        if version:
            data["version"] = version.strip()
        export = pkg.find("export")
        if export is not None:
            build_type = export.findtext("build_type")
            if build_type:
                data["build_type"] = build_type.strip()
        deps: set[str] = set()
        for tag in (
            "depend", "build_depend", "buildtool_depend", "build_export_depend",
            "exec_depend", "run_depend", "test_depend", "doc_depend",
        ):
            for node in pkg.findall(tag):
                if node.text and node.text.strip():
                    deps.add(node.text.strip())
        data["dependencies"] = sorted(deps)
    except (ET.ParseError, OSError) as exc:
        data["parse_errors"].append(str(exc))

    package_files = [p for p in iter_files(package_root) if root in p.parents or p == root]
    suffixes = {p.suffix.lower() for p in package_files}
    languages: list[str] = []
    if suffixes.intersection({".cpp", ".cc", ".cxx", ".c", ".hpp", ".h"}):
        languages.append("c++")
    if ".py" in suffixes:
        languages.append("python")
    data["languages"] = languages

    cmake = package_root / "CMakeLists.txt"
    if cmake.is_file():
        text = cmake.read_text(encoding="utf-8", errors="replace")
        data["executables"] = sorted(set(re.findall(r"add_executable\s*\(\s*([^\s\)]+)", text)))
        data["components"] = sorted(set(re.findall(r"rclcpp_components_register_nodes\s*\([^\)]*?\"([^\"]+)\"", text, re.DOTALL)))
    for setup_name in ("setup.py", "setup.cfg"):
        setup_path = package_root / setup_name
        if setup_path.is_file():
            text = setup_path.read_text(encoding="utf-8", errors="replace")
            entries = re.findall(r"['\"]([A-Za-z0-9_.-]+)\s*=\s*[A-Za-z0-9_.:.-]+['\"]", text)
            data["executables"] = sorted(set(data["executables"]).union(entries))
    return data


def safe_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES or path.suffix.lower() not in TEXT_SUFFIXES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.workspace.resolve()
    if not root.is_dir():
        raise SystemExit(f"workspace not found: {root}")

    files = list(iter_files(root))
    package_xmls = sorted(p for p in files if p.name == "package.xml")
    packages = [parse_package(p, root) for p in package_xmls]

    artifacts: dict[str, list[str]] = {
        "launch": [], "parameters": [], "interfaces": [], "urdf_xacro": [],
        "plugins": [], "docker": [], "systemd_udev": [], "tests": [], "bags": [],
        "ci": [], "knowledge": [],
    }
    combined_text_parts: list[str] = []
    for path in files:
        r = rel(path, root)
        lower = r.lower()
        suffix = path.suffix.lower()
        if lower.endswith((".launch", ".launch.py")) or "/launch/" in f"/{lower}":
            if suffix in {".py", ".xml", ".launch", ".yaml", ".yml"} or lower.endswith(".launch.py"):
                artifacts["launch"].append(r)
        if ("/config/" in f"/{lower}" or "/params/" in f"/{lower}" or "/parameter" in lower) and suffix in {".yaml", ".yml", ".json"}:
            artifacts["parameters"].append(r)
        if any(f"/{kind}/" in f"/{lower}" for kind in ("msg", "srv", "action")) and suffix in {".msg", ".srv", ".action"}:
            artifacts["interfaces"].append(r)
        if suffix in {".urdf", ".xacro"}:
            artifacts["urdf_xacro"].append(r)
        if path.name == "plugin.xml" or "plugins.xml" in lower:
            artifacts["plugins"].append(r)
        if path.name.startswith("Dockerfile") or path.name in {"docker-compose.yml", "docker-compose.yaml"}:
            artifacts["docker"].append(r)
        if suffix in {".service", ".rules"} or "/udev/" in f"/{lower}" or "/systemd/" in f"/{lower}":
            artifacts["systemd_udev"].append(r)
        if "/test" in lower or path.name.startswith("test_") or path.name.endswith("_test.cpp"):
            artifacts["tests"].append(r)
        if suffix in {".bag", ".mcap", ".db3"} or path.name == "metadata.yaml":
            artifacts["bags"].append(r)
        if lower.startswith(".github/workflows/") or path.name in {".gitlab-ci.yml", "Jenkinsfile"}:
            artifacts["ci"].append(r)
        if path.name == ".ros_debug_project.yaml" or lower.startswith("project_knowledge/"):
            artifacts["knowledge"].append(r)
        text = safe_text(path)
        if text:
            combined_text_parts.append(text[:200_000])

    combined = "\n".join(combined_text_parts).lower()
    capabilities = {
        "ros1_signals": any(x in combined for x in ["ros::nodehandle", "catkin_package", "rospy.", "nodelet"]),
        "ros2_signals": any(x in combined for x in ["rclcpp::", "rclpy.", "ament_cmake", "rosidl_generate_interfaces"]),
        "lifecycle": any(x in combined for x in ["lifecyclenode", "rclcpp_lifecycle", "lifecycle_msgs"]),
        "components": any(x in combined for x in ["rclcpp_components", "rclcpp_components_register_node"]),
        "callback_groups": any(x in combined for x in ["create_callback_group", "callbackgroup", "reentrantcallbackgroup"]),
        "ros2_control": any(x in combined for x in ["ros2_control", "controller_manager", "hardware_interface"]),
        "nav2": "nav2_" in combined or "nav2" in combined,
        "moveit": "moveit" in combined,
        "lidar": any(x in combined for x in ["lidar", "pointcloud2", "velodyne", "ouster", "livox"]),
        "imu": any(x in combined for x in ["sensor_msgs::msg::imu", "sensor_msgs/imu", "imu"]),
        "gnss_rtk": any(x in combined for x in ["navsatfix", "gnss", "rtk", "gps"]),
        "tf": any(x in combined for x in ["tf2", "transformbroadcaster", "static_transform_publisher"]),
        "custom_interfaces": bool(artifacts["interfaces"]),
    }

    branch = run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    commit = run_git(root, "rev-parse", "HEAD")
    status = run_git(root, "status", "--porcelain")
    model = {
        "schema_version": 1,
        "status": "measured",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": {
            "path": str(root),
            "branch": branch or "unknown",
            "commit": commit or "unknown",
            "dirty": bool(status) if status is not None else None,
        },
        "environment": {
            key: os.environ.get(key)
            for key in ("ROS_VERSION", "ROS_DISTRO", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY", "AMENT_PREFIX_PATH", "CMAKE_PREFIX_PATH")
            if os.environ.get(key) is not None
        },
        "packages": packages,
        "artifacts": {key: sorted(set(value)) for key, value in artifacts.items()},
        "capabilities": capabilities,
        "coverage": {
            "understanding_level": "L1",
            "static_scan": True,
            "build_verified": False,
            "runtime_snapshot": False,
            "reproduction": False,
            "regression_verified": False,
        },
        "limitations": [
            "Static repository scan only; runtime graph and effective parameters were not observed.",
            "Regex and file-layout detection are indexes, not proof of runtime behavior.",
            "Build, bag, hardware, timing, QoS compatibility, and regression results were not verified.",
        ],
    }

    if args.format == "yaml":
        text = yaml.safe_dump(model, allow_unicode=True, sort_keys=False)
    else:
        text = json.dumps(model, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

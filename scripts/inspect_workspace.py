#!/usr/bin/env python3
"""Build a read-only ROS 1 Noetic static fact model for a workspace/repository."""
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
    ".git", ".idea", ".vscode", "build", "devel", "install", "log", "logs",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules",
}
TEXT_SUFFIXES = {
    ".cpp", ".cc", ".cxx", ".c", ".hpp", ".h", ".py", ".xml", ".yaml", ".yml",
    ".launch", ".xacro", ".urdf", ".msg", ".srv", ".action",
}
TEXT_NAMES = {"CMakeLists.txt", "setup.py", "setup.cfg", "package.xml"}
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_PER_CAPABILITY = 12

SIGNALS: dict[str, dict[str, list[str]]] = {
    "ros1_signals": {
        "observed": [r"\bros::nodehandle\b", r"\brospy\.(?:publisher|subscriber|init_node)\b", r"\bcatkin_package\s*\("],
        "candidate": [r"\b(?:roscpp|rospy|catkin)\b"],
    },
    "catkin": {
        "observed": [r"\bcatkin_package\s*\(", r"\bfind_package\s*\(\s*catkin\b"],
        "candidate": [r"\bcatkin\b"],
    },
    "nodelet": {
        "observed": [r"\bnodelet::nodelet\b", r"\bpluginlib_export_class\s*\([^\)]*nodelet::nodelet"],
        "candidate": [r"\bnodelet\b"],
    },
    "actionlib": {
        "observed": [r"\bactionlib::(?:simpleactionserver|simpleactionclient)\b", r"\bactionlib\.simpleaction(?:server|client)\b"],
        "candidate": [r"\bactionlib\b"],
    },
    "dynamic_reconfigure": {
        "observed": [r"\bdynamic_reconfigure::server\b", r"\bdynamic_reconfigure\.server\b", r"\bgenerate_dynamic_reconfigure_options\s*\("],
        "candidate": [r"\bdynamic_reconfigure\b"],
    },
    "pluginlib": {
        "observed": [r"\bpluginlib_export_class\s*\(", r"\bpluginlib::classloader\b"],
        "candidate": [r"\bpluginlib\b"],
    },
    "ros_control": {
        "observed": [r"\bcontroller_interface::", r"\bhardware_interface::robot_hw\b", r"\bcontroller_manager::"],
        "candidate": [r"\bros_control\b", r"\bcontroller_manager\b"],
    },
    "move_base": {
        "observed": [r"\bmove_base_msgs\b", r"\bbase_local_planner\b", r"\bcostmap_2d\b"],
        "candidate": [r"\bmove_base\b"],
    },
    "lidar": {
        "observed": [r"\bpointcloud2\b", r"\b(?:velodyne|ouster|livox)_[a-z0-9_]+"],
        "candidate": [r"\b(?:lidar|velodyne|ouster|livox)\b"],
    },
    "imu": {
        "observed": [r"\bsensor_msgs(?:::|/)imu\b", r"\bsensor_msgs\.msg\.imu\b"],
        "candidate": [r"\bimu\b"],
    },
    "gnss_rtk": {
        "observed": [r"\bnavsatfix\b", r"\b(?:gnss|rtk)_[a-z0-9_]+"],
        "candidate": [r"\b(?:gnss|rtk|gps)\b"],
    },
    "tf": {
        "observed": [r"\b(?:static)?transformbroadcaster\b", r"\btf2_ros(?:::|\.)", r"\btf::transformbroadcaster\b"],
        "candidate": [r"\btf2\b", r"\bstatic_transform_publisher\b", r"\btf\b"],
    },
    # Foreign ROS 2 signals are intentionally detected so this Noetic branch can flag a version mismatch.
    "ros2_signals": {
        "observed": [r"\brclcpp::", r"\brclpy\.(?:node|init|create_node)\b", r"\brosidl_generate_interfaces\s*\(", r"\bament_target_dependencies\s*\("],
        "candidate": [r"\b(?:rclcpp|rclpy|ament_cmake|ros2)\b"],
    },
    # Kept as foreign-compatibility evidence for old validation fixtures; never interpreted as Noetic capabilities.
    "lifecycle": {
        "observed": [r"\blifecyclenode\b", r"\bon_(?:configure|activate|deactivate|cleanup|shutdown)\s*\(", r"\btrigger_transition\s*\("],
        "candidate": [r"\b(?:rclcpp_lifecycle|rclpy\.lifecycle|lifecycle_msgs)\b"],
    },
    "components": {
        "observed": [r"\brclcpp_components_register_nodes?\s*\(", r"\brclcpp_components::nodefactory\b"],
        "candidate": [r"\brclcpp_components\b"],
    },
    "callback_groups": {
        "observed": [r"\bcreate_callback_group\s*\(", r"\b(?:reentrant|mutuallyexclusive)callbackgroup\b"],
        "candidate": [r"\bcallbackgroup\b"],
    },
}

FOREIGN_ROS2_CAPABILITIES = {"ros2_signals", "lifecycle", "components", "callback_groups"}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], text=True, capture_output=True,
            timeout=5, check=False,
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


def safe_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return ""
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def without_comments(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".cpp", ".cc", ".cxx", ".c", ".hpp", ".h"}:
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        return re.sub(r"//.*", " ", text)
    if suffix == ".py":
        return re.sub(r"#.*", " ", text)
    if suffix in {".xml", ".xacro", ".urdf", ".launch"}:
        return re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    if suffix in {".yaml", ".yml"}:
        return re.sub(r"#.*", " ", text)
    return text


def parse_package(path: Path, root: Path) -> dict[str, Any]:
    package_root = path.parent
    data: dict[str, Any] = {
        "name": package_root.name,
        "path": rel(package_root, root),
        "format": "unknown",
        "build_type": "catkin",
        "version": "unknown",
        "dependencies": [],
        "languages": [],
        "executables": [],
        "nodelet_plugins": [],
        "parse_errors": [],
    }
    try:
        pkg = ET.parse(path).getroot()
        data["format"] = pkg.attrib.get("format", "1")
        if pkg.findtext("name"):
            data["name"] = pkg.findtext("name").strip()
        if pkg.findtext("version"):
            data["version"] = pkg.findtext("version").strip()
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

    package_files = list(iter_files(package_root))
    implementation_files = [
        p for p in package_files
        if not {"launch", "config", "params", "test", "tests", "doc", "docs"}.intersection(
            {part.lower() for part in p.relative_to(package_root).parts[:-1]}
        ) and p.name not in {"setup.py", "conftest.py"}
    ]
    suffixes = {p.suffix.lower() for p in implementation_files}
    if suffixes.intersection({".cpp", ".cc", ".cxx", ".c", ".hpp", ".h"}):
        data["languages"].append("c++")
    if ".py" in suffixes:
        data["languages"].append("python")

    cmake = package_root / "CMakeLists.txt"
    if cmake.is_file():
        text = cmake.read_text(encoding="utf-8", errors="replace")
        data["executables"] = sorted(set(re.findall(r"add_executable\s*\(\s*([^\s\)]+)", text)))
        data["nodelet_plugins"] = sorted(set(re.findall(r"pluginlib_export_class\s*\(\s*([^\s\)]+)", text, re.IGNORECASE)))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.workspace.resolve()
    if not root.is_dir():
        raise SystemExit(f"workspace not found: {root}")

    files = list(iter_files(root))
    packages = [parse_package(p, root) for p in sorted(p for p in files if p.name == "package.xml")]

    artifacts: dict[str, list[str]] = {
        "launch": [], "parameters": [], "interfaces": [], "dynamic_reconfigure": [],
        "urdf_xacro": [], "plugins": [], "docker": [], "systemd_udev": [], "tests": [],
        "bags": [], "ci": [], "knowledge": [],
    }
    evidence = {name: {"observed": [], "candidate": []} for name in SIGNALS}

    for path in files:
        r = rel(path, root)
        lower = r.lower()
        suffix = path.suffix.lower()
        if lower.endswith(".launch") or "/launch/" in f"/{lower}":
            if suffix in {".xml", ".launch"}:
                artifacts["launch"].append(r)
        if ("/config/" in f"/{lower}" or "/params/" in f"/{lower}") and suffix in {".yaml", ".yml", ".json"}:
            artifacts["parameters"].append(r)
        if any(f"/{kind}/" in f"/{lower}" for kind in ("msg", "srv", "action")) and suffix in {".msg", ".srv", ".action"}:
            artifacts["interfaces"].append(r)
        if "/cfg/" in f"/{lower}" and suffix == ".cfg":
            artifacts["dynamic_reconfigure"].append(r)
        if suffix in {".urdf", ".xacro"}:
            artifacts["urdf_xacro"].append(r)
        if path.name == "plugin.xml" or "plugins.xml" in lower or "nodelet" in path.name.lower() and suffix == ".xml":
            artifacts["plugins"].append(r)
        if path.name.startswith("Dockerfile") or path.name in {"docker-compose.yml", "docker-compose.yaml"}:
            artifacts["docker"].append(r)
        if suffix in {".service", ".rules"} or "/udev/" in f"/{lower}" or "/systemd/" in f"/{lower}":
            artifacts["systemd_udev"].append(r)
        if "/test" in lower or path.name.startswith("test_") or path.name.endswith("_test.cpp") or suffix == ".test":
            artifacts["tests"].append(r)
        if suffix == ".bag":
            artifacts["bags"].append(r)
        if lower.startswith(".github/workflows/") or path.name in {".gitlab-ci.yml", "Jenkinsfile"}:
            artifacts["ci"].append(r)
        if path.name == ".ros_debug_project.yaml" or lower.startswith("project_knowledge/"):
            artifacts["knowledge"].append(r)

        text = safe_text(path).lower()
        if not text or lower.startswith(".github/"):
            continue
        strong_text = without_comments(path, text)
        strong_allowed = path.name not in {"package.xml", "setup.py", "setup.cfg"}
        for capability, levels in SIGNALS.items():
            for level in ("observed", "candidate"):
                if level == "observed" and not strong_allowed:
                    continue
                if len(evidence[capability][level]) >= MAX_EVIDENCE_PER_CAPABILITY:
                    continue
                signal_text = strong_text if level == "observed" else text
                for pattern in levels[level]:
                    match = re.search(pattern, signal_text, re.IGNORECASE)
                    if match:
                        evidence[capability][level].append({"path": r, "signal": match.group(0)[:120]})
                        break

    capability_evidence: dict[str, dict[str, Any]] = {}
    capabilities: dict[str, bool] = {}
    for name in SIGNALS:
        observed = evidence[name]["observed"]
        candidates = evidence[name]["candidate"]
        status = "observed" if observed else "candidate" if candidates else "unknown"
        capability_evidence[name] = {
            "status": status,
            "confidence": "medium" if observed else "low" if candidates else "none",
            "evidence": observed or candidates,
            "limitation": "Static signal only; runtime activation and behavior are not proven.",
            "role": "foreign_ros2_signal" if name in FOREIGN_ROS2_CAPABILITIES else "noetic_capability",
        }
        capabilities[name] = bool(observed)

    custom = [{"path": p, "signal": "custom ROS 1 interface definition"} for p in artifacts["interfaces"][:MAX_EVIDENCE_PER_CAPABILITY]]
    capabilities["custom_interfaces"] = bool(custom)
    capability_evidence["custom_interfaces"] = {
        "status": "observed" if custom else "unknown", "confidence": "high" if custom else "none",
        "evidence": custom, "limitation": "Definition presence does not prove message generation, MD5 compatibility, build success, or runtime use.",
        "role": "noetic_capability",
    }

    foreign_ros2 = any(capabilities.get(name, False) or capability_evidence[name]["status"] == "candidate" for name in FOREIGN_ROS2_CAPABILITIES)
    env = {
        key: os.environ.get(key)
        for key in ("ROS_VERSION", "ROS_DISTRO", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME", "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH")
        if os.environ.get(key) is not None
    }
    env_match = env.get("ROS_VERSION") in {None, "1"} and env.get("ROS_DISTRO") in {None, "noetic"}

    model = {
        "schema_version": 2,
        "status": "observed",
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": {
            "path": str(root),
            "branch": run_git(root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown",
            "commit": run_git(root, "rev-parse", "HEAD") or "unknown",
            "dirty": bool(run_git(root, "status", "--porcelain") or ""),
        },
        "environment": env,
        "compatibility": {
            "environment_matches_noetic_if_known": env_match,
            "foreign_ros2_signals_detected": foreign_ros2,
            "decision": "review_version_mismatch" if foreign_ros2 or not env_match else "noetic_candidate",
        },
        "packages": packages,
        "artifacts": {key: sorted(set(value)) for key, value in artifacts.items()},
        "capabilities": capabilities,
        "capability_evidence": capability_evidence,
        "coverage": {
            "understanding_level": "L1", "static_scan": True, "build_verified": False,
            "runtime_snapshot": False, "reproduction": False, "regression_verified": False,
        },
        "limitations": [
            "Static repository scan only; ROS master graph, TCPROS data path, effective parameters and TF freshness were not observed.",
            "Observed means a static source/config signal was found; it is not a runtime measurement.",
            "Dependency-only and generic keyword matches remain candidates.",
            "catkin build, roslaunch behavior, message MD5 compatibility, rosbag1, hardware, timing and regression results were not verified.",
            "ROS 2 signals are reported only as version-mismatch evidence and must not route this Noetic Skill into ROS 2 debugging semantics.",
        ],
    }

    text = yaml.safe_dump(model, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(model, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

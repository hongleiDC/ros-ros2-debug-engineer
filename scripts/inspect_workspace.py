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
    ".git", ".idea", ".vscode", "build", "install", "log",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules",
}
TEXT_SUFFIXES = {".cpp", ".cc", ".cxx", ".c", ".hpp", ".h", ".py", ".xml", ".yaml", ".yml", ".launch", ".xacro", ".urdf"}
TEXT_NAMES = {"CMakeLists.txt", "setup.py", "setup.cfg", "package.xml"}
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_PER_CAPABILITY = 12

SIGNALS: dict[str, dict[str, list[str]]] = {
    "ros1_signals": {
        "observed": [r"\bros::nodehandle\b", r"\brospy\.(?:publisher|subscriber|init_node)\b", r"\bcatkin_package\s*\("],
        "candidate": [r"\b(?:roscpp|rospy|catkin)\b"],
    },
    "ros2_signals": {
        "observed": [r"\brclcpp::", r"\brclpy\.(?:node|init|create_node)\b", r"\brosidl_generate_interfaces\s*\("],
        "candidate": [r"\b(?:rclcpp|rclpy|ament_cmake)\b"],
    },
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
    "ros2_control": {
        "observed": [r"\bhardware_interface::", r"\bcontroller_interface::", r"\bcontroller_manager\b"],
        "candidate": [r"\bros2_control\b", r"\bhardware_interface\b"],
    },
    "nav2": {"observed": [r"\bnav2_[a-z0-9_]+"], "candidate": [r"\bnav2\b"]},
    "moveit": {"observed": [r"\bmoveit::", r"\bmoveit_[a-z0-9_]+"], "candidate": [r"\bmoveit\b"]},
    "lidar": {
        "observed": [r"\bpointcloud2\b", r"\b(?:velodyne|ouster|livox)_[a-z0-9_]+"],
        "candidate": [r"\b(?:lidar|velodyne|ouster|livox)\b"],
    },
    "imu": {
        "observed": [r"\bsensor_msgs(?:::msg::|/msg/|/)imu\b", r"\bsensor_msgs\.msg\.imu\b"],
        "candidate": [r"\bimu\b"],
    },
    "gnss_rtk": {
        "observed": [r"\bnavsatfix\b", r"\b(?:gnss|rtk)_[a-z0-9_]+"],
        "candidate": [r"\b(?:gnss|rtk|gps)\b"],
    },
    "tf": {
        "observed": [r"\b(?:static)?transformbroadcaster\b", r"\btf2_ros(?:::|\.)"],
        "candidate": [r"\btf2\b", r"\bstatic_transform_publisher\b"],
    },
}


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
    implementation_files = [
        p for p in package_files
        if not {"launch", "config", "params", "test", "tests", "doc", "docs"}.intersection(
            {part.lower() for part in p.relative_to(package_root).parts[:-1]}
        )
        and p.name not in {"setup.py", "conftest.py"}
    ]
    suffixes = {p.suffix.lower() for p in implementation_files}
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
        if path.stat().st_size > MAX_TEXT_BYTES or (path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES):
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def without_comments(path: Path, text: str) -> str:
    """Reduce strong-signal promotions caused by ordinary source comments."""
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
    evidence: dict[str, dict[str, list[dict[str, str]]]] = {
        name: {"observed": [], "candidate": []} for name in SIGNALS
    }
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
        text = safe_text(path).lower()
        if not text:
            continue
        if lower.startswith(".github/"):
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
        status_name = "observed" if observed else "candidate" if candidates else "unknown"
        capability_evidence[name] = {
            "status": status_name,
            "confidence": "medium" if observed else "low" if candidates else "none",
            "evidence": observed or candidates,
            "limitation": "Static signal only; runtime activation and behavior are not proven.",
        }
        capabilities[name] = bool(observed)
    custom_evidence = [{"path": path, "signal": "custom interface definition"} for path in artifacts["interfaces"][:MAX_EVIDENCE_PER_CAPABILITY]]
    capabilities["custom_interfaces"] = bool(custom_evidence)
    capability_evidence["custom_interfaces"] = {
        "status": "observed" if custom_evidence else "unknown",
        "confidence": "high" if custom_evidence else "none",
        "evidence": custom_evidence,
        "limitation": "Definition presence does not prove generation, build success, or runtime use.",
    }

    branch = run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    commit = run_git(root, "rev-parse", "HEAD")
    status = run_git(root, "status", "--porcelain")
    model = {
        "schema_version": 1,
        "status": "observed",
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
        "capability_evidence": capability_evidence,
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
            "Evidence status 'observed' means a static source/config signal was found; it is not a runtime measurement.",
            "Dependency-only and generic keyword matches remain candidates and do not set capability booleans.",
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

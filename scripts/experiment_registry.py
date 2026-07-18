#!/usr/bin/env python3
"""Create immutable ROS experiment plans, block duplicates, and record results."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ID_RE = re.compile(r"^EXP-[0-9]{4,}$")
DEP_NAMES = {"package.xml", "CMakeLists.txt", "setup.py", "setup.cfg", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock"}
DEP_SUFFIXES = (".repos", ".rosinstall")
EXCLUDED = {".git", "build", "install", "log", "dist", "__pycache__", ".venv", "venv"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(workspace: Path, *args: str) -> str | None:
    result = subprocess.run(["git", "-C", str(workspace), *args], text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def dependency_snapshot(workspace: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(workspace).parts):
            continue
        if path.name in DEP_NAMES or path.name.startswith("requirements") and path.suffix == ".txt" or path.name.startswith("Dockerfile") or path.suffix in DEP_SUFFIXES:
            result.append({"path": path.relative_to(workspace).as_posix(), "sha256": file_sha(path)})
    return result


def dirty_hash(workspace: Path) -> tuple[bool, str | None]:
    status = git(workspace, "status", "--porcelain=v1", "--untracked-files=all") or ""
    if not status:
        return False, None
    diff = git(workspace, "diff", "--binary", "HEAD") or ""
    payload = status.encode() + b"\0" + diff.encode()
    for line in status.splitlines():
        if line.startswith("?? "):
            path = (workspace / line[3:]).resolve()
            if path.is_file() and workspace in path.parents:
                payload += b"\0" + line[3:].encode() + b"\0" + path.read_bytes()
    return True, sha(payload)


def input_record(workspace: Path, raw: str, kind: str) -> dict[str, str]:
    path = Path(raw)
    path = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file():
        raise SystemExit(f"input file not found: {path}")
    display = path.relative_to(workspace).as_posix() if workspace in path.parents else str(path)
    return {"kind": kind, "path": display, "sha256": file_sha(path)}


def load_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "references" / "schemas" / "experiment.schema.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(record: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(load_schema(), format_checker=FormatChecker()).iter_errors(record), key=lambda e: list(e.absolute_path))
    if errors:
        raise SystemExit("\n".join(f"{'.'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors))


def fingerprint(record: dict[str, Any]) -> str:
    selected = {
        "mainline": record["scope"]["mainline"],
        "experiment": record["scope"]["experiment"],
        "environment": record["environment"],
        "dependencies": record["dependencies"],
        "inputs": record["inputs"],
        "changes": record["changes"],
        "commands": record["procedure"]["commands"],
    }
    return sha(json.dumps(selected, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def records(folder: Path) -> list[dict[str, Any]]:
    found = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                found.append(data)
        except Exception:
            continue
    return found


def create(args: argparse.Namespace) -> int:
    if not ID_RE.fullmatch(args.experiment_id):
        raise SystemExit("experiment_id must match EXP-0001")
    knowledge = args.knowledge.resolve()
    workspace = args.workspace.resolve()
    folder = knowledge / "experiments"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{args.experiment_id}.yaml"
    if target.exists():
        raise SystemExit(f"experiment already exists: {args.experiment_id}")
    dirty, dirty_fp = dirty_hash(workspace)
    current = git(workspace, "rev-parse", "HEAD") or "unknown"
    mainline = args.mainline_commit or git(workspace, "rev-parse", args.mainline_branch) or "unknown"
    env_names = ["ROS_VERSION", "ROS_DISTRO", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY"]
    files = [input_record(workspace, p, "data") for p in args.input_file]
    files += [input_record(workspace, p, "parameters") for p in args.parameter_file]
    created = now()
    record: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": args.experiment_id,
        "title": args.title,
        "status": "planned",
        "created_at": created,
        "updated_at": created,
        "objective": args.objective,
        "hypothesis": args.hypothesis,
        "scope": {
            "repository": {"path": str(workspace), "remote": git(workspace, "config", "--get", "remote.origin.url")},
            "mainline": {"branch": args.mainline_branch, "commit": mainline},
            "experiment": {"branch": git(workspace, "branch", "--show-current") or "unknown", "commit": current, "dirty": dirty, "dirty_fingerprint": dirty_fp},
            "parent_experiment_ids": args.parent,
            "compare_to_experiment_ids": args.compare_to,
        },
        "environment": {
            "ros_version": os.getenv("ROS_VERSION"), "ros_distro": os.getenv("ROS_DISTRO"),
            "rmw_implementation": os.getenv("RMW_IMPLEMENTATION"), "ros_domain_id": os.getenv("ROS_DOMAIN_ID"),
            "operating_system": platform.platform(), "architecture": platform.machine() or "unknown",
            "container_image": os.getenv("CONTAINER_IMAGE"), "container_digest": os.getenv("CONTAINER_IMAGE_DIGEST"),
            "middleware_config": {"ros_localhost_only": os.getenv("ROS_LOCALHOST_ONLY")},
            "environment_variables": {k: os.getenv(k) for k in env_names if os.getenv(k) is not None},
        },
        "dependencies": {"manifests": dependency_snapshot(workspace), "declared": args.dependency, "firmware": args.firmware},
        "inputs": {"references": args.input, "files": files, "devices": args.device, "calibrations": args.calibration},
        "changes": [{"description": text} for text in args.change],
        "procedure": {"commands": args.command, "steps": args.step, "expected": args.expected, "safety_constraints": args.safety, "metrics": [{"name": m.split(":", 1)[0]} for m in args.metric]},
        "fingerprint": {"algorithm": "sha256-v1", "value": "0" * 64, "fields": ["mainline", "experiment", "environment", "dependencies", "inputs", "changes", "commands"]},
        "duplicate_check": {"checked_at": created, "exact_match_ids": [], "similar_match_ids": [], "override_reason": args.duplicate_reason},
        "results": {"outcome": "not_run", "run_started_at": None, "run_finished_at": None, "summary": None, "metrics": [], "observations": [], "artifacts": [], "logs": [], "failures": []},
        "conclusion": {"verdict": "pending", "confidence": "low", "summary": None, "lessons": [], "next_actions": []},
    }
    record["fingerprint"]["value"] = fingerprint(record)
    matches = [r.get("experiment_id") for r in records(folder) if r.get("fingerprint", {}).get("value") == record["fingerprint"]["value"]]
    record["duplicate_check"]["exact_match_ids"] = [m for m in matches if isinstance(m, str)]
    if matches and not args.allow_duplicate:
        raise SystemExit(f"duplicate experiment blocked; matching IDs: {', '.join(matches)}")
    if matches and (not args.duplicate_reason or len(args.duplicate_reason.strip()) < 12):
        raise SystemExit("--allow-duplicate requires a specific --duplicate-reason of at least 12 characters")
    validate(record)
    target.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(target)
    return 0


def finish(args: argparse.Namespace) -> int:
    target = args.knowledge.resolve() / "experiments" / f"{args.experiment_id}.yaml"
    if not target.is_file():
        raise SystemExit(f"experiment not found: {args.experiment_id}")
    record = yaml.safe_load(target.read_text(encoding="utf-8"))
    record["status"] = args.status
    record["updated_at"] = now()
    record["results"].update({"outcome": args.outcome, "run_finished_at": now(), "summary": args.summary})
    record["results"]["observations"].extend(args.observation)
    record["results"]["failures"].extend(args.failure)
    for raw in args.artifact:
        path_text, _, description = raw.partition(":")
        path = Path(path_text).resolve()
        record["results"]["artifacts"].append({"path": str(path), "sha256": file_sha(path), "description": description or path.name})
    record["conclusion"].update({"verdict": args.verdict, "confidence": args.confidence, "summary": args.summary, "lessons": args.lesson, "next_actions": args.next_action})
    validate(record)
    target.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(target)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="action", required=True)
    create_p = commands.add_parser("create")
    create_p.add_argument("knowledge", type=Path); create_p.add_argument("experiment_id"); create_p.add_argument("title")
    create_p.add_argument("--workspace", type=Path, required=True); create_p.add_argument("--objective", required=True); create_p.add_argument("--hypothesis", required=True)
    create_p.add_argument("--mainline-branch", default="main"); create_p.add_argument("--mainline-commit")
    for name in ("input", "input-file", "parameter-file", "dependency", "firmware", "device", "calibration", "change", "step", "safety", "metric", "parent", "compare-to"):
        create_p.add_argument(f"--{name}", action="append", default=[])
    create_p.add_argument("--command", action="append", required=True); create_p.add_argument("--expected", action="append", required=True)
    create_p.add_argument("--allow-duplicate", action="store_true"); create_p.add_argument("--duplicate-reason")
    create_p.set_defaults(func=create)
    finish_p = commands.add_parser("finish")
    finish_p.add_argument("knowledge", type=Path); finish_p.add_argument("experiment_id")
    finish_p.add_argument("--status", choices=["completed", "aborted", "inconclusive"], required=True)
    finish_p.add_argument("--outcome", choices=["pass", "fail", "mixed", "error"], required=True)
    finish_p.add_argument("--summary", required=True); finish_p.add_argument("--verdict", choices=["supported", "rejected", "inconclusive", "superseded"], required=True)
    finish_p.add_argument("--confidence", choices=["low", "medium", "high"], required=True)
    for name in ("observation", "failure", "artifact", "lesson", "next-action"):
        finish_p.add_argument(f"--{name}", action="append", default=[])
    finish_p.set_defaults(func=finish)
    return root


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(args.func(args))

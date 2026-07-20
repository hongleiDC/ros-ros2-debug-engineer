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

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:
    raise SystemExit("Missing dependency 'jsonschema'. Run: python3 scripts/preflight.py --require knowledge") from None
import yaml

from goal_utils import active_goal, atomic_write_yaml, contract_hash, find_goal
from lock_utils import file_lock
from workspace_fingerprint import dirty_hash

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
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def dependency_snapshot(workspace: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(workspace).parts):
            continue
        if path.name in DEP_NAMES or path.name.startswith("requirements") and path.suffix == ".txt" or path.name.startswith("Dockerfile") or path.suffix in DEP_SUFFIXES:
            result.append({"path": path.relative_to(workspace).as_posix(), "sha256": file_sha(path)})
    return result


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


def similarity_fingerprint(record: dict[str, Any]) -> str:
    """Detect semantically repeated procedures even when commit or host details differ."""
    selected = {
        "objective": record["objective"],
        "hypothesis": record["hypothesis"],
        "inputs": record["inputs"],
        "changes": record["changes"],
        "commands": record["procedure"]["commands"],
        "expected": record["procedure"]["expected"],
        "metrics": record["procedure"].get("metrics", []),
    }
    return sha(json.dumps(selected, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def resolve_goal_alignment(args: argparse.Namespace, knowledge: Path) -> dict[str, Any]:
    state = (args.goal_state or knowledge).resolve()
    try:
        _, goal = find_goal(state, args.goal_id) if args.goal_id else active_goal(state)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if goal.get("status") != "active":
        raise SystemExit(f"goal {goal.get('goal_id')} is not active")
    criteria = {
        item.get("criterion_id"): item
        for item in goal.get("contract", {}).get("success_criteria", [])
        if isinstance(item, dict) and isinstance(item.get("criterion_id"), str)
    }
    selected = list(dict.fromkeys(args.criterion))
    if not selected:
        pending = [key for key, value in criteria.items() if value.get("status") == "pending"]
        if len(pending) == 1:
            selected = pending
        else:
            raise SystemExit("--criterion is required when the active goal has zero or multiple pending criteria")
    missing = [item for item in selected if item not in criteria]
    if missing:
        raise SystemExit(f"unknown goal criteria: {', '.join(missing)}")
    milestones = {
        item.get("milestone_id"): item
        for item in goal.get("progress", {}).get("milestones", [])
        if isinstance(item, dict) and isinstance(item.get("milestone_id"), str)
    }
    milestone = args.milestone or goal.get("progress", {}).get("current_milestone_id")
    if milestone not in milestones:
        raise SystemExit(f"unknown goal milestone: {milestone}")
    if not args.alignment or len(args.alignment.strip()) < 12:
        raise SystemExit("--alignment must explain how the experiment advances the active goal")
    expected_hash = contract_hash(goal)
    if goal.get("contract_hash") != expected_hash:
        raise SystemExit("active goal contract hash is invalid; repair the goal record before experimenting")
    return {
        "goal_id": goal["goal_id"],
        "contract_hash": goal["contract_hash"],
        "primary_goal_snapshot": goal["contract"]["primary_goal"],
        "criterion_ids": selected,
        "milestone_id": milestone,
        "alignment_reason": args.alignment.strip(),
    }


def records(folder: Path) -> list[dict[str, Any]]:
    found = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                found.append(data)
        except Exception as exc:
            raise SystemExit(f"cannot check duplicates because {path} is invalid: {exc}") from exc
    return found


def create(args: argparse.Namespace) -> int:
    if not ID_RE.fullmatch(args.experiment_id):
        raise SystemExit("experiment_id must match EXP-0001")
    knowledge = args.knowledge.resolve()
    workspace = args.workspace.resolve()
    folder = knowledge / "experiments"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{args.experiment_id}.yaml"
    goal_state = (args.goal_state or knowledge).resolve()
    dirty, dirty_fp = dirty_hash(workspace, [knowledge, goal_state])
    current = git(workspace, "rev-parse", "HEAD") or "unknown"
    mainline = args.mainline_commit or git(workspace, "rev-parse", args.mainline_branch) or "unknown"
    env_names = ["ROS_VERSION", "ROS_DISTRO", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY"]
    files = [input_record(workspace, p, "data") for p in args.input_file]
    files += [input_record(workspace, p, "parameters") for p in args.parameter_file]
    created = now()
    goal_alignment = resolve_goal_alignment(args, knowledge)
    record: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": args.experiment_id,
        "title": args.title,
        "status": "planned",
        "created_at": created,
        "updated_at": created,
        "objective": args.objective,
        "hypothesis": args.hypothesis,
        "goal_alignment": goal_alignment,
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
    similar_value = similarity_fingerprint(record)
    with file_lock(folder / ".experiment-registry.lock"):
        if target.exists():
            raise SystemExit(f"experiment already exists: {args.experiment_id}")
        existing = records(folder)
        matches = [r.get("experiment_id") for r in existing if r.get("fingerprint", {}).get("value") == record["fingerprint"]["value"]]
        similar = [
            r.get("experiment_id") for r in existing
            if r.get("fingerprint", {}).get("value") != record["fingerprint"]["value"]
            and similarity_fingerprint(r) == similar_value
        ]
        record["duplicate_check"]["exact_match_ids"] = [m for m in matches if isinstance(m, str)]
        record["duplicate_check"]["similar_match_ids"] = [m for m in similar if isinstance(m, str)]
        if matches and not args.allow_duplicate:
            raise SystemExit(f"duplicate experiment blocked; matching IDs: {', '.join(matches)}")
        if matches and (not args.duplicate_reason or len(args.duplicate_reason.strip()) < 12):
            raise SystemExit("--allow-duplicate requires a specific --duplicate-reason of at least 12 characters")
        validate(record)
        atomic_write_yaml(target, record)
    print(target)
    return 0


def start_run(args: argparse.Namespace) -> int:
    folder = args.knowledge.resolve() / "experiments"
    target = folder / f"{args.experiment_id}.yaml"
    with file_lock(folder / ".experiment-registry.lock"):
        if not target.is_file():
            raise SystemExit(f"experiment not found: {args.experiment_id}")
        record = yaml.safe_load(target.read_text(encoding="utf-8"))
        if record.get("status") != "planned":
            raise SystemExit(f"experiment must be planned before start; current status: {record.get('status')}")
        timestamp = now()
        record["status"] = "running"
        record["updated_at"] = timestamp
        record["results"]["run_started_at"] = timestamp
        validate(record)
        atomic_write_yaml(target, record)
    print(target)
    return 0


def finish(args: argparse.Namespace) -> int:
    folder = args.knowledge.resolve() / "experiments"
    target = folder / f"{args.experiment_id}.yaml"
    if not target.is_file():
        raise SystemExit(f"experiment not found: {args.experiment_id}")
    record = yaml.safe_load(target.read_text(encoding="utf-8"))
    if record.get("status") != "running":
        raise SystemExit("experiment must be started before it can be finished")
    original_updated_at = record.get("updated_at")
    record["status"] = args.status
    record["updated_at"] = now()
    record["results"].update({"outcome": args.outcome, "run_finished_at": now(), "summary": args.summary})
    record["results"]["observations"].extend(args.observation)
    record["results"]["failures"].extend(args.failure)
    workspace = Path(record.get("scope", {}).get("repository", {}).get("path", ".")).resolve()

    def result_file(raw: str) -> tuple[Path, str]:
        path_text, _, description = raw.partition(":")
        path = Path(path_text)
        path = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_file():
            raise SystemExit(f"result file not found: {path}")
        return path, description or path.name

    for raw in args.metric:
        parts = raw.split(":", 2)
        name_value = parts[0]
        unit = parts[1] if len(parts) > 1 and parts[1] else None
        comparison = parts[2] if len(parts) > 2 and parts[2] else None
        name, separator, value_text = name_value.partition("=")
        if not separator or not name.strip() or not value_text.strip():
            raise SystemExit("result metric must use name=value[:unit[:comparison]]")
        value: Any
        try:
            value = int(value_text)
        except ValueError:
            try:
                value = float(value_text)
            except ValueError:
                value = value_text
        record["results"]["metrics"].append({
            "name": name.strip(), "value": value, "unit": unit, "comparison": comparison,
        })
    for raw in args.artifact:
        path, description = result_file(raw)
        record["results"]["artifacts"].append({"path": str(path), "sha256": file_sha(path), "description": description})
    for raw in args.log:
        path, description = result_file(raw)
        record["results"]["logs"].append({"path": str(path), "sha256": file_sha(path), "description": description})
    record["conclusion"].update({"verdict": args.verdict, "confidence": args.confidence, "summary": args.summary, "lessons": args.lesson, "next_actions": args.next_action})
    validate(record)
    with file_lock(folder / ".experiment-registry.lock"):
        latest = yaml.safe_load(target.read_text(encoding="utf-8"))
        if latest.get("status") != "running" or latest.get("updated_at") != original_updated_at:
            raise SystemExit("experiment changed while results were being prepared; retry finish")
        atomic_write_yaml(target, record)
    print(target)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="action", required=True)
    create_p = commands.add_parser("create")
    create_p.add_argument("knowledge", type=Path); create_p.add_argument("experiment_id"); create_p.add_argument("title")
    create_p.add_argument("--workspace", type=Path, required=True); create_p.add_argument("--objective", required=True); create_p.add_argument("--hypothesis", required=True)
    create_p.add_argument("--goal-state", type=Path); create_p.add_argument("--goal-id")
    create_p.add_argument("--criterion", action="append", default=[]); create_p.add_argument("--milestone")
    create_p.add_argument("--alignment", required=True)
    create_p.add_argument("--mainline-branch", default="main"); create_p.add_argument("--mainline-commit")
    for name in ("input", "input-file", "parameter-file", "dependency", "firmware", "device", "calibration", "change", "step", "safety", "metric", "parent", "compare-to"):
        create_p.add_argument(f"--{name}", action="append", default=[])
    create_p.add_argument("--command", action="append", required=True); create_p.add_argument("--expected", action="append", required=True)
    create_p.add_argument("--allow-duplicate", action="store_true"); create_p.add_argument("--duplicate-reason")
    create_p.set_defaults(func=create)
    start_p = commands.add_parser("start")
    start_p.add_argument("knowledge", type=Path); start_p.add_argument("experiment_id")
    start_p.set_defaults(func=start_run)
    finish_p = commands.add_parser("finish")
    finish_p.add_argument("knowledge", type=Path); finish_p.add_argument("experiment_id")
    finish_p.add_argument("--status", choices=["completed", "aborted", "inconclusive"], required=True)
    finish_p.add_argument("--outcome", choices=["pass", "fail", "mixed", "error"], required=True)
    finish_p.add_argument("--summary", required=True); finish_p.add_argument("--verdict", choices=["supported", "rejected", "inconclusive", "superseded"], required=True)
    finish_p.add_argument("--confidence", choices=["low", "medium", "high"], required=True)
    for name in ("observation", "failure", "artifact", "log", "metric", "lesson", "next-action"):
        finish_p.add_argument(f"--{name}", action="append", default=[])
    finish_p.set_defaults(func=finish)
    return root


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(args.func(args))

#!/usr/bin/env python3
"""Persist task goals, re-anchor long debugging sessions, and block goal drift."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from goal_utils import active_goal, atomic_write_yaml, contract_hash, find_goal, goal_folder, goal_records

GOAL_RE = re.compile(r"^GOAL-[0-9]{4,}$")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(workspace: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dirty_hash(workspace: Path) -> tuple[bool, str | None]:
    status = git(workspace, "status", "--porcelain=v1", "--untracked-files=all") or ""
    if not status:
        return False, None
    diff = git(workspace, "diff", "--binary", "HEAD") or ""
    payload = status.encode("utf-8") + b"\0" + diff.encode("utf-8")
    for line in status.splitlines():
        if not line.startswith("?? "):
            continue
        candidate = (workspace / line[3:]).resolve()
        if candidate.is_file() and (candidate == workspace or workspace in candidate.parents):
            payload += b"\0" + line[3:].encode("utf-8") + b"\0" + candidate.read_bytes()
    return True, sha(payload)


def load_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "references" / "schemas" / "goal.schema.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(record: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda item: list(item.absolute_path))
    if errors:
        text = "\n".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise SystemExit(text)
    actual = contract_hash(record)
    if record.get("contract_hash") != actual:
        raise SystemExit("contract_hash does not match the current goal contract")


@contextmanager
def state_lock(state_root: Path) -> Iterator[None]:
    state_root = state_root.resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / ".goal-guard.lock"
    with lock_path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def parse_success(values: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(values, start=1):
        description, separator, evidence = raw.partition("::")
        description = description.strip()
        evidence = evidence.strip() if separator else "Direct command, test, log, metric, or code evidence"
        if not description:
            raise SystemExit("success criterion description cannot be empty")
        if not evidence:
            raise SystemExit("success criterion evidence requirement cannot be empty")
        result.append({
            "criterion_id": f"SC-{index}",
            "description": description,
            "evidence_required": evidence,
            "status": "pending",
            "evidence": [],
            "waiver_reason": None,
        })
    return result


def parse_milestones(values: list[str]) -> list[dict[str, Any]]:
    result = []
    for index, value in enumerate(values, start=1):
        text = value.strip()
        if not text:
            raise SystemExit("milestone description cannot be empty")
        result.append({
            "milestone_id": f"M-{index}",
            "description": text,
            "status": "in_progress" if index == 1 else "pending",
            "evidence": [],
        })
    return result


def checkpoint_id(record: dict[str, Any]) -> str:
    return f"CP-{len(record.get('checkpoints', [])) + 1:04d}"


def criterion_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["criterion_id"]: item
        for item in record["contract"]["success_criteria"]
        if isinstance(item, dict) and isinstance(item.get("criterion_id"), str)
    }


def milestone_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["milestone_id"]: item
        for item in record["progress"]["milestones"]
        if isinstance(item, dict) and isinstance(item.get("milestone_id"), str)
    }


def require_criteria(record: dict[str, Any], values: list[str] | None) -> list[str]:
    available = criterion_map(record)
    selected = values or [
        item["criterion_id"]
        for item in record["contract"]["success_criteria"]
        if item.get("status") == "pending"
    ][:1]
    if not selected:
        raise SystemExit("no active success criterion; select one explicitly")
    missing = [item for item in selected if item not in available]
    if missing:
        raise SystemExit(f"unknown success criteria: {', '.join(missing)}")
    return list(dict.fromkeys(selected))


def require_milestone(record: dict[str, Any], value: str | None) -> str:
    selected = value or record["progress"].get("current_milestone_id")
    if not selected:
        raise SystemExit("no current milestone")
    milestones = milestone_map(record)
    if selected not in milestones:
        raise SystemExit(f"unknown milestone: {selected}")
    if milestones[selected]["status"] in {"completed", "skipped"}:
        raise SystemExit(f"milestone {selected} is already {milestones[selected]['status']}")
    return selected


def append_checkpoint(
    record: dict[str, Any],
    *,
    trigger: str,
    criteria: list[str],
    milestone: str,
    drift_status: str,
    drift_reason: str | None,
    proposed_action: str | None,
    alignment_reason: str | None,
    expected_evidence: str | None,
    action_completed: str | None,
    evidence: list[str],
    decision: str,
    next_action: str,
) -> None:
    timestamp = now()
    record["checkpoints"].append({
        "checkpoint_id": checkpoint_id(record),
        "timestamp": timestamp,
        "trigger": trigger,
        "goal_restatement": record["contract"]["primary_goal"],
        "active_criterion_ids": criteria,
        "milestone_id": milestone,
        "drift_status": drift_status,
        "drift_reason": drift_reason,
        "proposed_action": proposed_action,
        "alignment_reason": alignment_reason,
        "expected_evidence": expected_evidence,
        "action_completed": action_completed,
        "evidence": evidence,
        "decision": decision,
        "next_action": next_action,
    })
    record["updated_at"] = timestamp
    record["progress"]["last_checkpoint_at"] = timestamp
    record["progress"]["current_milestone_id"] = milestone
    record["progress"]["next_action"] = next_action
    record["progress"]["drift_status"] = drift_status
    record["progress"]["drift_reason"] = drift_reason


def print_anchor(record: dict[str, Any]) -> None:
    milestones = milestone_map(record)
    current_id = record["progress"].get("current_milestone_id")
    current = milestones.get(current_id or "", {})
    payload = {
        "goal_id": record["goal_id"],
        "status": record["status"],
        "primary_goal": record["contract"]["primary_goal"],
        "contract_hash": record["contract_hash"],
        "success_criteria": [
            {
                "criterion_id": item["criterion_id"],
                "status": item["status"],
                "description": item["description"],
            }
            for item in record["contract"]["success_criteria"]
        ],
        "current_milestone": {
            "milestone_id": current_id,
            "status": current.get("status"),
            "description": current.get("description"),
        },
        "current_summary": record["progress"]["current_summary"],
        "next_action": record["progress"]["next_action"],
        "drift_status": record["progress"]["drift_status"],
        "drift_reason": record["progress"]["drift_reason"],
        "non_goals": record["contract"]["non_goals"],
        "constraints": record["contract"]["constraints"],
    }
    print(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).rstrip())


def start(args: argparse.Namespace) -> int:
    if not GOAL_RE.fullmatch(args.goal_id):
        raise SystemExit("goal_id must match GOAL-0001")
    if len(args.primary_goal.strip()) < 12:
        raise SystemExit("primary goal must be concrete and at least 12 characters")
    if not args.success:
        raise SystemExit("at least one --success criterion is required")
    if not args.milestone:
        raise SystemExit("at least one --milestone is required")
    state = args.state.resolve()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        raise SystemExit(f"workspace not found: {workspace}")
    with state_lock(state):
        existing_ids = {data.get("goal_id") for _, data in goal_records(state)}
        if args.goal_id in existing_ids:
            raise SystemExit(f"goal already exists: {args.goal_id}")
        current_active = [(path, data) for path, data in goal_records(state) if data.get("status") == "active"]
        if current_active:
            if not args.supersede_active:
                ids = ", ".join(str(data.get("goal_id")) for _, data in current_active)
                raise SystemExit(f"active goal already exists: {ids}")
            if not args.supersede_reason or len(args.supersede_reason.strip()) < 12:
                raise SystemExit("--supersede-active requires --supersede-reason of at least 12 characters")
            for path, old in current_active:
                old["status"] = "superseded"
                old["updated_at"] = now()
                old["completion"] = {
                    "finished_at": now(),
                    "outcome": "superseded",
                    "summary": args.supersede_reason.strip(),
                    "unresolved": [
                        item["criterion_id"]
                        for item in old["contract"]["success_criteria"]
                        if item.get("status") not in {"met", "waived"}
                    ],
                    "incomplete_reason": args.supersede_reason.strip(),
                }
                validate(old)
                atomic_write_yaml(path, old)

        dirty, dirty_fp = dirty_hash(workspace)
        branch = git(workspace, "branch", "--show-current") or "unknown"
        commit = git(workspace, "rev-parse", "HEAD") or "unknown"
        created = now()
        criteria = parse_success(args.success)
        milestones = parse_milestones(args.milestone)
        record: dict[str, Any] = {
            "schema_version": 1,
            "goal_id": args.goal_id,
            "title": args.title,
            "status": "active",
            "created_at": created,
            "updated_at": created,
            "request": {
                "original_request": args.request,
                "desired_outcome": args.desired_outcome,
                "source": args.source,
            },
            "contract": {
                "primary_goal": args.primary_goal.strip(),
                "success_criteria": criteria,
                "non_goals": args.non_goal,
                "constraints": args.constraint,
                "invariants": args.invariant,
                "stop_conditions": args.stop_condition,
            },
            "contract_hash": "0" * 64,
            "scope": {
                "repository": str(workspace),
                "remote": git(workspace, "config", "--get", "remote.origin.url"),
                "branch": branch,
                "commit": commit,
                "dirty": dirty,
                "dirty_fingerprint": dirty_fp,
                "packages": args.package,
                "files": args.file,
                "interfaces": args.interface,
                "environment": {
                    "operating_system": platform.platform(),
                    "architecture": platform.machine() or "unknown",
                    "ros_version": os.getenv("ROS_VERSION"),
                    "ros_distro": os.getenv("ROS_DISTRO"),
                    "rmw_implementation": os.getenv("RMW_IMPLEMENTATION"),
                },
            },
            "progress": {
                "current_summary": "Goal contract created; no engineering conclusion yet.",
                "current_milestone_id": milestones[0]["milestone_id"],
                "milestones": milestones,
                "blockers": [],
                "next_action": milestones[0]["description"],
                "drift_status": "aligned",
                "drift_reason": None,
                "last_checkpoint_at": created,
            },
            "revisions": [],
            "checkpoints": [],
            "completion": {
                "finished_at": None,
                "outcome": "pending",
                "summary": None,
                "unresolved": [],
                "incomplete_reason": None,
            },
        }
        record["contract_hash"] = contract_hash(record)
        append_checkpoint(
            record,
            trigger="task_start",
            criteria=[criteria[0]["criterion_id"]],
            milestone=milestones[0]["milestone_id"],
            drift_status="aligned",
            drift_reason=None,
            proposed_action=None,
            alignment_reason=None,
            expected_evidence=None,
            action_completed="Goal contract established.",
            evidence=[],
            decision="Proceed only through actions linked to a success criterion.",
            next_action=milestones[0]["description"],
        )
        validate(record)
        target = goal_folder(state) / f"{args.goal_id}.yaml"
        atomic_write_yaml(target, record)
        print(target)
        print_anchor(record)
    return 0


def show(args: argparse.Namespace) -> int:
    try:
        _, record = find_goal(args.state.resolve(), args.goal_id) if args.goal_id else active_goal(args.state.resolve())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    validate(record)
    print_anchor(record)
    return 0


def guard(args: argparse.Namespace) -> int:
    if len(args.alignment.strip()) < 12:
        raise SystemExit("--alignment must explain how the action advances the goal")
    if len(args.expected_evidence.strip()) < 5:
        raise SystemExit("--expected-evidence is too vague")
    state = args.state.resolve()
    with state_lock(state):
        try:
            path, record = active_goal(state)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if record["progress"]["drift_status"] == "drifted":
            raise SystemExit("goal is marked drifted; obtain user direction and revise or checkpoint before continuing")
        criteria = require_criteria(record, args.criterion)
        milestone = require_milestone(record, args.milestone)
        milestones = milestone_map(record)
        if milestones[milestone]["status"] == "pending":
            milestones[milestone]["status"] = "in_progress"
        append_checkpoint(
            record,
            trigger="pre_action",
            criteria=criteria,
            milestone=milestone,
            drift_status=record["progress"]["drift_status"],
            drift_reason=record["progress"]["drift_reason"],
            proposed_action=args.action,
            alignment_reason=args.alignment,
            expected_evidence=args.expected_evidence,
            action_completed=None,
            evidence=[],
            decision="Action structurally approved against the selected goal criterion.",
            next_action=args.action,
        )
        validate(record)
        atomic_write_yaml(path, record)
        print_anchor(record)
    return 0


def checkpoint(args: argparse.Namespace) -> int:
    if args.drift_status in {"at_risk", "drifted"} and (not args.drift_reason or len(args.drift_reason.strip()) < 8):
        raise SystemExit("at_risk or drifted checkpoints require a specific --drift-reason")
    state = args.state.resolve()
    with state_lock(state):
        try:
            path, record = active_goal(state)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        criteria = require_criteria(record, args.criterion)
        milestone = require_milestone(record, args.milestone)
        milestones = milestone_map(record)
        if args.complete_milestone:
            milestones[milestone]["status"] = "completed"
            milestones[milestone]["evidence"].extend(args.evidence)
            pending = [item for item in record["progress"]["milestones"] if item["status"] == "pending"]
            if pending:
                pending[0]["status"] = "in_progress"
                milestone = pending[0]["milestone_id"]
        record["progress"]["current_summary"] = args.summary
        record["progress"]["blockers"] = args.blocker
        append_checkpoint(
            record,
            trigger=args.trigger,
            criteria=criteria,
            milestone=milestone,
            drift_status=args.drift_status,
            drift_reason=args.drift_reason,
            proposed_action=None,
            alignment_reason=None,
            expected_evidence=None,
            action_completed=args.summary,
            evidence=args.evidence,
            decision=args.decision,
            next_action=args.next_action,
        )
        validate(record)
        atomic_write_yaml(path, record)
        print_anchor(record)
    return 0


def set_criterion(args: argparse.Namespace) -> int:
    state = args.state.resolve()
    with state_lock(state):
        try:
            path, record = active_goal(state)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        criteria = criterion_map(record)
        if args.criterion_id not in criteria:
            raise SystemExit(f"unknown success criterion: {args.criterion_id}")
        if args.status in {"met", "failed", "waived"} and not args.evidence:
            raise SystemExit(f"criterion status {args.status} requires at least one --evidence")
        if args.status == "waived" and (not args.waiver_reason or len(args.waiver_reason.strip()) < 12):
            raise SystemExit("waived criterion requires --waiver-reason of at least 12 characters")
        item = criteria[args.criterion_id]
        item["status"] = args.status
        item["evidence"] = args.evidence
        item["waiver_reason"] = args.waiver_reason
        record["updated_at"] = now()
        validate(record)
        atomic_write_yaml(path, record)
        print_anchor(record)
    return 0


def revise(args: argparse.Namespace) -> int:
    if not args.user_authorized:
        raise SystemExit("goal revision requires explicit --user-authorized")
    if len(args.reason.strip()) < 12 or len(args.authorization_evidence.strip()) < 8:
        raise SystemExit("revision reason and authorization evidence must be specific")
    state = args.state.resolve()
    with state_lock(state):
        try:
            path, record = active_goal(state)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        old_hash = record["contract_hash"]
        if args.primary_goal:
            record["contract"]["primary_goal"] = args.primary_goal.strip()
        for raw in args.add_success:
            existing = record["contract"]["success_criteria"]
            description, separator, evidence = raw.partition("::")
            evidence = evidence.strip() if separator else "Direct command, test, log, metric, or code evidence"
            existing.append({
                "criterion_id": f"SC-{len(existing) + 1}",
                "description": description.strip(),
                "evidence_required": evidence,
                "status": "pending",
                "evidence": [],
                "waiver_reason": None,
            })
        for text in args.add_non_goal:
            record["contract"]["non_goals"].append(text)
        for text in args.add_constraint:
            record["contract"]["constraints"].append(text)
        for text in args.add_milestone:
            milestones = record["progress"]["milestones"]
            milestones.append({
                "milestone_id": f"M-{len(milestones) + 1}",
                "description": text,
                "status": "pending",
                "evidence": [],
            })
        record["contract_hash"] = contract_hash(record)
        record["revisions"].append({
            "timestamp": now(),
            "old_contract_hash": old_hash,
            "new_contract_hash": record["contract_hash"],
            "reason": args.reason,
            "user_authorized": True,
            "authorization_evidence": args.authorization_evidence,
        })
        record["progress"]["drift_status"] = "aligned"
        record["progress"]["drift_reason"] = None
        record["updated_at"] = now()
        validate(record)
        atomic_write_yaml(path, record)
        print_anchor(record)
    return 0


def finish(args: argparse.Namespace) -> int:
    state = args.state.resolve()
    with state_lock(state):
        try:
            path, record = active_goal(state)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        unresolved = [
            item["criterion_id"]
            for item in record["contract"]["success_criteria"]
            if item.get("status") not in {"met", "waived"}
        ]
        if args.outcome == "completed" and unresolved:
            if not args.allow_incomplete or not args.incomplete_reason or len(args.incomplete_reason.strip()) < 12:
                raise SystemExit(
                    "cannot complete with unresolved criteria: " + ", ".join(unresolved) +
                    "; use paused/cancelled or provide an explicit incomplete override"
                )
        record["status"] = args.outcome
        record["updated_at"] = now()
        record["completion"] = {
            "finished_at": now(),
            "outcome": args.outcome,
            "summary": args.summary,
            "unresolved": unresolved,
            "incomplete_reason": args.incomplete_reason,
        }
        validate(record)
        atomic_write_yaml(path, record)
        print_anchor(record)
    return 0


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="action", required=True)

    start_p = commands.add_parser("start")
    start_p.add_argument("state", type=Path)
    start_p.add_argument("goal_id")
    start_p.add_argument("title")
    start_p.add_argument("--workspace", type=Path, required=True)
    start_p.add_argument("--request", required=True)
    start_p.add_argument("--desired-outcome", required=True)
    start_p.add_argument("--primary-goal", required=True)
    start_p.add_argument("--source")
    for name in ("success", "non-goal", "constraint", "invariant", "stop-condition", "milestone", "package", "file", "interface"):
        start_p.add_argument(f"--{name}", action="append", default=[])
    start_p.add_argument("--supersede-active", action="store_true")
    start_p.add_argument("--supersede-reason")
    start_p.set_defaults(func=start)

    show_p = commands.add_parser("show")
    show_p.add_argument("state", type=Path)
    show_p.add_argument("--goal-id")
    show_p.set_defaults(func=show)

    guard_p = commands.add_parser("guard")
    guard_p.add_argument("state", type=Path)
    guard_p.add_argument("--criterion", action="append", default=[])
    guard_p.add_argument("--milestone")
    guard_p.add_argument("--action", required=True)
    guard_p.add_argument("--alignment", required=True)
    guard_p.add_argument("--expected-evidence", required=True)
    guard_p.set_defaults(func=guard)

    checkpoint_p = commands.add_parser("checkpoint")
    checkpoint_p.add_argument("state", type=Path)
    checkpoint_p.add_argument("--trigger", choices=["tool_batch", "code_change", "experiment", "failure", "user_correction", "handoff", "resume", "manual"], required=True)
    checkpoint_p.add_argument("--criterion", action="append", default=[])
    checkpoint_p.add_argument("--milestone")
    checkpoint_p.add_argument("--summary", required=True)
    checkpoint_p.add_argument("--evidence", action="append", default=[])
    checkpoint_p.add_argument("--blocker", action="append", default=[])
    checkpoint_p.add_argument("--decision", required=True)
    checkpoint_p.add_argument("--next-action", required=True)
    checkpoint_p.add_argument("--drift-status", choices=["aligned", "at_risk", "drifted"], required=True)
    checkpoint_p.add_argument("--drift-reason")
    checkpoint_p.add_argument("--complete-milestone", action="store_true")
    checkpoint_p.set_defaults(func=checkpoint)

    criterion_p = commands.add_parser("criterion")
    criterion_p.add_argument("state", type=Path)
    criterion_p.add_argument("criterion_id")
    criterion_p.add_argument("--status", choices=["pending", "met", "failed", "waived"], required=True)
    criterion_p.add_argument("--evidence", action="append", default=[])
    criterion_p.add_argument("--waiver-reason")
    criterion_p.set_defaults(func=set_criterion)

    revise_p = commands.add_parser("revise")
    revise_p.add_argument("state", type=Path)
    revise_p.add_argument("--primary-goal")
    revise_p.add_argument("--add-success", action="append", default=[])
    revise_p.add_argument("--add-non-goal", action="append", default=[])
    revise_p.add_argument("--add-constraint", action="append", default=[])
    revise_p.add_argument("--add-milestone", action="append", default=[])
    revise_p.add_argument("--reason", required=True)
    revise_p.add_argument("--user-authorized", action="store_true")
    revise_p.add_argument("--authorization-evidence", required=True)
    revise_p.set_defaults(func=revise)

    finish_p = commands.add_parser("finish")
    finish_p.add_argument("state", type=Path)
    finish_p.add_argument("--outcome", choices=["completed", "paused", "cancelled", "superseded"], required=True)
    finish_p.add_argument("--summary", required=True)
    finish_p.add_argument("--allow-incomplete", action="store_true")
    finish_p.add_argument("--incomplete-reason")
    finish_p.set_defaults(func=finish)
    return root


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    raise SystemExit(parsed.func(parsed))

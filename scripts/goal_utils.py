#!/usr/bin/env python3
"""Shared helpers for persistent task-goal records."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import os
import tempfile

import yaml


def goal_folder(state_root: Path) -> Path:
    return state_root.resolve() / "goals"


def load_goal(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"goal record is not a mapping: {path}")
    return data


def goal_records(state_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    folder = goal_folder(state_root)
    result: list[tuple[Path, dict[str, Any]]] = []
    if not folder.is_dir():
        return result
    for path in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
        try:
            result.append((path, load_goal(path)))
        except Exception:
            continue
    return result


def find_goal(state_root: Path, goal_id: str) -> tuple[Path, dict[str, Any]]:
    matches = [(path, data) for path, data in goal_records(state_root) if data.get("goal_id") == goal_id]
    if not matches:
        raise ValueError(f"goal not found: {goal_id}")
    if len(matches) > 1:
        raise ValueError(f"duplicate goal id: {goal_id}")
    return matches[0]


def active_goal(state_root: Path) -> tuple[Path, dict[str, Any]]:
    matches = [(path, data) for path, data in goal_records(state_root) if data.get("status") == "active"]
    if not matches:
        raise ValueError("no active goal; start one with goal_guard.py start")
    if len(matches) > 1:
        ids = ", ".join(str(data.get("goal_id")) for _, data in matches)
        raise ValueError(f"multiple active goals are not allowed: {ids}")
    return matches[0]


def contract_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_goal": record.get("contract", {}).get("primary_goal"),
        "success_criteria": [
            {
                "criterion_id": item.get("criterion_id"),
                "description": item.get("description"),
                "evidence_required": item.get("evidence_required"),
            }
            for item in record.get("contract", {}).get("success_criteria", [])
        ],
        "non_goals": record.get("contract", {}).get("non_goals", []),
        "constraints": record.get("contract", {}).get("constraints", []),
        "invariants": record.get("contract", {}).get("invariants", []),
        "stop_conditions": record.get("contract", {}).get("stop_conditions", []),
        "scope": record.get("scope", {}),
    }


def contract_hash(record: dict[str, Any]) -> str:
    payload = json.dumps(contract_payload(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

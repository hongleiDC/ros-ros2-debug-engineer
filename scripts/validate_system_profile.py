#!/usr/bin/env python3
"""Validate a ROS 1 Noetic system profile and report baseline readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def validate_profile(profile: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(profile)]
    risk = profile.get("risk", {}) if isinstance(profile.get("risk"), dict) else {}
    conflicts = risk.get("conflicts", []) if isinstance(risk.get("conflicts"), list) else []
    unknowns = risk.get("unknowns", []) if isinstance(risk.get("unknowns"), list) else []
    target = profile.get("target", {}) if isinstance(profile.get("target"), dict) else {}
    if target.get("ros_version") != "1" or target.get("ros_distro") != "noetic":
        errors.append("target must be ROS 1 Noetic")
    if conflicts:
        readiness = "not_ready"
    elif unknowns:
        readiness = "partial"
    else:
        readiness = "ready"
    return {
        "schema_version": 1,
        "validation_kind": "ros_noetic_system_profile_validation",
        "valid": not errors,
        "baseline_readiness": readiness,
        "errors": errors,
        "warnings": [f"{len(unknowns)} unknown evidence items"] if unknowns else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--require-baseline-ready", action="store_true")
    args = parser.parse_args()
    schema = args.schema or Path(__file__).resolve().parents[1] / "references" / "schemas" / "robot_profile.schema.yaml"
    result = validate_profile(load_mapping(args.profile), load_mapping(schema))
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    if not result["valid"]:
        return 2
    if args.require_baseline_ready and result["baseline_readiness"] != "ready":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

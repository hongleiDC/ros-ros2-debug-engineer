#!/usr/bin/env python3
"""Validate a target ROS project's knowledge directory with JSON Schema."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from schema_utils import validate_knowledge


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("knowledge_dir", type=Path)
    parser.add_argument(
        "--schema-dir", type=Path,
        default=Path(__file__).resolve().parents[1] / "references" / "schemas",
    )
    args = parser.parse_args()
    errors = validate_knowledge(args.knowledge_dir, args.schema_dir)
    if errors:
        print("knowledge validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    count = len(list(args.knowledge_dir.rglob("*")))
    print(f"knowledge validation passed: {args.knowledge_dir} ({count} entries)")
    print("note: structural validation does not prove that engineering facts are true")
    return 0


if __name__ == "__main__":
    sys.exit(main())

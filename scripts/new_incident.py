#!/usr/bin/env python3
"""Create a validated structured incident without path traversal or overwrite."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re

import yaml

from schema_utils import validate_knowledge

INCIDENT_ID = re.compile(r"^INC-[0-9]{4,}$")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "incident"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path, help="project_knowledge directory")
    parser.add_argument("incident_id", help="e.g. INC-0006")
    parser.add_argument("title")
    args = parser.parse_args()

    if not INCIDENT_ID.fullmatch(args.incident_id):
        raise SystemExit("incident_id must match INC-0001")
    if not args.title.strip():
        raise SystemExit("title must not be empty")

    knowledge = args.project_dir.resolve()
    out_dir = (knowledge / "incidents").resolve()
    if knowledge != out_dir and knowledge not in out_dir.parents:
        raise SystemExit("incident directory escapes project knowledge")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / f"{args.incident_id}-{slugify(args.title)}.yaml").resolve()
    if out_dir not in out.parents:
        raise SystemExit("incident path escapes incidents directory")
    if out.exists():
        raise SystemExit(f"refusing to overwrite: {out}")

    data = {
        "schema_version": 1,
        "incident_id": args.incident_id,
        "title": args.title.strip(),
        "status": "open",
        "date": date.today().isoformat(),
        "symptom": "TODO",
        "hypotheses": [],
        "root_cause": None,
        "evidence": [],
        "fix": None,
        "regression": [],
        "forbidden_regressions": [],
    }
    out.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    schema_dir = Path(__file__).resolve().parents[1] / "references" / "schemas"
    errors = validate_knowledge(knowledge, schema_dir)
    if errors:
        out.unlink(missing_ok=True)
        for error in errors:
            print(f"- {error}")
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

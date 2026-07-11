#!/usr/bin/env python3
"""Create a standard incident record without overwriting existing files."""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "incident"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("project_dir", type=Path)
    p.add_argument("incident_id", help="e.g. INC-0006")
    p.add_argument("title")
    args = p.parse_args()
    out_dir = args.project_dir / "incidents"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.incident_id}-{slugify(args.title)}.md"
    if out.exists():
        raise SystemExit(f"refusing to overwrite: {out}")
    out.write_text(f"""# {args.incident_id} {args.title}\n\n- status: open\n- date: {date.today().isoformat()}\n\n## symptom\n\nTODO\n\n## root_cause\n\nTODO\n\n## evidence\n\nTODO\n\n## fix\n\nTODO\n\n## regression\n\nTODO\n\n## forbidden_regressions\n\nTODO\n""", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

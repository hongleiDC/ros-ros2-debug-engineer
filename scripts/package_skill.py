#!/usr/bin/env python3
"""Validate the Skill structure and create skill.zip."""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
import yaml

MAX_BYTES = 25 * 1024 * 1024
EXCLUDED = {".git", ".github", "__pycache__", ".pytest_cache", "dist", ".venv", "venv"}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    agent = root / "agents" / "openai.yaml"
    if not skill.is_file():
        return ["missing SKILL.md"]
    if not agent.is_file():
        errors.append("missing agents/openai.yaml")
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        errors.append("SKILL.md must start with YAML frontmatter")
    else:
        frontmatter = yaml.safe_load(match.group(1))
        if not isinstance(frontmatter, dict) or set(frontmatter) != {"name", "description"}:
            errors.append("frontmatter must contain only name and description")
        else:
            name = frontmatter.get("name")
            description = frontmatter.get("description")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                errors.append("name must be lowercase kebab-case")
            if not isinstance(description, str) or not description.strip():
                errors.append("description must be non-empty")
            elif description != description.lower():
                errors.append("description must be lowercase")
    for reference in re.findall(r"\((references/[^)]+)\)", text):
        if not (root / reference).exists():
            errors.append(f"missing referenced resource: {reference}")
    return errors


def files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if path.name in {"skill.zip", ".DS_Store"} or path.suffix == ".pyc":
            continue
        yield path, relative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output_dir", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root)
    if errors:
        print("skill validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "skill.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, relative in files(root):
            archive.write(path, relative.as_posix())
    if output.stat().st_size > MAX_BYTES:
        output.unlink()
        print("skill.zip exceeds 25 MB")
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

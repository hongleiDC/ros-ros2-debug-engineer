#!/usr/bin/env python3
"""Validate the Skill structure and create an exact skill.zip bundle."""
from __future__ import annotations

import argparse
import py_compile
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import yaml

MAX_BYTES = 25 * 1024 * 1024
EXCLUDED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", ".venv", "venv"}
BUNDLE_EXCLUDED_ROOTS = {".github", "tests"}
BUNDLE_EXCLUDED_FILES = {"README.md", "LICENSE", "LICENSE.md"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def validate_frontmatter(root: Path, errors: list[str]) -> None:
    skill = root / "SKILL.md"
    if not skill.is_file():
        errors.append("missing SKILL.md")
        return
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        errors.append("SKILL.md must start with YAML frontmatter")
        return
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"invalid SKILL.md frontmatter: {exc}")
        return
    if not isinstance(frontmatter, dict) or set(frontmatter) != {"name", "description"}:
        errors.append("frontmatter must contain only name and description")
        return
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        errors.append("name must be lowercase kebab-case")
    if not isinstance(description, str) or len(description.strip()) < 40:
        errors.append("description must clearly describe capability and triggering context")


def validate_agent(root: Path, errors: list[str]) -> None:
    path = root / "agents" / "openai.yaml"
    if not path.is_file():
        errors.append("missing agents/openai.yaml")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"invalid agents/openai.yaml: {exc}")
        return
    interface = data.get("interface") if isinstance(data, dict) else None
    if not isinstance(interface, dict):
        errors.append("agents/openai.yaml must contain interface mapping")
        return
    for key in ("display_name", "short_description", "default_prompt"):
        if not isinstance(interface.get(key), str) or not interface[key].strip():
            errors.append(f"agents/openai.yaml missing interface.{key}")
    default_prompt = interface.get("default_prompt", "")
    if isinstance(default_prompt, str) and "$ros-ros2-debug-engineer" not in default_prompt:
        errors.append("agents/openai.yaml interface.default_prompt must mention $ros-ros2-debug-engineer")


def validate_links(root: Path, errors: list[str]) -> None:
    for markdown in root.rglob("*.md"):
        if any(part in EXCLUDED for part in markdown.relative_to(root).parts):
            continue
        text = markdown.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean = target.split("#", 1)[0]
            if clean and not (markdown.parent / clean).resolve().exists():
                errors.append(f"{markdown.relative_to(root)}: missing linked resource {target}")


def validate_scripts(root: Path, errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for path in sorted((root / "scripts").glob("*.py")):
            try:
                py_compile.compile(str(path), cfile=str(Path(tmp) / f"{path.stem}.pyc"), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"{path.relative_to(root)}: {exc.msg}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    validate_frontmatter(root, errors)
    validate_agent(root, errors)
    validate_links(root, errors)
    validate_scripts(root, errors)
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlinks are not allowed in skill bundle: {path.relative_to(root)}")
    return errors


def files(root: Path) -> Iterable[tuple[Path, Path]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if relative.parts[0] in BUNDLE_EXCLUDED_ROOTS or relative.as_posix() in BUNDLE_EXCLUDED_FILES:
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
    output.unlink(missing_ok=True)
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
